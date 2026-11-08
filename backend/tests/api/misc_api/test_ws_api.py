"""Tests for ``app/api/ws.py``.

The endpoint is exercised through ``TestClient.websocket_connect`` (each
connection is closed as soon as the assertions are done, so nothing hangs) and
the connection manager is unit-tested with fake sockets.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from jose import jwt
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.api.ws import (
    ConnectionManager,
    broadcast_health_update,
    broadcast_metrics_update,
    broadcast_notification,
    broadcast_server_status_change,
    manager,
    websocket_endpoint,
)
from app.models.settings import GlobalSettings
from tests.conftest import TEST_SECRET_KEY
from tests.api.misc_api.test_ws_security import ws_path


def _token(subject, secret=TEST_SECRET_KEY, algorithm="HS256"):
    return jwt.encode(
        {"sub": subject, "exp": datetime.utcnow() + timedelta(minutes=5)},
        secret,
        algorithm=algorithm,
    )


class FakeWebSocket:
    """Minimal stand-in for a Starlette WebSocket."""

    def __init__(self, fail_on_send=False):
        self.accepted = False
        self.messages = []
        self._fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        if self._fail_on_send:
            raise RuntimeError("socket is closed")
        self.messages.append(message)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def test_should_connect_and_answer_ping_when_token_is_valid(api_client, seeded_db):
    with api_client.websocket_connect(ws_path(api_client, _token('admin'))) as websocket:
        welcome = websocket.receive_json()
        assert welcome == {
            "type": "connected",
            "message": "WebSocket connection established",
            "authenticated": True,
        }

        websocket.send_text("ping")
        assert websocket.receive_json() == {"type": "pong"}

    # Closing the context manager disconnects the socket from the manager.
    assert manager.active_connections == set()


def test_should_mark_connection_authenticated_when_token_is_valid(
    api_client, seeded_db, admin_headers
):
    token = _token("admin")

    with api_client.websocket_connect(ws_path(api_client, token)) as websocket:
        welcome = websocket.receive_json()
        assert welcome["authenticated"] is True

    assert manager.active_connections == set()


def test_should_reject_connection_when_token_is_invalid(api_client, seeded_db):
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect("/ws?token=definitely-not-a-jwt"):
            pass
    assert manager.active_connections == set()


def test_should_reject_connection_when_token_user_is_unknown(
    api_client, seeded_db
):
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"/ws?token={_token('ghost')}"):
            pass


def test_should_reject_connection_when_token_has_no_subject(api_client, seeded_db):
    token = jwt.encode({"exp": datetime.utcnow() + timedelta(minutes=5)}, TEST_SECRET_KEY, algorithm="HS256")

    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"/ws?token={token}"):
            pass


async def test_should_mark_connection_unauthenticated_when_auth_is_disabled(
    api_client, seeded_db, db_session
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()

    with api_client.websocket_connect(ws_path(api_client)) as websocket:
        welcome = websocket.receive_json()

    assert welcome["authenticated"] is False


class BrokenAcceptSocket:
    """Socket whose accept fails (e.g. transport already closed)."""

    async def accept(self):
        raise RuntimeError("cannot accept")


class ErroringReceiveSocket:
    """Socket that accepts, then fails while receiving."""

    def __init__(self):
        self.sent = []

    async def accept(self):
        return None

    async def send_json(self, message):
        self.sent.append(message)

    async def receive_text(self):
        raise ValueError("transport broken")


async def test_should_ignore_socket_when_accept_fails(api_client, seeded_db):
    socket = BrokenAcceptSocket()

    ticket = ws_path(api_client, _token("admin")).split("=", 1)[1]
    await websocket_endpoint(socket, ticket=ticket)

    assert manager.active_connections == set()


async def test_should_stop_listening_when_receiving_fails(api_client, seeded_db):
    socket = ErroringReceiveSocket()

    ticket = ws_path(api_client, _token("admin")).split("=", 1)[1]
    await websocket_endpoint(socket, ticket=ticket)

    assert socket.sent == [
        {
            "type": "connected",
            "message": "WebSocket connection established",
            "authenticated": True,
        }
    ]
    assert manager.active_connections == set()


class DisconnectingSocket:
    """Socket that accepts, then reports the client went away."""

    def __init__(self):
        self.sent = []

    async def accept(self):
        return None

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, code):
        self.closed = code

    async def receive_text(self):
        from starlette.websockets import WebSocketDisconnect

        raise WebSocketDisconnect()


async def test_should_reject_when_auth_lookup_fails(api_client, seeded_db):
    socket = DisconnectingSocket()

    ticket = ws_path(api_client, _token("admin")).split("=", 1)[1]
    with patch("app.api.ws._db.AsyncSessionLocal", side_effect=RuntimeError("db down")):
        await websocket_endpoint(socket, ticket=ticket)

    assert socket.sent == []
    assert socket.closed == 1008
    assert manager.active_connections == set()


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

async def test_should_accept_and_track_socket_when_connected():
    manager = ConnectionManager()
    socket = FakeWebSocket()

    await manager.connect(socket, token=None, auth_disabled=True, user_id=None)

    assert socket.accepted is True
    assert manager.active_connections == {socket}

    manager.disconnect(socket)
    assert manager.active_connections == set()


async def test_should_broadcast_only_to_owner_when_notification_is_sent(seeded_db):
    manager = ConnectionManager()
    first, second = FakeWebSocket(), FakeWebSocket()
    await manager.connect(first, token=_token("admin"), auth_disabled=False, user_id=seeded_db["admin_id"])
    await manager.connect(second, token=_token("bob"), auth_disabled=False, user_id=seeded_db["user_id"])

    await manager.broadcast({"type": "notification", "data": {"id": 1}}, user_id=seeded_db["admin_id"])

    assert first.messages == [{"type": "notification", "data": {"id": 1}}]
    assert second.messages == []


async def test_should_drop_socket_when_broadcast_fails(seeded_db):
    manager = ConnectionManager()
    healthy = FakeWebSocket()
    broken = FakeWebSocket(fail_on_send=True)
    await manager.connect(healthy, token=_token("admin"), auth_disabled=False, user_id=seeded_db["admin_id"])
    await manager.connect(broken, token=_token("admin"), auth_disabled=False, user_id=seeded_db["admin_id"])

    await manager.broadcast({"type": "ping"})

    assert healthy.messages == [{"type": "ping"}]
    assert manager.active_connections == {healthy}


async def test_should_send_personal_message_when_socket_is_alive():
    manager = ConnectionManager()
    socket = FakeWebSocket()

    await manager.send_personal({"type": "hello"}, socket)

    assert socket.messages == [{"type": "hello"}]


async def test_should_disconnect_socket_when_personal_message_fails():
    manager = ConnectionManager()
    socket = FakeWebSocket(fail_on_send=True)
    await manager.connect(socket, token=None, auth_disabled=True, user_id=None)

    await manager.send_personal({"type": "hello"}, socket)

    assert manager.active_connections == set()


# ---------------------------------------------------------------------------
# Broadcast helpers
# ---------------------------------------------------------------------------

async def test_should_broadcast_metrics_update_when_called():
    with patch.object(manager, "broadcast", AsyncMock()) as broadcast:
        await broadcast_metrics_update({"servers": 1})

    broadcast.assert_awaited_once_with({"type": "metrics_update", "data": {"servers": 1}})


async def test_should_broadcast_notification_when_called():
    with patch.object(manager, "broadcast", AsyncMock()) as broadcast:
        await broadcast_notification({"id": 3, "title": "hi"}, user_id=7)

    broadcast.assert_awaited_once_with(
        {"type": "notification", "data": {"id": 3, "title": "hi"}}, user_id=7
    )


async def test_should_broadcast_server_status_change_when_called():
    with patch.object(manager, "broadcast", AsyncMock()) as broadcast:
        await broadcast_server_status_change({"server_id": 1, "status": "running"})

    broadcast.assert_awaited_once_with(
        {"type": "server_status_change", "data": {"server_id": 1, "status": "running"}}
    )

async def test_should_broadcast_health_update_when_called():
    with patch.object(manager, "broadcast", AsyncMock()) as broadcast:
        await broadcast_health_update({"status": "healthy"})

    broadcast.assert_awaited_once_with(
        {"type": "health_update", "data": {"status": "healthy"}}
    )
