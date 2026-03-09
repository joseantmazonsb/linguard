"""
Backup Cleanup Service

Periodically removes old backup files based on the configured retention period.
Runs daily to clean up backups older than the retention_days setting.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import engine
from ..core.events import EventType, event_bus
from ..models.backup import Backup
from ..services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class BackupCleanupService:
    """
    Background service that periodically cleans up old backups.
    
    Runs a daily check to delete backups older than the configured retention period.
    """
    
    def __init__(
        self,
        settings_service: SettingsService,
        check_interval_hours: int = 24
    ):
        """
        Initialize the backup cleanup service.
        
        Args:
            settings_service: Settings service to get retention period and backup directory
            check_interval_hours: How often to check (default: 24 hours = daily)
        """
        self.settings_service = settings_service
        self.check_interval_seconds = check_interval_hours * 3600
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the background cleanup task."""
        if self._running:
            logger.warning("Backup cleanup service is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Backup cleanup service started (checking every {self.check_interval_seconds / 3600}h)")
        
    async def stop(self):
        """Stop the background cleanup task."""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Backup cleanup service stopped")
        
    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically."""
        while self._running:
            try:
                await self._cleanup_old_backups()
            except RuntimeError as e:
                if "Please complete the setup wizard" in str(e):
                    # Setup not complete yet, silently skip
                    logger.debug("Setup not complete, backup cleanup service will retry later")
                else:
                    logger.error(f"Error in backup cleanup loop: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Error in backup cleanup loop: {e}", exc_info=True)
            
            # Wait before next check
            await asyncio.sleep(self.check_interval_seconds)
            
    async def _cleanup_old_backups(self):
        """Remove backups older than the retention period."""
        async_session = AsyncSession(bind=engine, expire_on_commit=False)
        try:
            # Check if auto cleanup is enabled
            is_enabled = await self.settings_service.is_backup_auto_cleanup_enabled(async_session)
            
            if not is_enabled:
                logger.debug("Automatic backup cleanup is disabled")
                return
            
            # Get retention days from settings
            retention_days = await self.settings_service.get_backup_retention_days(async_session)
            
            if retention_days <= 0:
                logger.debug("Backup retention is disabled (retention_days <= 0)")
                return
            
            # Get backup directory
            backup_dir = await self.settings_service.get_backup_dir(async_session)
            
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            
            # Find old backups
            result = await async_session.execute(
                select(Backup).where(Backup.created_at < cutoff_date)
            )
            old_backups = list(result.scalars().all())
            
            if not old_backups:
                logger.debug(f"No backups older than {retention_days} days found")
                return
            
            logger.info(f"Found {len(old_backups)} backup(s) older than {retention_days} days, cleaning up...")
            
            deleted_count = 0
            failed_count = 0
            
            for backup in old_backups:
                try:
                    # Delete physical file
                    filepath = os.path.join(backup_dir, backup.filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.info(f"Deleted old backup file: {backup.filename} (created {backup.created_at})")
                    else:
                        logger.warning(f"Backup file not found (will remove DB record): {filepath}")
                    
                    # Delete database record
                    await async_session.delete(backup)
                    deleted_count += 1
                    
                    # Publish event
                    await event_bus.publish(
                        EventType.BACKUP_DELETED,
                        "backup",
                        backup.id,
                        {
                            "filename": backup.filename,
                            "age_days": (datetime.utcnow() - backup.created_at).days,
                            "auto_cleanup": True
                        },
                        user_id=None  # System-initiated cleanup
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup.filename}: {e}", exc_info=True)
                    failed_count += 1
            
            await async_session.commit()
            
            logger.info(f"Backup cleanup completed: {deleted_count} deleted, {failed_count} failed")
            
        except RuntimeError as e:
            if "Please complete the setup wizard" in str(e):
                # Setup not complete yet, silently skip
                logger.debug("Setup not complete, skipping backup cleanup")
            else:
                logger.error(f"Error during backup cleanup: {e}", exc_info=True)
                await async_session.rollback()
        except Exception as e:
            logger.error(f"Error during backup cleanup: {e}", exc_info=True)
            await async_session.rollback()
        finally:
            await async_session.close()
