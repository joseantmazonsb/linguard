"""
Unit tests for IP validation utilities.

Tests cover all validation functions in app/utils/ip_validation.py
"""

from app.utils.ip_validation import (
    validate_ipv4_cidr,
    validate_ipv6_cidr,
    validate_dns_ip,
    is_ip_in_subnet,
    normalize_ip_cidr,
    check_server_ip_subnet_conflicts,
)


class TestValidateIPv4CIDR:
    """Test validate_ipv4_cidr function."""

    def test_valid_ipv4_cidr(self):
        """Test valid IPv4 CIDR."""
        is_valid, error = validate_ipv4_cidr("192.168.1.0/24")
        assert is_valid is True
        assert error is None

    def test_valid_ipv4_cidr_32(self):
        """Test valid IPv4 CIDR with /32."""
        is_valid, error = validate_ipv4_cidr("192.168.1.1/32")
        assert is_valid is True
        assert error is None

    def test_invalid_ipv4_cidr_empty(self):
        """Test empty string returns valid with no error."""
        is_valid, error = validate_ipv4_cidr("")
        assert is_valid is True
        assert error is None

    def test_invalid_ipv4_cidr_no_cidr(self):
        """Test IPv4 without CIDR fails."""
        is_valid, error = validate_ipv4_cidr("192.168.1.1")
        assert is_valid is False
        assert "CIDR notation" in error

    def test_invalid_ipv4_cidr_invalid_format(self):
        """Test invalid IPv4 CIDR format fails."""
        is_valid, error = validate_ipv4_cidr("999.999.999.999/24")
        assert is_valid is False
        assert "Invalid IPv4 CIDR" in error

    def test_invalid_ipv4_cidr_malformed(self):
        """Test malformed IPv4 CIDR fails."""
        is_valid, error = validate_ipv4_cidr("192.168.1/24")
        assert is_valid is False
        assert "Invalid IPv4 CIDR" in error


class TestValidateIPv6CIDR:
    """Test validate_ipv6_cidr function."""

    def test_valid_ipv6_cidr(self):
        """Test valid IPv6 CIDR."""
        is_valid, error = validate_ipv6_cidr("2001:db8::/32")
        assert is_valid is True
        assert error is None

    def test_valid_ipv6_cidr_full(self):
        """Test valid full IPv6 CIDR."""
        is_valid, error = validate_ipv6_cidr("2001:0db8:0000:0000:0000:0000:0000:0001/64")
        assert is_valid is True
        assert error is None

    def test_valid_ipv6_cidr_compressed(self):
        """Test valid compressed IPv6 CIDR."""
        is_valid, error = validate_ipv6_cidr("fe80::1/64")
        assert is_valid is True
        assert error is None

    def test_invalid_ipv6_cidr_empty(self):
        """Test empty string returns valid with no error."""
        is_valid, error = validate_ipv6_cidr("")
        assert is_valid is True
        assert error is None

    def test_invalid_ipv6_cidr_no_cidr(self):
        """Test IPv6 without CIDR fails."""
        is_valid, error = validate_ipv6_cidr("2001:db8::1")
        assert is_valid is False
        assert "CIDR notation" in error

    def test_invalid_ipv6_cidr_invalid_format(self):
        """Test invalid IPv6 CIDR format fails."""
        is_valid, error = validate_ipv6_cidr("gggg::/32")
        assert is_valid is False
        assert "Invalid IPv6 CIDR" in error


class TestValidateDNSIP:
    """Test validate_dns_ip function."""

    def test_valid_dns_ipv4(self):
        """Test valid DNS IPv4 address."""
        is_valid, error = validate_dns_ip("192.168.1.1")
        assert is_valid is True
        assert error is None

    def test_valid_dns_ipv6(self):
        """Test valid DNS IPv6 address."""
        is_valid, error = validate_dns_ip("2001:db8::1")
        assert is_valid is True
        assert error is None

    def test_valid_dns_ipv6_compressed(self):
        """Test valid compressed DNS IPv6 address."""
        is_valid, error = validate_dns_ip("fe80::1")
        assert is_valid is True
        assert error is None

    def test_valid_dns_ipv4_loopback(self):
        """Test valid DNS IPv4 loopback."""
        is_valid, error = validate_dns_ip("127.0.0.1")
        assert is_valid is True
        assert error is None

    def test_valid_dns_ipv6_loopback(self):
        """Test valid DNS IPv6 loopback."""
        is_valid, error = validate_dns_ip("::1")
        assert is_valid is True
        assert error is None

    def test_invalid_dns_ip_empty(self):
        """Test empty string returns valid with no error."""
        is_valid, error = validate_dns_ip("")
        assert is_valid is True
        assert error is None

    def test_invalid_dns_ip_with_cidr(self):
        """Test DNS IP with CIDR fails."""
        is_valid, error = validate_dns_ip("192.168.1.1/24")
        assert is_valid is False
        assert "without CIDR" in error

    def test_invalid_dns_ip_invalid_format(self):
        """Test invalid DNS IP format fails."""
        is_valid, error = validate_dns_ip("invalid-ip")
        assert is_valid is False
        assert "Invalid IP address" in error


class TestIsIPInSubnet:
    """Test is_ip_in_subnet function."""

    def test_peer_in_subnet_same_network(self):
        """Test peer IP within same subnet."""
        is_valid, error = is_ip_in_subnet("10.0.0.5/24", "10.0.0.1/24")
        assert is_valid is True
        assert error is None

    def test_peer_in_subnet_different_network(self):
        """Test peer IP outside subnet fails."""
        is_valid, error = is_ip_in_subnet("192.168.1.5/24", "10.0.0.1/24")
        assert is_valid is False
        assert "not within server subnet" in error

    def test_peer_in_subnet_larger_network(self):
        """Test peer IP within larger subnet."""
        is_valid, error = is_ip_in_subnet("10.0.0.5/24", "10.0.0.0/16")
        assert is_valid is True
        assert error is None

    def test_empty_peer_ip(self):
        """Test empty peer IP returns valid."""
        is_valid, error = is_ip_in_subnet("", "10.0.0.1/24")
        assert is_valid is True
        assert error is None

    def test_empty_server_ip(self):
        """Test empty server IP returns valid."""
        is_valid, error = is_ip_in_subnet("10.0.0.5/24", "")
        assert is_valid is True
        assert error is None

    def test_invalid_format(self):
        """Test invalid IP format fails."""
        is_valid, error = is_ip_in_subnet("invalid", "10.0.0.1/24")
        assert is_valid is False
        assert "Error validating" in error

    def test_exact_match_allowed(self):
        """Test exact IP match is allowed."""
        is_valid, error = is_ip_in_subnet("10.0.0.1/24", "10.0.0.1/24")
        assert is_valid is True
        assert error is None


class TestNormalizeIPCIDR:
    """Test normalize_ip_cidr function."""

    def test_normalize_valid_ipv4(self):
        """Test normalize valid IPv4 CIDR."""
        result = normalize_ip_cidr("192.168.1.0/24")
        assert result == "192.168.1.0/24"

    def test_normalize_valid_ipv6(self):
        """Test normalize valid IPv6 CIDR."""
        result = normalize_ip_cidr("2001:db8::/32")
        assert result == "2001:db8::/32"

    def test_normalize_ipv4_expanded(self):
        """Test normalize IPv4 with leading zeros (should fail as ipaddress doesn't accept leading zeros)."""
        # ipaddress module doesn't accept leading zeros, so this should return None
        result = normalize_ip_cidr("192.168.001.000/24")
        assert result is None

    def test_normalize_ipv6_expanded(self):
        """Test normalize IPv6 with leading zeros (ipaddress does accept leading zeros)."""
        # ipaddress module DOES accept leading zeros for IPv6 and compresses them
        result = normalize_ip_cidr("2001:0db8:0000:0000:0000:0000:0000:0001/64")
        assert result == "2001:db8::/64"

    def test_normalize_empty(self):
        """Test normalize empty string returns None."""
        result = normalize_ip_cidr("")
        assert result is None

    def test_normalize_invalid_ipv4(self):
        """Test normalize invalid IPv4 returns None."""
        result = normalize_ip_cidr("999.999.999.999/24")
        assert result is None

    def test_normalize_invalid_ipv6(self):
        """Test normalize invalid IPv6 returns None."""
        result = normalize_ip_cidr("gggg::/32")
        assert result is None


class TestCheckServerIPSubnetConflicts:
    """Test check_server_ip_subnet_conflicts function."""

    def test_no_conflicts(self):
        """Test no conflicts between new and existing IPs."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "10.0.2.0/24",
            [("10.0.1.0/24", "server1"), ("192.168.1.0/24", "server2")]
        )
        assert is_valid is True
        assert error is None

    def test_conflict_new_in_existing_subnet(self):
        """Test conflict when new IP is in existing subnet."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "10.0.1.50/32",
            [("10.0.1.0/24", "server1")]
        )
        assert is_valid is False
        assert "conflicts with" in error

    def test_conflict_existing_in_new_subnet(self):
        """Test conflict when existing IP is in new subnet."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "10.0.0.0/24",
            [("10.0.0.50/32", "server1")]
        )
        assert is_valid is False
        assert "would contain" in error

    def test_empty_new_ip(self):
        """Test empty new IP returns valid."""
        is_valid, error = check_server_ip_subnet_conflicts("", [])
        assert is_valid is True
        assert error is None

    def test_empty_existing_ips(self):
        """Test empty existing IPs list returns valid."""
        is_valid, error = check_server_ip_subnet_conflicts("10.0.0.0/24", [])
        assert is_valid is True
        assert error is None

    def test_same_ip_allowed(self):
        """Test same IP is allowed (not a conflict)."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "10.0.1.0/24",
            [("10.0.1.0/24", "server1")]
        )
        assert is_valid is True
        assert error is None

    def test_invalid_format(self):
        """Test invalid IP format fails."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "invalid",
            [("10.0.1.0/24", "server1")]
        )
        assert is_valid is False
        assert "Error validating" in error

    def test_overlap_different_prefixes(self):
        """Test conflict with overlapping subnets."""
        is_valid, error = check_server_ip_subnet_conflicts(
            "10.0.0.0/16",
            [("10.0.50.0/24", "server1")]
        )
        assert is_valid is False
        assert "would contain" in error
