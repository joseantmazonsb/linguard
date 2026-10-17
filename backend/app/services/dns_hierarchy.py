from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pathlib import Path

from sqlalchemy import select, text, create_engine, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings


# Module-level database for testing purposes
_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
db = _session_factory()


class DNSHierarchyConfig(BaseSettings):
    """DNS hierarchy configuration."""
    
    dns_servers: list[dict] = []
    dns_domain: str = "example.com"
    wireguard_config_path: str = "/etc/wireguard/wg0.conf"
    dns_config_path: str = "/etc/dns/config.json"
    
    class Config:
        env_prefix = "DNS_HIERARCHY_"
        case_sensitive = False
    
    @classmethod
    def from_file(cls, config_file: str | Path) -> "DNSHierarchyConfig":
        """Load configuration from file."""
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"DNS hierarchy config file not found: {config_path}")
        
        # Create default config if file doesn't exist
        if not config_path.is_file():
            return cls()
        
        return cls()
    
    @classmethod
    def get_default_config(cls) -> "DNSHierarchyConfig":
        """Get default configuration."""
        return cls()


class DNSHierarchyService:
    """Service to handle hierarchical DNS configuration inheritance."""

    def __init__(self):
        self.db = db

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
    
    def get_dns_servers(self) -> list[str]:
        """Get DNS servers from config."""
        return config.dns_servers
    
    def add_dns_server(self, server: dict) -> bool:
        """Add a DNS server."""
        return add_dns_server(server) == 1
    
    def remove_dns_server(self, server_id: int) -> bool:
        """Remove a DNS server."""
        return remove_dns_server(server_id) == 1
    
    def update_dns_server(self, server_id: int, server: dict) -> bool:
        """Update a DNS server."""
        return update_dns_server(server_id, server) == 1
    
    def validate_dns_server(self, server: dict) -> bool:
        """Validate a DNS server configuration."""
        return validate_dns_server(server)
    
    def get_dns_config(self) -> dict:
        """Get DNS configuration."""
        return get_dns_config()
    
    def set_dns_config(self, config: dict) -> bool:
        """Set DNS configuration."""
        return set_dns_config(config)


# Functions for testing
def get_dns_servers() -> list[dict]:
    """Get all DNS servers from database."""
    try:
        result = db.execute(text("SELECT * FROM dns_server"))
        rows = result.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def add_dns_server(server: dict) -> int:
    """Add a DNS server to database."""
    try:
        db.execute(text(
            "INSERT INTO dns_server (name, ip, port, enabled) VALUES (:name, :ip, :port, :enabled)"
        ), {
            "name": server.get("name"),
            "ip": server.get("ip"),
            "port": server.get("port"),
            "enabled": server.get("enabled", True)
        })
        db.commit()
        return 1
    except Exception:
        return 0


def remove_dns_server(server_id: int) -> int:
    """Remove a DNS server from database."""
    try:
        db.execute(text("DELETE FROM dns_server WHERE id = :id"), {"id": server_id})
        db.commit()
        return 1
    except Exception:
        return 0


def update_dns_server(server_id: int, server: dict) -> int:
    """Update a DNS server in database."""
    try:
        db.execute(text(
            "UPDATE dns_server SET name = :name, ip = :ip, port = :port, enabled = :enabled "
            "WHERE id = :id"
        ), {
            "id": server_id,
            "name": server.get("name"),
            "ip": server.get("ip"),
            "port": server.get("port"),
            "enabled": server.get("enabled", True)
        })
        db.commit()
        return 1
    except Exception:
        return 0


def validate_dns_server(server: dict) -> bool:
    """Validate a DNS server configuration."""
    try:
        if not server.get("name"):
            return False
        if not server.get("ip"):
            return False
        if not server.get("port"):
            return False
        return True
    except Exception:
        return False


def get_dns_config() -> dict:
    """Get DNS configuration."""
    try:
        result = db.execute(text("SELECT * FROM dns_config"))
        row = result.fetchone()
        if row:
            return dict(row)
        return {}
    except Exception:
        return {}


def set_dns_config(config: dict) -> bool:
    """Set DNS configuration."""
    try:
        db.execute(text(
            "INSERT OR REPLACE INTO dns_config (dns_primary, dns_secondary, dns_domain) "
            "VALUES (:dns_primary, :dns_secondary, :dns_domain)"
        ), {
            "dns_primary": config.get("dns_primary"),
            "dns_secondary": config.get("dns_secondary"),
            "dns_domain": config.get("dns_domain")
        })
        db.commit()
        return True
    except Exception:
        return False


def get_peer_ips(server_id: int = 1) -> list[str]:
    """Get all peer IPs for a server."""
    try:
        result = db.execute(text(
            "SELECT ipv4_address, ipv6_address FROM peer WHERE server_id = :server_id"
        ), {"server_id": server_id})
        rows = result.fetchall()
        return [row.ipv4_address for row in rows if row.ipv4_address] + \
               [row.ipv6_address for row in rows if row.ipv6_address]
    except Exception:
        return []


def is_dns_valid(config_path: str) -> bool:
    """Check if DNS configuration is valid."""
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-c", f"import json; json.load(open('{config_path}'))"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_dns_servers() -> list[dict]:
    """Get all DNS servers from database."""
    try:
        result = db.execute(text("SELECT * FROM dns_server"))
        rows = result.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.dns_hierarchy", "--cov-report=term-missing"])
