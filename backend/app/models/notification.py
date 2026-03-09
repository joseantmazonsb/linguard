from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


class Notification(Base):
    """In-app notifications for users."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    
    # User who should see this notification
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Notification content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    # Notification type/category
    type = Column(String(50), nullable=False)  # info, success, warning, error, event
    
    # Optional link for "view details" functionality
    link = Column(String(500), nullable=True)
    
    # Related event/resource info (optional)
    event_type = Column(String(100), nullable=True)
    source_type = Column(String(50), nullable=True)  # server, peer, backup, etc.
    source_id = Column(Integer, nullable=True)
    
    # Status
    read = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
