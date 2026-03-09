import aiosmtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..models.integration import Integration
from ..models.traffic_trigger import TrafficTrigger
from .notification_service import NotificationService


class IntegrationService:
    """Service for managing integrations and dispatching events to them."""

    def __init__(self, notification_service: NotificationService, plugin_manager=None):
        self.notification_service = notification_service
        self.plugin_manager = plugin_manager

    async def get_integrations(
        self,
        db: AsyncSession,
        enabled_only: bool = False
    ) -> list[Integration]:
        """Get all integrations."""
        query = select(Integration)
        
        if enabled_only:
            query = query.where(Integration.enabled == True)
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_integration(
        self,
        db: AsyncSession,
        integration_id: int
    ) -> Integration | None:
        """Get a specific integration."""
        result = await db.execute(
            select(Integration).where(Integration.id == integration_id)
        )
        return result.scalar_one_or_none()

    async def create_integration(
        self,
        db: AsyncSession,
        name: str,
        type: str,
        config: dict,
        events_subscribed: list[str],
        description: str | None = None,
        enabled: bool = True,
        plugin_id: int | None = None
    ) -> Integration:
        """Create a new integration."""
        integration = Integration(
            name=name,
            description=description,
            type=type,
            config=config,
            events_subscribed=events_subscribed,
            enabled=enabled,
            plugin_id=plugin_id
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        return integration

    async def update_integration(
        self,
        db: AsyncSession,
        integration_id: int,
        **kwargs
    ) -> Integration | None:
        """Update an integration."""
        integration = await self.get_integration(db, integration_id)
        if not integration:
            return None

        for key, value in kwargs.items():
            if value is not None and hasattr(integration, key):
                setattr(integration, key, value)

        await db.commit()
        await db.refresh(integration)
        return integration

    async def delete_integration(
        self,
        db: AsyncSession,
        integration_id: int
    ) -> bool:
        """Delete an integration and remove it from all traffic triggers."""
        integration = await self.get_integration(db, integration_id)
        if not integration:
            return False

        # Remove this integration from all traffic triggers that reference it
        result = await db.execute(select(TrafficTrigger))
        all_triggers = result.scalars().all()
        
        for trigger in all_triggers:
            if trigger.trigger_integrations and integration_id in trigger.trigger_integrations:
                # Remove the integration ID from the list
                trigger.trigger_integrations = [
                    id for id in trigger.trigger_integrations if id != integration_id
                ]
        
        # Delete the integration
        await db.delete(integration)
        await db.commit()
        return True

    async def get_integrations_for_event(
        self,
        db: AsyncSession,
        event_type: EventType
    ) -> list[Integration]:
        """Get all enabled integrations subscribed to a specific event type."""
        result = await db.execute(
            select(Integration).where(Integration.enabled == True)
        )
        integrations = result.scalars().all()
        
        # Filter integrations that are subscribed to this event
        return [
            integration for integration in integrations
            if event_type.value in integration.events_subscribed
        ]

    async def dispatch_event_to_integrations(
        self,
        db: AsyncSession,
        event_type: EventType,
        event_data: dict
    ):
        """
        Dispatch an event to all relevant integrations.
        
        This method is called by the event system when an event occurs.
        It finds all integrations subscribed to the event and triggers them.
        """
        integrations = await self.get_integrations_for_event(db, event_type)
        
        for integration in integrations:
            try:
                await self._trigger_integration(db, integration, event_data)
            except Exception as e:
                print(f"Error triggering integration {integration.id}: {e}")

    async def _trigger_integration(
        self,
        db: AsyncSession,
        integration: Integration,
        event_data: dict
    ):
        """Trigger a specific integration based on its type."""
        # Update statistics
        integration.total_triggered += 1
        from datetime import datetime
        integration.last_triggered_at = datetime.utcnow()
        
        # Normalize event_data structure for integrations
        # The event bus uses: source_type, source_id, payload, timestamp
        # But integrations expect: resource_type, resource_id, metadata, timestamp
        normalized_event_data = {
            "event_type": event_data.get("event_type"),
            "resource_type": event_data.get("source_type"),
            "resource_id": event_data.get("source_id"),
            "metadata": event_data.get("payload", {}),
            "timestamp": event_data.get("timestamp"),
            "user_id": event_data.get("user_id")
        }
        
        # Dispatch based on integration type
        if integration.type == "notification":
            await self.notification_service.notify_from_integration(
                db, integration, normalized_event_data
            )
        elif integration.type == "webhook":
            await self._trigger_webhook(integration, normalized_event_data)
        elif integration.type == "email":
            await self._trigger_email(integration, normalized_event_data)
        elif integration.type == "slack":
            await self._trigger_slack(integration, normalized_event_data)
        elif integration.type == "discord":
            await self._trigger_discord(integration, normalized_event_data)
        elif integration.type == "telegram":
            await self._trigger_telegram(integration, normalized_event_data)
        elif integration.type == "script":
            # TODO: Implement script execution
            pass
        elif integration.type.startswith("plugin:"):
            # Handle plugin-based integrations
            await self._trigger_plugin(db, integration, normalized_event_data)
        
        # Don't commit here - let the caller handle the transaction
        # await db.commit()

    async def _trigger_webhook(self, integration: Integration, event_data: dict):
        """Send HTTP webhook request."""
        config = integration.config
        url = config.get("url")
        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        
        if not url:
            print(f"Webhook integration {integration.id} missing URL")
            return
        
        # Prepare payload
        payload = {
            "integration_id": integration.id,
            "integration_name": integration.name,
            "event_type": event_data.get("event_type"),
            "resource_type": event_data.get("resource_type"),
            "resource_id": event_data.get("resource_id"),
            "metadata": event_data.get("metadata", {}),
            "timestamp": event_data.get("timestamp")
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if method == "POST":
                    response = await client.post(url, json=payload, headers=headers)
                elif method == "PUT":
                    response = await client.put(url, json=payload, headers=headers)
                elif method == "GET":
                    response = await client.get(url, params=payload, headers=headers)
                else:
                    print(f"Unsupported HTTP method: {method}")
                    return
                
                response.raise_for_status()
                print(f"Webhook {integration.id} triggered successfully: {response.status_code}")
        except httpx.HTTPError as e:
            print(f"Webhook {integration.id} failed: {e}")
        except Exception as e:
            print(f"Webhook {integration.id} error: {e}")

    async def _trigger_slack(self, integration: Integration, event_data: dict):
        """Send message to Slack via webhook."""
        config = integration.config
        webhook_url = config.get("webhook_url")
        
        if not webhook_url:
            print(f"Slack integration {integration.id} missing webhook_url")
            return
        
        # Format Slack message with better structure
        event_type = event_data.get("event_type", "unknown")
        resource_type = event_data.get("resource_type", "resource")
        resource_id = event_data.get("resource_id", "N/A")
        metadata = event_data.get("metadata", {})
        timestamp = event_data.get("timestamp", "")
        
        # Map event types to emojis and friendly names
        event_emoji_map = {
            "server.created": ":computer: Server Created",
            "server.edited": ":pencil2: Server Updated",
            "server.deleted": ":wastebasket: Server Deleted",
            "server.started": ":arrow_forward: Server Started",
            "server.stopped": ":pause_button: Server Stopped",
            "server.reloaded": ":arrows_counterclockwise: Server Reloaded",
            "peer.created": ":bust_in_silhouette: Peer Created",
            "peer.edited": ":pencil2: Peer Updated",
            "peer.deleted": ":wastebasket: Peer Deleted",
            "peer.connected": ":green_circle: Peer Connected",
            "peer.disconnected": ":red_circle: Peer Disconnected",
            "peer.migrated": ":twisted_rightwards_arrows: Peer Migrated",
            "backup.created": ":floppy_disk: Backup Created",
            "backup.restored": ":recycle: Backup Restored",
            "backup.deleted": ":wastebasket: Backup Deleted",
            "settings.updated": ":gear: Settings Updated",
        }
        
        event_display = event_emoji_map.get(event_type, f":bell: {event_type.replace('_', ' ').title()}")
        
        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": event_display.replace(":", "")
                }
            }
        ]
        
        # Add resource info
        fields = []
        if resource_type and resource_id and resource_id != "N/A":
            fields.append({
                "type": "mrkdwn",
                "text": f"*Resource:*\n{resource_type.title()} #{resource_id}"
            })
        
        # Add key metadata fields
        if metadata.get("name"):
            fields.append({"type": "mrkdwn", "text": f"*Name:*\n{metadata['name']}"})
        
        # Interface name only
        if metadata.get("interface"):
            fields.append({"type": "mrkdwn", "text": f"*Interface:*\n{metadata['interface']}"})
        
        if metadata.get("email"):
            fields.append({"type": "mrkdwn", "text": f"*Email:*\n{metadata['email']}"})
        
        if metadata.get("changes"):
            changes = metadata['changes']
            if isinstance(changes, list):
                fields.append({"type": "mrkdwn", "text": f"*Changes:*\n{', '.join(changes)}"})
        
        if metadata.get("server_name"):
            fields.append({"type": "mrkdwn", "text": f"*Server:*\n{metadata['server_name']}"})
        
        if fields:
            blocks.append({"type": "section", "fields": fields})
        
        # Add timestamp
        if timestamp:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f":clock3: {timestamp}"}]
            })
        
        message = {
            "text": f"Linguard: {event_display}",
            "blocks": blocks
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=message)
                response.raise_for_status()
                print(f"Slack integration {integration.id} triggered successfully")
        except httpx.HTTPError as e:
            print(f"Slack integration {integration.id} failed: {e}")
        except Exception as e:
            print(f"Slack integration {integration.id} error: {e}")

    async def _trigger_discord(self, integration: Integration, event_data: dict):
        """Send message to Discord via webhook."""
        config = integration.config
        webhook_url = config.get("webhook_url")
        
        if not webhook_url:
            print(f"Discord integration {integration.id} missing webhook_url")
            return
        
        # Format Discord message with better structure
        event_type = event_data.get("event_type", "unknown")
        resource_type = event_data.get("resource_type", "resource")
        resource_id = event_data.get("resource_id", "N/A")
        metadata = event_data.get("metadata", {})
        timestamp = event_data.get("timestamp")
        
        # Map event types to emojis, colors, and friendly names
        event_config_map = {
            "server.created": {"emoji": "🖥️", "title": "Server Created", "color": 5763719},  # Green
            "server.edited": {"emoji": "✏️", "title": "Server Updated", "color": 3447003},  # Blue
            "server.deleted": {"emoji": "🗑️", "title": "Server Deleted", "color": 15158332},  # Red
            "server.started": {"emoji": "▶️", "title": "Server Started", "color": 3066993},  # Green
            "server.stopped": {"emoji": "⏸️", "title": "Server Stopped", "color": 15105570},  # Orange
            "server.reloaded": {"emoji": "🔄", "title": "Server Reloaded", "color": 3447003},  # Blue
            "peer.created": {"emoji": "👤", "title": "Peer Created", "color": 5763719},  # Green
            "peer.edited": {"emoji": "✏️", "title": "Peer Updated", "color": 3447003},  # Blue
            "peer.deleted": {"emoji": "🗑️", "title": "Peer Deleted", "color": 15158332},  # Red
            "peer.connected": {"emoji": "🟢", "title": "Peer Connected", "color": 3066993},  # Green
            "peer.disconnected": {"emoji": "🔴", "title": "Peer Disconnected", "color": 15158332},  # Red
            "peer.migrated": {"emoji": "🔀", "title": "Peer Migrated", "color": 10181046},  # Purple
            "backup.created": {"emoji": "💾", "title": "Backup Created", "color": 5763719},  # Green
            "backup.restored": {"emoji": "♻️", "title": "Backup Restored", "color": 3447003},  # Blue
            "backup.deleted": {"emoji": "🗑️", "title": "Backup Deleted", "color": 15158332},  # Red
            "settings.updated": {"emoji": "⚙️", "title": "Settings Updated", "color": 3447003},  # Blue
        }
        
        event_config = event_config_map.get(event_type, {"emoji": "🔔", "title": event_type.replace('_', ' ').title(), "color": 3447003})
        
        # Build Discord embed
        embed = {
            "title": f"{event_config['emoji']} {event_config['title']}",
            "color": event_config['color'],
            "fields": [],
            "timestamp": timestamp
        }
        
        # Add resource info
        if resource_type and resource_id and resource_id != "N/A":
            embed["fields"].append({
                "name": f"📋 {resource_type.title()}",
                "value": f"#{resource_id}",
                "inline": True
            })
        
        # Add key metadata fields
        if metadata.get("name"):
            embed["fields"].append({"name": "🏷️ Name", "value": metadata['name'], "inline": True})
        
        # Interface name only
        if metadata.get("interface"):
            embed["fields"].append({"name": "🌐 Interface", "value": metadata['interface'], "inline": True})
        
        if metadata.get("email"):
            embed["fields"].append({"name": "📧 Email", "value": metadata['email'], "inline": True})
        
        if metadata.get("allowed_ips"):
            embed["fields"].append({"name": "🌐 Allowed IPs", "value": f"`{metadata['allowed_ips']}`", "inline": False})
        
        if metadata.get("changes"):
            changes = metadata['changes']
            if isinstance(changes, list) and changes:
                embed["fields"].append({"name": "📝 Changes", "value": ", ".join(changes), "inline": False})
        
        if metadata.get("server_name"):
            embed["fields"].append({"name": "🖥️ Server", "value": metadata['server_name'], "inline": True})
        
        if metadata.get("to_server"):
            embed["fields"].append({"name": "➡️ Migrated To", "value": metadata['to_server'], "inline": True})
        
        if metadata.get("action"):
            embed["fields"].append({"name": "🎯 Action", "value": metadata['action'], "inline": True})
        
        if metadata.get("reason"):
            embed["fields"].append({"name": "💬 Reason", "value": metadata['reason'], "inline": False})
        
        # Add footer
        embed["footer"] = {"text": "Linguard VPN Management"}
        
        message = {
            "username": "Linguard",
            "embeds": [embed]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=message)
                response.raise_for_status()
                print(f"Discord integration {integration.id} triggered successfully")
        except httpx.HTTPError as e:
            print(f"Discord integration {integration.id} failed: {e}")
        except Exception as e:
            print(f"Discord integration {integration.id} error: {e}")

    async def _trigger_telegram(self, integration: Integration, event_data: dict):
        """Send message via Telegram bot."""
        config = integration.config
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")
        
        if not bot_token or not chat_id:
            print(f"Telegram integration {integration.id} missing bot_token or chat_id")
            return
        
        # Format Telegram message - keep it simple
        event_type = event_data.get("event_type", "unknown")
        resource_type = event_data.get("resource_type", "resource")
        resource_id = event_data.get("resource_id", "N/A")
        metadata = event_data.get("metadata", {})
        timestamp = event_data.get("timestamp", "")
        
        # Map event types to emojis and friendly names
        event_emoji_map = {
            "server.created": "🖥️ Server Created",
            "server.edited": "✏️ Server Updated",
            "server.deleted": "🗑️ Server Deleted",
            "server.started": "▶️ Server Started",
            "server.stopped": "⏸️ Server Stopped",
            "server.reloaded": "🔄 Server Reloaded",
            "peer.created": "👤 Peer Created",
            "peer.edited": "✏️ Peer Updated",
            "peer.deleted": "🗑️ Peer Deleted",
            "peer.connected": "🟢 Peer Connected",
            "peer.disconnected": "🔴 Peer Disconnected",
            "peer.migrated": "🔀 Peer Migrated",
            "backup.created": "💾 Backup Created",
            "backup.restored": "♻️ Backup Restored",
            "backup.deleted": "🗑️ Backup Deleted",
            "settings.updated": "⚙️ Settings Updated",
        }
        
        event_display = event_emoji_map.get(event_type, f"🔔 {event_type.replace('_', ' ').title()}")
        
        # Build simple message
        message_text = f"<b>{event_display}</b>\n\n"
        
        # Server/Peer ID and Name
        if resource_id != "N/A":
            message_text += f"<b>ID:</b> #{resource_id}\n"
        
        if metadata.get("name"):
            message_text += f"<b>Name:</b> {metadata['name']}\n"
        
        # Interface name only
        if metadata.get("interface"):
            message_text += f"<b>Interface:</b> {metadata['interface']}\n"
        elif metadata.get("allowed_ips"):
            message_text += f"<b>Allowed IPs:</b> <code>{metadata['allowed_ips']}</code>\n"
        
        # Timestamp
        if timestamp:
            message_text += f"\n<i>{timestamp}</i>"
        
        # Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                print(f"Telegram integration {integration.id} triggered successfully")
        except httpx.HTTPError as e:
            print(f"Telegram integration {integration.id} failed: {e}")
        except Exception as e:
            print(f"Telegram integration {integration.id} error: {e}")

    async def _trigger_email(self, integration: Integration, event_data: dict):
        """Send email notification."""
        config = integration.config
        smtp_host = config.get("smtp_host")
        smtp_port = config.get("smtp_port", 587)
        username = config.get("username")
        password = config.get("password")
        from_addr = config.get("from")
        to_addrs = config.get("to", [])
        
        if not all([smtp_host, username, password, from_addr, to_addrs]):
            print(f"Email integration {integration.id} missing required config")
            return
        
        # Format email
        event_type = event_data.get("event_type", "unknown")
        resource_type = event_data.get("resource_type", "resource")
        resource_id = event_data.get("resource_id", "N/A")
        metadata = event_data.get("metadata", {})
        
        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Linguard Event: {event_type.replace('_', ' ').title()}"
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
        
        # Plain text version
        text_content = f"""
Linguard Event Notification

Event Type: {event_type.replace('_', ' ').title()}
Resource Type: {resource_type}
Resource ID: {resource_id}

"""
        if metadata:
            text_content += "Details:\n"
            for key, value in metadata.items():
                text_content += f"  {key.replace('_', ' ').title()}: {value}\n"
        
        # HTML version
        html_content = f"""
<html>
  <body style="font-family: Arial, sans-serif;">
    <h2 style="color: #2563eb;">🔔 Linguard Event Notification</h2>
    <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px;">
      <p><strong>Event Type:</strong> {event_type.replace('_', ' ').title()}</p>
      <p><strong>Resource Type:</strong> {resource_type}</p>
      <p><strong>Resource ID:</strong> {resource_id}</p>
"""
        if metadata:
            html_content += "<h3>Details:</h3><ul>"
            for key, value in metadata.items():
                html_content += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
            html_content += "</ul>"
        
        html_content += """
    </div>
    <p style="color: #6b7280; font-size: 12px; margin-top: 20px;">
      This is an automated notification from Linguard VPN Management.
    </p>
  </body>
</html>
"""
        
        # Attach both versions
        part1 = MIMEText(text_content, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        try:
            async with aiosmtplib.SMTP(hostname=smtp_host, port=smtp_port) as smtp:
                await smtp.starttls()
                await smtp.login(username, password)
                await smtp.send_message(msg)
                print(f"Email integration {integration.id} triggered successfully")
        except aiosmtplib.SMTPException as e:
            print(f"Email integration {integration.id} SMTP error: {e}")
        except Exception as e:
            print(f"Email integration {integration.id} error: {e}")
    
    async def _trigger_plugin(
        self,
        db: AsyncSession,
        integration: Integration,
        event_data: dict
    ):
        """Trigger a plugin-based integration."""
        if not self.plugin_manager:
            print(f"Plugin integration {integration.id}: Plugin manager not initialized")
            return
        
        if not integration.plugin_id:
            print(f"Plugin integration {integration.id} missing plugin_id")
            return
        
        try:
            # Get the plugin instance from the plugin manager
            # The plugin manager maintains loaded plugin instances
            # We pass the event to the plugin which will handle it based on its handlers
            await self.plugin_manager.trigger_plugin_for_integration(
                integration.plugin_id,
                event_data
            )
            print(f"Plugin integration {integration.id} triggered successfully")
        except Exception as e:
            print(f"Plugin integration {integration.id} error: {e}")

    def initialize_event_handlers(self):
        """
        Initialize event handlers to listen for events and dispatch to integrations.
        
        This should be called on application startup.
        """
        # Subscribe to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, self._create_event_handler(event_type))

    def _create_event_handler(self, event_type: EventType):
        """Create an event handler for a specific event type."""
        async def handler(event_data: dict):
            # This will be called when an event occurs
            # We need to get a database session here - this would typically
            # come from a dependency injection system or database pool
            # For now, we'll skip the actual dispatch in the handler
            # and instead call dispatch_event_to_integrations from the API layer
            pass
        
        return handler
