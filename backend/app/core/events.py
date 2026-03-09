import asyncio
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """All possible event types in the system."""
    # Server events
    SERVER_CREATED = "server.created"
    SERVER_EDITED = "server.edited"
    SERVER_DELETED = "server.deleted"
    SERVER_STARTED = "server.started"
    SERVER_STOPPED = "server.stopped"
    SERVER_RELOADED = "server.reloaded"

    # Peer events
    PEER_CREATED = "peer.created"
    PEER_EDITED = "peer.edited"
    PEER_DELETED = "peer.deleted"
    PEER_CONNECTED = "peer.connected"
    PEER_DISCONNECTED = "peer.disconnected"
    PEER_MIGRATED = "peer.migrated"
    PEER_TRAFFIC_EXCEEDED = "peer.traffic_threshold_exceeded"
    
    # Traffic Trigger events
    TRAFFIC_THRESHOLD_EXCEEDED = "traffic.threshold_exceeded"

    # Backup events
    BACKUP_CREATED = "backup.created"
    BACKUP_RESTORED = "backup.restored"
    BACKUP_DELETED = "backup.deleted"

    # Integration events
    INTEGRATION_TRIGGERED = "integration.triggered"

    # Settings events
    SETTINGS_UPDATED = "settings.updated"

    # User events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_UPDATED = "user.updated"


class EventBus:
    """Event bus for publishing and subscribing to events (in-memory)."""

    def __init__(self):
        self._handlers: dict[EventType, list[Callable]] = {}

    async def connect(self):
        """
        Initialize the event bus.
        
        Note: This method exists for backward compatibility.
        The event bus now operates entirely in-memory.
        """
        pass

    async def disconnect(self):
        """Disconnect and cleanup (no-op for in-memory bus)."""
        pass

    async def publish(
        self,
        event_type: EventType,
        source_type: str,
        source_id: int,
        payload: dict[str, Any],
        user_id: int | None = None
    ):
        """
        Publish an event to the event bus (in-memory).

        Args:
            event_type: Type of event
            source_type: Type of resource (e.g., "server", "peer")
            source_id: ID of the resource
            payload: Event data
            user_id: Optional user ID who triggered the event
        """
        event_data = {
            "event_type": event_type.value,
            "source_type": source_type,
            "source_id": source_id,
            "payload": payload,
            "user_id": user_id,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }

        # Call local handlers asynchronously (non-blocking)
        # This prevents database lock issues with SQLite when handlers
        # try to write to the database while the original transaction is still active
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                # Schedule handler as a background task to avoid blocking
                asyncio.create_task(self._run_handler(handler, event_data))
    
    async def _run_handler(self, handler: Callable, event_data: dict):
        """Run an event handler with error handling."""
        try:
            await handler(event_data)
        except Exception as e:
            print(f"Error in event handler: {e}")
            import traceback
            traceback.print_exc()

    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)


# Global event bus instance
event_bus = EventBus()
