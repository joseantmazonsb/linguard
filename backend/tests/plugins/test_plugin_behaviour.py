"""Behavioural tests for the plugin loader and manager using real plugin files.

Each test writes a genuine ``plugin.py`` into ``tmp_path`` so discovery, class
registration, event-handler extraction and instantiation all run for real.
"""

import textwrap
from unittest.mock import AsyncMock, patch

import pytest

from app.core.events import EventType, event_bus
from app.models.integration import Integration
from app.models.plugin import Plugin
from app.plugins.base import _plugin_registry
from app.plugins.loader import PluginLoader
from app.plugins.manager import LoadedPluginInstance, PluginManager


PLUGIN_TEMPLATE = '''
from app.plugins.base import plugin, on_event


@plugin(name="{name}", version="{version}", description="{description}", author="Tester")
class {cls}:
    def __init__(self, context=None):
{init}

    @on_event({events})
    async def handle(self, event_data):
{body}
'''


def write_plugin(root, module_name, cls="DemoPlugin", name=None, version="1.0.0",
                 description="demo plugin", events='"server.created"',
                 body="        self.seen.append(event_data)", requirements=None,
                 init="        self.context = context\n        self.seen = []"):
    plugin_dir = root / module_name
    plugin_dir.mkdir(parents=True)
    source = PLUGIN_TEMPLATE.format(
        name=name or f"Plugin {module_name}", version=version, description=description,
        cls=cls, events=events, body=body, init=init,
    )
    (plugin_dir / "plugin.py").write_text(source)
    if requirements is not None:
        (plugin_dir / "requirements.txt").write_text(requirements)
    return plugin_dir


@pytest.fixture(autouse=True)
def isolate_registry():
    snapshot = set(_plugin_registry)
    yield
    for cls in set(_plugin_registry) - snapshot:
        _plugin_registry.pop(cls, None)


@pytest.fixture
def loader():
    return PluginLoader()


@pytest.fixture
def manager(api_db):
    return PluginManager(api_db.sessionmaker)


async def seed_plugin_row(db, plugin_dir, module_name, **kwargs):
    subscribed = kwargs.pop("subscribed_events", ["server.created"])
    row = Plugin(
        name=kwargs.pop("name", f"Plugin {module_name}"),
        version=kwargs.pop("version", "1.0.0"),
        module_name=module_name,
        file_path=str(plugin_dir / "plugin.py"),
        enabled=kwargs.pop("enabled", True),
        subscribed_events=subscribed,
        **kwargs,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ===========================================================================
# Loader
# ===========================================================================

class TestDiscovery:
    def test_should_create_directory_when_missing(self, loader, tmp_path):
        target = tmp_path / "plugins"

        assert loader.discover_plugins(str(target)) == []
        assert target.is_dir()

    def test_should_return_empty_when_path_is_a_file(self, loader, tmp_path):
        shared = tmp_path / "plugins"
        shared.write_text("not a directory")

        assert loader.discover_plugins(str(shared)) == []
        assert loader.discovered_plugins == {}

    def test_should_discover_plugin_with_metadata_and_handlers(self, loader, tmp_path):
        write_plugin(tmp_path, "alpha", cls="AlphaPlugin", name="Alpha",
                     events='"server.created", "peer.created"')

        discovered = loader.discover_plugins(str(tmp_path))

        assert len(discovered) == 1
        info = discovered[0]
        assert info["module_name"] == "alpha"
        assert info["metadata"].name == "Alpha"
        assert info["metadata"].version == "1.0.0"
        assert sorted(info["metadata"].event_handlers) == ["peer.created", "server.created"]
        assert loader.get_plugin_subscribed_events(info["plugin_class"]) == sorted(
            info["metadata"].event_handlers
        ) or set(loader.get_plugin_subscribed_events(info["plugin_class"])) == {
            "server.created", "peer.created"
        }
        assert loader.discovered_plugins["alpha"] is info

    def test_should_skip_hidden_and_pycache_directories(self, loader, tmp_path):
        write_plugin(tmp_path, "visible")
        for ignored in (".git", "__pycache__"):
            (tmp_path / ignored).mkdir()
            (tmp_path / ignored / "plugin.py").write_text("raise RuntimeError('should not load')")

        assert [p["module_name"] for p in loader.discover_plugins(str(tmp_path))] == ["visible"]

    def test_should_skip_directories_without_plugin_file(self, loader, tmp_path):
        (tmp_path / "not-a-plugin").mkdir()
        (tmp_path / "not-a-plugin" / "README.md").write_text("# nothing here")

        assert loader.discover_plugins(str(tmp_path)) == []

    def test_should_ignore_stray_files_in_plugins_dir(self, loader, tmp_path):
        (tmp_path / "plugin.py").write_text("this is the wrong place")
        write_plugin(tmp_path, "real")

        assert [p["module_name"] for p in loader.discover_plugins(str(tmp_path))] == ["real"]

    def test_should_parse_requirements_skipping_comments_and_blanks(self, loader, tmp_path):
        write_plugin(tmp_path, "with-deps",
                     requirements="# HTTP client\nhttpx==0.27.0\n\n  requests>=2.31  \n# trailing\n")

        info = loader.discover_plugins(str(tmp_path))[0]

        assert info["requirements"] == ["httpx==0.27.0", "requests>=2.31"]

    def test_should_set_empty_requirements_when_file_absent(self, loader, tmp_path):
        write_plugin(tmp_path, "no-deps")

        assert loader.discover_plugins(str(tmp_path))[0]["requirements"] == []

    def test_should_isolate_plugin_with_import_error(self, loader, tmp_path):
        broken = tmp_path / "broken"
        broken.mkdir()
        (broken / "plugin.py").write_text("import a_module_that_does_not_exist\n")
        write_plugin(tmp_path, "healthy")

        discovered = loader.discover_plugins(str(tmp_path))

        assert [p["module_name"] for p in discovered] == ["healthy"]

    def test_should_return_none_when_file_has_no_decorated_class(self, loader, tmp_path):
        plugin_dir = tmp_path / "plain"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text("class Plain:\n    pass\n")

        assert loader._load_plugin_file("plain", str(plugin_dir / "plugin.py")) is None

    def test_should_pick_first_class_when_multiple_plugins_defined(self, loader, tmp_path):
        plugin_dir = tmp_path / "multi"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(textwrap.dedent('''
            from app.plugins.base import plugin

            @plugin(name="Multi A", version="1.0")
            class MultiA:
                pass

            @plugin(name="Multi B", version="1.0")
            class MultiB:
                pass
        '''))

        info = loader._load_plugin_file("multi", str(plugin_dir / "plugin.py"))

        assert info["metadata"].name == "Multi A"


class TestConfigSchemaAndInstantiation:
    def test_should_read_config_schema_from_class(self, loader, tmp_path):
        plugin_dir = tmp_path / "schema"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(textwrap.dedent('''
            from app.plugins.base import plugin

            @plugin(name="Schema", version="1.0")
            class SchemaPlugin:
                @staticmethod
                def get_config_schema():
                    return {"type": "object", "properties": {"url": {"type": "string"}}}
        '''))

        info = loader._load_plugin_file("schema", str(plugin_dir / "plugin.py"))

        assert info["config_schema"] == {"type": "object",
                                         "properties": {"url": {"type": "string"}}}

    def test_should_tolerate_broken_config_schema(self, loader, tmp_path):
        plugin_dir = tmp_path / "bad-schema"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(textwrap.dedent('''
            from app.plugins.base import plugin

            @plugin(name="Bad schema", version="1.0")
            class BadSchema:
                @staticmethod
                def get_config_schema():
                    raise ValueError("nope")
        '''))

        info = loader._load_plugin_file("bad-schema", str(plugin_dir / "plugin.py"))

        assert info["config_schema"] is None

    def test_should_pass_context_when_constructor_accepts_it(self, loader, tmp_path):
        write_plugin(tmp_path, "ctx-plugin")
        info = loader._load_plugin_file("ctx-plugin", str(tmp_path / "ctx-plugin" / "plugin.py"))

        instance = loader.instantiate_plugin(info["plugin_class"], "CONTEXT")

        assert instance.context == "CONTEXT"

    def test_should_instantiate_without_context_when_constructor_takes_none(self, loader, tmp_path):
        plugin_dir = tmp_path / "no-ctx"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(textwrap.dedent('''
            from app.plugins.base import plugin

            @plugin(name="No ctx", version="1.0")
            class NoCtx:
                def __init__(self):
                    self.ready = True
        '''))

        info = loader._load_plugin_file("no-ctx", str(plugin_dir / "plugin.py"))

        assert loader.instantiate_plugin(info["plugin_class"], "CONTEXT").ready is True

    def test_should_propagate_constructor_failure(self, loader, tmp_path):
        plugin_dir = tmp_path / "boom"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.py").write_text(textwrap.dedent('''
            from app.plugins.base import plugin

            @plugin(name="Boom", version="1.0")
            class Boom:
                def __init__(self, context):
                    raise RuntimeError("cannot start")
        '''))

        info = loader._load_plugin_file("boom", str(plugin_dir / "plugin.py"))

        with pytest.raises(RuntimeError, match="cannot start"):
            loader.instantiate_plugin(info["plugin_class"], None)

    def test_should_return_no_events_for_unregistered_class(self, loader):
        class NotAPlugin:
            pass

        assert loader.get_plugin_subscribed_events(NotAPlugin) == []


# ===========================================================================
# Manager: discovery / lifecycle
# ===========================================================================

class TestDiscoveryIntoDatabase:
    async def test_should_insert_new_plugins_disabled_by_default(self, manager, db_session, tmp_path):
        write_plugin(tmp_path, "alpha", name="Alpha", events='"server.created"',
                     requirements="httpx\n")

        added = await manager.discover_plugins(str(tmp_path), db_session)

        assert added == 1
        from sqlalchemy import select
        row = (await db_session.execute(select(Plugin))).scalar_one()
        assert row.name == "Alpha"
        assert row.module_name == "alpha"
        assert row.enabled is False
        assert row.loaded is False
        assert row.config == {}
        assert row.subscribed_events == ["server.created"]
        assert row.requirements == ["httpx"]

    async def test_should_update_existing_row_without_duplicating(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha", name="Alpha", version="1.0.0",
                                 events='"server.created"')
        existing = await seed_plugin_row(db_session, plugin_dir, "alpha", name="Old name",
                                        version="0.9.0")

        added = await manager.discover_plugins(str(tmp_path), db_session)

        assert added == 0
        await db_session.refresh(existing)
        assert existing.name == "Alpha"
        assert existing.version == "1.0.0"
        assert existing.subscribed_events == ["server.created"]
        from sqlalchemy import func, select
        count = (await db_session.execute(select(func.count(Plugin.id)))).scalar()
        assert count == 1

    async def test_should_skip_plugins_already_discovered_twice(self, manager, db_session, tmp_path):
        write_plugin(tmp_path, "alpha")

        assert await manager.discover_plugins(str(tmp_path), db_session) == 1
        assert await manager.discover_plugins(str(tmp_path), db_session) == 0


class TestLoadAndUnload:
    async def test_should_load_plugin_and_mark_it_loaded(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha", name="Alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha", config={"url": "http://x"})

        assert await manager.load_plugin(row, db_session) is True

        assert manager.loaded_count() == 1
        assert manager.get_loaded_plugin_names() == [row.name]
        loaded = manager.loaded_plugins[row.id]
        assert loaded.context.config == {"url": "http://x"}
        assert loaded.context.plugin_id == row.id
        await db_session.refresh(row)
        assert row.loaded is True

    async def test_should_report_failure_when_plugin_file_disappeared(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha")
        (plugin_dir / "plugin.py").unlink()

        assert await manager.load_plugin(row, db_session) is False
        await db_session.refresh(row)
        assert row.loaded is False

    async def test_should_mark_not_loaded_when_constructor_raises(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(
            tmp_path, "boom",
            init='        raise RuntimeError("cannot start")',
        )
        row = await seed_plugin_row(db_session, plugin_dir, "boom")

        assert await manager.load_plugin(row, db_session) is False
        await db_session.refresh(row)
        assert row.loaded is False
        assert manager.loaded_count() == 0

    async def test_should_load_only_enabled_plugins_and_register_handlers(
            self, manager, db_session, tmp_path):
        enabled_dir = write_plugin(tmp_path, "on", name="On")
        disabled_dir = write_plugin(tmp_path, "off", name="Off")
        await seed_plugin_row(db_session, enabled_dir, "on", enabled=True)
        await seed_plugin_row(db_session, disabled_dir, "off", enabled=False)

        await manager.load_enabled_plugins(db_session)

        assert manager.get_loaded_plugin_names() == ["Plugin on"]
        assert manager._event_handlers_registered is True
        assert event_bus._handlers

    async def test_should_survive_a_plugin_that_fails_to_load(self, manager, db_session, tmp_path):
        good_dir = write_plugin(tmp_path, "good", name="Good")
        bad_dir = write_plugin(tmp_path, "bad", name="Bad")
        await seed_plugin_row(db_session, good_dir, "good")
        bad_row = await seed_plugin_row(db_session, bad_dir, "bad")
        (bad_dir / "plugin.py").unlink()

        await manager.load_enabled_plugins(db_session)

        assert manager.get_loaded_plugin_names() == ["Plugin good"]
        await db_session.refresh(bad_row)
        assert bad_row.loaded is False

    async def test_should_unload_plugin_closing_http_client(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha")
        await manager.load_plugin(row, db_session)
        client = manager.loaded_plugins[row.id].context.http_client
        with patch.object(client, "aclose", new=AsyncMock()) as aclose:
            assert await manager.unload_plugin(row.id, db_session) is True
        aclose.assert_awaited_once()

        assert manager.loaded_count() == 0
        await db_session.refresh(row)
        assert row.loaded is False

    async def test_should_refuse_to_unload_plugin_that_is_not_loaded(self, manager, db_session):
        assert await manager.unload_plugin(1234, db_session) is False

    async def test_should_unload_every_plugin_on_shutdown(self, manager, db_session, tmp_path):
        for module in ("one", "two"):
            plugin_dir = write_plugin(tmp_path, module, name=module.title())
            row = await seed_plugin_row(db_session, plugin_dir, module)
            await manager.load_plugin(row, db_session)

        await manager.unload_all()

        assert manager.loaded_count() == 0

    async def test_should_enable_plugin_and_load_it(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha", enabled=False)

        assert await manager.enable_plugin(row.id, db_session) is True

        await db_session.refresh(row)
        assert (row.enabled, row.loaded) == (True, True)
        assert manager.loaded_count() == 1

    async def test_should_not_enable_unknown_plugin(self, manager, db_session):
        assert await manager.enable_plugin(9999, db_session) is False

    async def test_should_disable_plugin_and_its_integrations(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha", name="Alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha", enabled=True)
        await manager.load_plugin(row, db_session)
        active = Integration(name="slack", type="webhook", plugin_id=row.id, enabled=True,
                             config={}, events_subscribed=[])
        idle = Integration(name="mail", type="webhook", plugin_id=row.id, enabled=False,
                           config={}, events_subscribed=[])
        db_session.add_all([active, idle])
        await db_session.commit()

        result = await manager.disable_plugin(row.id, db_session)

        assert result == {"success": True, "disabled_integrations": 1}
        await db_session.refresh(row)
        await db_session.refresh(active)
        assert row.enabled is False
        assert row.loaded is False
        assert active.enabled is False
        assert idle.enabled is False
        assert manager.loaded_count() == 0

    async def test_should_report_failure_when_disabling_unknown_plugin(self, manager, db_session):
        assert await manager.disable_plugin(4321, db_session) == {
            "success": False, "disabled_integrations": 0,
        }


# ===========================================================================
# Manager: event dispatch
# ===========================================================================

class TestEventDispatch:
    async def _loaded(self, manager, db_session, tmp_path, module="alpha",
                      events='"server.created"'):
        plugin_dir = write_plugin(tmp_path, module, name=module.title(), events=events)
        subscribed = [e.strip().strip('"') for e in events.split(",")]
        row = await seed_plugin_row(db_session, plugin_dir, module, subscribed_events=subscribed)
        await manager.load_plugin(row, db_session)
        return manager.loaded_plugins[row.id]

    async def test_should_invoke_only_plugins_subscribed_to_the_event(
            self, manager, db_session, tmp_path):
        server_listener = await self._loaded(manager, db_session, tmp_path, "srv")
        peer_listener = await self._loaded(manager, db_session, tmp_path, "peer",
                                           events='"peer.created"')

        await manager._dispatch_event_to_plugins(EventType.SERVER_CREATED, {"id": 1})

        assert server_listener.instance.seen == [{"id": 1}]
        assert peer_listener.instance.seen == []

    async def test_should_invoke_wildcard_subscribers_for_every_event(
            self, manager, db_session, tmp_path):
        wild = await self._loaded(manager, db_session, tmp_path, "wild", events='"*"')

        await manager._dispatch_event_to_plugins(EventType.SERVER_CREATED, {"n": 1})
        await manager._dispatch_event_to_plugins(EventType.PEER_DELETED, {"n": 2})

        assert wild.instance.seen == [{"n": 1}, {"n": 2}]

    async def test_should_record_stats_after_successful_invocation(
            self, manager, db_session, api_db, tmp_path):
        loaded = await self._loaded(manager, db_session, tmp_path)

        await manager._dispatch_event_to_plugins(EventType.SERVER_CREATED, {"id": 5})

        row = await self._row(api_db, loaded)
        assert row.total_invocations == 1
        assert row.total_errors == 0
        assert row.last_invoked_at is not None

    async def test_should_isolate_handler_errors_and_record_them(
            self, manager, db_session, api_db, tmp_path):
        loaded = await self._loaded(
            manager, db_session, tmp_path, "failing",
            events='"server.created", "peer.created"',
        )

        async def boom(self, event_data):
            raise ValueError("webhook returned 500")

        loaded.plugin_class.handle  # ensure handler exists
        loaded.instance.seen = []

        await manager._invoke_plugin(loaded, EventType.SERVER_CREATED, {"id": 1})

        # first invocation works
        row = await self._row(api_db, loaded)
        assert row.total_invocations == 1

        # make the handler explode and dispatch again: no exception escapes
        loaded.plugin_class._plugin_metadata.event_handlers["server.created"] = [boom]
        await manager._dispatch_event_to_plugins(EventType.SERVER_CREATED, {"id": 2})

        row = await self._row(api_db, loaded)
        assert row.total_errors == 1
        assert row.last_error_message == "webhook returned 500"
        assert row.last_error_at is not None

    async def _row(self, api_db, loaded):
        """Read the plugin row through a fresh session (avoids stale snapshots)."""
        from sqlalchemy import select
        async with api_db.sessionmaker() as session:
            return (await session.execute(
                select(Plugin).where(Plugin.id == loaded.db_id)
            )).scalar_one()

    async def test_should_do_nothing_when_no_plugin_subscribes(self, manager, db_session):
        with patch.object(manager, "_invoke_plugin", new=AsyncMock()) as invoke:
            await manager._dispatch_event_to_plugins(EventType.SERVER_CREATED, {})

        invoke.assert_not_awaited()


class TestErrorRecording:
    async def test_should_truncate_long_error_messages(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha")

        await manager._record_plugin_error(row.id, "x" * 1500)

        await db_session.refresh(row)
        assert len(row.last_error_message) == 1000
        assert row.total_errors == 1

    async def test_should_ignore_errors_for_unknown_plugins(self, manager):
        await manager._record_plugin_error(9999, "nobody home")
        await manager._update_plugin_stats(9999)

    async def test_should_handle_error_of_loaded_plugin(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha")
        row = await seed_plugin_row(db_session, plugin_dir, "alpha")
        await manager.load_plugin(row, db_session)

        await manager._handle_plugin_error(manager.loaded_plugins[row.id], RuntimeError("kaboom"))

        await db_session.refresh(row)
        assert row.last_error_message == "kaboom"
        assert row.total_errors == 1


class TestIntegrationTrigger:
    async def _loaded(self, manager, db_session, tmp_path):
        plugin_dir = write_plugin(tmp_path, "alpha", events='"server.created"')
        row = await seed_plugin_row(db_session, plugin_dir, "alpha")
        await manager.load_plugin(row, db_session)
        return manager.loaded_plugins[row.id]

    async def test_should_invoke_plugin_for_integration_event(self, manager, db_session, tmp_path):
        loaded = await self._loaded(manager, db_session, tmp_path)

        await manager.trigger_plugin_for_integration(
            loaded.db_id, {"event_type": "server.created", "id": 9}
        )

        assert loaded.instance.seen == [{"event_type": "server.created", "id": 9}]

    async def test_should_skip_trigger_when_plugin_not_loaded(self, manager, db_session, tmp_path, caplog):
        await self._loaded(manager, db_session, tmp_path)

        with caplog.at_level("WARNING"):
            await manager.trigger_plugin_for_integration(4242, {"event_type": "server.created"})

        assert "not loaded" in caplog.text

    async def test_should_skip_trigger_without_event_type(self, manager, db_session, tmp_path, caplog):
        loaded = await self._loaded(manager, db_session, tmp_path)

        with caplog.at_level("ERROR"):
            await manager.trigger_plugin_for_integration(loaded.db_id, {"id": 1})

        assert "missing 'event_type'" in caplog.text
        assert loaded.instance.seen == []

    async def test_should_skip_trigger_with_unknown_event_type(self, manager, db_session, tmp_path, caplog):
        loaded = await self._loaded(manager, db_session, tmp_path)

        with caplog.at_level("ERROR"):
            await manager.trigger_plugin_for_integration(
                loaded.db_id, {"event_type": "not.an.event"}
            )

        assert "Invalid event type" in caplog.text
        assert loaded.instance.seen == []


class TestLoadedPluginInstanceHandlers:
    def test_should_resolve_exact_and_wildcard_handlers(self):
        from app.plugins.base import PluginMetadata

        class Demo:
            def handle(self, event_data):
                pass

        metadata = PluginMetadata("Demo", "1.0")
        metadata.add_event_handler(["server.created"], Demo.handle)
        metadata.add_event_handler(["*"], Demo.handle)
        _plugin_registry[Demo] = metadata

        loaded = LoadedPluginInstance(
            db_id=1, name="Demo", plugin_class=Demo, instance=Demo(),
            context=None, subscribed_events=["*"],
        )

        assert loaded.get_handlers_for_event("server.created") == [Demo.handle, Demo.handle]
        assert loaded.get_handlers_for_event("peer.created") == [Demo.handle]

    def test_should_return_no_handlers_for_unregistered_class(self):
        class Orphan:
            pass

        loaded = LoadedPluginInstance(1, "Orphan", Orphan, Orphan(), None, [])

        assert loaded.get_handlers_for_event("server.created") == []
