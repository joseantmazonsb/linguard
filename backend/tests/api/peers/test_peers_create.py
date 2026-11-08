"""Peer creation: happy path, payload validation and business rules."""

from sqlalchemy import select

from app.models.peer import Peer

VALID_PAYLOAD = {
    "name": "phone",
    "public_key": "P" * 44,
    "private_key": "p" * 44,
    "ipv4_address": "10.8.0.5/24",
}


async def test_should_create_peer_and_mark_running_server_for_reload_when_payload_is_valid(
    auth_client, make_server, db_session, wg_installed
):
    server = await make_server(status="running", needs_reload=False)

    response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "phone"
    assert body["server_id"] == server.id
    assert body["ipv4_address"] == "10.8.0.5/24"
    assert body["ipv4_allowed_ips"] == "0.0.0.0/0"
    assert body["ipv6_allowed_ips"] == "::/0"
    assert body["allowed_ips"] == "0.0.0.0/0, ::/0"
    assert body["persistent_keepalive"] == 25
    assert body["enabled"] is True

    stored = (await db_session.execute(select(Peer).where(Peer.id == body["id"]))).scalar_one()
    assert stored.name == "phone"
    assert stored.public_key == "P" * 44

    await db_session.refresh(server)
    assert server.needs_reload is True


async def test_should_not_flag_reload_when_server_is_stopped(auth_client, make_server, db_session, wg_installed):
    server = await make_server(status="stopped", needs_reload=False)

    response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 201
    await db_session.refresh(server)
    assert server.needs_reload is False


async def test_should_split_combined_allowed_ips_when_creating(auth_client, make_server, wg_installed):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/",
        json={
            "server_id": server.id,
            **VALID_PAYLOAD,
            "allowed_ips": "10.0.0.0/8, fd00::/64",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ipv4_allowed_ips"] == "10.0.0.0/8"
    assert body["ipv6_allowed_ips"] == "fd00::/64"


async def test_should_return_422_when_wireguard_is_not_installed(auth_client, make_server, wg):
    from unittest.mock import patch

    server = await make_server()
    with patch("app.api.peers.detect_wireguard_binaries", return_value={"wg": None}):
        response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 422
    assert "WireGuard is not installed" in response.json()["detail"]


async def test_should_return_404_when_server_does_not_exist(auth_client, wg_installed):
    response = auth_client.post("/api/v1/peers/", json={"server_id": 9999, **VALID_PAYLOAD})

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_reject_duplicate_name_when_peer_already_exists(auth_client, make_server, make_peer, wg_installed):
    server = await make_server()
    await make_peer(server.id, name="phone")

    response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.name": ["Peer name 'phone' is already in use on this server"]}


async def test_should_allow_same_name_on_different_servers(auth_client, make_server, make_peer, wg_installed):
    server_a = await make_server(name="dup-a")
    server_b = await make_server(name="dup-b", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(server_a.id, name="phone")

    response = auth_client.post(
        "/api/v1/peers/",
        json={"server_id": server_b.id, **VALID_PAYLOAD, "ipv4_address": "10.9.0.5/24"},
    )

    assert response.status_code == 201


async def test_should_reject_ipv4_outside_server_subnet(auth_client, make_server, wg_installed):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/",
        json={"server_id": server.id, **VALID_PAYLOAD, "ipv4_address": "192.168.5.2/24"},
    )

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert "body.ipv4_address" in errors
    assert "not within server subnet" in errors["body.ipv4_address"][0]


async def test_should_reject_ipv6_outside_server_subnet(auth_client, make_server, wg_installed):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/",
        json={"server_id": server.id, **VALID_PAYLOAD, "ipv6_address": "fd00:99::5/64"},
    )

    assert response.status_code == 422
    assert "body.ipv6_address" in response.json()["errors"]


async def test_should_reject_peer_ipv4_equal_to_server_ip(auth_client, make_server, wg_installed):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/",
        json={"server_id": server.id, **VALID_PAYLOAD, "ipv4_address": "10.8.0.1/24"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]


async def test_should_reject_peer_ipv6_equal_to_server_ip(auth_client, make_server, wg_installed):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/",
        json={
            "server_id": server.id,
            **VALID_PAYLOAD,
            "ipv4_address": None,
            "ipv6_address": "fd00:8::1/64",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]


async def test_should_reject_duplicate_ipv4_address_when_peer_exists(auth_client, make_server, make_peer, wg_installed):
    server = await make_server()
    await make_peer(server.id, name="existing", ipv4_address="10.8.0.5/24")

    response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == [
        "IP address already in use by peer: existing on this server"
    ]


async def test_should_reject_duplicate_ipv6_address_when_peer_exists(auth_client, make_server, make_peer, wg_installed):
    server = await make_server()
    await make_peer(server.id, name="existing", ipv4_address=None, ipv6_address="fd00:8::9/64")

    response = auth_client.post(
        "/api/v1/peers/",
        json={
            "server_id": server.id,
            **VALID_PAYLOAD,
            "ipv4_address": None,
            "ipv6_address": "fd00:8::9/64",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == [
        "IP address already in use by peer: existing on this server"
    ]


async def test_should_reject_payload_when_no_ip_address_is_given(auth_client, make_server):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/", json={"server_id": server.id, "name": "no-ip", "public_key": "k", "private_key": "k"}
    )

    assert response.status_code == 422
    errors = response.json()["errors"]
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert errors["body.ipv4_address"] == [message]
    assert errors["body.ipv6_address"] == [message]


async def test_should_reject_invalid_cidr_when_payload_ipv4_is_malformed(auth_client, make_server):
    server = await make_server()

    response = auth_client.post(
        "/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD, "ipv4_address": "10.8.0.5"}
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == ["Invalid CIDR"]


async def test_should_reject_short_name_when_creating(auth_client, make_server):
    server = await make_server()

    response = auth_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD, "name": "a"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.name"] == ["Peer name must be at least 2 characters long"]


async def test_should_require_authentication_when_creating(api_client, seeded_db):
    response = api_client.post("/api/v1/peers/", json={"server_id": 1, **VALID_PAYLOAD})

    assert response.status_code == 401


async def test_should_reject_standard_user_when_creating(user_client, make_server, wg_installed):
    server = await make_server()

    response = user_client.post("/api/v1/peers/", json={"server_id": server.id, **VALID_PAYLOAD})

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"
