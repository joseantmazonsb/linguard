import json
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..models.backup import Backup
from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings
from ..models.integration import Integration
from ..models.traffic_trigger import TrafficTrigger
from ..models.plugin import Plugin


class BackupService:
    """Service for creating and restoring backups."""
    
    def __init__(self, settings_service=None):
        """
        Initialize backup service.
        
        Args:
            settings_service: Optional SettingsService for getting backup directory from database.
                            If None, will use default 'backups' directory.
        """
        self.settings_service = settings_service

    async def _filename_exists_in_db(self, db: AsyncSession, filename: str) -> bool:
        """Check if a backup with the given filename already exists in the database."""
        result = await db.execute(
            select(Backup).where(Backup.filename == filename)
        )
        return result.scalar_one_or_none() is not None

    async def create_backup(
        self,
        db: AsyncSession,
        user_id: int,
        description: str | None = None,
        encrypt: bool = False,
        passphrase: str | None = None
    ) -> Backup:
        """
        Create a full backup of all configurations.

        Args:
            db: Database session
            user_id: User creating the backup
            description: Optional backup description
            encrypt: Whether to encrypt the backup (not implemented, defaults to False)
            passphrase: Encryption passphrase (not implemented, ignored)

        Returns:
            Backup model instance
        """
        # Note: Encryption is not currently implemented
        encrypt = False
        
        # Gather all data
        backup_data = {
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "global_settings": {},
            "servers": [],
            "peers": [],
            "integrations": [],
            "traffic_triggers": [],
            "plugins": []
        }

        # Global settings
        result = await db.execute(select(GlobalSettings))
        global_settings = result.scalar_one_or_none()
        if global_settings:
            backup_data["global_settings"] = {
                "dns_primary": global_settings.dns_primary,
                "dns_secondary": global_settings.dns_secondary,
            }

        # Servers
        result = await db.execute(select(Server))
        servers = result.scalars().all()
        for server in servers:
            backup_data["servers"].append({
                "id": server.id,
                "name": server.name,
                "interface": server.interface,
                "description": server.description,
                "public_key": server.public_key,
                "private_key": server.private_key,
                "endpoint": server.endpoint,
                "listen_port": server.listen_port,
                "ipv4_address": server.ipv4_address,
                "ipv6_address": server.ipv6_address,
                "dns_primary": server.dns_primary,
                "dns_secondary": server.dns_secondary,
                "is_bounce_server": server.is_bounce_server,
                "bounce_via_server_id": server.bounce_via_server_id,
                "enabled": server.enabled
            })

        # Peers
        result = await db.execute(select(Peer))
        peers = result.scalars().all()
        for peer in peers:
            backup_data["peers"].append({
                "id": peer.id,
                "server_id": peer.server_id,
                "name": peer.name,
                "description": peer.description,
                "email": peer.email,
                "public_key": peer.public_key,
                "private_key": peer.private_key,
                "preshared_key": peer.preshared_key,
                "ipv4_address": peer.ipv4_address,
                "ipv6_address": peer.ipv6_address,
                "ipv4_allowed_ips": peer.ipv4_allowed_ips,
                "ipv6_allowed_ips": peer.ipv6_allowed_ips,
                "dns_primary": peer.dns_primary,
                "dns_secondary": peer.dns_secondary,
                "persistent_keepalive": peer.persistent_keepalive,
                "endpoint": peer.endpoint,
                "enabled": peer.enabled
            })

        # Integrations
        result = await db.execute(select(Integration))
        integrations = result.scalars().all()
        for integration in integrations:
            backup_data["integrations"].append({
                "id": integration.id,
                "name": integration.name,
                "description": integration.description,
                "type": integration.type,
                "config": integration.config,
                "events_subscribed": integration.events_subscribed,
                "enabled": integration.enabled,
                "plugin_id": integration.plugin_id
            })

        # Traffic Triggers
        result = await db.execute(select(TrafficTrigger))
        triggers = result.scalars().all()
        for trigger in triggers:
            backup_data["traffic_triggers"].append({
                "id": trigger.id,
                "name": trigger.name,
                "scope": trigger.scope,
                "peer_id": trigger.peer_id,
                "server_id": trigger.server_id,
                "direction": trigger.direction,
                "threshold_bytes": trigger.threshold_bytes,
                "window": trigger.window,
                "cooldown_seconds": trigger.cooldown_seconds,
                "enabled": trigger.enabled,
                "trigger_integrations": trigger.trigger_integrations
            })

        # Plugins
        result = await db.execute(select(Plugin))
        plugins = result.scalars().all()
        for plugin in plugins:
            backup_data["plugins"].append({
                "id": plugin.id,
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "module_name": plugin.module_name,
                "file_path": plugin.file_path,
                "config_schema": plugin.config_schema,
                "config": plugin.config,
                "enabled": plugin.enabled,
                "subscribed_events": plugin.subscribed_events,
                "requirements": plugin.requirements
            })

        # Convert to JSON
        json_data = json.dumps(backup_data, indent=2)

        # Encrypt if requested
        if encrypt:
            if not passphrase:
                raise ValueError("Passphrase required for encryption")
            # TODO: Implement encryption
            # For now, just encode as base64
            import base64
            json_data = base64.b64encode(json_data.encode()).decode()

        # Get backup directory from settings (or use default)
        if self.settings_service:
            backup_dir = await self.settings_service.get_backup_dir(db)
        else:
            backup_dir = "backups"  # Fallback for tests or before setup
        
        # Save to file with unique filename
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate unique filename with microseconds for uniqueness
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        microseconds = datetime.utcnow().strftime("%f")[:3]  # Get first 3 digits of microseconds (milliseconds)
        base_filename = f"wireguard_backup_{timestamp}_{microseconds}.json"
        filename = base_filename
        filepath = os.path.join(backup_dir, filename)
        
        # Additional safety: If file exists on disk OR filename exists in database, add counter
        counter = 1
        while os.path.exists(filepath) or await self._filename_exists_in_db(db, filename):
            filename = f"wireguard_backup_{timestamp}_{microseconds}_{counter}.json"
            filepath = os.path.join(backup_dir, filename)
            counter += 1

        with open(filepath, 'w') as f:
            f.write(json_data)

        # Get file size
        file_size = os.path.getsize(filepath)

        # Create backup record
        backup = Backup(
            filename=filename,
            description=description,
            size_bytes=file_size,
            is_encrypted=encrypt,
            servers_count=len(backup_data["servers"]),
            peers_count=len(backup_data["peers"]),
            created_by_user_id=user_id
        )

        db.add(backup)
        await db.flush()
        await db.refresh(backup)

        # Publish event
        await event_bus.publish(
            EventType.BACKUP_CREATED,
            "backup",
            backup.id,
            {
                "filename": filename,
                "servers_count": backup.servers_count,
                "peers_count": backup.peers_count,
                "integrations_count": len(backup_data["integrations"]),
                "traffic_triggers_count": len(backup_data["traffic_triggers"]),
                "plugins_count": len(backup_data["plugins"]),
                "encrypted": encrypt
            },
            user_id
        )

        return backup

    async def restore_backup(
        self,
        db: AsyncSession,
        backup_id: int,
        user_id: int,
        passphrase: str | None = None,
        clear_existing: bool = False
    ) -> dict:
        """
        Restore from a backup.

        Args:
            db: Database session
            backup_id: Backup to restore
            user_id: User performing restore
            passphrase: Decryption passphrase (if encrypted)
            clear_existing: Whether to clear existing data first

        Returns:
            Restore result summary
        """
        # Get backup record
        result = await db.execute(select(Backup).where(Backup.id == backup_id))
        backup = result.scalar_one_or_none()

        if not backup:
            raise ValueError("Backup not found")

        # Get backup directory from settings (or use default)
        if self.settings_service:
            backup_dir = await self.settings_service.get_backup_dir(db)
        else:
            backup_dir = "backups"  # Fallback

        # Read backup file
        filepath = os.path.join(backup_dir, backup.filename)

        if not os.path.exists(filepath):
            raise ValueError("Backup file not found")

        with open(filepath) as f:
            json_data = f.read()

        # Decrypt if needed
        if backup.is_encrypted:
            if not passphrase:
                raise ValueError("Passphrase required for encrypted backup")
            # TODO: Implement decryption
            import base64
            json_data = base64.b64decode(json_data.encode()).decode()

        # Parse JSON
        backup_data = json.loads(json_data)

        # Clear existing data if requested
        if clear_existing:
            await db.execute(TrafficTrigger.__table__.delete())
            await db.execute(Integration.__table__.delete())
            await db.execute(Peer.__table__.delete())
            await db.execute(Server.__table__.delete())
            # Note: We don't delete plugins as they are discovered from filesystem

        # Restore global settings
        if "global_settings" in backup_data:
            gs_data = backup_data["global_settings"]
            result = await db.execute(select(GlobalSettings))
            global_settings = result.scalar_one_or_none()

            if global_settings:
                for key, value in gs_data.items():
                    setattr(global_settings, key, value)
            else:
                global_settings = GlobalSettings(**gs_data)
                db.add(global_settings)

        # Restore servers
        server_id_map = {}
        for server_data in backup_data.get("servers", []):
            old_id = server_data.pop("id")
            
            # Check if server with same name already exists
            result = await db.execute(
                select(Server).where(Server.name == server_data["name"])
            )
            existing_server = result.scalar_one_or_none()
            
            if existing_server:
                # Skip this server and map old ID to existing ID
                server_id_map[old_id] = existing_server.id
            else:
                # Create new server
                server = Server(**server_data)
                db.add(server)
                await db.flush()
                await db.refresh(server)
                server_id_map[old_id] = server.id

        # Restore peers
        peer_id_map = {}
        for peer_data in backup_data.get("peers", []):
            old_id = peer_data.pop("id")
            # Map old server_id to new server_id
            old_server_id = peer_data["server_id"]
            if old_server_id in server_id_map:
                peer_data["server_id"] = server_id_map[old_server_id]
                
                # Check if peer with same name already exists on this server
                result = await db.execute(
                    select(Peer).where(
                        Peer.name == peer_data["name"],
                        Peer.server_id == peer_data["server_id"]
                    )
                )
                existing_peer = result.scalar_one_or_none()
                
                if existing_peer:
                    # Skip this peer and map old ID to existing ID
                    peer_id_map[old_id] = existing_peer.id
                else:
                    # Create new peer
                    peer = Peer(**peer_data)
                    db.add(peer)
                    await db.flush()
                    await db.refresh(peer)
                    peer_id_map[old_id] = peer.id

        # Restore plugins
        plugin_id_map = {}
        plugin_module_map = {}
        for plugin_data in backup_data.get("plugins", []):
            old_id = plugin_data.pop("id")
            module_name = plugin_data["module_name"]
            
            # Check if plugin already exists
            result = await db.execute(
                select(Plugin).where(Plugin.module_name == module_name)
            )
            existing_plugin = result.scalar_one_or_none()
            
            if existing_plugin:
                # Update existing plugin config and enabled status
                existing_plugin.config = plugin_data.get("config", {})
                existing_plugin.enabled = plugin_data.get("enabled", True)
                plugin_id_map[old_id] = existing_plugin.id
                plugin_module_map[module_name] = existing_plugin.id
            else:
                # Plugin doesn't exist - it needs to be discovered first
                # We'll just map the module name for integrations
                plugin_module_map[module_name] = None

        # Restore integrations
        integration_id_map = {}
        for integration_data in backup_data.get("integrations", []):
            old_id = integration_data.pop("id")
            
            # Handle plugin_id mapping
            if integration_data.get("plugin_id"):
                old_plugin_id = integration_data["plugin_id"]
                if old_plugin_id in plugin_id_map:
                    integration_data["plugin_id"] = plugin_id_map[old_plugin_id]
                else:
                    # Plugin doesn't exist, skip this integration
                    continue
            
            integration = Integration(**integration_data)
            db.add(integration)
            await db.flush()
            await db.refresh(integration)
            integration_id_map[old_id] = integration.id

        # Restore traffic triggers
        for trigger_data in backup_data.get("traffic_triggers", []):
            trigger_data.pop("id")
            
            # Map old peer_id to new peer_id
            if trigger_data.get("peer_id"):
                old_peer_id = trigger_data["peer_id"]
                if old_peer_id in peer_id_map:
                    trigger_data["peer_id"] = peer_id_map[old_peer_id]
                else:
                    # Peer doesn't exist, skip this trigger
                    continue
            
            # Map old server_id to new server_id
            if trigger_data.get("server_id"):
                old_server_id = trigger_data["server_id"]
                if old_server_id in server_id_map:
                    trigger_data["server_id"] = server_id_map[old_server_id]
                else:
                    # Server doesn't exist, skip this trigger
                    continue
            
            # Map old integration IDs to new integration IDs
            if trigger_data.get("trigger_integrations"):
                old_integration_ids = trigger_data["trigger_integrations"]
                new_integration_ids = []
                for old_int_id in old_integration_ids:
                    if old_int_id in integration_id_map:
                        new_integration_ids.append(integration_id_map[old_int_id])
                trigger_data["trigger_integrations"] = new_integration_ids
            
            trigger = TrafficTrigger(**trigger_data)
            db.add(trigger)

        await db.flush()

        # Publish event
        await event_bus.publish(
            EventType.BACKUP_RESTORED,
            "backup",
            backup.id,
            {
                "filename": backup.filename,
                "servers_restored": len(backup_data.get("servers", [])),
                "peers_restored": len(backup_data.get("peers", [])),
                "integrations_restored": len(backup_data.get("integrations", [])),
                "traffic_triggers_restored": len(backup_data.get("traffic_triggers", [])),
                "plugins_restored": len(backup_data.get("plugins", [])),
                "cleared_existing": clear_existing
            },
            user_id
        )

        return {
            "success": True,
            "servers_restored": len(backup_data.get("servers", [])),
            "peers_restored": len(backup_data.get("peers", [])),
            "integrations_restored": len(backup_data.get("integrations", [])),
            "traffic_triggers_restored": len(backup_data.get("traffic_triggers", [])),
            "plugins_restored": len(backup_data.get("plugins", [])),
            "cleared_existing": clear_existing
        }

    async def import_backup(
        self,
        db: AsyncSession,
        file_path: str,
        user_id: int,
        description: str | None = None
    ) -> Backup:
        """
        Import a backup file from an uploaded file.

        Args:
            db: Database session
            file_path: Path to the uploaded backup file
            user_id: User importing the backup
            description: Optional backup description

        Returns:
            Backup model instance
        """
        # Read and validate the backup file
        with open(file_path, 'r') as f:
            json_data = f.read()

        # Try to parse JSON to validate
        try:
            backup_data = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

        # Validate backup structure
        if "version" not in backup_data:
            raise ValueError("Invalid backup file: missing version")

        # Get backup directory from settings (or use default)
        if self.settings_service:
            backup_dir = await self.settings_service.get_backup_dir(db)
        else:
            backup_dir = "backups"  # Fallback

        # Copy to backup directory
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"wireguard_backup_{timestamp}_imported.json"
        dest_path = os.path.join(backup_dir, filename)

        # Copy file
        import shutil
        shutil.copy(file_path, dest_path)

        # Get file size
        file_size = os.path.getsize(dest_path)

        # Create backup record
        backup = Backup(
            filename=filename,
            description=description or "Imported backup",
            size_bytes=file_size,
            is_encrypted=False,
            servers_count=len(backup_data.get("servers", [])),
            peers_count=len(backup_data.get("peers", [])),
            created_by_user_id=user_id
        )

        db.add(backup)
        await db.commit()
        await db.refresh(backup)

        return backup
