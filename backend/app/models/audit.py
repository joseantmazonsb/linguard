from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class AuditLog(Base):
    """Audit log for all administrative actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Action Details
    action = Column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, MIGRATE, etc.
    resource_type = Column(String(50), nullable=False, index=True)  # server, peer, backup, etc.
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(255), nullable=True)

    # Change Details
    details = Column(JSON, nullable=True)  # JSON with before/after or other details

    # Request Info
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Status
    status = Column(String(20), default="success")  # success, failed
    error_message = Column(Text, nullable=True)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User")
