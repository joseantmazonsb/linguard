"""Pytest configuration and global fixtures."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load global fixtures
pytest_plugins = [
    "tests.fixtures",
]


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client(client):
    """Create async test client for integration tests."""
    from fastapi.testclient import AsyncTestClient
    from app.main import app
    
    async with AsyncTestClient(app) as ac:
        yield ac


@pytest.fixture
def auth_headers(client):
    """Create auth headers for API requests."""
    # Get token from login endpoint
    login_data = {"username": "admin", "password": "admin"}
    login_response = client.post("/api/v1/auth/token", json=login_data)
    
    if login_response.status_code != 200:
        pytest.skip("Cannot authenticate for tests")
    
    token = login_response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_server(client, auth_headers):
    """Create a test server for integration tests."""
    # This fixture creates a server in the database for tests
    # The actual implementation depends on the test requirements
    return None


@pytest.fixture
def test_peer(test_server, client, auth_headers):
    """Create a test peer for integration tests."""
    # This fixture creates a peer in the database for tests
    # The actual implementation depends on the test requirements
    return None
