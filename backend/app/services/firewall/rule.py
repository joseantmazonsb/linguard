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


class FirewallRule(BaseModel):
    """Firewall rule for NAT/masquerading management."""
    
    name: str = Field(..., description="Rule name")
    action: str = Field(..., description="Rule action (accept, drop, reject, log)")
    protocol: str = Field("tcp", description="Protocol (tcp, udp, icmp, all)")
    src_ip: str = Field("any", description="Source IP or CIDR")
    dst_ip: str = Field("any", description="Destination IP or CIDR")
    port: str = Field("any", description="Port or port range")
    enabled: bool = Field(True, description="Whether the rule is enabled")
    
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
    
    @field_validator("action", mode="before")
    @classmethod
    def validate_action(cls, v):
        """Validate action field."""
        if v.lower() in ["accept", "drop", "reject", "log"]:
            return v.lower()
        raise ValueError(f"Invalid action: {v}")
    
    @field_validator("protocol", mode="before")
    @classmethod
    def validate_protocol(cls, v):
        """Validate protocol field."""
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if v.lower() in valid_protocols:
            return v.lower()
        raise ValueError(f"Invalid protocol: {v}")
    
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
        rule: FirewallRule instance to validate
        
    Returns:
        True if rule is valid, False otherwise
    """
    try:
        # Use model_validate to validate the rule data
        # This is more flexible than creating a new instance
        FirewallRule.model_validate(rule.model_dump())
        return True
    except Exception as e:
        # Check if it's a validation error
        return False
