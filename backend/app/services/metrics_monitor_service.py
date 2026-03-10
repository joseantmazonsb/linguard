"""
Metrics Monitor Service

Background service that periodically:
1. Collects traffic metrics from WireGuard interfaces
2. Checks traffic threshold triggers
3. Cleans up old metrics data
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import database as _db
from ..models.traffic_metric import TrafficMetric
from ..models.settings import GlobalSettings
from ..services.metrics_collector import MetricsCollectorService
from ..services.traffic_threshold_service import TrafficThresholdService
from ..services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class MetricsMonitorService:
    """
    Background service for periodic metrics collection and threshold monitoring.
    
    Runs on a configurable interval (5, 15, 30, or 60 minutes).
    Also handles cleanup of old metrics data based on retention policy.
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollectorService,
        traffic_threshold_service: TrafficThresholdService,
        settings_service: SettingsService
    ):
        """
        Initialize the metrics monitor service.
        
        Args:
            metrics_collector: Service to collect WireGuard metrics
            traffic_threshold_service: Service to check traffic triggers
            settings_service: Service to read settings
        """
        self.metrics_collector = metrics_collector
        self.traffic_threshold_service = traffic_threshold_service
        self.settings_service = settings_service
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_cleanup = datetime.now(timezone.utc)
        
    async def start(self):
        """Start the background monitoring task."""
        if self._running:
            logger.warning("Metrics monitor service is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Metrics monitor service started")
        
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
        logger.info("Metrics monitor service stopped")
        
    async def _monitoring_loop(self):
        """Main monitoring loop that runs periodically."""
        # Wait a bit on startup to let the system initialize
        await asyncio.sleep(10)
        
        while self._running:
            try:
                async_session = AsyncSession(bind=_db.engine, expire_on_commit=False)
                try:
                    # Get collection interval from settings
                    interval_minutes = await self._get_collection_interval(async_session)
                    
                    logger.debug(f"Running metrics collection cycle (interval: {interval_minutes}min)")
                    
                    # 1. Collect metrics from WireGuard
                    await self._collect_metrics(async_session)
                    
                    # 2. Check traffic triggers
                    await self._check_triggers(async_session)
                    
                    # 3. Cleanup old metrics (once per day)
                    await self._cleanup_old_metrics_if_needed(async_session)
                    
                finally:
                    await async_session.close()
                
                # Wait for next collection cycle
                logger.debug(f"Metrics collection cycle complete. Sleeping for {interval_minutes} minutes")
                await asyncio.sleep(interval_minutes * 60)
                
            except RuntimeError as e:
                if "Please complete the setup wizard" in str(e):
                    # Setup not complete yet, wait and retry
                    logger.debug("Setup not complete, metrics monitor will retry in 5 minutes")
                    await asyncio.sleep(300)
                else:
                    logger.error(f"Error in metrics monitoring loop: {e}", exc_info=True)
                    await asyncio.sleep(300)  # Wait 5 minutes before retrying
            except Exception as e:
                logger.error(f"Error in metrics monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def _get_collection_interval(self, db: AsyncSession) -> int:
        """
        Get metrics collection interval from settings.
        
        Returns:
            Interval in minutes (5, 15, 30, or 60)
        """
        try:
            from sqlalchemy import select
            
            result = await db.execute(select(GlobalSettings))
            settings = result.scalar_one_or_none()
            
            if settings and settings.metrics_collection_interval_minutes:
                interval = settings.metrics_collection_interval_minutes
                # Validate interval is one of the allowed values
                if interval in [5, 15, 30, 60]:
                    return interval
                else:
                    logger.warning(
                        f"Invalid metrics_collection_interval_minutes: {interval}. "
                        f"Using default of 5 minutes"
                    )
            
            return 5  # Default to 5 minutes
        except Exception as e:
            logger.error(f"Error reading collection interval from settings: {e}")
            return 5  # Default to 5 minutes
    
    async def _collect_metrics(self, db: AsyncSession):
        """Collect traffic metrics from WireGuard interfaces."""
        try:
            result = await self.metrics_collector.collect_all_metrics(db)
            logger.info(
                f"Metrics collected: {result['servers_updated']} servers, "
                f"{result['peers_updated']} peers"
            )
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}", exc_info=True)
    
    async def _check_triggers(self, db: AsyncSession):
        """Check all traffic threshold triggers."""
        try:
            result = await self.traffic_threshold_service.check_all_triggers(db)
            
            if result['triggers_fired'] > 0:
                logger.info(
                    f"Traffic triggers checked: {result['triggers_checked']} total, "
                    f"{result['triggers_fired']} fired"
                )
            else:
                logger.debug(
                    f"Traffic triggers checked: {result['triggers_checked']} total, "
                    f"none exceeded threshold"
                )
        except Exception as e:
            logger.error(f"Error checking traffic triggers: {e}", exc_info=True)
    
    async def _cleanup_old_metrics_if_needed(self, db: AsyncSession):
        """
        Clean up old metrics data if 24 hours have passed since last cleanup.
        
        Deletes metrics older than the retention period configured in settings.
        """
        now = datetime.now(timezone.utc)
        time_since_cleanup = (now - self._last_cleanup).total_seconds()
        
        # Run cleanup once per day (86400 seconds)
        if time_since_cleanup < 86400:
            return
        
        try:
            logger.info("Starting metrics cleanup...")
            
            # Get retention days from settings
            from sqlalchemy import select
            result = await db.execute(select(GlobalSettings))
            settings = result.scalar_one_or_none()
            
            retention_days = 90  # Default
            if settings and settings.metrics_retention_days:
                retention_days = settings.metrics_retention_days
            
            # Calculate cutoff date
            cutoff_date = now - timedelta(days=retention_days)
            
            # Delete old metrics
            delete_stmt = delete(TrafficMetric).where(
                TrafficMetric.recorded_at < cutoff_date
            )
            result = await db.execute(delete_stmt)
            await db.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(
                    f"Deleted {deleted_count} metrics older than {retention_days} days "
                    f"(before {cutoff_date.strftime('%Y-%m-%d')})"
                )
            else:
                logger.debug(f"No metrics older than {retention_days} days to clean up")
            
            self._last_cleanup = now
            
        except Exception as e:
            logger.error(f"Error during metrics cleanup: {e}", exc_info=True)
