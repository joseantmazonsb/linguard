"""Server configuration export and import."""

from subprocess import CompletedProcess
from unittest.mock import AsyncMock, patch

SERVER_CONFIG = """[Interface]
# managed by linguist
PrivateKey = {private_key}
Address = 10.9.0.1/24, fd00:9::1/64
ListenPort = 51830
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {peer_key}
AllowedIPs = 10.9.0.2/32
"""


def _config(private_key="t" * 43 + "=", peer_key="u" * 43 + "="):
    return SERVER_CONFIG.format(private_key=private_key, peer_key=peer_key)


def _wg_pubkey():
    return CompletedProcess(args=["wg", "pubkey"], returncode=0, stdout=b"v" * 44 + b"\n", stderr=b"")


async def test_should_export_config_with_only_enabled_peers(auth_client, make_server, make_peer):
    server = await make_server(name="office", endpoint="vpn.example.com")
    enabled = await make_peer(
        server.id,
        name="enabled",
        public_key="E" * 44,
        ipv4_address="10.8.0.2/24",
        ipv6_address="fd00:8::2/64",
    )
    await make_peer(server.id, name="disabled", public_key="D" * 44, ipv4_address="10.8.0.3/24", enabled=False)

    response = auth_client.get(f"/api/v1/servers/{server.id}/config")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "[Interface]" in text
    assert f"PrivateKey = {server.private_key}" in text
    assert "Address = 10.8.0.1/24, fd00:8::1/64" in text
    assert "ListenPort = 51820" in text
    assert f"PublicKey = {enabled.public_key}" in text
    assert "AllowedIPs = 10.8.0.2/32, fd00:8::2/128" in text
    assert "D" * 44 not in text


async def test_should_return_404_when_exporting_missing_server_config(auth_client):
    response = auth_client.get("/api/v1/servers/9999/config")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_500_when_server_config_generation_fails(auth_client, make_server):
    from app.main import app

    server = await make_server(name="office")
    service = app.container.wireguard_service()

    with patch.object(service, "generate_server_config", new=AsyncMock(side_effect=RuntimeError("broken"))):
        response = auth_client.get(f"/api/v1/servers/{server.id}/config")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate config: broken"


async def test_should_import_server_from_config_file_when_valid(auth_client, db_session, wg_installed):
    with patch("subprocess.run", return_value=_wg_pubkey()):
        response = auth_client.post(
            "/api/v1/servers/import",
            files={"config_file": ("office.conf", _config(), "text/plain")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "office"
    assert body["listen_port"] == 51830
    assert body["ipv4_address"] == "10.9.0.1/24"
    assert body["ipv6_address"] == "fd00:9::1/64"
    assert body["dns_primary"] == "1.1.1.1"
    assert body["dns_secondary"] == "8.8.8.8"
    assert body["public_key"] == "v" * 44
    assert body["status"] == "stopped"
    assert body["peer_count"] == 0


async def test_should_strip_conf_extension_when_naming_imported_server(auth_client, wg_installed):
    with patch("subprocess.run", return_value=_wg_pubkey()):
        response = auth_client.post(
            "/api/v1/servers/import",
            files={"config_file": ("home-gw.conf", _config(), "text/plain")},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "home-gw"


async def test_should_return_422_when_wireguard_is_not_installed(auth_client):
    with patch("app.api.servers.detect_wireguard_binaries", return_value={"wg": None}):
        response = auth_client.post(
            "/api/v1/servers/import",
            files={"config_file": ("office.conf", _config(), "text/plain")},
        )

    assert response.status_code == 422
    assert "WireGuard is not installed" in response.json()["detail"]


async def test_should_return_400_when_config_listen_port_is_invalid(auth_client, wg_installed):
    broken = _config().replace("ListenPort = 51830", "ListenPort = not-a-number")

    response = auth_client.post(
        "/api/v1/servers/import",
        files={"config_file": ("broken.conf", broken, "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid config file:")


async def test_should_return_400_when_public_key_cannot_be_derived(auth_client, wg_installed):
    with patch("subprocess.run", side_effect=FileNotFoundError("no wg")):
        response = auth_client.post(
            "/api/v1/servers/import",
            files={"config_file": ("office.conf", _config(), "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid config file: Could not derive public key from private key. " "Config must include a valid PrivateKey."
    )


async def test_should_return_500_when_server_parser_crashes(auth_client, wg_installed):
    parser = auth_client.app.container.config_parser_service()

    with patch.object(parser, "parse_server_config", side_effect=RuntimeError("kaput")):
        response = auth_client.post(
            "/api/v1/servers/import",
            files={"config_file": ("office.conf", _config(), "text/plain")},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to import config: kaput"


async def test_should_forbid_standard_user_when_importing(user_client):
    response = user_client.post(
        "/api/v1/servers/import",
        files={"config_file": ("office.conf", _config(), "text/plain")},
    )

    assert response.status_code == 403
