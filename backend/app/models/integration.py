from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from ..core.database import Base


class Integration(Base):
    """External integrations for notifications and webhooks."""
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Integration Type
    type = Column(String(50), nullable=False)  # webhook, email, slack, discord, telegram, script, plugin:<module_name>
    
    # Plugin Reference (only used when type starts with "plugin:")
    plugin_id = Column(Integer, ForeignKey("plugins.id", ondelete="CASCADE"), nullable=True)

    # Configuration (JSON based on type)
    config = Column(JSON, nullable=False)
    # Examples:
    # webhook: {"url": "https://...", "method": "POST", "headers": {...}}
    # email: {"smtp_host": "...", "smtp_port": 587, "from": "...", "to": [...]}
    # slack: {"webhook_url": "https://hooks.slack.com/..."}
    # telegram: {"bot_token": "...", "chat_id": "..."}

    # Event Subscriptions
    events_subscribed = Column(JSON, nullable=False)  # List of event types

    # Status
    enabled = Column(Boolean, default=True)

    # Statistics
    total_triggered = Column(Integer, default=0)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
