from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Peer(Base):
    """WireGuard peer/client configuration."""
    __tablename__ = "peers"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)

    # Basic Info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)  # Optional contact

    # Keys
    public_key = Column(String(44), nullable=False)
    private_key = Column(String(44), nullable=False)
    preshared_key = Column(String(44), nullable=True)

    # Network Configuration
    ipv4_address = Column(String(18), nullable=True)  # Single IP or CIDR
    ipv6_address = Column(String(43), nullable=True)
    ipv4_allowed_ips = Column(Text, nullable=True)  # Comma-separated CIDRs
    ipv6_allowed_ips = Column(Text, nullable=True)

    # DNS Configuration (inherits from server, can override)
    dns_primary = Column(String(45), nullable=True)
    dns_secondary = Column(String(45), nullable=True)

    # Connection Settings
    persistent_keepalive = Column(Integer, default=25)
    endpoint = Column(String(255), nullable=True)  # For peer-to-peer configs

    # Status
    enabled = Column(Boolean, default=True)
    last_handshake = Column(DateTime(timezone=True), nullable=True)

    # Traffic Statistics
    rx_bytes = Column(BigInteger, default=0)
    tx_bytes = Column(BigInteger, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    server = relationship("Server", back_populates="peers")

    @property
    def allowed_ips(self) -> str:
        """Combine IPv4 and IPv6 allowed IPs into a single comma-separated string."""
        allowed_list = []
        if self.ipv4_allowed_ips:
            allowed_list.append(self.ipv4_allowed_ips)
        if self.ipv6_allowed_ips:
            allowed_list.append(self.ipv6_allowed_ips)
        return ', '.join(allowed_list) if allowed_list else "0.0.0.0/0, ::/0"
