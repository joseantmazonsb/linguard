"""
Integration tests for Peer API validation.

Tests the peer CREATE, UPDATE, and MIGRATE endpoints to ensure:
1. Peers cannot have the same IP as their server
2. Peers cannot have duplicate IPs
3. NULL IPv4/IPv6 handling works correctly
4. IP autofill returns first free IP (not server IP)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_create_peer_with_only_ipv4(async_client: AsyncClient, auth_headers: dict, test_server):
    """Test creating a peer with only IPv4 (no IPv6) - tests NULL matching bug fix."""
    # Arrange
    peer_data = {
        "name": "TestPeerIPv4Only",
        "server_id": test_server.id,
        "ipv4_address": "10.8.0.50/32",
        "public_key": "test_public_key_base64_encoded_32_chars==",
        "allowed_ips": "0.0.0.0/0"
    }
    
    # Act
    response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200 or response.status_code == 201
    data = response.json()
    assert data["ipv4_address"] == "10.8.0.50/32"
    assert data["ipv6_address"] is None


@pytest.mark.asyncio
async def test_create_peer_with_only_ipv6(async_client: AsyncClient, auth_headers: dict, test_server):
    """Test creating a peer with only IPv6 (no IPv4)."""
    # Arrange
    peer_data = {
        "name": "TestPeerIPv6Only",
        "server_id": test_server.id,
        "ipv6_address": "fd00::50/128",
        "public_key": "test_public_key_base64_encoded_32_chars==",
        "allowed_ips": "::/0"
    }
    
    # Act
    response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200 or response.status_code == 201
    data = response.json()
    assert data["ipv4_address"] is None
    assert data["ipv6_address"] == "fd00::50/128"


@pytest.mark.asyncio
async def test_create_peer_with_server_ip_fails(async_client: AsyncClient, auth_headers: dict, test_server):
    """Test that creating a peer with the same IP as the server fails with 422."""
    # Arrange - try to use server's IP
    peer_data = {
        "name": "BadPeer",
        "server_id": test_server.id,
        "ipv4_address": test_server.ipv4_address,  # Same as server!
        "public_key": "test_public_key_base64_encoded_32_chars==",
        "allowed_ips": "0.0.0.0/0"
    }
    
    # Act
    response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "cannot be the same as the server IP" in str(data)


@pytest.mark.asyncio
async def test_create_peer_with_duplicate_ipv4_fails(async_client: AsyncClient, auth_headers: dict, test_server, test_peer):
    """Test that creating a peer with a duplicate IPv4 fails with 422."""
    # Arrange - try to use existing peer's IP
    peer_data = {
        "name": "DuplicatePeer",
        "server_id": test_server.id,
        "ipv4_address": test_peer.ipv4_address,  # Same as existing peer!
        "public_key": "different_public_key_base64_encoded==",
        "allowed_ips": "0.0.0.0/0"
    }
    
    # Act
    response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "already in use" in str(data)


@pytest.mark.asyncio
async def test_update_peer_to_server_ip_fails(async_client: AsyncClient, auth_headers: dict, test_server, test_peer):
    """Test that updating a peer to use the server's IP fails with 422."""
    # Arrange
    update_data = {
        "ipv4_address": test_server.ipv4_address  # Try to change to server IP
    }
    
    # Act
    response = await async_client.put(
        f"/api/v1/peers/{test_peer.id}",
        json=update_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "cannot be the same as the server IP" in str(data)


@pytest.mark.asyncio
async def test_get_peer_defaults_returns_free_ip(async_client: AsyncClient, auth_headers: dict, test_server):
    """Test that /peers/defaults/{server_id} returns first free IP, not server IP."""
    # Act
    response = await async_client.get(
        f"/api/v1/peers/defaults/{test_server.id}",
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    # Verify suggested IPv4 is not the server IP
    if data.get("ipv4_address"):
        server_ip = test_server.ipv4_address.split('/')[0]
        suggested_ip = data["ipv4_address"].split('/')[0]
        assert suggested_ip != server_ip, f"Suggested IP {suggested_ip} should not equal server IP {server_ip}"
    
    # Verify suggested IPv6 is not the server IP
    if data.get("ipv6_address") and test_server.ipv6_address:
        server_ip = test_server.ipv6_address.split('/')[0]
        suggested_ip = data["ipv6_address"].split('/')[0]
        assert suggested_ip != server_ip, f"Suggested IPv6 {suggested_ip} should not equal server IPv6 {server_ip}"


@pytest.mark.asyncio
async def test_migration_preview_returns_free_ip(async_client: AsyncClient, auth_headers: dict, test_server, test_server2, test_peer):
    """Test that migration preview returns first free IP on target server."""
    # Act
    response = await async_client.get(
        f"/api/v1/peers/{test_peer.id}/migration-preview",
        params={"target_server_id": test_server2.id},
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    # Verify suggested IPv4 is not the target server IP
    if data.get("suggested_ipv4_address") and test_server2.ipv4_address:
        server_ip = test_server2.ipv4_address.split('/')[0]
        suggested_ip = data["suggested_ipv4_address"].split('/')[0]
        assert suggested_ip != server_ip, f"Suggested IP {suggested_ip} should not equal target server IP {server_ip}"


@pytest.mark.asyncio
async def test_migrate_peer_with_server_ip_fails(async_client: AsyncClient, auth_headers: dict, test_server, test_server2, test_peer):
    """Test that migrating a peer with target server's IP fails with 422."""
    # Arrange
    migration_data = {
        "target_server_id": test_server2.id,
        "ipv4_address": test_server2.ipv4_address  # Try to use target server IP
    }
    
    # Act
    response = await async_client.post(
        f"/api/v1/peers/{test_peer.id}/migrate",
        json=migration_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "cannot be the same as the server IP" in str(data)


@pytest.mark.asyncio
async def test_create_peer_without_ip_fails(async_client: AsyncClient, auth_headers: dict, test_server):
    """Test that creating a peer without any IP address fails with 422."""
    # Arrange - no IPv4 or IPv6
    peer_data = {
        "name": "NoPeer",
        "server_id": test_server.id,
        "public_key": "test_public_key_base64_encoded_32_chars==",
        "allowed_ips": "0.0.0.0/0"
    }
    
    # Act
    response = await async_client.post(
        "/api/v1/peers/",
        json=peer_data,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "at least one" in str(data).lower() or "required" in str(data).lower()


# Fixtures would be defined in conftest.py
# These are placeholder signatures showing what fixtures we need
pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    pass


pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for API requests."""
    pass


pytest.fixture
async def test_server(db: AsyncSession):
    """Create a test server with IP 10.8.0.1/24."""
    pass


pytest.fixture
async def test_server2(db: AsyncSession):
    """Create a second test server for migration tests."""
    pass


pytest.fixture
async def test_peer(db: AsyncSession, test_server):
    """Create a test peer on test_server."""
    pass
