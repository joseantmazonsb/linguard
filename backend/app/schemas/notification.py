from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class NotificationBase(BaseModel):
    title: str
    message: str
    type: str  # info, success, warning, error, event
    link: str | None = None
    event_type: str | None = None
    source_type: str | None = None
    source_id: int | None = None


class NotificationCreate(NotificationBase):
    user_id: int


class NotificationUpdate(BaseModel):
    read: bool


class NotificationResponse(NotificationBase):
    id: int
    user_id: int
    read: bool
    created_at: datetime
    read_at: datetime | None

    @field_serializer('created_at', 'read_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        # If datetime is naive, assume it's UTC (SQLite stores as naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True
