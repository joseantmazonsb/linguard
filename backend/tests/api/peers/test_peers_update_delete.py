"""Peer updates and deletion."""

from sqlalchemy import select

from app.models.peer import Peer


async def test_should_update_only_given_fields_when_payload_is_partial(auth_client, make_server, make_peer, db_session):
    server = await make_server(status="stopped", needs_reload=False)
    peer = await make_peer(server.id, name="old-name", ipv4_address="10.8.0.4/24")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"name": "new-name"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "new-name"
    assert body["ipv4_address"] == "10.8.0.4/24"

    await db_session.refresh(peer)
    assert peer.name == "new-name"
    await db_session.refresh(server)
    assert server.needs_reload is False


async def test_should_mark_running_server_for_reload_when_peer_is_updated(
    auth_client, make_server, make_peer, db_session
):
    server = await make_server(status="running", needs_reload=False)
    peer = await make_peer(server.id)

    response = auth_client.put(
        f"/api/v1/peers/{peer.id}",
        json={"enabled": False, "description": "on hold", "persistent_keepalive": 15},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["description"] == "on hold"
    assert body["persistent_keepalive"] == 15
    await db_session.refresh(server)
    assert server.needs_reload is True


async def test_should_return_404_when_updating_missing_peer(auth_client):
    response = auth_client.put("/api/v1/peers/9999", json={"name": "ghost"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_reject_duplicate_name_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    await make_peer(server.id, name="taken")
    peer = await make_peer(server.id, name="other", ipv4_address="10.8.0.3/24")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"name": "taken"})

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.name": ["Peer name 'taken' is already in use on this server"]}


async def test_should_allow_keeping_own_name_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id, name="same")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"name": "same", "description": "kept"})

    assert response.status_code == 200
    assert response.json()["description"] == "kept"


async def test_should_reject_ipv4_outside_subnet_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": "172.16.0.2/24"})

    assert response.status_code == 422
    assert "not within server subnet" in response.json()["errors"]["body.ipv4_address"][0]


async def test_should_reject_ipv4_equal_to_server_ip_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": "10.8.0.1/24"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]


async def test_should_reject_ipv6_outside_subnet_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv6_address": "fd00:77::5/64"})

    assert response.status_code == 422
    assert "body.ipv6_address" in response.json()["errors"]


async def test_should_reject_ipv6_equal_to_server_ip_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv6_address": "fd00:8::1/64"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]


async def test_should_reject_duplicate_ipv4_of_other_peer_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    await make_peer(server.id, name="squatter", ipv4_address="10.8.0.7/24")
    peer = await make_peer(server.id, name="mover", ipv4_address="10.8.0.8/24")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": "10.8.0.7/24"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == [
        "IP address already in use by peer: squatter on this server"
    ]


async def test_should_reject_duplicate_ipv6_of_other_peer_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    await make_peer(server.id, name="squatter", ipv4_address=None, ipv6_address="fd00:8::7/64")
    peer = await make_peer(server.id, name="mover", ipv4_address=None, ipv6_address="fd00:8::8/64")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv6_address": "fd00:8::7/64"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == [
        "IP address already in use by peer: squatter on this server"
    ]


async def test_should_clear_ipv4_when_ipv6_remains(auth_client, make_server, make_peer, db_session):
    server = await make_server()
    peer = await make_peer(server.id, ipv4_address="10.8.0.4/24", ipv6_address="fd00:8::4/64")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": ""})

    assert response.status_code == 200
    assert response.json()["ipv4_address"] is None
    await db_session.refresh(peer)
    assert peer.ipv4_address is None
    assert peer.ipv6_address == "fd00:8::4/64"


async def test_should_reject_clearing_both_addresses_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id, ipv4_address="10.8.0.4/24", ipv6_address="fd00:8::4/64")

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": "", "ipv6_address": ""})

    assert response.status_code == 422
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert response.json()["errors"] == {
        "body.ipv4_address": [message],
        "body.ipv6_address": [message],
    }


async def test_should_reject_invalid_cidr_when_updating(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.put(f"/api/v1/peers/{peer.id}", json={"ipv4_address": "10.8.0"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == ["Invalid CIDR"]


async def test_should_delete_peer_and_flag_reload_when_peer_exists(auth_client, make_server, make_peer, db_session):
    server = await make_server(status="running", needs_reload=False)
    peer = await make_peer(server.id)
    kept = await make_peer(server.id, name="kept", ipv4_address="10.8.0.3/24")

    response = auth_client.delete(f"/api/v1/peers/{peer.id}")

    assert response.status_code == 204
    assert response.content == b""
    remaining = (await db_session.execute(select(Peer))).scalars().all()
    assert [row.id for row in remaining] == [kept.id]
    await db_session.refresh(server)
    assert server.needs_reload is True


async def test_should_return_404_when_deleting_missing_peer(auth_client):
    response = auth_client.delete("/api/v1/peers/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_forbid_standard_user_when_deleting(user_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = user_client.delete(f"/api/v1/peers/{peer.id}")

    assert response.status_code == 403
