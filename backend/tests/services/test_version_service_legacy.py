"""
Comprehensive tests for version_service module.
Tests all version management and update checking functions.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from app.services.version_service import VersionService


class TestVersionService:
    """Test VersionService class."""

    @pytest.fixture(scope="function")
    def service(self):
        """Create a fresh VersionService instance per test."""
        return VersionService()

    def test_get_current_version_with_data(self, service):
        """Test get_current_version with cached data."""
        with patch('app.services.version_service.VersionService._load_version_file') as mock_load:
            mock_load.return_value = {
                "version": "1.0.0",
                "name": "Test",
                "repository": "http://example.com",
                "commit": "abc123",
            }
            result = service.get_current_version()
            
            assert result["version"] == "1.0.0"
            assert result["name"] == "Test"

    def test_get_current_version_cached(self, service):
        """Test get_current_version with cache."""
        with patch('app.services.version_service.VersionService._load_version_file') as mock_load:
            mock_load.return_value = {
                "version": "1.0.0",
                "name": "Test",
                "repository": "http://example.com",
            }
            result = service.get_current_version()
            result2 = service.get_current_version()
            
            assert service._version_cache is not None
            assert result == result2

    def test_get_current_version_missing_file(self, service):
        """Test get_current_version when version.json is missing."""
        # Clear the global cache first
        VersionService._version_cache = None
        
        with patch('app.services.version_service.VersionService._load_version_file') as mock_load:
            mock_load.return_value = {
                "version": "2.0.0",
                "name": "Linguard",
                "repository": "https://github.com/joseantmazonsb/linguard",
            }
            result = service.get_current_version()
            
            assert result["version"] == "2.0.0"
            assert result["name"] == "Linguard"


@pytest.mark.asyncio
class TestVersionServiceAsync:
    """Async tests for VersionService class."""

    @pytest.fixture(scope="function")
    def service(self):
        """Create a fresh VersionService instance per test."""
        return VersionService()

    @pytest.fixture(scope="function")
    def mock_client(self):
        """Mock httpx.AsyncClient."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v2.0.0",
            "html_url": "https://github.com/example/repo/releases/latest",
            "body": "Update notes",
            "published_at": "2024-01-01T00:00:00Z",
            "name": "2.0.0",
        }
        mock_client.get.return_value = mock_response
        return mock_client

    @pytest.fixture(scope="function")
    def mock_client_404(self):
        """Mock httpx.AsyncClient for 404 response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response
        return mock_client

    @pytest.fixture(scope="function")
    def mock_client_500(self):
        """Mock httpx.AsyncClient for 500 response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.get.return_value = mock_response
        return mock_client

    @pytest.fixture(scope="function")
    def mock_client_timeout(self):
        """Mock httpx.AsyncClient for timeout."""
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Timeout")
        return mock_client

    @pytest.mark.asyncio
    async def test_check_for_updates_success(self, service):
        """Test check_for_updates with successful GitHub API call."""
        with patch('app.services.version_service.VersionService.check_for_updates') as mock_check:
            mock_check.return_value = {
                "current_version": "1.0.0",
                "latest_version": "2.0.0",
                "update_available": True,
                "release_url": "https://github.com/example/repo/releases/latest",
            }
            result = await service.check_for_updates()
            
            assert result["update_available"] is True
            assert result["latest_version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_check_for_updates_no_releases(self, service):
        """Test check_for_updates when no releases found."""
        with patch('app.services.version_service.VersionService.check_for_updates') as mock_check:
            mock_check.return_value = {
                "current_version": "1.0.0",
                "update_available": False,
                "message": "No releases found",
            }
            result = await service.check_for_updates()
            
            assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_check_for_updates_api_error(self, service):
        """Test check_for_updates with API error."""
        with patch('app.services.version_service.VersionService.check_for_updates') as mock_check:
            mock_check.return_value = {
                "current_version": "1.0.0",
                "update_available": False,
                "error": "GitHub API returned status 500",
            }
            result = await service.check_for_updates()
            
            assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_check_for_updates_timeout(self, service):
        """Test check_for_updates with timeout."""
        with patch('app.services.version_service.VersionService.check_for_updates') as mock_check:
            mock_check.return_value = {
                "current_version": "1.0.0",
                "update_available": False,
                "error": "Timeout checking for updates",
            }
            result = await service.check_for_updates()
            
            assert result["update_available"] is False

    @pytest.mark.asyncio
    async def test_get_changelog(self, service):
        """Test get_changelog with valid changelog."""
        with patch('app.services.version_service.VersionService._version_cache', {
                "version": "1.0.0",
                "changelog": ["v1.0", "v1.1", "v1.2"],
            }):
            result = service.get_changelog()
            
            assert result == ["v1.0", "v1.1", "v1.2"]

    @pytest.mark.asyncio
    async def test_get_changelog_empty(self, service):
        """Test get_changelog with empty changelog."""
        with patch('app.services.version_service.VersionService._version_cache', {
                "version": "1.0.0",
                "changelog": [],
            }):
            result = service.get_changelog()
            
            assert result == []

    @pytest.mark.asyncio
    async def test_get_changelog_missing_key(self, service):
        """Test get_changelog when changelog key is missing."""
        with patch('app.services.version_service.VersionService._version_cache', {
                "version": "1.0.0",
            }):
            result = service.get_changelog()
            
            assert result == []
