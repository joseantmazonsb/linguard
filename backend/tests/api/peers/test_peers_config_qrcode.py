"""Peer configuration export and QR code generation."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from PIL import Image

from app.main import app


async def test_should_export_client_config_when_peer_exists(auth_client, make_server, make_peer):
    server = await make_server(
        name="office",
        endpoint="vpn.example.com",
        dns_primary="1.1.1.1",
        dns_secondary="8.8.8.8",
    )
    peer = await make_peer(
        server.id,
        name="laptop",
        ipv4_address="10.8.0.2/24",
        ipv6_address="fd00:8::2/64",
        preshared_key="z" * 44,
        ipv4_allowed_ips="10.0.0.0/8",
        ipv6_allowed_ips="fd00::/64",
        persistent_keepalive=15,
    )

    response = auth_client.get(f"/api/v1/peers/{peer.id}/config")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "[Interface]" in text
    assert "PrivateKey = " + peer.private_key in text
    assert "Address = 10.8.0.2/24, fd00:8::2/64" in text
    assert "[Peer]" in text
    assert "PublicKey = " + server.public_key in text
    assert "PresharedKey = " + "z" * 44 in text
    assert "DNS = 1.1.1.1, 8.8.8.8" in text
    assert "AllowedIPs = 10.0.0.0/8, fd00::/64" in text
    assert "PersistentKeepalive = 15" in text


async def test_should_return_404_when_exporting_missing_peer_config(auth_client):
    response = auth_client.get("/api/v1/peers/9999/config")

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_return_500_when_config_generation_fails(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)
    service = app.container.wireguard_service()

    with patch.object(service, "generate_peer_config_from_db", new=AsyncMock(side_effect=RuntimeError("no config"))):
        response = auth_client.get(f"/api/v1/peers/{peer.id}/config")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate config: no config"


async def test_should_return_png_qrcode_when_peer_exists(auth_client, make_server, make_peer):
    server = await make_server(endpoint="vpn.example.com")
    peer = await make_peer(server.id, name="phone")

    response = auth_client.get(f"/api/v1/peers/{peer.id}/qrcode")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(response.content))
    assert image.format == "PNG"
    assert image.width > 0 and image.height > 0


async def test_should_return_404_when_qrcode_requested_for_missing_peer(auth_client):
    response = auth_client.get("/api/v1/peers/9999/qrcode")

    assert response.status_code == 404
    assert response.json()["detail"] == "Peer not found"


async def test_should_return_500_when_qrcode_generation_fails(auth_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)
    service = app.container.wireguard_service()

    with patch.object(service, "generate_peer_config_from_db", new=AsyncMock(side_effect=RuntimeError("nope"))):
        response = auth_client.get(f"/api/v1/peers/{peer.id}/qrcode")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate QR code: nope"


async def test_should_forbid_standard_user_when_exporting_config(user_client, make_server, make_peer):
    server = await make_server()
    peer = await make_peer(server.id)

    response = user_client.get(f"/api/v1/peers/{peer.id}/config")

    assert response.status_code == 403
