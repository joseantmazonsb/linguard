"""
Unit tests for QR code generation endpoint.

Tests that the /peers/{peer_id}/qrcode endpoint correctly generates QR codes
for peer configurations.
"""

import pytest
from io import BytesIO
from PIL import Image


@pytest.mark.asyncio
async def test_get_peer_qrcode_success(async_client, auth_headers, test_server, test_peer):
    """Test successfully generating a QR code for a peer."""
    # Act
    response = await async_client.get(
        f"/api/v1/peers/{test_peer.id}/qrcode",
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify it's a valid PNG image
    content = response.content
    assert len(content) > 0
    
    # Check PNG signature
    assert content[:8] == b'\x89PNG\r\n\x1a\n'
    
    # Verify we can open it as an image
    img = Image.open(BytesIO(content))
    assert img.format == "PNG"
    assert img.size[0] > 0 and img.size[1] > 0


@pytest.mark.asyncio
async def test_get_peer_qrcode_peer_not_found(async_client, auth_headers):
    """Test QR code generation with non-existent peer."""
    # Act
    response = await async_client.get(
        "/api/v1/peers/99999/qrcode",
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_peer_qrcode_requires_auth(async_client, test_peer):
    """Test that QR code endpoint requires authentication."""
    # Act - call without auth headers
    response = await async_client.get(
        f"/api/v1/peers/{test_peer.id}/qrcode"
    )
    
    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_peer_qrcode_with_ipv4_only(async_client, auth_headers, test_server):
    """Test QR code generation for peer with only IPv4."""
    # Arrange - create a peer with only IPv4
    peer_data = {
        "name": "QR Test Peer IPv4",
        "server_id": test_server.id,
        "ipv4_address": "10.8.0.100/32",
        "public_key": "test_qr_public_key_base64_encoded_chars",
        "private_key": "test_qr_private_key_base64_encoded_char",
        "allowed_ips": "0.0.0.0/0"
    }
    
    create_response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    assert create_response.status_code in [200, 201]
    peer = create_response.json()
    
    # Act - get QR code
    response = await async_client.get(
        f"/api/v1/peers/{peer['id']}/qrcode",
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify it's a valid PNG
    content = response.content
    img = Image.open(BytesIO(content))
    assert img.format == "PNG"


@pytest.mark.asyncio
async def test_get_peer_qrcode_with_both_ips(async_client, auth_headers, test_server):
    """Test QR code generation for peer with both IPv4 and IPv6."""
    # Arrange - create a peer with both IPs
    peer_data = {
        "name": "QR Test Peer Dual Stack",
        "server_id": test_server.id,
        "ipv4_address": "10.8.0.101/32",
        "ipv6_address": "fd00::101/128",
        "public_key": "test_qr_dual_public_key_base64_chars=",
        "private_key": "test_qr_dual_private_key_base64_char=",
        "allowed_ips": "0.0.0.0/0, ::/0"
    }
    
    create_response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    assert create_response.status_code in [200, 201]
    peer = create_response.json()
    
    # Act - get QR code
    response = await async_client.get(
        f"/api/v1/peers/{peer['id']}/qrcode",
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    
    # Verify it's a valid PNG
    content = response.content
    img = Image.open(BytesIO(content))
    assert img.format == "PNG"
    
    # QR code with both IPs should be larger than with just one
    # (more data = larger QR code)
    assert img.size[0] > 100  # Reasonable minimum size
