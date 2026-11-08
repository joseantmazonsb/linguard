"""
Simple test to verify conftest fixtures are loaded.
"""
import pytest

@pytest.fixture
def mock_version_service():
    """Mock version service for testing."""
    class MockVersionService:
        async def check_for_updates(self):
            return {
                "update_available": True,
                "latest_version": "2.0.0",
                "current_version": "1.0.0",
                "release_url": "https://example.com/release-2.0.0"
            }
    return MockVersionService()


@pytest.mark.asyncio
async def test_simple_fixture(mock_version_service):
    """Test that the fixture works."""
    result = await mock_version_service.check_for_updates()
    assert result["update_available"] is True
    assert result["latest_version"] == "2.0.0"
