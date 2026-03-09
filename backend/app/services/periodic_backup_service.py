"""
Periodic Backup Service

Automatically creates backups at a scheduled time daily.
Runs daily at the time configured in settings (hour and minute).
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import engine
from ..core.events import EventType, event_bus
from ..services.backup_service import BackupService
from ..services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class PeriodicBackupService:
    """
    Background service that creates backups automatically at a scheduled time.
    
    Runs daily at the configured hour:minute, but only if periodic backups are enabled.
    """
    
    def __init__(
        self,
        backup_service: BackupService,
        settings_service: SettingsService
    ):
        """
        Initialize the periodic backup service.
        
        Args:
            backup_service: Service to create backups
            settings_service: Service to get schedule configuration
        """
        self.backup_service = backup_service
        self.settings_service = settings_service
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the background backup task."""
        if self._running:
            logger.warning("Periodic backup service is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._backup_loop())
        logger.info("Periodic backup service started")
        
    async def stop(self):
        """Stop the background backup task."""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Periodic backup service stopped")
        
    async def _backup_loop(self):
        """Main loop that waits for the scheduled time and creates backups."""
        while self._running:
            try:
                # Check if periodic backups are enabled
                async_session = AsyncSession(bind=engine, expire_on_commit=False)
                try:
                    is_enabled = await self.settings_service.is_backup_periodic_enabled(async_session)
                    
                    if not is_enabled:
                        # If disabled, check again in 1 hour
                        logger.debug("Periodic backups are disabled, checking again in 1 hour")
                        await asyncio.sleep(3600)
                        continue
                    
                    # Get scheduled time and frequency
                    frequency = await self.settings_service.get_backup_schedule_frequency(async_session)
                    schedule_hour = await self.settings_service.get_backup_schedule_hour(async_session)
                    schedule_minute = await self.settings_service.get_backup_schedule_minute(async_session)
                    
                finally:
                    await async_session.close()
                
                # Calculate seconds until next scheduled time
                seconds_until_backup = self._calculate_seconds_until_next_backup(
                    frequency, schedule_hour, schedule_minute
                )
                
                frequency_text = {
                    "daily": "daily",
                    "weekly": "weekly on Monday",
                    "monthly": "monthly on the 1st"
                }.get(frequency, frequency)
                
                logger.info(
                    f"Next scheduled backup ({frequency_text}) at {schedule_hour:02d}:{schedule_minute:02d} "
                    f"({seconds_until_backup / 3600:.1f} hours from now)"
                )
                
                # Wait until scheduled time
                await asyncio.sleep(seconds_until_backup)
                
                # Create the backup
                if self._running:
                    await self._create_scheduled_backup()
                    
            except RuntimeError as e:
                if "Please complete the setup wizard" in str(e):
                    # Setup not complete yet, wait and retry
                    logger.debug("Setup not complete, periodic backup service will retry in 1 hour")
                    await asyncio.sleep(3600)
                else:
                    logger.error(f"Error in periodic backup loop: {e}", exc_info=True)
                    await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in periodic backup loop: {e}", exc_info=True)
                # Wait 1 hour before retrying on error
                await asyncio.sleep(3600)
    
    def _calculate_seconds_until_next_backup(self, frequency: str, hour: int, minute: int) -> float:
        """
        Calculate seconds until the next scheduled backup time.
        
        Args:
            frequency: Backup frequency (daily, weekly, monthly)
            hour: Target hour (0-23)
            minute: Target minute (0-59)
            
        Returns:
            Number of seconds until next occurrence of the scheduled time
        """
        now = datetime.now()
        target_time = time(hour=hour, minute=minute)
        
        if frequency == "daily":
            # Create datetime for today at target time
            target_datetime = datetime.combine(now.date(), target_time)
            
            # If target time has already passed today, schedule for tomorrow
            if target_datetime <= now:
                target_datetime += timedelta(days=1)
                
        elif frequency == "weekly":
            # Schedule for next Monday at target time
            target_datetime = datetime.combine(now.date(), target_time)
            days_until_monday = (7 - now.weekday()) % 7  # 0 = Monday
            
            # If it's Monday and time hasn't passed, use today
            if days_until_monday == 0 and target_datetime > now:
                pass  # Use today
            else:
                # Otherwise, schedule for next Monday
                if days_until_monday == 0:
                    days_until_monday = 7
                target_datetime += timedelta(days=days_until_monday)
                
        elif frequency == "monthly":
            # Schedule for 1st of next month at target time
            # If it's the 1st and time hasn't passed, use today
            if now.day == 1:
                target_datetime = datetime.combine(now.date(), target_time)
                if target_datetime <= now:
                    # Move to next month
                    if now.month == 12:
                        target_datetime = datetime(now.year + 1, 1, 1, hour, minute)
                    else:
                        target_datetime = datetime(now.year, now.month + 1, 1, hour, minute)
            else:
                # Move to 1st of next month
                if now.month == 12:
                    target_datetime = datetime(now.year + 1, 1, 1, hour, minute)
                else:
                    target_datetime = datetime(now.year, now.month + 1, 1, hour, minute)
        else:
            # Default to daily if invalid frequency
            target_datetime = datetime.combine(now.date(), target_time)
            if target_datetime <= now:
                target_datetime += timedelta(days=1)
        
        # Calculate difference in seconds
        delta = target_datetime - now
        return delta.total_seconds()
    
    async def _create_scheduled_backup(self):
        """Create an automatic backup."""
        async_session = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            # Check again if still enabled (could have been disabled while waiting)
            is_enabled = await self.settings_service.is_backup_periodic_enabled(async_session)
            if not is_enabled:
                logger.info("Periodic backups were disabled, skipping scheduled backup")
                return
            
            logger.info("Creating scheduled backup...")
            
            # Create backup with system user (user_id = 1, or create a system user)
            # For now, use user_id = 1 (should be the admin user created during setup)
            backup = await self.backup_service.create_backup(
                db=async_session,
                user_id=1,  # System/admin user
                description=f"Automatic backup - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                encrypt=False,
                passphrase=None
            )
            
            await async_session.commit()
            
            logger.info(
                f"Scheduled backup created successfully: {backup.filename} "
                f"({backup.servers_count} servers, {backup.peers_count} peers)"
            )
            
            # Publish event
            await event_bus.publish(
                EventType.BACKUP_CREATED,
                "backup",
                backup.id,
                {
                    "filename": backup.filename,
                    "servers_count": backup.servers_count,
                    "peers_count": backup.peers_count,
                    "scheduled": True,
                    "automatic": True
                },
                user_id=None  # System-initiated backup
            )
            
        except Exception as e:
            logger.error(f"Failed to create scheduled backup: {e}", exc_info=True)
            await async_session.rollback()
        finally:
            await async_session.close()
