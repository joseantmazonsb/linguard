from pydantic import BaseModel, EmailStr, field_validator
from enum import Enum

from ..utils.validation import (
    validate_username,
    validate_password,
    validate_secret_key,
    validate_token_expiry,
    validate_backup_retention_days,
    validate_name,
    validate_endpoint,
    validate_port,
)


class DatabaseType(str, Enum):
    """Supported database types."""
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MYSQL = "mysql"


class ConfigureDatabase(BaseModel):
    """Configure database backend (first step in setup)."""
    database_type: DatabaseType
    database_url: str  # Full database URL


class SetupStatus(BaseModel):
    """Setup status response."""
    setup_completed: bool
    requires_setup: bool
    current_step: str | None = None  # Track which step user is on


class InitializeSetup(BaseModel):
    """Initialize setup with first admin account."""
    username: str
    email: EmailStr
    password: str

    @field_validator('username')
    @classmethod
    def validate_username_field(cls, v):
        return validate_username(v, field_name="Username")

    @field_validator('password')
    @classmethod
    def validate_password_field(cls, v):
        return validate_password(v, field_name="Password")


class ConfigureGlobals(BaseModel):
    """Configure global settings (all application settings)."""
    # DNS Configuration
    dns_primary: str | None = "1.1.1.1"
    dns_secondary: str | None = "8.8.8.8"
    
    # Security Settings
    secret_key: str  # Required - should be generated
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    disable_auth: bool = False
    
    # Logging Settings
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_path: str = "./linguard.log"  # Path to log file
    
    # Backup Settings
    backup_dir: str = "./backups"
    backup_retention_days: int = 30
    backup_auto_cleanup_enabled: bool = True
    backup_periodic_enabled: bool = True
    backup_schedule_frequency: str = "weekly"
    backup_schedule_hour: int = 2
    backup_schedule_minute: int = 0

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key_field(cls, v):
        return validate_secret_key(v, field_name="Secret key")

    @field_validator('access_token_expire_minutes')
    @classmethod
    def validate_token_expiry_field(cls, v):
        return validate_token_expiry(v, field_name="Access token expiry")

    @field_validator('backup_retention_days')
    @classmethod
    def validate_backup_retention_field(cls, v):
        return validate_backup_retention_days(v, field_name="Backup retention days")


class CreateServer(BaseModel):
    """Create first server during setup."""
    name: str
    endpoint: str
    listen_port: int
    ipv4_address: str
    ipv6_address: str | None = None
    dns: str | None = None
    mtu: int | None = None
    persistent_keepalive: int | None = None

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        return validate_name(v, field_name="Server name")

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_field(cls, v):
        return validate_endpoint(v, field_name="Endpoint")

    @field_validator('listen_port')
    @classmethod
    def validate_listen_port_field(cls, v):
        return validate_port(v, field_name="Listen port")


class CreatePeer(BaseModel):
    """Create first peer during setup."""
    server_id: int
    name: str
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    dns: str | None = None
    preshared_key: bool = False

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        return validate_name(v, field_name="Peer name")


class UpdateSetupProgress(BaseModel):
    """Update current setup step."""
    current_step: str


class SetupComplete(BaseModel):
    """Setup completion response."""
    success: bool
    message: str
    backup_id: int | None = None

