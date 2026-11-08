"""
Traffic Threshold Service

Manages traffic thresholds for triggering webhooks when traffic limits are exceeded.
Monitors traffic metrics against configured thresholds and triggers integrations when limits are breached.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..core.events import EventType, event_bus
from ..models.traffic_trigger import TrafficScope, TrafficTrigger
from ..models.traffic_metric import TrafficMetric

logger = logging.getLogger(__name__)

# Relationship options required whenever triggers are turned into API
# responses: an async session cannot lazily load them afterwards.
_EAGER_RELATIONSHIPS = (
    selectinload(TrafficTrigger.peer),
    selectinload(TrafficTrigger.server),
)


class TrafficDirection(str, Enum):
    """Direction of traffic monitoring."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    COMBINED = "combined"


class TimeWindow(str, Enum):
    """Time window for threshold evaluation."""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


class TrafficThresholdService:
    """
    Service for managing and evaluating traffic thresholds.
    
    Evaluates traffic metrics against configured thresholds and determines
    whether thresholds have been exceeded within specified time windows.
    """
    
    MIN_COOLDOWN_MINUTES = 1
    
    def __init__(self):
        """Initialize the traffic threshold service."""
        self._cached_metrics: Dict[str, Dict] = {}
        self._last_cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
    
    async def evaluate_threshold(
        self,
        threshold_bytes: int,
        metrics: Dict[str, Dict],
        time_window: str = TimeWindow.LAST_HOUR.value,
        direction: TrafficDirection = TrafficDirection.COMBINED,
    ) -> bool:
        """
        Evaluate if traffic threshold has been exceeded.
        
        Args:
            threshold_bytes: The threshold value in bytes to compare against
            metrics: Traffic metrics data including rx_bytes, tx_bytes, timestamps
            time_window: Time window for evaluation (last_hour, last_24_hours, etc.)
            direction: Direction of traffic (inbound, outbound, or combined)
            
        Returns:
            True if threshold has been exceeded, False otherwise
            
        Raises:
            ValueError: If threshold_bytes is invalid or time_window is unknown
            ValueError: If metrics data is missing required fields
        """
        # Validate threshold_bytes
        if not self._validate_threshold_bytes(threshold_bytes):
            raise ValueError("threshold_bytes must be a positive number")
        
        # Validate time_window
        if not self._validate_time_window(time_window):
            raise ValueError(f"Invalid time window: {time_window}")
        
        # Validate metrics data
        if not self._validate_metrics(metrics):
            raise ValueError("Invalid metrics data")
        
        # Get relevant metrics based on direction
        relevant_metrics = self._get_relevant_metrics(metrics, direction)
        
        # Calculate total traffic for the requested direction
        if direction == TrafficDirection.INBOUND:
            total_bytes = sum(metric.get("rx_bytes", 0) for metric in relevant_metrics)
        elif direction == TrafficDirection.OUTBOUND:
            total_bytes = sum(metric.get("tx_bytes", 0) for metric in relevant_metrics)
        else:
            total_bytes = sum(
                metric.get("rx_bytes", 0) + metric.get("tx_bytes", 0)
                for metric in relevant_metrics
            )
        
        # Compare against threshold
        return total_bytes >= threshold_bytes
    
    def _validate_threshold_bytes(self, threshold_bytes: int) -> bool:
        """
        Validate threshold_bytes value.
        
        Args:
            threshold_bytes: The threshold value to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(threshold_bytes, (int, float)):
            return False
        if threshold_bytes <= 0:
            return False
        return True
    
    def _validate_time_window(self, time_window: str) -> bool:
        """
        Validate time window value.
        
        Args:
            time_window: The time window to validate
            
        Returns:
            True if valid, False otherwise
        """
        valid_windows = [w.value for w in TimeWindow]
        return time_window in valid_windows
    
    def _validate_metrics(self, metrics: Dict[str, Dict]) -> bool:
        """
        Validate metrics data structure.
        
        Args:
            metrics: Metrics data to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(metrics, dict):
            return False
        
        for peer_id, peer_metrics in metrics.items():
            if not isinstance(peer_metrics, dict):
                return False
            if "rx_bytes" not in peer_metrics or "tx_bytes" not in peer_metrics:
                return False
            if not isinstance(peer_metrics["rx_bytes"], (int, float)) or \
               not isinstance(peer_metrics["tx_bytes"], (int, float)):
                return False
        
        return True
    
    def _get_relevant_metrics(
        self,
        metrics: Dict[str, Dict],
        direction: TrafficDirection,
        time_window: str = TimeWindow.LAST_HOUR.value,
    ) -> List[Dict]:
        """
        Filter metrics based on direction and time window.
        
        Args:
            metrics: Raw metrics data
            direction: Direction to filter by
            time_window: Time window for filtering
            
        Returns:
            List of relevant metrics
        """
        if direction == TrafficDirection.COMBINED:
            # Return all metrics
            return list(metrics.values())
        
        # For inbound/outbound, filter based on rx_bytes/tx_bytes
        relevant_metrics = []
        for peer_id, peer_metrics in metrics.items():
            # Get all metrics for this peer
            all_metrics = self._get_all_peer_metrics(metrics.get(peer_id, {}))
            
            # Filter based on direction
            filtered_metrics = []
            for metric in all_metrics:
                if direction == TrafficDirection.INBOUND:
                    if metric.get("rx_bytes", 0) > 0:
                        filtered_metrics.append(metric)
                elif direction == TrafficDirection.OUTBOUND:
                    if metric.get("tx_bytes", 0) > 0:
                        filtered_metrics.append(metric)
            
            relevant_metrics.extend(filtered_metrics)
        
        return relevant_metrics
    
    def _get_all_peer_metrics(self, peer_metrics: Dict) -> List[Dict]:
        """
        Extract all traffic metrics for a peer.
        
        Args:
            peer_metrics: Peer metrics data
            
        Returns:
            List of traffic metrics
        """
        metrics = []
        
        # Handle different metric structures
        if "metrics" in peer_metrics:
            metrics = peer_metrics["metrics"]
        elif "traffic" in peer_metrics:
            metrics = peer_metrics["traffic"]
        elif peer_metrics:
            # Assume single metric data
            metrics = [peer_metrics]
        
        return metrics
    
    def get_threshold_recommendation(
        self,
        current_bytes: int,
        time_window: str = TimeWindow.LAST_HOUR.value,
    ) -> Dict:
        """
        Get recommended threshold based on current traffic.
        
        Args:
            current_bytes: Current traffic in bytes
            time_window: Time window for the current traffic
            
        Returns:
            Dictionary with recommended threshold value and metadata
        """
        if current_bytes <= 0:
            return {
                "recommended_threshold": 0,
                "reason": "No traffic detected",
                "safety_margin": 0,
            }
        
        # Apply safety margin (10% above current traffic)
        safety_margin = int(current_bytes * 0.1)
        recommended = current_bytes + safety_margin
        
        return {
            "recommended_threshold": recommended,
            "reason": f"Based on current traffic with 10% safety margin",
            "safety_margin": safety_margin,
            "current_traffic": current_bytes,
        }
    
    def calculate_traffic_percent(
        self,
        current_bytes: int,
        threshold_bytes: int,
    ) -> float:
        """
        Calculate percentage of threshold currently used.
        
        Args:
            current_bytes: Current traffic in bytes
            threshold_bytes: Configured threshold
            
        Returns:
            Percentage (0-100) of threshold used, or 0 if threshold is 0
        """
        if threshold_bytes <= 0:
            return 0.0
        
        return (current_bytes / threshold_bytes) * 100.0
    
    def format_traffic_bytes(self, bytes_value: int) -> str:
        """
        Format bytes to human-readable string.
        
        Args:
            bytes_value: Bytes value to format
            
        Returns:
            Human-readable string (e.g., "1.5 GB")
        """
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(bytes_value)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if size == int(size):
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    async def evaluate_peer_thresholds(
        self,
        peer_id: str,
        peer_metrics: Dict,
        thresholds: List[Dict],
    ) -> List[Dict]:
        """
        Evaluate multiple thresholds for a single peer.
        
        Args:
            peer_id: Peer identifier
            peer_metrics: Metrics for the peer
            thresholds: List of threshold configurations to evaluate
            
        Returns:
            List of evaluation results with threshold details and status
        """
        results = []
        
        for threshold_config in thresholds:
            try:
                threshold_bytes = threshold_config.get("threshold_bytes", 0)
                time_window = threshold_config.get("time_window", TimeWindow.LAST_HOUR.value)
                direction = threshold_config.get("direction", TrafficDirection.COMBINED)
                enabled = threshold_config.get("enabled", True)
                
                if not enabled:
                    results.append({
                        "threshold_bytes": threshold_bytes,
                        "time_window": time_window,
                        "direction": direction,
                        "exceeded": False,
                        "status": "skipped",
                        "reason": "Threshold is disabled",
                    })
                    continue
                
                exceeded = await self.evaluate_threshold(
                    threshold_bytes=threshold_bytes,
                    metrics={peer_id: peer_metrics},
                    time_window=time_window,
                    direction=direction,
                )
                
                results.append({
                    "threshold_bytes": threshold_bytes,
                    "time_window": time_window,
                    "direction": direction,
                    "exceeded": exceeded,
                    "status": "evaluated",
                    "current_bytes": self._get_current_bytes(peer_metrics),
                })
                
            except Exception as e:
                results.append({
                    "threshold_bytes": 0,
                    "time_window": TimeWindow.LAST_HOUR.value,
                    "direction": TrafficDirection.COMBINED.value,
                    "exceeded": False,
                    "status": "error",
                    "reason": str(e),
                })
        
        return results
    
    def _get_current_bytes(self, metrics: Dict) -> int:
        """
        Get current total bytes from metrics.
        
        Args:
            metrics: Metrics data
            
        Returns:
            Total bytes (rx + tx)
        """
        if not metrics:
            return 0
        
        total_rx = metrics.get("rx_bytes", 0)
        total_tx = metrics.get("tx_bytes", 0)
        
        return int(total_rx + total_tx)
    
    def get_time_window_description(self, time_window: str) -> str:
        """
        Get human-readable description of time window.
        
        Args:
            time_window: Time window value
            
        Returns:
            Human-readable description
        """
        descriptions = {
            TimeWindow.LAST_HOUR.value: "Last hour",
            TimeWindow.LAST_24_HOURS.value: "Last 24 hours",
            TimeWindow.LAST_7_DAYS.value: "Last 7 days",
            TimeWindow.LAST_30_DAYS.value: "Last 30 days",
        }
        return descriptions.get(time_window, "Unknown period")
    
    def validate_threshold_config(self, config: Dict) -> List[str]:
        """
        Validate a threshold configuration.
        
        Args:
            config: Threshold configuration dictionary
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check required fields
        if "threshold_bytes" not in config:
            errors.append("threshold_bytes is required")
        if "time_window" not in config:
            errors.append("time_window is required")
        
        # Validate threshold_bytes
        if "threshold_bytes" in config:
            threshold_bytes = config["threshold_bytes"]
            if not self._validate_threshold_bytes(threshold_bytes):
                errors.append("threshold_bytes must be a positive number")
        
        # Validate time_window
        if "time_window" in config:
            time_window = config["time_window"]
            if not self._validate_time_window(time_window):
                errors.append(f"Invalid time window: {time_window}")
        
        # Validate direction if present
        if "direction" in config:
            direction = config["direction"]
            if direction not in [d.value for d in TrafficDirection]:
                errors.append(f"Invalid direction: {direction}")
        
        return errors
    
    async def batch_evaluate_thresholds(
        self,
        peer_ids: List[str],
        peer_metrics: Dict[str, Dict],
        thresholds: List[Dict],
    ) -> Dict[str, List[Dict]]:
        """
        Evaluate thresholds for multiple peers in batch.
        
        Args:
            peer_ids: List of peer identifiers
            peer_metrics: Metrics for all peers indexed by peer_id
            thresholds: List of threshold configurations
            
        Returns:
            Dictionary mapping peer_id to list of evaluation results
        """
        results = {}
        
        for peer_id in peer_ids:
            peer_data = peer_metrics.get(peer_id, {})
            
            # Check if peer has data
            if not peer_data:
                results[peer_id] = [{
                    "threshold_bytes": 0,
                    "time_window": TimeWindow.LAST_HOUR.value,
                    "direction": TrafficDirection.COMBINED.value,
                    "exceeded": False,
                    "status": "no_data",
                    "reason": "No metrics data for peer",
                }]
                continue
            
            results[peer_id] = await self.evaluate_peer_thresholds(
                peer_id=peer_id,
                peer_metrics=peer_data,
                thresholds=thresholds,
            )
        
        return results


    # ------------------------------------------------------------------
    # CRUD operations used by the traffic-triggers API
    # ------------------------------------------------------------------

    async def list_triggers(
        self,
        db: AsyncSession,
        enabled_only: bool = False,
        scope: Optional[TrafficScope] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TrafficTrigger]:
        """List traffic triggers with optional filtering."""
        from ..models.peer import Peer
        from ..models.server import Server

        query = select(TrafficTrigger).options(*_EAGER_RELATIONSHIPS)
        if enabled_only:
            query = query.where(TrafficTrigger.enabled.is_(True))
        if scope is not None:
            query = query.where(TrafficTrigger.scope == scope)
        if search:
            pattern = f"%{search}%"
            query = query.outerjoin(Peer, TrafficTrigger.peer_id == Peer.id)
            query = query.outerjoin(Server, TrafficTrigger.server_id == Server.id)
            query = query.where(
                TrafficTrigger.name.ilike(pattern)
                | Peer.name.ilike(pattern)
                | Server.name.ilike(pattern)
            )
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().unique().all())

    async def get_trigger(self, db: AsyncSession, trigger_id: int) -> Optional[TrafficTrigger]:
        """Get a traffic trigger by ID, or None if it does not exist."""
        result = await db.execute(
            select(TrafficTrigger)
            .options(*_EAGER_RELATIONSHIPS)
            .where(TrafficTrigger.id == trigger_id)
        )
        return result.scalar_one_or_none()

    async def create_trigger(self, db: AsyncSession, **data) -> TrafficTrigger:
        """Create a new traffic trigger."""
        trigger = TrafficTrigger(**data)
        db.add(trigger)
        await db.commit()
        # Re-read with relationships loaded: the ORM cannot lazily load them
        # from an async session, and API responses include peer/server names.
        return await self.get_trigger(db, trigger.id)

    async def update_trigger(self, db: AsyncSession, trigger_id: int, **data) -> Optional[TrafficTrigger]:
        """Update an existing traffic trigger, or None if it does not exist."""
        trigger = await self.get_trigger(db, trigger_id)
        if not trigger:
            return None
        for field, value in data.items():
            setattr(trigger, field, value)
        await db.commit()
        return await self.get_trigger(db, trigger_id)

    async def delete_trigger(self, db: AsyncSession, trigger_id: int) -> bool:
        """Delete a traffic trigger. Returns False if it did not exist."""
        trigger = await self.get_trigger(db, trigger_id)
        if not trigger:
            return False
        await db.delete(trigger)
        await db.commit()
        return True

    async def check_all_triggers(self, db: AsyncSession) -> Dict:
        """Evaluate every enabled trigger against recorded traffic.

        Called periodically by ``MetricsMonitorService``. For each trigger the
        traffic of its scope is summed over its window; when the threshold is
        exceeded (and the cooldown has elapsed) the trigger counters are
        updated and ``TRAFFIC_THRESHOLD_EXCEEDED`` is published on the event
        bus, which fans out to the configured integrations.
        """
        result = await db.execute(
            select(TrafficTrigger)
            .options(*_EAGER_RELATIONSHIPS)
            .where(TrafficTrigger.enabled == True)  # noqa: E712 (SQL boolean)
        )
        triggers = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        checked = 0
        fired = 0
        fired_names: List[str] = []

        for trigger in triggers:
            checked += 1
            trigger.last_checked_at = now

            if self._is_in_cooldown(trigger):
                logger.debug(
                    "Trigger '%s' is cooling down, skipping", trigger.name
                )
                continue

            try:
                traffic = await self.calculate_traffic_in_window(
                    db=db,
                    scope=trigger.scope,
                    direction=trigger.direction,
                    window=trigger.window,
                    peer_id=trigger.peer_id,
                    server_id=trigger.server_id,
                )
            except Exception as exc:  # one bad trigger must not stop the rest
                logger.error("Error evaluating trigger '%s': %s", trigger.name, exc)
                continue

            total_bytes = traffic["total_bytes"]
            if total_bytes < trigger.threshold_bytes:
                continue

            trigger.last_triggered_at = now
            trigger.total_triggers = (trigger.total_triggers or 0) + 1
            fired += 1
            fired_names.append(trigger.name)

            logger.info(
                "Trigger '%s' exceeded: %s >= %s bytes",
                trigger.name, total_bytes, trigger.threshold_bytes,
            )

            if trigger.trigger_event:
                await event_bus.publish(
                    EventType.TRAFFIC_THRESHOLD_EXCEEDED,
                    "traffic_trigger",
                    trigger.id,
                    {
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "scope": getattr(trigger.scope, "value", str(trigger.scope)),
                        "peer_id": trigger.peer_id,
                        "server_id": trigger.server_id,
                        "direction": getattr(
                            trigger.direction, "value", str(trigger.direction)
                        ),
                        "window": getattr(trigger.window, "value", str(trigger.window)),
                        "threshold_bytes": trigger.threshold_bytes,
                        "total_bytes": total_bytes,
                        "rx_bytes": traffic["rx_bytes"],
                        "tx_bytes": traffic["tx_bytes"],
                        "integration_ids": trigger.trigger_integrations or [],
                        "total_triggers": trigger.total_triggers,
                    },
                    user_id=None,
                )

        await db.commit()

        return {
            "triggers_checked": checked,
            "triggers_fired": fired,
            "fired": fired_names,
        }

    async def calculate_traffic_in_window(
        self,
        db: AsyncSession,
        scope: TrafficScope,
        direction,
        window,
        peer_id: Optional[int] = None,
        server_id: Optional[int] = None,
    ) -> Dict:
        """Sum recorded traffic metrics for a scope over a time window."""
        deltas = {
            TimeWindow.LAST_HOUR: timedelta(hours=1),
            TimeWindow.LAST_24_HOURS: timedelta(hours=24),
            TimeWindow.LAST_7_DAYS: timedelta(days=7),
            TimeWindow.LAST_30_DAYS: timedelta(days=30),
        }
        # ``window`` may be the model enum (ThresholdWindow) or the service
        # enum (TimeWindow); both expose a ``value``.
        window_value = window.value if hasattr(window, "value") else str(window)
        delta = None
        for key, value in deltas.items():
            if key.value == window_value:
                delta = value
                break
        if delta is None:
            delta = timedelta(hours=1)

        since = datetime.now(timezone.utc) - delta
        query = select(TrafficMetric).where(TrafficMetric.recorded_at >= since)
        if scope == TrafficScope.PEER and peer_id is not None:
            query = query.where(TrafficMetric.peer_id == peer_id)
        elif scope == TrafficScope.SERVER and server_id is not None:
            query = query.where(TrafficMetric.server_id == server_id)

        result = await db.execute(query)
        metrics = result.scalars().all()
        rx = sum(m.rx_bytes for m in metrics)
        tx = sum(m.tx_bytes for m in metrics)
        direction_value = direction.value if hasattr(direction, "value") else str(direction)
        # Triggers store rx_only/tx_only (TrafficTrigger.direction) while this
        # service also exposes inbound/outbound; accept both spellings.
        if direction_value in ("inbound", "rx_only"):
            total = rx
        elif direction_value in ("outbound", "tx_only"):
            total = tx
        else:
            total = rx + tx
        return {
            "total_bytes": total,
            "rx_bytes": rx,
            "tx_bytes": tx,
            "window": window_value,
        }

    def _is_in_cooldown(self, trigger: TrafficTrigger) -> bool:
        """Check whether the trigger fired recently and is still cooling down."""
        if not trigger.last_triggered_at:
            return False
        last = trigger.last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < last + timedelta(seconds=trigger.cooldown_seconds or 0)
