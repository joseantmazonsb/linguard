"""
Interface Monitor Service

Monitors WireGuard interfaces in the background and syncs server status 
with the database. Publishes status change events via WebSocket.
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import database as _db
from ..core.events import EventType, event_bus
from ..models.server import Server
from ..services.wireguard import WireGuardService

logger = logging.getLogger(__name__)


class InterfaceMonitorService:
    """
    Background service that monitors WireGuard interfaces and syncs server status.
    
    Runs a periodic check (every 10 seconds) to detect if servers are manually
    started/stopped outside the webapp, and updates the database accordingly.
    """
    
    def __init__(
        self,
        wireguard_service: WireGuardService,
        check_interval_seconds: int = 10
    ):
        """
        Initialize the interface monitor service.
        
        Args:
            wireguard_service: WireGuard service for checking interface status
            check_interval_seconds: How often to check (default: 10 seconds)
        """
        self.wireguard_service = wireguard_service
        self.check_interval_seconds = check_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the background monitoring task."""
        if self._running:
            logger.warning("Interface monitor is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Interface monitor started (checking every {self.check_interval_seconds}s)")
        
    async def stop(self):
        """Stop the background monitoring task."""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Interface monitor stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop that runs periodically."""
        while self._running:
            try:
                await self._check_all_servers()
            except Exception as e:
                logger.error(f"Error in interface monitor loop: {e}", exc_info=True)
            
            # Wait before next check
            await asyncio.sleep(self.check_interval_seconds)
            
    async def _check_all_servers(self):
        """Check all servers and sync their status with actual WireGuard state."""
        async_session = AsyncSession(bind=_db.engine, expire_on_commit=False)
        try:
            # Get all servers from database
            result = await async_session.execute(select(Server))
            servers = list(result.scalars().all())
            
            for server in servers:
                await self._check_server_status(server, async_session)
                
            await async_session.commit()
            
        except Exception as e:
            logger.error(f"Error checking servers: {e}", exc_info=True)
            await async_session.rollback()
        finally:
            await async_session.close()
            
    async def _check_server_status(self, server: Server, db: AsyncSession):
        """
        Check a single server's status and sync with database.
        
        Args:
            server: Server object to check
            db: Database session
        """
        try:
            # Check if interface exists by public key
            actual_interface = self.wireguard_service.find_interface_by_public_key(server.public_key)
            
            old_status = server.status
            
            if actual_interface:
                # Interface exists - server is actually running
                if server.status != "running":
                    logger.info(f"Server '{server.name}' (ID: {server.id}) detected as running (interface: {actual_interface})")
                    server.status = "running"
                    
                    # Publish status change event
                    await event_bus.publish(
                        EventType.SERVER_STARTED,
                        "server",
                        server.id,
                        {
                            "name": server.name,
                            "interface": actual_interface,
                            "status": "running",
                            "detected": True  # Indicates this was auto-detected, not manually started
                        },
                        user_id=None  # System-detected change
                    )
            else:
                # Interface doesn't exist - server is actually stopped
                if server.status == "running":
                    logger.info(f"Server '{server.name}' (ID: {server.id}) detected as stopped")
                    server.status = "stopped"
                    
                    # Publish status change event
                    await event_bus.publish(
                        EventType.SERVER_STOPPED,
                        "server",
                        server.id,
                        {
                            "name": server.name,
                            "status": "stopped",
                            "detected": True  # Indicates this was auto-detected, not manually stopped
                        },
                        user_id=None  # System-detected change
                    )
                    
        except Exception as e:
            logger.error(f"Error checking server {server.id}: {e}", exc_info=True)
