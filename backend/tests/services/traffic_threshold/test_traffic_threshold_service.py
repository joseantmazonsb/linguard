"""Tests for ``app.services.traffic_threshold_service``.

Covers threshold evaluation (direction, validation, boundaries), the helper
formatting APIs and the CRUD/window-aggregation code used by the traffic-trigger
API, all against the real SQLite database.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.peer import Peer
from app.models.server import Server
from app.models.traffic_metric import TrafficMetric
from app.models.traffic_trigger import (
    ThresholdWindow,
    TrafficDirection as ModelDirection,
    TrafficScope,
    TrafficTrigger,
)
from app.services.traffic_threshold_service import (
    TimeWindow,
    TrafficDirection,
    TrafficThresholdService,
)


@pytest.fixture
def service():
    return TrafficThresholdService()


# ===========================================================================
# Threshold evaluation
# ===========================================================================

class TestEvaluateThreshold:
    async def test_should_compare_combined_traffic_against_threshold(self, service):
        metrics = {"1": {"rx_bytes": 600, "tx_bytes": 500}, "2": {"rx_bytes": 100, "tx_bytes": 0}}

        assert await service.evaluate_threshold(1200, metrics) is True
        assert await service.evaluate_threshold(1201, metrics) is False

    async def test_should_treat_exact_threshold_as_exceeded(self, service):
        assert await service.evaluate_threshold(100, {"1": {"rx_bytes": 60, "tx_bytes": 40}}) is True

    async def test_should_only_count_received_bytes_for_inbound(self, service):
        metrics = {"1": {"rx_bytes": 50, "tx_bytes": 1000}}

        assert await service.evaluate_threshold(100, metrics, direction=TrafficDirection.INBOUND) is False
        assert await service.evaluate_threshold(50, metrics, direction=TrafficDirection.INBOUND) is True

    async def test_should_only_count_transmitted_bytes_for_outbound(self, service):
        metrics = {"1": {"rx_bytes": 1000, "tx_bytes": 50}}

        assert await service.evaluate_threshold(100, metrics, direction=TrafficDirection.OUTBOUND) is False
        assert await service.evaluate_threshold(50, metrics, direction=TrafficDirection.OUTBOUND) is True

    async def test_should_sum_the_requested_direction_across_peers(self, service):
        metrics = {
            "1": {"rx_bytes": 10, "tx_bytes": 100},
            "2": {"rx_bytes": 20, "tx_bytes": 100},
        }

        assert await service.evaluate_threshold(30, metrics, direction=TrafficDirection.INBOUND) is True
        assert await service.evaluate_threshold(30, metrics, direction=TrafficDirection.OUTBOUND) is True
        assert await service.evaluate_threshold(231, metrics) is False

    async def test_should_use_traffic_lists_as_metric_source(self, service):
        # ``_get_all_peer_metrics`` understands nested containers (used by
        # callers that pass raw monitor payloads).
        peer_metrics = {"traffic": [{"rx_bytes": 0, "tx_bytes": 30}]}
        assert service._get_all_peer_metrics(peer_metrics) == [{"rx_bytes": 0, "tx_bytes": 30}]
        assert service._get_all_peer_metrics({"metrics": [{"rx_bytes": 1, "tx_bytes": 2}]}) == [
            {"rx_bytes": 1, "tx_bytes": 2}
        ]
        assert service._get_all_peer_metrics({"rx_bytes": 5, "tx_bytes": 6}) == [
            {"rx_bytes": 5, "tx_bytes": 6}
        ]
        assert service._get_all_peer_metrics({}) == []

    async def test_should_return_false_for_empty_metrics(self, service):
        assert await service.evaluate_threshold(1, {}) is False

    @pytest.mark.parametrize(
        "time_window", [w.value for w in TimeWindow]
    )
    async def test_should_accept_every_documented_window(self, service, time_window):
        assert await service.evaluate_threshold(10, {"1": {"rx_bytes": 10, "tx_bytes": 0}},
                                                time_window=time_window) is True

    @pytest.mark.parametrize("threshold", [0, -5])
    async def test_should_reject_non_positive_threshold(self, service, threshold):
        with pytest.raises(ValueError, match="threshold_bytes must be a positive number"):
            await service.evaluate_threshold(threshold, {"1": {"rx_bytes": 1, "tx_bytes": 1}})

    async def test_should_reject_non_numeric_threshold(self, service):
        with pytest.raises(ValueError, match="must be a positive number"):
            await service.evaluate_threshold("1000", {"1": {"rx_bytes": 1, "tx_bytes": 1}})

    async def test_should_reject_unknown_time_window(self, service):
        with pytest.raises(ValueError, match="Invalid time window: last_century"):
            await service.evaluate_threshold(10, {"1": {"rx_bytes": 1, "tx_bytes": 1}},
                                             time_window="last_century")

    @pytest.mark.parametrize(
        "metrics",
        [
            "not-a-dict",
            {"1": "nope"},
            {"1": {"rx_bytes": 1}},
            {"1": {"rx_bytes": "1", "tx_bytes": 1}},
        ],
    )
    async def test_should_reject_malformed_metrics(self, service, metrics):
        with pytest.raises(ValueError, match="Invalid metrics data"):
            await service.evaluate_threshold(10, metrics)


# ===========================================================================
# Formatting / recommendations
# ===========================================================================

class TestHelpers:
    def test_should_recommend_threshold_with_ten_percent_margin(self, service):
        assert service.get_threshold_recommendation(1000) == {
            "recommended_threshold": 1100,
            "reason": "Based on current traffic with 10% safety margin",
            "safety_margin": 100,
            "current_traffic": 1000,
        }

    def test_should_recommend_zero_when_no_traffic(self, service):
        assert service.get_threshold_recommendation(0)["reason"] == "No traffic detected"

    @pytest.mark.parametrize(
        "current, threshold, expected",
        [(50, 100, 50.0), (150, 100, 150.0), (10, 0, 0.0), (10, -1, 0.0)],
    )
    def test_should_calculate_percentage_of_threshold(self, service, current, threshold, expected):
        assert service.calculate_traffic_percent(current, threshold) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0 B"),
            (512, "512 B"),
            (1024, "1 KB"),
            (1536, "1.5 KB"),
            (1024 ** 2, "1 MB"),
            (int(1.5 * 1024 ** 3), "1.5 GB"),
            (1024 ** 4, "1 TB"),
            (1024 ** 5, "1024 TB"),
        ],
    )
    def test_should_format_bytes_human_readably(self, service, value, expected):
        assert service.format_traffic_bytes(value) == expected

    def test_should_describe_known_and_unknown_windows(self, service):
        assert service.get_time_window_description("last_24_hours") == "Last 24 hours"
        assert service.get_time_window_description("forever") == "Unknown period"

    def test_should_validate_threshold_configuration(self, service):
        assert service.validate_threshold_config(
            {"threshold_bytes": 100, "time_window": "last_hour", "direction": "inbound"}
        ) == []

        errors = service.validate_threshold_config({"time_window": "weekly", "direction": "sideways"})
        assert "threshold_bytes is required" in errors
        assert "Invalid time window: weekly" in errors
        assert "Invalid direction: sideways" in errors

        assert service.validate_threshold_config(
            {"threshold_bytes": -1, "time_window": "last_hour"}
        ) == ["threshold_bytes must be a positive number"]


class TestPeerAndBatchEvaluation:
    async def test_should_evaluate_each_enabled_threshold(self, service):
        results = await service.evaluate_peer_thresholds(
            peer_id="7",
            peer_metrics={"rx_bytes": 500, "tx_bytes": 500},
            thresholds=[
                {"threshold_bytes": 100, "time_window": "last_hour", "direction": "combined"},
                {"threshold_bytes": 5000, "time_window": "last_24_hours", "direction": "inbound"},
            ],
        )

        assert [r["exceeded"] for r in results] == [True, False]
        assert results[0]["status"] == "evaluated"
        assert results[0]["current_bytes"] == 1000

    async def test_should_mark_disabled_threshold_as_skipped(self, service):
        results = await service.evaluate_peer_thresholds(
            "7", {"rx_bytes": 10, "tx_bytes": 0},
            [{"threshold_bytes": 1, "enabled": False, "time_window": "last_hour"}],
        )

        assert results[0]["exceeded"] is False
        assert results[0]["status"] == "skipped"
        assert results[0]["reason"] == "Threshold is disabled"

    async def test_should_report_configuration_errors_per_threshold(self, service):
        results = await service.evaluate_peer_thresholds(
            "7", {"rx_bytes": 10, "tx_bytes": 0},
            [{"threshold_bytes": 0, "time_window": "last_hour"}],
        )

        assert results[0]["status"] == "error"
        assert results[0]["exceeded"] is False
        assert "positive number" in results[0]["reason"]

    async def test_should_report_missing_peer_data_in_batch(self, service):
        results = await service.batch_evaluate_thresholds(
            peer_ids=["1", "2"],
            peer_metrics={"1": {"rx_bytes": 100, "tx_bytes": 0}},
            thresholds=[{"threshold_bytes": 50, "time_window": "last_hour"}],
        )

        assert results["1"][0]["exceeded"] is True
        assert results["2"][0]["status"] == "no_data"


# ===========================================================================
# CRUD
# ===========================================================================

async def make_server(db, name="srv"):
    server = Server(name=name, public_key="a" * 44, private_key="b" * 44, listen_port=51820,
                    ipv4_address="10.8.0.1/24")
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def make_trigger(db, name, **kwargs):
    kwargs.setdefault("scope", TrafficScope.GLOBAL)
    kwargs.setdefault("direction", ModelDirection.COMBINED)
    kwargs.setdefault("threshold_bytes", 1_000_000)
    kwargs.setdefault("window", ThresholdWindow.LAST_HOUR)
    trigger = TrafficTrigger(name=name, **kwargs)
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger


class TestTriggerCrud:
    async def test_should_create_and_fetch_trigger(self, service, db_session):
        server = await make_server(db_session)

        trigger = await service.create_trigger(
            db_session, name="hourly", scope=TrafficScope.SERVER, server_id=server.id,
            direction=ModelDirection.RX_ONLY, threshold_bytes=500, window=ThresholdWindow.LAST_HOUR,
        )

        assert trigger.id is not None
        fetched = await service.get_trigger(db_session, trigger.id)
        assert fetched.name == "hourly"
        assert fetched.threshold_bytes == 500
        assert await service.get_trigger(db_session, 9999) is None

    async def test_should_update_existing_trigger(self, service, db_session):
        trigger = await make_trigger(db_session, "old")

        updated = await service.update_trigger(db_session, trigger.id,
                                              name="new", threshold_bytes=42, enabled=False)

        assert updated.name == "new"
        assert updated.threshold_bytes == 42
        assert updated.enabled is False
        await db_session.refresh(trigger)
        assert trigger.name == "new"

    async def test_should_return_none_when_updating_missing_trigger(self, service, db_session):
        assert await service.update_trigger(db_session, 1234, name="ghost") is None

    async def test_should_delete_trigger(self, service, db_session):
        trigger = await make_trigger(db_session, "temp")

        assert await service.delete_trigger(db_session, trigger.id) is True
        assert await service.get_trigger(db_session, trigger.id) is None
        assert await service.delete_trigger(db_session, trigger.id) is False

    async def test_should_filter_triggers(self, service, db_session):
        server = await make_server(db_session, "tokyo")
        peer = Peer(server_id=server.id, name="alice", public_key="c" * 44, private_key="d" * 44)
        db_session.add(peer)
        await db_session.commit()
        await db_session.refresh(peer)

        await make_trigger(db_session, "global-on", enabled=True)
        await make_trigger(db_session, "global-off", enabled=False)
        await make_trigger(db_session, "peer-trigger", scope=TrafficScope.PEER, peer_id=peer.id)
        await make_trigger(db_session, "server-trigger", scope=TrafficScope.SERVER, server_id=server.id)

        enabled = await service.list_triggers(db_session, enabled_only=True)
        assert [t.name for t in enabled] == ["global-on", "peer-trigger", "server-trigger"]

        peer_only = await service.list_triggers(db_session, scope=TrafficScope.PEER)
        assert [t.name for t in peer_only] == ["peer-trigger"]

        by_name = await service.list_triggers(db_session, search="global")
        assert {t.name for t in by_name} == {"global-on", "global-off"}

        by_peer_name = await service.list_triggers(db_session, search="alice")
        assert [t.name for t in by_peer_name] == ["peer-trigger"]

        by_server_name = await service.list_triggers(db_session, search="tokyo")
        assert [t.name for t in by_server_name] == ["server-trigger"]

        paginated = await service.list_triggers(db_session, skip=1, limit=2)
        assert len(paginated) == 2


# ===========================================================================
# Window aggregation & cooldown
# ===========================================================================

class TestWindowAggregation:
    async def _metrics(self, db, *, peer_id=None, server_id=None):
        now = datetime.utcnow()
        db.add_all([
            TrafficMetric(peer_id=peer_id, server_id=server_id, rx_bytes=100, tx_bytes=10,
                          recorded_at=now - timedelta(minutes=5)),
            TrafficMetric(peer_id=peer_id, server_id=server_id, rx_bytes=200, tx_bytes=20,
                          recorded_at=now - timedelta(minutes=30)),
            # outside every window used here
            TrafficMetric(peer_id=peer_id, server_id=server_id, rx_bytes=9999, tx_bytes=9999,
                          recorded_at=now - timedelta(days=60)),
        ])
        await db.commit()

    async def test_should_sum_peer_metrics_inside_window(self, service, db_session):
        server = await make_server(db_session)
        peer = Peer(server_id=server.id, name="alice", public_key="c" * 44, private_key="d" * 44)
        db_session.add(peer)
        await db_session.commit()
        await db_session.refresh(peer)
        await self._metrics(db_session, peer_id=peer.id)

        result = await service.calculate_traffic_in_window(
            db_session, TrafficScope.PEER, ModelDirection.COMBINED, ThresholdWindow.LAST_HOUR,
            peer_id=peer.id,
        )

        assert result == {"total_bytes": 330, "rx_bytes": 300, "tx_bytes": 30, "window": "last_hour"}

    async def test_should_honour_direction(self, service, db_session):
        server = await make_server(db_session)
        await self._metrics(db_session, server_id=server.id)

        inbound = await service.calculate_traffic_in_window(
            db_session, TrafficScope.SERVER, ModelDirection.RX_ONLY, ThresholdWindow.LAST_24_HOURS,
            server_id=server.id,
        )
        outbound = await service.calculate_traffic_in_window(
            db_session, TrafficScope.SERVER, ModelDirection.TX_ONLY, ThresholdWindow.LAST_24_HOURS,
            server_id=server.id,
        )

        assert (inbound["total_bytes"], outbound["total_bytes"]) == (300, 30)

    async def test_should_include_older_metrics_for_long_windows(self, service, db_session):
        server = await make_server(db_session)
        await self._metrics(db_session, server_id=server.id)

        result = await service.calculate_traffic_in_window(
            db_session, TrafficScope.SERVER, ModelDirection.COMBINED, ThresholdWindow.LAST_30_DAYS,
            server_id=server.id,
        )

        assert result["total_bytes"] == 330

    async def test_should_sum_every_server_for_global_scope(self, service, db_session):
        first = await make_server(db_session, "one")
        second = await make_server(db_session, "two")
        await self._metrics(db_session, server_id=first.id)
        await self._metrics(db_session, server_id=second.id)

        result = await service.calculate_traffic_in_window(
            db_session, TrafficScope.GLOBAL, ModelDirection.COMBINED, ThresholdWindow.LAST_7_DAYS,
        )

        assert result["total_bytes"] == 660

    async def test_should_fall_back_to_last_hour_for_unknown_window(self, service, db_session):
        server = await make_server(db_session)
        await self._metrics(db_session, server_id=server.id)

        result = await service.calculate_traffic_in_window(
            db_session, TrafficScope.SERVER, "combined", "whenever", server_id=server.id,
        )

        assert result["window"] == "whenever"
        assert result["total_bytes"] == 330


class TestCooldown:
    def test_should_not_be_in_cooldown_before_first_trigger(self, service):
        trigger = TrafficTrigger(name="t", scope=TrafficScope.GLOBAL,
                                 direction=ModelDirection.COMBINED, threshold_bytes=1,
                                 window=ThresholdWindow.LAST_HOUR, cooldown_seconds=3600)

        assert service._is_in_cooldown(trigger) is False

    def test_should_be_in_cooldown_within_window(self, service):
        trigger = TrafficTrigger(name="t", scope=TrafficScope.GLOBAL,
                                 direction=ModelDirection.COMBINED, threshold_bytes=1,
                                 window=ThresholdWindow.LAST_HOUR, cooldown_seconds=3600)
        trigger.last_triggered_at = datetime.utcnow() - timedelta(minutes=10)

        assert service._is_in_cooldown(trigger) is True

    def test_should_leave_cooldown_after_window(self, service):
        trigger = TrafficTrigger(name="t", scope=TrafficScope.GLOBAL,
                                 direction=ModelDirection.COMBINED, threshold_bytes=1,
                                 window=ThresholdWindow.LAST_HOUR, cooldown_seconds=60)
        trigger.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        assert service._is_in_cooldown(trigger) is False

    def test_should_treat_zero_cooldown_as_never_cooling(self, service):
        trigger = TrafficTrigger(name="t", scope=TrafficScope.GLOBAL,
                                 direction=ModelDirection.COMBINED, threshold_bytes=1,
                                 window=ThresholdWindow.LAST_HOUR, cooldown_seconds=0)
        trigger.last_triggered_at = datetime.now(timezone.utc)

        assert service._is_in_cooldown(trigger) is False


# ===========================================================================
# check_all_triggers (periodic notification fan-out)
# ===========================================================================

class TestCheckAllTriggers:
    async def _traffic(self, db, *, peer_id=None, server_id=None, rx=1000, tx=500):
        db.add(TrafficMetric(peer_id=peer_id, server_id=server_id, rx_bytes=rx, tx_bytes=tx,
                             recorded_at=datetime.utcnow() - timedelta(minutes=1)))
        await db.commit()

    async def test_should_fire_trigger_and_publish_event(self, service, db_session):
        server = await make_server(db_session)
        trigger = await make_trigger(db_session, "burst", scope=TrafficScope.SERVER,
                                     server_id=server.id, threshold_bytes=1000)
        await self._traffic(db_session, server_id=server.id)

        with patch("app.services.traffic_threshold_service.event_bus.publish",
                   new=AsyncMock()) as publish:
            result = await service.check_all_triggers(db_session)

        assert result == {"triggers_checked": 1, "triggers_fired": 1, "fired": ["burst"]}
        await db_session.refresh(trigger)
        assert trigger.total_triggers == 1
        assert trigger.last_triggered_at is not None
        assert trigger.last_checked_at is not None

        publish.assert_awaited_once()
        args = publish.await_args.args
        assert args[0].value == "traffic.threshold_exceeded"
        assert args[1] == "traffic_trigger"
        assert args[2] == trigger.id
        payload = args[3]
        assert payload["total_bytes"] == 1500
        assert payload["threshold_bytes"] == 1000
        assert payload["integration_ids"] == []

    async def test_should_not_fire_when_traffic_is_below_threshold(self, service, db_session):
        server = await make_server(db_session)
        trigger = await make_trigger(db_session, "calm", scope=TrafficScope.SERVER,
                                     server_id=server.id, threshold_bytes=10_000)
        await self._traffic(db_session, server_id=server.id)

        with patch("app.services.traffic_threshold_service.event_bus.publish",
                   new=AsyncMock()) as publish:
            result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 0
        publish.assert_not_awaited()
        await db_session.refresh(trigger)
        assert trigger.total_triggers == 0
        assert trigger.last_triggered_at is None

    async def test_should_skip_disabled_triggers(self, service, db_session):
        server = await make_server(db_session)
        await make_trigger(db_session, "off", scope=TrafficScope.SERVER, server_id=server.id,
                           threshold_bytes=1, enabled=False)
        await self._traffic(db_session, server_id=server.id)

        assert await service.check_all_triggers(db_session) == {
            "triggers_checked": 0, "triggers_fired": 0, "fired": [],
        }

    async def test_should_respect_cooldown_between_firings(self, service, db_session):
        server = await make_server(db_session)
        trigger = await make_trigger(db_session, "cooldown", scope=TrafficScope.SERVER,
                                     server_id=server.id, threshold_bytes=1, cooldown_seconds=3600)
        trigger.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.commit()
        await self._traffic(db_session, server_id=server.id)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_checked"] == 1
        assert result["triggers_fired"] == 0
        await db_session.refresh(trigger)
        assert trigger.last_checked_at is not None

    async def test_should_not_publish_when_event_delivery_is_disabled(self, service, db_session):
        server = await make_server(db_session)
        trigger = await make_trigger(db_session, "silent", scope=TrafficScope.SERVER,
                                     server_id=server.id, threshold_bytes=1, trigger_event=False)
        await self._traffic(db_session, server_id=server.id)

        with patch("app.services.traffic_threshold_service.event_bus.publish",
                   new=AsyncMock()) as publish:
            result = await service.check_all_triggers(db_session)

        assert result["fired"] == ["silent"]
        publish.assert_not_awaited()
        await db_session.refresh(trigger)
        assert trigger.total_triggers == 1

    async def test_should_keep_evaluating_when_one_trigger_fails(self, service, db_session):
        server = await make_server(db_session)
        await make_trigger(db_session, "broken", scope=TrafficScope.SERVER,
                           server_id=server.id, threshold_bytes=1)
        await make_trigger(db_session, "healthy", scope=TrafficScope.SERVER,
                           server_id=server.id, threshold_bytes=1)
        await self._traffic(db_session, server_id=server.id)

        calls = {"n": 0}
        original = service.calculate_traffic_in_window

        async def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("metrics table unavailable")
            return await original(*args, **kwargs)

        service.calculate_traffic_in_window = flaky

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1
        assert result["fired"] == ["healthy"]

    async def test_should_count_rx_only_direction(self, service, db_session):
        server = await make_server(db_session)
        await make_trigger(db_session, "rx", scope=TrafficScope.SERVER, server_id=server.id,
                           threshold_bytes=700, direction=ModelDirection.RX_ONLY)
        await self._traffic(db_session, server_id=server.id, rx=1000, tx=500)

        # rx-only sees 1000 >= 700, combined would see 1500 as well,
        # but tx-only (500) must not fire.
        await make_trigger(db_session, "tx", scope=TrafficScope.SERVER, server_id=server.id,
                           threshold_bytes=700, direction=ModelDirection.TX_ONLY)

        result = await service.check_all_triggers(db_session)

        assert result["fired"] == ["rx"]
