"""
Conftest fixtures for integration tests.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.integration_service import IntegrationService
from app.services.notification_service import NotificationService
from app.models.integration import Integration
from app.core.events import EventType


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service."""
    notification_service = MagicMock()
    
    async def mock_notify_from_integration(db, integration, event_data):
        notification_service.notify_from_integration = AsyncMock()
        notification_service.notify_from_integration(db, integration, event_data)
    
    notification_service.notify_from_integration = mock_notify_from_integration
    
    async def mock_create_notification(db, user_id, title, message, type, link=None,
                                      event_type=None, source_type=None, source_id=None,
                                      auto_commit=True):
        from app.models.notification import Notification
        notification = Notification(
            user_id=user_id, title=title, message=message, type=type,
            link=link, event_type=event_type, source_type=source_type, source_id=source_id
        )
        if auto_commit:
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
        return notification
    
    notification_service.create_notification = mock_create_notification
    
    return notification_service


@pytest.fixture
def mock_plugin_manager():
    """Create a mock plugin manager."""
    plugin_manager = MagicMock()
    
    async def mock_trigger_plugin_for_integration(plugin_id, event_data):
        plugin_manager.trigger_plugin_for_integration = AsyncMock()
        plugin_manager.trigger_plugin_for_integration(plugin_id, event_data)
    
    plugin_manager.trigger_plugin_for_integration = mock_trigger_plugin_for_integration
    
    return plugin_manager


@pytest.fixture
def mock_db_session(mocker):
    """Create a mock database session."""
    db = MagicMock()
    
    # Create a mock result class with proper async methods
    class MockResult:
        def __init__(self, integrations=None, triggers=None):
            self._integrations = integrations or []
            self._triggers = triggers or []
            self._call_count = 0
        
        def scalars(self):
            self._call_count += 1
            return self
        
        def all(self):
            if self._call_count == 1:
                return self._integrations
            return []
        
        def scalar_one_or_none(self):
            if self._call_count == 1:
                return self._integrations[0] if self._integrations else None
            return None
        
        def delete(self, obj):
            self._call_count += 1
            return True
    
    # Create proper mock for execute
    def mock_execute(query, *args, **kwargs):
        """Mock execute method with proper async behavior."""
        db._call_count += 1
        
        # Check if query has column descriptions for filtering
        col_desc = getattr(query, 'column_descriptions', None)
        
        if col_desc and hasattr(query, 'column_descriptions'):
            # Check for enabled filtering
            if 'enabled' in query.column_descriptions:
                enabled_value = query.column_descriptions['enabled'].value
                mock_integrations = [i for i in mock_integration if getattr(i, 'enabled', True) == enabled_value]
                result = MockResult(mock_integrations)
            else:
                # Check for TrafficTrigger
                entity = getattr(query, 'entity', None)
                if entity == 'TrafficTrigger':
                    result = MockResult(mock_triggers)
                else:
                    result = MockResult(list(mock_integration.values()))
        else:
            # No column_descriptions - return all integrations
            result = MockResult(list(mock_integration.values()))
        
        return result
    
    db.execute = mock_execute
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = MagicMock()
    
    return db


@pytest.fixture
def mock_integration(db_session):
    """Create mock integrations."""
    mock_db_session = db_session
    
    integration = Integration(
        id=1, name="Test Integration", type="webhook",
        config={"url": "http://test.com"},
        events_subscribed=["server.created"],
        enabled=True,
        total_triggered=0,
        last_triggered_at=None,
        created_at=datetime.now(timezone.utc)
    )
    
    mock_db_session.integrations = {1: integration}
    
    class MockResult:
        def scalars(self):
            return self
        def all(self):
            return list(mock_db_session.integrations.values())
        def scalar_one_or_none(self):
            return mock_db_session.integrations.get(1)
    
    return integration


@pytest.fixture
def mock_triggers():
    """Create mock triggers."""
    class MockTrigger:
        def __init__(self, integrations):
            self.trigger_integrations = integrations
    
    return [MockTrigger([1, 2])]


@pytest.fixture
def mock_plugins():
    """Create mock plugins."""
    plugin = MagicMock()
    plugin.id = 1
    plugin.version = "1.0.0"
    
    return plugin


@pytest.fixture
def mock_traffic_trigger(db_session):
    """Create mock traffic trigger for use in tests."""
    trigger = MagicMock()
    trigger.trigger_integrations = [1, 2, 3]
    
    class MockResult:
        def scalars(self):
            return self
        def all(self):
            return [trigger]
        def scalar_one_or_none(self):
            return trigger
    
    return trigger


@pytest.fixture
def mock_db_session_triggers(mocker):
    """Create mock database session with traffic triggers."""
    db = MagicMock()
    
    # Create a mock result class with proper async behavior for triggers
    class MockResult:
        def __init__(self, triggers=None):
            self._triggers = triggers or []
            self._call_count = 0
        
        def scalars(self):
            self._call_count += 1
            return self
        
        def all(self):
            return self._triggers
    
    # Create proper mock for execute with triggers
    def mock_execute(query, *args, **kwargs):
        """Mock execute method for traffic triggers."""
        db._call_count += 1
        
        # Check for TrafficTrigger column
        entity = getattr(query, 'entity', None)
        col_desc = getattr(query, 'column_descriptions', None)
        
        if entity == 'TrafficTrigger' or (col_desc and 'trigger_integrations' in col_desc):
            mock_triggers = [MagicMock(trigger_integrations=[1, 2, 3])]
            result = MockResult(mock_triggers)
        else:
            result = MockResult([])
        
        return result
    
    db.execute = mock_execute
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = MagicMock()
    
    return db


@pytest.fixture
def service(mock_notification_service, mock_plugin_manager):
    """Create an IntegrationService instance."""
    return IntegrationService(
        notification_service=mock_notification_service,
        plugin_manager=mock_plugin_manager
    )


@pytest.fixture
def event_bus():
    """Mock event bus."""
    event_bus = MagicMock()
    
    async def mock_subscribe(event_type, handler):
        event_bus.subscribe = MagicMock()
        event_bus.subscribe(event_type, handler)
    
    event_bus.subscribe = mock_subscribe
    
    return event_bus
