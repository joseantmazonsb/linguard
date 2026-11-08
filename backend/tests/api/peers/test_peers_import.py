"""Peer config file import."""

from subprocess import CompletedProcess
from unittest.mock import patch

from sqlalchemy import select

from app.models.peer import Peer

CLIENT_CONFIG = """[Interface]
PrivateKey = {private_key}
Address = 10.8.0.9/32, fd00:8::9/128
DNS = 1.1.1.1, 8.8.8.8

[Peer]
PublicKey = {server_key}
AllowedIPs = 10.0.0.0/8, fd00::/64
Endpoint = vpn.example.com:51820
PersistentKeepalive = 15
"""


def _config(**overrides):
    values = {"private_key": "e" * 43 + "=", "server_key": "f" * 43 + "="}
    values.update(overrides)
    return CLIENT_CONFIG.format(**values)


def _wg_pubkey(stdout=b"c" * 44 + b"\n"):
    return CompletedProcess(args=["wg", "pubkey"], returncode=0, stdout=stdout, stderr=b"")


async def test_should_import_peer_from_config_file_when_server_is_running(
    auth_client, make_server, db_session, wg, wg_installed
):
    server = await make_server(status="running")

    with patch("subprocess.run", return_value=_wg_pubkey()) as run:
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("laptop.conf", _config(), "text/plain")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "laptop"
    assert body["server_id"] == server.id
    assert body["ipv4_address"] == "10.8.0.9/32"
    assert body["ipv6_address"] == "fd00:8::9/128"
    assert body["dns_primary"] == "1.1.1.1"
    assert body["dns_secondary"] == "8.8.8.8"
    assert body["ipv4_allowed_ips"] == "10.0.0.0/8"
    assert body["ipv6_allowed_ips"] == "fd00::/64"
    assert body["persistent_keepalive"] == 15
    # The peer's own public key is derived from the config's private key.
    assert body["public_key"] == "c" * 44
    assert run.call_args.args[0] == ["wg", "pubkey"]

    stored = (await db_session.execute(select(Peer))).scalars().one()
    assert stored.name == "laptop"
    assert stored.private_key == "e" * 43 + "="
    # The running server is reloaded so the new peer becomes active.
    wg.reload_interface.assert_awaited_once()


async def test_should_strip_wg_extension_when_naming_imported_peer(auth_client, make_server, wg_installed):
    server = await make_server(status="stopped")

    with patch("subprocess.run", return_value=_wg_pubkey()):
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("tablet.wg", _config(), "text/plain")},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "tablet"


async def test_should_still_import_when_server_reload_fails(auth_client, make_server, wg, wg_installed):
    server = await make_server(status="running")
    wg.reload_interface.side_effect = RuntimeError("wg reload failed")

    with patch("subprocess.run", return_value=_wg_pubkey()):
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("phone.conf", _config(), "text/plain")},
        )

    assert response.status_code == 201


async def test_should_return_422_when_wireguard_is_not_installed(auth_client, make_server, wg):
    server = await make_server()

    with patch("app.api.peers.detect_wireguard_binaries", return_value={"wg": None}):
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("phone.conf", _config(), "text/plain")},
        )

    assert response.status_code == 422
    assert "WireGuard is not installed" in response.json()["detail"]


async def test_should_return_404_when_import_target_server_is_missing(auth_client, wg_installed):
    response = auth_client.post(
        "/api/v1/peers/import",
        params={"server_id": 9999},
        files={"config_file": ("phone.conf", _config(), "text/plain")},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


async def test_should_return_400_when_config_file_is_malformed(auth_client, make_server, wg_installed):
    server = await make_server()
    broken = CLIENT_CONFIG.format(private_key="e" * 43 + "=", server_key="f" * 43 + "=")
    broken = broken.replace("Endpoint = vpn.example.com:51820", "Endpoint = vpn.example.com:not-a-port")

    response = auth_client.post(
        "/api/v1/peers/import",
        params={"server_id": server.id},
        files={"config_file": ("broken.conf", broken, "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid config file:")


async def test_should_return_400_when_public_key_cannot_be_derived(auth_client, make_server, wg_installed):
    server = await make_server()

    with patch("subprocess.run", side_effect=FileNotFoundError("wg missing")):
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("phone.conf", _config(), "text/plain")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Invalid config file: Could not derive public key from private key. "
        "Config must include public key or valid private key."
    )


async def test_should_return_500_when_parser_crashes(auth_client, make_server, wg_installed):
    server = await make_server()
    parser = auth_client.app.container.config_parser_service()

    with patch.object(parser, "parse_peer_config", side_effect=RuntimeError("parser kaput")):
        response = auth_client.post(
            "/api/v1/peers/import",
            params={"server_id": server.id},
            files={"config_file": ("phone.conf", _config(), "text/plain")},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to import config: parser kaput"


async def test_should_forbid_standard_user_when_importing(user_client, make_server):
    server = await make_server()

    response = user_client.post(
        "/api/v1/peers/import",
        params={"server_id": server.id},
        files={"config_file": ("phone.conf", _config(), "text/plain")},
    )

    assert response.status_code == 403
