"""
Reusable validation functions for Linguard API.

Provides validators for common fields like names, passwords, endpoints, ports, etc.
These validators raise PydanticCustomError with descriptive messages on validation failure.
"""

import re
import ipaddress
from typing import Optional
from pydantic_core import PydanticCustomError


def _raise_validation_error(message: str) -> None:
    """
    Helper to raise a Pydantic validation error without the 'Value error, ' prefix.
    
    Args:
        message: The error message to display
    """
    raise PydanticCustomError('value_error', message)


def validate_name(value: str, field_name: str = "Name", max_length: int = 128) -> str:
    """
    Validate a name field (server name, peer name, etc.).
    
    Rules:
    - Must not be empty after stripping whitespace
    - Minimum 2 characters
    - Must contain at least one letter
    - Maximum length of max_length characters (default: 128)
    
    Args:
        value: The name to validate
        field_name: The field name for error messages (default: "Name")
        max_length: Maximum allowed length (default: 128)
        
    Returns:
        The validated and stripped name
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        raise ValueError(f"{field_name} is required")
    
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be empty or whitespace only")
    
    if len(stripped) < 2:
        raise ValueError(f"{field_name} must be at least 2 characters long")
    
    if not any(c.isalpha() for c in stripped):
        raise ValueError(f"{field_name} must contain at least one letter")
    
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    
    return stripped


def validate_description(value: Optional[str], field_name: str = "Description", max_length: int = 500) -> Optional[str]:
    """
    Validate an optional description field.
    
    Rules:
    - Optional (can be None or empty)
    - Maximum length of max_length characters (default: 500)
    
    Args:
        value: The description to validate
        field_name: The field name for error messages (default: "Description")
        max_length: Maximum allowed length (default: 500)
        
    Returns:
        The validated and stripped description, or None if empty
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        return None
    
    stripped = value.strip()
    if not stripped:
        return None
    
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must not exceed {max_length} characters")
    
    return stripped


def validate_password(value: str, field_name: str = "Password") -> str:
    """
    Validate a password field.
    
    Rules:
    - Minimum 6 characters
    
    Args:
        value: The password to validate
        field_name: The field name for error messages (default: "Password")
        
    Returns:
        The validated password
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        raise ValueError(f"{field_name} is required")
    
    if len(value) < 6:
        raise ValueError(f"{field_name} must be at least 6 characters long")
    
    return value


def validate_port(value: int, field_name: str = "Port") -> int:
    """
    Validate a network port number.
    
    Rules:
    - Must be between 1024 and 65535 (above reserved ports)
    
    Args:
        value: The port number to validate
        field_name: The field name for error messages (default: "Port")
        
    Returns:
        The validated port number
        
    Raises:
        ValueError: If validation fails
    """
    if value < 1024 or value > 65535:
        raise ValueError(f"{field_name} must be between 1024 and 65535")
    
    return value


def validate_endpoint(value: Optional[str], field_name: str = "Endpoint") -> Optional[str]:
    """
    Validate a WireGuard endpoint (hostname, IPv4, or IPv6).
    
    Rules:
    - Can be IPv4 address (e.g., "192.168.1.1")
    - Can be IPv6 address (e.g., "2001:db8::1" or "[2001:db8::1]")
    - Can be hostname (e.g., "vpn.example.com")
    - Should NOT include port (port is separate field)
    
    Args:
        value: The endpoint to validate
        field_name: The field name for error messages (default: "Endpoint")
        
    Returns:
        The validated endpoint
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        return None
    
    stripped = value.strip()
    if not stripped:
        return None
    
    # Remove brackets if present (for IPv6)
    test_value = stripped.strip('[]')
    
    # Try to parse as IPv4
    try:
        ipaddress.IPv4Address(test_value)
        return stripped
    except ValueError:
        pass
    
    # Try to parse as IPv6
    try:
        ipaddress.IPv6Address(test_value)
        return stripped
    except ValueError:
        pass
    
    # Validate as hostname (basic validation)
    # Hostname rules: alphanumeric, hyphens, dots, max 253 chars
    hostname_pattern = r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$'
    if not re.match(hostname_pattern, test_value):
        raise ValueError(
            f"{field_name} must be a valid IPv4 address, IPv6 address, or hostname"
        )
    
    if len(test_value) > 253:
        raise ValueError(f"{field_name} hostname must not exceed 253 characters")
    
    # Reject purely numeric hostnames (e.g., "123" or "123.456")
    # This prevents ambiguity with IP addresses and follows DNS standards
    if test_value.replace('.', '').replace('-', '').isdigit():
        raise ValueError(f"{field_name} hostname cannot be purely numeric")
    
    return stripped


def validate_persistent_keepalive(value: Optional[int], field_name: str = "Persistent keepalive") -> Optional[int]:
    """
    Validate WireGuard persistent keepalive interval.
    
    Rules:
    - Optional (can be None or 0 to disable)
    - If set, must be between 1 and 65535 seconds
    
    Args:
        value: The keepalive interval in seconds
        field_name: The field name for error messages
        
    Returns:
        The validated keepalive value or None
        
    Raises:
        ValueError: If validation fails
    """
    if value is None or value == 0:
        return None
    
    if value < 0 or value > 65535:
        raise ValueError(f"{field_name} must be between 0 and 65535 seconds")
    
    return value


def validate_token_expiry(value: int, field_name: str = "Token expiry") -> int:
    """
    Validate access token expiration time in minutes.
    
    Rules:
    - Must be between 1 and 43200 minutes (30 days)
    
    Args:
        value: The expiry time in minutes
        field_name: The field name for error messages
        
    Returns:
        The validated expiry time
        
    Raises:
        ValueError: If validation fails
    """
    if value < 1 or value > 43200:
        raise ValueError(f"{field_name} must be between 1 and 43200 minutes")
    
    return value


def validate_backup_retention_days(value: int, field_name: str = "Backup retention days") -> int:
    """
    Validate backup retention period in days.
    
    Rules:
    - Must be between 1 and 365 days
    
    Args:
        value: The retention period in days
        field_name: The field name for error messages
        
    Returns:
        The validated retention period
        
    Raises:
        ValueError: If validation fails
    """
    if value < 1 or value > 365:
        raise ValueError(f"{field_name} must be between 1 and 365 days")
    
    return value


def validate_secret_key(value: str, field_name: str = "Secret key") -> str:
    """
    Validate JWT secret key.
    
    Rules:
    - Minimum 32 characters for security
    
    Args:
        value: The secret key to validate
        field_name: The field name for error messages
        
    Returns:
        The validated secret key
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        raise ValueError(f"{field_name} is required")
    
    if len(value) < 32:
        raise ValueError(f"{field_name} must be at least 32 characters long for security")
    
    return value


def validate_username(value: str, field_name: str = "Username") -> str:
    """
    Validate a username field.
    
    Rules:
    - Must not be empty after stripping whitespace
    - Maximum length of 50 characters
    - Must contain only alphanumeric characters, underscores, and hyphens
    
    Args:
        value: The username to validate
        field_name: The field name for error messages
        
    Returns:
        The validated and stripped username
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        raise ValueError(f"{field_name} is required")
    
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} cannot be empty or whitespace only")
    
    if len(stripped) > 50:
        raise ValueError(f"{field_name} must not exceed 50 characters")
    
    # Username pattern: alphanumeric, underscores, hyphens
    username_pattern = r'^[A-Za-z0-9_-]+$'
    if not re.match(username_pattern, stripped):
        raise ValueError(
            f"{field_name} must contain only letters, numbers, underscores, and hyphens"
        )
    
    return stripped


def validate_email(value: Optional[str], field_name: str = "Email") -> Optional[str]:
    """
    Validate an email address.
    
    Rules:
    - Optional (can be None or empty)
    - Must match basic email pattern if provided
    
    Args:
        value: The email to validate
        field_name: The field name for error messages
        
    Returns:
        The validated and stripped email, or None if empty
        
    Raises:
        ValueError: If validation fails
    """
    if not value:
        return None
    
    stripped = value.strip()
    if not stripped:
        return None
    
    # Basic email pattern validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, stripped):
        raise ValueError(f"{field_name} must be a valid email address")
    
    if len(stripped) > 254:  # RFC 5321
        raise ValueError(f"{field_name} must not exceed 254 characters")
    
    return stripped
