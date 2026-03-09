from datetime import datetime
from typing import Any

from pydantic import BaseModel, computed_field


class AuditLogBase(BaseModel):
    """Base audit log schema"""
    action: str
    resource_type: str
    resource_id: int
    resource_name: str | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditLogResponse(AuditLogBase):
    """Audit log response schema"""
    id: int
    user_id: int | None = None
    status: str = "success"
    error_message: str | None = None
    timestamp: datetime
    
    @computed_field
    @property
    def created_at(self) -> str:
        """Alias timestamp as created_at for frontend compatibility"""
        return self.timestamp.isoformat()
    
    @computed_field
    @property
    def username(self) -> str:
        """Get username from user relationship"""
        return getattr(self, '_username', 'Unknown')

    class Config:
        from_attributes = True
