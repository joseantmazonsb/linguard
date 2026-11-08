"""Tests for ``app/api/traffic_triggers.py``.

Triggers are stored in the real SQLite database, and the "test" endpoint is
exercised against real ``traffic_metrics`` rows so the traffic summation and
cooldown logic run for real.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.traffic_metric import TrafficMetric
from app.models.traffic_trigger import TrafficTrigger

BASE = "/api/v1/traffic-triggers"


def peer_payload(peer, **overrides):
    payload = {
        "name": "peer cap",
        "description": "peer level threshold",
        "scope": "peer",
        "peer_id": peer.id,
        "direction": "combined",
        "threshold_bytes": 1000,
        "window": "last_hour",
        "cooldown_seconds": 600,
    }
    payload.update(overrides)
    return payload


def server_payload(server, **overrides):
    payload = {
        "name": "server cap",
        "scope": "server",
        "server_id": server.id,
        "direction": "rx_only",
        "threshold_bytes": 5000,
        "window": "last_24_hours",
    }
    payload.update(overrides)
    return payload


async def _add_metric(db_session, *, peer=None, server=None, rx=0, tx=0, recorded_at=None):
    metric = TrafficMetric(
        peer_id=peer.id if peer is not None else None,
        server_id=server.id if server is not None else None,
        rx_bytes=rx,
        tx_bytes=tx,
        rx_bytes_delta=rx,
        tx_bytes_delta=tx,
        is_connected=True,
        recorded_at=recorded_at or datetime.now(timezone.utc),
    )
    db_session.add(metric)
    await db_session.commit()
    return metric


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_should_create_peer_trigger_when_peer_exists(auth_client, db_session, peer):
    response = auth_client.post(BASE + "/", json=peer_payload(peer))

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "peer cap"
    assert body["scope"] == "peer"
    assert body["peer_id"] == peer.id
    assert body["peer_name"] == "peer-main"
    assert body["threshold_bytes"] == 1000
    assert body["cooldown_seconds"] == 600
    assert body["cooldown_minutes"] == 10
    assert body["enabled"] is True

    stored = (
        await db_session.execute(select(TrafficTrigger).where(TrafficTrigger.id == body["id"]))
    ).scalar_one()
    assert stored.peer_id == peer.id


async def test_should_create_server_trigger_when_server_exists(auth_client, server):
    response = auth_client.post(BASE + "/", json=server_payload(server))

    assert response.status_code == 201
    body = response.json()
    assert body["scope"] == "server"
    assert body["server_id"] == server.id
    assert body["server_name"] == "srv-main"
    assert body["direction"] == "rx_only"


async def test_should_create_global_trigger_with_integrations_when_they_exist(
    auth_client, integration
):
    response = auth_client.post(
        BASE + "/",
        json={
            "name": "global cap",
            "scope": "global",
            "threshold_bytes": 10_000_000,
            "window": "last_7_days",
            "integration_ids": [integration.id],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["scope"] == "global"
    assert body["trigger_integrations"] == [integration.id]
    assert body["integration_ids"] == [integration.id]


async def test_should_return_404_when_creating_trigger_for_unknown_peer(auth_client, peer):
    response = auth_client.post(BASE + "/", json=peer_payload(peer, peer_id=98765))

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer with ID 98765 not found"


async def test_should_return_404_when_creating_trigger_for_unknown_server(auth_client, server):
    response = auth_client.post(BASE + "/", json=server_payload(server, server_id=98765))

    assert response.status_code == 404
    assert response.json()["detail"] == "Server with ID 98765 not found"


async def test_should_return_404_when_creating_trigger_with_unknown_integration(
    auth_client, peer
):
    response = auth_client.post(
        BASE + "/", json=peer_payload(peer, trigger_integrations=[424242])
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "One or more integration IDs not found"


async def test_should_reject_trigger_when_threshold_is_not_positive(auth_client, peer):
    response = auth_client.post(BASE + "/", json=peer_payload(peer, threshold_bytes=0))

    assert response.status_code == 422


async def test_should_reject_peer_scoped_trigger_when_peer_id_is_missing(auth_client):
    payload = {
        "name": "peer cap",
        "scope": "peer",
        "direction": "combined",
        "threshold_bytes": 1000,
        "window": "last_hour",
    }

    response = auth_client.post(BASE + "/", json=payload)

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------

async def test_should_filter_triggers_when_query_parameters_are_given(
    auth_client, peer, server
):
    created_peer = auth_client.post(BASE + "/", json=peer_payload(peer)).json()
    global_body = auth_client.post(
        BASE + "/",
        json={
            "name": "global cap",
            "scope": "global",
            "threshold_bytes": 42,
            "window": "last_hour",
            "enabled": False,
        },
    ).json()

    assert {t["id"] for t in auth_client.get(BASE + "/").json()} == {
        created_peer["id"],
        global_body["id"],
    }

    enabled = auth_client.get(BASE + "/", params={"enabled_only": True}).json()
    assert [t["id"] for t in enabled] == [created_peer["id"]]

    scoped = auth_client.get(BASE + "/", params={"scope": "global"}).json()
    assert [t["id"] for t in scoped] == [global_body["id"]]

    # Search matches the trigger name and the related peer name.
    by_peer = auth_client.get(BASE + "/", params={"search": "peer-main"}).json()
    assert [t["id"] for t in by_peer] == [created_peer["id"]]
    by_name = auth_client.get(BASE + "/", params={"search": "global"}).json()
    assert [t["id"] for t in by_name] == [global_body["id"]]

    paged = auth_client.get(BASE + "/", params={"skip": 1, "limit": 5}).json()
    assert len(paged) == 1


async def test_should_get_trigger_by_id_when_it_exists(auth_client, peer):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    response = auth_client.get(f"{BASE}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["threshold_bytes"] == 1000


async def test_should_return_404_when_getting_unknown_trigger(auth_client):
    assert auth_client.get(f"{BASE}/4242").status_code == 404
    assert auth_client.post(f"{BASE}/4242/test").status_code == 404
    assert auth_client.delete(f"{BASE}/4242").status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

async def test_should_update_trigger_when_payload_is_partial(auth_client, peer):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    response = auth_client.put(
        f"{BASE}/{created['id']}", json={"name": "renamed", "threshold_bytes": 2048}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "renamed"
    assert body["threshold_bytes"] == 2048
    assert body["peer_id"] == peer.id


async def test_should_clear_peer_when_scope_changes_to_global(auth_client, peer):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    response = auth_client.put(f"{BASE}/{created['id']}", json={"scope": "global"})

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "global"
    assert body["peer_id"] is None


async def test_should_clear_peer_when_scope_changes_to_server(auth_client, peer, server):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    response = auth_client.put(
        f"{BASE}/{created['id']}", json={"scope": "server", "server_id": server.id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == server.id
    assert body["peer_id"] is None


async def test_should_return_404_when_updating_trigger_with_unknown_references(
    auth_client, peer, server
):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    unknown_peer = auth_client.put(f"{BASE}/{created['id']}", json={"peer_id": 99999})
    assert unknown_peer.status_code == 404
    assert unknown_peer.json()["detail"] == "Peer with ID 99999 not found"

    unknown_server = auth_client.put(f"{BASE}/{created['id']}", json={"server_id": 99999})
    assert unknown_server.status_code == 404
    assert unknown_server.json()["detail"] == "Server with ID 99999 not found"

    unknown_integration = auth_client.put(
        f"{BASE}/{created['id']}", json={"trigger_integrations": [99999]}
    )
    assert unknown_integration.status_code == 404
    assert unknown_integration.json()["detail"] == "One or more integration IDs not found"


async def test_should_return_404_when_updating_unknown_trigger(auth_client):
    response = auth_client.put(f"{BASE}/4242", json={"name": "ghost"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Traffic trigger not found"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

async def test_should_delete_trigger_when_it_exists(auth_client, peer, db_session):
    created = auth_client.post(BASE + "/", json=peer_payload(peer)).json()

    response = auth_client.delete(f"{BASE}/{created['id']}")

    assert response.status_code == 204
    remaining = (
        await db_session.execute(
            select(TrafficTrigger).where(TrafficTrigger.id == created["id"])
        )
    ).scalar_one_or_none()
    assert remaining is None


# ---------------------------------------------------------------------------
# Dry-run test endpoint
# ---------------------------------------------------------------------------

async def test_should_report_threshold_exceeded_when_traffic_is_above_threshold(
    auth_client, db_session, peer
):
    created = auth_client.post(BASE + "/", json=peer_payload(peer, threshold_bytes=600)).json()
    await _add_metric(db_session, peer=peer, rx=500, tx=400)

    response = auth_client.post(f"{BASE}/{created['id']}/test")

    assert response.status_code == 200
    body = response.json()
    assert body["threshold_exceeded"] is True
    assert body["would_trigger"] is True
    assert body["in_cooldown"] is False
    assert body["current_bytes"] == 900
    assert body["threshold_bytes"] == 600
    assert body["traffic_breakdown"]["rx_bytes"] == 500
    assert body["traffic_breakdown"]["tx_bytes"] == 400
    assert body["traffic_breakdown"]["window"] == "last_hour"
    assert "would fire" in body["reason"]


async def test_should_report_below_threshold_when_traffic_is_low(
    auth_client, db_session, peer
):
    created = auth_client.post(BASE + "/", json=peer_payload(peer, threshold_bytes=10_000)).json()
    await _add_metric(db_session, peer=peer, rx=100, tx=100)

    response = auth_client.post(f"{BASE}/{created['id']}/test")

    body = response.json()
    assert body["threshold_exceeded"] is False
    assert body["would_trigger"] is False
    assert body["current_bytes"] == 200
    assert "below threshold" in body["reason"]


async def test_should_report_cooldown_when_trigger_fired_recently(
    auth_client, db_session, peer
):
    created = auth_client.post(
        BASE + "/", json=peer_payload(peer, threshold_bytes=10, cooldown_seconds=3600)
    ).json()
    await _add_metric(db_session, peer=peer, rx=1000, tx=0)

    trigger = (
        await db_session.execute(select(TrafficTrigger).where(TrafficTrigger.id == created["id"]))
    ).scalar_one()
    trigger.last_triggered_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    response = auth_client.post(f"{BASE}/{created['id']}/test")

    body = response.json()
    assert body["threshold_exceeded"] is True
    assert body["in_cooldown"] is True
    assert body["would_trigger"] is False
    assert "cooldown" in body["reason"]


async def test_should_only_count_recent_metrics_when_window_is_last_hour(
    auth_client, db_session, peer
):
    created = auth_client.post(BASE + "/", json=peer_payload(peer, threshold_bytes=1)).json()
    await _add_metric(db_session, peer=peer, rx=10, tx=0)
    await _add_metric(
        db_session,
        peer=peer,
        rx=100_000,
        tx=0,
        recorded_at=datetime.now(timezone.utc) - timedelta(days=3),
    )

    response = auth_client.post(f"{BASE}/{created['id']}/test")

    assert response.json()["current_bytes"] == 10


async def test_should_require_authentication_when_listing_triggers(api_client, seeded_db):
    assert api_client.get(BASE + "/").status_code == 401
