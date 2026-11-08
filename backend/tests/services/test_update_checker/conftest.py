"""
Fixtures for update_checker tests.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from app.services.update_checker import UpdateCheckerService
from app.services.version_service import VersionService
from app.services.notification_service import NotificationService


@pytest.fixture
def mock_version_service():
    """Mock version service for testing."""
    # Use a class-based mock that properly implements the async method
    class MockVersionService:
        async def check_for_updates(self):
            return {
                "update_available": True,
                "latest_version": "2.0.0",
                "current_version": "1.0.0",
                "release_url": "https://example.com/release-2.0.0"
            }
    return MockVersionService()


@pytest.fixture
def mock_notification_service():
    """Mock notification service for testing."""
    mock = MagicMock()
    # Make create_notification return None and track calls
    mock.create_notification = MagicMock(return_value=None)
    # Make _broadcast_notification do nothing (mock it)
    mock._broadcast_notification = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_db():
    """Mock database session."""
    mock_session = MagicMock()
    # Make execute() return a mock result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.fixture
def mock_user():
    """Mock user for testing."""
    return MagicMock(id=1, username="admin")


@pytest.fixture
def mock_db():
    """Mock database session."""
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    return mock_session


@pytest.fixture
def checker(mock_version_service, mock_notification_service):
    """Create an UpdateCheckerService instance."""
    return UpdateCheckerService(
        version_service=mock_version_service,
        notification_service=mock_notification_service,
        check_interval_hours=6
    )
