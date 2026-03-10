"""Background service for periodic update checking."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .notification_service import NotificationService
from .version_service import VersionService
from ..core import database as _db


class UpdateCheckerService:
    """Background service that periodically checks for updates."""
    
    def __init__(
        self,
        version_service: VersionService,
        notification_service: NotificationService,
        check_interval_hours: int = 6
    ):
        self.version_service = version_service
        self.notification_service = notification_service
        self.check_interval = timedelta(hours=check_interval_hours)
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_notified_version: Optional[str] = None
    
    async def start(self):
        """Start the background update checker."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        print(f"🔄 Update checker started (interval: {self.check_interval.total_seconds() / 3600:.1f}h)")
    
    async def stop(self):
        """Stop the background update checker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("⏹️  Update checker stopped")
    
    async def _check_loop(self):
        """Main loop that checks for updates periodically."""
        # Wait a bit after startup before first check
        await asyncio.sleep(60)  # 1 minute initial delay
        
        while self._running:
            try:
                await self._check_and_notify()
            except Exception as e:
                print(f"❌ Error in update checker: {e}")
            
            # Wait for next check
            await asyncio.sleep(self.check_interval.total_seconds())
    
    async def _check_and_notify(self):
        """Check for updates and send notification if available."""
        try:
            # Check for updates
            update_info = await self.version_service.check_for_updates()
            
            if update_info.get("update_available"):
                latest_version = update_info.get("latest_version")
                
                # Only notify if this is a new version we haven't notified about yet
                if latest_version and latest_version != self._last_notified_version:
                    async with _db.AsyncSessionLocal() as db:
                        try:
                            # Get the first user (admin) to send notification to
                            # In a multi-user system, you might want to notify all admins
                            from sqlalchemy import select
                            from ..models.user import User
                            
                            result = await db.execute(select(User).limit(1))
                            user = result.scalar_one_or_none()
                            
                            if user:
                                # Create notification
                                await self.notification_service.create_notification(
                                    db=db,
                                    user_id=user.id,
                                    title="Update Available",
                                    message=f"Version {latest_version} is now available. Current version: {update_info.get('current_version')}",
                                    type="info",
                                    link=update_info.get("release_url")
                                )
                                
                                await db.commit()
                                
                                # Remember we notified about this version
                                self._last_notified_version = latest_version
                                
                                print(f"📢 Update notification sent: v{latest_version}")
                            else:
                                print("⚠️  No users found to notify about update")
                                
                        except Exception as e:
                            print(f"❌ Error creating update notification: {e}")
                            await db.rollback()
                            
            else:
                # No updates available or error checking
                if update_info.get("error"):
                    print(f"⚠️  Update check error: {update_info['error']}")
                else:
                    print(f"✅ No updates available (current: {update_info.get('current_version')})")
                    
        except Exception as e:
            print(f"❌ Error checking for updates: {e}")
