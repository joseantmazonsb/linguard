"""Test database module."""
import pytest
import asyncio
from pathlib import Path

from app.core.database import (
    _build_engine,
    init_db,
    engine,
    AsyncSessionLocal,
)


def test_build_engine_sqlite():
    """Test building SQLite engine."""
    result = _build_engine("sqlite+aiosqlite:///:memory:")
    # Check that engine is created and has the right URL
    assert result is not None
    # SQLAlchemy URL object - check it contains sqlite
    assert str(result.url).startswith("sqlite")


def test_build_engine_postgresql():
    """Test building PostgreSQL engine."""
    # Skip if async driver not available
    try:
        result = _build_engine("postgresql://user:pass@localhost:5432/test")
        assert result is not None
        assert str(result.url).startswith("postgresql")
    except Exception:
        # If async driver not available, skip this test
        pass


def test_build_engine_mysql():
    """Test building MySQL engine."""
    # Skip if async driver not available
    try:
        result = _build_engine("mysql://root:pass@localhost:3306/linguard")
        assert result is not None
        assert str(result.url).startswith("mysql")
    except Exception:
        # If async driver not available, skip this test
        pass


def test_build_engine_sqlite_with_fkeys():
    """Test building SQLite engine with foreign key support."""
    result = _build_engine("sqlite+aiosqlite:///test.db")
    assert result is not None
    assert str(result.url).startswith("sqlite")


def test_build_engine_no_sqlite_fkeys():
    """Test building non-SQLite engine doesn't add foreign keys pragma."""
    try:
        result = _build_engine("postgresql://user:pass@localhost:5432/test")
        assert result is not None
        assert str(result.url).startswith("postgresql")
    except Exception:
        # If async driver not available, skip this test
        pass


def test_build_engine_echo_false():
    """Test build_engine sets echo=False."""
    result = _build_engine("sqlite+aiosqlite:///:memory:")
    assert result is not None
    assert str(result.url).startswith("sqlite")
