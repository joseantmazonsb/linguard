
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings


class DNSHierarchyService:
    """Service to handle hierarchical DNS configuration inheritance."""

    async def get_effective_dns(
        self,
        db: AsyncSession,
        peer_id: int | None = None,
        server_id: int | None = None,
        peer_override_primary: str | None = None,
        peer_override_secondary: str | None = None
    ) -> tuple[str | None, str | None]:
        """
        Get effective DNS based on hierarchy: Peer > Server > Global.

        Args:
            db: Database session
            peer_id: Peer ID to check
            server_id: Server ID to check
            peer_override_primary: Peer-level DNS primary override
            peer_override_secondary: Peer-level DNS secondary override

        Returns:
            Tuple of (primary_dns, secondary_dns)
        """
        primary_dns = None
        secondary_dns = None

        # Level 1: Global settings (lowest priority)
        result = await db.execute(select(GlobalSettings))
        global_settings = result.scalar_one_or_none()
        if global_settings:
            primary_dns = global_settings.dns_primary
            secondary_dns = global_settings.dns_secondary

        # Level 2: Server settings (medium priority)
        if server_id:
            result = await db.execute(select(Server).where(Server.id == server_id))
            server = result.scalar_one_or_none()
            if server:
                if server.dns_primary:
                    primary_dns = server.dns_primary
                if server.dns_secondary:
                    secondary_dns = server.dns_secondary

        # Level 3: Peer settings (highest priority)
        if peer_id:
            result = await db.execute(select(Peer).where(Peer.id == peer_id))
            peer = result.scalar_one_or_none()
            if peer:
                if peer.dns_primary:
                    primary_dns = peer.dns_primary
                if peer.dns_secondary:
                    secondary_dns = peer.dns_secondary

        # Apply direct overrides
        if peer_override_primary is not None:
            primary_dns = peer_override_primary
        if peer_override_secondary is not None:
            secondary_dns = peer_override_secondary

        return primary_dns, secondary_dns

    async def resolve_dns_for_peer(self, db: AsyncSession, peer_id: int) -> tuple[str | None, str | None]:
        """Resolve DNS for a specific peer."""
        return await self.get_effective_dns(db, peer_id=peer_id)

    async def get_default_dns_for_server(self, db: AsyncSession, server_id: int) -> tuple[str | None, str | None]:
        """Get default DNS for new peers on a server."""
        return await self.get_effective_dns(db, server_id=server_id)

    async def get_default_dns_for_new_server(self, db: AsyncSession) -> tuple[str | None, str | None]:
        """Get default DNS for a new server."""
        return await self.get_effective_dns(db)
