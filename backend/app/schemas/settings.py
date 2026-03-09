from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


class GlobalSettingsBase(BaseModel):
    # DNS Configuration
    dns_primary: str | None = None
    dns_secondary: str | None = None
    
    # Security Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    disable_auth: bool = False
    
    # Logging Settings
    log_level: str = "INFO"
    log_path: str | None = None
    
    # Backup Settings
    backup_dir: str
    backup_retention_days: int = 30
    backup_auto_cleanup_enabled: bool = True
    backup_periodic_enabled: bool = False
    backup_schedule_frequency: str = "daily"
    backup_schedule_hour: int = 2
    backup_schedule_minute: int = 0
    
    # Plugin Settings
    plugins_directory: str = "./plugins"
    
    # Traffic Monitoring Settings
    metrics_collection_interval_minutes: int = 5
    metrics_retention_days: int = 90
    metrics_global_notifications_per_hour: int = 50


class GlobalSettingsUpdate(BaseModel):
    """Settings that can be updated (all optional)"""
    dns_primary: str | None = None
    dns_secondary: str | None = None
    secret_key: str | None = None
    algorithm: str | None = None
    access_token_expire_minutes: int | None = None
    disable_auth: bool | None = None
    log_level: str | None = None
    log_path: str | None = None
    backup_dir: str | None = None
    backup_retention_days: int | None = None
    backup_auto_cleanup_enabled: bool | None = None
    backup_periodic_enabled: bool | None = None
    backup_schedule_frequency: str | None = None
    backup_schedule_hour: int | None = None
    backup_schedule_minute: int | None = None
    plugins_directory: str | None = None
    metrics_collection_interval_minutes: int | None = None
    metrics_retention_days: int | None = None
    metrics_global_notifications_per_hour: int | None = None


class GlobalSettingsResponse(GlobalSettingsBase):
    id: int
    database_type: str  # Read-only, from linguard.config.json
    database_url: str | None = None  # Read-only, database connection string
    setup_completed: bool
    setup_current_step: str | None
    created_at: datetime
    updated_at: datetime | None

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True

