from typing import Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


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
    
    @validator("action", pre=True)
    def validate_action(cls, v):
        """Validate action field."""
        if v.lower() in ["accept", "drop", "reject", "log"]:
            return v.lower()
        raise ValueError(f"Invalid action: {v}")
    
    @validator("protocol", pre=True)
    def validate_protocol(cls, v):
        """Validate protocol field."""
        valid_protocols = ["tcp", "udp", "icmp", "all"]
        if v.lower() in valid_protocols:
            return v.lower()
        raise ValueError(f"Invalid protocol: {v}")
    
    @validator("src_ip", pre=True)
    def validate_src_ip(cls, v):
        """Validate source IP field."""
        if v.lower() == "any":
            return "any"
        return v
    
    @validator("dst_ip", pre=True)
    def validate_dst_ip(cls, v):
        """Validate destination IP field."""
        if v.lower() == "any":
            return "any"
        return v
    
    @validator("port", pre=True)
    def validate_port(cls, v):
        """Validate port field."""
        if v.lower() == "any":
            return "any"
        return v
