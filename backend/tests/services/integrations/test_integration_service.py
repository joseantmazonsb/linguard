"""Tests for IntegrationService: CRUD, event fan-out and every transport."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.integration_service as integration_module
from app.core.events import EventType, event_bus
from app.models.integration import Integration
from app.models.traffic_trigger import ThresholdWindow, TrafficScope, TrafficTrigger
from app.services.integration_service import IntegrationService
from app.services.notification_service import NotificationService

EVENT = {
    "event_type": "server.created",
    "source_type": "server",
    "source_id": 4,
    "payload": {"name": "edge-1"},
    "timestamp": "2026-01-01 00:00:00 UTC",
    "user_id": 1,
}

NORMALIZED = {
    "event_type": "server.created",
    "resource_type": "server",
    "resource_id": 4,
    "metadata": {"name": "edge-1"},
    "timestamp": "2026-01-01 00:00:00 UTC",
    "user_id": 1,
}


@pytest.fixture
def notification_service():
    return NotificationService()


@pytest.fixture
def service(notification_service):
    return IntegrationService(notification_service=notification_service)


def make_integration(type_="webhook", config=None, enabled=True, **kwargs):
    return Integration(
        id=kwargs.pop("id", 1),
        name=kwargs.pop("name", "test integration"),
        type=type_,
        config=config if config is not None else {},
        events_subscribed=kwargs.pop("events_subscribed", ["server.created"]),
        enabled=enabled,
        total_triggered=kwargs.pop("total_triggered", 0),
        **kwargs,
    )


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise integration_module.httpx.HTTPStatusError(
                "error", request=MagicMock(), response=MagicMock(status_code=self.status_code)
            )


def patch_http(method="post", response=None, error=None):
    """Patch httpx.AsyncClient in integration_service with a recording fake."""
    client = MagicMock()
    for verb in ("post", "put", "get"):
        if verb == method:
            if error:
                setattr(client, verb, AsyncMock(side_effect=error))
            else:
                setattr(client, verb, AsyncMock(return_value=response or FakeResponse()))
        else:
            setattr(client, verb, AsyncMock(return_value=response or FakeResponse()))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch.object(integration_module.httpx, "AsyncClient", return_value=cm), client


async def _persist(db_session, **kwargs):
    integration = Integration(
        name=kwargs.pop("name", "integration"),
        type=kwargs.pop("type", "webhook"),
        config=kwargs.pop("config", {"url": "https://example.test/hook"}),
        events_subscribed=kwargs.pop("events_subscribed", ["server.created"]),
        enabled=kwargs.pop("enabled", True),
        **kwargs,
    )
    db_session.add(integration)
    await db_session.commit()
    await db_session.refresh(integration)
    return integration


# ----------------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------------


async def test_should_create_and_read_integration_when_persisted(service, api_db, db_session):
    created = await service.create_integration(
        db_session,
        name="hooks",
        type="webhook",
        config={"url": "https://example.test"},
        events_subscribed=["server.created"],
        description="desc",
        enabled=False,
        plugin_id=None,
    )

    assert created.id is not None
    fetched = await service.get_integration(db_session, created.id)
    assert fetched.name == "hooks"
    assert fetched.description == "desc"
    assert fetched.enabled is False
    assert fetched.events_subscribed == ["server.created"]


async def test_should_only_return_enabled_integrations_when_filtered(service, api_db, db_session):
    await _persist(db_session, name="enabled", enabled=True)
    await _persist(db_session, name="disabled", enabled=False)

    all_rows = await service.get_integrations(db_session)
    enabled_rows = await service.get_integrations(db_session, enabled_only=True)

    assert {i.name for i in all_rows} == {"enabled", "disabled"}
    assert [i.name for i in enabled_rows] == ["enabled"]


async def test_should_return_none_when_integration_does_not_exist(service, api_db, db_session):
    assert await service.get_integration(db_session, 999) is None


async def test_should_update_fields_when_values_given(service, api_db, db_session):
    integration = await _persist(db_session)

    updated = await service.update_integration(
        db_session,
        integration.id,
        name="renamed",
        enabled=False,
        config=None,  # None values must be ignored
        unknown_field="ignored",
    )

    assert updated.name == "renamed"
    assert updated.enabled is False
    assert updated.config == {"url": "https://example.test/hook"}
    assert not hasattr(updated, "unknown_field")


async def test_should_return_none_when_updating_unknown_integration(service, api_db, db_session):
    assert await service.update_integration(db_session, 999, name="nope") is None


async def test_should_remove_integration_from_triggers_when_deleted(service, api_db, db_session):
    integration = await _persist(db_session)
    other = await _persist(db_session, name="other")
    trigger = TrafficTrigger(
        name="trigger",
        scope=TrafficScope.PEER,
        threshold_bytes=1000,
        window=ThresholdWindow.LAST_HOUR,
        trigger_integrations=[integration.id, other.id],
    )
    db_session.add(trigger)
    await db_session.commit()
    await db_session.refresh(trigger)

    assert await service.delete_integration(db_session, integration.id) is True

    assert (await db_session.execute(
        select(Integration).where(Integration.id == integration.id)
    )).scalar_one_or_none() is None
    await db_session.refresh(trigger)
    assert trigger.trigger_integrations == [other.id]


async def test_should_return_false_when_deleting_unknown_integration(service, api_db, db_session):
    assert await service.delete_integration(db_session, 999) is False


# ----------------------------------------------------------------------------
# Event subscription filtering
# ----------------------------------------------------------------------------


async def test_should_return_only_subscribed_enabled_integrations_when_event_given(
    service, api_db, db_session
):
    subscribed = await _persist(db_session, name="subscribed", events_subscribed=["server.created"])
    await _persist(db_session, name="not-subscribed", events_subscribed=["peer.created"])
    await _persist(db_session, name="disabled", events_subscribed=["server.created"], enabled=False)

    by_enum = await service.get_integrations_for_event(db_session, EventType.SERVER_CREATED)
    by_str = await service.get_integrations_for_event(db_session, "server.created")

    assert [i.id for i in by_enum] == [subscribed.id]
    assert [i.id for i in by_str] == [subscribed.id]


# ----------------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------------


async def test_should_dispatch_event_to_every_subscribed_integration(service, api_db, db_session):
    first = await _persist(db_session, name="first")
    second = await _persist(db_session, name="second")
    service._trigger_integration = AsyncMock()

    await service.dispatch_event_to_integrations(db_session, EventType.SERVER_CREATED, EVENT)

    triggered = [call.args[1].id for call in service._trigger_integration.await_args_list]
    assert triggered == [first.id, second.id]


async def test_should_keep_dispatching_when_one_integration_fails(service, api_db, db_session):
    await _persist(db_session, name="first")
    await _persist(db_session, name="second")

    async def flaky(db, integration, event_data):
        if integration.name == "first":
            raise RuntimeError("boom")

    service._trigger_integration = AsyncMock(side_effect=flaky)

    await service.dispatch_event_to_integrations(db_session, EventType.SERVER_CREATED, EVENT)

    assert service._trigger_integration.await_count == 2


async def test_should_skip_dispatch_when_no_integration_subscribed(service, api_db, db_session):
    await _persist(db_session, events_subscribed=["peer.created"])
    service._trigger_integration = AsyncMock()

    await service.dispatch_event_to_integrations(db_session, EventType.SERVER_CREATED, EVENT)

    service._trigger_integration.assert_not_awaited()


async def test_should_update_trigger_statistics_when_integration_triggered(service, db_session):
    integration = make_integration(type_="notification")
    service.notification_service.notify_from_integration = AsyncMock()

    await service._trigger_integration(db_session, integration, EVENT)

    assert integration.total_triggered == 1
    assert isinstance(integration.last_triggered_at, datetime)


async def test_should_create_in_app_notification_when_type_is_notification(service, db_session):
    integration = make_integration(type_="notification")
    service.notification_service.notify_from_integration = AsyncMock()

    await service._trigger_integration(db_session, integration, EVENT)

    service.notification_service.notify_from_integration.assert_awaited_once_with(
        db_session, integration, NORMALIZED
    )


async def test_should_delegate_to_webhook_when_type_is_webhook(service, db_session):
    integration = make_integration(type_="webhook")
    service._trigger_webhook = AsyncMock()

    await service._trigger_integration(db_session, integration, EVENT)

    service._trigger_webhook.assert_awaited_once_with(integration, NORMALIZED)


async def test_should_delegate_to_each_transport_when_dispatched(service, db_session):
    for type_ in ("email", "slack", "discord", "telegram", "plugin:my-plugin"):
        integration = make_integration(type_=type_)
        with patch.object(service, f"_trigger_{'plugin' if type_.startswith('plugin:') else type_}", new=AsyncMock()) as handler:
            await service._trigger_integration(db_session, integration, EVENT)
            if type_.startswith("plugin:"):
                handler.assert_awaited_once_with(db_session, integration, NORMALIZED)
            else:
                handler.assert_awaited_once_with(integration, NORMALIZED)


async def test_should_reject_script_without_changing_persisted_statistics(service, db_session):
    integration = await _persist(db_session, type="script", config={"script_path": "/bin/false"})
    integration_id = integration.id

    with pytest.raises(ValueError, match="[Ss]cript.*(unsupported|not supported)"):
        await service._trigger_integration(db_session, integration, EVENT)

    await db_session.commit()
    db_session.expire_all()
    stored = await service.get_integration(db_session, integration_id)
    assert stored.total_triggered == 0
    assert stored.last_triggered_at is None


async def test_should_continue_dispatch_after_rejecting_stored_script(service, db_session, capsys):
    script = await _persist(db_session, name="script", type="script")
    notification = await _persist(db_session, name="notification", type="notification", config={})
    service.notification_service.notify_from_integration = AsyncMock()

    await service.dispatch_event_to_integrations(db_session, EventType.SERVER_CREATED, EVENT)
    await db_session.commit()

    assert script.total_triggered == 0
    assert script.last_triggered_at is None
    assert notification.total_triggered == 1
    assert "Script integrations are not supported" in capsys.readouterr().out
    service.notification_service.notify_from_integration.assert_awaited_once()


async def test_should_report_failure_when_creating_script_integration(auth_client, db_session):
    response = auth_client.post(
        "/api/v1/integrations/",
        json={"name": "script", "type": "script", "config": {"script_path": "/bin/true"},
              "events_subscribed": ["server.created"]},
    )

    assert response.status_code in (400, 422)
    assert "script" in str(response.json()["detail"]).lower()
    assert (await db_session.execute(select(Integration).where(Integration.name == "script"))).scalar_one_or_none() is None


async def test_should_ignore_unknown_integration_type_when_dispatching(service, db_session):
    integration = make_integration(type_="carrier-pigeon")

    await service._trigger_integration(db_session, integration, EVENT)  # no handler, no error

    assert integration.total_triggered == 1


# ----------------------------------------------------------------------------
# Webhook transport
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["POST", "PUT", "GET"])
async def test_should_send_webhook_with_configured_method(service, method):
    integration = make_integration(
        type_="webhook",
        config={"url": "https://example.test/hook", "method": method, "headers": {"X-Token": "abc"}},
    )
    patcher, client = patch_http(method=method.lower())

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)

    call = getattr(client, method.lower()).await_args
    assert call.args[0] == "https://example.test/hook"
    if method == "GET":
        assert call.kwargs["params"]["event_type"] == "server.created"
    else:
        payload = call.kwargs["json"]
        assert payload["integration_id"] == 1
        assert payload["integration_name"] == "test integration"
        assert payload["resource_type"] == "server"
        assert payload["resource_id"] == 4
        assert payload["metadata"] == {"name": "edge-1"}
        assert payload["timestamp"] == NORMALIZED["timestamp"]
    assert call.kwargs["headers"] == {"X-Token": "abc"}


async def test_should_default_to_post_when_webhook_method_not_configured(service):
    integration = make_integration(config={"url": "https://example.test/hook"})
    patcher, client = patch_http(method="post")

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)

    client.post.assert_awaited_once()


async def test_should_skip_webhook_when_url_missing(service):
    integration = make_integration(config={})
    patcher, client = patch_http()

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)

    client.post.assert_not_awaited()


async def test_should_skip_webhook_when_method_unsupported(service):
    integration = make_integration(config={"url": "https://example.test/hook", "method": "DELETE"})
    patcher, client = patch_http()

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)

    client.post.assert_not_awaited()
    client.put.assert_not_awaited()
    client.get.assert_not_awaited()


async def test_should_swallow_webhook_http_errors(service):
    integration = make_integration(config={"url": "https://example.test/hook"})
    patcher, _ = patch_http(response=FakeResponse(status_code=500))

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)  # must not raise


async def test_should_swallow_webhook_unexpected_errors(service):
    integration = make_integration(config={"url": "https://example.test/hook"})
    patcher, _ = patch_http(error=RuntimeError("boom"))

    with patcher:
        await service._trigger_webhook(integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Slack transport
# ----------------------------------------------------------------------------


async def test_should_send_slack_blocks_when_webhook_configured(service):
    integration = make_integration(
        type_="slack", config={"webhook_url": "https://hooks.slack.test/abc"}
    )
    patcher, client = patch_http()
    event = dict(
        NORMALIZED,
        event_type="server.created",
        metadata={
            "name": "edge-1",
            "interface": "wg0",
            "email": "a@b.c",
            "changes": ["listen_port", "dns"],
            "server_name": "edge",
        },
    )

    with patcher:
        await service._trigger_slack(integration, event)

    call = client.post.await_args
    assert call.args[0] == "https://hooks.slack.test/abc"
    message = call.kwargs["json"]
    assert message["text"] == "Linguard: :computer: Server Created"
    header, section, context = message["blocks"]
    # header text is the display name with every ":" stripped
    assert header["text"]["text"] == "computer Server Created"
    texts = [field["text"] for field in section["fields"]]
    assert "*Resource:*\nServer #4" in texts
    assert "*Name:*\nedge-1" in texts
    assert "*Interface:*\nwg0" in texts
    assert "*Email:*\na@b.c" in texts
    assert "*Changes:*\nlisten_port, dns" in texts
    assert "*Server:*\nedge" in texts
    assert context["elements"][0]["text"] == f":clock3: {NORMALIZED['timestamp']}"


async def test_should_render_generic_slack_message_when_event_and_resource_unknown(service):
    integration = make_integration(type_="slack", config={"webhook_url": "https://hooks.slack.test/x"})
    patcher, client = patch_http()
    event = {"event_type": "custom.thing", "resource_type": "", "resource_id": None, "metadata": {}, "timestamp": ""}

    with patcher:
        await service._trigger_slack(integration, event)

    message = client.post.await_args.kwargs["json"]
    assert message["text"] == "Linguard: :bell: Custom.Thing"
    assert len(message["blocks"]) == 1  # no section (no fields) and no context (no timestamp)


async def test_should_ignore_non_list_slack_changes(service):
    integration = make_integration(type_="slack", config={"webhook_url": "https://hooks.slack.test/x"})
    patcher, client = patch_http()
    event = dict(NORMALIZED, metadata={"changes": "field added"})

    with patcher:
        await service._trigger_slack(integration, event)

    fields = client.post.await_args.kwargs["json"]["blocks"][1]["fields"]
    assert all("Changes" not in f["text"] for f in fields)


async def test_should_skip_slack_when_webhook_url_missing(service):
    integration = make_integration(type_="slack", config={})
    patcher, client = patch_http()

    with patcher:
        await service._trigger_slack(integration, NORMALIZED)

    client.post.assert_not_awaited()


async def test_should_swallow_slack_errors(service):
    integration = make_integration(type_="slack", config={"webhook_url": "https://hooks.slack.test/x"})
    patcher, _ = patch_http(response=FakeResponse(status_code=500))

    with patcher:
        await service._trigger_slack(integration, NORMALIZED)  # must not raise


async def test_should_swallow_unexpected_slack_errors(service):
    integration = make_integration(type_="slack", config={"webhook_url": "https://hooks.slack.test/x"})
    patcher, _ = patch_http(error=RuntimeError("boom"))

    with patcher:
        await service._trigger_slack(integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Discord transport
# ----------------------------------------------------------------------------


async def test_should_send_discord_embed_when_webhook_configured(service):
    integration = make_integration(
        type_="discord", config={"webhook_url": "https://discord.test/abc"}
    )
    patcher, client = patch_http()
    event = dict(
        NORMALIZED,
        event_type="peer.migrated",
        resource_type="peer",
        metadata={
            "name": "phone",
            "interface": "wg0",
            "email": "a@b.c",
            "allowed_ips": "10.0.0.2/32",
            "changes": ["server_id"],
            "server_name": "edge",
            "to_server": "core",
            "action": "migrate",
            "reason": "capacity",
        },
    )

    with patcher:
        await service._trigger_discord(integration, event)

    message = client.post.await_args.kwargs["json"]
    assert message["username"] == "Linguard"
    embed = message["embeds"][0]
    assert embed["title"] == "🔀 Peer Migrated"
    assert embed["color"] == 10181046
    assert embed["timestamp"] == NORMALIZED["timestamp"]
    assert embed["footer"] == {"text": "Linguard VPN Management"}
    names = {field["name"]: field["value"] for field in embed["fields"]}
    assert names["📋 Peer"] == "#4"
    assert names["🏷️ Name"] == "phone"
    assert names["🌐 Interface"] == "wg0"
    assert names["📧 Email"] == "a@b.c"
    assert names["🌐 Allowed IPs"] == "`10.0.0.2/32`"
    assert names["📝 Changes"] == "server_id"
    assert names["🖥️ Server"] == "edge"
    assert names["➡️ Migrated To"] == "core"
    assert names["🎯 Action"] == "migrate"
    assert names["💬 Reason"] == "capacity"


async def test_should_render_default_discord_embed_when_event_unknown(service):
    integration = make_integration(type_="discord", config={"webhook_url": "https://discord.test/x"})
    patcher, client = patch_http()
    event = {"event_type": "weird.event", "metadata": {"changes": []}, "timestamp": None}

    with patcher:
        await service._trigger_discord(integration, event)

    embed = client.post.await_args.kwargs["json"]["embeds"][0]
    assert embed["title"] == "🔔 Weird.Event"
    assert embed["fields"] == []  # empty changes list and no resource info
    assert embed["timestamp"] is None


async def test_should_skip_discord_when_webhook_url_missing(service):
    integration = make_integration(type_="discord", config={})
    patcher, client = patch_http()

    with patcher:
        await service._trigger_discord(integration, NORMALIZED)

    client.post.assert_not_awaited()


async def test_should_swallow_discord_http_errors(service):
    integration = make_integration(type_="discord", config={"webhook_url": "https://discord.test/x"})
    patcher, _ = patch_http(response=FakeResponse(status_code=500))

    with patcher:
        await service._trigger_discord(integration, NORMALIZED)  # must not raise


async def test_should_swallow_unexpected_discord_errors(service):
    integration = make_integration(type_="discord", config={"webhook_url": "https://discord.test/x"})
    patcher, _ = patch_http(error=RuntimeError("boom"))

    with patcher:
        await service._trigger_discord(integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Telegram transport
# ----------------------------------------------------------------------------


async def test_should_send_telegram_message_when_bot_configured(service):
    integration = make_integration(
        type_="telegram", config={"bot_token": "TOKEN", "chat_id": "-100"}
    )
    patcher, client = patch_http()
    event = dict(NORMALIZED, metadata={"name": "edge-1", "interface": "wg0"})

    with patcher:
        await service._trigger_telegram(integration, event)

    call = client.post.await_args
    assert call.args[0] == "https://api.telegram.org/botTOKEN/sendMessage"
    payload = call.kwargs["json"]
    assert payload["chat_id"] == "-100"
    assert payload["parse_mode"] == "HTML"
    assert payload["text"] == (
        "<b>🖥️ Server Created</b>\n\n"
        "<b>ID:</b> #4\n"
        "<b>Name:</b> edge-1\n"
        "<b>Interface:</b> wg0\n\n"
        f"<i>{NORMALIZED['timestamp']}</i>"
    )


async def test_should_use_allowed_ips_when_telegram_peer_has_no_interface(service):
    integration = make_integration(
        type_="telegram", config={"bot_token": "TOKEN", "chat_id": "42"}
    )
    patcher, client = patch_http()
    event = {
        "event_type": "peer.created",
        "resource_type": "peer",
        "resource_id": "N/A",
        "metadata": {"allowed_ips": "10.0.0.5/32"},
        "timestamp": "",
    }

    with patcher:
        await service._trigger_telegram(integration, event)

    text = client.post.await_args.kwargs["json"]["text"]
    assert text == (
        "<b>👤 Peer Created</b>\n\n"
        "<b>Allowed IPs:</b> <code>10.0.0.5/32</code>\n"
    )


async def test_should_render_default_telegram_title_when_event_unknown(service):
    integration = make_integration(type_="telegram", config={"bot_token": "T", "chat_id": "1"})
    patcher, client = patch_http()

    with patcher:
        await service._trigger_telegram(integration, {"event_type": "weird.event", "metadata": {}})

    text = client.post.await_args.kwargs["json"]["text"]
    assert text.startswith("<b>🔔 Weird.Event</b>")


@pytest.mark.parametrize(
    "config",
    [{}, {"bot_token": "T"}, {"chat_id": "1"}],
)
async def test_should_skip_telegram_when_credentials_missing(service, config):
    integration = make_integration(type_="telegram", config=config)
    patcher, client = patch_http()

    with patcher:
        await service._trigger_telegram(integration, NORMALIZED)

    client.post.assert_not_awaited()


async def test_should_swallow_telegram_http_errors(service):
    integration = make_integration(type_="telegram", config={"bot_token": "T", "chat_id": "1"})
    patcher, _ = patch_http(response=FakeResponse(status_code=400))

    with patcher:
        await service._trigger_telegram(integration, NORMALIZED)  # must not raise


async def test_should_swallow_unexpected_telegram_errors(service):
    integration = make_integration(type_="telegram", config={"bot_token": "T", "chat_id": "1"})
    patcher, _ = patch_http(error=RuntimeError("boom"))

    with patcher:
        await service._trigger_telegram(integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Email transport
# ----------------------------------------------------------------------------


def smtp_patch(send_error=None, login_error=None):
    smtp = MagicMock()
    smtp.starttls = AsyncMock()
    smtp.login = AsyncMock(side_effect=login_error)
    smtp.send_message = AsyncMock(side_effect=send_error)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=smtp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch.object(integration_module.aiosmtplib, "SMTP", return_value=cm), smtp


EMAIL_CONFIG = {
    "smtp_host": "smtp.example.test",
    "smtp_port": 587,
    "username": "user",
    "password": "secret",
    "from": "linguard@example.test",
    "to": ["admin@example.test", "ops@example.test"],
}


async def test_should_send_multipart_email_when_smtp_configured(service):
    integration = make_integration(type_="email", config=EMAIL_CONFIG)
    patcher, smtp = smtp_patch()

    with patcher:
        await service._trigger_email(integration, dict(NORMALIZED, metadata={"name": "edge-1"}))

    smtp.starttls.assert_awaited_once()
    smtp.login.assert_awaited_once_with("user", "secret")
    message = smtp.send_message.await_args.args[0]
    # only underscores are humanised in the subject line
    assert message["Subject"] == "Linguard Event: Server.Created"
    assert message["From"] == "linguard@example.test"
    assert message["To"] == "admin@example.test, ops@example.test"

    body = message.get_payload()
    assert len(body) == 2
    assert body[0].get_content_type() == "text/plain"
    plain = body[0].get_payload(decode=True).decode()
    assert "Event Type: Server.Created" in plain
    assert "  Name: edge-1" in plain
    html = body[1].get_payload(decode=True).decode()
    assert "🔔 Linguard Event Notification" in html
    assert "<li><strong>Name:</strong> edge-1</li>" in html


async def test_should_accept_single_recipient_string_when_sending_email(service):
    integration = make_integration(
        type_="email", config=dict(EMAIL_CONFIG, to="admin@example.test")
    )
    patcher, smtp = smtp_patch()

    with patcher:
        await service._trigger_email(integration, {"event_type": "backup.created", "metadata": {}})

    message = smtp.send_message.await_args.args[0]
    assert message["To"] == "admin@example.test"
    plain = message.get_payload()[0].get_payload(decode=True).decode()
    assert "Details:" not in plain  # no metadata -> no details section


@pytest.mark.parametrize(
    "missing",
    ["smtp_host", "username", "password", "from", "to"],
)
async def test_should_skip_email_when_required_config_missing(service, missing):
    config = dict(EMAIL_CONFIG)
    config.pop(missing)
    integration = make_integration(type_="email", config=config)
    patcher, smtp = smtp_patch()

    with patcher:
        await service._trigger_email(integration, NORMALIZED)

    smtp.send_message.assert_not_awaited()


async def test_should_swallow_smtp_errors_when_sending_email(service):
    integration = make_integration(type_="email", config=EMAIL_CONFIG)
    patcher, _ = smtp_patch(send_error=integration_module.aiosmtplib.SMTPException("rejected"))

    with patcher:
        await service._trigger_email(integration, NORMALIZED)  # must not raise


async def test_should_swallow_unexpected_email_errors(service):
    integration = make_integration(type_="email", config=EMAIL_CONFIG)
    patcher, _ = smtp_patch(login_error=OSError("connection refused"))

    with patcher:
        await service._trigger_email(integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Plugin transport
# ----------------------------------------------------------------------------


async def test_should_trigger_plugin_when_manager_available(service, db_session):
    manager = MagicMock()
    manager.trigger_plugin_for_integration = AsyncMock()
    service.plugin_manager = manager
    integration = make_integration(type_="plugin:notifier", plugin_id=12)

    await service._trigger_plugin(db_session, integration, NORMALIZED)

    manager.trigger_plugin_for_integration.assert_awaited_once_with(12, NORMALIZED)


async def test_should_skip_plugin_when_manager_not_initialized(service, db_session):
    service.plugin_manager = None
    integration = make_integration(type_="plugin:notifier", plugin_id=12)

    await service._trigger_plugin(db_session, integration, NORMALIZED)  # no error


async def test_should_skip_plugin_when_plugin_id_missing(service, db_session):
    manager = MagicMock()
    manager.trigger_plugin_for_integration = AsyncMock()
    service.plugin_manager = manager
    integration = make_integration(type_="plugin:notifier", plugin_id=None)

    await service._trigger_plugin(db_session, integration, NORMALIZED)

    manager.trigger_plugin_for_integration.assert_not_awaited()


async def test_should_swallow_plugin_errors(service, db_session):
    manager = MagicMock()
    manager.trigger_plugin_for_integration = AsyncMock(side_effect=RuntimeError("plugin failed"))
    service.plugin_manager = manager
    integration = make_integration(type_="plugin:notifier", plugin_id=12)

    await service._trigger_plugin(db_session, integration, NORMALIZED)  # must not raise


# ----------------------------------------------------------------------------
# Event bus wiring
# ----------------------------------------------------------------------------


def test_should_subscribe_handler_for_every_event_type_when_initialized(service):
    with patch.object(event_bus, "subscribe") as subscribe:
        service.initialize_event_handlers()

    subscribed = [call.args[0] for call in subscribe.call_args_list]
    assert subscribed == list(EventType)


async def test_should_do_nothing_when_event_handler_invoked(service):
    handler = service._create_event_handler(EventType.SERVER_CREATED)

    assert await handler({"event_type": "server.created"}) is None
