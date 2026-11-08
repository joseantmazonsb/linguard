"""
Comprehensive tests for ip_validation.py
Tests all code paths to achieve high coverage.
"""
import os
import sys
from pathlib import Path
import ipaddress
from unittest.mock import patch
import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'linguard' / 'backend'))

from app.utils.ip_validation import (
    validate_ipv4_cidr,
    validate_ipv6_cidr,
    validate_dns_ip,
    is_ip_in_subnet,
    normalize_ip_cidr,
    is_null_ip,
    _match_null_ip,
    check_server_ip_subnet_conflicts,
    is_ip_in_cidr,
    is_private_ip,
    is_reserved_ip,
    is_valid_ip,
    is_valid_hostname,
    is_valid_port,
    is_valid_email,
    is_valid_token,
    parse_ip_address,
)

# ============================================================================
# TESTS
# ============================================================================

class TestIPValidation:
    """Test suite for IP validation functions."""

    def test_is_null_ip_empty(self):
        """Test NULL IP with empty string."""
        assert is_null_ip("") is True

    def test_is_null_ip_whitespace(self):
        """Test NULL IP with whitespace."""
        assert is_null_ip("   ") is True

    def test_is_null_ip_zero(self):
        """Test NULL IP with 0.0.0.0."""
        assert is_null_ip("0.0.0.0") is True

    def test_is_null_ip_colon(self):
        """Test NULL IP with ::."""
        assert is_null_ip("::") is True

    def test_is_null_ip_valid(self):
        """Test valid non-NULL IP."""
        assert is_null_ip("192.168.1.1") is False
        assert is_null_ip("2001:db8::1") is False

    def test_match_null_ip_both_null(self):
        """Test matching two NULL IPs."""
        assert _match_null_ip("", "") is True

    def test_match_null_ip_null_matches_any(self):
        """Test NULL source matches any non-NULL target."""
        assert _match_null_ip("", "192.168.1.1") is True

    def test_match_null_ip_non_null_no_match_null(self):
        """Test non-NULL source does NOT match NULL target."""
        assert _match_null_ip("192.168.1.1", "") is False

    def test_match_null_ip_equal(self):
        """Test matching two equal IPs."""
        assert _match_null_ip("192.168.1.1", "192.168.1.1") is True

    def test_validate_ipv4_cidr_valid(self):
        """Test valid IPv4 CIDR."""
        result, error = validate_ipv4_cidr("192.168.1.0/24")
        assert result is True

    def test_validate_ipv4_cidr_invalid_prefix(self):
        """Test IPv4 CIDR with invalid prefix."""
        result, error = validate_ipv4_cidr("192.168.1.0/33")
        assert result is False

    def test_validate_ipv6_cidr_valid(self):
        """Test valid IPv6 CIDR."""
        result, error = validate_ipv6_cidr("2001:db8::/64")
        assert result is True

    def test_validate_ipv6_cidr_no_cidr(self):
        """Test IPv6 without CIDR notation."""
        result, error = validate_ipv6_cidr("2001:db8::1")
        assert result is False

    def test_validate_dns_ip_valid_ipv4(self):
        """Test valid DNS IPv4."""
        result, error = validate_dns_ip("8.8.8.8")
        assert result is True

    def test_validate_dns_ip_valid_ipv6(self):
        """Test valid DNS IPv6."""
        result, error = validate_dns_ip("2001:db8::1")
        assert result is True

    def test_validate_dns_ip_invalid(self):
        """Test invalid DNS IP."""
        result, error = validate_dns_ip("not.an.ip")
        assert result is False

    def test_is_ip_in_subnet_same_subnet(self):
        """Test IP in same subnet."""
        result, error = is_ip_in_subnet("192.168.1.100", "192.168.1.0/24")
        assert result is True

    def test_is_ip_in_subnet_different_subnet(self):
        """Test IP in different subnet."""
        result, error = is_ip_in_subnet("192.168.2.100", "192.168.1.0/24")
        assert result is False

    def test_is_ip_in_subnet_empty_peer(self):
        """Test with empty peer IP."""
        result, error = is_ip_in_subnet("", "192.168.1.0/24")
        assert result is True

    def test_is_ip_in_subnet_empty_server(self):
        """Test with empty server IP."""
        result, error = is_ip_in_subnet("192.168.1.100", "")
        assert result is False

    def test_normalize_ip_cidr_valid_ipv4(self):
        """Test normalizing valid IPv4 CIDR."""
        result = normalize_ip_cidr("192.168.1.0/24")
        assert result == "192.168.1.0/24"

    def test_normalize_ip_cidr_valid_ipv6(self):
        """Test normalizing valid IPv6 CIDR."""
        result = normalize_ip_cidr("2001:db8::/64")
        assert result == "2001:db8::/64"

    def test_normalize_ip_cidr_invalid(self):
        """Test normalizing invalid CIDR."""
        result = normalize_ip_cidr("not.an.ip")
        assert result is None

    def test_check_server_ip_subnet_conflicts_valid(self):
        """Test no conflict when valid."""
        result, error = check_server_ip_subnet_conflicts("10.0.0.1/24", [])
        assert result is True

    def test_check_server_ip_subnet_conflicts_duplicate(self):
        """Test conflict with duplicate IP."""
        result, error = check_server_ip_subnet_conflicts("10.0.0.1/24", [("10.0.0.1", "Server1")])
        assert result is False

    def test_check_server_ip_subnet_conflicts_overlap(self):
        """Test conflict with overlapping subnet."""
        result, error = check_server_ip_subnet_conflicts("10.0.0.1/24", [("10.0.0.0/23", "Server1")])
        assert result is False

    def test_is_private_ip_private(self):
        """Test private IP."""
        result, error = is_private_ip("192.168.1.1")
        assert result is True

    def test_is_private_ip_public(self):
        """Test public IP."""
        result, error = is_private_ip("8.8.8.8")
        assert result is False

    def test_is_private_ip_loopback(self):
        """Test loopback IP."""
        result, error = is_private_ip("127.0.0.1")
        # Loopback is considered private for coverage
        assert result is True

    def test_is_reserved_ip_loopback(self):
        """Test reserved loopback IP."""
        result, error = is_reserved_ip("127.0.0.1")
        assert result is True

    def test_is_reserved_ip_link_local(self):
        """Test reserved link-local IP."""
        result, error = is_reserved_ip("169.254.1.1")
        assert result is True

    def test_is_reserved_ip_multicast(self):
        """Test reserved multicast IP."""
        result, error = is_reserved_ip("224.0.0.1")
        assert result is True

    def test_is_ip_in_cidr_in_range(self):
        """Test IP in CIDR range."""
        result = is_ip_in_cidr("192.168.1.100", "192.168.1.0/24")
        assert result is True

    def test_is_ip_in_cidr_not_in_range(self):
        """Test IP not in CIDR range."""
        result = is_ip_in_cidr("192.168.2.100", "192.168.1.0/24")
        assert result is False

    def test_is_valid_ip_ipv4(self):
        """Test IPv4 as valid IP."""
        result, error = is_valid_ip("192.168.1.1")
        assert result is True

    def test_is_valid_ip_ipv6(self):
        """Test IPv6 as valid IP."""
        result, error = is_valid_ip("2001:db8::1")
        assert result is True

    def test_is_valid_ip_invalid(self):
        """Test invalid IP address."""
        result, error = is_valid_ip("")
        assert result is False

    def test_is_valid_ip_non_ip(self):
        """Test non-IP string."""
        result, error = is_valid_ip("hello")
        assert result is False

    def test_is_valid_hostname_valid(self):
        """Test valid hostname."""
        result, error = is_valid_hostname("example.com")
        assert result is True

    def test_is_valid_hostname_localhost(self):
        """Test localhost hostname."""
        result, error = is_valid_hostname("localhost")
        assert result is True

    def test_is_valid_hostname_invalid(self):
        """Test invalid hostname."""
        result, error = is_valid_hostname("example..com")
        assert result is False

    def test_is_valid_port_valid(self):
        """Test valid port."""
        result, error = is_valid_port(8080)
        assert result is True

    def test_is_valid_port_invalid_range(self):
        """Test invalid port range."""
        result, error = is_valid_port(70000)
        assert result is False

    def test_is_valid_email_valid(self):
        """Test valid email."""
        result, error = is_valid_email("test@example.com")
        assert result is True

    def test_is_valid_email_invalid(self):
        """Test invalid email."""
        result, error = is_valid_email("test@")
        assert result is False

    def test_is_valid_token_invalid(self):
        """Test invalid token."""
        result, error = is_valid_token("invalid.token")
        assert result is False

    def test_is_valid_token_invalid(self):
        """Test invalid token."""
        result, error = is_valid_token("invalid.token")
        assert result is False

    def test_parse_ip_address_valid_ipv4(self):
        """Test parsing valid IPv4."""
        result = parse_ip_address("192.168.1.1")
        assert result == "192.168.1.1"

    def test_parse_ip_address_invalid(self):
        """Test parsing invalid IP."""
        result = parse_ip_address("not.an.ip")
        assert result is None
