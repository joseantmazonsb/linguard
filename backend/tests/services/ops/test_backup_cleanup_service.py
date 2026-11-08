"""Tests for BackupCleanupService: retention, error handling and the cleanup loop."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.backup_cleanup_service as cleanup_module
from app.models.backup import Backup
from app.services.backup_cleanup_service import BackupCleanupService
from app.services.settings_service import SettingsService


@pytest.fixture
def service():
    return BackupCleanupService(settings_service=SettingsService())


async def _seed_backup(db_session, user_id, filename, age_days):
    backup = Backup(
        filename=filename,
        description="test",
        size_bytes=10,
        created_by_user_id=user_id,
        created_at=datetime.utcnow() - timedelta(days=age_days),
    )
    db_session.add(backup)
    await db_session.commit()
    await db_session.refresh(backup)
    return backup


async def test_should_delete_old_backup_file_and_record_when_cleanup_runs(service, seeded_db, db_session, tmp_path):
    # Point the retention at a directory owned by this test
    from app.models.settings import GlobalSettings
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    settings.backup_retention_days = 10
    settings.backup_auto_cleanup_enabled = True
    old_file = tmp_path / "old_backup.zip"
    old_file.write_text("data")
    old = await _seed_backup(db_session, seeded_db["admin_id"], "old_backup.zip", age_days=20)
    recent = await _seed_backup(db_session, seeded_db["admin_id"], "recent_backup.zip", age_days=1)

    with patch.object(cleanup_module.event_bus, "publish", new=AsyncMock()) as publish:
        await service._cleanup_old_backups()

    assert not old_file.exists()
    remaining = (await db_session.execute(select(Backup))).scalars().all()
    assert [b.filename for b in remaining] == ["recent_backup.zip"]
    publish.assert_awaited_once()
    args = publish.await_args.args
    assert args[0] == cleanup_module.EventType.BACKUP_DELETED
    assert args[2] == old.id
    assert args[3]["auto_cleanup"] is True
    assert args[3]["filename"] == "old_backup.zip"
    assert args[3]["age_days"] == 20
    assert recent.id


async def test_should_remove_db_record_when_backup_file_is_missing(service, seeded_db, db_session, tmp_path):
    from app.models.settings import GlobalSettings
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    settings.backup_retention_days = 5
    await _seed_backup(db_session, seeded_db["admin_id"], "gone.zip", age_days=30)

    with patch.object(cleanup_module.event_bus, "publish", new=AsyncMock()):
        await service._cleanup_old_backups()

    assert (await db_session.execute(select(Backup))).scalars().all() == []


async def test_should_keep_backups_when_auto_cleanup_disabled(service, seeded_db, db_session, tmp_path):
    from app.models.settings import GlobalSettings
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    settings.backup_retention_days = 5
    settings.backup_auto_cleanup_enabled = False
    (tmp_path / "old.zip").write_text("data")
    await _seed_backup(db_session, seeded_db["admin_id"], "old.zip", age_days=30)

    await service._cleanup_old_backups()

    assert len((await db_session.execute(select(Backup))).scalars().all()) == 1
    assert (tmp_path / "old.zip").exists()


@pytest.mark.parametrize("retention_days", [0, -1])
async def test_should_keep_backups_when_retention_is_disabled(service, seeded_db, db_session, tmp_path, retention_days):
    from app.models.settings import GlobalSettings
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    settings.backup_retention_days = retention_days
    await _seed_backup(db_session, seeded_db["admin_id"], "old.zip", age_days=30)

    await service._cleanup_old_backups()

    assert len((await db_session.execute(select(Backup))).scalars().all()) == 1


async def test_should_do_nothing_when_no_backup_is_older_than_retention(service, seeded_db, db_session):
    with patch.object(cleanup_module.event_bus, "publish", new=AsyncMock()) as publish:
        await service._cleanup_old_backups()

    publish.assert_not_awaited()


async def test_should_skip_silently_when_setup_is_not_completed(service, api_db, db_session):
    # No GlobalSettings row at all -> SettingsService raises the setup-wizard RuntimeError.
    await service._cleanup_old_backups()  # must not raise


async def test_should_keep_going_when_one_file_cannot_be_deleted(service, seeded_db, db_session, tmp_path):
    from app.models.settings import GlobalSettings
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.backup_dir = str(tmp_path)
    settings.backup_retention_days = 5
    (tmp_path / "a.zip").write_text("data")
    (tmp_path / "b.zip").write_text("data")
    await _seed_backup(db_session, seeded_db["admin_id"], "a.zip", age_days=30)
    await _seed_backup(db_session, seeded_db["admin_id"], "b.zip", age_days=30)

    real_remove = cleanup_module.os.remove

    def flaky_remove(path):
        if path.endswith("a.zip"):
            raise OSError("permission denied")
        return real_remove(path)

    with patch.object(cleanup_module.event_bus, "publish", new=AsyncMock()), \
         patch.object(cleanup_module.os, "remove", side_effect=flaky_remove):
        await service._cleanup_old_backups()

    remaining = [b.filename for b in (await db_session.execute(select(Backup))).scalars().all()]
    assert remaining == ["a.zip"]
    assert not (tmp_path / "b.zip").exists()


async def test_should_rollback_when_unexpected_error_occurs(service, seeded_db, api_db):
    with patch.object(
        SettingsService, "is_backup_auto_cleanup_enabled", side_effect=ValueError("boom")
    ):
        await service._cleanup_old_backups()  # must not raise


def _fake_loop(times):
    loop = MagicMock()
    loop.time.side_effect = times
    return loop


async def test_should_exit_loop_when_timeout_is_reached(service):
    cleanup = AsyncMock()
    times = iter([0.0, 100.0])
    with patch.object(service, "_cleanup_old_backups", cleanup), \
         patch.object(cleanup_module.asyncio, "get_event_loop", return_value=_fake_loop(times)), \
         patch.object(cleanup_module.asyncio, "sleep", new=AsyncMock()) as sleep:
        service._running = True
        await service._cleanup_loop(timeout=50)

    cleanup.assert_awaited_once()
    sleep.assert_not_awaited()


async def test_should_sleep_between_iterations_until_timeout(service):
    cleanup = AsyncMock()
    times = iter([0.0, 10.0, 100.0])  # two iterations, second one hits the timeout
    with patch.object(service, "_cleanup_old_backups", cleanup), \
         patch.object(cleanup_module.asyncio, "get_event_loop", return_value=_fake_loop(times)), \
         patch.object(cleanup_module.asyncio, "sleep", new=AsyncMock()) as sleep:
        service._running = True
        await service._cleanup_loop(timeout=50)

    assert cleanup.await_count == 2
    sleep.assert_awaited_once()


async def test_should_keep_running_when_one_iteration_fails(service):
    calls = {"n": 0}

    async def failing_cleanup():
        calls["n"] += 1
        if calls["n"] == 2:
            service._running = False
        raise RuntimeError("Please complete the setup wizard first.")

    with patch.object(service, "_cleanup_old_backups", side_effect=failing_cleanup), \
         patch.object(cleanup_module.asyncio, "sleep", new=AsyncMock()) as sleep:
        service._running = True
        await service._cleanup_loop(timeout=None)

    assert calls["n"] == 2  # the failure on the first iteration did not stop the loop
    assert sleep.await_count == 2  # sleeps after every iteration


@pytest.mark.parametrize("error", [OSError("disk gone"), RuntimeError("unexpected runtime error")])
async def test_should_keep_running_when_iteration_raises_generic_error(service, error):
    calls = {"n": 0}

    async def failing_cleanup():
        calls["n"] += 1
        service._running = False
        raise error

    with patch.object(service, "_cleanup_old_backups", side_effect=failing_cleanup), \
         patch.object(cleanup_module.asyncio, "sleep", new=AsyncMock()):
        service._running = True
        await service._cleanup_loop(timeout=None)

    assert calls["n"] == 1


async def test_should_rollback_when_runtime_error_is_not_about_setup(service, seeded_db):
    with patch.object(
        SettingsService, "is_backup_auto_cleanup_enabled",
        side_effect=RuntimeError("database is locked"),
    ):
        await service._cleanup_old_backups()  # logged and rolled back, not raised


async def test_should_start_and_stop_background_task_when_requested(service):
    async def forever(timeout=None):
        while True:
            await asyncio.sleep(3600)

    with patch.object(service, "_cleanup_loop", side_effect=forever):
        await service.start()
        assert service._running is True
        task = service._task
        assert task is not None and not task.done()

        # Starting twice must not spawn a second task
        await service.start()
        assert service._task is task

        await service.stop()

    assert service._running is False
    assert task.cancelled() or task.done()


async def test_should_do_nothing_when_stopping_service_that_is_not_running(service):
    await service.stop()  # no task, no exception

    assert service._running is False
    assert service._task is None
