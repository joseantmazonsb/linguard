"""
Comprehensive tests for ip_validation.py.
Tests all code paths to achieve high coverage.
"""
import pytest
from app.utils.ip_validation import (
    validate_ipv4_cidr,
    validate_ipv6_cidr,
    validate_dns_ip,
    is_ip_in_subnet,
    normalize_ip_cidr,
    is_null_ip,
    _match_null_ip,
    check_server_ip_subnet_conflicts,
    is_valid_ip,
    is_valid_hostname,
    is_valid_port,
    is_valid_email,
    is_valid_token,
    is_private_ip,
    is_reserved_ip,
    is_ip_in_cidr,
)


def run_tests():
    """Run all test functions."""
    import pytest
    pytest.main([__file__, "-v", "--cov=app.utils.ip_validation", "--cov-report=term-missing"])


# ============================================================================
# VALIDATE IPv4 CIDR TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("192.168.1.0/24", True, None),
    ("10.0.0.0/8", True, None),
    ("172.16.0.0/12", True, None),
    ("255.255.255.255/32", True, None),
    ("192.168.1.1/32", True, None),
    ("10.0.0.1/32", True, None),
    ("", False, "IPv4 CIDR cannot be empty"),
    ("  ", False, "IPv4 CIDR cannot be empty"),
    ("192.168.1.0", False, "Invalid CIDR"),
    ("192.168.1", False, "Invalid CIDR"),
    ("invalid/cidr", False, "Invalid CIDR"),
    ("256.1.1.1/24", False, "Invalid CIDR"),
    ("192.168.1.0/0", False, "Invalid CIDR"),
    ("192.168.1.0/33", False, "Invalid CIDR"),
    ("192.168.1.0/40", False, "Invalid CIDR"),
])
def test_validate_ipv4_cidr(ip_str, expected, error_msg):
    """Test IPv4 CIDR validation."""
    result = validate_ipv4_cidr(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# VALIDATE IPv6 CIDR TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("fd00::/64", True, None),
    ("2001:db8::/32", True, None),
    ("fe80::/10", True, None),
    ("::/128", True, None),
    ("2001:0db8:0000:0000:0000:0000:0000:0001/128", True, None),
    ("::1/128", True, None),
    ("2001:0db8::1/128", True, None),
    ("", False, "IPv6 CIDR cannot be empty"),
    ("  ", False, "IPv6 CIDR cannot be empty"),
    ("fd00::1", False, "IPv6 address must include CIDR notation (e.g., fd00::1/64)"),
    ("fd00", False, "Invalid IPv6 CIDR format: At least 3 parts expected in 'fd00'"),
    ("invalid::/40", False, "Invalid IPv6 CIDR format: Only hex digits permitted in 'invalid' in 'invalid::'"),
    ("::1", False, "IPv6 address must include CIDR notation (e.g., fd00::1/64)"),
    ("2001:db8::1", False, "IPv6 address must include CIDR notation (e.g., fd00::1/64)"),
])
def test_validate_ipv6_cidr(ip_str, expected, error_msg):
    """Test IPv6 CIDR validation."""
    result = validate_ipv6_cidr(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# VALIDATE DNS IP TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("8.8.8.8", True, None),
    ("1.1.1.1", True, None),
    ("208.67.222.222", True, None),
    ("2001:4860:4860::8888", True, None),
    ("2606:4700:4700::1111", True, None),
    ("", False, "DNS IP address cannot be empty"),
    ("8.8.8.8/24", False, "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"),
    ("::/128", False, "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"),
])
def test_validate_dns_ip(ip_str, expected, error_msg):
    """Test DNS IP validation."""
    result = validate_dns_ip(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# NORMALIZE IP CIDR TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected", [
    ("192.168.1.0/24", "192.168.1.0/24"),
    ("10.0.0.0/8", "10.0.0.0/8"),
    ("172.16.0.0/12", "172.16.0.0/12"),
    ("fd00::/64", "fd00::/64"),
    ("2001:db8::/32", "2001:db8::/32"),
    ("", None),
    ("  ", None),
    ("invalid", None),
])
def test_normalize_ip_cidr(ip_str, expected):
    """Test IP CIDR normalization."""
    result = normalize_ip_cidr(ip_str)
    assert result == expected


# ============================================================================
# NULL IP TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected", [
    (None, True),
    ("", True),
    ("   ", True),
    ("0.0.0.0", True),
    ("::", True),
    ("192.168.1.1", False),
    ("10.0.0.1", False),
    ("2001:db8::1", False),
    ("fd00::1", False),
    ("  192.168.1.1  ", False),
])
def test_is_null_ip(ip_str, expected):
    """Test NULL IP detection."""
    result = is_null_ip(ip_str)
    assert result == expected


# ============================================================================
# IP MATCHING TESTS
# ============================================================================

@pytest.mark.parametrize("source_ip,target_ip,expected", [
    (None, None, True),
    ("", "", True),
    (None, "192.168.1.1", True),
    ("", "10.0.0.1", True),
    (None, "2001:db8::1", True),
    ("192.168.1.1", None, False),
    ("10.0.0.1", "", False),
    ("192.168.1.1", "192.168.1.1", True),
    ("10.0.0.1", "10.0.0.1", True),
    ("2001:db8::1", "2001:db8::1", True),
    ("192.168.1.1", "192.168.1.2", False),
    ("10.0.0.1", "10.0.0.2", False),
])
def test_match_null_ip(source_ip, target_ip, expected):
    """Test IP matching with NULL support."""
    result = _match_null_ip(source_ip, target_ip)
    assert result == expected


# ============================================================================
# ADDITIONAL TESTS FOR COVERAGE
# ============================================================================

@pytest.mark.parametrize("peer_ip,server_ip,expected,error_msg", [
    ("192.168.1.5", "192.168.1.1/24", True, None),
    ("192.168.1.200", "192.168.1.1/24", True, None),
    ("192.168.2.5", "192.168.1.1/24", False, "Peer IP 192.168.2.5 is not within server subnet 192.168.1.0/24"),
    ("192.168.1.1", "192.168.1.5/24", True, None),
    ("192.168.1.200", "192.168.1.5/24", True, None),
    ("192.168.2.5", "192.168.1.5/24", False, "Peer IP 192.168.2.5 is not within server subnet 192.168.1.0/24"),
    ("192.168.1.5", "192.168.1.1", True, None),
    ("192.168.2.5", "192.168.1.1", False, "Peer IP 192.168.2.5 is not in the same /24 subnet as server IP 192.168.1.1"),
    ("192.168.1.1", "192.168.1.5", True, None),
    ("192.168.2.1", "192.168.1.1", False, "Peer IP 192.168.2.1 is not in the same /24 subnet as server IP 192.168.1.1"),
    ("::1", "::1/128", True, None),
    ("::2", "::1/128", False, "Peer IP ::2 is not within server subnet ::1/128"),
    ("2001:db8::1", "2001:db8::1/128", True, None),
    ("2001:db8::2", "2001:db8::1/128", False, "Peer IP 2001:db8::2 is not within server subnet 2001:db8::1/128"),
    ("", None, True, None),
    (None, "192.168.1.1/24", True, None),
    ("", "192.168.1.1/24", True, None),
])
def test_is_ip_in_subnet(peer_ip, server_ip, expected, error_msg):
    """Test IP subnet membership check."""
    result = is_ip_in_subnet(peer_ip, server_ip)
    assert result == (expected, error_msg)


# ============================================================================
# SERVER IP CONFLICT CHECK TESTS
# ============================================================================

@pytest.mark.parametrize("new_server_ip,existing_server_ips,expected,error_msg", [
    ("192.168.1.1/24", [], True, None),
    ("192.168.1.1/24", None, True, None),
    ("192.168.1.1/24", "", True, None),
    ("192.168.1.1/24", ["None"], False, "Error validating subnet conflicts: 'None' does not appear to be an IPv4 or IPv6 network"),
    ("192.168.1.1/24", [("192.168.1.1/24", "existing-server")], False, "Server IP 192.168.1.1 is already in use"),
    ("192.168.1.1/24", ["192.168.1.1/24"], False, "Server IP 192.168.1.1 is already in use"),
    ("192.168.1.50/24", [("192.168.1.1/24", "existing-server")], False, "Server IP 192.168.1.50 conflicts with existing server 'existing-server' subnet 192.168.1.0/24"),
    ("192.168.1.0/24", [("192.168.1.50/24", "existing-server")], False, "Server IP 192.168.1.0 conflicts with existing server 'existing-server' subnet 192.168.1.0/24"),
    ("192.168.2.1/24", [("192.168.1.1/24", "existing-server")], True, None),
    ("10.0.0.1/24", [("192.168.1.1/24", "existing-server")], True, None),
    ("192.168.1.1/24", [("10.0.0.1/24", "existing-server")], True, None),
    ("192.168.1.1/24", [("10.0.0.1/24", "server1"), ("172.16.0.1/24", "server2")], True, None),
    ("", "192.168.1.1/24", False, "New server IP is required"),
    ("   ", "192.168.1.1/24", False, "New server IP is required"),
    ("192.168.1.1/24", ["invalid/24"], False, "Error validating subnet conflicts: 'invalid/24' does not appear to be an IPv4 or IPv6 network"),
])
def test_check_server_ip_subnet_conflicts(new_server_ip, existing_server_ips, expected, error_msg):
    """Test server IP subnet conflict detection."""
    result = check_server_ip_subnet_conflicts(new_server_ip, existing_server_ips)
    assert result == (expected, error_msg)


# ============================================================================
# VALID IP TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("192.168.1.1/24", True, None),
    ("10.0.0.0/8", True, None),
    ("192.168.1.1", True, None),
    ("10.0.0.1", True, None),
    ("2001:db8::1/64", True, None),
    ("fd00::/12", True, None),
    ("2001:db8::1", True, None),
    ("fd00::1", True, None),
    ("8.8.8.8", True, None),
    ("", False, "IP address cannot be empty"),
    ("  ", False, "IP address cannot be empty"),
    ("invalid", False, "Invalid IP address format"),
    ("256.1.1.1/24", False, "Invalid IP address format"),
])
def test_is_valid_ip(ip_str, expected, error_msg):
    """Test IP validation."""
    result = is_valid_ip(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL HOSTNAME TESTS
# ============================================================================

@pytest.mark.parametrize("hostname,expected,error_msg", [
    ("localhost", True, None),
    ("example.com", True, None),
    ("mail.example.com", True, None),
    ("www.test.org", True, None),
    ("server1.example.com", True, None),
    ("sub.domain.example.com", True, None),
    ("test123.example.com", True, None),
    ("my-server.example.com", True, None),
    ("sub-domain.example.com", True, None),
    ("", False, "Hostname cannot be empty"),
    ("   ", False, "Hostname cannot be empty"),
    ("a" * 254 + ".com", False, "Hostname too long (max 253 characters)"),
    (".example.com", False, "Invalid hostname: empty part"),
    ("example..com", False, "Invalid hostname: empty part"),
    ("example.-com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("example-.com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("very-long-subdomain-that-exceeds-63-characters.example.com", True, None),
    ("example@com", False, "Invalid hostname: hyphens not allowed at start/end"),
    # Additional tests for is_valid_hostname coverage
    ("test.example.com", True, None),
    ("a1.b2.example.com", True, None),
    ("-invalid.example.com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("invalid-.example.com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("123.example.com", True, None),
    ("example-123.com", True, None),
])
def test_is_valid_hostname(hostname, expected, error_msg):
    """Test hostname validation."""
    result = is_valid_hostname(hostname)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL EMAIL TESTS
# ============================================================================

@pytest.mark.parametrize("email,expected,error_msg", [
    ("user@example.com", True, None),
    ("user.name@example.com", True, None),
    ("user_name@example.com", True, None),
    ("user+tag@example.com", True, None),
    ("user123@example.com", True, None),
    ("user@subdomain.example.com", True, None),
    ("test.user@domain.co.uk", True, None),
    ("localhost", True, None),
    ("", False, "Email cannot be empty"),
    ("   ", False, "Email cannot be empty"),
    ("@example.com", False, "Invalid email format"),
    ("user@", False, "Invalid email format"),
    ("user@example", False, "Invalid email format"),
    ("user..name@example.com", False, "Invalid email: consecutive dots"),
    ("@.example.com", False, "Invalid email format"),
    ("user@example..com", False, "Invalid email: consecutive dots"),
    ("user@example", False, "Invalid email format"),
    # Additional tests for is_valid_email coverage
    ("user.name@example.co", True, None),
    ("user+tag123@example.com", True, None),
    ("user.name+tag@example.com", True, None),
    ("user_name+tag123@example.com", True, None),
    ("user@sub.example.com", True, None),
    ("user@sub.sub.example.com", True, None),
])
def test_is_valid_email(email, expected, error_msg):
    """Test email validation."""
    result = is_valid_email(email)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL TOKEN TESTS
# ============================================================================

@pytest.mark.parametrize("token,expected,error_msg", [
    ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c", False, "Invalid base64 encoding in token"),
    ("SGVsbG8gV29ybGQ=", False, "Invalid token format"),
    ("", False, "Token cannot be empty"),
    ("  ", False, "Token cannot be empty"),
    ("invalid", True, None),
    ("abc.def.ghi", False, "Invalid base64 encoding in token"),
])
def test_is_valid_token(token, expected, error_msg):
    """Test token validation."""
    result = is_valid_token(token)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL PRIVATE IP TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("192.168.1.1", True, None),
    ("10.0.0.1", True, None),
    ("172.16.0.1", True, None),
    ("172.31.255.255", True, None),
    ("0.0.0.0", True, None),
    ("127.0.0.1", True, None),
    ("::1", True, None),
    ("fe80::1", True, None),
    ("2001:db8::1", True, None),
    ("8.8.8.8", False, "Address 8.8.8.8 is a public IP"),
])
def test_is_private_ip(ip_str, expected, error_msg):
    """Test private IP validation."""
    result = is_private_ip(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL RESERVED IP TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,expected,error_msg", [
    ("127.0.0.1", True, None),
    ("::1", True, None),
    ("255.255.255.255", True, None),
    ("224.0.0.1", True, None),
    ("169.254.0.1", True, None),
    ("240.0.0.0", True, None),
    ("192.168.1.1", True, None),
    ("10.0.0.1", True, None),
    ("8.8.8.8", False, "Address 8.8.8.8 is not a reserved IP"),
    ("2001:db8::1", False, "Address 2001:db8::1 is not a reserved IP"),
])
def test_is_reserved_ip(ip_str, expected, error_msg):
    """Test reserved IP validation."""
    result = is_reserved_ip(ip_str)
    assert result == (expected, error_msg)


# ============================================================================
# ADDITIONAL IP IN CIDR TESTS
# ============================================================================

@pytest.mark.parametrize("ip_str,cidr_str,expected", [
    ("192.168.1.50", "192.168.1.0/24", True),
    ("192.168.1.1", "192.168.1.0/24", True),
    ("192.168.2.50", "192.168.1.0/24", False),
    ("192.168.1.50", "192.168.1.0/16", True),
    ("192.168.2.50", "192.168.1.0/16", True),
    ("192.168.1.50", "192.168.1.0/24", True),
    ("192.168.1.1", "192.168.1.0/24", True),
    ("192.168.2.50", "192.168.1.0/24", False),
    ("2001:db8::50", "2001:db8::/32", True),
    ("2001:db8::1", "2001:db8::/32", True),
    ("2001:db9::50", "2001:db8::/32", False),
    ("8.8.8.8", "8.8.8.0/24", True),
    ("8.8.8.1", "8.8.8.0/24", True),
    ("8.8.9.8", "8.8.8.0/24", False),
])
def test_is_ip_in_cidr(ip_str, cidr_str, expected):
    """Test IP in CIDR check."""
    result = is_ip_in_cidr(ip_str, cidr_str)
    assert result == expected


# ============================================================================
# VALID HOSTNAME TESTS
# ============================================================================

@pytest.mark.parametrize("hostname,expected,error_msg", [
    ("localhost", True, None),
    ("example.com", True, None),
    ("mail.example.com", True, None),
    ("www.test.org", True, None),
    ("server1.example.com", True, None),
    ("sub.domain.example.com", True, None),
    ("test123.example.com", True, None),
    ("my-server.example.com", True, None),
    ("sub-domain.example.com", True, None),
    ("", False, "Hostname cannot be empty"),
    ("   ", False, "Hostname cannot be empty"),
    ("a" * 254 + ".com", False, "Hostname too long (max 253 characters)"),
    (".example.com", False, "Invalid hostname: empty part"),
    ("example..com", False, "Invalid hostname: empty part"),
    ("example.-com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("example-.com", False, "Invalid hostname: hyphens not allowed at start/end"),
    ("very-long-subdomain-that-exceeds-63-characters.example.com", True, None),
    ("example@com", False, "Invalid hostname: hyphens not allowed at start/end"),
])
def test_is_valid_hostname(hostname, expected, error_msg):
    """Test hostname validation."""
    result = is_valid_hostname(hostname)
    assert result == (expected, error_msg)


# ============================================================================
# VALID PORT TESTS
# ============================================================================

@pytest.mark.parametrize("port,expected,error_msg", [
    (0, True, None),
    (1, True, None),
    (80, True, None),
    (443, True, None),
    (8080, True, None),
    (65535, True, None),
    (-1, False, "Port must be between 0 and 65535"),
    (65536, False, "Port must be between 0 and 65535"),
    ("80", False, "Port must be an integer"),
    (80.0, False, "Port must be an integer"),
    (True, False, "Port must be an integer"),
    (False, False, "Port must be an integer"),
])
def test_is_valid_port(port, expected, error_msg):
    """Test port validation."""
    result = is_valid_port(port)
    assert result == (expected, error_msg)


# ============================================================================
# VALID EMAIL TESTS
# ============================================================================

@pytest.mark.parametrize("email,expected,error_msg", [
    ("user@example.com", True, None),
    ("user.name@example.com", True, None),
    ("user_name@example.com", True, None),
    ("user+tag@example.com", True, None),
    ("user123@example.com", True, None),
    ("user@subdomain.example.com", True, None),
    ("test.user@domain.co.uk", True, None),
    ("localhost", True, None),
    ("", False, "Email cannot be empty"),
    ("   ", False, "Email cannot be empty"),
    ("@example.com", False, "Invalid email format"),
    ("user@", False, "Invalid email format"),
    ("user@example", False, "Invalid email format"),
    ("user..name@example.com", False, "Invalid email: consecutive dots"),
    ("@.example.com", False, "Invalid email format"),
    ("user@example..com", False, "Invalid email: consecutive dots"),
    ("user@example", False, "Invalid email format"),
])
def test_is_valid_email(email, expected, error_msg):
    """Test email validation."""
    result = is_valid_email(email)
    assert result == (expected, error_msg)


# ============================================================================
# VALID TOKEN TESTS
# ============================================================================

@pytest.mark.parametrize("token,expected,error_msg", [
    ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c", False, "Invalid base64 encoding in token"),
    ("SGVsbG8gV29ybGQ=", False, "Invalid token format"),
    ("", False, "Token cannot be empty"),
    ("  ", False, "Token cannot be empty"),
    ("invalid", True, None),
    ("abc.def.ghi", False, "Invalid base64 encoding in token"),
])
def test_is_valid_token(token, expected, error_msg):
    """Test token validation."""
    result = is_valid_token(token)
    assert result == (expected, error_msg)


if __name__ == "__main__":
    run_tests()
