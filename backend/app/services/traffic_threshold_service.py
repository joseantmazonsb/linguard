"""Service for managing traffic threshold triggers and monitoring."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..models.traffic_trigger import (
    TrafficTrigger,
    TrafficDirection,
    TrafficScope,
    ThresholdWindow,
)
from ..models.traffic_metric import TrafficMetric
from ..models.peer import Peer
from ..models.server import Server
from ..models.integration import Integration

logger = logging.getLogger(__name__)


class TrafficThresholdService:
    """Service for managing and checking traffic threshold triggers."""

    async def check_all_triggers(self, db: AsyncSession) -> Dict[str, int]:
        """
        Check all enabled traffic triggers and fire those that exceed thresholds.
        
        Returns:
            Dictionary with counts of triggers checked and fired
        """
        result = await db.execute(
            select(TrafficTrigger).where(TrafficTrigger.enabled == True)
        )
        triggers = result.scalars().all()
        
        triggers_checked = 0
        triggers_fired = 0
        
        for trigger in triggers:
            try:
                # Update last checked timestamp
                trigger.last_checked_at = datetime.now(timezone.utc)
                
                # Check if trigger should fire
                if await self.check_trigger(db, trigger):
                    triggers_fired += 1
                
                triggers_checked += 1
            except Exception as e:
                logger.error(f"Error checking trigger {trigger.id}: {e}", exc_info=True)
        
        await db.commit()
        
        return {
            "triggers_checked": triggers_checked,
            "triggers_fired": triggers_fired
        }

    async def check_trigger(
        self,
        db: AsyncSession,
        trigger: TrafficTrigger
    ) -> bool:
        """
        Check a single trigger and fire if threshold exceeded.
        
        Args:
            db: Database session
            trigger: TrafficTrigger to check
            
        Returns:
            True if trigger was fired, False otherwise
        """
        # Check cooldown
        if self._is_in_cooldown(trigger):
            logger.debug(f"Trigger {trigger.id} is in cooldown, skipping")
            return False
        
        # Calculate current traffic for the window
        traffic_data = await self.calculate_traffic_in_window(
            db=db,
            scope=trigger.scope,
            direction=trigger.direction,
            window=trigger.window,
            peer_id=trigger.peer_id,
            server_id=trigger.server_id
        )
        
        current_bytes = traffic_data["total_bytes"]
        
        # Check if threshold exceeded
        if current_bytes >= trigger.threshold_bytes:
            logger.info(
                f"Trigger {trigger.id} ({trigger.name}) exceeded: "
                f"{current_bytes:,} >= {trigger.threshold_bytes:,} bytes"
            )
            
            await self.fire_trigger(db, trigger, current_bytes, traffic_data)
            return True
        
        return False

    async def calculate_traffic_in_window(
        self,
        db: AsyncSession,
        scope: TrafficScope,
        direction: TrafficDirection,
        window: ThresholdWindow,
        peer_id: Optional[int] = None,
        server_id: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Calculate traffic volume in a rolling time window.
        
        Args:
            db: Database session
            scope: Traffic scope (peer/server/global)
            direction: Traffic direction (rx/tx/combined)
            window: Time window for aggregation
            peer_id: Peer ID (required for peer scope)
            server_id: Server ID (required for server scope)
            
        Returns:
            Dictionary with traffic breakdown:
                - rx_bytes: Total received bytes
                - tx_bytes: Total transmitted bytes
                - total_bytes: Total combined bytes (based on direction)
        """
        window_start = self._get_window_start_time(window)
        
        # Build base query
        query = select(
            func.sum(TrafficMetric.rx_bytes_delta).label('total_rx'),
            func.sum(TrafficMetric.tx_bytes_delta).label('total_tx')
        ).where(
            TrafficMetric.recorded_at >= window_start
        )
        
        # Apply scope filters
        if scope == TrafficScope.PEER:
            if peer_id is None:
                raise ValueError("peer_id required for PEER scope")
            query = query.where(TrafficMetric.peer_id == peer_id)
        elif scope == TrafficScope.SERVER:
            if server_id is None:
                raise ValueError("server_id required for SERVER scope")
            query = query.where(TrafficMetric.server_id == server_id)
        elif scope == TrafficScope.GLOBAL:
            # Global: sum all peer traffic
            query = query.where(TrafficMetric.peer_id.isnot(None))
        
        result = await db.execute(query)
        row = result.one()
        
        rx_bytes = int(row.total_rx or 0)
        tx_bytes = int(row.total_tx or 0)
        
        # Calculate total based on direction
        if direction == TrafficDirection.RX_ONLY:
            total_bytes = rx_bytes
        elif direction == TrafficDirection.TX_ONLY:
            total_bytes = tx_bytes
        else:  # COMBINED
            total_bytes = rx_bytes + tx_bytes
        
        return {
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "total_bytes": total_bytes
        }

    async def fire_trigger(
        self,
        db: AsyncSession,
        trigger: TrafficTrigger,
        current_bytes: int,
        traffic_data: Dict[str, int]
    ):
        """
        Fire a trigger by publishing event and dispatching to integrations.
        
        Args:
            db: Database session
            trigger: TrafficTrigger that was exceeded
            current_bytes: Current traffic volume
            traffic_data: Full traffic breakdown
        """
        # Update trigger state
        trigger.last_triggered_at = datetime.now(timezone.utc)
        trigger.total_triggers += 1
        
        # Build event payload
        payload = await self._format_event_payload(db, trigger, current_bytes, traffic_data)
        
        # Publish event to EventBus if enabled
        if trigger.trigger_event:
            await event_bus.publish(
                EventType.TRAFFIC_THRESHOLD_EXCEEDED,
                "traffic_trigger",
                trigger.id,
                payload
            )
            logger.info(f"Published TRAFFIC_THRESHOLD_EXCEEDED event for trigger {trigger.id}")
        
        # Trigger integrations if configured
        if trigger.trigger_integrations:
            await self._trigger_integrations(db, trigger, payload)

    async def _trigger_integrations(
        self,
        db: AsyncSession,
        trigger: TrafficTrigger,
        payload: Dict
    ):
        """Directly trigger configured integrations."""
        from ..services.integration_service import IntegrationService
        
        # Get enabled integrations from trigger config
        result = await db.execute(
            select(Integration).where(
                Integration.id.in_(trigger.trigger_integrations),
                Integration.enabled == True
            )
        )
        integrations = result.scalars().all()
        
        for integration in integrations:
            try:
                # Format event data for integration
                event_data = {
                    "event_type": EventType.TRAFFIC_THRESHOLD_EXCEEDED.value,
                    "source_type": "traffic_trigger",
                    "source_id": trigger.id,
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                }
                
                # Get integration service and trigger it
                from ..core.containers import Container
                container = Container()
                integration_service = container.integration_service()
                
                await integration_service._trigger_integration(db, integration, event_data)
                logger.info(f"Triggered integration {integration.id} for trigger {trigger.id}")
            except Exception as e:
                logger.error(
                    f"Error triggering integration {integration.id} for trigger {trigger.id}: {e}",
                    exc_info=True
                )

    async def _format_event_payload(
        self,
        db: AsyncSession,
        trigger: TrafficTrigger,
        current_bytes: int,
        traffic_data: Dict[str, int]
    ) -> Dict:
        """Format rich event payload with context information."""
        window_start = self._get_window_start_time(trigger.window)
        window_end = datetime.now(timezone.utc)
        
        exceeded_by_bytes = current_bytes - trigger.threshold_bytes
        exceeded_by_percent = (exceeded_by_bytes / trigger.threshold_bytes) * 100
        
        payload = {
            "trigger_id": trigger.id,
            "trigger_name": trigger.name,
            "description": trigger.description,
            
            # Scope
            "scope": trigger.scope.value,
            "direction": trigger.direction.value,
            "window": trigger.window.value,
            
            # Threshold info
            "threshold_bytes": trigger.threshold_bytes,
            "current_bytes": current_bytes,
            "exceeded_by_bytes": exceeded_by_bytes,
            "exceeded_by_percent": round(exceeded_by_percent, 2),
            
            # Traffic breakdown
            "rx_bytes": traffic_data["rx_bytes"],
            "tx_bytes": traffic_data["tx_bytes"],
            "total_bytes": current_bytes,
            
            # Timing
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "triggered_at": window_end.isoformat(),
        }
        
        # Add context based on scope
        if trigger.scope == TrafficScope.PEER and trigger.peer_id:
            result = await db.execute(select(Peer).where(Peer.id == trigger.peer_id))
            peer = result.scalar_one_or_none()
            if peer:
                payload["peer_id"] = peer.id
                payload["peer_name"] = peer.name
                payload["server_id"] = peer.server_id
                
                # Get server name
                if peer.server_id:
                    result = await db.execute(select(Server).where(Server.id == peer.server_id))
                    server = result.scalar_one_or_none()
                    if server:
                        payload["server_name"] = server.name
        
        elif trigger.scope == TrafficScope.SERVER and trigger.server_id:
            result = await db.execute(select(Server).where(Server.id == trigger.server_id))
            server = result.scalar_one_or_none()
            if server:
                payload["server_id"] = server.id
                payload["server_name"] = server.name
        
        return payload

    def _is_in_cooldown(self, trigger: TrafficTrigger) -> bool:
        """Check if trigger is in cooldown period."""
        if not trigger.last_triggered_at:
            return False
        
        time_since_last = (datetime.now(timezone.utc) - trigger.last_triggered_at).total_seconds()
        return time_since_last < trigger.cooldown_seconds

    def _get_window_start_time(self, window: ThresholdWindow) -> datetime:
        """Calculate the start time for a rolling window."""
        now = datetime.now(timezone.utc)
        
        if window == ThresholdWindow.LAST_HOUR:
            return now - timedelta(hours=1)
        elif window == ThresholdWindow.LAST_24_HOURS:
            return now - timedelta(hours=24)
        elif window == ThresholdWindow.LAST_7_DAYS:
            return now - timedelta(days=7)
        elif window == ThresholdWindow.LAST_30_DAYS:
            return now - timedelta(days=30)
        else:
            # Default to last hour
            return now - timedelta(hours=1)

    # CRUD Operations

    async def create_trigger(
        self,
        db: AsyncSession,
        **kwargs
    ) -> TrafficTrigger:
        """Create a new traffic trigger."""
        # Remove frontend-only fields that don't exist in the model
        kwargs.pop('integration_ids', None)
        kwargs.pop('cooldown_minutes', None)
        
        trigger = TrafficTrigger(**kwargs)
        db.add(trigger)
        await db.commit()
        await db.refresh(trigger)
        return trigger

    async def list_triggers(
        self,
        db: AsyncSession,
        enabled_only: bool = False,
        scope: Optional[TrafficScope] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrafficTrigger]:
        """List traffic triggers with optional filters and pagination."""
        from sqlalchemy.orm import selectinload
        from sqlalchemy import or_
        from ..models.peer import Peer
        from ..models.server import Server
        
        query = select(TrafficTrigger).options(
            selectinload(TrafficTrigger.peer),
            selectinload(TrafficTrigger.server)
        )
        
        if enabled_only:
            query = query.where(TrafficTrigger.enabled == True)
        
        if scope:
            query = query.where(TrafficTrigger.scope == scope)
        
        # Search by trigger name, peer name, or server name
        if search:
            search_term = f"%{search}%"
            query = query.outerjoin(Peer, TrafficTrigger.peer_id == Peer.id)
            query = query.outerjoin(Server, TrafficTrigger.server_id == Server.id)
            
            # Build search conditions, handling NULL values
            conditions = [TrafficTrigger.name.ilike(search_term)]
            
            # Only search peer/server names if they exist (not NULL)
            from sqlalchemy import and_
            conditions.append(and_(Peer.name.isnot(None), Peer.name.ilike(search_term)))
            conditions.append(and_(Server.name.isnot(None), Server.name.ilike(search_term)))
            
            query = query.where(or_(*conditions))
        
        # Add ordering and pagination
        query = query.order_by(TrafficTrigger.id.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_trigger(
        self,
        db: AsyncSession,
        trigger_id: int
    ) -> Optional[TrafficTrigger]:
        """Get trigger by ID."""
        from sqlalchemy.orm import selectinload
        
        result = await db.execute(
            select(TrafficTrigger)
            .options(
                selectinload(TrafficTrigger.peer),
                selectinload(TrafficTrigger.server)
            )
            .where(TrafficTrigger.id == trigger_id)
        )
        return result.scalar_one_or_none()

    async def update_trigger(
        self,
        db: AsyncSession,
        trigger_id: int,
        **kwargs
    ) -> Optional[TrafficTrigger]:
        """Update a traffic trigger."""
        trigger = await self.get_trigger(db, trigger_id)
        if not trigger:
            return None
        
        # Remove frontend-only fields that don't exist in the model
        kwargs.pop('integration_ids', None)
        kwargs.pop('cooldown_minutes', None)
        
        for key, value in kwargs.items():
            setattr(trigger, key, value)
        
        await db.commit()
        await db.refresh(trigger)
        return trigger

    async def delete_trigger(
        self,
        db: AsyncSession,
        trigger_id: int
    ) -> bool:
        """Delete a traffic trigger."""
        trigger = await self.get_trigger(db, trigger_id)
        if not trigger:
            return False
        
        await db.delete(trigger)
        await db.commit()
        return True
