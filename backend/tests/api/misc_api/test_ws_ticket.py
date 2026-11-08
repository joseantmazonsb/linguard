"""Ticket issuance and consumption via the real HTTP and WebSocket routes."""

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from jose import jwt
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.api.ws import manager
from app.models.settings import GlobalSettings
from tests.conftest import TEST_SECRET_KEY


def access_token(subject="admin", expires=None):
    return jwt.encode(
        {"sub": subject, "exp": expires or datetime.utcnow() + timedelta(minutes=5)},
        TEST_SECRET_KEY, algorithm="HS256",
    )


def issue(client, bearer):
    return client.post("/api/v1/ws/ticket", headers={"Authorization": f"Bearer {bearer}"})


def test_ticket_requires_valid_bearer(api_client, seeded_db):
    assert api_client.post("/api/v1/ws/ticket").status_code == 401
    assert issue(api_client, "invalid").status_code == 401
    no_exp = jwt.encode({"sub": "admin"}, TEST_SECRET_KEY, algorithm="HS256")
    assert issue(api_client, no_exp).status_code == 401


def test_ticket_is_single_use_and_bearer_query_is_rejected(api_client, seeded_db):
    bearer = access_token()
    response = issue(api_client, bearer)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    ticket = response.json()["ticket"]
    assert bearer not in ticket
    with api_client.websocket_connect(f"/ws?ticket={ticket}") as socket:
        assert socket.receive_json()["authenticated"] is True
    for path in (f"/ws?ticket={ticket}", f"/ws?ticket={bearer}", f"/ws?token={bearer}", "/ws"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with api_client.websocket_connect(path):
                pass
        assert exc.value.code == 1008


def test_ticket_replay_is_atomic_across_simultaneous_connections(api_client, seeded_db):
    ticket = issue(api_client, access_token()).json()["ticket"]
    barrier = Barrier(2)

    def connect():
        barrier.wait()
        try:
            with api_client.websocket_connect(f"/ws?ticket={ticket}") as socket:
                return socket.receive_json()["type"]
        except WebSocketDisconnect as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: connect(), range(2)))
    assert sorted(results, key=str) == [1008, "connected"]


async def test_key_rotation_after_issuance_invalidates_ticket(api_client, seeded_db, db_session):
    ticket = issue(api_client, access_token()).json()["ticket"]
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.secret_key = "rotated-key"
    await db_session.commit()
    with pytest.raises(WebSocketDisconnect) as exc:
        with api_client.websocket_connect(f"/ws?ticket={ticket}"):
            pass
    assert exc.value.code == 1008


async def test_oidc_only_mode_invalidates_local_tickets_and_connections(api_client, seeded_db, api_db):
    bearer = access_token()
    ticket = issue(api_client, bearer).json()["ticket"]
    with api_client.websocket_connect(f"/ws?ticket={issue(api_client, bearer).json()['ticket']}") as socket:
        socket.receive_json()

        async def change_mode():
            async with api_db.sessionmaker() as db:
                settings = (await db.execute(select(GlobalSettings))).scalar_one()
                settings.auth_mode = "oidc_only"
                await db.commit()
            await manager.broadcast({"type": "metrics_update", "data": {}})

        socket.portal.call(change_mode)
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"/ws?ticket={ticket}"):
            pass


def test_expired_ticket_is_rejected(api_client, seeded_db):
    with patch("app.api.ws.monotonic", return_value=100):
        ticket = issue(api_client, access_token()).json()["ticket"]
    with patch("app.api.ws.monotonic", return_value=10000):
        with pytest.raises(WebSocketDisconnect) as exc:
            with api_client.websocket_connect(f"/ws?ticket={ticket}"):
                pass
    assert exc.value.code == 1008


def test_access_token_expiry_before_ticket_consumption_is_rejected(api_client, seeded_db):
    ticket = issue(api_client, access_token()).json()["ticket"]
    with patch("jose.jwt.datetime") as clock:
        clock.utcnow.return_value = datetime.utcnow() + timedelta(minutes=10)
        with pytest.raises(WebSocketDisconnect) as exc:
            with api_client.websocket_connect(f"/ws?ticket={ticket}"):
                pass
    assert exc.value.code == 1008


def test_ticket_capacity_is_bounded(api_client, seeded_db):
    with patch("app.api.ws.MAX_TICKETS", 0):
        assert issue(api_client, access_token()).status_code == 503


def test_access_token_expiry_still_closes_socket_on_broadcast(api_client, seeded_db):
    ticket = issue(api_client, access_token()).json()["ticket"]
    with api_client.websocket_connect(f"/ws?ticket={ticket}") as socket:
        socket.receive_json()
        with patch("jose.jwt.datetime") as clock:
            clock.utcnow.return_value = datetime.utcnow() + timedelta(minutes=10)
            socket.portal.call(manager.broadcast, {"type": "metrics_update", "data": {}})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008


async def test_auth_disabled_still_requires_ticket(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect("/ws"):
            pass
    response = api_client.post("/api/v1/ws/ticket")
    assert response.status_code == 200
    with api_client.websocket_connect(f"/ws?ticket={response.json()['ticket']}") as socket:
        assert socket.receive_json()["authenticated"] is False


async def test_auth_disabled_before_setup_completion_still_requires_bearer(api_client, seeded_db, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    settings.setup_completed = False
    await db_session.commit()
    assert api_client.post("/api/v1/ws/ticket").status_code == 401
    response = issue(api_client, access_token())
    assert response.status_code == 200
    with api_client.websocket_connect(f"/ws?ticket={response.json()['ticket']}") as socket:
        assert socket.receive_json()["authenticated"] is True
