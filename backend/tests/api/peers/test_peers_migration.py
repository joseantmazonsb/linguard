"""Peer migration: preview and the migrate endpoint."""

from unittest.mock import AsyncMock, patch


async def test_should_suggest_next_free_addresses_when_previewing_migration(
    auth_client, make_server, make_peer, fake_keypair
):
    source = await make_server(name="edge")
    target = await make_server(
        name="core",
        ipv4_address="10.9.0.1/24",
        ipv6_address="fd00:9::1/64",
        dns_primary="9.9.9.9",
        dns_secondary="149.112.112.112",
    )
    await make_peer(target.id, name="already-there", ipv4_address="10.9.0.2/24", ipv6_address=None)
    peer = await make_peer(
        source.id,
        name="remote",
        ipv4_address="10.8.0.2/24",
        ipv6_address="fd00:8::2/64",
        dns_primary="1.1.1.1",
        ipv4_allowed_ips="10.0.0.0/8",
        persistent_keepalive=15,
    )

    response = auth_client.get(f"/api/v1/peers/{peer.id}/migration-preview", params={"target_server_id": target.id})

    assert response.status_code == 200
    body = response.json()
    assert body["suggested_ipv4_address"] == "10.9.0.3/24"
    assert body["suggested_ipv6_address"] == "fd00:9::2/64"
    assert body["suggested_dns_primary"] == "9.9.9.9"
    assert body["suggested_dns_secondary"] == "149.112.112.112"
    assert body["current_ipv4_address"] == "10.8.0.2/24"
    assert body["current_ipv6_address"] == "fd00:8::2/64"
    assert body["current_dns_primary"] == "1.1.1.1"
    assert body["current_ipv4_allowed_ips"] == "10.0.0.0/8"
    assert body["current_persistent_keepalive"] == 15


async def test_should_return_404_when_previewing_missing_peer(auth_client, make_server):
    target = await make_server()

    response = auth_client.get("/api/v1/peers/9999/migration-preview", params={"target_server_id": target.id})

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_return_404_when_migration_target_is_missing(auth_client, make_server, make_peer):
    source = await make_server()
    peer = await make_peer(source.id)

    response = auth_client.get(f"/api/v1/peers/{peer.id}/migration-preview", params={"target_server_id": 9999})

    assert response.status_code == 404
    assert response.json()["detail"] == "Target server not found"


async def test_should_move_peer_with_custom_config_when_migration_succeeds(
    auth_client, make_server, make_peer, db_session, wg
):
    source = await make_server(name="edge", status="running")
    target = await make_server(
        name="core",
        status="running",
        ipv4_address="10.9.0.1/24",
        ipv6_address="fd00:9::1/64",
        dns_primary="9.9.9.9",
    )
    peer = await make_peer(source.id, name="remote", ipv4_address="10.8.0.2/24")

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={
            "target_server_id": target.id,
            "ipv4_address": "10.9.0.4/24",
            "ipv6_address": "fd00:9::4/64",
            "dns_primary": "9.9.9.9",
            "dns_secondary": "149.112.112.112",
            "ipv4_allowed_ips": "10.0.0.0/8",
            "ipv6_allowed_ips": "fd00::/64",
            "persistent_keepalive": 20,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == target.id
    assert body["ipv4_address"] == "10.9.0.4/24"
    assert body["ipv6_address"] == "fd00:9::4/64"
    assert body["dns_primary"] == "9.9.9.9"
    assert body["dns_secondary"] == "149.112.112.112"
    assert body["ipv4_allowed_ips"] == "10.0.0.0/8"
    assert body["ipv6_allowed_ips"] == "fd00::/64"
    assert body["persistent_keepalive"] == 20

    await db_session.refresh(peer)
    assert peer.server_id == target.id
    # Both interfaces were reloaded because both servers were running.
    assert wg.reload_interface.await_count == 2


async def test_should_skip_reload_when_servers_are_stopped(auth_client, make_server, make_peer, wg):
    source = await make_server(name="edge", status="stopped")
    target = await make_server(name="core", status="stopped", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.9.0.5/24"},
    )

    assert response.status_code == 200
    wg.reload_interface.assert_not_awaited()


async def test_should_still_migrate_when_interface_reload_fails(auth_client, make_server, make_peer, wg):
    source = await make_server(name="edge", status="running")
    target = await make_server(name="core", status="running", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)
    wg.reload_interface.side_effect = RuntimeError("wg reload exploded")

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.9.0.6/24"},
    )

    assert response.status_code == 200
    assert response.json()["server_id"] == target.id


async def test_should_return_400_when_peer_is_already_on_target_server(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": server.id, "ipv4_address": "10.8.0.9/24"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Peer is already on this server"


async def test_should_return_404_when_migrating_missing_peer(auth_client, make_server):
    target = await make_server()

    response = auth_client.post(
        "/api/v1/peers/9999/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.8.0.9/24"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_return_404_when_migration_target_does_not_exist(auth_client, make_server, make_peer):
    source = await make_server()
    peer = await make_peer(source.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": 9999, "ipv4_address": "10.8.0.9/24"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Target server not found"


async def test_should_reject_migration_when_no_address_is_requested(auth_client, make_server, make_peer):
    source = await make_server()
    target = await make_server(ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    response = auth_client.post(f"/api/v1/peers/{peer.id}/migrate", json={"target_server_id": target.id})

    assert response.status_code == 422
    message = "At least one IP address (IPv4 or IPv6) is required"
    assert response.json()["errors"]["body.ipv4_address"] == [message]


async def test_should_reject_migration_address_outside_target_subnet(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.55.0.4/24"},
    )

    assert response.status_code == 422
    assert "not within server subnet" in response.json()["errors"]["body.ipv4_address"][0]


async def test_should_reject_migration_ipv6_outside_target_subnet(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv6_address": "fd00:55::4/64"},
    )

    assert response.status_code == 422
    assert "body.ipv6_address" in response.json()["errors"]


async def test_should_reject_migration_address_equal_to_target_server_ip(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    ipv4_response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.9.0.1/24"},
    )
    ipv6_response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv6_address": "fd00:9::1/64"},
    )

    assert ipv4_response.status_code == 422
    assert ipv4_response.json()["errors"]["body.ipv4_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]
    assert ipv6_response.status_code == 422
    assert ipv6_response.json()["errors"]["body.ipv6_address"] == [
        "Peer IP address cannot be the same as the server IP address"
    ]


async def test_should_reject_migration_when_target_address_is_in_use(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(target.id, name="squatter", ipv4_address=None, ipv6_address="fd00:9::7/64")
    peer = await make_peer(source.id)

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv6_address": "fd00:9::7/64"},
    )

    assert response.status_code == 422
    # Duplicate detection must attribute the clash to the IPv6 field, not IPv4.
    assert response.json()["errors"]["body.ipv6_address"] == [
        "IP address already in use by peer: squatter on target server"
    ]


async def test_should_reject_migration_when_target_peer_name_is_taken(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(target.id, name="remote", ipv4_address="10.9.0.2/24")
    peer = await make_peer(source.id, name="remote")

    response = auth_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.9.0.9/24"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.name"] == ["Peer name 'remote' is already in use on target server"]


async def test_should_return_400_when_migration_service_raises_value_error(auth_client, make_server, make_peer):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)
    service = auth_client.app.container.migration_service()

    with patch.object(service, "migrate_peer", new=AsyncMock(side_effect=ValueError("target busy"))):
        response = auth_client.post(
            f"/api/v1/peers/{peer.id}/migrate",
            json={"target_server_id": target.id, "ipv4_address": "10.9.0.9/24"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "target busy"


async def test_should_return_500_when_migration_service_crashes(auth_client, make_server, make_peer, db_session):
    source = await make_server(name="edge")
    target = await make_server(name="core", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)
    service = auth_client.app.container.migration_service()

    with patch.object(service, "migrate_peer", new=AsyncMock(side_effect=RuntimeError("boom"))):
        response = auth_client.post(
            f"/api/v1/peers/{peer.id}/migrate",
            json={"target_server_id": target.id, "ipv4_address": "10.9.0.9/24"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Migration failed: boom"
    await db_session.refresh(peer)
    assert peer.server_id == source.id


async def test_should_forbid_standard_user_when_migrating(user_client, make_server, make_peer):
    source = await make_server()
    target = await make_server(ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    peer = await make_peer(source.id)

    response = user_client.post(
        f"/api/v1/peers/{peer.id}/migrate",
        json={"target_server_id": target.id, "ipv4_address": "10.9.0.9/24"},
    )

    assert response.status_code == 403
