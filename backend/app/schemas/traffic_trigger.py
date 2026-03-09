"""Pydantic schemas for traffic triggers."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from ..models.traffic_trigger import TrafficDirection, TrafficScope, ThresholdWindow


class TrafficTriggerBase(BaseModel):
    """Base schema for traffic triggers."""
    name: str = Field(..., min_length=1, max_length=100, description="Trigger name")
    description: Optional[str] = Field(None, description="Optional description")
    scope: TrafficScope = Field(..., description="Monitoring scope (peer/server/global)")
    peer_id: Optional[int] = Field(None, description="Peer ID (required for peer scope)")
    server_id: Optional[int] = Field(None, description="Server ID (required for server scope)")
    direction: TrafficDirection = Field(
        default=TrafficDirection.COMBINED,
        description="Traffic direction to monitor (rx_only/tx_only/combined)"
    )
    threshold_bytes: int = Field(..., gt=0, description="Threshold in bytes")
    window: ThresholdWindow = Field(..., description="Time window for aggregation")
    
    # Support both naming conventions for integrations
    trigger_integrations: Optional[List[int]] = Field(
        None,
        description="List of integration IDs to trigger (backend field name)"
    )
    integration_ids: Optional[List[int]] = Field(
        None,
        description="List of integration IDs to trigger (frontend field name)"
    )
    
    trigger_event: bool = Field(
        default=True,
        description="Whether to publish event to EventBus"
    )
    enabled: bool = Field(default=True, description="Whether trigger is enabled")
    
    # Support both naming conventions for cooldown
    cooldown_seconds: Optional[int] = Field(
        None,
        ge=0,
        description="Cooldown period in seconds (backend field name)"
    )
    cooldown_minutes: Optional[int] = Field(
        None,
        ge=0,
        description="Cooldown period in minutes (frontend field name)"
    )

    @field_validator('peer_id')
    @classmethod
    def validate_peer_id(cls, v, info):
        """Validate peer_id based on scope."""
        scope = info.data.get('scope')
        if scope == TrafficScope.PEER and v is None:
            raise ValueError('peer_id is required when scope is PEER')
        if scope != TrafficScope.PEER and v is not None:
            raise ValueError('peer_id must be null when scope is not PEER')
        return v

    @field_validator('server_id')
    @classmethod
    def validate_server_id(cls, v, info):
        """Validate server_id based on scope."""
        scope = info.data.get('scope')
        if scope == TrafficScope.SERVER and v is None:
            raise ValueError('server_id is required when scope is SERVER')
        if scope != TrafficScope.SERVER and v is not None:
            raise ValueError('server_id must be null when scope is not SERVER')
        return v
    
    @model_validator(mode='after')
    def normalize_fields(self):
        """Normalize integration_ids and cooldown between frontend/backend naming."""
        # Handle integration_ids vs trigger_integrations
        if self.integration_ids is not None and self.trigger_integrations is None:
            self.trigger_integrations = self.integration_ids
        elif self.trigger_integrations is not None and self.integration_ids is None:
            self.integration_ids = self.trigger_integrations
        elif self.trigger_integrations is None and self.integration_ids is None:
            self.trigger_integrations = []
            self.integration_ids = []
        
        # Handle cooldown_minutes vs cooldown_seconds
        if self.cooldown_minutes is not None and self.cooldown_seconds is None:
            self.cooldown_seconds = self.cooldown_minutes * 60
        elif self.cooldown_seconds is not None and self.cooldown_minutes is None:
            self.cooldown_minutes = self.cooldown_seconds // 60
        elif self.cooldown_seconds is None and self.cooldown_minutes is None:
            self.cooldown_seconds = 3600
            self.cooldown_minutes = 60
        
        return self


class TrafficTriggerCreate(TrafficTriggerBase):
    """Schema for creating a traffic trigger."""
    pass


class TrafficTriggerUpdate(BaseModel):
    """Schema for updating a traffic trigger (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    scope: Optional[TrafficScope] = None
    peer_id: Optional[int] = None
    server_id: Optional[int] = None
    direction: Optional[TrafficDirection] = None
    threshold_bytes: Optional[int] = Field(None, gt=0)
    window: Optional[ThresholdWindow] = None
    trigger_integrations: Optional[List[int]] = None
    integration_ids: Optional[List[int]] = None
    trigger_event: Optional[bool] = None
    enabled: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=0)
    cooldown_minutes: Optional[int] = Field(None, ge=0)
    
    @model_validator(mode='after')
    def normalize_fields(self):
        """Normalize integration_ids and cooldown between frontend/backend naming."""
        # Handle integration_ids vs trigger_integrations
        if self.integration_ids is not None and self.trigger_integrations is None:
            self.trigger_integrations = self.integration_ids
        elif self.trigger_integrations is not None and self.integration_ids is None:
            self.integration_ids = self.trigger_integrations
        
        # Handle cooldown_minutes vs cooldown_seconds
        if self.cooldown_minutes is not None and self.cooldown_seconds is None:
            self.cooldown_seconds = self.cooldown_minutes * 60
        elif self.cooldown_seconds is not None and self.cooldown_minutes is None:
            self.cooldown_minutes = self.cooldown_seconds // 60
        
        return self


class TrafficTriggerResponse(TrafficTriggerBase):
    """Schema for traffic trigger responses."""
    id: int
    last_triggered_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    total_triggers: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
    peer_name: Optional[str] = None
    server_name: Optional[str] = None
    
    # Computed fields for frontend compatibility
    integration_ids: List[int] = Field(default_factory=list, description="Alias for trigger_integrations")
    cooldown_minutes: int = Field(default=60, description="Cooldown in minutes (computed from cooldown_seconds)")

    class Config:
        from_attributes = True
        
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle computed fields."""
        # Clean up peer_id/server_id based on scope to handle legacy data
        peer_id = obj.peer_id if obj.scope == TrafficScope.PEER else None
        server_id = obj.server_id if obj.scope == TrafficScope.SERVER else None
        
        # Get the base data
        data = {
            'id': obj.id,
            'name': obj.name,
            'description': obj.description,
            'scope': obj.scope,
            'peer_id': peer_id,
            'server_id': server_id,
            'direction': obj.direction,
            'threshold_bytes': obj.threshold_bytes,
            'window': obj.window,
            'trigger_integrations': obj.trigger_integrations or [],
            'integration_ids': obj.trigger_integrations or [],  # Alias
            'trigger_event': obj.trigger_event,
            'enabled': obj.enabled,
            'cooldown_seconds': obj.cooldown_seconds,
            'cooldown_minutes': obj.cooldown_seconds // 60,  # Convert to minutes
            'last_triggered_at': obj.last_triggered_at,
            'last_checked_at': obj.last_checked_at,
            'total_triggers': obj.total_triggers,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
            'peer_name': obj.peer.name if hasattr(obj, 'peer') and obj.peer else None,
            'server_name': obj.server.name if hasattr(obj, 'server') and obj.server else None,
        }
        return cls(**data)


class TrafficTriggerListItem(BaseModel):
    """Simplified schema for listing traffic triggers."""
    id: int
    name: str
    scope: TrafficScope
    direction: TrafficDirection
    threshold_bytes: int
    window: ThresholdWindow
    enabled: bool
    total_triggers: int
    last_triggered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrafficTriggerTestResponse(BaseModel):
    """Response schema for testing a trigger."""
    trigger_id: int
    trigger_name: str
    threshold_exceeded: bool
    current_bytes: int
    threshold_bytes: int
    traffic_breakdown: dict
    would_trigger: bool
    in_cooldown: bool
    reason: str
