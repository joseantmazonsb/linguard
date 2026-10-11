"""
Unit tests for IPv4 & IPv6 management.

Tests cover:
- IP validation
- IP management
- IPv6 NAT
- NULL IP handling
"""

from unittest.mock import MagicMock, patch


class TestIPValidation:
    """Test IP validation functions."""
    
    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR validation."""
        from app.utils.ip_validation import validate_ipv4_cidr
        
        # Valid IPv4 CIDR
        valid_cidrs = [
            ("192.168.1.0/24", (True, None)),
            ("10.0.0.0/8", (True, None)),
            ("172.16.0.0/12", (True, None)),
        ]
        
        for cidr, expected in valid_cidrs:
            result = validate_ipv4_cidr(cidr)
            assert result == expected
            
    def test_invalid_ipv4_cidr(self):
        """Test invalid IPv4 CIDR validation."""
        from app.utils.ip_validation import validate_ipv4_cidr
        
        # Invalid IPv4 CIDR
        invalid_cidrs = [
            ("192.168.1.0/32", (False, "Invalid CIDR")),
            ("192.168.1.0/128", (False, "Invalid CIDR")),
            ("not.valid", (False, "Invalid CIDR")),
        ]
        
        for cidr, expected in invalid_cidrs:
            result = validate_ipv4_cidr(cidr)
            assert result == expected


class TestIPManagement:
    """Test IP management functions."""
    
    @patch('app.services.ip_management.subprocess')
    def test_get_available_ipv4(self, mock_subprocess):
        """Test getting available IPv4 addresses."""
        from app.services.ip_management import get_next_available_ipv4
        
        # Setup mock
        mock_subprocess.check_output.return_value = b"192.168.1.1 192.168.1.2\n"
        
        # Mock the database query
        with patch('app.services.ip_management.db') as mock_db:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = "192.168.1.3"
            mock_db.execute.return_value = mock_result
            
            available_ip = get_next_available_ipv4("192.168.1.0/24")
            
            assert available_ip is not None
            
    @patch('app.services.ip_management.subprocess')
    def test_get_available_ipv6(self, mock_subprocess):
        """Test getting available IPv6 addresses."""
        from app.services.ip_management import get_next_available_ipv6
        
        # Setup mock
        mock_subprocess.check_output.return_value = b"fe80::1 fe80::2\n"
        
        # Mock the database query
        with patch('app.services.ip_management.db') as mock_db:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = "fe80::3"
            mock_db.execute.return_value = mock_result
            
            available_ip = get_next_available_ipv6("fe80::/64")
            
            assert available_ip is not None
            
    def test_server_ip_never_available(self):
        """Test that server IP is never returned as available."""
        from app.services.ip_management import _is_ip_available
        
        server_ip = "192.168.1.1"
        
        # Server IP should never be available
        assert _is_ip_available(server_ip, server_ip) is False
        
        # Different IP should be available
        assert _is_ip_available("192.168.1.2", server_ip) is True
        
    def test_subnet_calculation(self):
        """Test subnet calculation."""
        from app.services.ip_management import _get_subnet_addresses
        
        # Test /24 subnet
        subnet = "192.168.1.0/24"
        addresses = _get_subnet_addresses(subnet)
        
        assert len(addresses) == 254  # 256 - 2 (network + broadcast)
        assert "192.168.1.1" in addresses
        assert "192.168.1.254" in addresses
        
    def test_subnet_calculation_ipv6(self):
        """Test IPv6 subnet calculation."""
        from app.services.ip_management import _get_subnet_addresses
        
        # Test /64 subnet
        subnet = "fe80::/64"
        addresses = _get_subnet_addresses(subnet)
        
        assert len(addresses) > 0
        assert "::1" not in addresses  # Loopback not in subnet


class TestIPv6NAT:
    """Test IPv6 NAT functionality."""
    
    def test_ipv6_nat_mapping(self):
        """Test IPv6 to IPv4 NAT mapping."""
        from app.services.bounce_routing import _create_nat_mapping
        
        # Create NAT mapping
        nat_mapping = _create_nat_mapping("fe80::1", "192.168.1.100")
        
        assert nat_mapping is not None
        assert "fe80::1" in nat_mapping
        assert nat_mapping["fe80::1"] == "192.168.1.100"
        
    def test_ipv6_nat_reverse_mapping(self):
        """Test reverse IPv6 NAT mapping."""
        from app.services.bounce_routing import _get_ipv4_for_ipv6
        
        nat_mapping = {
            "fe80::1": "192.168.1.100",
            "fe80::2": "192.168.1.101",
        }
        
        # Get IPv4 for IPv6
        ipv4 = _get_ipv4_for_ipv6(nat_mapping, "fe80::1")
        
        assert ipv4 == "192.168.1.100"
        
    def test_ipv6_nat_not_found(self):
        """Test IPv6 NAT mapping not found."""
        from app.services.bounce_routing import _get_ipv4_for_ipv6
        
        nat_mapping = {
            "fe80::1": "192.168.1.100",
        }
        
        # Get IPv4 for non-existent IPv6
        ipv4 = _get_ipv4_for_ipv6(nat_mapping, "fe80::2")
        
        assert ipv4 is None


class TestNULLIPHandling:
    """Test NULL IP handling (when no IP assigned)."""
    
    def test_null_ip_detection(self):
        """Test detection of NULL IP."""
        from app.utils.ip_validation import is_null_ip
        
        # NULL IP detection
        null_ips = [
            None,
            "",
            "0.0.0.0",
            "::",
        ]
        
        for ip in null_ips:
            assert is_null_ip(ip) is True
            
    def test_valid_ip_not_null(self):
        """Test that valid IPs are not considered NULL."""
        from app.utils.ip_validation import is_null_ip
        
        # Valid IPs should not be NULL
        valid_ips = [
            "192.168.1.1",
            "fe80::1",
            "10.0.0.1",
        ]
        
        for ip in valid_ips:
            assert is_null_ip(ip) is False
            
    def test_null_ip_in_peer_validation(self):
        """Test NULL IP handling in peer validation."""
        from app.schemas.peer import PeerCreate
        
        # Create peer without IP
        peer_data = PeerCreate(
            name="TestPeer",
            public_key="test_public_key",
            private_key="test_private_key",
            ipv4_address=None,
            ipv6_address=None,
            preshared_key=None,
            allowed_ips="0.0.0.0/0",
        )
        
        assert peer_data.ipv4_address is None
        assert peer_data.ipv6_address is None
        
    def test_null_ip_matching(self):
        """Test NULL IP matching logic."""
        from app.utils.ip_validation import _match_null_ip
        
        # NULL IP should match NULL IP
        assert _match_null_ip(None, None) is True
        
        # NULL IP should match any IP
        assert _match_null_ip(None, "192.168.1.1") is True
        
        # Valid IP should not match NULL
        assert _match_null_ip("192.168.1.1", None) is False


class TestCIDRConversion:
    """Test CIDR notation conversion."""
    
    def test_cidr_to_subnet(self):
        """Test CIDR to subnet conversion."""
        from app.services.ip_management import cidr_to_subnet
        
        # IPv4 CIDR
        subnet = cidr_to_subnet("192.168.1.0/24")
        
        assert subnet.startswith("192.168.1.")
        
    def test_cidr_to_subnet_ipv6(self):
        """Test IPv6 CIDR to subnet conversion."""
        from app.services.ip_management import cidr_to_subnet
        
        # IPv6 CIDR
        subnet = cidr_to_subnet("fe80::/64")
        
        assert subnet.startswith("fe80::")
        
    def test_subnet_to_cidr(self):
        """Test subnet to CIDR conversion."""
        from app.services.ip_management import subnet_to_cidr
        
        # Test subnet to CIDR
        cidr = subnet_to_cidr("192.168.1.0", 24)
        
        assert cidr == "192.168.1.0/24"
        
    def test_cidr_prefix_length(self):
        """Test CIDR prefix length extraction."""
        from app.services.ip_management import cidr_prefix_length
        
        # Test IPv4 prefix
        prefix = cidr_prefix_length("192.168.1.0/24")
        assert prefix == 24
        
        # Test IPv6 prefix
        prefix = cidr_prefix_length("fe80::/64")
        assert prefix == 64


class TestIPAllocation:
    """Test IP allocation logic."""
    
    def test_first_available_ip(self):
        """Test getting first available IP in subnet."""
        from app.services.ip_management import _get_first_available_ip
        
        # Test subnet
        subnet = "192.168.1.0/24"
        
        # Should return first usable IP (usually .1)
        ip = _get_first_available_ip(subnet)
        
        assert ip is not None
        assert ip != "192.168.1.0"  # Network address not usable
        
    def test_reserve_network_broadcast(self):
        """Test that network and broadcast addresses are reserved."""
        from app.services.ip_management import _is_reserved_ip
        
        subnet = "192.168.1.0/24"
        
        # Network and broadcast should be reserved
        assert _is_reserved_ip("192.168.1.0", subnet) is True
        assert _is_reserved_ip("192.168.1.255", subnet) is True
        
    def test_loopback_reserved(self):
        """Test that loopback addresses are reserved."""
        from app.services.ip_management import _is_reserved_ip
        
        subnet = "192.168.1.0/24"
        
        # Loopback should be reserved
        assert _is_reserved_ip("127.0.0.1", subnet) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.ip_management", "--cov-report=term-missing"])
