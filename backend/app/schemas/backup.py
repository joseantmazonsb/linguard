from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class BackupBase(BaseModel):
    """Base backup schema"""
    description: str | None = None


class BackupCreate(BackupBase):
    """Backup creation schema"""
    pass


class BackupResponse(BaseModel):
    """Backup response schema"""
    id: int
    filename: str
    description: str | None = None
    size_bytes: int
    is_encrypted: bool
    servers_count: int = 0
    peers_count: int = 0
    created_by_user_id: int
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True
