"""List / count / detail / defaults endpoints for peers."""


async def test_should_return_empty_list_when_no_peers_exist(auth_client):
    response = auth_client.get("/api/v1/peers/")

    assert response.status_code == 200
    assert response.json() == []


async def test_should_require_authentication_when_listing_peers(api_client, seeded_db):
    response = api_client.get("/api/v1/peers/")

    assert response.status_code == 401


async def test_should_list_peers_ordered_by_id_when_peers_exist(auth_client, make_server, make_peer):
    server = await make_server(name="office")
    first = await make_peer(server.id, name="first")
    second = await make_peer(server.id, name="second", ipv4_address="10.8.0.3/24")

    response = auth_client.get("/api/v1/peers/")

    assert response.status_code == 200
    body = response.json()
    assert [peer["id"] for peer in body] == [first.id, second.id]
    assert body[0]["name"] == "first"
    assert body[0]["server_id"] == server.id
    assert body[0]["allowed_ips"] == "0.0.0.0/0, ::/0"


async def test_should_filter_peers_when_server_id_is_given(auth_client, make_server, make_peer):
    server_a = await make_server(name="a")
    server_b = await make_server(name="b", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(server_a.id, name="on-a")
    on_b = await make_peer(server_b.id, name="on-b")

    response = auth_client.get("/api/v1/peers/", params={"server_id": server_b.id})

    assert response.status_code == 200
    body = response.json()
    assert [peer["id"] for peer in body] == [on_b.id]
    assert body[0]["name"] == "on-b"


async def test_should_paginate_when_skip_and_limit_are_given(auth_client, make_server, make_peer):
    server = await make_server()
    for index in range(3):
        await make_peer(server.id, name=f"peer-{index}", ipv4_address=f"10.8.0.{index + 2}/24")

    response = auth_client.get("/api/v1/peers/", params={"skip": 1, "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "peer-1"


async def test_should_reject_limit_above_maximum_when_listing(auth_client):
    response = auth_client.get("/api/v1/peers/", params={"limit": 101})

    assert response.status_code == 422
    assert "body.query.limit" in response.json()["errors"]


async def test_should_count_all_and_per_server_peers(auth_client, make_server, make_peer):
    server_a = await make_server(name="count-a")
    server_b = await make_server(name="count-b", ipv4_address="10.10.0.1/24", ipv6_address="fd00:10::1/64")
    await make_peer(server_a.id, name="c1")
    await make_peer(server_a.id, name="c2", ipv4_address="10.8.0.3/24")
    await make_peer(server_b.id, name="c3")

    total = auth_client.get("/api/v1/peers/count")
    filtered = auth_client.get("/api/v1/peers/count", params={"server_id": server_a.id})

    assert total.status_code == 200
    assert total.json() == {"total": 3}
    assert filtered.json() == {"total": 2}


async def test_should_count_zero_when_no_peers_exist(auth_client):
    response = auth_client.get("/api/v1/peers/count")

    assert response.status_code == 200
    assert response.json() == {"total": 0}


async def test_should_return_peer_with_combined_allowed_ips_when_found(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(
        server.id,
        name="laptop",
        ipv4_allowed_ips="10.0.0.0/8",
        ipv6_allowed_ips="fd00::/64",
        last_handshake=None,
    )

    response = auth_client.get(f"/api/v1/peers/{peer.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == peer.id
    assert body["name"] == "laptop"
    assert body["allowed_ips"] == "10.0.0.0/8, fd00::/64"
    # Datetimes are normalised to UTC-aware ISO strings for the frontend.
    assert body["created_at"].endswith("Z")
    assert body["last_handshake"] is None


async def test_should_return_404_when_peer_does_not_exist(auth_client):
    response = auth_client.get("/api/v1/peers/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_return_defaults_for_next_free_ip_when_server_exists(
    auth_client, make_server, make_peer, fake_keypair
):
    server = await make_server(dns_primary="1.1.1.1", dns_secondary="8.8.8.8")
    await make_peer(server.id, ipv4_address="10.8.0.2/24", ipv6_address=None)

    response = auth_client.get(f"/api/v1/peers/defaults/{server.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["server_id"] == server.id
    assert body["ipv4_address"] == "10.8.0.3/24"
    assert body["ipv6_address"] == "fd00:8::2/64"
    assert body["dns_primary"] == "1.1.1.1"
    assert body["dns_secondary"] == "8.8.8.8"
    assert body["private_key"] == "priv-key"
    assert body["public_key"] == "pub-key"
    assert body["preshared_key"] == "psk-key"
    assert body["persistent_keepalive"] == 25
    assert body["enabled"] is True


async def test_should_return_404_when_defaults_requested_for_missing_server(auth_client):
    response = auth_client.get("/api/v1/peers/defaults/4242")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"
