"""Tests for PeriodicBackupService: schedule computation, loop and backup creation."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.periodic_backup_service as periodic_module
from app.models.settings import GlobalSettings
from app.services.periodic_backup_service import PeriodicBackupService
from app.services.settings_service import SettingsService


class FrozenDatetime(datetime):
    """datetime subclass whose ``now()`` returns a fixed instant."""

    frozen_now: datetime = datetime(2026, 3, 10, 10, 0, 0)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen_now


@pytest.fixture
def service():
    backup_service = MagicMock()
    backup_service.create_backup = AsyncMock()
    return PeriodicBackupService(
        backup_service=backup_service, settings_service=SettingsService()
    )


async def _set_settings(db_session, **values):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    for key, value in values.items():
        setattr(settings, key, value)
    await db_session.commit()
    return settings


# ----------------------------------------------------------------------------
# Schedule computation
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "now, frequency, hour, minute, expected_seconds",
    [
        # daily: target still ahead today
        (datetime(2026, 3, 10, 10, 0), "daily", 12, 30, 9000),
        # daily: target already passed -> tomorrow
        (datetime(2026, 3, 10, 10, 0), "daily", 9, 0, 23 * 3600),
        # daily: exactly now -> tomorrow (strictly future)
        (datetime(2026, 3, 10, 10, 0), "daily", 10, 0, 24 * 3600),
        # weekly: Monday, time still ahead -> today
        (datetime(2026, 3, 9, 8, 0), "weekly", 10, 0, 7200),
        # weekly: Monday, time passed -> next Monday
        (datetime(2026, 3, 9, 8, 0), "weekly", 7, 0, 7 * 86400 - 3600),
        # weekly: Wednesday -> next Monday
        (datetime(2026, 3, 11, 8, 0), "weekly", 10, 0, 5 * 86400 + 7200),
        # monthly: 1st, time ahead -> today
        (datetime(2026, 3, 1, 8, 0), "monthly", 10, 0, 7200),
        # monthly: 1st, time passed -> next month
        (datetime(2026, 3, 1, 8, 0), "monthly", 7, 0, 30 * 86400 + 23 * 3600),
        # monthly: 1st of December, time passed -> 1st of January next year
        (datetime(2026, 12, 1, 8, 0), "monthly", 7, 0, 30 * 86400 + 23 * 3600),
        # monthly: mid month (June) -> 1st of July
        (
            datetime(2026, 6, 15, 12, 0),
            "monthly",
            2,
            0,
            int((datetime(2026, 7, 1, 2, 0) - datetime(2026, 6, 15, 12, 0)).total_seconds()),
        ),
        # monthly: mid December -> 1st of January next year
        (
            datetime(2026, 12, 15, 12, 0),
            "monthly",
            2,
            0,
            int((datetime(2027, 1, 1, 2, 0) - datetime(2026, 12, 15, 12, 0)).total_seconds()),
        ),
        # unknown frequency falls back to daily
        (datetime(2026, 3, 10, 10, 0), "hourly", 11, 0, 3600),
        (datetime(2026, 3, 10, 10, 0), "hourly", 9, 0, 23 * 3600),
    ],
)
def test_should_compute_seconds_until_next_backup_when_schedule_given(
    service, now, frequency, hour, minute, expected_seconds
):
    FrozenDatetime.frozen_now = now
    with patch.object(periodic_module, "datetime", FrozenDatetime):
        seconds = service._calculate_seconds_until_next_backup(frequency, hour, minute)

    assert seconds == pytest.approx(expected_seconds)
    assert seconds > 0


# ----------------------------------------------------------------------------
# Background loop
# ----------------------------------------------------------------------------


async def test_should_wait_one_hour_when_periodic_backups_disabled(service, seeded_db, db_session):
    await _set_settings(db_session, backup_periodic_enabled=False)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        service._running = False

    with patch.object(periodic_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._backup_loop()

    assert slept == [3600]
    service.backup_service.create_backup.assert_not_awaited()


async def test_should_wait_until_scheduled_time_and_create_backup_when_enabled(
    service, seeded_db, db_session
):
    await _set_settings(
        db_session,
        backup_periodic_enabled=True,
        backup_schedule_frequency="daily",
        backup_schedule_hour=3,
        backup_schedule_minute=15,
    )
    service._create_scheduled_backup = AsyncMock()
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:  # stop on the second cycle
            service._running = False

    FrozenDatetime.frozen_now = datetime(2026, 3, 10, 10, 0, 0)
    with patch.object(periodic_module.asyncio, "sleep", side_effect=fake_sleep), \
         patch.object(periodic_module, "datetime", FrozenDatetime):
        service._running = True
        await service._backup_loop()

    assert len(slept) == 2
    assert slept[0] == pytest.approx(17 * 3600 + 15 * 60)
    service._create_scheduled_backup.assert_awaited_once()


async def test_should_not_create_backup_when_service_stopped_while_waiting(service, seeded_db, db_session):
    await _set_settings(db_session, backup_periodic_enabled=True, backup_schedule_hour=3, backup_schedule_minute=15)
    service._create_scheduled_backup = AsyncMock()

    async def fake_sleep(seconds):
        service._running = False

    with patch.object(periodic_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._backup_loop()

    service._create_scheduled_backup.assert_not_awaited()


async def test_should_retry_in_one_hour_when_setup_not_completed(service, api_db):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        service._running = False

    with patch.object(periodic_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._backup_loop()

    assert slept == [3600]


@pytest.mark.parametrize(
    "error",
    [RuntimeError("database is locked"), ValueError("boom")],
)
async def test_should_retry_in_one_hour_when_loop_iteration_fails(service, seeded_db, error):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        service._running = False

    with patch.object(
        SettingsService, "is_backup_periodic_enabled", side_effect=error
    ), patch.object(periodic_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._backup_loop()

    assert slept == [3600]


# ----------------------------------------------------------------------------
# Scheduled backup creation
# ----------------------------------------------------------------------------


async def test_should_create_backup_and_publish_event_when_scheduled(service, seeded_db, db_session):
    await _set_settings(db_session, backup_periodic_enabled=True)
    backup = MagicMock()
    backup.id = 42
    backup.filename = "auto.zip"
    backup.servers_count = 2
    backup.peers_count = 5
    service.backup_service.create_backup.return_value = backup

    with patch.object(periodic_module.event_bus, "publish", new=AsyncMock()) as publish:
        await service._create_scheduled_backup()

    kwargs = service.backup_service.create_backup.await_args.kwargs
    assert kwargs["user_id"] == 1
    assert kwargs["encrypt"] is False
    assert kwargs["passphrase"] is None
    assert kwargs["description"].startswith("Automatic backup - ")

    publish.assert_awaited_once()
    args = publish.await_args.args
    assert args[0] == periodic_module.EventType.BACKUP_CREATED
    assert args[2] == 42
    assert args[3]["scheduled"] is True
    assert args[3]["automatic"] is True
    assert args[3]["servers_count"] == 2
    assert args[3]["peers_count"] == 5
    assert publish.await_args.kwargs["user_id"] is None


async def test_should_skip_backup_when_periodic_backups_were_disabled_meanwhile(
    service, seeded_db, db_session
):
    await _set_settings(db_session, backup_periodic_enabled=False)

    with patch.object(periodic_module.event_bus, "publish", new=AsyncMock()) as publish:
        await service._create_scheduled_backup()

    service.backup_service.create_backup.assert_not_awaited()
    publish.assert_not_awaited()


async def test_should_rollback_and_log_when_backup_creation_fails(service, seeded_db, db_session):
    await _set_settings(db_session, backup_periodic_enabled=True)
    service.backup_service.create_backup.side_effect = OSError("disk full")

    with patch.object(periodic_module.event_bus, "publish", new=AsyncMock()) as publish:
        await service._create_scheduled_backup()  # must not raise

    publish.assert_not_awaited()


# ----------------------------------------------------------------------------
# Lifecycle
# ----------------------------------------------------------------------------


async def test_should_start_and_stop_background_task_when_requested(service):
    async def forever():
        while True:
            await asyncio.sleep(3600)

    with patch.object(service, "_backup_loop", side_effect=forever):
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
