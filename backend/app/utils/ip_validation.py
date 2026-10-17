"""IP address validation utilities for WireGuard servers and peers."""

import ipaddress
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
        
        # Validate CIDR prefix length (must be 1-30 for subnets, not a host)
        prefix_len = network.prefixlen
        if prefix_len == 32 or prefix_len > 30:
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
