from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Server(Base):
    """WireGuard server configuration."""
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    interface = Column(String(20), unique=True, nullable=True)  # Auto-detected, e.g., wg0, utun10
    description = Column(Text, nullable=True)

    # Keys
    public_key = Column(String(44), nullable=False)
    private_key = Column(String(44), nullable=False)

    # Network Configuration
    endpoint = Column(String(255), nullable=True)  # Public IP or domain
    listen_port = Column(Integer, nullable=False)
    ipv4_address = Column(String(18), nullable=True)  # CIDR notation
    ipv6_address = Column(String(43), nullable=True)  # CIDR notation

    # DNS Configuration (inherits from global, can override)
    dns_primary = Column(String(45), nullable=True)
    dns_secondary = Column(String(45), nullable=True)

    # Bounce Server Configuration
    is_bounce_server = Column(Boolean, default=False)
    bounce_via_server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)

    # Status
    status = Column(String(20), default="stopped")  # stopped, running, error
    enabled = Column(Boolean, default=True)
    autostart = Column(Boolean, default=True)  # Auto-start server on application boot
    needs_reload = Column(Boolean, default=False)  # Set when config changes require reload
    
    # Traffic Statistics (aggregate of all peers)
    rx_bytes = Column(BigInteger, default=0)
    tx_bytes = Column(BigInteger, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_started_at = Column(DateTime(timezone=True), nullable=True)
    last_stopped_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    peers = relationship("Peer", back_populates="server", cascade="all, delete-orphan")
    bounce_via = relationship("Server", remote_side=[id], foreign_keys=[bounce_via_server_id])
