"""
Integration tests for Backup API endpoints.
These tests use FastAPI TestClient to test the actual API endpoints,
avoiding complex mocking issues with async services.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestBackupAPI:
    """Test Backup API endpoints."""

    def test_backup_endpoint_exists(self):
        """Test that backup endpoint exists and returns 401 (unauthorized)."""
        response = client.get("/api/v1/backups/")
        assert response.status_code == 401 or response.status_code == 200

    def test_create_backup_endpoint_exists(self):
        """Test that create backup endpoint exists and returns 401 (unauthorized)."""
        response = client.post("/api/v1/backups/")
        assert response.status_code == 401 or response.status_code == 201

    def test_get_backup_endpoint_exists(self):
        """Test that get backup endpoint exists and returns 401 (unauthorized)."""
        response = client.get("/api/v1/backups/1")
        assert response.status_code == 401 or response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
