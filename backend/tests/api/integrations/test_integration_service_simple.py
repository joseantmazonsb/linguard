"""
Simple tests for IntegrationService that don't require complex fixtures.
Used to get basic coverage for integration_service.py.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
from app.services.integration_service import IntegrationService
from app.models.integration import Integration
from app.core.events import EventType


class MockResult:
    """Mock database result."""
    def __init__(self, items=None, item=None):
        self._items = items or []
        self._item = item
    
    def all(self):
        return self._items
    
    def scalar_one_or_none(self):
        return self._item
    
    def scalars(self):
        return self


class MockDB:
    """In-memory stand-in for an AsyncSession.

    Queries are inspected through their compiled parameters so that the same
    ``select(...).where(...)`` calls used in production are honoured without
    needing a real database for these focused unit tests.
    """

    def __init__(self, integrations=None, triggers=None):
        self._integrations = integrations or []
        self._triggers = triggers or []
        self.deleted = []

    @staticmethod
    def _entity_name(query):
        try:
            entity = query.column_descriptions[0].get("entity")
        except (AttributeError, IndexError, KeyError):
            return None
        return getattr(entity, "__name__", None)

    async def execute(self, query):
        params = query.compile().params if hasattr(query, "compile") else {}

        if self._entity_name(query) == "TrafficTrigger":
            items = list(self._triggers)
        else:
            items = list(self._integrations)

        for key, value in params.items():
            column = key.rsplit("_", 1)[0]
            items = [i for i in items if getattr(i, column, None) == value]

        if "id" in {k.rsplit("_", 1)[0] for k in params}:
            return MockResult(items, items[0] if items else None)
        return MockResult(items)
    
    async def add(self, obj):
        return None
    
    async def commit(self):
        return None
    
    async def refresh(self, obj):
        return None
    
    async def delete(self, obj):
        self.deleted.append(obj)
        return True


@pytest.mark.asyncio
async def test_get_integrations_empty():
    """Test getting all integrations when there are none."""
    mock_db = MockDB([])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    integrations = await service.get_integrations(mock_db)
    
    assert integrations == []


@pytest.mark.asyncio
async def test_get_integrations_with_enabled_filter():
    """Test getting only enabled integrations."""
    mock_db = MockDB([
        Integration(
            id=1, name="Test", type="webhook",
            config={}, events_subscribed=[], enabled=True,
            total_triggered=0, last_triggered_at=None,
            created_at=datetime.now(timezone.utc)
        )
    ])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    integrations = await service.get_integrations(mock_db, enabled_only=True)
    
    assert len(integrations) == 1


@pytest.mark.asyncio
async def test_get_integrations_without_enabled_filter():
    """Test getting all integrations without enabled filter."""
    mock_db = MockDB([
        Integration(
            id=1, name="Test", type="webhook",
            config={}, events_subscribed=[], enabled=False,
            total_triggered=0, last_triggered_at=None,
            created_at=datetime.now(timezone.utc)
        )
    ])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    integrations = await service.get_integrations(mock_db, enabled_only=False)
    
    assert len(integrations) == 1


@pytest.mark.asyncio
async def test_get_integration_not_found():
    """Test getting integration that doesn't exist."""
    mock_db = MockDB([])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    integration = await service.get_integration(mock_db, 999)
    
    assert integration is None


@pytest.mark.asyncio
async def test_create_integration():
    """Test creating a new integration."""
    mock_db = MockDB([])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    created = await service.create_integration(
        db=mock_db,
        name="Test",
        type="webhook",
        config={"url": "https://example.com"},
        events_subscribed=["server.created"],
        description="Test",
        enabled=True,
        plugin_id=None
    )
    
    assert created.name == "Test"
    assert created.type == "webhook"


@pytest.mark.asyncio
async def test_update_integration_not_found():
    """Test updating non-existing integration returns None."""
    mock_db = MockDB([])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    updated = await service.update_integration(mock_db, 999)
    
    assert updated is None


@pytest.mark.asyncio
async def test_delete_integration_not_found():
    """Test deleting non-existing integration returns False."""
    mock_db = MockDB([])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    success = await service.delete_integration(mock_db, 999)
    
    assert success is False


@pytest.mark.asyncio
async def test_delete_integration_no_triggers():
    """Test deleting integration when no triggers reference it."""
    mock_db = MockDB([
        Integration(
            id=1, name="Test", type="webhook",
            config={}, events_subscribed=[], enabled=True,
            total_triggered=0, last_triggered_at=None,
            created_at=datetime.now(timezone.utc)
        )
    ], [])
    
    service = IntegrationService(notification_service=MagicMock(), plugin_manager=None)
    success = await service.delete_integration(mock_db, 1)
    
    assert success is True
    assert mock_db.deleted[0].id == 1
