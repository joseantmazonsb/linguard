from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


class IntegrationBase(BaseModel):
    name: str
    description: str | None = None
    type: str  # webhook, email, slack, discord, telegram, script, notification
    config: dict
    events_subscribed: list[str]
    enabled: bool = True


class IntegrationCreate(IntegrationBase):
    pass


class IntegrationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    events_subscribed: list[str] | None = None
    enabled: bool | None = None


class IntegrationResponse(IntegrationBase):
    id: int
    total_triggered: int
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime | None

    @field_serializer('created_at', 'updated_at', 'last_triggered_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True


class HookBase(BaseModel):
    """Event subscription (hook) - links events to integrations."""
    integration_id: int
    event_type: str
    enabled: bool = True


class HookCreate(HookBase):
    pass


class HookUpdate(BaseModel):
    enabled: bool | None = None


class HookResponse(HookBase):
    id: int
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
