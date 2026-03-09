"""IP address validation utilities for WireGuard servers and peers."""

import ipaddress
from typing import Optional


def validate_ipv4_cidr(ip_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate IPv4 address in CIDR notation.
    
    Returns:
        (is_valid, error_message)
    """
    if not ip_str:
        return True, None
    
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
    if not ip_str:
        return True, None
    
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
        peer_ip: Peer IP in CIDR notation (e.g., "10.0.0.5/24")
        server_ip: Server IP in CIDR notation (e.g., "10.0.0.1/24")
    
    Returns:
        (is_valid, error_message)
    """
    if not peer_ip or not server_ip:
        return True, None
    
    try:
        # Extract network from server IP
        server_network = ipaddress.ip_network(server_ip, strict=False)
        
        # Extract host address from peer IP (strip CIDR)
        peer_addr_str = peer_ip.split('/')[0]
        peer_addr = ipaddress.ip_address(peer_addr_str)
        
        # Check if peer address is in server's network
        if peer_addr not in server_network:
            return False, f"Peer IP {peer_addr} is not within server subnet {server_network}"
        
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
        existing_server_ips: List of existing server IPs with names as tuples (ip, name)
    
    Returns:
        (is_valid, error_message)
    """
    if not new_server_ip:
        return True, None
    
    try:
        new_network = ipaddress.ip_network(new_server_ip, strict=False)
        new_host = ipaddress.ip_address(new_server_ip.split('/')[0])
        
        for existing_ip, server_name in existing_server_ips:
            if not existing_ip:
                continue
                
            existing_network = ipaddress.ip_network(existing_ip, strict=False)
            existing_host = ipaddress.ip_address(existing_ip.split('/')[0])
            
            # Check if new server's IP is within an existing server's subnet
            if new_host in existing_network and new_server_ip != existing_ip:
                return False, f"Server IP {new_host} conflicts with existing server '{server_name}' subnet {existing_network}"
            
            # Check if existing server's IP is within new server's subnet
            if existing_host in new_network and new_server_ip != existing_ip:
                return False, f"New subnet {new_network} would contain existing server '{server_name}' IP {existing_host}"
        
        return True, None
        
    except ValueError as e:
        return False, f"Error validating subnet conflicts: {str(e)}"
