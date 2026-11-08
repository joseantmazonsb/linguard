"""Server lifecycle: start, stop and reload."""


async def test_should_start_server_when_it_is_stopped(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="stopped", needs_reload=True)
    wg.interface = "wg1"

    response = auth_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["interface"] == "wg1"
    assert body["needs_reload"] is False
    # The endpoint asks WireGuard to create a temporary interface named after the id.
    args = wg.start_interface.await_args.args
    assert args[1:] == (server.id, f"wg{server.id}")

    await db_session.refresh(server)
    assert server.status == "running"
    assert server.needs_reload is False


async def test_should_return_404_when_starting_missing_server(auth_client, wg):
    response = auth_client.post("/api/v1/servers/9999/start")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_400_when_server_is_already_running(auth_client, make_server, wg):
    server = await make_server(name="edge", status="running")

    response = auth_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 400
    assert response.json()["detail"] == "Server is already running"
    wg.start_interface.assert_not_awaited()


async def test_should_return_500_when_wireguard_fails_to_start(auth_client, make_server, wg):
    server = await make_server(name="edge", status="stopped")
    wg.start_interface.return_value = False

    response = auth_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to start server: Failed to start WireGuard interface"


async def test_should_return_500_when_interface_is_missing_after_start(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="stopped")
    wg.interface = None

    response = auth_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to start server: Interface not found after starting"
    await db_session.refresh(server)
    assert server.status == "stopped"


async def test_should_return_500_when_start_raises(auth_client, make_server, wg):
    server = await make_server(name="edge", status="stopped")
    wg.start_interface.side_effect = RuntimeError("wg not permitted")

    response = auth_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to start server: wg not permitted"


async def test_should_stop_server_when_it_is_running(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="running", interface="wg0", needs_reload=True)
    wg.interface = "wg2"

    response = auth_client.post(f"/api/v1/servers/{server.id}/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "stopped"
    assert body["interface"] is None
    assert body["needs_reload"] is False
    wg.stop_interface.assert_called_once_with("wg2", ipv4_subnet="10.8.0.1/24", ipv6_subnet="fd00:8::1/64")

    await db_session.refresh(server)
    assert server.status == "stopped"
    assert server.interface is None


async def test_should_fall_back_to_stored_interface_when_stopping(auth_client, make_server, wg):
    server = await make_server(name="edge", status="running", interface="wg9")
    wg.interface = None

    response = auth_client.post(f"/api/v1/servers/{server.id}/stop")

    assert response.status_code == 200
    wg.stop_interface.assert_called_once_with("wg9", ipv4_subnet="10.8.0.1/24", ipv6_subnet="fd00:8::1/64")


async def test_should_return_404_when_stopping_missing_server(auth_client, wg):
    response = auth_client.post("/api/v1/servers/9999/stop")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_400_when_stopping_server_that_is_not_running(auth_client, make_server, wg):
    server = await make_server(name="edge", status="stopped")

    response = auth_client.post(f"/api/v1/servers/{server.id}/stop")

    assert response.status_code == 400
    assert response.json()["detail"] == "Server is not running"


async def test_should_return_500_when_stop_fails(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="running", interface="wg0")
    wg.stop_interface.side_effect = RuntimeError("wg down failed")

    response = auth_client.post(f"/api/v1/servers/{server.id}/stop")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to stop server: wg down failed"
    await db_session.refresh(server)
    assert server.status == "running"


async def test_should_reload_server_when_interface_is_present(auth_client, make_server, db_session, wg):
    server = await make_server(name="edge", status="running", needs_reload=True)
    wg.interface = "wg1"

    response = auth_client.post(f"/api/v1/servers/{server.id}/reload")

    assert response.status_code == 200
    body = response.json()
    assert body["interface"] == "wg1"
    assert body["needs_reload"] is False
    wg.reload_interface.assert_awaited_once()

    await db_session.refresh(server)
    assert server.needs_reload is False


async def test_should_return_400_when_reloading_server_without_interface(auth_client, make_server, wg):
    server = await make_server(name="edge", status="stopped")
    wg.interface = None

    response = auth_client.post(f"/api/v1/servers/{server.id}/reload")

    assert response.status_code == 400
    assert response.json()["detail"] == "Server is not running"


async def test_should_return_404_when_reloading_missing_server(auth_client, wg):
    response = auth_client.post("/api/v1/servers/9999/reload")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_500_when_reload_fails(auth_client, make_server, wg):
    server = await make_server(name="edge", status="running")
    wg.interface = "wg1"
    wg.reload_interface.return_value = False

    response = auth_client.post(f"/api/v1/servers/{server.id}/reload")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to reload server: Failed to reload WireGuard interface"


async def test_should_forbid_standard_user_when_starting(user_client, make_server, wg):
    server = await make_server(name="edge", status="stopped")

    response = user_client.post(f"/api/v1/servers/{server.id}/start")

    assert response.status_code == 403
