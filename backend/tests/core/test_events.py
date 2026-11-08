"""Tests for the in-memory EventBus contract used across services."""
import asyncio

import pytest

from app.core.events import EventBus, EventType, event_bus


@pytest.fixture
def bus():
    return EventBus()


class TestPublish:
    async def test_should_call_subscribed_handler_with_event_metadata(self, bus):
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(EventType.PEER_CREATED, handler)

        await bus.publish(
            EventType.PEER_CREATED, "peer", 7, {"name": "laptop"}, user_id=3
        )
        await asyncio.sleep(0)  # let the background task run

        assert len(received) == 1
        event = received[0]
        assert event["event_type"] == "peer.created"
        assert event["source_type"] == "peer"
        assert event["source_id"] == 7
        assert event["payload"] == {"name": "laptop"}
        assert event["user_id"] == 3
        assert event["timestamp"].endswith("UTC")

    async def test_should_invoke_every_handler_for_the_same_event(self, bus):
        calls = []

        def make(name):
            async def handler(_event):
                calls.append(name)
            return handler

        bus.subscribe(EventType.SERVER_STARTED, make("first"))
        bus.subscribe(EventType.SERVER_STARTED, make("second"))

        await bus.publish(EventType.SERVER_STARTED, "server", 1, {})
        await asyncio.sleep(0)

        assert sorted(calls) == ["first", "second"]

    async def test_should_not_call_handlers_of_other_events(self, bus):
        calls = []

        async def handler(_event):
            calls.append("hit")

        bus.subscribe(EventType.SERVER_STARTED, handler)

        await bus.publish(EventType.SERVER_STOPPED, "server", 1, {})
        await asyncio.sleep(0)

        assert calls == []

    async def test_should_keep_going_when_a_handler_raises(self, bus, capsys):
        calls = []

        async def broken(_event):
            raise RuntimeError("handler exploded")

        async def healthy(_event):
            calls.append("ok")

        bus.subscribe(EventType.BACKUP_CREATED, broken)
        bus.subscribe(EventType.BACKUP_CREATED, healthy)

        await bus.publish(EventType.BACKUP_CREATED, "backup", 1, {})
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert calls == ["ok"]
        assert "handler exploded" in capsys.readouterr().out

    async def test_should_not_block_publisher_until_handlers_finish(self, bus):
        finished = []

        async def slow(_event):
            await asyncio.sleep(0.05)
            finished.append("done")

        bus.subscribe(EventType.INTEGRATION_TRIGGERED, slow)

        await bus.publish(EventType.INTEGRATION_TRIGGERED, "integration", 1, {})

        assert finished == []  # publisher returned before the handler ran
        await asyncio.sleep(0.1)
        assert finished == ["done"]


class TestLifecycle:
    async def test_should_connect_and_disconnect_without_side_effects(self, bus):
        await bus.connect()
        await bus.disconnect()

        assert bus._handlers == {}

    async def test_should_share_one_global_bus_instance(self):
        assert event_bus is event_bus and isinstance(event_bus, EventBus)
