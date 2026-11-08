"""Server creation, update and deletion."""

from sqlalchemy import select

from app.models.peer import Peer
from app.models.server import Server

SERVER_PAYLOAD = {
    "name": "edge",
    "listen_port": 51820,
    "ipv4_address": "10.8.0.1/24",
    "public_key": "S" * 44,
    "private_key": "s" * 44,
}


async def test_should_create_server_when_payload_is_valid(auth_client, db_session, wg_installed):
    response = auth_client.post("/api/v1/servers/", json=SERVER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "edge"
    assert body["listen_port"] == 51820
    assert body["ipv4_address"] == "10.8.0.1/24"
    assert body["status"] == "stopped"
    assert body["needs_reload"] is False
    assert body["peer_count"] == 0
    assert body["autostart"] is True
    assert body["public_key"] == "S" * 44

    stored = (await db_session.execute(select(Server))).scalars().one()
    assert stored.name == "edge"
    assert stored.private_key == "s" * 44


async def test_should_create_ipv6_only_server_when_no_ipv4_is_given(auth_client, wg_installed):
    payload = {**SERVER_PAYLOAD, "ipv4_address": None, "ipv6_address": "fd00:8::1/64"}

    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 201
    assert response.json()["ipv4_address"] is None
    assert response.json()["ipv6_address"] == "fd00:8::1/64"


async def test_should_return_422_when_wireguard_is_not_installed(auth_client):
    from unittest.mock import patch

    with patch("app.api.servers.detect_wireguard_binaries", return_value={"wg": None}):
        response = auth_client.post("/api/v1/servers/", json=SERVER_PAYLOAD)

    assert response.status_code == 422
    assert "WireGuard is not installed" in response.json()["detail"]


async def test_should_reject_duplicate_name_when_creating(auth_client, make_server, wg_installed):
    await make_server(name="edge")

    response = auth_client.post("/api/v1/servers/", json=SERVER_PAYLOAD)

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.name": ["Server name 'edge' is already in use"]}


async def test_should_reject_duplicate_ipv4_when_creating(auth_client, make_server, wg_installed):
    await make_server(name="existing")

    response = auth_client.post("/api/v1/servers/", json=SERVER_PAYLOAD)

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == ["IPv4 address already in use by server: existing"]


async def test_should_reject_duplicate_ipv6_when_creating(auth_client, make_server, wg_installed):
    await make_server(name="existing")

    payload = {**SERVER_PAYLOAD, "ipv4_address": None, "ipv6_address": "fd00:8::1/64"}
    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == ["IPv6 address already in use by server: existing"]


async def test_should_reject_overlapping_ipv4_subnet_when_creating(auth_client, make_server, wg_installed):
    await make_server(name="existing", ipv4_address="10.8.0.1/24")

    payload = {**SERVER_PAYLOAD, "ipv4_address": "10.8.0.2/24", "ipv6_address": None}
    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == [
        "Server IP 10.8.0.2 conflicts with existing server 'existing' subnet 10.8.0.0/24"
    ]


async def test_should_reject_overlapping_ipv6_subnet_when_creating(auth_client, make_server, wg_installed):
    await make_server(name="existing", ipv6_address="fd00:8::1/64")

    payload = {**SERVER_PAYLOAD, "ipv4_address": "10.9.0.1/24", "ipv6_address": "fd00:8::2/64"}
    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 422
    assert "conflicts with existing server 'existing' subnet" in (response.json()["errors"]["body.ipv6_address"][0])


async def test_should_return_404_when_bounce_server_is_missing(auth_client, wg_installed):
    payload = {**SERVER_PAYLOAD, "bounce_via_server_id": 9999}

    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Bounce server not found"


async def test_should_return_400_when_target_is_not_a_bounce_server(auth_client, make_server, wg_installed):
    plain = await make_server(name="plain", ipv4_address="10.40.0.1/24", ipv6_address=None)

    response = auth_client.post("/api/v1/servers/", json={**SERVER_PAYLOAD, "bounce_via_server_id": plain.id})

    assert response.status_code == 400
    assert response.json()["detail"] == "Specified server is not configured as a bounce server"


async def test_should_create_server_through_bounce_when_bounce_server_is_valid(auth_client, make_server, wg_installed):
    bounce = await make_server(name="bounce", is_bounce_server=True, ipv4_address="10.20.0.1/24", ipv6_address=None)

    response = auth_client.post(
        "/api/v1/servers/",
        json={
            **SERVER_PAYLOAD,
            "ipv4_address": "10.8.0.1/24",
            "bounce_via_server_id": bounce.id,
        },
    )

    assert response.status_code == 201
    assert response.json()["bounce_via_server_id"] == bounce.id


async def test_should_reject_payload_when_no_ip_address_is_given(auth_client, wg_installed):
    payload = {"name": "edge", "listen_port": 51820, "public_key": "S", "private_key": "s"}

    response = auth_client.post("/api/v1/servers/", json=payload)

    assert response.status_code == 422
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert response.json()["errors"]["body.ipv4_address"] == [message]
    assert response.json()["errors"]["body.ipv6_address"] == [message]


async def test_should_reject_reserved_port_when_creating(auth_client, wg_installed):
    response = auth_client.post("/api/v1/servers/", json={**SERVER_PAYLOAD, "listen_port": 80})

    assert response.status_code == 422
    assert response.json()["errors"]["body.listen_port"] == ["Listen port must be between 1024 and 65535"]


async def test_should_forbid_standard_user_when_creating(user_client, wg_installed):
    response = user_client.post("/api/v1/servers/", json=SERVER_PAYLOAD)

    assert response.status_code == 403


async def test_should_update_fields_when_payload_is_valid(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="stopped")

    response = auth_client.put(
        f"/api/v1/servers/{server.id}",
        json={
            "name": "edge-renamed",
            "description": "primary",
            "endpoint": "vpn.example.com",
            "listen_port": 51830,
            "ipv4_address": "10.8.0.1/24",
            "enabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "edge-renamed"
    assert body["description"] == "primary"
    assert body["endpoint"] == "vpn.example.com"
    assert body["listen_port"] == 51830
    assert body["enabled"] is False

    await db_session.refresh(server)
    assert server.name == "edge-renamed"
    assert server.listen_port == 51830


async def test_should_return_404_when_updating_missing_server(auth_client, wg):
    response = auth_client.put("/api/v1/servers/9999", json={"name": "ghost", "ipv4_address": "10.8.0.1/24"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_reject_update_when_payload_has_no_address(auth_client, make_server, wg):
    server = await make_server(name="edge")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"name": "edge-2"})

    assert response.status_code == 422
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert response.json()["errors"]["body.ipv4_address"] == [message]
    assert response.json()["errors"]["body.ipv6_address"] == [message]


async def test_should_reject_duplicate_name_when_updating(auth_client, make_server, wg):
    await make_server(name="taken")
    server = await make_server(name="edge", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"name": "taken", "ipv4_address": "10.9.0.1/24"})

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.name": ["Server name 'taken' is already in use"]}


async def test_should_reject_duplicate_ipv4_of_other_server_when_updating(auth_client, make_server, wg):
    await make_server(name="other", ipv4_address="10.9.0.1/24", ipv6_address=None)
    server = await make_server(name="edge")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv4_address": "10.9.0.1/24"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv4_address"] == ["IPv4 address already in use by server: other"]


async def test_should_reject_duplicate_ipv6_of_other_server_when_updating(auth_client, make_server, wg):
    await make_server(name="other", ipv4_address=None, ipv6_address="fd00:9::1/64")
    server = await make_server(name="edge")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv6_address": "fd00:9::1/64"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.ipv6_address"] == ["IPv6 address already in use by server: other"]


async def test_should_reject_overlapping_subnets_when_updating(auth_client, make_server, wg):
    await make_server(name="other", ipv4_address="10.30.0.1/24", ipv6_address="fd00:30::1/64")
    server = await make_server(name="edge")

    ipv4_response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv4_address": "10.30.0.5/24"})
    ipv6_response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv6_address": "fd00:30::5/64"})

    assert ipv4_response.status_code == 422
    assert "conflicts with existing server 'other' subnet" in (ipv4_response.json()["errors"]["body.ipv4_address"][0])
    assert ipv6_response.status_code == 422
    assert "conflicts with existing server 'other' subnet" in (ipv6_response.json()["errors"]["body.ipv6_address"][0])


async def test_should_clear_ipv4_when_ipv6_is_provided(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge")

    response = auth_client.put(
        f"/api/v1/servers/{server.id}", json={"ipv4_address": "", "ipv6_address": "fd00:8::1/64"}
    )

    assert response.status_code == 200
    assert response.json()["ipv4_address"] is None
    await db_session.refresh(server)
    assert server.ipv4_address is None


async def test_should_clear_ipv6_when_ipv4_is_provided(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv4_address": "10.8.0.1/24", "ipv6_address": ""})

    assert response.status_code == 200
    assert response.json()["ipv6_address"] is None
    await db_session.refresh(server)
    assert server.ipv6_address is None
    assert server.ipv4_address == "10.8.0.1/24"


async def test_should_reject_clearing_all_addresses_when_updating(auth_client, make_server, wg):
    server = await make_server(name="edge")

    response = auth_client.put(f"/api/v1/servers/{server.id}", json={"ipv4_address": "", "ipv6_address": ""})

    assert response.status_code == 422
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert response.json()["errors"]["body.ipv4_address"] == [message]


async def test_should_validate_bounce_server_when_bounce_is_changed(auth_client, make_server, wg):
    plain = await make_server(name="plain", ipv4_address="10.40.0.1/24", ipv6_address=None)
    server = await make_server(name="edge")

    response = auth_client.put(
        f"/api/v1/servers/{server.id}",
        json={"ipv4_address": "10.8.0.1/24", "bounce_via_server_id": plain.id},
    )

    assert response.status_code == 422
    assert response.json()["errors"] == {"body.bounce_via_server_id": ["Invalid bounce server configuration"]}


async def test_should_keep_bounce_server_when_value_is_unchanged(auth_client, make_server, wg):
    bounce = await make_server(name="bounce", is_bounce_server=True, ipv4_address="10.50.0.1/24", ipv6_address=None)
    server = await make_server(name="edge", bounce_via_server_id=bounce.id)

    response = auth_client.put(
        f"/api/v1/servers/{server.id}",
        json={"ipv4_address": "10.8.0.1/24", "bounce_via_server_id": bounce.id},
    )

    assert response.status_code == 200
    assert response.json()["bounce_via_server_id"] == bounce.id


async def test_should_reject_invalid_endpoint_when_updating(auth_client, make_server, wg):
    server = await make_server(name="edge")

    response = auth_client.put(
        f"/api/v1/servers/{server.id}",
        json={"endpoint": "not a host name", "ipv4_address": "10.8.0.1/24"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.endpoint"] == [
        "Endpoint must be a valid IPv4 address, IPv6 address, or hostname"
    ]


async def test_should_delete_server_and_its_peers_when_server_exists(
    auth_client, make_server, make_peer, db_session, wg
):
    server = await make_server(name="edge", status="stopped")
    await make_peer(server.id, name="child", ipv4_address="10.8.0.2/24")
    other = await make_server(name="other", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(other.id, name="kept")

    response = auth_client.delete(f"/api/v1/servers/{server.id}")

    assert response.status_code == 204
    servers = (await db_session.execute(select(Server))).scalars().all()
    assert [row.name for row in servers] == ["other"]
    peers = (await db_session.execute(select(Peer))).scalars().all()
    assert [row.name for row in peers] == ["kept"]


async def test_should_stop_interface_when_deleting_running_server(auth_client, make_server, wg):
    server = await make_server(name="edge", status="running", interface="wg5")

    response = auth_client.delete(f"/api/v1/servers/{server.id}")

    assert response.status_code == 204
    wg.stop_interface.assert_called_once_with("wg5", ipv4_subnet="10.8.0.1/24", ipv6_subnet="fd00:8::1/64")


async def test_should_return_404_when_deleting_missing_server(auth_client, wg):
    response = auth_client.delete("/api/v1/servers/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_forbid_standard_user_when_deleting(user_client, make_server, wg):
    server = await make_server(name="edge")

    response = user_client.delete(f"/api/v1/servers/{server.id}")

    assert response.status_code == 403
