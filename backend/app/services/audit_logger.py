
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditLog
from ..models.user import User


class AuditService:
    """Service for comprehensive audit logging."""

    async def log_action(
        self,
        db: AsyncSession,
        user: User,
        action: str,
        resource_type: str,
        resource_id: int | None,
        resource_name: str | None,
        details: dict | None,
        request: Request | None = None,
        status: str = "success",
        error_message: str | None = None
    ):
        """
        Log an administrative action.

        Args:
            db: Database session
            user: User performing the action
            action: Action type (CREATE, UPDATE, DELETE, MIGRATE, etc.)
            resource_type: Type of resource (server, peer, backup, etc.)
            resource_id: ID of the resource
            resource_name: Name of the resource
            details: Additional details (JSON)
            request: Optional FastAPI request object
            status: Action status (success, failed)
            error_message: Optional error message if failed
        """
        ip_address = None
        user_agent = None

        if request:
            # Get client IP
            if request.client:
                ip_address = request.client.host

            # Get user agent
            user_agent = request.headers.get("user-agent")

        audit_log = AuditLog(
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            error_message=error_message
        )

        db.add(audit_log)
        await db.flush()

    def create_change_details(self, old_values: dict, new_values: dict) -> dict:
        """
        Create a details dictionary showing what changed.

        Args:
            old_values: Dictionary of old values
            new_values: Dictionary of new values

        Returns:
            Dictionary with before/after/changes
        """
        changes = {}

        for key in set(old_values.keys()) | set(new_values.keys()):
            old_val = old_values.get(key)
            new_val = new_values.get(key)

            if old_val != new_val:
                changes[key] = {
                    "from": old_val,
                    "to": new_val
                }

        return {
            "before": old_values,
            "after": new_values,
            "changes": changes
        }
