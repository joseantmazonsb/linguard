"""Server list / detail / autofill defaults."""


async def test_should_return_empty_list_when_no_servers_exist(auth_client, wg):
    response = auth_client.get("/api/v1/servers/")

    assert response.status_code == 200
    assert response.json() == []


async def test_should_require_authentication_when_listing_servers(api_client, seeded_db, wg):
    response = api_client.get("/api/v1/servers/")

    assert response.status_code == 401


async def test_should_list_servers_with_peer_counts_when_servers_exist(auth_client, make_server, make_peer, wg):
    await make_server(name="empty")
    busy = await make_server(name="busy", ipv4_address="10.9.0.1/24", ipv6_address="fd00:9::1/64")
    await make_peer(busy.id, name="one", ipv4_address="10.9.0.2/24")
    await make_peer(busy.id, name="two", ipv4_address="10.9.0.3/24")

    response = auth_client.get("/api/v1/servers/")

    assert response.status_code == 200
    body = response.json()
    assert [server["name"] for server in body] == ["empty", "busy"]
    assert [server["peer_count"] for server in body] == [0, 2]
    assert body[1]["id"] == busy.id


async def test_should_mark_server_running_when_interface_exists(auth_client, make_server, db_session, wg):
    server = await make_server(name="live", status="stopped", interface=None)
    wg.interface = "wg7"

    response = auth_client.get("/api/v1/servers/")

    assert response.status_code == 200
    body = response.json()[0]
    assert body["status"] == "running"
    assert body["interface"] == "wg7"
    await db_session.refresh(server)
    assert server.status == "running"


async def test_should_mark_server_stopped_when_interface_disappeared(auth_client, make_server, db_session, wg):
    server = await make_server(name="ghost", status="running", interface="wg3")
    wg.interface = None

    response = auth_client.get(f"/api/v1/servers/{server.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stopped"
    assert body["interface"] is None
    await db_session.refresh(server)
    assert server.status == "stopped"


async def test_should_return_server_with_peer_count_when_found(auth_client, make_server, make_peer, wg):
    server = await make_server(name="office", status="stopped", endpoint="vpn.example.com")
    await make_peer(server.id, name="laptop")

    response = auth_client.get(f"/api/v1/servers/{server.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == server.id
    assert body["name"] == "office"
    assert body["peer_count"] == 1
    assert body["endpoint"] == "vpn.example.com"
    assert body["ipv4_address"] == "10.8.0.1/24"
    assert body["created_at"].endswith("Z")


async def test_should_return_404_when_server_does_not_exist(auth_client, wg):
    response = auth_client.get("/api/v1/servers/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_autofill_first_subnet_when_no_servers_exist(auth_client, fake_keypair):
    response = auth_client.get("/api/v1/servers/defaults/autofill")

    assert response.status_code == 200
    body = response.json()
    assert body["interface"] == "wg0"
    assert body["listen_port"] == 51820
    assert body["ipv4_address"] == "10.0.0.1/24"
    assert body["ipv6_address"].endswith("/64")
    assert body["private_key"] == "priv-key"
    assert body["public_key"] == "pub-key"
    assert body["is_bounce_server"] is False
    assert body["enabled"] is True


async def test_should_autofill_next_free_values_when_servers_already_exist(auth_client, make_server, fake_keypair):
    await make_server(name="existing", listen_port=51900, ipv4_address="10.0.0.1/24")

    response = auth_client.get("/api/v1/servers/defaults/autofill")

    assert response.status_code == 200
    body = response.json()
    assert body["interface"] == "wg1"
    assert body["listen_port"] == 51901
    # The subnet used by the existing server is skipped.
    assert body["ipv4_address"] == "10.0.1.1/24"
