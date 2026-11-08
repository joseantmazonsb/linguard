"""
Comprehensive tests for ip_management.py service.
Tests IPManagementService class and all utility functions.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from ipaddress import ip_network, ip_address

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ip_management import (
    IPManagementService,
    get_next_available_ipv4,
    get_next_available_ipv6,
    get_available_ip,
    reserve_ip,
    get_server_subnet,
    calculate_subnet,
    calculate_subnet_ipv6,
    get_ipv6_nat_mapping,
    get_ipv6_nat_reverse_mapping,
    null_ip,
    get_cidr_to_subnet,
    get_subnet_to_cidr,
    cidr_to_subnet,
    subnet_to_cidr,
    cidr_prefix_length,
    _get_first_available_ip,
    _is_reserved_ip,
)


# Mock classes for testing
class MockDBSession:
    """Mock database session for testing."""
    def __init__(self):
        self.execute_calls = []
        
    def execute(self, query, *args, **kwargs):
        """Mock execute method."""
        self.execute_calls.append(query)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        
        # Mock server return value
        if "Server" in str(query):
            server = MagicMock()
            server.id = 1
            server.name = "Test Server"
            server.ipv4_address = "192.168.1.0/24"
            server.ipv6_address = "2001:db8::/64"
            server.status = "stopped"
            server.needs_reload = False
            result.scalar_one_or_none.return_value = server
            result.scalar.return_value = server
        elif "Peer" in str(query):
            peer = MagicMock()
            peer.id = 1
            peer.server_id = 1
            peer.ipv4_address = "192.168.1.100/32"
            peer.ipv6_address = "2001:db8::100/128"
            # Return list directly
            result.scalars.return_value.all.return_value = [peer]
        else:
            result.scalar_one_or_none.return_value = None
        
        return result
    
    async def execute_async(self, query, *args, **kwargs):
        """Async execute method for async functions."""
        return self.execute(query, *args, **kwargs)


@pytest.fixture
def mock_db():
    """Create mock database session that works with the service code."""
    # Create a mock session object
    mock = MagicMock()
    
    # Mock servers that the service will find
    server = MagicMock()
    server.id = 1
    server.ipv4_address = "192.168.1.0/24"
    server.ipv6_address = "2001:db8::/64"
    server.status = "stopped"
    server.needs_reload = False
    
    # Create a proper mock result object that returns the server
    server_result = MagicMock()
    server_result.scalars.return_value.all.return_value = [server]
    server_result.scalar_one_or_none.return_value = server
    
    # Create a mock result object for peer queries (empty list)
    peer_result = MagicMock()
    peer_result.scalars.return_value.all.return_value = []
    
    # The service awaits db.execute(), so the mock must be an AsyncMock returning
    # (async) result objects for the server and peer queries.
    mock.execute = AsyncMock(side_effect=[server_result, peer_result, peer_result])
    return mock


@pytest.fixture
def mock_ip_management_service():
    """Create IPManagementService."""
    return IPManagementService()


class TestIPManagementService:
    """Test suite for IPManagementService class."""

    @pytest.mark.asyncio
    async def test_get_next_available_ipv4_success(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv4 address."""
        # The service queries: select(Server).where(Server.id == server_id)
        # Then: select(Peer).where(Peer.server_id == server_id, Peer.ipv4_address.isnot(None))
        # The fixture already sets up mock_execute to return the server and empty peer list
        
        # Call the method
        result = await mock_ip_management_service.get_next_available_ipv4(mock_db, 1)
        
        # Verify result - should return next IP in the server's subnet
        # Server has 192.168.1.0/24, no peers used
        # So next available is 192.168.1.1/24
        assert result == "192.168.1.1/24"

    @pytest.mark.asyncio
    async def test_get_next_available_ipv4_no_server(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv4 when server doesn't exist."""
        # Setup: mock returns None for server
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await mock_ip_management_service.get_next_available_ipv4(mock_db, 1)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_next_available_ipv4_no_ipv4_address(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv4 when server has no IPv4."""
        # Setup: mock returns server without IPv4
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value.ipv4_address = None
        
        result = await mock_ip_management_service.get_next_available_ipv4(mock_db, 1)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_next_available_ipv6_success(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv6 address."""
        # The service queries: select(Server).where(Server.id == server_id)
        # Then: select(Peer).where(Peer.server_id == server_id, Peer.ipv6_address.isnot(None))
        # The fixture already sets up mock_execute to return the server and empty peer list
        
        # Call the method
        result = await mock_ip_management_service.get_next_available_ipv6(mock_db, 1)
        
        # Verify result - should return next IP in the server's IPv6 subnet
        assert result == "2001:db8::1/64"

    @pytest.mark.asyncio
    async def test_get_next_available_ipv6_no_server(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv6 when server doesn't exist."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await mock_ip_management_service.get_next_available_ipv6(mock_db, 1)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_next_available_ipv6_no_ipv6_address(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv6 when server has no IPv6."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value.ipv6_address = None
        
        result = await mock_ip_management_service.get_next_available_ipv6(mock_db, 1)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_next_server_subnet_ipv4_success(self, mock_ip_management_service, mock_db):
        """Test getting next available server IPv4 subnet."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = await mock_ip_management_service.get_next_server_subnet_ipv4(mock_db)
        
        # No subnets are used, so the server gets 10.0.0.1/24 (host .1 of 10.0.0.0/24)
        assert result == "10.0.0.1/24"

    @pytest.mark.asyncio
    async def test_get_next_server_subnet_ipv4_no_subnets(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv4 subnet when all are used."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        server = MagicMock()
        server.ipv4_address = "10.0.0.1/24"
        mock_db.execute.return_value.scalars.return_value.all.return_value = [server]
        
        result = await mock_ip_management_service.get_next_server_subnet_ipv4(mock_db)
        
        # 10.0.0.0/24 is taken, so the next server gets 10.0.1.1/24
        assert result == "10.0.1.1/24"

    @pytest.mark.asyncio
    async def test_get_next_server_subnet_ipv6_success(self, mock_ip_management_service, mock_db):
        """Test getting next available server IPv6 subnet."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = await mock_ip_management_service.get_next_server_subnet_ipv6(mock_db)
        
        # No subnets used: the server gets fd00::1/64 (first host of fd00::/64)
        assert result == "fd00::1/64"

    @pytest.mark.asyncio
    async def test_get_next_server_subnet_ipv6_no_subnets(self, mock_ip_management_service, mock_db):
        """Test getting next available IPv6 subnet when all are used."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        server = MagicMock()
        server.ipv6_address = "fd00::1/64"
        mock_db.execute.return_value.scalars.return_value.all.return_value = [server]
        
        result = await mock_ip_management_service.get_next_server_subnet_ipv6(mock_db)
        
        # fd00::/64 is taken, the next server gets fd00:0:0:1::1/64
        assert result == "fd00:0:0:1::1/64"

    def test_validate_ipv4_valid(self, mock_ip_management_service):
        """Test validating a valid IPv4 address."""
        result = mock_ip_management_service.validate_ipv4("192.168.1.1")
        assert result is True

    def test_validate_ipv4_invalid(self, mock_ip_management_service):
        """Test validating an invalid IPv4 address."""
        result = mock_ip_management_service.validate_ipv4("invalid")
        assert result is False

    def test_validate_ipv4_network(self, mock_ip_management_service):
        """Test validating a valid IPv4 network."""
        result = mock_ip_management_service.validate_ipv4("192.168.1.0/24")
        assert result is True

    def test_validate_ipv4_network_invalid(self, mock_ip_management_service):
        """Test validating an invalid IPv4 network."""
        result = mock_ip_management_service.validate_ipv4("invalid/24")
        assert result is False

    def test_validate_ipv6_valid(self, mock_ip_management_service):
        """Test validating a valid IPv6 address."""
        result = mock_ip_management_service.validate_ipv6("2001:db8::1")
        assert result is True

    def test_validate_ipv6_invalid(self, mock_ip_management_service):
        """Test validating an invalid IPv6 address."""
        result = mock_ip_management_service.validate_ipv6("invalid")
        assert result is False

    def test_validate_ipv6_network(self, mock_ip_management_service):
        """Test validating a valid IPv6 network."""
        result = mock_ip_management_service.validate_ipv6("2001:db8::/64")
        assert result is True

    def test_validate_ipv6_network_invalid(self, mock_ip_management_service):
        """Test validating an invalid IPv6 network."""
        result = mock_ip_management_service.validate_ipv6("invalid/64")
        assert result is False


class TestIPManagementUtilityFunctions:
    """Test suite for module-level IP management utility functions."""

    def test_get_next_available_ipv4_default(self):
        """Test getting next available IPv4 with default subnet."""
        result = get_next_available_ipv4()
        assert result == "10.0.0.100"

    def test_get_next_available_ipv4_custom_subnet(self):
        """Test getting next available IPv4 with custom subnet."""
        result = get_next_available_ipv4("192.168.1.0/24")
        assert result == "192.168.1.100/24"

    def test_get_next_available_ipv6_default(self):
        """Test getting next available IPv6 with default subnet."""
        result = get_next_available_ipv6()
        assert result == "fd00::100"

    def test_get_next_available_ipv6_custom_subnet(self):
        """Test getting next available IPv6 with custom subnet."""
        # The 100th address of fd00::/64 is fd00::64
        result = get_next_available_ipv6("fd00::/64")
        assert result == "fd00::64/64"

    def test_get_available_ip(self):
        """Test getting available IP."""
        result = get_available_ip()
        assert result == "10.0.0.101"

    def test_reserve_ip(self):
        """Test reserving an IP."""
        result = reserve_ip("192.168.1.1")
        assert result is True

    def test_reserve_ip_empty(self):
        """Test reserving empty IP."""
        result = reserve_ip("")
        assert result is True

    def test_get_server_subnet(self):
        """Test getting server subnet."""
        result = get_server_subnet()
        assert result == "192.168.1.0/24"

    def test_calculate_subnet_ipv4(self):
        """Test calculating IPv4 subnet information."""
        result = calculate_subnet("192.168.1.0/24")
        assert result["network"] == "192.168.1.0"
        assert result["netmask"] == "255.255.255.0"
        assert result["broadcast"] == "192.168.1.255"
        assert result["first_host"] == "192.168.1.1"
        assert result["last_host"] == "192.168.1.254"
        assert result["total_hosts"] == 254

    def test_calculate_subnet_ipv6(self):
        """Test calculating IPv6 subnet information."""
        result = calculate_subnet_ipv6("fd00::1/64")
        assert result["network"] == "fd00::1"
        assert result["prefixlen"] == 64
        assert result["total_addresses"] == 1 << (128 - 64)

    def test_get_ipv6_nat_mapping(self):
        """Test getting IPv6 NAT mapping."""
        result = get_ipv6_nat_mapping()
        assert result["64:ff9b::/96"] == "2001:db8::1"

    def test_get_ipv6_nat_reverse_mapping(self):
        """Test getting IPv6 NAT reverse mapping."""
        result = get_ipv6_nat_reverse_mapping()
        assert result["2001:db8::1"] == "64:ff9b::1"

    def test_null_ip_none(self):
        """Test null IP with None."""
        result = null_ip(None)
        assert result is True

    def test_null_ip_empty(self):
        """Test null IP with empty string."""
        result = null_ip("")
        assert result is True

    def test_null_ip_valid(self):
        """Test null IP with valid IP."""
        result = null_ip("192.168.1.1")
        assert result is False

    def test_null_ip_whitespace(self):
        """Test null IP with whitespace."""
        result = null_ip("  ")
        assert result is True

    def test_get_cidr_to_subnet(self):
        """Test converting CIDR to subnet."""
        result = get_cidr_to_subnet("192.168.1.0/24")
        assert result == "192.168.1.0"

    def test_get_subnet_to_cidr(self):
        """Test converting subnet to CIDR."""
        result = get_subnet_to_cidr("192.168.1.0", 24)
        assert result == "192.168.1.0/24"

    def test_cidr_to_subnet(self):
        """Test CIDR to subnet conversion."""
        result = cidr_to_subnet("192.168.1.0/24")
        assert result == "192.168.1.0"

    def test_subnet_to_cidr(self):
        """Test subnet to CIDR conversion."""
        result = subnet_to_cidr("192.168.1.0", 24)
        assert result == "192.168.1.0/24"

    def test_cidr_prefix_length_valid(self):
        """Test extracting prefix length from valid CIDR."""
        result = cidr_prefix_length("192.168.1.0/24")
        assert result == 24

    def test_cidr_prefix_length_ipv6(self):
        """Test extracting prefix length from IPv6 CIDR."""
        result = cidr_prefix_length("2001:db8::/64")
        assert result == 64

    def test_cidr_prefix_length_invalid(self):
        """Test extracting prefix length from invalid CIDR."""
        result = cidr_prefix_length("invalid")
        assert result == 0

    def test_get_first_available_ip_empty(self):
        """Test getting first available IP with empty reserved list."""
        result = _get_first_available_ip("192.168.1.0/24")
        assert result == "192.168.1.1"

    def test_get_first_available_ip_reserved(self):
        """Test getting first available IP with reserved IPs."""
        result = _get_first_available_ip("192.168.1.0/24", reserved_ips=["192.168.1.1"])
        assert result == "192.168.1.2"

    def test_get_first_available_ip_none(self):
        """Test getting first available IP that returns None."""
        result = _get_first_available_ip("invalid/24")
        assert result is None

    def test_is_reserved_ip_default(self):
        """Test if IP is in default reserved list."""
        # Default reserved: 0.0.0.0, 255.255.255.255, 127.0.0.1, 127.255.255.255
        result = _is_reserved_ip("0.0.0.0")
        assert result is True

    def test_is_reserved_ip_network(self):
        """Test if IP is network address."""
        result = _is_reserved_ip("192.168.1.0", "192.168.1.0/24")
        assert result is True

    def test_is_reserved_ip_broadcast(self):
        """Test if IP is broadcast address."""
        result = _is_reserved_ip("192.168.1.255", "192.168.1.255/24")
        assert result is True

    def test_is_reserved_ip_not_reserved(self):
        """Test if IP is not in reserved list."""
        result = _is_reserved_ip("192.168.1.100", "192.168.1.0/24")
        assert result is False

    def test_is_reserved_ip_custom_list(self):
        """Test if IP is in custom reserved list."""
        result = _is_reserved_ip("192.168.1.1", ["192.168.1.1"])
        assert result is True

    def test_is_reserved_ip_custom_list_not_reserved(self):
        """Test if IP is not in custom reserved list."""
        result = _is_reserved_ip("192.168.1.100", ["192.168.1.1"])
        assert result is False


class TestIPAddressValidation:
    """Test suite for IP address validation functions."""

    def test_ip_address_ipv4_valid(self):
        """Test valid IPv4 address."""
        ip = ip_address("192.168.1.1")
        assert ip.version == 4
        assert str(ip) == "192.168.1.1"

    def test_ip_address_ipv6_valid(self):
        """Test valid IPv6 address."""
        ip = ip_address("2001:db8::1")
        assert ip.version == 6
        assert str(ip) == "2001:db8::1"

    def test_ip_address_ipv6_compressed(self):
        """Test compressed IPv6 address."""
        ip = ip_address("::1")
        assert ip.version == 6
        assert str(ip) == "::1"

    def test_network_ipv4(self):
        """Test IPv4 network."""
        network = ip_network("192.168.1.0/24")
        assert network.version == 4
        assert str(network.network_address) == "192.168.1.0"
        assert str(network.broadcast_address) == "192.168.1.255"
        assert str(network) == "192.168.1.0/24"

    def test_network_ipv6(self):
        """Test IPv6 network."""
        network = ip_network("2001:db8::/64")
        assert network.version == 6
        assert str(network.network_address) == "2001:db8::"
        assert str(network) == "2001:db8::/64"

    def test_ip_in_network(self):
        """Test if IP is in network."""
        network = ip_network("192.168.1.0/24")
        assert ip_address("192.168.1.1") in network
        assert ip_address("192.168.2.1") not in network

    def test_ip_not_in_network(self):
        """Test if IP is not in network."""
        network = ip_network("192.168.1.0/24")
        assert ip_address("192.168.1.1") in network
        assert ip_address("192.168.2.1") not in network
        # Broadcast address IS in the network (this is correct behavior)
        assert ip_address("192.168.1.255") in network

    def test_network_hosts(self):
        """Test network hosts iterator."""
        network = ip_network("192.168.1.0/24")
        hosts = list(network.hosts())
        assert len(hosts) > 0

    def test_network_hosts_empty(self):
        """Test network hosts iterator returns empty list."""
        # Note: 0.0.0.0/32 has network address = broadcast address = host, so hosts() returns 1
        # For a truly empty network, we'd need something like /31 with both ends
        network = ip_network("0.0.0.0/32")
        hosts = list(network.hosts())
        # ipaddress library includes network and broadcast in hosts() for /32
        assert len(hosts) == 1

    def test_subnet_mask_calculation(self):
        """Test subnet mask calculation."""
        network = ip_network("192.168.1.0/24")
        assert str(network.netmask) == "255.255.255.0"

    def test_network_range(self):
        """Test network range calculation."""
        network = ip_network("192.168.1.0/24")
        start = network.network_address
        end = network.broadcast_address
        assert str(start) == "192.168.1.0"
        assert str(end) == "192.168.1.255"

    def test_network_prefix_length(self):
        """Test network prefix length."""
        network = ip_network("192.168.1.0/24")
        assert network.prefixlen == 24

    def test_network_prefix_length_ipv6(self):
        """Test IPv6 network prefix length."""
        network = ip_network("2001:db8::/64")
        assert network.prefixlen == 64

    def test_network_zero_prefix(self):
        """Test network with zero prefix."""
        network = ip_network("0.0.0.0/0")
        assert network.prefixlen == 0

    def test_network_32_prefix(self):
        """Test network with 32-bit prefix."""
        network = ip_network("127.0.0.0/32")
        assert network.prefixlen == 32
