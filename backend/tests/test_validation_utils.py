"""
Unit tests for Validation utilities.

Tests cover all validation functions in app/utils/validation.py
"""

import pytest
from pydantic_core import PydanticCustomError
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


class TestValidateName:
    """Test validate_name function."""

    def test_valid_name(self):
        """Test valid name validation."""
        result = validate_name("Test Server")
        assert result == "Test Server"

    def test_valid_name_lowercase(self):
        """Test lowercase name validation."""
        result = validate_name("test-server")
        assert result == "test-server"

    def test_valid_name_single_char_fails(self):
        """Test that single character name fails."""
        with pytest.raises(ValueError):
            validate_name("A")

    def test_valid_name_empty_fails(self):
        """Test that empty name fails."""
        with pytest.raises(ValueError):
            validate_name("")

    def test_valid_name_whitespace_only_fails(self):
        """Test that whitespace-only name fails."""
        with pytest.raises(ValueError):
            validate_name("   ")

    def test_valid_name_max_length(self, max_length=128):
        """Test name at max length."""
        name = "a" * max_length
        result = validate_name(name)
        assert result == name

    def test_valid_name_over_max_length_fails(self, max_length=128):
        """Test name over max length fails."""
        name = "a" * (max_length + 1)
        with pytest.raises(ValueError):
            validate_name(name)

    def test_valid_name_custom_max_length(self):
        """Test custom max length."""
        result = validate_name("Test", max_length=5)
        assert result == "Test"

    def test_valid_name_custom_max_length_fails(self):
        """Test custom max length exceeded."""
        with pytest.raises(ValueError):
            validate_name("Test", max_length=3)


class TestValidateDescription:
    """Test validate_description function."""

    def test_valid_description(self):
        """Test valid description validation."""
        result = validate_description("Test description")
        assert result == "Test description"

    def test_valid_description_empty_returns_none(self):
        """Test empty description returns None."""
        result = validate_description("")
        assert result is None

    def test_valid_description_none_returns_none(self):
        """Test None description returns None."""
        result = validate_description(None)
        assert result is None

    def test_valid_description_whitespace_only_returns_none(self):
        """Test whitespace-only description returns None."""
        result = validate_description("   ")
        assert result is None

    def test_valid_description_max_length(self, max_length=500):
        """Test description at max length."""
        desc = "a" * max_length
        result = validate_description(desc)
        assert result == desc

    def test_valid_description_over_max_length_fails(self, max_length=500):
        """Test description over max length fails."""
        desc = "a" * (max_length + 1)
        with pytest.raises(ValueError):
            validate_description(desc)

    def test_valid_description_custom_max_length(self):
        """Test custom max length."""
        result = validate_description("Test", max_length=10)
        assert result == "Test"


class TestValidatePassword:
    """Test validate_password function."""

    def test_valid_password(self):
        """Test valid password validation."""
        result = validate_password("password123")
        assert result == "password123"

    def test_valid_password_min_length(self):
        """Test password at minimum length."""
        result = validate_password("123456")
        assert result == "123456"

    def test_valid_password_empty_fails(self):
        """Test empty password fails."""
        with pytest.raises(ValueError):
            validate_password("")

    def test_valid_password_too_short_fails(self):
        """Test password too short fails."""
        with pytest.raises(ValueError):
            validate_password("12345")

    def test_valid_password_custom_field_name(self):
        """Test custom field name in error."""
        with pytest.raises(ValueError) as exc_info:
            validate_password("12345", field_name="Custom Password")
        assert "Custom Password" in str(exc_info.value)


class TestValidatePort:
    """Test validate_port function."""

    def test_valid_port(self):
        """Test valid port validation."""
        result = validate_port(8080)
        assert result == 8080

    def test_valid_port_min(self):
        """Test minimum valid port."""
        result = validate_port(1024)
        assert result == 1024

    def test_valid_port_max(self):
        """Test maximum valid port."""
        result = validate_port(65535)
        assert result == 65535

    def test_valid_port_below_min_fails(self):
        """Test port below minimum fails."""
        with pytest.raises(ValueError):
            validate_port(1023)

    def test_valid_port_above_max_fails(self):
        """Test port above maximum fails."""
        with pytest.raises(ValueError):
            validate_port(65536)


class TestValidateEndpoint:
    """Test validate_endpoint function."""

    def test_valid_ipv4_endpoint(self):
        """Test valid IPv4 endpoint."""
        result = validate_endpoint("192.168.1.1")
        assert result == "192.168.1.1"

    def test_valid_ipv6_endpoint(self):
        """Test valid IPv6 endpoint."""
        result = validate_endpoint("2001:db8::1")
        assert result == "2001:db8::1"

    def test_valid_ipv6_endpoint_bracketed(self):
        """Test valid IPv6 endpoint with brackets."""
        result = validate_endpoint("[2001:db8::1]")
        assert result == "[2001:db8::1]"

    def test_valid_hostname(self):
        """Test valid hostname."""
        result = validate_endpoint("vpn.example.com")
        assert result == "vpn.example.com"

    def test_valid_hostname_simple(self):
        """Test simple hostname."""
        result = validate_endpoint("server1")
        assert result == "server1"

    def test_valid_endpoint_none(self):
        """Test None endpoint returns None."""
        result = validate_endpoint(None)
        assert result is None

    def test_valid_endpoint_empty(self):
        """Test empty endpoint returns None."""
        result = validate_endpoint("")
        assert result is None

    def test_valid_endpoint_whitespace_only(self):
        """Test whitespace-only endpoint returns None."""
        result = validate_endpoint("   ")
        assert result is None

    def test_invalid_endpoint_purely_numeric(self):
        """Test purely numeric endpoint fails."""
        with pytest.raises(ValueError):
            validate_endpoint("123")

    def test_invalid_endpoint_purely_numeric_dotted(self):
        """Test purely numeric dotted endpoint fails."""
        with pytest.raises(ValueError):
            validate_endpoint("123.456")

    def test_invalid_endpoint_hostname_too_long(self):
        """Test hostname over 253 chars fails."""
        hostname = "a" * 254 + ".example.com"
        with pytest.raises(ValueError):
            validate_endpoint(hostname)

    def test_valid_endpoint_custom_field_name(self):
        """Test custom field name in error."""
        with pytest.raises(ValueError) as exc_info:
            validate_endpoint("123", field_name="Custom Endpoint")
        assert "Custom Endpoint" in str(exc_info.value)


class TestValidatePersistentKeepalive:
    """Test validate_persistent_keepalive function."""

    def test_valid_keepalive(self):
        """Test valid keepalive validation."""
        result = validate_persistent_keepalive(30)
        assert result == 30

    def test_valid_keepalive_zero(self):
        """Test zero keepalive (disabled)."""
        result = validate_persistent_keepalive(0)
        assert result is None

    def test_valid_keepalive_none(self):
        """Test None keepalive returns None."""
        result = validate_persistent_keepalive(None)
        assert result is None

    def test_valid_keepalive_max(self):
        """Test maximum valid keepalive."""
        result = validate_persistent_keepalive(65535)
        assert result == 65535

    def test_valid_keepalive_negative_fails(self):
        """Test negative keepalive fails."""
        with pytest.raises(ValueError):
            validate_persistent_keepalive(-1)

    def test_valid_keepalive_over_max_fails(self):
        """Test keepalive over max fails."""
        with pytest.raises(ValueError):
            validate_persistent_keepalive(65536)


class TestValidateTokenExpiry:
    """Test validate_token_expiry function."""

    def test_valid_expiry(self):
        """Test valid expiry validation."""
        result = validate_token_expiry(1440)
        assert result == 1440

    def test_valid_expiry_min(self):
        """Test minimum valid expiry."""
        result = validate_token_expiry(1)
        assert result == 1

    def test_valid_expiry_max(self):
        """Test maximum valid expiry (30 days)."""
        result = validate_token_expiry(43200)
        assert result == 43200

    def test_valid_expiry_zero_fails(self):
        """Test zero expiry fails."""
        with pytest.raises(ValueError):
            validate_token_expiry(0)

    def test_valid_expiry_negative_fails(self):
        """Test negative expiry fails."""
        with pytest.raises(ValueError):
            validate_token_expiry(-1)


class TestValidateBackupRetentionDays:
    """Test validate_backup_retention_days function."""

    def test_valid_retention(self):
        """Test valid retention validation."""
        result = validate_backup_retention_days(30)
        assert result == 30

    def test_valid_retention_min(self):
        """Test minimum valid retention."""
        result = validate_backup_retention_days(1)
        assert result == 1

    def test_valid_retention_max(self):
        """Test maximum valid retention (365 days)."""
        result = validate_backup_retention_days(365)
        assert result == 365

    def test_valid_retention_zero_fails(self):
        """Test zero retention fails."""
        with pytest.raises(ValueError):
            validate_backup_retention_days(0)

    def test_valid_retention_negative_fails(self):
        """Test negative retention fails."""
        with pytest.raises(ValueError):
            validate_backup_retention_days(-1)

    def test_valid_retention_over_max_fails(self):
        """Test retention over max fails."""
        with pytest.raises(ValueError):
            validate_backup_retention_days(366)


class TestValidateSecretKey:
    """Test validate_secret_key function."""

    def test_valid_secret_key(self):
        """Test valid secret key validation."""
        result = validate_secret_key("a" * 32)
        assert result == "a" * 32

    def test_valid_secret_key_min_length(self):
        """Test secret key at minimum length."""
        result = validate_secret_key("a" * 32)
        assert result == "a" * 32

    def test_valid_secret_key_empty_fails(self):
        """Test empty secret key fails."""
        with pytest.raises(ValueError):
            validate_secret_key("")

    def test_valid_secret_key_too_short_fails(self):
        """Test secret key too short fails."""
        with pytest.raises(ValueError):
            validate_secret_key("a" * 31)

    def test_valid_secret_key_custom_field_name(self):
        """Test custom field name in error."""
        with pytest.raises(ValueError) as exc_info:
            validate_secret_key("a" * 10, field_name="Custom Key")
        assert "Custom Key" in str(exc_info.value)


class TestValidateUsername:
    """Test validate_username function."""

    def test_valid_username(self):
        """Test valid username validation."""
        result = validate_username("john_doe")
        assert result == "john_doe"

    def test_valid_username_lowercase(self):
        """Test lowercase username validation."""
        result = validate_username("user123")
        assert result == "user123"

    def test_valid_username_with_hyphen(self):
        """Test username with hyphen."""
        result = validate_username("user-name")
        assert result == "user-name"

    def test_valid_username_at_max_length(self):
        """Test username at max length."""
        username = "a" * 50
        result = validate_username(username)
        assert result == username

    def test_valid_username_empty_fails(self):
        """Test empty username fails."""
        with pytest.raises(ValueError):
            validate_username("")

    def test_valid_username_whitespace_only_fails(self):
        """Test whitespace-only username fails."""
        with pytest.raises(ValueError):
            validate_username("   ")

    def test_valid_username_over_max_length_fails(self):
        """Test username over max length fails."""
        username = "a" * 51
        with pytest.raises(ValueError):
            validate_username(username)

    def test_valid_username_invalid_chars_fails(self):
        """Test username with invalid characters fails."""
        with pytest.raises(ValueError):
            validate_username("user@name")

    def test_valid_username_invalid_chars_space_fails(self):
        """Test username with spaces fails."""
        with pytest.raises(ValueError):
            validate_username("user name")

    def test_valid_username_custom_field_name(self):
        """Test custom field name in error."""
        with pytest.raises(ValueError) as exc_info:
            validate_username("user@", field_name="Custom Username")
        assert "Custom Username" in str(exc_info.value)


class TestValidateEmail:
    """Test validate_email function."""

    def test_valid_email(self):
        """Test valid email validation."""
        result = validate_email("test@example.com")
        assert result == "test@example.com"

    def test_valid_email_lowercase(self):
        """Test lowercase email validation."""
        result = validate_email("user.name@example.co.uk")
        assert result == "user.name@example.co.uk"

    def test_valid_email_at_max_length(self):
        """Test email at max length (RFC 5321)."""
        email = "a" * 62 + "@example.com"  # 62 chars before @ + @example.com = 254
        result = validate_email(email)
        assert result == email

    def test_valid_email_none_returns_none(self):
        """Test None email returns None."""
        result = validate_email(None)
        assert result is None

    def test_valid_email_empty_returns_none(self):
        """Test empty email returns None."""
        result = validate_email("")
        assert result is None

    def test_valid_email_whitespace_only_returns_none(self):
        """Test whitespace-only email returns None."""
        result = validate_email("   ")
        assert result is None

    def test_valid_email_over_max_length_fails(self):
        """Test email over max length fails."""
        email = "a" * 255 + "@example.com"
        with pytest.raises(ValueError):
            validate_email(email)

    def test_valid_email_invalid_format_fails(self):
        """Test invalid email format fails."""
        with pytest.raises(ValueError):
            validate_email("invalid-email")

    def test_valid_email_custom_field_name(self):
        """Test custom field name in error."""
        with pytest.raises(ValueError) as exc_info:
            validate_email("invalid", field_name="Custom Email")
        assert "Custom Email" in str(exc_info.value)
