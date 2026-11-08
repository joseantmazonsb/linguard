"""Tests for ``app/api/plugins.py``.

Plugins are discovered and loaded from a real directory under ``tmp_path``
(the ``plugins_directory`` setting is redirected there), so discovery, module
import, enable and disable all run the production code paths.
"""

from sqlalchemy import select

from app.main import app
from app.models.audit import AuditLog
from app.models.integration import Integration
from app.models.plugin import Plugin

BASE = "/api/v1/plugins"


async def _discover(auth_client):
    return auth_client.post(f"{BASE}/discover")


async def _only_plugin(db_session):
    return (await db_session.execute(select(Plugin))).scalars().all()


async def _plugin_id(db_session):
    return (await db_session.execute(select(Plugin.id))).scalar_one()


async def _audit_actions(db_session):
    result = await db_session.execute(select(AuditLog.action))
    return [row[0] for row in result.all()]


async def _stored_plugin(db_session, plugin_id):
    db_session.expire_all()
    return (
        await db_session.execute(select(Plugin).where(Plugin.id == plugin_id))
    ).scalar_one()


# ---------------------------------------------------------------------------
# Discovery & listing
# ---------------------------------------------------------------------------

async def test_should_discover_plugin_from_directory(auth_client, plugins_dir, db_session):
    response = await _discover(auth_client)

    assert response.status_code == 200
    body = response.json()
    assert body["newly_discovered"] == 1
    assert body["total_plugins"] == 1
    assert body["message"] == "Discovered 1 new plugin(s). Total: 1"

    plugins = await _only_plugin(db_session)
    assert len(plugins) == 1
    plugin = plugins[0]
    assert plugin.name == "Demo Plugin"
    assert plugin.module_name == "demo_plugin"
    assert plugin.version == "1.0.0"
    assert plugin.author == "tester"
    assert plugin.enabled is False
    assert plugin.loaded is False
    assert plugin.subscribed_events == ["server.created"]
    assert plugin.requirements == ["httpx>=0.24"]
    assert plugin.config_schema == {"api_key": {"type": "string", "required": True}}
    assert plugin.file_path.endswith("plugin.py")

    assert await _audit_actions(db_session) == ["DISCOVER"]


async def test_should_report_no_new_plugins_when_discovering_twice(
    auth_client, plugins_dir
):
    await _discover(auth_client)

    response = await _discover(auth_client)

    assert response.status_code == 200
    body = response.json()
    assert body["newly_discovered"] == 0
    assert body["total_plugins"] == 1


async def test_should_use_default_directory_when_plugins_directory_is_empty(
    auth_client, plugins_dir, db_session, tmp_path, monkeypatch
):
    from app.models.settings import GlobalSettings

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.plugins_directory = ""
    await db_session.commit()
    # "./plugins" is resolved against the working directory.
    monkeypatch.chdir(tmp_path)

    response = await _discover(auth_client)

    assert response.status_code == 200
    assert (tmp_path / "plugins").is_dir()


async def test_should_list_and_get_plugins_when_discovered(auth_client, plugins_dir, db_session):
    empty = auth_client.get(BASE + "/")
    assert empty.status_code == 200
    assert empty.json() == {"plugins": [], "total": 0}

    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    listing = auth_client.get(BASE + "/")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["plugins"][0]["name"] == "Demo Plugin"

    fetched = auth_client.get(f"{BASE}/{plugin_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == plugin_id
    assert body["config_schema"] == {"api_key": {"type": "string", "required": True}}
    assert body["subscribed_events"] == ["server.created"]


async def test_should_return_404_when_plugin_does_not_exist(auth_client, plugins_dir):
    assert auth_client.get(f"{BASE}/4242").status_code == 404
    assert auth_client.post(f"{BASE}/4242/enable").status_code == 404
    assert auth_client.post(f"{BASE}/4242/disable").status_code == 404
    assert auth_client.put(f"{BASE}/4242/config", json={"config": {}}).status_code == 404
    assert auth_client.delete(f"{BASE}/4242").status_code == 404


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------

async def test_should_enable_plugin_when_file_is_loadable(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    response = auth_client.post(f"{BASE}/{plugin_id}/enable")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Plugin 'Demo Plugin' enabled successfully"
    assert body["plugin"]["enabled"] is True
    assert body["plugin"]["loaded"] is True

    stored = await _stored_plugin(db_session, plugin_id)
    assert stored.enabled is True
    assert stored.loaded is True
    assert plugin_id in app.container.plugin_manager().loaded_plugins

    assert "ENABLE" in await _audit_actions(db_session)


async def test_should_report_already_enabled_when_enabling_twice(
    auth_client, plugins_dir, db_session
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    auth_client.post(f"{BASE}/{plugin_id}/enable")

    response = auth_client.post(f"{BASE}/{plugin_id}/enable")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Plugin 'Demo Plugin' is already enabled"
    assert body["plugin"]["loaded"] is True


async def test_should_disable_plugin_when_it_is_enabled(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    auth_client.post(f"{BASE}/{plugin_id}/enable")

    response = auth_client.post(f"{BASE}/{plugin_id}/disable")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Plugin 'Demo Plugin' disabled successfully"

    stored = await _stored_plugin(db_session, plugin_id)
    assert stored.enabled is False
    assert stored.loaded is False
    assert plugin_id not in app.container.plugin_manager().loaded_plugins

    assert "DISABLE" in await _audit_actions(db_session)


async def test_should_disable_related_integrations_when_plugin_is_disabled(
    auth_client, plugins_dir, db_session
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    auth_client.post(f"{BASE}/{plugin_id}/enable")

    integration = Integration(
        name="Plugin integration",
        type="plugin:demo_plugin",
        plugin_id=plugin_id,
        config={},
        events_subscribed=["server.created"],
        enabled=True,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)
    integration_id = integration.id

    response = auth_client.post(f"{BASE}/{plugin_id}/disable")

    assert response.status_code == 200
    assert "(1 integration(s) also disabled)" in response.json()["message"]

    db_session.expire_all()
    stored = (
        await db_session.execute(select(Integration).where(Integration.id == integration_id))
    ).scalar_one()
    assert stored.enabled is False


async def test_should_report_already_disabled_when_disabling_twice(
    auth_client, plugins_dir, db_session
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    response = auth_client.post(f"{BASE}/{plugin_id}/disable")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Plugin 'Demo Plugin' is already disabled"


async def test_should_return_500_when_plugin_cannot_be_loaded(
    auth_client, plugins_dir, db_session, tmp_path
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    # A file without a @plugin decorated class cannot be loaded.
    broken = tmp_path / "broken_plugin.py"
    broken.write_text("VALUE = 42\n")
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.file_path = str(broken)
    await db_session.commit()

    response = auth_client.post(f"{BASE}/{plugin_id}/enable")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to enable plugin: could not load 'Demo Plugin'"

    # The failed enable is not persisted as an enabled plugin.
    stored = await _stored_plugin(db_session, plugin_id)
    assert stored.enabled is False
    assert stored.loaded is False


async def test_should_return_500_when_plugin_manager_fails_to_enable(
    auth_client, plugins_dir, db_session
):
    from unittest.mock import AsyncMock, patch

    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    manager = app.container.plugin_manager()

    with patch.object(
        manager, "enable_plugin", AsyncMock(side_effect=RuntimeError("loader exploded"))
    ):
        response = auth_client.post(f"{BASE}/{plugin_id}/enable")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Failed to enable plugin:")


async def test_should_return_500_when_plugin_manager_fails_to_disable(
    auth_client, plugins_dir, db_session
):
    from unittest.mock import AsyncMock, patch

    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    auth_client.post(f"{BASE}/{plugin_id}/enable")
    manager = app.container.plugin_manager()

    with patch.object(
        manager, "disable_plugin", AsyncMock(side_effect=RuntimeError("unloader exploded"))
    ):
        response = auth_client.post(f"{BASE}/{plugin_id}/disable")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Failed to disable plugin:")


# ---------------------------------------------------------------------------
# Config update & delete
# ---------------------------------------------------------------------------

async def test_should_update_plugin_config_when_plugin_exists(
    auth_client, plugins_dir, db_session
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    response = auth_client.put(
        f"{BASE}/{plugin_id}/config", json={"config": {"api_key": "secret"}}
    )

    assert response.status_code == 200
    assert response.json()["config"] == {"api_key": "secret"}

    stored = await _stored_plugin(db_session, plugin_id)
    assert stored.config == {"api_key": "secret"}

    assert "UPDATE_CONFIG" in await _audit_actions(db_session)


async def test_should_reject_invalid_legacy_field_map_config(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)

    for config in ({}, {"api_key": 123}):
        response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": config})
        assert response.status_code in (400, 422)
        assert "api_key" in str(response.json()["detail"])

    assert (await _stored_plugin(db_session, plugin_id)).config == {}
    assert "UPDATE_CONFIG" not in await _audit_actions(db_session)


async def test_should_validate_standard_json_schema_before_persisting(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = {
        "type": "object",
        "properties": {"settings": {"type": "object", "properties": {"port": {"type": "integer", "minimum": 1}}, "required": ["port"]}},
        "required": ["settings"],
        "additionalProperties": False,
    }
    plugin.config = {"settings": {"port": 42}}
    await db_session.commit()

    for config in ({}, {"settings": {"port": 0}}, {"settings": {"port": 4}, "extra": True}):
        response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": config})
        assert response.status_code in (400, 422)
        assert response.json()["detail"]
        assert (await _stored_plugin(db_session, plugin_id)).config == {"settings": {"port": 42}}

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {"settings": {"port": 80}}})
    assert response.status_code == 200
    assert (await _stored_plugin(db_session, plugin_id)).config == {"settings": {"port": 80}}


async def test_should_reject_invalid_declared_schema_without_persisting(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = {"type": "not-a-real-type"}
    await db_session.commit()

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {}})

    assert response.status_code in (400, 422)
    assert "schema" in str(response.json()["detail"]).lower()
    assert (await _stored_plugin(db_session, plugin_id)).config == {}


async def test_should_validate_schema_without_type_keyword(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = {"minProperties": 1}
    await db_session.commit()

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {}})

    assert response.status_code in (400, 422)
    assert (await _stored_plugin(db_session, plugin_id)).config == {}
    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {"enabled": True}})
    assert response.status_code == 200


async def test_should_reject_remote_schema_reference_without_fetching(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = {"$ref": "https://example.test/schema.json"}
    await db_session.commit()

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {}})

    assert response.status_code in (400, 422)
    assert "schema" in str(response.json()["detail"]).lower()
    assert (await _stored_plugin(db_session, plugin_id)).config == {}


async def test_should_validate_local_schema_references(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = {
        "$defs": {"token": {"type": "string", "minLength": 3}},
        "type": "object",
        "properties": {"token": {"$ref": "#/$defs/token"}},
        "required": ["token"],
    }
    await db_session.commit()

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {"token": "x"}})
    assert response.status_code == 422
    assert "token" in response.json()["detail"]
    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {"token": "abc"}})
    assert response.status_code == 200


async def test_should_allow_config_when_no_schema_declared(auth_client, plugins_dir, db_session):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    plugin = await _stored_plugin(db_session, plugin_id)
    plugin.config_schema = None
    await db_session.commit()

    response = auth_client.put(f"{BASE}/{plugin_id}/config", json={"config": {"value": 123}})

    assert response.status_code == 200
    assert (await _stored_plugin(db_session, plugin_id)).config == {"value": 123}


async def test_should_delete_plugin_and_unload_it_when_loaded(
    auth_client, plugins_dir, db_session
):
    await _discover(auth_client)
    plugin_id = await _plugin_id(db_session)
    auth_client.post(f"{BASE}/{plugin_id}/enable")
    manager = app.container.plugin_manager()
    assert plugin_id in manager.loaded_plugins

    response = auth_client.delete(f"{BASE}/{plugin_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Plugin 'Demo Plugin' removed from database (files not deleted)"
    assert plugin_id not in manager.loaded_plugins

    db_session.expire_all()
    remaining = (
        await db_session.execute(select(Plugin).where(Plugin.id == plugin_id))
    ).scalar_one_or_none()
    assert remaining is None


async def test_should_require_authentication_when_listing_plugins(api_client, seeded_db):
    assert api_client.get(BASE + "/").status_code == 401
