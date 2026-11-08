from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import hashlib


def _generate_id(name: str) -> int:
    """Generate a unique ID based on the rule name."""
    return int(hashlib.md5(name.encode()).hexdigest(), 16) % 1000000


class FirewallRuleAction(Enum):
    """Firewall rule actions."""
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"
    LOG = "log"


def _port_matches(port: str, rule_port: str) -> bool:
    """
    Check if a port matches a rule port.
    
    Args:
        port: Port to check
        rule_port: Rule port (can be "any", single port, or range)
        
    Returns:
        True if port matches
    """
    if rule_port == "any":
        return True
    
    try:
        port_num = int(port)
        rule_nums = rule_port.split("-")
        
        if len(rule_nums) == 1:
            return str(port_num) == rule_port
        else:
            min_port, max_port = int(rule_nums[0]), int(rule_nums[1])
            return min_port <= port_num <= max_port
    except ValueError:
        return False


def _ip_in_cidr(ip: str, cidr: str) -> bool:
    """
    Check if an IP is in a CIDR range.
    
    Args:
        ip: IP address to check
        cidr: CIDR range (e.g., "192.168.1.0/24" or "any")
        
    Returns:
        True if IP is in CIDR range
    """
    if cidr == "any":
        return True
    
    if "/" not in cidr:
        return ip == cidr
    
    network, prefix = cidr.split("/")
    
    # Validate prefix length
    try:
        prefix_len = int(prefix)
        if prefix_len < 0 or prefix_len > 32:
            return False
    except ValueError:
        return False
    
    if ip == "any":
        return True
    
    try:
        # Parse IP addresses
        def ip_to_int(ip_str: str) -> int:
            parts = ip_str.split(".")
            return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
        
        ip_int = ip_to_int(ip)
        network_int = ip_to_int(network)
        
        # Create mask
        mask = (0xffffffff << (32 - prefix_len)) & 0xffffffff
        
        # Check if IP is in network
        return (ip_int & mask) == (network_int & mask)
    except (ValueError, IndexError):
        return False


class FirewallRule(BaseModel):
    """Firewall rule for NAT/masquerading management."""
    
    name: str = Field(..., description="Rule name")
    action: str = Field(default="accept", description="Rule action (accept, drop, reject, log)")
    protocol: str = Field(default="tcp", description="Protocol (tcp, udp, icmp, all)")
    src_ip: str = Field(default="any", description="Source IP or CIDR")
    dst_ip: str = Field(default="any", description="Destination IP or CIDR")
    port: str = Field(default="any", description="Port or port range")
    enabled: bool = Field(default=True, description="Whether the rule is enabled")
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_dump(self, *args, **kwargs):
        """Custom serialization for FirewallRule."""
        data = super().model_dump(*args, **kwargs)
        return data
    
    def __eq__(self, other: object) -> bool:
        """Compare two FirewallRule instances."""
        if not isinstance(other, FirewallRule):
            return False
        return self.model_dump() == other.model_dump()
    
    def matches(self, src_ip: str, dst_ip: str, protocol: str, port: str) -> bool:
        """
        Check if a packet matches this rule.
        
        Args:
            src_ip: Source IP
            dst_ip: Destination IP
            protocol: Protocol (tcp, udp, icmp, all)
            port: Port or port range
            
        Returns:
            True if the packet matches the rule
        """
        # Check source IP
        if src_ip != "any" and self.src_ip != "any":
            if not _ip_in_cidr(src_ip, self.src_ip):
                return False
        
        # Check destination IP
        if dst_ip != "any" and self.dst_ip != "any":
            if not _ip_in_cidr(dst_ip, self.dst_ip):
                return False
        
        # Check protocol
        if protocol != "any" and self.protocol != "all":
            if protocol.lower() != self.protocol.lower():
                return False
        
        # Check port
        if port != "any" and self.port != "any":
            # Check if port matches
            if not _port_matches(port, self.port):
                return False
        
        return True
    
    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v):
        """Validate action field."""
        if v.lower() in ["accept", "drop", "reject", "log"]:
            return v.lower()
        raise ValueError(f"Invalid action: {v}")
    
    @field_validator("action")
    @classmethod
    def validate_action_final(cls, v):
        """Final validation for action field."""
        if v.lower() not in ["accept", "drop", "reject", "log"]:
            raise ValueError(f"Invalid action: {v}")
        return v
    
    @field_validator("protocol", mode="before")
    @classmethod
    def validate_protocol(cls, v):
        """Validate protocol field."""
        valid_protocols = ["tcp", "udp", "icmp", "all", "any"]
        if v.lower() in valid_protocols:
            return v.lower()
        raise ValueError(f"Invalid protocol: {v}")
    
    @field_validator("protocol")
    @classmethod
    def validate_protocol_final(cls, v):
        """Final validation for protocol field."""
        if v.lower() not in ["tcp", "udp", "icmp", "all", "any"]:
            raise ValueError(f"Invalid protocol: {v}")
        return v
    
    @field_validator("src_ip", mode="before")
    @classmethod
    def validate_src_ip(cls, v):
        """Validate source IP field."""
        if v.lower() == "any":
            return "any"
        return v
    
    @field_validator("dst_ip", mode="before")
    @classmethod
    def validate_dst_ip(cls, v):
        """Validate destination IP field."""
        if v.lower() == "any":
            return "any"
        return v
    
    @field_validator("port", mode="before")
    @classmethod
    def validate_port(cls, v):
        """Validate port field."""
        if v.lower() == "any":
            return "any"
        return v


def validate_rule(rule: FirewallRule) -> bool:
    """
    Validate a firewall rule.
    
    Args:
        rule: FirewallRule instance or dictionary to validate
        
    Returns:
        True if rule is valid, False otherwise
    """
    try:
        # Handle both FirewallRule instances and dictionaries
        if isinstance(rule, FirewallRule):
            # Validate the instance
            FirewallRule.model_validate(rule.model_dump())
            return True
        elif isinstance(rule, dict):
            # Check if required fields are present
            required_fields = ["name", "action", "protocol"]
            missing_fields = [f for f in required_fields if f not in rule]
            if missing_fields:
                return False
            
            # Create a temporary instance to validate
            FirewallRule.model_validate(rule)
            return True
        else:
            # Unknown type
            return False
    except Exception:
        # If validation fails, return False
        return False
