"""
Unit tests for IP validation functions.

Tests cover:
- IPv4 CIDR validation
- IPv6 CIDR validation
- DNS IP validation
- IP subnet checks
"""

from unittest.mock import MagicMock, patch


class TestIPv4Validation:
    """Test IPv4 CIDR validation."""
    
    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR addresses."""
        from app.utils.ip_validation import validate_ipv4_cidr
        
        valid_cidrs = [
            "192.168.1.0/24",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.1.100/32",
        ]
        
        for cidr in valid_cidrs:
            result = validate_ipv4_cidr(cidr)
            assert result[0] is True
            assert result[1] is None
            
    def test_invalid_ipv4_cidr(self):
        """Test invalid IPv4 CIDR addresses."""
        from app.utils.ip_validation import validate_ipv4_cidr
        
        # /32 is valid for single host (e.g., specific IP address)
        # /128 is invalid for IPv4 (too specific)
        invalid_cidrs = [
            ("192.168.1.0/128", False),  # /128 invalid for IPv4
            ("not.valid", False),
            ("", False),
        ]
        
        for cidr, should_be_valid in invalid_cidrs:
            result = validate_ipv4_cidr(cidr)
            if should_be_valid:
                assert result[0] is True
            else:
                assert result[0] is False
                assert result[1] is not None


class TestIPv6Validation:
    """Test IPv6 CIDR validation."""
    
    def test_valid_ipv6_cidr(self):
        """Test valid IPv6 CIDR addresses."""
        from app.utils.ip_validation import validate_ipv6_cidr
        
        valid_cidrs = [
            "fe80::1/64",
            "2001:db8::1/64",
            "::1/128",
            "::/0",
            "fe80:0000:0000:0000:0000:0000:0000:0001/128",
        ]
        
        for cidr in valid_cidrs:
            result = validate_ipv6_cidr(cidr)
            assert result[0] is True
            assert result[1] is None
            
    def test_invalid_ipv6_cidr(self):
        """Test invalid IPv6 CIDR addresses."""
        from app.utils.ip_validation import validate_ipv6_cidr
        
        invalid_cidrs = [
            ("2001:db8:1:2:3:4:5:6:7/64", False),  # Too many groups
            ("2001:db8:::1/64", False),  # Double ::
            ("fe80::1::2/64", False),  # Double ::
            ("gggg::1/64", False),  # Invalid hex
            ("", False),
        ]
        
        for cidr, should_be_valid in invalid_cidrs:
            result = validate_ipv6_cidr(cidr)
            if should_be_valid:
                assert result[0] is True
            else:
                assert result[0] is False
                assert result[1] is not None


class TestDNSValidation:
    """Test DNS IP validation."""
    
    def test_valid_dns_ip(self):
        """Test valid DNS IP addresses."""
        from app.utils.ip_validation import validate_dns_ip
        
        valid_ips = [
            "8.8.8.8",
            "8.8.4.4",
            "1.1.1.1",
            "1.0.0.1",
            "208.67.222.222",
            "208.67.220.220",
            "fe80::1",
            "2001:db8::1",
        ]
        
        for ip in valid_ips:
            result = validate_dns_ip(ip)
            assert result[0] is True
            assert result[1] is None
            
    def test_invalid_dns_ip(self):
        """Test invalid DNS IP addresses."""
        from app.utils.ip_validation import validate_dns_ip
        
        invalid_ips = [
            ("not.an.ip", False),
            ("", False),
            ("192.168.1", False),  # Incomplete
        ]
        
        for ip, should_be_valid in invalid_ips:
            result = validate_dns_ip(ip)
            if should_be_valid:
                assert result[0] is True
            else:
                assert result[0] is False
                assert result[1] is not None


class TestIPInSubnet:
    """Test IP in subnet validation."""
    
    def test_ip_in_same_subnet(self):
        """Test IP in same subnet as server."""
        from app.utils.ip_validation import is_ip_in_subnet
        
        # Same subnet
        peer_ip, server_ip = "192.168.1.100", "192.168.1.1"
        result = is_ip_in_subnet(peer_ip, server_ip)
        
        assert result[0] is True
        
    def test_ip_different_subnet(self):
        """Test IP in different subnet from server."""
        from app.utils.ip_validation import is_ip_in_subnet
        
        # Different subnet
        peer_ip, server_ip = "192.168.2.100", "192.168.1.1"
        result = is_ip_in_subnet(peer_ip, server_ip)
        
        assert result[0] is False
        
    def test_null_peer_ip_in_any_subnet(self):
        """Test NULL peer IP matches any subnet."""
        from app.utils.ip_validation import is_ip_in_subnet
        
        # NULL peer IP should match any subnet
        peer_ip, server_ip = None, "192.168.1.1"
        result = is_ip_in_subnet(peer_ip, server_ip)
        
        assert result[0] is True
        
    def test_null_server_ip(self):
        """Test NULL server IP."""
        from app.utils.ip_validation import is_ip_in_subnet
        
        # NULL server IP
        peer_ip, server_ip = "192.168.1.100", None
        result = is_ip_in_subnet(peer_ip, server_ip)
        
        assert result[0] is False


class TestNormalizeCIDR:
    """Test CIDR normalization."""
    
    def test_normalize_ipv4_cidr(self):
        """Test IPv4 CIDR normalization."""
        from app.utils.ip_validation import normalize_ip_cidr
        
        # Normalize IPv4 CIDR
        normalized = normalize_ip_cidr("192.168.1.0/24")
        
        assert normalized is not None
        assert "/" in normalized
        assert normalized.startswith("192.168.1.")
        
    def test_normalize_ipv6_cidr(self):
        """Test IPv6 CIDR normalization."""
        from app.utils.ip_validation import normalize_ip_cidr
        
        # Normalize IPv6 CIDR
        normalized = normalize_ip_cidr("fe80::/64")
        
        assert normalized is not None
        assert "/" in normalized
        assert normalized.startswith("fe80::")
        
    def test_normalize_invalid_cidr(self):
        """Test invalid CIDR normalization."""
        from app.utils.ip_validation import normalize_ip_cidr
        
        # Normalize invalid CIDR
        normalized = normalize_ip_cidr("not.valid")
        
        assert normalized is None


class TestServerIPConflict:
    """Test server IP conflict detection."""
    
    def test_no_conflict_different_subnet(self):
        """Test no conflict when IPs are in different subnets."""
        from app.utils.ip_validation import check_server_ip_subnet_conflicts
        
        new_ip = "192.168.2.1"
        existing_ips = ["192.168.1.1", "192.168.1.2"]
        
        result = check_server_ip_subnet_conflicts(new_ip, existing_ips)
        
        assert result[0] is True  # No conflict
        assert result[1] is None
        
    def test_conflict_same_subnet(self):
        """Test conflict when IPs are in same subnet."""
        from app.utils.ip_validation import check_server_ip_subnet_conflicts
        
        new_ip = "192.168.1.1"
        existing_ips = ["192.168.1.1", "192.168.1.2"]
        
        result = check_server_ip_subnet_conflicts(new_ip, existing_ips)
        
        assert result[0] is False  # Conflict
        assert result[1] is not None
        
    def test_null_new_ip_no_conflict(self):
        """Test NULL new IP has no conflict."""
        from app.utils.ip_validation import check_server_ip_subnet_conflicts
        
        new_ip = None
        existing_ips = ["192.168.1.1", "192.168.1.2"]
        
        result = check_server_ip_subnet_conflicts(new_ip, existing_ips)
        
        assert result[0] is True  # No conflict
        assert result[1] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.utils.ip_validation", "--cov-report=term-missing"])
