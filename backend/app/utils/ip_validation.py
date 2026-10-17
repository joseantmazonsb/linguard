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
        network = ipaddress.IPv4Network(ip_str, strict=False)
        # Check if it's a host address (not just a network)
        if '/' not in ip_str:
            return False, "IPv4 address must include CIDR notation (e.g., 10.0.0.1/24)"
        return True, None
    except ValueError as e:
        return False, f"Invalid IPv4 CIDR format: {str(e)}"


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
    # Empty strings are considered valid (for flexibility)
    if not ip_str:
        return True, None
    
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
    if not peer_ip:
        return True, None
    
    # Empty server IP is also valid (no conflict to check)
    if not server_ip:
        return True, None
    
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
    if not new_server_ip:
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
            
            if not existing_ip:
                continue
                
            existing_network = ipaddress.ip_network(existing_ip, strict=False)
            existing_host = ipaddress.ip_address(existing_ip.split('/')[0])
            
            # Check if new server's IP is within an existing server's subnet
            # Allow same subnet/IP (duplicate allowed)
            if new_host in existing_network and new_server_ip != existing_ip:
                return False, f"Server IP {new_host} conflicts with existing server '{server_name}' subnet {existing_network}"
            
            # Check if existing server's IP is within new server's subnet
            # Allow same subnet/IP (duplicate allowed)
            if existing_host in new_network:
                # Only flag as conflict if it's a different IP/subnet
                if existing_ip != new_server_ip:
                    return False, f"New subnet {new_network} would contain existing server '{server_name}' IP {existing_host}"
        
        return True, None
        
    except ValueError as e:
        return False, f"Error validating subnet conflicts: {str(e)}"
