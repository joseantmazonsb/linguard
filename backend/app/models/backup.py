from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Backup(Base):
    """Backup metadata."""
    __tablename__ = "backups"

    id = Column(Integer, primary_key=True, index=True)

    # Backup Details
    filename = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)

    # Encryption
    is_encrypted = Column(Boolean, default=False)

    # Statistics
    servers_count = Column(Integer, default=0)
    peers_count = Column(Integer, default=0)

    # Created By
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    created_by = relationship("User")
