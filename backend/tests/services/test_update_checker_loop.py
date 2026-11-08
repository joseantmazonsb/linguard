"""UpdateCheckerService: loop control and notification de-duplication."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.events import EventType  # noqa: F401  (documents related events)
from app.models.notification import Notification
from app.services.update_checker import UpdateCheckerService


@pytest.fixture
def version_service():
    service = MagicMock()
    service.check_for_updates = AsyncMock(return_value={"update_available": False})
    return service


@pytest.fixture
def notification_service():
    service = MagicMock()
    service.create_notification = AsyncMock()
    return service


@pytest.fixture
def checker(version_service, notification_service):
    return UpdateCheckerService(version_service, notification_service)


class TestCheckAndNotify:
    async def test_should_do_nothing_when_no_update_available(self, checker, version_service):
        version_service.check_for_updates.return_value = {
            "update_available": False,
            "current_version": "1.0.0",
        }

        await checker._check_and_notify()

        checker.notification_service.create_notification.assert_not_awaited()
        assert checker._last_notified_version is None

    async def test_should_create_notification_for_first_user(self, checker, seeded_db):
        checker.version_service.check_for_updates.return_value = {
            "update_available": True,
            "latest_version": "2.0.0",
            "current_version": "1.0.0",
            "release_url": "https://example.com/2.0.0",
        }

        await checker._check_and_notify()

        checker.notification_service.create_notification.assert_awaited_once()
        kwargs = checker.notification_service.create_notification.await_args.kwargs
        assert kwargs["title"] == "Update Available"
        assert "2.0.0" in kwargs["message"]
        assert kwargs["link"] == "https://example.com/2.0.0"
        assert checker._last_notified_version == "2.0.0"

    async def test_should_not_notify_twice_for_the_same_version(self, checker):
        checker.version_service.check_for_updates.return_value = {
            "update_available": True,
            "latest_version": "2.0.0",
        }
        checker._last_notified_version = "2.0.0"

        await checker._check_and_notify()

        checker.notification_service.create_notification.assert_not_awaited()

    async def test_should_skip_store_when_no_users_exist(self, checker, api_db):
        checker.version_service.check_for_updates.return_value = {
            "update_available": True,
            "latest_version": "3.0.0",
        }

        await checker._check_and_notify()

        checker.notification_service.create_notification.assert_not_awaited()
        assert checker._last_notified_version is None

    async def test_should_remember_version_when_database_is_unavailable(
        self, checker, monkeypatch
    ):
        from app.core import database as app_database

        checker.version_service.check_for_updates.return_value = {
            "update_available": True,
            "latest_version": "4.0.0",
        }
        monkeypatch.setattr(app_database, "AsyncSessionLocal", None)

        await checker._check_and_notify()

        assert checker._last_notified_version == "4.0.0"
        checker.notification_service.create_notification.assert_not_awaited()

    async def test_should_remember_version_when_notification_fails(
        self, checker, seeded_db
    ):
        checker.version_service.check_for_updates.return_value = {
            "update_available": True,
            "latest_version": "5.0.0",
        }
        checker.notification_service.create_notification.side_effect = RuntimeError(
            "smtp down"
        )

        await checker._check_and_notify()

        assert checker._last_notified_version == "5.0.0"

    async def test_should_swallow_errors_from_version_service(self, checker):
        checker.version_service.check_for_updates.side_effect = RuntimeError("http 500")

        await checker._check_and_notify()  # must not raise

        assert checker._last_notified_version is None

    async def test_should_report_error_field_without_notifying(self, checker):
        checker.version_service.check_for_updates.return_value = {
            "update_available": False,
            "error": "network unreachable",
        }

        await checker._check_and_notify()

        checker.notification_service.create_notification.assert_not_awaited()


class TestCheckLoop:
    async def test_should_check_after_initial_delay_and_stop_when_not_running(
        self, checker, monkeypatch
    ):
        sleeps = []
        checks = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            # First sleep is the 60s warm-up: emulate the service being stopped
            # right after it, so the loop exits before doing any work.
            checker._running = False

        async def fake_check():
            checks.append(1)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(checker, "_check_and_notify", fake_check)

        await checker._check_loop()

        assert sleeps == [60]
        assert checks == []

    async def test_should_run_one_check_then_continue_until_stopped(
        self, checker, monkeypatch
    ):
        sleeps = []
        checks = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 2:
                checker._running = False

        async def fake_check():
            checks.append(1)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(checker, "_check_and_notify", fake_check)
        checker._running = True

        await checker._check_loop()

        assert checks == [1]
        assert sleeps[1] == checker.check_interval.total_seconds()

    async def test_should_survive_failing_check_iteration(self, checker, monkeypatch):
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 2:
                checker._running = False

        async def failing_check():
            raise RuntimeError("boom")

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(checker, "_check_and_notify", failing_check)
        checker._running = True

        await checker._check_loop()  # must not propagate

        assert len(sleeps) == 2


class TestLifecycle:
    async def test_should_start_background_task(self, checker, monkeypatch):
        started = asyncio.Event()

        async def long_running_loop():
            started.set()
            await asyncio.sleep(3600)

        monkeypatch.setattr(checker, "_check_loop", long_running_loop)

        await checker.start()
        await asyncio.wait_for(started.wait(), timeout=1)

        assert checker._running is True
        assert checker._task is not None and not checker._task.done()
        await checker.stop()

    async def test_should_ignore_second_start(self, checker, monkeypatch):
        calls = []

        async def long_running_loop():
            calls.append(1)
            await asyncio.sleep(3600)

        monkeypatch.setattr(checker, "_check_loop", long_running_loop)

        await checker.start()
        task = checker._task
        await asyncio.sleep(0)  # let the loop coroutine enter its first iteration
        await checker.start()
        await asyncio.sleep(0)

        assert checker._task is task
        assert len(calls) == 1  # the second start did not spawn a new loop
        await checker.stop()

    async def test_should_cancel_task_on_stop(self, checker, monkeypatch):
        async def long_running_loop():
            await asyncio.sleep(3600)

        monkeypatch.setattr(checker, "_check_loop", long_running_loop)
        await checker.start()
        task = checker._task

        await checker.stop()

        assert checker._running is False
        assert task.cancelled()

    async def test_should_be_noop_when_stopping_a_stopped_checker(self, checker):
        await checker.stop()

        assert checker._running is False
