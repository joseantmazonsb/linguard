"""Tests for ``app.plugins.base`` (decorators, storage, context)."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.plugins.base import (
    PluginContext,
    PluginMetadata,
    PluginStorage,
    _plugin_registry,
    on_event,
    plugin,
)


@pytest.fixture
def registered():
    """Track plugin classes registered by a test and clean the registry."""
    before = set(_plugin_registry)
    yield
    for cls in set(_plugin_registry) - before:
        _plugin_registry.pop(cls, None)


class TestPluginDecorator:
    def test_should_store_metadata_and_class_attributes(self, registered):
        @plugin(name="Slack Notifier", version="2.1.0", description="Sends alerts", author="Jo")
        class SlackNotifier:
            pass

        metadata = _plugin_registry[SlackNotifier]
        assert isinstance(metadata, PluginMetadata)
        assert (metadata.name, metadata.version, metadata.description, metadata.author) == (
            "Slack Notifier", "2.1.0", "Sends alerts", "Jo",
        )
        assert SlackNotifier._plugin_name == "Slack Notifier"
        assert SlackNotifier._plugin_version == "2.1.0"
        assert SlackNotifier._plugin_description == "Sends alerts"
        assert SlackNotifier._plugin_author == "Jo"
        assert SlackNotifier._plugin_metadata is metadata

    def test_should_default_optional_metadata_to_empty_strings(self, registered):
        @plugin(name="Bare", version="0.1")
        class Bare:
            pass

        metadata = _plugin_registry[Bare]
        assert metadata.description == ""
        assert metadata.author == ""

    def test_should_append_handlers_per_event_type(self):
        metadata = PluginMetadata("p", "1.0")

        def h1(data):
            return data

        def h2(data):
            return data

        metadata.add_event_handler(["server.created", "peer.created"], h1)
        metadata.add_event_handler(["server.created"], h2)

        assert metadata.event_handlers == {
            "server.created": [h1, h2],
            "peer.created": [h1],
        }


class TestOnEventDecorator:
    async def test_should_mark_handler_and_delegate_to_function(self):
        calls = []

        class Demo:
            @on_event("server.created", "server.started")
            async def handle(self, event_data):
                calls.append((self, event_data))
                return "done"

        instance = Demo()
        result = await instance.handle({"peer_id": 3})

        assert result == "done"
        assert Demo.handle._is_event_handler is True
        assert Demo.handle._event_types == ["server.created", "server.started"]
        assert calls == [(instance, {"peer_id": 3})]

    async def test_should_support_wildcard_subscription(self):
        class Wild:
            @on_event("*")
            async def handle(self, event_data):
                return None

        assert Wild.handle._event_types == ["*"]


class TestPluginStorage:
    async def _make_plugin(self, db_session):
        from app.models.plugin import Plugin

        plugin_row = Plugin(
            name="storage-plugin", version="1.0", module_name="storage_plugin",
            file_path="/tmp/storage/plugin.py", enabled=False,
        )
        db_session.add(plugin_row)
        await db_session.commit()
        await db_session.refresh(plugin_row)
        return plugin_row

    async def test_should_return_default_for_missing_key(self, api_db, db_session):
        row = await self._make_plugin(db_session)
        storage = PluginStorage(row.id, api_db.sessionmaker)

        assert await storage.get("missing") is None
        assert await storage.get("missing", default="fallback") == "fallback"

    async def test_should_insert_then_update_a_value(self, api_db, db_session):
        row = await self._make_plugin(db_session)
        storage = PluginStorage(row.id, api_db.sessionmaker)

        await storage.set("token", "abc")
        assert await storage.get("token") == "abc"

        await storage.set("token", "xyz")
        assert await storage.get("token") == "xyz"
        assert await storage.list_keys() == ["token"]

    async def test_should_store_structured_values(self, api_db, db_session):
        row = await self._make_plugin(db_session)
        storage = PluginStorage(row.id, api_db.sessionmaker)

        await storage.set("config", {"retries": 3, "targets": ["a", "b"]})

        assert await storage.get("config") == {"retries": 3, "targets": ["a", "b"]}

    async def test_should_scope_keys_per_plugin(self, api_db, db_session):
        first = await self._make_plugin(db_session)
        from app.models.plugin import Plugin

        second = Plugin(name="other-plugin", version="1.0", module_name="other_plugin",
                        file_path="/tmp/other/plugin.py", enabled=False)
        db_session.add(second)
        await db_session.commit()
        await db_session.refresh(second)

        await PluginStorage(first.id, api_db.sessionmaker).set("k", 1)
        await PluginStorage(second.id, api_db.sessionmaker).set("k", 2)

        assert await PluginStorage(first.id, api_db.sessionmaker).get("k") == 1
        assert await PluginStorage(second.id, api_db.sessionmaker).get("k") == 2

    async def test_should_delete_single_key(self, api_db, db_session):
        row = await self._make_plugin(db_session)
        storage = PluginStorage(row.id, api_db.sessionmaker)
        await storage.set("a", 1)
        await storage.set("b", 2)

        await storage.delete("a")

        assert await storage.list_keys() == ["b"]

    async def test_should_clear_all_keys(self, api_db, db_session):
        row = await self._make_plugin(db_session)
        storage = PluginStorage(row.id, api_db.sessionmaker)
        await storage.set("a", 1)
        await storage.set("b", 2)

        await storage.clear()

        assert await storage.list_keys() == []


class TestPluginContext:
    def _context(self, api_db, config=None, name="ctx"):
        return PluginContext(
            plugin_id=7,
            plugin_name=name,
            config=config,
            storage=PluginStorage(7, api_db.sessionmaker),
            db_session_factory=api_db.sessionmaker,
        )

    def test_should_expose_config_and_plugin_identity(self, api_db):
        context = self._context(api_db, config={"url": "https://example.com"})

        assert context.plugin_id == 7
        assert context.config == {"url": "https://example.com"}
        assert context.logger.name == "plugin.ctx"

    def test_should_default_config_to_empty_dict(self, api_db):
        assert self._context(api_db, config=None).config == {}

    def test_should_create_http_client_with_timeout(self, api_db):
        context = self._context(api_db, name="http")

        try:
            assert isinstance(context.http_client, httpx.AsyncClient)
            assert context.http_client.timeout == httpx.Timeout(10.0)
        finally:
            import asyncio

            asyncio.get_event_loop().run_until_complete(context.http_client.aclose())

    def test_should_use_injected_http_client(self, api_db):
        client = httpx.AsyncClient()

        context = PluginContext(1, "p", {}, PluginStorage(1, api_db.sessionmaker),
                                api_db.sessionmaker, http_client=client)

        assert context.http_client is client
        assert isinstance(client, httpx.AsyncClient)

    def test_should_forward_log_calls_to_plugin_logger(self, api_db):
        context = self._context(api_db, name="logging")

        with patch.object(context.logger, "info") as info, \
                patch.object(context.logger, "warning") as warning, \
                patch.object(context.logger, "error") as error, \
                patch.object(context.logger, "debug") as debug:
            context.log_info("i")
            context.log_warning("w")
            context.log_error("e")
            context.log_debug("d")

        info.assert_called_once_with("i")
        warning.assert_called_once_with("w")
        error.assert_called_once_with("e")
        debug.assert_called_once_with("d")

    async def test_should_hand_out_database_sessions(self, api_db):
        context = self._context(api_db)

        session = await context.get_db_session()

        assert session is not None
        await session.close()

    async def test_should_publish_known_events_with_plugin_source(self, api_db):
        context = self._context(api_db)

        with patch("app.core.events.event_bus.publish", new=AsyncMock()) as publish:
            await context.publish_event("peer.created", {"peer_id": 1})

        from app.core.events import EventType

        publish.assert_awaited_once_with(
            EventType.PEER_CREATED,
            source_type="plugin",
            source_id=7,
            payload={"peer_id": 1},
        )

    async def test_should_warn_and_skip_unknown_event_types(self, api_db):
        context = self._context(api_db)

        with patch("app.core.events.event_bus.publish", new=AsyncMock()) as publish, \
                patch.object(context.logger, "warning") as warning:
            await context.publish_event("custom.thing", {})

        publish.assert_not_awaited()
        warning.assert_called_once()
        assert "custom.thing" in warning.call_args[0][0]
