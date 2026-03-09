"""
Unit tests for IP Management Service.

Tests the functionality of get_next_available_ipv4/ipv6 to ensure:
1. Server IP is never returned as available
2. Existing peer IPs are excluded
3. First free IP in subnet is correctly identified
"""

import pytest
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ip_management import IPManagementService
from app.models.server import Server
from app.models.peer import Peer


@pytest.fixture
def ip_management_service():
    """Create IPManagementService instance."""
    return IPManagementService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_next_available_ipv4_excludes_server_ip(ip_management_service, mock_db):
    """Test that the server IP is never returned as available."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv4_address="10.8.0.1/24",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    # Mock database query to return server
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    # Mock no existing peers
    peers_result = Mock()
    peers_result.scalars.return_value.all.return_value = []
    
    mock_db.execute.side_effect = [server_result, peers_result]
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv4(mock_db, 1)
    
    # Assert
    assert next_ip is not None
    assert next_ip != "10.8.0.1/24"  # Should NOT be server IP
    assert next_ip == "10.8.0.2/24"  # Should be first host after server


@pytest.mark.asyncio
async def test_get_next_available_ipv4_skips_used_ips(ip_management_service, mock_db):
    """Test that IPs used by peers are skipped."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv4_address="10.8.0.1/24",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    # Create mock peers using IPs .2, .3, .4
    peer1 = Mock(spec=Peer)
    peer1.ipv4_address = "10.8.0.2/32"
    
    peer2 = Mock(spec=Peer)
    peer2.ipv4_address = "10.8.0.3/32"
    
    peer3 = Mock(spec=Peer)
    peer3.ipv4_address = "10.8.0.4/32"
    
    # Mock database queries
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    peers_result = Mock()
    peers_result.scalars.return_value.all.return_value = [peer1, peer2, peer3]
    
    mock_db.execute.side_effect = [server_result, peers_result]
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv4(mock_db, 1)
    
    # Assert
    assert next_ip == "10.8.0.5/24"  # Should skip .1 (server), .2, .3, .4 (peers)


@pytest.mark.asyncio
async def test_get_next_available_ipv4_handles_null_peers(ip_management_service, mock_db):
    """Test that peers with NULL IPv4 addresses are handled correctly."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv4_address="10.8.0.1/24",
        ipv6_address="fd00::1/64",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    # Create peer with IPv4
    peer1 = Mock(spec=Peer)
    peer1.ipv4_address = "10.8.0.2/32"
    
    # Create peer with only IPv6 (NULL IPv4)
    peer2 = Mock(spec=Peer)
    peer2.ipv4_address = None
    
    # Mock database queries
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    peers_result = Mock()
    peers_result.scalars.return_value.all.return_value = [peer1, peer2]
    
    mock_db.execute.side_effect = [server_result, peers_result]
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv4(mock_db, 1)
    
    # Assert
    assert next_ip == "10.8.0.3/24"  # Should only skip .1 (server) and .2 (peer1)


@pytest.mark.asyncio
async def test_get_next_available_ipv6_excludes_server_ip(ip_management_service, mock_db):
    """Test that the server IPv6 is never returned as available."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv6_address="fd00::1/64",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    # Mock database query to return server
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    # Mock no existing peers
    peers_result = Mock()
    peers_result.scalars.return_value.all.return_value = []
    
    mock_db.execute.side_effect = [server_result, peers_result]
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv6(mock_db, 1)
    
    # Assert
    assert next_ip is not None
    assert next_ip != "fd00::1/64"  # Should NOT be server IP
    assert next_ip == "fd00::2/64"  # Should be first host after server


@pytest.mark.asyncio
async def test_get_next_available_ipv4_returns_none_when_no_server(ip_management_service, mock_db):
    """Test that None is returned when server doesn't exist."""
    # Arrange
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = None
    
    mock_db.execute.return_value = server_result
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv4(mock_db, 999)
    
    # Assert
    assert next_ip is None


@pytest.mark.asyncio
async def test_get_next_available_ipv4_returns_none_when_server_has_no_ipv4(ip_management_service, mock_db):
    """Test that None is returned when server has no IPv4 address."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv4_address=None,  # No IPv4
        ipv6_address="fd00::1/64",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    mock_db.execute.return_value = server_result
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv4(mock_db, 1)
    
    # Assert
    assert next_ip is None


@pytest.mark.asyncio
async def test_get_next_available_ipv6_handles_null_peers(ip_management_service, mock_db):
    """Test that peers with NULL IPv6 addresses are handled correctly."""
    # Arrange
    server = Server(
        id=1,
        name="Test Server",
        interface="wg0",
        listen_port=51820,
        ipv4_address="10.8.0.1/24",
        ipv6_address="fd00::1/64",
        private_key="test_key",
        public_key="test_pub_key",
        enabled=True
    )
    
    # Create peer with IPv6
    peer1 = Mock(spec=Peer)
    peer1.ipv6_address = "fd00::2/128"
    
    # Create peer with only IPv4 (NULL IPv6)
    peer2 = Mock(spec=Peer)
    peer2.ipv6_address = None
    
    # Mock database queries
    server_result = Mock()
    server_result.scalar_one_or_none.return_value = server
    
    peers_result = Mock()
    peers_result.scalars.return_value.all.return_value = [peer1, peer2]
    
    mock_db.execute.side_effect = [server_result, peers_result]
    
    # Act
    next_ip = await ip_management_service.get_next_available_ipv6(mock_db, 1)
    
    # Assert
    assert next_ip == "fd00::3/64"  # Should only skip ::1 (server) and ::2 (peer1)


def test_validate_ipv4_valid(ip_management_service):
    """Test IPv4 validation with valid address."""
    assert ip_management_service.validate_ipv4("10.8.0.1/24") is True
    assert ip_management_service.validate_ipv4("192.168.1.1/32") is True


def test_validate_ipv4_invalid(ip_management_service):
    """Test IPv4 validation with invalid address."""
    assert ip_management_service.validate_ipv4("invalid") is False
    assert ip_management_service.validate_ipv4("999.999.999.999/24") is False


def test_validate_ipv6_valid(ip_management_service):
    """Test IPv6 validation with valid address."""
    assert ip_management_service.validate_ipv6("fd00::1/64") is True
    assert ip_management_service.validate_ipv6("2001:db8::1/128") is True


def test_validate_ipv6_invalid(ip_management_service):
    """Test IPv6 validation with invalid address."""
    assert ip_management_service.validate_ipv6("invalid") is False
    assert ip_management_service.validate_ipv6("gggg::1/64") is False
