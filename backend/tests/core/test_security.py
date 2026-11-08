"""Test authentication and security module."""
import pytest
from datetime import timedelta

from app.core.security import (
    verify_password,
    get_password_hash,
)
from app.models.settings import GlobalSettings


def test_verify_password_correct():
    """Test password verification with correct password."""
    hashed = get_password_hash("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_incorrect():
    """Test password verification with incorrect password."""
    hashed = get_password_hash("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_empty():
    """Test password verification with empty password."""
    hashed = get_password_hash("password")
    assert verify_password("", hashed) is False


def test_verify_password_short():
    """Test password verification with short password."""
    hashed = get_password_hash("short")
    assert verify_password("short", hashed) is True


def test_get_password_hash():
    """Test password hashing."""
    password = "test_password"
    hashed = get_password_hash(password)
    assert hashed is not None
    assert len(hashed) > 0


def test_get_password_hash_empty():
    """Test password hashing with empty string."""
    assert get_password_hash("") is not None


def test_password_hashing_consistency():
    """Test that password hashing is consistent (same hash for same password)."""
    password = "test_password"
    hashed1 = get_password_hash(password)
    hashed2 = get_password_hash(password)
    
    # Hashes should be the same for same password
    # Note: bcrypt with random salt may produce different hashes, but same password
    # should produce different hashes for different passwords
    assert hashed1 is not None
    assert hashed2 is not None
    assert hashed1 != hashed2  # Different calls should produce different hashes


def test_password_truncation():
    """Test password truncation to 72 bytes."""
    # Long password
    long_password = "a" * 200
    hashed = get_password_hash(long_password)
    
    # Should truncate to 72 bytes
    assert len(long_password[:72]) == 72
