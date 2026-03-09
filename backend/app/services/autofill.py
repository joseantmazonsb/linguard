from sqlalchemy.ext.asyncio import AsyncSession

from .dns_hierarchy import DNSHierarchyService
from .ip_management import IPManagementService
from .wireguard import WireGuardService


class AutoFillService:
    """Service for auto-filling form fields with intelligent defaults."""

    def __init__(
        self,
        ip_management_service: IPManagementService,
        dns_hierarchy_service: DNSHierarchyService,
        wireguard_service: WireGuardService
    ):
        self.ip_management_service = ip_management_service
        self.dns_hierarchy_service = dns_hierarchy_service
        self.wireguard_service = wireguard_service

    async def get_server_defaults(self, db: AsyncSession) -> dict:
        """
        Get default values for creating a new server.

        Returns:
            Dictionary with default values
        """
        # Get DNS defaults
        dns_primary, dns_secondary = await self.dns_hierarchy_service.get_default_dns_for_new_server(db)

        # Get next available port (starting from 51820)
        from sqlalchemy import func, select

        from ..models.server import Server

        result = await db.execute(select(func.max(Server.listen_port)))
        max_port = result.scalar()
        next_port = (max_port + 1) if max_port and max_port >= 51820 else 51820

        # Get next available subnets
        ipv4_address = await self.ip_management_service.get_next_server_subnet_ipv4(db)
        ipv6_address = await self.ip_management_service.get_next_server_subnet_ipv6(db)

        # Generate keypair
        private_key, public_key = self.wireguard_service.generate_keypair()

        # Get next interface name
        result = await db.execute(select(func.count(Server.id)))
        server_count = result.scalar() or 0
        interface = f"wg{server_count}"

        return {
            "interface": interface,
            "listen_port": next_port,
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary,
            "private_key": private_key,
            "public_key": public_key,
            "is_bounce_server": False,
            "enabled": True
        }

    async def get_peer_defaults(self, db: AsyncSession, server_id: int) -> dict:
        """
        Get default values for creating a new peer.

        Args:
            db: Database session
            server_id: Server ID where the peer will be added

        Returns:
            Dictionary with default values
        """
        # Get DNS defaults from server hierarchy
        dns_primary, dns_secondary = await self.dns_hierarchy_service.get_default_dns_for_server(db, server_id)

        # Get next available IPs
        ipv4_address = await self.ip_management_service.get_next_available_ipv4(db, server_id)
        ipv6_address = await self.ip_management_service.get_next_available_ipv6(db, server_id)

        # Generate keypair
        private_key, public_key = self.wireguard_service.generate_keypair()

        # Generate preshared key
        preshared_key = self.wireguard_service.generate_preshared_key()

        # Default allowed IPs (full tunnel)
        ipv4_allowed_ips = "0.0.0.0/0"
        ipv6_allowed_ips = "::/0"

        return {
            "server_id": server_id,
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "ipv4_allowed_ips": ipv4_allowed_ips,
            "ipv6_allowed_ips": ipv6_allowed_ips,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary,
            "private_key": private_key,
            "public_key": public_key,
            "preshared_key": preshared_key,
            "persistent_keepalive": 25,
            "enabled": True
        }
