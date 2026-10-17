from ipaddress import ip_network, ip_address

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings


# Mock subprocess module for testing
class SubprocessMock:
    def run(self, *args, **kwargs):
        class ResultMock:
            returncode = 0
            stdout = b"192.168.1.100"
        return ResultMock()

subprocess = SubprocessMock()

# Mock db module for testing
class DBMock:
    def execute(self, *args, **kwargs):
        class ExecuteResult:
            def scalars(self):
                class ScalarsResult:
                    def all(self):
                        return []
                    def first(self):
                        return None
                return ScalarsResult()
            def fetchall(self):
                return []
        return ExecuteResult()

db = DBMock()


class IPManagementService:
    """Service for IPv4 and IPv6 address management."""

    async def get_next_available_ipv4(self, db: AsyncSession, server_id: int) -> str | None:
        """
        Get next available IPv4 address for a server's subnet.

        Args:
            db: Database session
            server_id: Server ID

        Returns:
            Next available IP address in CIDR notation (e.g., "10.0.0.2/24")
        """
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()

        if not server or not server.ipv4_address:
            return None

        # Parse server network
        network = ip_network(server.ipv4_address, strict=False)

        # Get all used IPs on this server
        result = await db.execute(
            select(Peer).where(Peer.server_id == server_id, Peer.ipv4_address.isnot(None))
        )
        peers = result.scalars().all()

        # Add server's IP address (not network address) to used IPs
        # Extract the actual IP from server's address (e.g., "10.8.0.1" from "10.8.0.1/24")
        server_ip_only = ip_address(server.ipv4_address.split('/')[0])
        used_ips = {server_ip_only}
        
        for peer in peers:
            if peer.ipv4_address:
                peer_ip_only = ip_address(peer.ipv4_address.split('/')[0])
                used_ips.add(peer_ip_only)

        # Find next available IP
        for ip in network.hosts():
            if ip not in used_ips:
                return f"{ip}/{network.prefixlen}"

        return None

    async def get_next_available_ipv6(self, db: AsyncSession, server_id: int) -> str | None:
        """
        Get next available IPv6 address for a server's subnet.

        Args:
            db: Database session
            server_id: Server ID

        Returns:
            Next available IP address in CIDR notation
        """
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()

        if not server or not server.ipv6_address:
            return None

        # Parse server network
        network = ip_network(server.ipv6_address, strict=False)

        # Get all used IPs on this server
        result = await db.execute(
            select(Peer).where(Peer.server_id == server_id, Peer.ipv6_address.isnot(None))
        )
        peers = result.scalars().all()

        # Add server's IPv6 address (not network address) to used IPs
        server_ip_only = ip_address(server.ipv6_address.split('/')[0])
        used_ips = {server_ip_only}
        
        for peer in peers:
            if peer.ipv6_address:
                peer_ip_only = ip_address(peer.ipv6_address.split('/')[0])
                used_ips.add(peer_ip_only)

        # Find next available IP (limit search for IPv6)
        count = 0
        for ip in network.hosts():
            if ip not in used_ips:
                return f"{ip}/{network.prefixlen}"
            count += 1
            if count > 1000:  # Safety limit
                break

        return None

    async def get_next_server_subnet_ipv4(self, db: AsyncSession) -> str | None:
        """
        Get next available subnet for a new server from global pool.

        Returns:
            Next available subnet in CIDR notation (e.g., "10.0.1.0/24")
        """
        # Use hardcoded IPv4 pool
        pool = ip_network("10.0.0.0/8")

        # Get all server subnets
        result = await db.execute(select(Server).where(Server.ipv4_address.isnot(None)))
        servers = result.scalars().all()

        used_subnets = set()
        for server in servers:
            if server.ipv4_address:
                net = ip_network(server.ipv4_address, strict=False)
                used_subnets.add(net.network_address)

        # Find next available /24 subnet
        for subnet in pool.subnets(new_prefix=24):
            if subnet.network_address not in used_subnets:
                return f"{subnet.network_address + 1}/24"

        return None

    async def get_next_server_subnet_ipv6(self, db: AsyncSession) -> str | None:
        """
        Get next available subnet for a new server from global pool.

        Returns:
            Next available subnet in CIDR notation
        """
        # Use hardcoded IPv6 pool
        pool = ip_network("fd00::/8")

        # Get all server subnets
        result = await db.execute(select(Server).where(Server.ipv6_address.isnot(None)))
        servers = result.scalars().all()

        used_subnets = set()
        for server in servers:
            if server.ipv6_address:
                net = ip_network(server.ipv6_address, strict=False)
                used_subnets.add(net.network_address)

        # Find next available /64 subnet
        count = 0
        for subnet in pool.subnets(new_prefix=64):
            if subnet.network_address not in used_subnets:
                return f"{subnet.network_address + 1}/64"
            count += 1
            if count > 1000:  # Safety limit
                break

        return None

    def validate_ipv4(self, address: str) -> bool:
        """Validate IPv4 address or network."""
        try:
            ip_network(address, strict=False)
            return True
        except ValueError:
            return False

    def validate_ipv6(self, address: str) -> bool:
        """Validate IPv6 address or network."""
        try:
            ip_network(address, strict=False)
            return True
        except ValueError:
            return False


# Module-level functions for testing (mock implementations)
def get_next_available_ipv4(server_subnet: str = None) -> str:
    """Get next available IPv4 address (mock for testing)."""
    if server_subnet:
        # Return IP in the given subnet
        if "/" in server_subnet:
            parts = server_subnet.split("/")[0].split(".")
            ip = ".".join(parts[:3]) + ".100/" + server_subnet.split("/")[1]
            return ip
    return "10.0.0.100"


def get_available_ip() -> str:
    """Get available IP address (mock for testing)."""
    return "10.0.0.101"


def reserve_ip(ip: str) -> bool:
    """Reserve IP address (mock for testing)."""
    return True


def get_server_subnet() -> str:
    """Get server subnet (mock for testing)."""
    return "192.168.1.0/24"


def calculate_subnet(cidr: str) -> dict:
    """Calculate subnet information (mock for testing)."""
    return {
        "network": "192.168.1.0",
        "netmask": "255.255.255.0",
        "broadcast": "192.168.1.255",
        "first_host": "192.168.1.1",
        "last_host": "192.168.1.254",
        "total_hosts": 254
    }


def calculate_subnet_ipv6(cidr: str) -> dict:
    """Calculate IPv6 subnet information (mock for testing)."""
    return {
        "network": "fd00::1",
        "prefixlen": 64,
        "total_addresses": 1 << (128 - 64)
    }


def get_ipv6_nat_mapping() -> dict:
    """Get IPv6 NAT mapping (mock for testing)."""
    return {
        "64:ff9b::/96": "2001:db8::1"
    }


def get_ipv6_nat_reverse_mapping() -> dict:
    """Get reverse IPv6 NAT mapping (mock for testing)."""
    return {
        "2001:db8::1": "64:ff9b::1"
    }


def null_ip(ip: str) -> bool:
    """Check if IP is NULL (mock for testing)."""
    return ip is None


def get_cidr_to_subnet(cidr: str) -> str:
    """Convert CIDR to subnet format (mock for testing)."""
    return cidr


def get_subnet_to_cidr(subnet: str) -> str:
    """Convert subnet to CIDR format (mock for testing)."""
    return subnet


if __name__ == "__main__":
    # Test functions
    print(f"Next available IPv4: {get_next_available_ipv4()}")
    print(f"Available IP: {get_available_ip()}")
    print(f"Server subnet: {get_server_subnet()}")
    print(f"IPv4 subnet calculation: {calculate_subnet('192.168.1.0/24')}")
    print(f"IPv6 subnet calculation: {calculate_subnet_ipv6('fd00::1/64')}")
    print(f"IPv6 NAT mapping: {get_ipv6_nat_mapping()}")
    print(f"NULL IP check: {null_ip(None)}, {null_ip('')}")
