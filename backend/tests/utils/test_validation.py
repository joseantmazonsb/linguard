"""
Comprehensive tests for validation module.
Tests all validation functions to achieve high coverage.
"""
import pytest
from app.utils.validation import (
    validate_name,
    validate_description,
    validate_password,
    validate_port,
    validate_endpoint,
    validate_persistent_keepalive,
    validate_token_expiry,
    validate_backup_retention_days,
    validate_secret_key,
    validate_username,
    validate_email,
)


# ============================================================================
# NAME VALIDATION TESTS
# ============================================================================

class TestValidateName:
    """Tests for validate_name function."""

    def test_validate_name_valid(self):
        """Test validation of valid name."""
        result = validate_name("test-server")
        assert result == "test-server"

    def test_validate_name_with_spaces(self):
        """Test validation of name with leading/trailing spaces."""
        result = validate_name("  test-server  ")
        assert result == "test-server"

    def test_validate_name_minimum_length(self):
        """Test validation of minimum length (2 characters)."""
        result = validate_name("ab")
        assert result == "ab"

    def test_validate_name_minimum_length_fails(self):
        """Test validation of minimum length fails with single character."""
        with pytest.raises(ValueError, match=r"must be at least 2 characters long"):
            validate_name("a")

    def test_validate_name_minimum_length_fails_empty(self):
        """Test validation of minimum length fails with empty string."""
        with pytest.raises(ValueError, match=r"is required"):
            validate_name("")

    def test_validate_name_minimum_length_fails_whitespace_only(self):
        """Test validation of minimum length fails with whitespace only."""
        with pytest.raises(ValueError, match=r"cannot be empty or whitespace only"):
            validate_name("   ")

    def test_validate_name_contains_letter(self):
        """Test validation of name must contain at least one letter."""
        result = validate_name("test")
        assert result == "test"

    def test_validate_name_no_letter_fails(self):
        """Test validation fails when name has no letters."""
        with pytest.raises(ValueError, match=r"must contain at least one letter"):
            validate_name("123")

    def test_validate_name_no_letter_whitespace_only_fails(self):
        """Test validation fails with whitespace and numbers."""
        with pytest.raises(ValueError, match=r"must contain at least one letter"):
            validate_name("  123  ")

    def test_validate_name_max_length_valid(self):
        """Test validation of maximum length (128 characters)."""
        result = validate_name("x" * 128)
        assert len(result) == 128

    def test_validate_name_max_length_fails(self):
        """Test validation fails when name exceeds maximum length."""
        with pytest.raises(ValueError, match=r"must not exceed 128 characters"):
            validate_name("x" * 129)

    def test_validate_name_custom_max_length_valid(self):
        """Test validation with custom maximum length."""
        result = validate_name("test", max_length=10)
        assert len(result) <= 10

    def test_validate_name_custom_max_length_fails(self):
        """Test validation fails with custom maximum length."""
        with pytest.raises(ValueError, match=r"must not exceed 10 characters"):
            validate_name("x" * 11, max_length=10)

    def test_validate_name_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_name("test", field_name="Custom Name")
        assert result == "test"


# ============================================================================
# DESCRIPTION VALIDATION TESTS
# ============================================================================

class TestValidateDescription:
    """Tests for validate_description function."""

    def test_validate_description_valid(self):
        """Test validation of valid description."""
        result = validate_description("Test description")
        assert result == "Test description"

    def test_validate_description_empty_returns_none(self):
        """Test validation of empty description returns None."""
        result = validate_description("")
        assert result is None

    def test_validate_description_whitespace_only_returns_none(self):
        """Test validation of whitespace-only description returns None."""
        result = validate_description("   ")
        assert result is None

    def test_validate_description_max_length_valid(self):
        """Test validation of maximum length (500 characters)."""
        result = validate_description("x" * 500)
        assert len(result) == 500

    def test_validate_description_max_length_fails(self):
        """Test validation fails when description exceeds maximum length."""
        with pytest.raises(ValueError, match=r"must not exceed 500 characters"):
            validate_description("x" * 501)

    def test_validate_description_custom_max_length_valid(self):
        """Test validation with custom maximum length."""
        result = validate_description("test", max_length=50)
        assert len(result) <= 50

    def test_validate_description_custom_max_length_fails(self):
        """Test validation fails with custom maximum length."""
        with pytest.raises(ValueError, match=r"must not exceed 50 characters"):
            validate_description("x" * 51, max_length=50)

    def test_validate_description_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_description("test", field_name="Desc")
        assert result == "test"


# ============================================================================
# PASSWORD VALIDATION TESTS
# ============================================================================

class TestValidatePassword:
    """Tests for validate_password function."""

    def test_validate_password_valid(self):
        """Test validation of valid password (6+ characters)."""
        result = validate_password("password")
        assert result == "password"

    def test_validate_password_minimum_length(self):
        """Test validation of minimum length (6 characters)."""
        result = validate_password("123456")
        assert result == "123456"

    def test_validate_password_minimum_length_fails(self):
        """Test validation fails with less than 6 characters."""
        with pytest.raises(ValueError, match=r"must be at least 6 characters long"):
            validate_password("12345")

    def test_validate_password_minimum_length_fails_empty(self):
        """Test validation fails with empty password."""
        with pytest.raises(ValueError, match=r"is required"):
            validate_password("")

    def test_validate_password_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_password("testpass", field_name="Pass")
        assert result == "testpass"


# ============================================================================
# PORT VALIDATION TESTS
# ============================================================================

class TestValidatePort:
    """Tests for validate_port function."""

    def test_validate_port_valid_low(self):
        """Test validation of valid port (1024+)."""
        result = validate_port(1024)
        assert result == 1024

    def test_validate_port_valid_high(self):
        """Test validation of valid high port (65535)."""
        result = validate_port(65535)
        assert result == 65535

    def test_validate_port_reserved_fails(self):
        """Test validation fails for reserved port (below 1024)."""
        with pytest.raises(ValueError, match=r"must be between 1024 and 65535"):
            validate_port(1023)

    def test_validate_port_reserved_fails_zero(self):
        """Test validation fails for port 0."""
        with pytest.raises(ValueError, match=r"must be between 1024 and 65535"):
            validate_port(0)

    def test_validate_port_reserved_fails_negative(self):
        """Test validation fails for negative port."""
        with pytest.raises(ValueError, match=r"must be between 1024 and 65535"):
            validate_port(-1)

    def test_validate_port_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_port(8080, field_name="My Port")
        assert result == 8080


# ============================================================================
# ENDPOINT VALIDATION TESTS
# ============================================================================

class TestValidateEndpoint:
    """Tests for validate_endpoint function."""

    def test_validate_endpoint_valid_ipv4(self):
        """Test validation of valid IPv4 address."""
        result = validate_endpoint("192.168.1.1")
        assert result == "192.168.1.1"

    def test_validate_endpoint_valid_ipv4_with_brackets(self):
        """Test validation of IPv4 with brackets (should still work)."""
        result = validate_endpoint("[192.168.1.1]")
        assert result == "[192.168.1.1]"

    def test_validate_endpoint_valid_ipv6(self):
        """Test validation of valid IPv6 address."""
        result = validate_endpoint("2001:db8::1")
        assert result == "2001:db8::1"

    def test_validate_endpoint_valid_ipv6_brackets(self):
        """Test validation of IPv6 with brackets."""
        result = validate_endpoint("[2001:db8::1]")
        assert result == "[2001:db8::1]"

    def test_validate_endpoint_valid_hostname(self):
        """Test validation of valid hostname."""
        result = validate_endpoint("vpn.example.com")
        assert result == "vpn.example.com"

    def test_validate_endpoint_valid_hostname_with_dash(self):
        """Test validation of hostname with dashes."""
        result = validate_endpoint("my-vpn-server.local")
        assert result == "my-vpn-server.local"

    def test_validate_endpoint_empty_returns_none(self):
        """Test validation of empty endpoint returns None."""
        result = validate_endpoint("")
        assert result is None

    def test_validate_endpoint_whitespace_only_returns_none(self):
        """Test validation of whitespace-only endpoint returns None."""
        result = validate_endpoint("   ")
        assert result is None

    def test_validate_endpoint_with_port_excluded(self):
        """Test validation rejects endpoint with port."""
        with pytest.raises(ValueError, match=r"must be a valid IPv4 address"):
            validate_endpoint("192.168.1.1:8080")

    def test_validate_endpoint_invalid_ipv4(self):
        """Test validation fails for invalid IPv4 (treated as purely numeric)."""
        with pytest.raises(ValueError, match=r"cannot be purely numeric"):
            validate_endpoint("999.999.999.999")

    def test_validate_endpoint_invalid_ipv6(self):
        """Test validation fails for invalid IPv6."""
        with pytest.raises(ValueError, match=r"must be a valid IPv4 address"):
            validate_endpoint("999::db8::1")

    def test_validate_endpoint_pure_number_fails(self):
        """Test validation fails for purely numeric hostname."""
        with pytest.raises(ValueError, match=r"cannot be purely numeric"):
            validate_endpoint("123")

    def test_validate_endpoint_pure_number_with_dot_fails(self):
        """Test validation fails for purely numeric hostname with dots."""
        with pytest.raises(ValueError, match=r"cannot be purely numeric"):
            validate_endpoint("123.456")

    def test_validate_endpoint_hostname_too_long_fails(self):
        """Test validation fails for hostname exceeding 253 characters."""
        with pytest.raises(ValueError, match=r"must be a valid IPv4 address, IPv6 address, or hostname"):
            validate_endpoint("x" * 254)

    def test_validate_endpoint_hostname_with_special_chars(self):
        """Test validation of hostname with valid special characters."""
        result = validate_endpoint("user.name.server.example.com")
        assert result == "user.name.server.example.com"


# ============================================================================
# PERSISTENT KEEPALIVE VALIDATION TESTS
# ============================================================================

class TestValidatePersistentKeepalive:
    """Tests for validate_persistent_keepalive function."""

    def test_validate_keepalive_valid_min(self):
        """Test validation of minimum keepalive (1 second)."""
        result = validate_persistent_keepalive(1)
        assert result == 1

    def test_validate_keepalive_valid_max(self):
        """Test validation of maximum keepalive (65535)."""
        result = validate_persistent_keepalive(65535)
        assert result == 65535

    def test_validate_keepalive_valid_none(self):
        """Test validation of None keepalive returns None."""
        result = validate_persistent_keepalive(None)
        assert result is None

    def test_validate_keepalive_invalid_negative(self):
        """Test validation fails for negative keepalive."""
        with pytest.raises(ValueError, match=r"must be between 0 and 65535 seconds"):
            validate_persistent_keepalive(-1)

    def test_validate_keepalive_invalid_too_large(self):
        """Test validation fails for keepalive exceeding maximum."""
        with pytest.raises(ValueError, match=r"must be between 0 and 65535 seconds"):
            validate_persistent_keepalive(65536)

    def test_validate_keepalive_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_persistent_keepalive(25, field_name="My Keepalive")
        assert result == 25

    def test_validate_keepalive_zero_returns_none(self):
        """Test validation of zero returns None."""
        result = validate_persistent_keepalive(0)
        assert result is None


# ============================================================================
# TOKEN EXPIRY VALIDATION TESTS
# ============================================================================

class TestValidateTokenExpiry:
    """Tests for validate_token_expiry function."""

    def test_validate_expiry_valid_min(self):
        """Test validation of minimum expiry (1 minute)."""
        result = validate_token_expiry(1)
        assert result == 1

    def test_validate_expiry_valid_max(self):
        """Test validation of maximum expiry (43200 minutes = 30 days)."""
        result = validate_token_expiry(43200)
        assert result == 43200

    def test_validate_expiry_invalid_too_small(self):
        """Test validation fails for expiry less than 1 minute."""
        with pytest.raises(ValueError, match=r"must be between 1 and 43200 minutes"):
            validate_token_expiry(0)

    def test_validate_expiry_invalid_too_large(self):
        """Test validation fails for expiry exceeding 43200 minutes."""
        with pytest.raises(ValueError, match=r"must be between 1 and 43200 minutes"):
            validate_token_expiry(43201)

    def test_validate_expiry_negative_fails(self):
        """Test validation fails for negative expiry."""
        with pytest.raises(ValueError, match=r"must be between 1 and 43200 minutes"):
            validate_token_expiry(-1)

    def test_validate_expiry_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_token_expiry(240, field_name="My Expiry")
        assert result == 240


# ============================================================================
# BACKUP RETENTION VALIDATION TESTS
# ============================================================================

class TestValidateBackupRetentionDays:
    """Tests for validate_backup_retention_days function."""

    def test_validate_retention_valid_min(self):
        """Test validation of minimum retention (1 day)."""
        result = validate_backup_retention_days(1)
        assert result == 1

    def test_validate_retention_valid_max(self):
        """Test validation of maximum retention (365 days)."""
        result = validate_backup_retention_days(365)
        assert result == 365

    def test_validate_retention_invalid_too_small(self):
        """Test validation fails for retention less than 1 day."""
        with pytest.raises(ValueError, match=r"must be between 1 and 365 days"):
            validate_backup_retention_days(0)

    def test_validate_retention_invalid_too_large(self):
        """Test validation fails for retention exceeding 365 days."""
        with pytest.raises(ValueError, match=r"must be between 1 and 365 days"):
            validate_backup_retention_days(366)

    def test_validate_retention_negative_fails(self):
        """Test validation fails for negative retention."""
        with pytest.raises(ValueError, match=r"must be between 1 and 365 days"):
            validate_backup_retention_days(-1)

    def test_validate_retention_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_backup_retention_days(30, field_name="My Retention")
        assert result == 30


# ============================================================================
# SECRET KEY VALIDATION TESTS
# ============================================================================

class TestValidateSecretKey:
    """Tests for validate_secret_key function."""

    def test_validate_secret_minimum_length(self):
        """Test validation of minimum length (32 characters)."""
        result = validate_secret_key("x" * 32)
        assert result == "x" * 32

    def test_validate_secret_minimum_length_fails(self):
        """Test validation fails with less than 32 characters."""
        with pytest.raises(ValueError, match=r"must be at least 32 characters long for security"):
            validate_secret_key("x" * 31)

    def test_validate_secret_minimum_length_fails_empty(self):
        """Test validation fails with empty secret key."""
        with pytest.raises(ValueError, match=r"is required"):
            validate_secret_key("")

    def test_validate_secret_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_secret_key("my-super-secret-key-123456789012", field_name="My Secret")
        assert result == "my-super-secret-key-123456789012"


# ============================================================================
# USERNAME VALIDATION TESTS
# ============================================================================

class TestValidateUsername:
    """Tests for validate_username function."""

    def test_validate_username_valid(self):
        """Test validation of valid username."""
        result = validate_username("johndoe")
        assert result == "johndoe"

    def test_validate_username_with_underscore(self):
        """Test validation of username with underscore."""
        result = validate_username("john_doe")
        assert result == "john_doe"

    def test_validate_username_with_hyphen(self):
        """Test validation of username with hyphen."""
        result = validate_username("john-doe")
        assert result == "john-doe"

    def test_validate_username_empty_fails(self):
        """Test validation fails with empty username."""
        with pytest.raises(ValueError, match=r"is required"):
            validate_username("")

    def test_validate_username_whitespace_only_fails(self):
        """Test validation fails with whitespace-only username."""
        with pytest.raises(ValueError, match=r"cannot be empty or whitespace only"):
            validate_username("   ")

    def test_validate_username_too_long_fails(self):
        """Test validation fails when username exceeds 50 characters."""
        with pytest.raises(ValueError, match=r"must not exceed 50 characters"):
            validate_username("x" * 51)

    def test_validate_username_invalid_chars_fails(self):
        """Test validation fails for invalid characters."""
        with pytest.raises(ValueError, match=r"must contain only letters, numbers, underscores, and hyphens"):
            validate_username("john@doe")

    def test_validate_username_invalid_chars_special(self):
        """Test validation fails for special characters."""
        with pytest.raises(ValueError, match=r"must contain only letters, numbers, underscores, and hyphens"):
            validate_username("john.doe")

    def test_validate_username_starting_with_hyphen(self):
        """Test validation of username starting with hyphen (allowed)."""
        result = validate_username("-john")
        assert result == "-john"

    def test_validate_username_starting_with_number(self):
        """Test validation of username starting with number."""
        result = validate_username("1john")
        assert result == "1john"


# ============================================================================
# EMAIL VALIDATION TESTS
# ============================================================================

class TestValidateEmail:
    """Tests for validate_email function."""

    def test_validate_email_valid(self):
        """Test validation of valid email."""
        result = validate_email("test@example.com")
        assert result == "test@example.com"

    def test_validate_email_valid_with_plus(self):
        """Test validation of email with plus address."""
        result = validate_email("user+tag@example.com")
        assert result == "user+tag@example.com"

    def test_validate_email_valid_with_dot_in_local(self):
        """Test validation of email with dot in local part."""
        result = validate_email("john.doe@example.com")
        assert result == "john.doe@example.com"

    def test_validate_email_valid_with_underscore(self):
        """Test validation of email with underscore."""
        result = validate_email("john_doe@example.com")
        assert result == "john_doe@example.com"

    def test_validate_email_empty_returns_none(self):
        """Test validation of empty email returns None."""
        result = validate_email("")
        assert result is None

    def test_validate_email_whitespace_only_returns_none(self):
        """Test validation of whitespace-only email returns None."""
        result = validate_email("   ")
        assert result is None

    def test_validate_email_invalid_format_fails(self):
        """Test validation fails for invalid email format."""
        with pytest.raises(ValueError, match=r"must be a valid email address"):
            validate_email("invalid-email")

    def test_validate_email_no_domain_fails(self):
        """Test validation fails for email without domain."""
        with pytest.raises(ValueError, match=r"must be a valid email address"):
            validate_email("user@")

    def test_validate_email_invalid_tld_fails(self):
        """Test validation fails for email with invalid TLD."""
        with pytest.raises(ValueError, match=r"must be a valid email address"):
            validate_email("user@invalid")

    def test_validate_email_too_long_fails(self):
        """Test validation fails for email exceeding 254 characters."""
        with pytest.raises(ValueError, match=r"must be a valid email address"):
            validate_email("x" * 255)

    def test_validate_email_custom_field_name(self):
        """Test validation with custom field name."""
        result = validate_email("test@example.com", field_name="My Email")
        assert result == "test@example.com"

    def test_validate_email_invalid_special_chars(self):
        """Test validation fails for email with invalid special characters."""
        with pytest.raises(ValueError, match=r"must be a valid email address"):
            validate_email("test@example.com!")

    def test_validate_email_subdomain_valid(self):
        """Test validation of email with subdomain."""
        result = validate_email("user@mail.example.com")
        assert result == "user@mail.example.com"

    def test_validate_email_long_subdomain_valid(self):
        """Test validation of email with long subdomain."""
        result = validate_email("user" + "sub" * 20 + "@example.com")
        assert result == "user" + "sub" * 20 + "@example.com"
