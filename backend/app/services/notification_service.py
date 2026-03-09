from datetime import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.integration import Integration
from ..models.notification import Notification
from ..models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing in-app notifications."""

    async def create_notification(
        self,
        db: AsyncSession,
        user_id: int,
        title: str,
        message: str,
        type: str = "info",
        link: str | None = None,
        event_type: str | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
        auto_commit: bool = True
    ) -> Notification:
        """
        Create a new notification.
        
        Args:
            db: Database session
            user_id: ID of the user to notify
            title: Notification title
            message: Notification message
            type: Notification type (info, warning, error, success)
            link: Optional link for the notification
            event_type: Optional event type that triggered the notification
            source_type: Optional source resource type (server, peer, etc.)
            source_id: Optional source resource ID
            auto_commit: Whether to commit the transaction automatically (default: True)
            
        Returns:
            Created notification
        """
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            link=link,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id
        )
        db.add(notification)
        
        if auto_commit:
            await db.commit()
            await db.refresh(notification)
        else:
            # Flush to get the ID without committing
            await db.flush()
        
        # Broadcast notification via WebSocket
        await self._broadcast_notification(notification)
        
        return notification
    
    async def _broadcast_notification(self, notification: Notification):
        """Broadcast notification to connected WebSocket clients."""
        try:
            from ..api.ws import broadcast_notification
            
            await broadcast_notification({
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "type": notification.type,
                "link": notification.link,
                "read": notification.read,
                "created_at": notification.created_at.isoformat() if notification.created_at else None
            })
        except Exception as e:
            # Don't fail notification creation if WebSocket broadcast fails
            print(f"Failed to broadcast notification via WebSocket: {e}")

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> list[Notification]:
        """Get notifications for a user."""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.read == False)
        
        query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def mark_as_read(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> Notification | None:
        """Mark a notification as read."""
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification and not notification.read:
            notification.read = True
            notification.read_at = datetime.utcnow()
            await db.commit()
            await db.refresh(notification)
        
        return notification

    async def mark_all_as_read(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """Mark all notifications as read for a user. Returns count of updated notifications."""
        result = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.read == False
            )
        )
        notifications = result.scalars().all()
        
        count = 0
        for notification in notifications:
            notification.read = True
            notification.read_at = datetime.utcnow()
            count += 1
        
        await db.commit()
        return count

    async def delete_notification(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> bool:
        """Delete a notification. Returns True if deleted."""
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            await db.delete(notification)
            await db.commit()
            return True
        
        return False

    async def delete_all_notifications(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """Delete all notifications for a user. Returns count of deleted notifications."""
        result = await db.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        notifications = result.scalars().all()
        
        count = 0
        for notification in notifications:
            await db.delete(notification)
            count += 1
        
        await db.commit()
        return count

    async def get_unread_count(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """Get count of unread notifications for a user."""
        result = await db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.read == False
            )
        )
        return len(result.scalars().all())

    async def notify_from_integration(
        self,
        db: AsyncSession,
        integration: Integration,
        event_data: dict
    ):
        """
        Create notifications for all users based on an integration event.
        
        This is called by the integration dispatcher when a 'notification' type
        integration is triggered.
        """
        # Get all users (in a real app, you might want to filter based on roles/permissions)
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        # Extract event details
        event_type = event_data.get("event_type", "")
        # Handle both old (source_type/source_id/payload) and new (resource_type/resource_id/metadata) formats
        source_type = event_data.get("resource_type") or event_data.get("source_type", "")
        source_id = event_data.get("resource_id") or event_data.get("source_id")
        payload = event_data.get("metadata") or event_data.get("payload", {})
        
        # Build notification message based on event type
        title, message, link = self._build_notification_from_event(
            event_type, source_type, source_id, payload
        )
        
        # Create notification for each user
        for user in users:
            await self.create_notification(
                db=db,
                user_id=user.id,
                title=title,
                message=message,
                type="event",
                link=link,
                event_type=event_type,
                source_type=source_type,
                source_id=source_id,
                auto_commit=False  # Let the integration service handle the commit
            )

    def _build_notification_from_event(
        self,
        event_type: str,
        source_type: str,
        source_id: int | None,
        payload: dict
    ) -> tuple[str, str, str | None]:
        """Build notification title, message, and link from event data."""
        
        # Extract common info
        name = payload.get("name") or f"{source_type} #{source_id}"
        
        # Debug logging
        logger.info(f"Building notification for event '{event_type}': payload={payload}, extracted name='{name}'")
        
        # Map event types to user-friendly notifications
        event_messages = {
            # Server events
            "server.created": (
                "New Server Created", 
                f"Server '{name}' has been created and is ready to use.", 
                f"/servers"
            ),
            "server.edited": (
                "Server Updated", 
                f"Server '{name}' configuration has been updated.", 
                f"/servers"
            ),
            "server.started": (
                "Server Started", 
                f"Server '{name}' is now running and accepting connections.", 
                f"/servers"
            ),
            "server.stopped": (
                "Server Stopped", 
                f"Server '{name}' has been stopped.", 
                f"/servers"
            ),
            "server.reloaded": (
                "Server Reloaded", 
                f"Server '{name}' configuration has been reloaded.", 
                f"/servers"
            ),
            "server.deleted": (
                "Server Deleted", 
                f"Server '{name}' has been permanently deleted.", 
                f"/servers"
            ),
            
            # Peer events
            "peer.created": (
                "New Peer Created", 
                f"Peer '{name}' has been added to the network.", 
                f"/peers"
            ),
            "peer.edited": (
                "Peer Updated", 
                f"Peer '{name}' configuration has been updated.", 
                f"/peers"
            ),
            "peer.deleted": (
                "Peer Deleted", 
                f"Peer '{name}' has been removed from the network.", 
                f"/peers"
            ),
            "peer.connected": (
                "Peer Connected", 
                f"Peer '{name}' has successfully connected to the VPN.", 
                f"/peers"
            ),
            "peer.disconnected": (
                "Peer Disconnected", 
                f"Peer '{name}' has disconnected from the VPN.", 
                f"/peers"
            ),
            "peer.migrated": (
                "Peer Migrated", 
                f"Peer '{name}' has been migrated to a different server.", 
                f"/peers"
            ),
            "peer.traffic_threshold_exceeded": (
                "Traffic Alert", 
                f"Peer '{name}' has exceeded its traffic threshold.", 
                f"/peers"
            ),
            
            # Backup events
            "backup.created": (
                "Backup Created", 
                f"New system backup has been created successfully.", 
                f"/backup"
            ),
            "backup.restored": (
                "Backup Restored", 
                f"System has been restored from backup successfully.", 
                f"/backup"
            ),
            "backup.deleted": (
                "Backup Deleted", 
                f"Backup has been permanently deleted.", 
                f"/backup"
            ),
            
            # Integration events
            "integration.triggered": (
                "Integration Triggered", 
                f"An integration has been triggered by a system event.", 
                f"/integrations"
            ),
            
            # Settings events
            "settings.updated": (
                "Settings Updated", 
                "System settings have been updated successfully.", 
                f"/settings"
            ),
            
            # User events
            "user.login": (
                "User Login", 
                f"User logged in to the system.", 
                None
            ),
            "user.logout": (
                "User Logout", 
                f"User logged out from the system.", 
                None
            ),
            "user.updated": (
                "Profile Updated", 
                f"User profile has been updated.", 
                None
            ),
        }
        
        # Get notification details or use default
        title, message, link = event_messages.get(
            event_type,
            ("System Event", f"A system event has occurred: {event_type.replace('.', ' ').title()}", None)
        )
        
        return title, message, link
