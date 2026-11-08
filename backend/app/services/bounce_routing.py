from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.peer import Peer
from ..models.server import Server


class BounceServerService:
    """Service for handling bounce server configurations and routing."""

    async def configure_bounce_routing(
        self,
        db: AsyncSession,
        peer: Peer,
        target_server: Server,
        bounce_server: Server
    ) -> dict:
        """
        Configure routing through a bounce server.

        Args:
            db: Database session
            peer: Peer/client to configure
            target_server: Target server behind bounce
            bounce_server: Bounce server

        Returns:
            Configuration dictionary with updated routing
        """
        # For a bounce server setup, the peer connects to the bounce server
        # and the bounce server forwards traffic to the target server

        # Peer config points to bounce server
        peer_config = {
            "server_endpoint": bounce_server.endpoint,
            "server_port": bounce_server.listen_port,
            "server_public_key": bounce_server.public_key,
            # AllowedIPs should include target server's subnet
            "allowed_ips": f"{target_server.ipv4_address}, {target_server.ipv6_address}"
        }

        # Bounce server needs peer configuration for forwarding
        bounce_peer_config = {
            "public_key": peer.public_key,
            "allowed_ips": f"{peer.ipv4_address}, {peer.ipv6_address}",
            "preshared_key": peer.preshared_key
        }

        # Target server needs routing through bounce
        target_peer_config = {
            "public_key": bounce_server.public_key,
            "allowed_ips": f"{peer.ipv4_address}, {peer.ipv6_address}",
            "endpoint": f"{bounce_server.endpoint}:{bounce_server.listen_port}"
        }

        return {
            "peer_config": peer_config,
            "bounce_peer_config": bounce_peer_config,
            "target_peer_config": target_peer_config
        }

    async def validate_bounce_server(self, db: AsyncSession, server_id: int, bounce_via_id: int) -> bool:
        """
        Validate that a bounce server configuration is valid.

        Args:
            db: Database session
            server_id: Server to configure
            bounce_via_id: Bounce server ID

        Returns:
            True if valid, False otherwise
        """
        # Can't bounce through itself
        if server_id == bounce_via_id:
            return False

        # Check bounce server exists
        result = await db.execute(select(Server).where(Server.id == bounce_via_id))
        bounce_server = result.scalar_one_or_none()

        if not bounce_server:
            return False

        # Bounce server should be marked as bounce server
        if not bounce_server.is_bounce_server:
            return False

        # Check for circular dependencies
        current_bounce = bounce_server.bounce_via_server_id
        visited = {server_id, bounce_via_id}

        while current_bounce:
            if current_bounce in visited:
                return False  # Circular dependency

            visited.add(current_bounce)
            result = await db.execute(select(Server).where(Server.id == current_bounce))
            next_server = result.scalar_one_or_none()

            if not next_server:
                break

            current_bounce = next_server.bounce_via_server_id

        return True

    def generate_bounce_allowed_ips(self, peer_ips: list[str], target_subnets: list[str]) -> str:
        """
        Generate AllowedIPs for bounce server configuration.

        Args:
            peer_ips: List of peer IP addresses
            target_subnets: List of target server subnets

        Returns:
            Comma-separated AllowedIPs string
        """
        all_ips = peer_ips + target_subnets
        return ', '.join(all_ips)
