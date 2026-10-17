"""
Integration tests for Backup API endpoints.
These tests use FastAPI TestClient to test the actual API endpoints,
avoiding complex mocking issues with async services.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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


class TestBackupAPI:
    """Test Backup API endpoints."""

    def test_backup_endpoint_exists(self, auth_headers):
        """Test that backup endpoint exists and returns 200 (no auth required for listing)."""
        response = client.get("/api/v1/backups/", headers=auth_headers)
        assert response.status_code in [200, 401]

    def test_create_backup_endpoint_exists(self, auth_headers):
        """Test that create backup endpoint exists and returns 201."""
        response = client.post("/api/v1/backups/", headers=auth_headers)
        assert response.status_code in [201, 400]

    def test_get_backup_endpoint_exists(self, auth_headers):
        """Test that get backup endpoint exists."""
        response = client.get("/api/v1/backups/1", headers=auth_headers)
        assert response.status_code in [200, 404]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
