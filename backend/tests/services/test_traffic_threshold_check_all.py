"""check_all_triggers: the periodic evaluation invoked by the metrics monitor.

This is the piece that connects recorded TrafficMetric rows with the triggers
configured by the user, so it is tested against a real database.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.events import EventType, event_bus
from app.models.peer import Peer
from app.models.server import Server
from app.models.traffic_metric import TrafficMetric
from app.models.traffic_trigger import (
    ThresholdWindow,
    TrafficDirection,
    TrafficScope,
    TrafficTrigger,
)
from app.services.traffic_threshold_service import TrafficThresholdService


@pytest.fixture
def service():
    return TrafficThresholdService()


@pytest.fixture
def captured_events(monkeypatch):
    events = []
    original = event_bus.publish

    async def spy(event_type, source_type, source_id, payload, user_id=None):
        events.append(
            {"event_type": event_type, "source_id": source_id, "payload": payload}
        )
        await original(event_type, source_type, source_id, payload, user_id=user_id)

    monkeypatch.setattr(event_bus, "publish", spy)
    return events


@pytest.fixture
async def server(db_session):
    row = Server(
        id=1, name="wg0", public_key="spk", private_key="ssk", listen_port=51820
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture
async def peer(db_session, server):
    row = Peer(
        id=10, server_id=server.id, name="laptop", public_key="pk", private_key="sk"
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def _add_metric(db_session, *, peer_id=None, server_id=None, rx=0, tx=0, age_minutes=0):
    metric = TrafficMetric(
        peer_id=peer_id,
        server_id=server_id,
        rx_bytes=rx,
        tx_bytes=tx,
        recorded_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
    )
    db_session.add(metric)
    await db_session.commit()
    return metric


async def _add_trigger(db_session, **overrides):
    values = dict(
        name="cap",
        scope=TrafficScope.PEER,
        peer_id=10,
        direction=TrafficDirection.COMBINED,
        threshold_bytes=1000,
        window=ThresholdWindow.LAST_HOUR,
        trigger_integrations=[],
        trigger_event=True,
        enabled=True,
        cooldown_seconds=3600,
        total_triggers=0,
    )
    values.update(overrides)
    trigger = TrafficTrigger(**values)
    db_session.add(trigger)
    await db_session.commit()
    await db_session.refresh(trigger)
    return trigger


class TestCheckAllTriggers:
    async def test_should_report_zero_when_there_are_no_triggers(self, service, db_session):
        result = await service.check_all_triggers(db_session)

        assert result == {"triggers_checked": 0, "triggers_fired": 0, "fired": []}

    async def test_should_not_fire_below_threshold(self, service, db_session, peer):
        await _add_metric(db_session, peer_id=peer.id, rx=100, tx=100)
        await _add_trigger(db_session)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_checked"] == 1
        assert result["triggers_fired"] == 0

    async def test_should_fire_and_update_counters_when_threshold_exceeded(
        self, service, db_session, peer, captured_events
    ):
        await _add_metric(db_session, peer_id=peer.id, rx=800, tx=800)
        trigger = await _add_trigger(db_session)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1
        assert result["fired"] == ["cap"]
        refreshed = (
            await db_session.execute(
                select(TrafficTrigger).where(TrafficTrigger.id == trigger.id)
            )
        ).scalar_one()
        assert refreshed.total_triggers == 1
        assert refreshed.last_triggered_at is not None
        assert refreshed.last_checked_at is not None

        published = [e for e in captured_events if e["event_type"] == EventType.TRAFFIC_THRESHOLD_EXCEEDED]
        assert len(published) == 1
        payload = published[0]["payload"]
        assert payload["trigger_name"] == "cap"
        assert payload["total_bytes"] == 1600
        assert payload["rx_bytes"] == 800
        assert payload["threshold_bytes"] == 1000

    async def test_should_respect_direction_rx_only(self, service, db_session, peer, captured_events):
        await _add_metric(db_session, peer_id=peer.id, rx=50, tx=5000)
        await _add_trigger(db_session, direction=TrafficDirection.RX_ONLY)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 0

    async def test_should_ignore_metrics_outside_the_window(self, service, db_session, peer):
        await _add_metric(db_session, peer_id=peer.id, rx=5000, tx=0, age_minutes=120)
        await _add_trigger(db_session)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 0

    async def test_should_skip_disabled_triggers(self, service, db_session, peer):
        await _add_metric(db_session, peer_id=peer.id, rx=5000)
        await _add_trigger(db_session, enabled=False)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_checked"] == 0

    async def test_should_not_fire_again_during_cooldown(self, service, db_session, peer):
        await _add_metric(db_session, peer_id=peer.id, rx=5000)
        await _add_trigger(
            db_session, last_triggered_at=datetime.now(timezone.utc) - timedelta(minutes=5)
        )

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 0

    async def test_should_fire_again_after_cooldown_elapsed(self, service, db_session, peer):
        await _add_metric(db_session, peer_id=peer.id, rx=5000)
        await _add_trigger(
            db_session,
            cooldown_seconds=60,
            last_triggered_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1

    async def test_should_not_publish_when_trigger_event_disabled(
        self, service, db_session, peer, captured_events
    ):
        await _add_metric(db_session, peer_id=peer.id, rx=5000)
        await _add_trigger(db_session, trigger_event=False)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1
        assert [e for e in captured_events if e["event_type"] == EventType.TRAFFIC_THRESHOLD_EXCEEDED] == []

    async def test_should_evaluate_server_scoped_trigger(self, service, db_session, server, peer):
        await _add_metric(db_session, server_id=server.id, rx=2000)
        await _add_trigger(
            db_session, scope=TrafficScope.SERVER, peer_id=None, server_id=server.id
        )

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1

    async def test_should_evaluate_global_trigger_over_all_metrics(
        self, service, db_session, server, peer
    ):
        await _add_metric(db_session, peer_id=peer.id, rx=2000)
        await _add_trigger(db_session, scope=TrafficScope.GLOBAL, peer_id=None, server_id=None)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_fired"] == 1

    async def test_should_keep_evaluating_when_one_trigger_errors(
        self, service, db_session, peer, monkeypatch
    ):
        await _add_metric(db_session, peer_id=peer.id, rx=5000)
        await _add_trigger(db_session, name="broken")
        await _add_trigger(db_session, name="works")

        original = service.calculate_traffic_in_window
        calls = {"n": 0}

        async def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("metric table unavailable")
            return await original(**kwargs)

        monkeypatch.setattr(service, "calculate_traffic_in_window", flaky)

        result = await service.check_all_triggers(db_session)

        assert result["triggers_checked"] == 2
        assert result["fired"] == ["works"]
