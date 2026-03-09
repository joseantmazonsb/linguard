from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from ..core.database import Base


class Plugin(Base):
    """Installed/discovered plugins."""
    
    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    version = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String(100), nullable=True)

    # Plugin file info
    module_name = Column(String(200), nullable=False)  # e.g., "slack_notifier"
    file_path = Column(String(500), nullable=False)  # Full path to plugin file

    # Configuration
    config_schema = Column(JSON, nullable=True)  # JSON Schema for config validation
    config = Column(JSON, nullable=True)  # User's configuration values

    # Status
    enabled = Column(Boolean, default=False, nullable=False)
    loaded = Column(Boolean, default=False, nullable=False)

    # Events this plugin subscribes to
    subscribed_events = Column(JSON, nullable=True)  # ["server.created", ...]

    # Statistics
    total_invocations = Column(Integer, default=0, nullable=False)
    total_errors = Column(Integer, default=0, nullable=False)
    last_invoked_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    last_error_message = Column(Text, nullable=True)

    # Dependencies
    requirements = Column(JSON, nullable=True)  # List of pip packages from requirements.txt

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PluginData(Base):
    """Key-value storage for plugins."""
    
    __tablename__ = "plugin_data"

    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(200), nullable=False)
    value = Column(JSON, nullable=True)  # Can store any JSON-serializable data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('plugin_id', 'key', name='uq_plugin_key'),
    )
