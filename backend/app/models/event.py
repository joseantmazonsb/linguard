import enum

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.sql import func

from ..core.database import Base


class EventStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Event(Base):
    """Event log for event-driven architecture."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    # Event Details
    event_type = Column(String(100), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # server, peer, backup, etc.
    source_id = Column(Integer, nullable=True)

    # Event Data
    payload = Column(JSON, nullable=False)
    user_id = Column(Integer, nullable=True)

    # Processing Status
    status = Column(SQLEnum(EventStatus), default=EventStatus.PENDING, index=True)
    error_message = Column(String(500), nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
