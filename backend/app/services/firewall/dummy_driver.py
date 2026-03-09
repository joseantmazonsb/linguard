"""Dummy firewall driver for development/testing (no-op, always succeeds)."""

import logging
from typing import Optional
from .base import FirewallDriver, NATConfig

logger = logging.getLogger(__name__)


class DummyFirewallDriver(FirewallDriver):
    """
    Dummy firewall driver that does nothing (for development/testing).
    
    This driver is used when DEBUG_BYPASS_FIREWALL=true to allow development
    on non-Linux systems (like macOS/Windows) without actual NAT setup.
    
    All operations succeed but don't actually configure networking.
    """
    
    def name(self) -> str:
        return "dummy (development mode)"
    
    def is_available(self) -> bool:
        """Always returns True (dummy driver is always available)."""
        return True
    
    def get_default_interface(self) -> Optional[str]:
        """Returns a fake default interface name."""
        return "eth0"
    
    def setup_nat(self, config: NATConfig) -> bool:
        """
        Pretends to set up NAT (does nothing).
        
        Args:
            config: NAT configuration
            
        Returns:
            Always True
        """
        logger.warning(
            f"[DUMMY] Pretending to set up NAT for interface '{config.interface}' "
            f"(subnet: {config.ipv4_subnet or config.ipv6_subnet}) - "
            f"traffic will NOT be routed!"
        )
        return True
    
    def cleanup_nat(self, config: NATConfig) -> bool:
        """
        Pretends to clean up NAT (does nothing).
        
        Args:
            config: NAT configuration
            
        Returns:
            Always True
        """
        logger.debug(f"[DUMMY] Pretending to clean up NAT for interface '{config.interface}'")
        return True
