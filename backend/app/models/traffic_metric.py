from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class TrafficMetric(Base):
    """Historical traffic metrics for peers and servers."""
    __tablename__ = "traffic_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Can be associated with either a peer or server
    peer_id = Column(Integer, ForeignKey("peers.id", ondelete="CASCADE"), nullable=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Traffic data (in bytes)
    rx_bytes = Column(BigInteger, default=0, nullable=False)
    tx_bytes = Column(BigInteger, default=0, nullable=False)
    
    # Delta from previous measurement (for rate calculations)
    rx_bytes_delta = Column(BigInteger, default=0, nullable=False)
    tx_bytes_delta = Column(BigInteger, default=0, nullable=False)
    
    # Connection info (for peers)
    handshake_at = Column(DateTime(timezone=True), nullable=True)
    is_connected = Column(Boolean, default=False)
    
    # Timestamp
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)

    # Relationships
    peer = relationship("Peer", foreign_keys=[peer_id])
    server = relationship("Server", foreign_keys=[server_id])


# Performance indexes for rolling window queries
Index('idx_traffic_metrics_peer_time', TrafficMetric.peer_id, TrafficMetric.recorded_at)
Index('idx_traffic_metrics_server_time', TrafficMetric.server_id, TrafficMetric.recorded_at)
Index('idx_traffic_metrics_recorded_at', TrafficMetric.recorded_at)
