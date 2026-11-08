"""Tests for InterfaceMonitorService: DB/state sync driven by wg interface state.

The monitor shells out to `wg` indirectly through WireGuardService, so that
single method (`find_interface_by_public_key`) is replaced with a deterministic
fake that reports which interface the server owns.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core import events as events_module
from app.core.events import EventType
from app.models.server import Server
from app.services.interface_monitor import InterfaceMonitorService


def _server(server_id, name, status, public_key):
    return Server(
        id=server_id,
        name=name,
        public_key=public_key,
        private_key="a" * 43 + "=",
        listen_port=51820,
        status=status,
    )


class FakeWireGuard:
    def __init__(self, present_keys=(), raise_for=None):
        self.present_keys = set(present_keys)
        self.raise_for = raise_for or set()

    def find_interface_by_public_key(self, public_key):
        if public_key in self.raise_for:
            raise RuntimeError("wg exploded")
        return f"wg-{public_key[:4]}" if public_key in self.present_keys else None


@pytest.fixture
def published(monkeypatch):
    """Capture events published on the shared bus."""
    captured = []

    async def fake_publish(event_type, source_type, source_id, payload, user_id=None):
        captured.append(
            {
                "event_type": event_type,
                "source_id": source_id,
                "payload": payload,
                "user_id": user_id,
            }
        )

    monkeypatch.setattr(events_module.event_bus, "publish", fake_publish)
    return captured


class TestMonitorLifecycle:
    async def test_should_start_task_and_flag_running(self, monkeypatch):
        service = InterfaceMonitorService(wireguard_service=FakeWireGuard())
        monkeypatch.setattr(service, "_monitor_loop", AsyncMock())

        await service.start()

        assert service._running is True
        assert service._task is not None
        await service.stop()

    async def test_should_not_start_twice(self, monkeypatch):
        service = InterfaceMonitorService(wireguard_service=FakeWireGuard())
        loop = AsyncMock()
        monkeypatch.setattr(service, "_monitor_loop", loop)

        await service.start()
        first_task = service._task
        await service.start()

        assert service._task is first_task
        loop.assert_called_once()
        await service.stop()

    async def test_should_stop_when_running(self, monkeypatch):
        service = InterfaceMonitorService(wireguard_service=FakeWireGuard())
        monkeypatch.setattr(service, "_monitor_loop", AsyncMock())
        await service.start()

        await service.stop()

        assert service._running is False

    async def test_should_be_noop_when_stopping_a_stopped_service(self):
        service = InterfaceMonitorService(wireguard_service=FakeWireGuard())

        await service.stop()

        assert service._running is False


class TestMonitorLoop:
    async def test_should_keep_looping_and_swallow_errors(self, monkeypatch):
        service = InterfaceMonitorService(wireguard_service=FakeWireGuard())
        calls = {"check": 0, "sleep": 0}

        async def failing_check():
            calls["check"] += 1
            raise RuntimeError("db down")

        async def fake_sleep(_seconds):
            calls["sleep"] += 1
            if calls["sleep"] >= 2:
                service._running = False

        monkeypatch.setattr(service, "_check_all_servers", failing_check)
        monkeypatch.setattr(asyncio, "sleep", fake_sleep)
        service._running = True

        await service._monitor_loop()

        assert calls["check"] == 2  # error did not break the loop


class TestStatusSync:
    async def test_should_mark_stopped_server_as_running_when_interface_exists(
        self, db_session, published
    ):
        db_session.add(_server(1, "wg-a", "stopped", "AAAA" + "a" * 40))
        await db_session.commit()

        monitor = InterfaceMonitorService(
            wireguard_service=FakeWireGuard(present_keys={"AAAA" + "a" * 40})
        )
        await monitor._check_all_servers()

        refreshed = await db_session.execute(select(Server).where(Server.id == 1))
        assert refreshed.scalar_one().status == "running"
        assert [e["event_type"] for e in published] == [EventType.SERVER_STARTED]
        assert published[0]["payload"]["detected"] is True
        assert published[0]["user_id"] is None

    async def test_should_mark_running_server_as_stopped_when_interface_missing(
        self, db_session, published
    ):
        db_session.add(_server(2, "wg-b", "running", "BBBB" + "b" * 40))
        await db_session.commit()

        monitor = InterfaceMonitorService(wireguard_service=FakeWireGuard())
        await monitor._check_all_servers()

        refreshed = await db_session.execute(select(Server).where(Server.id == 2))
        assert refreshed.scalar_one().status == "stopped"
        assert [e["event_type"] for e in published] == [EventType.SERVER_STOPPED]

    async def test_should_not_publish_when_status_is_unchanged(
        self, db_session, published
    ):
        db_session.add(_server(3, "wg-c", "running", "CCCC" + "c" * 40))
        await db_session.commit()

        monitor = InterfaceMonitorService(
            wireguard_service=FakeWireGuard(present_keys={"CCCC" + "c" * 40})
        )
        await monitor._check_all_servers()

        assert published == []

    async def test_should_continue_with_other_servers_when_one_check_fails(
        self, db_session, published
    ):
        good = "DDDD" + "d" * 40
        bad = "EEEE" + "e" * 40
        db_session.add(_server(4, "good", "stopped", good))
        db_session.add(_server(5, "bad", "stopped", bad))
        await db_session.commit()

        monitor = InterfaceMonitorService(
            wireguard_service=FakeWireGuard(present_keys={good}, raise_for={bad})
        )
        await monitor._check_all_servers()

        result = await db_session.execute(select(Server).where(Server.id == 4))
        assert result.scalar_one().status == "running"

    async def test_should_rollback_when_query_fails(self, db_session):
        calls = {"rollback": 0, "close": 0}

        class FailingSession:
            def __init__(self, **kwargs):
                pass

            async def execute(self, *_args, **_kwargs):
                raise RuntimeError("cannot connect")

            async def commit(self):
                raise AssertionError("commit must not run after a failure")

            async def rollback(self):
                calls["rollback"] += 1

            async def close(self):
                calls["close"] += 1

        monitor = InterfaceMonitorService(wireguard_service=FakeWireGuard())

        with patch("app.services.interface_monitor.AsyncSession", FailingSession):
            await monitor._check_all_servers()  # must not raise

        assert calls == {"rollback": 1, "close": 1}
