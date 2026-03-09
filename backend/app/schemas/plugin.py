from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class PluginBase(BaseModel):
    """Base plugin schema."""
    name: str
    version: str
    description: str | None = None
    author: str | None = None


class PluginStats(BaseModel):
    """Plugin statistics."""
    total_invocations: int = 0
    total_errors: int = 0
    last_invoked_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None

    @field_serializer('last_invoked_at', 'last_error_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class PluginResponse(PluginBase):
    """Plugin response with full details."""
    id: int
    module_name: str
    file_path: str
    config_schema: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    enabled: bool
    loaded: bool
    subscribed_events: list[str] | None = None
    requirements: list[str] | None = None
    
    # Statistics
    total_invocations: int = 0
    total_errors: int = 0
    last_invoked_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_message: str | None = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime | None

    @field_serializer('last_invoked_at', 'last_error_at', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True


class PluginListItem(BaseModel):
    """Simplified plugin info for list views."""
    id: int
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    enabled: bool
    loaded: bool
    total_invocations: int = 0
    total_errors: int = 0

    class Config:
        from_attributes = True


class PluginListResponse(BaseModel):
    """List of plugins."""
    plugins: list[PluginResponse]
    total: int


class PluginConfigUpdate(BaseModel):
    """Update plugin configuration."""
    config: dict[str, Any] = Field(..., description="Plugin configuration values")


class PluginDiscoverResponse(BaseModel):
    """Response from plugin discovery."""
    newly_discovered: int
    total_plugins: int
    message: str


class PluginEnableResponse(BaseModel):
    """Response from enabling a plugin."""
    success: bool
    message: str
    plugin: PluginResponse | None = None


class PluginDisableResponse(BaseModel):
    """Response from disabling a plugin."""
    success: bool
    message: str


class PluginDeleteResponse(BaseModel):
    """Response from deleting a plugin."""
    success: bool
    message: str
