"""Tests for ``app/api/integrations.py``.

The integration CRUD endpoints run against the real per-test SQLite database.
The only boundary replaced is outbound HTTP to the Telegram API: the module's
``httpx.AsyncClient`` is swapped for a fake that returns canned JSON, so the
production code path (URL building, validation, error mapping) still runs.
"""

from unittest.mock import patch

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.integration import Integration
from app.models.plugin import Plugin
from app.models.traffic_trigger import ThresholdWindow, TrafficDirection, TrafficScope, TrafficTrigger

WEBHOOK_PAYLOAD = {
    "name": "Ops webhook",
    "description": "posts events",
    "type": "webhook",
    "config": {"url": "https://hooks.example.com/linguard", "method": "POST"},
    "events_subscribed": ["server.created", "peer.connected"],
}


# ---------------------------------------------------------------------------
# Fake Telegram HTTP client (true network boundary)
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeAsyncClient:
    """Async context manager standing in for ``httpx.AsyncClient``."""

    last_instance = None

    def __init__(self, response):
        self._response = response
        self.requested_urls = []
        FakeAsyncClient.last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.requested_urls.append(url)
        return self._response


def telegram_response(chat_id=12345, ok=True, description=None, result=None):
    if result is None:
        result = [{"message": {"chat": {"id": chat_id}}}] if chat_id is not None else []
    data = {"ok": ok, "result": result}
    if description:
        data["description"] = description
    return data


def patch_telegram(payload):
    return patch(
        "app.api.integrations.httpx.AsyncClient",
        lambda *a, **kw: FakeAsyncClient(FakeResponse(payload)),
    )


async def _seed_builtin_in_app(db_session):
    integration = Integration(
        name="In-App Notifications",
        description="Built-in notification center",
        type="notification",
        config={},
        events_subscribed=["server.reloaded", "peer.connected", "peer.disconnected"],
        enabled=True,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)
    return integration


async def _audit_rows(db_session):
    result = await db_session.execute(select(AuditLog))
    return result.scalars().all()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def test_should_create_integration_and_persist_it(auth_client, db_session):
    response = auth_client.post("/api/v1/integrations/", json=WEBHOOK_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ops webhook"
    assert body["type"] == "webhook"
    assert body["config"]["url"] == "https://hooks.example.com/linguard"
    assert body["events_subscribed"] == ["server.created", "peer.connected"]
    assert body["enabled"] is True
    assert body["total_triggered"] == 0

    stored = (
        await db_session.execute(select(Integration).where(Integration.id == body["id"]))
    ).scalar_one()
    assert stored.plugin_id is None

    audit = await _audit_rows(db_session)
    assert [(a.action, a.resource_type) for a in audit] == [("CREATE", "integration")]


async def test_should_list_and_get_integrations_when_they_exist(auth_client):
    created = auth_client.post("/api/v1/integrations/", json=WEBHOOK_PAYLOAD).json()

    listing = auth_client.get("/api/v1/integrations/")
    assert listing.status_code == 200
    assert [i["id"] for i in listing.json()] == [created["id"]]

    fetched = auth_client.get(f"/api/v1/integrations/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Ops webhook"


async def test_should_return_404_when_integration_does_not_exist(auth_client):
    assert auth_client.get("/api/v1/integrations/999").status_code == 404
    assert auth_client.put("/api/v1/integrations/999", json={"name": "x"}).status_code == 404
    assert auth_client.delete("/api/v1/integrations/999").status_code == 404


async def test_should_update_integration_when_payload_is_partial(auth_client, db_session):
    created = auth_client.post("/api/v1/integrations/", json=WEBHOOK_PAYLOAD).json()

    response = auth_client.put(
        f"/api/v1/integrations/{created['id']}",
        json={"name": "Renamed webhook", "enabled": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed webhook"
    assert body["enabled"] is False
    assert body["config"] == WEBHOOK_PAYLOAD["config"]  # untouched

    actions = [a.action for a in await _audit_rows(db_session)]
    assert "UPDATE" in actions


async def test_should_delete_integration_and_clear_trigger_references(auth_client, db_session):
    created = auth_client.post("/api/v1/integrations/", json=WEBHOOK_PAYLOAD).json()
    trigger = TrafficTrigger(
        name="too much traffic",
        scope=TrafficScope.GLOBAL,
        direction=TrafficDirection.COMBINED,
        threshold_bytes=1024,
        window=ThresholdWindow.LAST_HOUR,
        trigger_integrations=[created["id"]],
        enabled=True,
    )
    db_session.add(trigger)
    await db_session.commit()
    await db_session.refresh(trigger)

    response = auth_client.delete(f"/api/v1/integrations/{created['id']}")

    assert response.status_code == 204
    assert (
        await db_session.execute(select(Integration).where(Integration.id == created["id"]))
    ).scalar_one_or_none() is None

    await db_session.refresh(trigger)
    assert trigger.trigger_integrations == []


# ---------------------------------------------------------------------------
# Built-in "In-App Notifications" protection
# ---------------------------------------------------------------------------

async def test_should_reject_rename_when_integration_is_built_in(auth_client, db_session):
    builtin = await _seed_builtin_in_app(db_session)

    response = auth_client.put(
        f"/api/v1/integrations/{builtin.id}", json={"name": "Something else"}
    )

    assert response.status_code == 403
    assert "name" in response.json()["detail"]


async def test_should_reject_description_change_when_integration_is_built_in(
    auth_client, db_session
):
    builtin = await _seed_builtin_in_app(db_session)

    response = auth_client.put(
        f"/api/v1/integrations/{builtin.id}", json={"description": "new text"}
    )

    assert response.status_code == 403
    assert "description" in response.json()["detail"]


async def test_should_reject_unsupported_events_when_integration_is_built_in(
    auth_client, db_session
):
    builtin = await _seed_builtin_in_app(db_session)

    response = auth_client.put(
        f"/api/v1/integrations/{builtin.id}",
        json={"events_subscribed": ["server.created"]},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "peer.connected" in detail and "server.reloaded" in detail


async def test_should_update_allowed_events_when_integration_is_built_in(
    auth_client, db_session
):
    builtin = await _seed_builtin_in_app(db_session)

    response = auth_client.put(
        f"/api/v1/integrations/{builtin.id}",
        json={"events_subscribed": ["peer.connected"]},
    )

    assert response.status_code == 200
    assert response.json()["events_subscribed"] == ["peer.connected"]


async def test_should_reject_delete_when_integration_is_built_in(auth_client, db_session):
    builtin = await _seed_builtin_in_app(db_session)

    response = auth_client.delete(f"/api/v1/integrations/{builtin.id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Cannot delete the built-in In-App Notifications integration"
    assert (
        await db_session.execute(select(Integration).where(Integration.id == builtin.id))
    ).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

async def test_should_fetch_chat_id_when_creating_telegram_integration(auth_client):
    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {"bot_token": "123:ABC"},
        "events_subscribed": ["server.created"],
    }

    with patch_telegram(telegram_response(chat_id=987654)) as fake:
        response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 201
    config = response.json()["config"]
    assert config["chat_id"] == "987654"
    assert config["bot_token"] == "123:ABC"
    # The bot token is used to call the Telegram getUpdates API.
    assert FakeAsyncClient.last_instance.requested_urls == [
        "https://api.telegram.org/bot123:ABC/getUpdates"
    ]
    assert fake is not None


async def test_should_reject_telegram_integration_when_bot_token_missing(auth_client):
    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {},
        "events_subscribed": [],
    }

    response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Bot token is required for Telegram integration"


async def test_should_reject_telegram_integration_when_bot_token_is_invalid(auth_client):
    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {"bot_token": "bad"},
        "events_subscribed": [],
    }

    with patch_telegram(telegram_response(ok=False, description="Unauthorized")):
        response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid bot token: Unauthorized"


async def test_should_reject_telegram_integration_when_bot_has_no_messages(auth_client):
    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {"bot_token": "123:ABC"},
        "events_subscribed": [],
    }

    with patch_telegram(telegram_response(chat_id=None, result=[])):
        response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 400
    assert "Please send a message to your bot first" in response.json()["detail"]


async def test_should_reject_telegram_integration_when_last_update_has_no_chat(auth_client):
    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {"bot_token": "123:ABC"},
        "events_subscribed": [],
    }

    with patch_telegram({"ok": True, "result": [{"edited_message": {}}]}):
        response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 400
    assert "Could not extract chat ID" in response.json()["detail"]


async def test_should_reject_telegram_integration_when_api_is_unreachable(auth_client):
    import httpx

    class UnreachableClient(FakeAsyncClient):
        async def get(self, url, **kwargs):
            raise httpx.ConnectError("connection refused")

    payload = {
        "name": "Telegram alerts",
        "type": "telegram",
        "config": {"bot_token": "123:ABC"},
        "events_subscribed": [],
    }

    with patch(
        "app.api.integrations.httpx.AsyncClient",
        lambda *a, **kw: UnreachableClient(FakeResponse({})),
    ):
        response = auth_client.post("/api/v1/integrations/", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Failed to connect to Telegram API")


async def test_should_refresh_chat_id_when_telegram_bot_token_changes(auth_client, db_session):
    integration = Integration(
        name="Telegram alerts",
        type="telegram",
        config={"bot_token": "old-token", "chat_id": "111"},
        events_subscribed=["server.created"],
        enabled=True,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    with patch_telegram(telegram_response(chat_id=222)):
        response = auth_client.put(
            f"/api/v1/integrations/{integration.id}",
            json={"config": {"bot_token": "new-token"}},
        )

    assert response.status_code == 200
    config = response.json()["config"]
    assert config == {"bot_token": "new-token", "chat_id": "222"}
    assert FakeAsyncClient.last_instance.requested_urls[-1].startswith(
        "https://api.telegram.org/botnew-token/getUpdates"
    )


async def test_should_reject_empty_bot_token_when_updating_telegram(auth_client, db_session):
    integration = Integration(
        name="Telegram alerts",
        type="telegram",
        config={"bot_token": "old-token", "chat_id": "111"},
        events_subscribed=[],
        enabled=True,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)

    response = auth_client.put(
        f"/api/v1/integrations/{integration.id}", json={"config": {"bot_token": ""}}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Bot token is required for Telegram integration"


# ---------------------------------------------------------------------------
# Plugin-based integrations and available types
# ---------------------------------------------------------------------------

async def test_should_create_plugin_integration_when_plugin_exists(auth_client, db_session):
    plugin = Plugin(
        name="Demo Plugin",
        version="1.0.0",
        module_name="demo_plugin",
        file_path="/tmp/demo/plugin.py",
        enabled=False,
    )
    db_session.add(plugin)
    await db_session.commit()
    await db_session.refresh(plugin)

    response = auth_client.post(
        "/api/v1/integrations/",
        json={
            "name": "Demo integration",
            "type": "plugin:demo_plugin",
            "config": {"token": "x"},
            "events_subscribed": ["server.created"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "plugin:demo_plugin"

    stored = (
        await db_session.execute(select(Integration).where(Integration.id == body["id"]))
    ).scalar_one()
    assert stored.plugin_id == plugin.id
    assert stored.config == {"token": "x"}


async def test_should_return_404_when_plugin_integration_type_is_unknown(auth_client):
    response = auth_client.post(
        "/api/v1/integrations/",
        json={
            "name": "Ghost",
            "type": "plugin:does_not_exist",
            "config": {},
            "events_subscribed": [],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Plugin 'does_not_exist' not found"


async def test_should_list_builtin_and_plugin_types_when_plugins_exist(auth_client, db_session):
    db_session.add(
        Plugin(
            name="Demo Plugin",
            version="2.0.0",
            description="does demo things",
            author="tester",
            module_name="demo_plugin",
            file_path="/tmp/demo/plugin.py",
            config_schema={"api_key": {"type": "string"}},
            enabled=True,
        )
    )
    await db_session.commit()

    response = auth_client.get("/api/v1/integrations/types/available")

    assert response.status_code == 200
    types = {t["type"]: t for t in response.json()}
    assert {"notification", "webhook", "email", "slack", "discord", "telegram", "script"} <= set(types)
    plugin_type = types["plugin:demo_plugin"]
    assert plugin_type["name"] == "Demo Plugin"
    assert plugin_type["is_plugin"] is True
    assert plugin_type["plugin_author"] == "tester"
    assert plugin_type["plugin_version"] == "2.0.0"
    assert plugin_type["config_schema"] == {"api_key": {"type": "string"}}


async def test_should_require_authentication_when_listing_integrations(api_client, seeded_db):
    assert api_client.get("/api/v1/integrations/").status_code == 401
