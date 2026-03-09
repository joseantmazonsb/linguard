"""
Settings Service for runtime access to GlobalSettings.

This service provides cached access to application settings stored in the database.
Settings are loaded from the database and cached to avoid repeated queries.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.settings import GlobalSettings


class SettingsService:
    """Service for accessing global settings from database"""

    def __init__(self):
        self._cache = None
        self._cache_timestamp = None

    async def get_settings(self, db: AsyncSession) -> GlobalSettings:
        """Get global settings (with caching)"""
        # For now, always fetch fresh. In production, implement caching with TTL
        result = await db.execute(select(GlobalSettings))
        settings = result.scalar_one_or_none()

        if not settings:
            raise RuntimeError(
                "Global settings not found. Please complete the setup wizard first."
            )

        return settings

    async def get_secret_key(self, db: AsyncSession) -> str:
        """Get JWT secret key"""
        settings = await self.get_settings(db)
        return settings.secret_key

    async def get_algorithm(self, db: AsyncSession) -> str:
        """Get JWT algorithm"""
        settings = await self.get_settings(db)
        return settings.algorithm

    async def get_access_token_expire_minutes(self, db: AsyncSession) -> int:
        """Get token expiration time"""
        settings = await self.get_settings(db)
        return settings.access_token_expire_minutes

    async def is_auth_disabled(self, db: AsyncSession) -> bool:
        """Check if authentication is disabled"""
        settings = await self.get_settings(db)
        return settings.disable_auth

    async def get_cors_origins(self, db: AsyncSession) -> list[str]:
        """Get CORS origins as list (hardcoded to allow all)"""
        return ["*"]

    async def get_backup_dir(self, db: AsyncSession) -> str:
        """Get backup directory"""
        settings = await self.get_settings(db)
        return settings.backup_dir

    async def get_backup_retention_days(self, db: AsyncSession) -> int:
        """Get backup retention days"""
        settings = await self.get_settings(db)
        return settings.backup_retention_days

    async def get_wireguard_interface_prefix(self, db: AsyncSession) -> str:
        """Get WireGuard interface prefix (hardcoded to 'wg')"""
        return "wg"

    async def get_log_level(self, db: AsyncSession) -> str:
        """Get log level"""
        settings = await self.get_settings(db)
        return settings.log_level

    async def get_log_path(self, db: AsyncSession) -> str | None:
        """Get log file path"""
        settings = await self.get_settings(db)
        return settings.log_path

    async def is_backup_auto_cleanup_enabled(self, db: AsyncSession) -> bool:
        """Check if automatic backup cleanup is enabled"""
        settings = await self.get_settings(db)
        return settings.backup_auto_cleanup_enabled

    async def is_backup_periodic_enabled(self, db: AsyncSession) -> bool:
        """Check if periodic backups are enabled"""
        settings = await self.get_settings(db)
        return settings.backup_periodic_enabled

    async def get_backup_schedule_frequency(self, db: AsyncSession) -> str:
        """Get the backup schedule frequency (daily, weekly, monthly)"""
        settings = await self.get_settings(db)
        return settings.backup_schedule_frequency

    async def get_backup_schedule_hour(self, db: AsyncSession) -> int:
        """Get the hour for scheduled backups (0-23)"""
        settings = await self.get_settings(db)
        return settings.backup_schedule_hour

    async def get_backup_schedule_minute(self, db: AsyncSession) -> int:
        """Get the minute for scheduled backups (0-59)"""
        settings = await self.get_settings(db)
        return settings.backup_schedule_minute
