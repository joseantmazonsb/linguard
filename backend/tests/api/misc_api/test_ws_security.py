"""Security regression tests against real WebSocket connections."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from jose import jwt
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.api.ws import manager
from app.models.settings import GlobalSettings
from app.models.user import User
from app.services.notification_service import NotificationService
from tests.conftest import TEST_SECRET_KEY


def token(subject, secret=TEST_SECRET_KEY, expires=None):
    claims = {"exp": expires or datetime.utcnow() + timedelta(minutes=5)}
    if subject is not None:
        claims["sub"] = subject
    return jwt.encode(claims, secret, algorithm="HS256")


def ws_path(client, bearer=None):
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    response = client.post("/api/v1/ws/ticket", headers=headers)
    assert response.status_code == 200
    return f"/ws?ticket={response.json()['ticket']}"


@pytest.mark.parametrize("credential", [
    None,
    "not-a-token",
    token("admin", secret="wrong-key"),
    token("admin", expires=datetime.utcnow() - timedelta(minutes=1)),
    jwt.encode({"sub": "admin"}, TEST_SECRET_KEY, algorithm="HS256"),
    token(None),
    token("ghost"),
])
def test_rejects_missing_or_invalid_credentials(api_client, seeded_db, credential):
    path = "/ws" if credential is None else f"/ws?token={credential}"
    with pytest.raises(WebSocketDisconnect) as exc:
        with api_client.websocket_connect(path):
            pass
    assert exc.value.code == 1008
    assert not manager.active_connections


def test_rejects_missing_settings(api_client, api_db):
    with pytest.raises(WebSocketDisconnect) as exc:
        with api_client.websocket_connect(f"/ws?token={token('admin')}"):
            pass
    assert exc.value.code == 1008


def test_rejects_database_failure(api_client, seeded_db):
    with patch("app.api.ws._db.AsyncSessionLocal", side_effect=RuntimeError("db down")):
        with pytest.raises(WebSocketDisconnect) as exc:
            with api_client.websocket_connect("/ws"):
                pass
    assert exc.value.code == 1008


async def test_auth_disabled_uses_first_user_identity(api_client, seeded_db, db_session, api_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()

    with api_client.websocket_connect(ws_path(api_client)) as socket:
        assert socket.receive_json()["authenticated"] is False

        async def send_notification():
            async with api_db.sessionmaker() as db:
                await NotificationService().create_notification(
                    db, user_id=seeded_db["admin_id"], title="mine", message="private"
                )
                await NotificationService().create_notification(
                    db, user_id=seeded_db["user_id"], title="theirs", message="private"
                )

        socket.portal.call(send_notification)
        assert socket.receive_json()["data"]["title"] == "mine"
        socket.send_text("ping")
        assert socket.receive_json() == {"type": "pong"}


async def test_auth_disabled_ticket_is_rejected_when_no_users_exist(
    api_client, seeded_db, db_session
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    users = (await db_session.execute(select(User))).scalars().all()
    for user in users:
        await db_session.delete(user)
    await db_session.commit()

    assert api_client.post("/api/v1/ws/ticket").status_code == 401


def test_notifications_only_reach_recipient_across_connections(api_client, seeded_db, api_db):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as admin, \
         api_client.websocket_connect(ws_path(api_client, token('bob'))) as bob, \
         api_client.websocket_connect(ws_path(api_client, token('bob'))) as bob2:
        for socket in (admin, bob, bob2):
            assert socket.receive_json()["authenticated"] is True

        async def send_notification():
            async with api_db.sessionmaker() as db:
                await NotificationService().create_notification(
                    db, user_id=seeded_db["user_id"], title="private", message="for bob"
                )

        bob.portal.call(send_notification)
        for socket in (bob, bob2):
            assert socket.receive_json()["data"]["title"] == "private"
        admin.send_text("ping")
        assert admin.receive_json() == {"type": "pong"}


@pytest.mark.parametrize("message_type", ["metrics_update", "health_update", "server_status_change"])
def test_system_broadcasts_are_admin_only_even_from_direct_manager_call(
    api_client, seeded_db, message_type
):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as admin, \
         api_client.websocket_connect(ws_path(api_client, token('bob'))) as bob:
        admin.receive_json()
        bob.receive_json()
        admin.portal.call(manager.broadcast, {"type": message_type, "data": {"secret": True}})
        assert admin.receive_json()["type"] == message_type
        bob.send_text("ping")
        assert bob.receive_json() == {"type": "pong"}


def test_expired_connection_is_closed_before_broadcast(api_client, seeded_db):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as socket:
        socket.receive_json()
        with patch("jose.jwt.datetime") as clock:
            clock.utcnow.return_value = datetime.utcnow() + timedelta(minutes=10)
            socket.portal.call(manager.broadcast, {"type": "metrics_update", "data": {}})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


def test_demoted_admin_loses_privileged_broadcasts_but_retains_own_notifications(
    api_client, seeded_db, api_db
):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as socket:
        socket.receive_json()

        async def demote_and_broadcast():
            async with api_db.sessionmaker() as db:
                admin = await db.get(User, seeded_db["admin_id"])
                admin.role = "standard"
                await db.commit()
            await manager.broadcast({"type": "metrics_update", "data": {"secret": True}})
            await manager.broadcast({"type": "notification", "data": {"id": 1}}, seeded_db["admin_id"])

        socket.portal.call(demote_and_broadcast)
        assert socket.receive_json() == {"type": "notification", "data": {"id": 1}}


@pytest.mark.parametrize("change", ["key", "algorithm", "auth_mode", "deleted_user", "missing_settings"])
def test_revoked_connections_are_closed_before_broadcast(api_client, seeded_db, api_db, change):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as socket:
        socket.receive_json()

        async def revoke_and_broadcast():
            async with api_db.sessionmaker() as db:
                settings = (await db.execute(select(GlobalSettings))).scalar_one()
                if change == "key":
                    settings.secret_key = "rotated-key"
                elif change == "algorithm":
                    settings.algorithm = "HS384"
                elif change == "auth_mode":
                    settings.disable_auth = True
                elif change == "deleted_user":
                    await db.delete(await db.get(User, seeded_db["admin_id"]))
                else:
                    await db.delete(settings)
                await db.commit()
            # Revocation must be detected even when the message targets another user.
            await manager.broadcast({"type": "notification", "data": {}}, seeded_db["user_id"])

        socket.portal.call(revoke_and_broadcast)
        socket.send_text("ping")
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


def test_database_failure_closes_existing_connection(api_client, seeded_db):
    with api_client.websocket_connect(ws_path(api_client, token('admin'))) as socket:
        socket.receive_json()
        with patch("app.api.ws._db.AsyncSessionLocal", side_effect=RuntimeError("db down")):
            socket.portal.call(manager.broadcast, {"type": "metrics_update", "data": {}})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


async def test_auth_disabled_connection_closes_if_auth_is_enabled(api_client, seeded_db, db_session, api_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    with api_client.websocket_connect(ws_path(api_client)) as socket:
        socket.receive_json()

        async def enable_and_broadcast():
            async with api_db.sessionmaker() as db:
                settings = (await db.execute(select(GlobalSettings))).scalar_one()
                settings.disable_auth = False
                await db.commit()
            await manager.broadcast({"type": "metrics_update", "data": {}})

        socket.portal.call(enable_and_broadcast)
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


async def test_auth_disabled_connection_closes_when_first_user_changes(api_client, seeded_db, db_session, api_db):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    with api_client.websocket_connect(ws_path(api_client)) as socket:
        socket.receive_json()

        async def change_identity_and_broadcast():
            async with api_db.sessionmaker() as db:
                await db.delete(await db.get(User, seeded_db["admin_id"]))
                await db.commit()
            await manager.broadcast({"type": "notification", "data": {}}, seeded_db["user_id"])

        socket.portal.call(change_identity_and_broadcast)
        socket.send_text("ping")
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
