"""API endpoints for traffic threshold triggers."""
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ..core.containers import Container
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.user import User
from ..models.traffic_trigger import TrafficScope
from ..schemas.traffic_trigger import (
    TrafficTriggerCreate,
    TrafficTriggerResponse,
    TrafficTriggerUpdate,
    TrafficTriggerListItem,
    TrafficTriggerTestResponse,
)
from ..services.traffic_threshold_service import TrafficThresholdService

router = APIRouter()


@router.get("/", response_model=List[TrafficTriggerResponse])
@inject
async def list_triggers(
    enabled_only: bool = False,
    scope: Optional[TrafficScope] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """
    List all traffic triggers.
    
    Query Parameters:
    - enabled_only: Only return enabled triggers
    - scope: Filter by scope (peer/server/global)
    - search: Search by trigger name, peer name, or server name
    - skip: Number of records to skip (for pagination)
    - limit: Maximum number of records to return (default: 100)
    """
    triggers = await service.list_triggers(db, enabled_only=enabled_only, scope=scope, search=search, skip=skip, limit=limit)
    return [TrafficTriggerResponse.from_orm(t) for t in triggers]


@router.get("/{trigger_id}", response_model=TrafficTriggerResponse)
@inject
async def get_trigger(
    trigger_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """Get a specific traffic trigger by ID."""
    trigger = await service.get_trigger(db, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traffic trigger not found"
        )
    return TrafficTriggerResponse.from_orm(trigger)


@router.post(
    "/",
    response_model=TrafficTriggerResponse,
    status_code=status.HTTP_201_CREATED
)
@inject
async def create_trigger(
    trigger_data: TrafficTriggerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """
    Create a new traffic trigger.
    
    The trigger will automatically start monitoring based on the configured scope,
    direction, window, and threshold.
    """
    # Validate peer_id or server_id exists if specified
    if trigger_data.peer_id:
        from sqlalchemy import select
        from ..models.peer import Peer
        result = await db.execute(select(Peer).where(Peer.id == trigger_data.peer_id))
        peer = result.scalar_one_or_none()
        if not peer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Peer with ID {trigger_data.peer_id} not found"
            )
    
    if trigger_data.server_id:
        from sqlalchemy import select
        from ..models.server import Server
        result = await db.execute(select(Server).where(Server.id == trigger_data.server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server with ID {trigger_data.server_id} not found"
            )
    
    # Validate integrations exist
    if trigger_data.trigger_integrations:
        from sqlalchemy import select
        from ..models.integration import Integration
        result = await db.execute(
            select(Integration).where(
                Integration.id.in_(trigger_data.trigger_integrations)
            )
        )
        integrations = result.scalars().all()
        if len(integrations) != len(trigger_data.trigger_integrations):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more integration IDs not found"
            )
    
    trigger = await service.create_trigger(db, **trigger_data.model_dump())
    
    # Load relationships for response
    await db.refresh(trigger)
    return TrafficTriggerResponse.from_orm(trigger)


@router.put("/{trigger_id}", response_model=TrafficTriggerResponse)
@inject
async def update_trigger(
    trigger_id: int,
    trigger_data: TrafficTriggerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """Update a traffic trigger."""
    # Validate peer_id or server_id if being updated
    if trigger_data.peer_id:
        from sqlalchemy import select
        from ..models.peer import Peer
        result = await db.execute(select(Peer).where(Peer.id == trigger_data.peer_id))
        peer = result.scalar_one_or_none()
        if not peer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Peer with ID {trigger_data.peer_id} not found"
            )
    
    if trigger_data.server_id:
        from sqlalchemy import select
        from ..models.server import Server
        result = await db.execute(select(Server).where(Server.id == trigger_data.server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Server with ID {trigger_data.server_id} not found"
            )
    
    # Validate integrations if being updated
    if trigger_data.trigger_integrations:
        from sqlalchemy import select
        from ..models.integration import Integration
        result = await db.execute(
            select(Integration).where(
                Integration.id.in_(trigger_data.trigger_integrations)
            )
        )
        integrations = result.scalars().all()
        if len(integrations) != len(trigger_data.trigger_integrations):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more integration IDs not found"
            )
    
    # Prepare update data, handling scope changes
    update_data = {k: v for k, v in trigger_data.model_dump().items() if v is not None}
    
    # If scope is being changed, explicitly clear peer_id/server_id as needed
    if trigger_data.scope is not None:
        if trigger_data.scope != TrafficScope.PEER:
            update_data['peer_id'] = None
        if trigger_data.scope != TrafficScope.SERVER:
            update_data['server_id'] = None
    
    trigger = await service.update_trigger(db, trigger_id, **update_data)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traffic trigger not found"
        )
    
    await db.refresh(trigger)
    return TrafficTriggerResponse.from_orm(trigger)


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_trigger(
    trigger_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """Delete a traffic trigger."""
    success = await service.delete_trigger(db, trigger_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traffic trigger not found"
        )
    return None


@router.post("/{trigger_id}/test", response_model=TrafficTriggerTestResponse)
@inject
async def test_trigger(
    trigger_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: TrafficThresholdService = Depends(
        Provide[Container.traffic_threshold_service]
    ),
):
    """
    Test a trigger (dry-run) without actually firing it.
    
    This endpoint calculates current traffic and checks if the trigger would fire,
    but does not update the trigger state or send any notifications.
    """
    trigger = await service.get_trigger(db, trigger_id)
    if not trigger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Traffic trigger not found"
        )
    
    # Calculate current traffic
    traffic_data = await service.calculate_traffic_in_window(
        db=db,
        scope=trigger.scope,
        direction=trigger.direction,
        window=trigger.window,
        peer_id=trigger.peer_id,
        server_id=trigger.server_id
    )
    
    current_bytes = traffic_data["total_bytes"]
    threshold_exceeded = current_bytes >= trigger.threshold_bytes
    in_cooldown = service._is_in_cooldown(trigger)
    
    # Determine if trigger would actually fire
    would_trigger = threshold_exceeded and not in_cooldown
    
    # Build reason message
    if not threshold_exceeded:
        reason = (
            f"Current traffic ({current_bytes:,} bytes) is below threshold "
            f"({trigger.threshold_bytes:,} bytes)"
        )
    elif in_cooldown:
        reason = (
            f"Threshold exceeded but trigger is in cooldown "
            f"(last triggered: {trigger.last_triggered_at})"
        )
    else:
        reason = f"Trigger would fire! Current traffic ({current_bytes:,} bytes) exceeds threshold ({trigger.threshold_bytes:,} bytes)"
    
    return TrafficTriggerTestResponse(
        trigger_id=trigger.id,
        trigger_name=trigger.name,
        threshold_exceeded=threshold_exceeded,
        current_bytes=current_bytes,
        threshold_bytes=trigger.threshold_bytes,
        traffic_breakdown=traffic_data,
        would_trigger=would_trigger,
        in_cooldown=in_cooldown,
        reason=reason
    )
