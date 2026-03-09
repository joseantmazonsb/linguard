"""Traffic trigger models for threshold-based monitoring and alerting."""
import enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class TrafficDirection(str, enum.Enum):
    """Traffic direction for threshold monitoring."""
    RX_ONLY = "rx_only"
    TX_ONLY = "tx_only"
    COMBINED = "combined"


class TrafficScope(str, enum.Enum):
    """Scope of traffic monitoring."""
    PEER = "peer"
    SERVER = "server"
    GLOBAL = "global"


class ThresholdWindow(str, enum.Enum):
    """Time window for traffic aggregation."""
    LAST_HOUR = "last_hour"
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"


class TrafficTrigger(Base):
    """Traffic threshold triggers for monitoring and alerting."""
    __tablename__ = "traffic_triggers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Scope configuration
    scope = Column(SQLEnum(TrafficScope), nullable=False)
    peer_id = Column(Integer, ForeignKey("peers.id", ondelete="CASCADE"), nullable=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=True, index=True)

    # Threshold configuration
    direction = Column(SQLEnum(TrafficDirection), nullable=False, default=TrafficDirection.COMBINED)
    threshold_bytes = Column(BigInteger, nullable=False)
    window = Column(SQLEnum(ThresholdWindow), nullable=False)

    # Action configuration
    trigger_integrations = Column(JSON, nullable=False, default=list)  # List of integration IDs
    trigger_event = Column(Boolean, default=True)  # Publish to EventBus

    # State
    enabled = Column(Boolean, default=True, index=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    total_triggers = Column(Integer, default=0)

    # Cooldown to prevent spam (seconds)
    cooldown_seconds = Column(Integer, default=3600)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    peer = relationship("Peer", foreign_keys=[peer_id])
    server = relationship("Server", foreign_keys=[server_id])
