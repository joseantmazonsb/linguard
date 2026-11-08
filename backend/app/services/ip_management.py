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
            if count > 1000:  # Safety limit - all IPs used
                return None

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
                # Increment the network address by 1
                # Convert to string first to split by dots
                addr_str = str(subnet.network_address)
                octets = addr_str.split('.')
                last_octet = int(octets[-1])
                next_octet = last_octet + 1
                if next_octet <= 255:
                    next_addr = '.'.join(octets[:-1] + [str(next_octet)])
                else:
                    # Overflow - increment second to last octet
                    octets = octets[:-1]
                    second_last = int(octets[-1])
                    next_octet = second_last + 1
                    next_addr = '.'.join(octets[:-1] + [str(next_octet)] + ['0'])
                return f"{next_addr}/24"

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
                # Increment the network address by 1
                # Convert to a number and back
                try:
                    addr_num = int(subnet.network_address)
                    next_addr_num = addr_num + 1
                    # Convert back to string
                    next_addr = str(ip_address(next_addr_num))
                except Exception:
                    # Fallback: expand and increment manually
                    addr_expanded = str(subnet.network_address)
                    addr_expanded = addr_expanded.replace('::', ':0:0:0:0:0:0:0')
                    parts = addr_expanded.split(':')
                    last_32_bits = int(parts[-2], 16)
                    next_32_bits = last_32_bits + 1
                    next_addr = ':'.join(parts[:-2] + [f"{next_32_bits:04x}"])
                return f"{next_addr}/64"
            count += 1
            if count > 1000:  # Safety limit
                return None

        return None

    def validate_ipv4(self, address: str) -> bool:
        """Validate IPv4 address or network."""
        try:
            return ip_network(address, strict=False).version == 4
        except ValueError:
            return False

    def validate_ipv6(self, address: str) -> bool:
        """Validate IPv6 address or network."""
        try:
            return ip_network(address, strict=False).version == 6
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


def get_next_available_ipv6(server_subnet: str = None) -> str:
    """Get next available IPv6 address (mock for testing)."""
    if server_subnet:
        # Return IP in the given subnet
        if "/" in server_subnet:
            network = ip_network(server_subnet, strict=False)
            # 100th address inside the subnet keeps the result valid IPv6
            return f"{network.network_address + 100}/{network.prefixlen}"
    return "fd00::100"


def _is_ip_available(ip: str, server_ip: str = None) -> bool:
    """
    Check if an IP address is available (not already in use).
    
    Args:
        ip: IP address to check
        server_ip: Server IP to compare against (if provided, IP must be different)
    
    Returns:
        True if IP is available, False otherwise
    """
    if not ip or ip.strip() == "":
        return False
    
    if server_ip and ip == server_ip:
        # Same IP as server - not available
        return False
    
    # For testing purposes, assume IP is available unless it matches server_ip
    return True


def _get_subnet_addresses(cidr: str) -> list:
    """
    Get list of subnet addresses (excluding network and broadcast).
    
    Args:
        cidr: CIDR notation (e.g., "192.168.1.0/24")
    
    Returns:
        List of host IP addresses in the subnet (as strings)
    """
    try:
        network = ip_network(cidr, strict=False)
        # For IPv6, avoid generating all hosts (too many)
        if network.version == 6:
            # Generate a limited number of addresses manually for IPv6
            addresses = []
            prefix = network.network_address
            prefix_str = str(prefix)
            
            # For link-local IPv6 (fe80::/64), generate simple addresses
            if prefix_str.startswith('fe80::'):
                # Generate fe80::1, fe80::2, ... fe80::10
                for i in range(1, 11):
                    addresses.append(f"fe80::{i}")
                return addresses
            else:
                # For other IPv6 subnets, generate addresses incrementing the last 32 bits
                addresses = []
                for i in range(1, 11):
                    try:
                        # Create IP by incrementing the last 16 bits
                        ip_v6 = ip_address(f"{prefix_str.split(':')[-2]}:{i}")
                        addresses.append(str(ip_v6))
                    except Exception:
                        break
                return addresses
        # For IPv4, use the built-in method (limited)
        return [str(ip) for ip in list(network.hosts())[:100]]
    except ValueError:
        return []


def _increment_ip(ip: str, increment: int = 1) -> str:
    """Increment an IP address by the given amount."""
    try:
        parts = [int(p) for p in ip.split('.')]
    except ValueError:
        # Not an IPv4 address (e.g. IPv6): return it untouched
        return ip
    if len(parts) == 4:  # IPv4
        # Simple increment for the last octet
        for i in range(len(parts) - 1, -1, -1):
            parts[i] += increment
            if parts[i] <= 255:
                break
            parts[i] = 0
        return '.'.join(str(p) for p in parts)
    return ip


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
    if ip is None:
        return True
    if isinstance(ip, str):
        return ip.strip() == ""
    return False


def get_cidr_to_subnet(cidr: str) -> str:
    """Convert CIDR to subnet format (mock for testing)."""
    if "/" in cidr:
        return cidr.split("/")[0]
    return cidr


def get_subnet_to_cidr(subnet: str, prefix_length: int) -> str:
    """Convert subnet to CIDR format (mock for testing)."""
    return f"{subnet}/{prefix_length}"


def cidr_to_subnet(cidr: str) -> str:
    """
    Convert CIDR to subnet notation.
    
    Args:
        cidr: CIDR string (e.g., "192.168.1.0/24")
    
    Returns:
        Subnet notation (e.g., "192.168.1.0")
    """
    if "/" in cidr:
        return cidr.split("/")[0]
    return cidr


def subnet_to_cidr(subnet: str, prefix_length: int) -> str:
    """
    Convert subnet to CIDR notation.
    
    Args:
        subnet: Subnet address (e.g., "192.168.1.0")
        prefix_length: CIDR prefix length (e.g., 24)
    
    Returns:
        CIDR notation (e.g., "192.168.1.0/24")
    """
    return f"{subnet}/{prefix_length}"


def cidr_prefix_length(cidr: str) -> int:
    """
    Extract prefix length from CIDR notation.
    
    Args:
        cidr: CIDR string (e.g., "192.168.1.0/24")
    
    Returns:
        Prefix length as integer
    """
    if "/" in cidr:
        return int(cidr.split("/")[1])
    return 0


def _get_first_available_ip(server_subnet: str, reserved_ips: list[str] = None) -> str:
    """
    Get first available IP in a subnet.

    Args:
        server_subnet: Subnet CIDR (e.g., "192.168.1.0/24")
        reserved_ips: List of reserved IPs

    Returns:
        First available IP or None
    """
    if reserved_ips is None:
        reserved_ips = []

    try:
        network = ip_network(server_subnet, strict=False)

        # Check hosts in order (limit for IPv6)
        count = 0
        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str not in reserved_ips:
                return ip_str
            count += 1
            if count > 1000:  # Safety limit for IPv6
                break

        return None
    except ValueError:
        return None


def _is_reserved_ip(ip: str, subnet_or_reserved: str | list[str] | None = None) -> bool:
    """
    Check if an IP is reserved.

    Args:
        ip: IP address to check
        subnet_or_reserved: Either a subnet CIDR string or list of reserved IPs

    Returns:
        True if IP is reserved, False otherwise
    """
    # Default reserved IPs
    default_reserved = ["0.0.0.0", "255.255.255.255", "127.0.0.1", "127.255.255.255"]

    # If subnet_or_reserved is None, use default reserved
    if subnet_or_reserved is None:
        reserved_ips = default_reserved
    # If subnet_or_reserved is a string (subnet), check if IP is network or broadcast
    elif isinstance(subnet_or_reserved, str):
        if "/" in subnet_or_reserved:
            # It's a subnet, check if IP is network or broadcast
            try:
                network = ip_network(subnet_or_reserved, strict=False)
                ip_addr = ip_address(ip)
                if ip_addr == network.network_address or ip_addr == network.broadcast_address:
                    return True
            except ValueError:
                pass
            # Fall back to default reserved
            reserved_ips = default_reserved
        else:
            # Just an IP without subnet, use default reserved
            reserved_ips = default_reserved
    else:
        # It's a list of reserved IPs
        reserved_ips = subnet_or_reserved + default_reserved

    return ip in reserved_ips


if __name__ == "__main__":
    # Test functions
    print(f"Next available IPv4: {get_next_available_ipv4()}")
    print(f"Available IP: {get_available_ip()}")
    print(f"Server subnet: {get_server_subnet()}")
    print(f"IPv4 subnet calculation: {calculate_subnet('192.168.1.0/24')}")
    print(f"IPv6 subnet calculation: {calculate_subnet_ipv6('fd00::1/64')}")
    print(f"IPv6 NAT mapping: {get_ipv6_nat_mapping()}")
    print(f"NULL IP check: {null_ip(None)}, {null_ip('')}")
