"""
Simple tests for ws.py API
Tests basic functionality without database fixtures
"""
from unittest.mock import MagicMock, patch
import pytest

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ============================================================================
# TESTS
# ============================================================================

def test_websocket_connection():
    """Test WebSocket connection."""
    with client.websocket_connect("/ws") as websocket:
        # In newer FastAPI versions, the context manager handles accept internally
        # In older versions, call websocket.accept() explicitly
        # For this test, we just verify the connection can be established
        # The accept is handled automatically by the context manager
        pass  # Connection established successfully
