from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..models.peer import Peer
from ..models.server import Server
from ..services.dns_hierarchy import DNSHierarchyService
from ..services.ip_management import IPManagementService

# Import for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..services.audit_logger import AuditService


class MigrationService:
    """Service for migrating peers between servers."""

    def __init__(
        self,
        ip_management_service: IPManagementService,
        dns_hierarchy_service: DNSHierarchyService,
        audit_service: "AuditService"
    ):
        self.ip_management_service = ip_management_service
        self.dns_hierarchy_service = dns_hierarchy_service
        self.audit_service = audit_service

    async def migrate_peer(
        self,
        db: AsyncSession,
        peer_id: int,
        target_server_id: int,
        user_id: int,
        custom_config: dict | None = None
    ) -> dict:
        """
        Migrate a peer from one server to another.
        
        Keys (public_key, private_key, preshared_key) are ALWAYS preserved during migration.

        Args:
            db: Database session
            peer_id: Peer to migrate
            target_server_id: Destination server
            user_id: User performing the migration
            custom_config: Optional custom configuration (ipv4_address, ipv6_address, dns_primary, dns_secondary, etc.)

        Returns:
            Migration result with old and new configurations
        """
        # Get peer
        result = await db.execute(select(Peer).where(Peer.id == peer_id))
        peer = result.scalar_one_or_none()

        if not peer:
            raise ValueError("Peer not found")

        # Get source and target servers
        result = await db.execute(select(Server).where(Server.id == peer.server_id))
        source_server = result.scalar_one_or_none()

        result = await db.execute(select(Server).where(Server.id == target_server_id))
        target_server = result.scalar_one_or_none()

        if not target_server:
            raise ValueError("Target server not found")

        # Store old values
        old_server_id = peer.server_id
        old_ipv4 = peer.ipv4_address
        old_ipv6 = peer.ipv6_address
        old_dns_primary = peer.dns_primary
        old_dns_secondary = peer.dns_secondary

        # Update server assignment
        peer.server_id = target_server_id

        # Apply custom configuration if provided
        if custom_config:
            # IP addresses
            if 'ipv4_address' in custom_config and custom_config['ipv4_address']:
                peer.ipv4_address = custom_config['ipv4_address']
            if 'ipv6_address' in custom_config and custom_config['ipv6_address']:
                peer.ipv6_address = custom_config['ipv6_address']
            
            # DNS settings
            if 'dns_primary' in custom_config:
                peer.dns_primary = custom_config['dns_primary']
            if 'dns_secondary' in custom_config:
                peer.dns_secondary = custom_config['dns_secondary']
            
            # Allowed IPs
            if 'ipv4_allowed_ips' in custom_config:
                peer.ipv4_allowed_ips = custom_config['ipv4_allowed_ips']
            if 'ipv6_allowed_ips' in custom_config:
                peer.ipv6_allowed_ips = custom_config['ipv6_allowed_ips']
            
            # Keepalive
            if 'persistent_keepalive' in custom_config and custom_config['persistent_keepalive']:
                peer.persistent_keepalive = custom_config['persistent_keepalive']
        else:
            # Auto-assign new IPs if no custom config provided
            new_ipv4 = await self.ip_management_service.get_next_available_ipv4(db, target_server_id)
            new_ipv6 = await self.ip_management_service.get_next_available_ipv6(db, target_server_id)

            peer.ipv4_address = new_ipv4
            peer.ipv6_address = new_ipv6
            
            # Update DNS to match target server defaults
            dns_primary, dns_secondary = await self.dns_hierarchy_service.get_default_dns_for_server(db, target_server_id)
            peer.dns_primary = dns_primary
            peer.dns_secondary = dns_secondary

        await db.flush()

        # Publish migration event
        await event_bus.publish(
            EventType.PEER_MIGRATED,
            "peer",
            peer.id,
            {
                "peer_name": peer.name,
                "source_server_id": old_server_id,
                "source_server_name": source_server.name if source_server else None,
                "target_server_id": target_server_id,
                "target_server_name": target_server.name,
                "old_ipv4": old_ipv4,
                "old_ipv6": old_ipv6,
                "new_ipv4": peer.ipv4_address,
                "new_ipv6": peer.ipv6_address,
                "custom_config": custom_config is not None
            },
            user_id
        )

        return {
            "success": True,
            "peer_id": peer.id,
            "peer_name": peer.name,
            "source_server": {
                "id": old_server_id,
                "name": source_server.name if source_server else None
            },
            "target_server": {
                "id": target_server_id,
                "name": target_server.name
            },
            "old_configuration": {
                "ipv4_address": old_ipv4,
                "ipv6_address": old_ipv6
            },
            "new_configuration": {
                "ipv4_address": peer.ipv4_address,
                "ipv6_address": peer.ipv6_address,
                "dns_primary": peer.dns_primary,
                "dns_secondary": peer.dns_secondary
            }
        }

    async def bulk_migrate_peers(
        self,
        db: AsyncSession,
        peer_ids: list[int],
        target_server_id: int,
        user_id: int
    ) -> dict:
        """
        Migrate multiple peers to a target server.

        Args:
            db: Database session
            peer_ids: List of peer IDs to migrate
            target_server_id: Destination server
            user_id: User performing the migration

        Returns:
            Bulk migration results
        """
        results = []
        errors = []

        for peer_id in peer_ids:
            try:
                result = await self.migrate_peer(
                    db, peer_id, target_server_id, user_id, None
                )
                results.append(result)
            except Exception as e:
                errors.append({
                    "peer_id": peer_id,
                    "error": str(e)
                })

        return {
            "success": len(errors) == 0,
            "migrated": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }
