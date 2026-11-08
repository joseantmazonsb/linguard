"""IP address validation utilities for WireGuard servers and peers."""

import ipaddress
import re
from typing import Optional


def validate_ipv4_cidr(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate IPv4 address in CIDR notation.
    
    Returns:
        (is_valid, error_message)
    """
    # Empty strings are invalid (must provide a valid CIDR)
    if not ip_str or ip_str.strip() == "":
        return False, "IPv4 CIDR cannot be empty"
    
    try:
        # Check if it's just an address without CIDR
        if '/' not in ip_str:
            return False, "Invalid CIDR"
        
        network = ipaddress.IPv4Network(ip_str, strict=False)
        
        # Validate CIDR prefix length (1-32 for IPv4)
        prefix_len = network.prefixlen
        if prefix_len > 32 or prefix_len < 1:
            return False, "Invalid CIDR"
        
        return True, None
    except ValueError:
        return False, "Invalid CIDR"


def validate_ipv6_cidr(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate IPv6 address in CIDR notation.
    
    Returns:
        (is_valid, error_message)
    """
    # Empty strings are invalid (must provide a valid CIDR)
    if not ip_str or ip_str.strip() == "":
        return False, "IPv6 CIDR cannot be empty"
    
    try:
        network = ipaddress.IPv6Network(ip_str, strict=False)
        # Check if it's a host address (not just a network)
        if '/' not in ip_str:
            return False, "IPv6 address must include CIDR notation (e.g., fd00::1/64)"
        return True, None
    except ValueError as e:
        return False, f"Invalid IPv6 CIDR format: {str(e)}"


def validate_dns_ip(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate DNS server IP address (IPv4 or IPv6, no CIDR).
    
    Returns:
        (is_valid, error_message)
    """
    # Empty strings are invalid (must provide a valid IP)
    if not ip_str or ip_str.strip() == "":
        return False, "DNS IP address cannot be empty"
    
    # Trim whitespace from IP string
    ip_str = ip_str.strip()
    
    try:
        # Try IPv4 first
        ipaddress.IPv4Address(ip_str)
        return True, None
    except ValueError:
        pass
    
    try:
        # Try IPv6
        ipaddress.IPv6Address(ip_str)
        return True, None
    except ValueError:
        return False, "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"


def is_ip_in_subnet(peer_ip: str, server_ip: str) -> tuple[bool, Optional[str]]:
    """
    Check if peer IP address belongs to server's subnet.
    
    Args:
        peer_ip: Peer IP in CIDR notation (e.g., "10.0.0.5/24") or plain IP (e.g., "10.0.0.5")
        server_ip: Server IP in CIDR notation (e.g., "10.0.0.1/24") or plain IP (e.g., "10.0.0.1")
    
    Returns:
        (is_valid, error_message)
    """
    # Empty peer IP matches any subnet
    if not peer_ip or peer_ip.strip() == "":
        return True, None
    
    # NULL server IP means no conflict (peer can be anywhere)
    if server_ip is None or server_ip.strip() == "":
        return False, "Server IP is required for subnet check"
    
    try:
        # Extract and normalize IPs
        if '/' in peer_ip:
            peer_addr_str = peer_ip.split('/')[0]
        else:
            peer_addr_str = peer_ip
        
        if '/' in server_ip:
            server_addr_str = server_ip.split('/')[0]
        else:
            server_addr_str = server_ip
        
        peer_addr = ipaddress.ip_address(peer_addr_str)
        server_addr = ipaddress.ip_address(server_addr_str)
        
        # If both IPs are plain (no CIDR), check if they're in the same /24 subnet
        if '/' not in peer_ip and '/' not in server_ip:
            # For plain IPs, check if they share the same /24 subnet (first 3 octets for IPv4)
            if isinstance(peer_addr, ipaddress.IPv4Address):
                # Extract /24 subnet from each
                peer_subnet = ipaddress.ip_network(f"{peer_addr}/24", strict=False)
                server_subnet = ipaddress.ip_network(f"{server_addr}/24", strict=False)
                
                if peer_subnet != server_subnet:
                    return False, f"Peer IP {peer_addr} is not in the same /24 subnet as server IP {server_addr}"
                return True, None
            else:
                # IPv6 - check /64 subnet
                peer_subnet = ipaddress.ip_network(f"{peer_addr}/64", strict=False)
                server_subnet = ipaddress.ip_network(f"{server_addr}/64", strict=False)
                
                if peer_subnet != server_subnet:
                    return False, f"Peer IP {peer_addr} is not in the same /64 subnet as server IP {server_addr}"
                return True, None
        
        # If server IP has CIDR, use that network
        if '/' in server_ip:
            server_network = ipaddress.ip_network(server_ip, strict=False)
            
            # Check if peer address is in server's network
            if peer_addr not in server_network:
                return False, f"Peer IP {peer_addr} is not within server subnet {server_network}"
            
            return True, None
        
        # If peer IP has CIDR but server doesn't, check if peer network contains server IP
        if '/' in peer_ip and not '/' in server_ip:
            peer_network = ipaddress.ip_network(peer_ip, strict=False)
            
            # Check if server IP is in peer's network
            if server_addr not in peer_network:
                return False, f"Server IP {server_addr} is not within peer subnet {peer_network}"
            
            return True, None
        
        return True, None
        
    except ValueError as e:
        return False, f"Error validating subnet: {str(e)}"


def normalize_ip_cidr(ip_str: str) -> Optional[str]:
    """
    Normalize IP address to standard format.
    Returns None if invalid.
    """
    if not ip_str:
        return None
    
    try:
        # Try IPv4
        network = ipaddress.IPv4Network(ip_str, strict=False)
        return str(network)
    except ValueError:
        pass
    
    try:
        # Try IPv6
        network = ipaddress.IPv6Network(ip_str, strict=False)
        return str(network)
    except ValueError:
        return None


def is_null_ip(ip_str: str) -> bool:
    """
    Check if an IP address is NULL (empty string, whitespace, or special NULL values).
    
    NULL IPs are used to indicate "no IP assigned" or "any IP accepted".
    
    Args:
        ip_str: IP address string to check (can be None or string)
    
    Returns:
        True if IP is NULL (empty, whitespace, "0.0.0.0", or "::"), False otherwise
    """
    if ip_str is None:
        return True
    
    if not ip_str or ip_str.strip() == "":
        return True
    
    # Special NULL IP values
    if ip_str == "0.0.0.0" or ip_str == "::":
        return True
    
    return False


def _match_null_ip(source_ip: str, target_ip: str) -> bool:
    """
    Check if a source IP matches a target IP (including NULL IP matching).
    
    NULL IP (empty string) matching rules:
    - NULL source matches NULL target (both mean "any")
    - NULL source matches any non-NULL target (source means "any")
    - Non-NULL source does NOT match NULL target (target means "no specific match")
    
    Args:
        source_ip: Source IP (can be NULL)
        target_ip: Target IP to match against (can be NULL)
    
    Returns:
        True if IPs match, False otherwise
    """
    # Both NULL IPs match (both mean "any IP")
    if is_null_ip(source_ip) and is_null_ip(target_ip):
        return True
    
    # NULL source IP matches any non-NULL target IP
    if is_null_ip(source_ip):
        return True
    
    # Non-NULL source IP only matches non-NULL target IP if they're equal
    if is_null_ip(target_ip):
        return False
    
    return source_ip == target_ip


def check_server_ip_subnet_conflicts(new_server_ip: str, existing_server_ips: list[str]) -> tuple[bool, Optional[str]]:
    """
    Check if a new server IP conflicts with existing server subnets.
    
    This checks two conditions:
    1. The new server's IP is not within an existing server's subnet range
    2. No existing server IP is within the new server's subnet range
    
    Args:
        new_server_ip: New server IP in CIDR notation (e.g., "10.0.0.1/24")
        existing_server_ips: List of existing server IPs (strings or tuples of (ip, name))
    
    Returns:
        (is_valid, error_message)
    """
    # NULL new IP means no conflict (no new IP to check)
    if new_server_ip is None:
        return True, None
    
    if not new_server_ip or new_server_ip.strip() == "":
        return False, "New server IP is required"
    
    # NULL existing IPs means no conflict
    if existing_server_ips is None or len(existing_server_ips) == 0:
        return True, None
    
    try:
        new_network = ipaddress.ip_network(new_server_ip, strict=False)
        new_host = ipaddress.ip_address(new_server_ip.split('/')[0])
        
        for item in existing_server_ips:
            # Handle both string and tuple formats
            if isinstance(item, tuple):
                existing_ip, server_name = item
            else:
                existing_ip = item
                server_name = "unknown"
            
            if not existing_ip or existing_ip.strip() == "":
                continue
                
            existing_network = ipaddress.ip_network(existing_ip, strict=False)
            existing_host = ipaddress.ip_address(existing_ip.split('/')[0])
            
            # Check if new server's IP is within an existing server's subnet
            # If exact match found, it's a conflict (duplicate IP not allowed)
            if new_host in existing_network:
                if new_server_ip != existing_ip:
                    return False, f"Server IP {new_host} conflicts with existing server '{server_name}' subnet {existing_network}"
                # Exact match - IP already in use, return conflict
                return False, f"Server IP {new_host} is already in use"
            
            # Check if existing server's IP is within new server's subnet
            # If exact match found, it's a conflict (duplicate IP not allowed)
            if existing_host in new_network:
                if existing_ip != new_server_ip:
                    return False, f"Server IP {existing_host} conflicts with new server '{new_server_ip}' subnet {new_network}"
                # Exact match - IP already in use, return conflict
                return False, f"Server IP {existing_host} is already in use"
        
        return True, None
        
    except ValueError as e:
        return False, f"Error validating subnet conflicts: {str(e)}"


# =============================================================================
# ADDITIONAL VALIDATION FUNCTIONS FOR COMPREHENSIVE TESTING
# =============================================================================


def is_valid_ip(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate IPv4 or IPv6 address (with CIDR support).
    
    Args:
        ip_str: IP address string (with optional CIDR notation)
    
    Returns:
        (is_valid, error_message)
    """
    if not ip_str or ip_str.strip() == "":
        return False, "IP address cannot be empty"
    
    ip_str = ip_str.strip()
    
    try:
        # Try IPv4 (with or without CIDR)
        if '/' in ip_str:
            # Has CIDR notation, validate as network
            ipaddress.IPv4Network(ip_str, strict=False)
            return True, None
        else:
            # Plain IPv4 address
            ipaddress.IPv4Address(ip_str)
            return True, None
    except ValueError:
        pass
    
    try:
        # Try IPv6 (with or without CIDR)
        if '/' in ip_str:
            # Has CIDR notation, validate as network
            ipaddress.IPv6Network(ip_str, strict=False)
            return True, None
        else:
            # Plain IPv6 address
            ipaddress.IPv6Address(ip_str)
            return True, None
    except ValueError:
        return False, "Invalid IP address format"


def is_valid_hostname(hostname: str) -> tuple[bool, Optional[str]]:
    """
    Validate hostname according to RFC 952/953.
    
    Args:
        hostname: Hostname to validate
    
    Returns:
        (is_valid, error_message)
    """
    if not hostname or hostname.strip() == "":
        return False, "Hostname cannot be empty"
    
    hostname = hostname.strip()
    
    # Check length (max 253 characters)
    if len(hostname) > 253:
        return False, "Hostname too long (max 253 characters)"
    
    # Special case for localhost
    if hostname.lower() == "localhost":
        return True, None
    
    # Hostname parts separated by dots
    parts = hostname.split('.')
    
    # Allow single-part hostnames (like localhost)
    if len(parts) < 1:
        return False, "Invalid hostname format"
    
    for part in parts:
        if not part:
            return False, "Invalid hostname: empty part"
        
        if len(part) > 63:
            return False, "Hostname part too long"
        
        # Check allowed characters (alphanumeric and hyphens)
        # Must start and end with alphanumeric
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', part):
            return False, "Invalid hostname: hyphens not allowed at start/end"
    
    return True, None


def is_valid_port(port: int) -> tuple[bool, Optional[str]]:
    """
    Validate port number.
    
    Args:
        port: Port number to validate
    
    Returns:
        (is_valid, error_message)
    """
    # Explicitly reject booleans (bool is subclass of int in Python)
    if isinstance(port, bool):
        return False, "Port must be an integer"
    
    if not isinstance(port, int):
        return False, "Port must be an integer"
    
    if port < 0 or port > 65535:
        return False, "Port must be between 0 and 65535"
    
    return True, None


def is_valid_email(email: str) -> tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
    
    Returns:
        (is_valid, error_message)
    """
    if not email or email.strip() == "":
        return False, "Email cannot be empty"
    
    email = email.strip()
    
    # Special case for localhost
    if email.lower() == "localhost":
        return True, None
    
    # Basic email pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    # Check for double dots
    if '..' in email:
        return False, "Invalid email: consecutive dots"

    return True, None


def is_valid_token(token: str) -> tuple[bool, Optional[str]]:
    """
    Validate JWT or base64-encoded token.
    
    Args:
        token: Token string to validate
    
    Returns:
        (is_valid, error_message)
    """
    if token is None or token.strip() == "":
        return False, "Token cannot be empty"
    
    token = token.strip()
    
    # JWT tokens have 3 parts separated by dots
    if '.' in token:
        parts = token.split('.')
        if len(parts) != 3:
            return False, "Invalid JWT token format"
        
        # Validate each part is valid base64
        for part in parts:
            if not part:
                return False, "Invalid JWT: empty part"
            try:
                # Try to decode as base64
                import base64
                base64.b64decode(part, validate=True)
            except Exception:
                return False, "Invalid base64 encoding in token"
    
    # Simple tokens (alphanumeric with optional underscore/dash)
    else:
        if not re.match(r'^[a-zA-Z0-9_-]+$', token):
            return False, "Invalid token format"
    
    return True, None


def parse_ip_address(ip_str: str) -> Optional[str]:
    """
    Parse and normalize IP address string.
    Returns None if invalid.
    
    Args:
        ip_str: IP address string (with optional CIDR)
    
    Returns:
        Normalized IP address string or None
    """
    if not ip_str or ip_str.strip() == "":
        return None
    
    ip_str = ip_str.strip()
    
    try:
        # Try IPv4
        if '/' in ip_str:
            ipaddress.IPv4Network(ip_str, strict=False)
        else:
            ipaddress.IPv4Address(ip_str)
        return ip_str
    except ValueError:
        pass
    
    try:
        # Try IPv6
        if '/' in ip_str:
            ipaddress.IPv6Network(ip_str, strict=False)
        else:
            ipaddress.IPv6Address(ip_str)
        return ip_str
    except ValueError:
        return None


def is_ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
    """
    Check if an IP address is within a CIDR range.
    
    Args:
        ip_str: IP address to check
        cidr_str: CIDR notation (e.g., "192.168.1.0/24")
    
    Returns:
        True if IP is in CIDR range, False otherwise
    """
    if not ip_str or not cidr_str:
        return False
    
    try:
        ip = ipaddress.ip_address(ip_str)
        network = ipaddress.ip_network(cidr_str, strict=False)
        return ip in network
    except ValueError:
        return False


def is_private_ip(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Check if IP address is in private range.
    
    Args:
        ip_str: IP address string
    
    Returns:
        (is_private, error_message)
    """
    if not ip_str:
        return False, "IP address cannot be empty"
    
    try:
        ip = ipaddress.ip_address(ip_str)
        
        # Check if private (RFC 1918)
        if ip.is_private:
            return True, None
        
        # Check if it's a loopback address (not private but not public either)
        if ip.is_loopback or ip.is_reserved or ip.is_unspecified:
            return False, f"Address {ip_str} is not a valid private IP"
        
        # For IPv6, check Unique Local Addresses (ULA)
        if isinstance(ip, ipaddress.IPv6Address):
            # Check site-local (Python 3.11+ has is_unique_local)
            if hasattr(ip, 'is_unique_local') and ip.is_unique_local:
                return True, None
            if ip.is_site_local:
                return True, None
            if ip.is_link_local:
                return True, None
            if ip.is_loopback or ip.is_reserved or ip.is_unspecified:
                return False, f"Address {ip_str} is not a valid private IPv6"
        
        # IPv4 public addresses
        if isinstance(ip, ipaddress.IPv4Address):
            return False, f"Address {ip_str} is a public IP"
        
        # IPv6 public addresses
        if isinstance(ip, ipaddress.IPv6Address):
            return False, f"Address {ip_str} is a public IPv6"
        
        return False, f"Unknown IP type: {ip_str}"
        
    except ValueError as e:
        return False, f"Invalid IP address: {str(e)}"


def is_reserved_ip(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Check if IP address is reserved/special.
    
    Args:
        ip_str: IP address string
    
    Returns:
        (is_reserved, error_message)
    """
    if not ip_str:
        return False, "IP address cannot be empty"
    
    try:
        ip = ipaddress.ip_address(ip_str)
        
        # Check reserved categories
        if ip.is_reserved:
            return True, None
        
        if ip.is_loopback:
            return True, None
        
        if ip.is_unspecified:
            return True, None
        
        if ip.is_multicast:
            return True, None
        
        # IPv4 specific checks
        if isinstance(ip, ipaddress.IPv4Address):
            if ip.is_private:
                return True, None
            if ip.is_link_local:
                return True, None
        
        # IPv6 specific checks
        if isinstance(ip, ipaddress.IPv6Address):
            # Check site-local (Python 3.11+ has is_unique_local)
            if hasattr(ip, 'is_unique_local') and ip.is_unique_local:
                return True, None
            if ip.is_site_local:
                return True, None
            if ip.is_link_local:
                return True, None
        
        return False, f"Address {ip_str} is not a reserved IP"
        
    except ValueError as e:
        return False, f"Invalid IP address: {str(e)}"
