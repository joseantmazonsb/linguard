"""
Simple tests for ws.py API
Tests basic authenticated WebSocket functionality.
"""
from datetime import datetime, timedelta

from jose import jwt

from tests.conftest import TEST_SECRET_KEY
from tests.api.misc_api.test_ws_security import ws_path


# ============================================================================
# TESTS
# ============================================================================

def test_websocket_connection(api_client, seeded_db):
    """Test WebSocket connection."""
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.utcnow() + timedelta(minutes=5)},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )
    with api_client.websocket_connect(ws_path(api_client, token)) as websocket:
        assert websocket.receive_json()["authenticated"] is True
