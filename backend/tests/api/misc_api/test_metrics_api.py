"""Tests for ``app/api/metrics.py``.

Read endpoints run against real ``traffic_metrics`` rows in the per-test
SQLite database. Only the collection trigger is stubbed: it shells out to the
``wg`` binary, which is the true boundary of that endpoint.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest_asyncio

from app.main import app
from app.models.peer import Peer
from app.models.server import Server
from app.models.traffic_metric import TrafficMetric

BASE = "/api/v1/metrics"


@pytest_asyncio.fixture
async def hour_start():
    """Start of a recent hour, so several metrics can share a bucket."""
    now = datetime.now(timezone.utc)
    return (now - timedelta(minutes=5)).replace(minute=0, second=0, microsecond=0)


async def _add_metric(
    db_session,
    *,
    server=None,
    peer=None,
    rx=0,
    tx=0,
    recorded_at=None,
    handshake_at=None,
    connected=True,
):
    metric = TrafficMetric(
        server_id=server.id if server is not None else None,
        peer_id=peer.id if peer is not None else None,
        rx_bytes=rx,
        tx_bytes=tx,
        rx_bytes_delta=rx,
        tx_bytes_delta=tx,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        handshake_at=handshake_at,
        is_connected=connected,
    )
    db_session.add(metric)
    await db_session.commit()
    return metric


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

async def test_should_collect_metrics_when_collector_runs(auth_client):
    collector = app.container.metrics_collector_service()

    with patch.object(
        collector,
        "collect_all_metrics",
        AsyncMock(return_value={"servers_updated": 2, "peers_updated": 5}),
    ) as collect:
        response = auth_client.post(BASE + "/collect")

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "servers_updated": 2,
        "peers_updated": 5,
    }
    collect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Single server / peer history
# ---------------------------------------------------------------------------

async def test_should_return_server_metrics_when_history_exists(
    auth_client, db_session, server, hour_start
):
    old = await _add_metric(
        db_session, server=server, rx=1, tx=1, recorded_at=hour_start - timedelta(days=3)
    )
    await _add_metric(db_session, server=server, rx=100, tx=50, recorded_at=hour_start)
    await _add_metric(
        db_session, server=server, rx=200, tx=80, recorded_at=hour_start + timedelta(minutes=10)
    )

    response = auth_client.get(f"{BASE}/server/{server.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["server"] == {
        "id": server.id,
        "name": "srv-main",
        "current_rx_bytes": 1500,
        "current_tx_bytes": 500,
    }
    assert [m["recorded_at"] for m in body["metrics"]] == [
        hour_start.replace(tzinfo=None).isoformat(),
        (hour_start + timedelta(minutes=10)).replace(tzinfo=None).isoformat(),
    ]
    assert body["metrics"][0]["rx_bytes_delta"] == 100
    assert body["metrics"][0]["is_connected"] is True
    assert body["summary"] == {"total_data_points": 2, "time_range_hours": 24}
    assert old is not None


async def test_should_return_404_when_server_metrics_requested_for_unknown_server(
    auth_client, seeded_db
):
    response = auth_client.get(f"{BASE}/server/4242")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_peer_metrics_when_history_exists(
    auth_client, db_session, peer, hour_start
):
    handshake = hour_start + timedelta(minutes=1)
    await _add_metric(
        db_session, peer=peer, rx=10, tx=20, recorded_at=hour_start, handshake_at=handshake
    )
    await _add_metric(
        db_session,
        peer=peer,
        rx=30,
        tx=40,
        recorded_at=hour_start + timedelta(minutes=5),
        connected=False,
    )

    response = auth_client.get(f"{BASE}/peer/{peer.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["peer"]["id"] == peer.id
    assert body["peer"]["name"] == "peer-main"
    assert body["peer"]["current_rx_bytes"] == 700
    assert body["peer"]["current_tx_bytes"] == 300
    assert body["peer"]["last_handshake"] is None
    assert body["metrics"][0]["handshake_at"] is not None
    assert body["metrics"][1]["handshake_at"] is None
    assert body["metrics"][1]["is_connected"] is False
    assert body["summary"]["total_data_points"] == 2


async def test_should_return_404_when_peer_metrics_requested_for_unknown_peer(
    auth_client, seeded_db
):
    response = auth_client.get(f"{BASE}/peer/4242")

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_respect_hours_window_when_returning_server_metrics(
    auth_client, db_session, server, hour_start
):
    await _add_metric(db_session, server=server, rx=5, tx=5, recorded_at=hour_start)
    await _add_metric(
        db_session,
        server=server,
        rx=500,
        tx=500,
        recorded_at=hour_start - timedelta(hours=10),
    )

    response = auth_client.get(f"{BASE}/server/{server.id}", params={"hours": 2})

    body = response.json()
    assert body["summary"]["total_data_points"] == 1
    assert body["summary"]["time_range_hours"] == 2
    assert body["metrics"][0]["rx_bytes"] == 5


async def test_should_reject_metrics_request_when_hours_is_out_of_range(
    auth_client, server
):
    assert auth_client.get(f"{BASE}/server/{server.id}", params={"hours": 0}).status_code == 422
    assert auth_client.get(f"{BASE}/server/{server.id}", params={"hours": 721}).status_code == 422


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

async def test_should_aggregate_server_metrics_when_metrics_exist(
    auth_client, db_session, server, hour_start
):
    db_session.add(
        Server(
            name="srv-second",
            interface="wg1",
            public_key="pk2",
            private_key="sk2",
            listen_port=51821,
            rx_bytes=10,
            tx_bytes=5,
        )
    )
    await db_session.commit()
    await _add_metric(db_session, server=server, rx=100, tx=40, recorded_at=hour_start)
    await _add_metric(
        db_session, server=server, rx=20, tx=10, recorded_at=hour_start + timedelta(minutes=20)
    )

    response = auth_client.get(BASE + "/servers/aggregate")

    assert response.status_code == 200
    body = response.json()
    assert body["current_totals"] == {"total_rx_bytes": 1510, "total_tx_bytes": 505}
    assert len(body["hourly_metrics"]) == 1
    hourly = body["hourly_metrics"][0]
    assert hourly["rx_bytes"] == 120
    assert hourly["tx_bytes"] == 50
    assert hourly["timestamp"] == hour_start.strftime("%Y-%m-%d %H:00:00")
    assert [s["name"] for s in body["servers"]] == ["srv-main", "srv-second"]
    assert body["servers"][0]["total_bytes"] == 2000
    assert body["summary"] == {"time_range_hours": 24, "total_servers": 2}


async def test_should_aggregate_peer_metrics_when_metrics_exist(
    auth_client, db_session, server, peer, hour_start
):
    await _add_metric(db_session, peer=peer, rx=300, tx=100, recorded_at=hour_start)
    await _add_metric(
        db_session, peer=peer, rx=50, tx=25, recorded_at=hour_start + timedelta(minutes=30)
    )

    response = auth_client.get(BASE + "/peers/aggregate", params={"hours": 48})

    assert response.status_code == 200
    body = response.json()
    assert body["current_totals"] == {"total_rx_bytes": 700, "total_tx_bytes": 300}
    assert body["peers"] == [
        {
            "id": peer.id,
            "name": "peer-main",
            "rx_bytes": 700,
            "tx_bytes": 300,
            "total_bytes": 1000,
        }
    ]
    assert body["hourly_metrics"][0]["rx_bytes"] == 350
    assert body["summary"] == {"time_range_hours": 48, "total_peers": 1}


async def test_should_return_zero_totals_when_no_metrics_exist(auth_client, seeded_db):
    servers = auth_client.get(BASE + "/servers/aggregate").json()
    peers = auth_client.get(BASE + "/peers/aggregate").json()

    assert servers["current_totals"] == {"total_rx_bytes": 0, "total_tx_bytes": 0}
    assert servers["hourly_metrics"] == []
    assert servers["servers"] == []
    assert servers["summary"]["total_servers"] == 0
    assert peers["peers"] == []
    assert peers["summary"]["total_peers"] == 0


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

async def test_should_limit_dashboard_lists_when_many_servers_and_peers_exist(
    auth_client, db_session, server, peer, hour_start
):
    for index in range(6):
        db_session.add(
            Server(
                name=f"extra-server-{index}",
                interface=f"wgextra{index}",
                public_key=f"pk-extra-{index}",
                private_key=f"sk-extra-{index}",
                listen_port=52000 + index,
                rx_bytes=index * 1000,
                tx_bytes=0,
            )
        )
        db_session.add(
            Peer(
                server_id=server.id,
                name=f"extra-peer-{index}",
                public_key=f"peer-pk-{index}",
                private_key=f"peer-sk-{index}",
                rx_bytes=index * 10,
                tx_bytes=0,
            )
        )
    await db_session.commit()
    await _add_metric(db_session, server=server, rx=70, tx=30, recorded_at=hour_start)
    await _add_metric(db_session, peer=peer, rx=7, tx=3, recorded_at=hour_start)

    response = auth_client.get(BASE + "/dashboard", params={"hours": 12})

    assert response.status_code == 200
    body = response.json()
    assert len(body["servers"]["top_servers"]) == 5
    assert body["servers"]["top_servers"][0]["name"] == "extra-server-5"
    assert len(body["peers"]["top_peers"]) == 5
    assert body["servers"]["hourly_metrics"][0]["rx_bytes"] == 70
    assert body["peers"]["hourly_metrics"][0]["rx_bytes"] == 7
    assert body["summary"] == {"time_range_hours": 12}


async def test_should_require_authentication_when_reading_dashboard(api_client, seeded_db):
    assert api_client.get(BASE + "/dashboard").status_code == 401
