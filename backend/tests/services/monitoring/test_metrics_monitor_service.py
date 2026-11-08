"""Tests for MetricsMonitorService: collection cycle, trigger checks, retention and loop."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.metrics_monitor_service as monitor_module
from app.models.server import Server
from app.models.settings import GlobalSettings
from app.models.traffic_metric import TrafficMetric
from app.services.metrics_monitor_service import MetricsMonitorService

SERVER_PUB = "aGVsbG8td29ybGQtc2VydmVyLXB1YmxpYy1rZXkteHl6MTIzNDU="


@pytest.fixture
def collector():
    c = MagicMock()
    c.collect_all_metrics = AsyncMock(return_value={"servers_updated": 1, "peers_updated": 2})
    return c


@pytest.fixture
def triggers():
    t = MagicMock()
    t.check_all_triggers = AsyncMock(return_value={"triggers_checked": 3, "triggers_fired": 0})
    return t


@pytest.fixture
def service(collector, triggers):
    return MetricsMonitorService(
        metrics_collector=collector,
        traffic_threshold_service=triggers,
        settings_service=MagicMock(),
    )


async def _set_settings(db_session, **values):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    for key, value in values.items():
        setattr(settings, key, value)
    await db_session.commit()
    return settings


async def _seed_metric(db_session, recorded_at, server_id=None):
    metric = TrafficMetric(
        server_id=server_id,
        rx_bytes=1,
        tx_bytes=1,
        rx_bytes_delta=0,
        tx_bytes_delta=0,
        recorded_at=recorded_at,
    )
    db_session.add(metric)
    await db_session.commit()
    return metric


# ----------------------------------------------------------------------------
# Collection interval
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("configured", [5, 15, 30, 60])
async def test_should_return_configured_interval_when_valid(service, seeded_db, db_session, configured):
    await _set_settings(db_session, metrics_collection_interval_minutes=configured)

    assert await service._get_collection_interval(db_session) == configured


@pytest.mark.parametrize("configured", [7, 0, -5])
async def test_should_fall_back_to_five_minutes_when_interval_invalid(
    service, seeded_db, db_session, configured
):
    await _set_settings(db_session, metrics_collection_interval_minutes=configured)

    assert await service._get_collection_interval(db_session) == 5


async def test_should_fall_back_to_five_minutes_when_no_settings_row(service, api_db, db_session):
    assert await service._get_collection_interval(db_session) == 5


async def test_should_fall_back_to_five_minutes_when_settings_query_fails(service, api_db, db_session):
    db_session.execute = AsyncMock(side_effect=RuntimeError("db down"))

    assert await service._get_collection_interval(db_session) == 5


# ----------------------------------------------------------------------------
# Collection / trigger steps
# ----------------------------------------------------------------------------


async def test_should_delegate_to_collector_when_collecting(service, db_session, collector):
    await service._collect_metrics(db_session)

    collector.collect_all_metrics.assert_awaited_once_with(db_session)


async def test_should_swallow_collector_errors_when_collecting(service, db_session, collector):
    collector.collect_all_metrics.side_effect = RuntimeError("wg exploded")

    await service._collect_metrics(db_session)  # must not raise


@pytest.mark.parametrize("fired", [0, 2])
async def test_should_delegate_to_threshold_service_when_checking_triggers(
    service, db_session, triggers, fired
):
    triggers.check_all_triggers.return_value = {"triggers_checked": 4, "triggers_fired": fired}

    await service._check_triggers(db_session)

    triggers.check_all_triggers.assert_awaited_once_with(db_session)


async def test_should_swallow_threshold_errors_when_checking_triggers(service, db_session, triggers):
    triggers.check_all_triggers.side_effect = ValueError("bad trigger config")

    await service._check_triggers(db_session)  # must not raise


# ----------------------------------------------------------------------------
# Retention / cleanup
# ----------------------------------------------------------------------------


async def test_should_skip_cleanup_when_last_cleanup_was_recent(service, seeded_db, db_session):
    server = Server(
        name="s1", interface="wg0", public_key=SERVER_PUB, private_key="priv", listen_port=51820
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)
    await _seed_metric(db_session, datetime.utcnow() - timedelta(days=400), server.id)
    service._last_cleanup = datetime.now(UTC)

    await service._cleanup_old_metrics_if_needed(db_session)

    assert len((await db_session.execute(select(TrafficMetric))).scalars().all()) == 1


async def test_should_delete_metrics_older_than_retention_when_cleanup_due(
    service, seeded_db, db_session
):
    await _set_settings(db_session, metrics_retention_days=30)
    server = Server(
        name="s1", interface="wg0", public_key=SERVER_PUB, private_key="priv", listen_port=51820
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)
    old = await _seed_metric(db_session, datetime.utcnow() - timedelta(days=40), server.id)
    recent = await _seed_metric(db_session, datetime.utcnow() - timedelta(days=1), server.id)
    service._last_cleanup = datetime.now(UTC) - timedelta(days=2)

    await service._cleanup_old_metrics_if_needed(db_session)

    remaining = [m.id for m in (await db_session.execute(select(TrafficMetric))).scalars().all()]
    assert remaining == [recent.id]
    assert old.id not in remaining
    # last cleanup timestamp is advanced so the next run waits a day again
    assert (datetime.now(UTC) - service._last_cleanup).total_seconds() < 60


async def test_should_use_default_retention_when_no_settings_row(service, api_db, db_session):
    server = Server(
        name="s1", interface="wg0", public_key=SERVER_PUB, private_key="priv", listen_port=51820
    )
    db_session.add(server)
    await db_session.commit()
    await db_session.refresh(server)
    old = await _seed_metric(db_session, datetime.utcnow() - timedelta(days=120), server.id)
    kept = await _seed_metric(db_session, datetime.utcnow() - timedelta(days=10), server.id)
    service._last_cleanup = datetime.now(UTC) - timedelta(days=2)

    await service._cleanup_old_metrics_if_needed(db_session)

    remaining = [m.id for m in (await db_session.execute(select(TrafficMetric))).scalars().all()]
    assert remaining == [kept.id]
    assert old.id not in remaining


async def test_should_update_last_cleanup_when_nothing_to_delete(service, seeded_db, db_session):
    service._last_cleanup = datetime.now(UTC) - timedelta(days=2)
    previous = service._last_cleanup

    await service._cleanup_old_metrics_if_needed(db_session)

    assert service._last_cleanup > previous


async def test_should_swallow_cleanup_errors_and_keep_old_timestamp(service, api_db, db_session):
    service._last_cleanup = datetime.now(UTC) - timedelta(days=2)
    previous = service._last_cleanup
    db_session.execute = AsyncMock(side_effect=RuntimeError("db locked"))

    await service._cleanup_old_metrics_if_needed(db_session)  # must not raise

    assert service._last_cleanup == previous


# ----------------------------------------------------------------------------
# Background loop
# ----------------------------------------------------------------------------


async def test_should_run_full_cycle_then_wait_for_interval(service, seeded_db, db_session, collector, triggers):
    await _set_settings(db_session, metrics_collection_interval_minutes=15)
    service._collect_metrics = AsyncMock()
    service._check_triggers = AsyncMock()
    service._cleanup_old_metrics_if_needed = AsyncMock()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            service._running = False

    with patch.object(monitor_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitoring_loop()

    assert slept == [10, 15 * 60]
    service._collect_metrics.assert_awaited_once()
    service._check_triggers.assert_awaited_once()
    service._cleanup_old_metrics_if_needed.assert_awaited_once()


async def test_should_run_cycle_against_real_database_when_started(service, seeded_db, collector, triggers):
    """The loop opens its own session bound to the configured engine."""
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            service._running = False

    with patch.object(monitor_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitoring_loop()

    collector.collect_all_metrics.assert_awaited_once()
    triggers.check_all_triggers.assert_awaited_once()
    assert slept[0] == 10


@pytest.mark.parametrize(
    "error, expected_wait",
    [
        (RuntimeError("Global settings not found. Please complete the setup wizard first."), 300),
        (RuntimeError("something else broke"), 300),
        (ValueError("unexpected"), 300),
    ],
)
async def test_should_wait_five_minutes_when_cycle_fails(service, error, expected_wait):
    service._get_collection_interval = AsyncMock(side_effect=error)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            service._running = False

    with patch.object(monitor_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitoring_loop()

    assert slept == [10, expected_wait]


async def test_should_keep_running_when_one_cycle_fails(service):
    calls = {"n": 0}

    async def flaky_interval(db):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("transient")
        service._running = False
        return 5

    service._get_collection_interval = flaky_interval
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    with patch.object(monitor_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitoring_loop()

    assert calls["n"] == 2  # the failing first cycle did not kill the loop


# ----------------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------------


async def test_should_start_and_stop_background_task_when_requested(service):
    async def forever():
        while True:
            await asyncio.sleep(3600)

    with patch.object(service, "_monitoring_loop", side_effect=forever):
        await service.start()
        assert service._running is True
        task = service._task
        assert task is not None and not task.done()

        await service.start()  # idempotent
        assert service._task is task

        await service.stop()

    assert service._running is False
    assert task.cancelled() or task.done()


async def test_should_do_nothing_when_stopping_service_that_is_not_running(service):
    await service.stop()

    assert service._running is False
    assert service._task is None
