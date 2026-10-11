"""
Intelligent autocomplete for Linguard CLI.
Provides IP suggestions based on server configuration and network ranges.
"""

import click
import ipaddress
from typing import List, Optional, Tuple


class IPCompleter:
    """Intelligent IP completer with network range suggestions."""
    
    # Common network ranges for suggestions
    PRIVATE_RANGES = [
        ("10.0.0.0/8", "Private Class A (10.0.0.0 - 10.255.255.255)"),
        ("172.16.0.0/12", "Private Class B (172.16.0.0 - 172.31.255.255)"),
        ("192.168.0.0/16", "Private Class C (192.168.0.0 - 192.168.255.255)"),
        ("127.0.0.0/8", "Loopback (127.0.0.0 - 127.255.255.255)"),
    ]
    
    COMMON_SUBNETS = [
        "/24",  # 254 hosts
        "/16",  # 65534 hosts
        "/8",   # 16M hosts
        "/32",  # Single IP
        "/25",  # 126 hosts
        "/26",  # 62 hosts
        "/27",  # 30 hosts
        "/28",  # 14 hosts
        "/29",  # 6 hosts
        "/30",  # 2 hosts
    ]
    
    # Common public IP ranges (for testing/demo)
    COMMON_PATTERNS = [
        ("203.0.113.", "TEST-NET-3 (documentation)"),
        ("198.51.100.", "TEST-NET-2 (documentation)"),
        ("192.0.2.", "TEST-NET-1 (documentation)"),
        ("8.8.8.", "Google DNS"),
        ("1.1.1.", "Cloudflare DNS"),
    ]
    
    @classmethod
    def suggest_ips(cls, prefix: str = None, min_length: int = 1) -> List[str]:
        """
        Suggest IP addresses based on prefix or common ranges.
        
        Args:
            prefix: IP prefix to match (e.g., "192.168.1")
            min_length: Minimum IP length in characters
            
        Returns:
            List of suggested IP addresses
        """
        suggestions = []
        
        if prefix and len(prefix) >= min_length:
            # Try to match existing prefix
            try:
                # Add common subnet masks
                for mask in cls.COMMON_SUBNETS:
                    ip_str = f"{prefix}/{mask}"
                    if cls._is_valid_ip(ip_str):
                        suggestions.append(ip_str)
            except ValueError:
                pass
            
            # Try to generate sequential IPs
            suggestions.extend(cls._generate_sequential_ips(prefix))
            
            # Try IPv6
            if prefix.lower().startswith("fd"):
                suggestions.extend(cls._suggest_ipv6(prefix))
        else:
            # No prefix - suggest common ranges
            suggestions.extend(cls._generate_common_ips())
            suggestions.extend(cls._generate_sequential_ips("10.0.0"))
            suggestions.extend(cls._generate_sequential_ips("192.168.1"))
            
        return suggestions
    
    @classmethod
    def _is_valid_ip(cls, ip_str: str) -> bool:
        """Check if IP string is valid."""
        try:
            if "/" in ip_str:
                ipaddress.IPv4Network(ip_str, strict=False)
                return True
            else:
                ipaddress.IPv4Address(ip_str)
                return True
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    @classmethod
    def _generate_common_ips(cls) -> List[str]:
        """Generate common IP suggestions."""
        suggestions = []
        
        # Generate from common patterns
        for pattern, _ in cls.COMMON_PATTERNS:
            # Try last octet 1-254
            for i in range(1, 255):
                if "." in pattern:
                    ip_str = f"{pattern}{i}"
                else:
                    ip_str = f"{pattern}{i}.0"
                
                if cls._is_valid_ip(ip_str):
                    suggestions.append(ip_str)
                    if len(suggestions) >= 20:
                        break
            if len(suggestions) >= 20:
                break
        
        return suggestions
    
    @classmethod
    def _generate_sequential_ips(cls, base: str) -> List[str]:
        """Generate sequential IP suggestions from base."""
        suggestions = []
        try:
            parts = base.split(".")
            if len(parts) == 3:
                # Generate with common subnets
                for subnet in cls.COMMON_SUBNETS[:5]:  # Limit to most common
                    ip_str = f"{base}/{subnet}"
                    if cls._is_valid_ip(ip_str):
                        suggestions.append(ip_str)
        except ValueError:
            pass
        
        return suggestions
    
    @classmethod
    def _generate_ipv4(cls, prefix: str) -> List[str]:
        """Generate IPv4 addresses from prefix."""
        suggestions = []
        try:
            # Parse prefix
            base_ip = ipaddress.IPv4Address(prefix)
            
            # Generate sequential IPs
            for i in range(1, 10):
                next_ip = base_ip + i
                ip_str = str(next_ip)
                if len(ip_str) >= len(prefix):
                    suggestions.append(ip_str)
                    if len(suggestions) >= 5:
                        break
        except ValueError:
            pass
        
        return suggestions
    
    @classmethod
    def _generate_sequential_ips(cls, prefix: str) -> List[str]:
        """Generate sequential IP suggestions."""
        suggestions = []
        try:
            # Try to parse as IP
            base_ip = ipaddress.IPv4Address(prefix)
            
            # Generate next few IPs
            for i in range(1, 6):
                next_ip = base_ip + i
                suggestions.append(str(next_ip))
        except ValueError:
            pass
        
        return suggestions
    
    @classmethod
    def _suggest_ipv6(cls, prefix: str) -> List[str]:
        """Suggest IPv6 addresses."""
        suggestions = []
        
        # Common IPv6 patterns
        if "fd" in prefix.lower():
            # ULA (Unique Local Address)
            for i in range(1, 5):
                suggestions.append(f"fd00::{i}:1")
                suggestions.append(f"fd00::1/{i}")
                if len(suggestions) >= 10:
                    break
        
        return suggestions


@click.command(name="ip")
@click.argument("prefix", required=False, default="")
@click.option("--count", "-c", default=10, type=int, help="Number of suggestions")
def ip_command(prefix: str, count: int):
    """Generate IP address suggestions."""
    suggestions = IPCompleter.suggest_ips(prefix, min_length=1)
    
    # Limit to requested count
    suggestions = suggestions[:count]
    
    click.echo("Suggested IP addresses:")
    for i, ip in enumerate(suggestions, 1):
        click.echo(f"  {i}. {ip}")


@click.command(name="subnet")
@click.argument("network", required=False, default="")
@click.option("--class", "-t", type=click.Choice(["A", "B", "C"]), default="C", help="Network class")
def subnet_command(network: str, class_: str):
    """Generate subnet suggestions."""
    if network:
        try:
            # Try to parse existing network
            if "/" in network:
                base_network = ipaddress.IPv4Network(network, strict=False)
            else:
                base_network = ipaddress.IPv4Network(f"{network}/24", strict=False)
            
            # Suggest subnets
            suggestions = []
            for cidr in range(24, 32, 2):
                try:
                    subnet = base_network.subnet(new_prefix=cidr)
                    suggestions.append(str(subnet))
                except ValueError:
                    break
                
                if len(suggestions) >= 10:
                    break
            
            click.echo("Subnet suggestions:")
            for i, subnet in enumerate(suggestions, 1):
                click.echo(f"  {i}. {subnet}")
        except ValueError:
            click.echo("Invalid network format. Use: 192.168.1.0/24")
    else:
        # Suggest common subnets
        common_subnets = [
            ("192.168.1.0/24", "Class C - 254 hosts"),
            ("192.168.0.0/16", "Class C - 65534 hosts"),
            ("10.0.0.0/8", "Class A - 16M hosts"),
            ("172.16.0.0/12", "Class B - 1M hosts"),
        ]
        
        click.echo("Common subnet ranges:")
        for subnet, desc in common_subnets:
            click.echo(f"  {subnet} - {desc}")


@click.command(name="port")
@click.option("--range", "-r", default="51820-65535", help="Port range")
def port_command(range: str):
    """Suggest common WireGuard ports."""
    # Common WireGuard ports
    common_ports = [
        51820,  # Default
        51821,  # Alternative
        51822,  # Alternative
        443,    # HTTPS (stealth mode)
        8443,   # Alt HTTPS
        8080,   # Proxy
    ]
    
    click.echo("Common WireGuard ports:")
    for port in common_ports:
        click.echo(f"  {port}")
    
    # If range provided, show some from range
    if "-" in range:
        start, end = map(int, range.split("-"))
        suggested = list(range(start, min(end + 1, start + 10)))
        click.echo("\nFrom range:")
        for port in suggested:
            click.echo(f"  {port}")


@click.command(name="dns")
@click.option("--provider", "-p", type=click.Choice(["cloudflare", "google", "cloud"]), default="cloudflare")
def dns_command(provider: Optional[str] = None):
    """Suggest DNS servers."""
    dns_servers = {
        "cloudflare": ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"],
        "google": ["8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"],
        "cloud": ["9.9.9.9", "149.112.112.112"],
    }
    
    if provider:
        servers = dns_servers[provider]
    else:
        servers = list(dns_servers.values())[0]
    
    click.echo(f"Suggested DNS ({provider}):")
    for dns in servers:
        click.echo(f"  {dns}")


@click.command(name="peer")
@click.option("--server-port", "-p", default=51820, help="Server port for endpoint matching")
@click.argument("name", required=False, default="")
def peer_command(name: str, server_port: int):
    """Suggest peer names and endpoints."""
    # Suggest common peer names
    peer_names = [
        "Office Network",
        "Home Device",
        "Mobile Hotspot",
        "Backup Server",
        "Development Machine",
        "Production Server",
        "IoT Device",
        "Remote Worker",
    ]
    
    # Suggest endpoints based on port
    click.echo("Suggested peer names:")
    for i, name in enumerate(peer_names, 1):
        click.echo(f"  {i}. {name}")
    
    click.echo("\nSuggested endpoints (based on port {}):".format(server_port))
    endpoints = [
        "192.168.1.100",
        "192.168.1.101",
        "192.168.1.102",
        "203.0.113.50",
        "10.0.0.50",
        "172.16.0.100",
    ]
    
    for endpoint in endpoints:
        click.echo(f"  {endpoint}")
