"""
Plugin framework base classes, decorators, and utilities.

This module provides the core infrastructure for the Linguard plugin system.
"""
import functools
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Plugin metadata storage (populated by decorators)
_plugin_registry: Dict[type, "PluginMetadata"] = {}


class PluginMetadata:
    """Metadata for a plugin class."""
    
    def __init__(
        self,
        name: str,
        version: str,
        description: str = "",
        author: str = ""
    ):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.event_handlers: Dict[str, List[Callable]] = {}  # event_type -> [handlers]
    
    def add_event_handler(self, event_types: List[str], handler: Callable):
        """Register an event handler for one or more event types."""
        for event_type in event_types:
            if event_type not in self.event_handlers:
                self.event_handlers[event_type] = []
            self.event_handlers[event_type].append(handler)


def plugin(
    name: str,
    version: str,
    description: str = "",
    author: str = ""
):
    """
    Decorator to mark a class as a plugin.
    
    Usage:
        @plugin(
            name="My Plugin",
            version="1.0.0",
            description="Does something cool",
            author="Your Name"
        )
        class MyPlugin:
            ...
    """
    def decorator(cls):
        # Store metadata
        metadata = PluginMetadata(name, version, description, author)
        _plugin_registry[cls] = metadata
        
        # Add metadata as class attributes for easy access
        cls._plugin_name = name
        cls._plugin_version = version
        cls._plugin_description = description
        cls._plugin_author = author
        cls._plugin_metadata = metadata
        
        return cls
    
    return decorator


def on_event(*event_types: str):
    """
    Decorator to mark a method as an event handler.
    
    Usage:
        @on_event("server.created", "server.started")
        async def handle_server_events(self, event_data: dict):
            ...
    
    Args:
        *event_types: One or more event type strings to subscribe to
                      Use "*" to subscribe to all events
    """
    def decorator(func: Callable):
        # Mark function with event types metadata
        func._event_types = list(event_types)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._event_types = list(event_types)
        wrapper._is_event_handler = True
        
        return wrapper
    
    return decorator


class PluginStorage:
    """Key-value storage API for plugins."""
    
    def __init__(self, plugin_id: int, db_session_factory: Callable):
        """
        Initialize plugin storage.
        
        Args:
            plugin_id: Database ID of the plugin
            db_session_factory: Callable that returns an AsyncSession
        """
        self.plugin_id = plugin_id
        self._db_session_factory = db_session_factory
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from storage."""
        from sqlalchemy import select
        from ..models.plugin import PluginData
        
        async with self._db_session_factory() as session:
            result = await session.execute(
                select(PluginData).where(
                    PluginData.plugin_id == self.plugin_id,
                    PluginData.key == key
                )
            )
            data = result.scalar_one_or_none()
            return data.value if data else default
    
    async def set(self, key: str, value: Any):
        """Set a value in storage."""
        from sqlalchemy import select
        from ..models.plugin import PluginData
        
        async with self._db_session_factory() as session:
            # Check if key exists
            result = await session.execute(
                select(PluginData).where(
                    PluginData.plugin_id == self.plugin_id,
                    PluginData.key == key
                )
            )
            data = result.scalar_one_or_none()
            
            if data:
                # Update existing
                data.value = value
            else:
                # Create new
                data = PluginData(
                    plugin_id=self.plugin_id,
                    key=key,
                    value=value
                )
                session.add(data)
            
            await session.commit()
    
    async def delete(self, key: str):
        """Delete a value from storage."""
        from sqlalchemy import select, delete as sql_delete
        from ..models.plugin import PluginData
        
        async with self._db_session_factory() as session:
            await session.execute(
                sql_delete(PluginData).where(
                    PluginData.plugin_id == self.plugin_id,
                    PluginData.key == key
                )
            )
            await session.commit()
    
    async def list_keys(self) -> List[str]:
        """List all keys for this plugin."""
        from sqlalchemy import select
        from ..models.plugin import PluginData
        
        async with self._db_session_factory() as session:
            result = await session.execute(
                select(PluginData.key).where(
                    PluginData.plugin_id == self.plugin_id
                )
            )
            return [row[0] for row in result.all()]
    
    async def clear(self):
        """Delete all data for this plugin."""
        from sqlalchemy import delete as sql_delete
        from ..models.plugin import PluginData
        
        async with self._db_session_factory() as session:
            await session.execute(
                sql_delete(PluginData).where(
                    PluginData.plugin_id == self.plugin_id
                )
            )
            await session.commit()


class PluginContext:
    """
    Context object provided to all plugin instances.
    
    This provides plugins with access to:
    - Plugin metadata and configuration
    - Logging
    - Key-value storage
    - HTTP client
    - Database session (for read-only queries)
    """
    
    def __init__(
        self,
        plugin_id: int,
        plugin_name: str,
        config: Dict[str, Any],
        storage: PluginStorage,
        db_session_factory: Callable,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.config = config or {}
        self.storage = storage
        self._db_session_factory = db_session_factory
        self.http_client = http_client or httpx.AsyncClient(timeout=10.0)
        
        # Create logger for this plugin
        self.logger = logging.getLogger(f"plugin.{plugin_name}")
    
    def log_info(self, message: str):
        """Log an info message."""
        self.logger.info(message)
    
    def log_warning(self, message: str):
        """Log a warning message."""
        self.logger.warning(message)
    
    def log_error(self, message: str):
        """Log an error message."""
        self.logger.error(message)
    
    def log_debug(self, message: str):
        """Log a debug message."""
        self.logger.debug(message)
    
    async def get_db_session(self) -> AsyncSession:
        """
        Get a database session.
        
        WARNING: Use with caution. Prefer using the KV storage API for plugin data.
        This is primarily for read-only queries of Linguard's data.
        """
        return self._db_session_factory()
    
    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """
        Publish a custom event to the event bus.
        
        This allows plugins to emit their own events that other plugins can listen to.
        """
        from ..core.events import event_bus, EventType
        
        # Try to find matching EventType
        try:
            evt = EventType(event_type)
            await event_bus.publish(
                evt,
                source_type="plugin",
                source_id=self.plugin_id,
                payload=data
            )
        except ValueError:
            # Custom event type not in EventType enum
            # Log warning for now, in future we could support custom events
            self.log_warning(f"Event type '{event_type}' not found in EventType enum")
