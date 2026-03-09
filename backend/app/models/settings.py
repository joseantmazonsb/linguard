from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from ..core.database import Base


class GlobalSettings(Base):
    """Global configuration settings stored in database."""

    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True, index=True)

    # DNS Configuration
    dns_primary = Column(String(45), nullable=True)  # IPv4 or IPv6
    dns_secondary = Column(String(45), nullable=True)

    # Database Info (read-only, for display purposes)
    database_type = Column(
        String(20), default="sqlite", nullable=False
    )  # postgresql, sqlite, mysql
    database_url = Column(String(500), nullable=True)  # Database connection URL

    # Security Settings
    secret_key = Column(String(500), nullable=False)  # JWT secret key
    algorithm = Column(String(20), default="HS256", nullable=False)  # JWT algorithm
    access_token_expire_minutes = Column(
        Integer, default=30, nullable=False
    )  # Token expiration
    disable_auth = Column(
        Boolean, default=False, nullable=False
    )  # Disable auth for testing

    # Logging Settings
    log_level = Column(
        String(20), default="INFO", nullable=False
    )  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_path = Column(String(500), default="./linguard.log", nullable=False)  # Path to log file

    # Backup Settings
    backup_dir = Column(String(500), nullable=False)  # Directory for backups
    backup_retention_days = Column(
        Integer, default=30, nullable=False
    )  # Keep backups for N days
    backup_auto_cleanup_enabled = Column(
        Boolean, default=True, nullable=False
    )  # Enable automatic cleanup of old backups
    backup_periodic_enabled = Column(
        Boolean, default=False, nullable=False
    )  # Enable periodic automated backups
    backup_schedule_frequency = Column(
        String(20), default="daily", nullable=False
    )  # Frequency: daily, weekly, monthly
    backup_schedule_hour = Column(
        Integer, default=2, nullable=False
    )  # Hour for scheduled backup (0-23)
    backup_schedule_minute = Column(
        Integer, default=0, nullable=False
    )  # Minute for scheduled backup (0-59)

    # Plugin Settings
    plugins_directory = Column(
        String(500), default="./plugins", nullable=False
    )  # Directory where plugins are stored

    # Traffic Monitoring Settings
    metrics_collection_interval_minutes = Column(
        Integer, default=5, nullable=False
    )  # Metrics collection frequency (5, 15, 30, 60 minutes)
    metrics_retention_days = Column(
        Integer, default=90, nullable=False
    )  # Keep traffic metrics for N days
    metrics_global_notifications_per_hour = Column(
        Integer, default=50, nullable=False
    )  # Global notification rate limit

    # Setup State
    setup_completed = Column(Boolean, default=False, nullable=False)
    setup_current_step = Column(
        String(20), nullable=True
    )  # Track current setup step for resume

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
