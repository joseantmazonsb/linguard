"""Firewall service that delegates to iptables driver (Linux only)."""

import logging
import platform
import sys
from typing import Optional
from .base import FirewallDriver, NATConfig
from .iptables_driver import IptablesDriver
from .dummy_driver import DummyFirewallDriver
from app.core.config import settings

logger = logging.getLogger(__name__)


class FirewallService:
    """
    Firewall service for Linux with iptables.
    
    Requirements:
    - Linux operating system
    - iptables installed
    - Passwordless sudo for iptables commands
    
    For development on non-Linux systems:
    - Set DEBUG_BYPASS_FIREWALL=true to use dummy driver
    """
    
    def __init__(self):
        self.driver: Optional[FirewallDriver] = None
        self._detect_driver()
    
    def _detect_driver(self):
        """Detect and initialize iptables driver (Linux only)."""
        
        # Debug bypass - use dummy driver
        if settings.DEBUG_BYPASS_FIREWALL:
            self.driver = DummyFirewallDriver()
            logger.warning("⚠️  DEBUG MODE: Using dummy firewall driver (NAT will NOT work!)")
            logger.warning("   Set DEBUG_BYPASS_FIREWALL=false for production deployment")
            return
        
        # Platform check - require Linux
        current_platform = platform.system()
        if current_platform != "Linux":
            logger.error("=" * 80)
            logger.error("❌ PLATFORM ERROR: Linguard requires Linux with iptables")
            logger.error(f"   Current platform: {current_platform}")
            logger.error("")
            logger.error("   Solutions:")
            logger.error("   1. Deploy on Linux (Ubuntu 20.04+, Debian 11+, etc.)")
            logger.error("   2. Use Docker for deployment (recommended)")
            logger.error("   3. For development only: Set DEBUG_BYPASS_FIREWALL=true")
            logger.error("=" * 80)
            sys.exit(1)
        
        # Initialize iptables driver
        iptables = IptablesDriver()
        if iptables.is_available():
            self.driver = iptables
            logger.info(f"✓ Firewall driver: {iptables.name()}")
        else:
            logger.error("=" * 80)
            logger.error("❌ FIREWALL ERROR: iptables not available")
            logger.error("")
            logger.error("   Required:")
            logger.error("   - Install iptables: sudo apt install iptables")
            logger.error("   - Configure passwordless sudo (see documentation)")
            logger.error("")
            logger.error("   Sudoers configuration (/etc/sudoers.d/linguard):")
            logger.error("   yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables")
            logger.error("=" * 80)
            sys.exit(1)
    
    def is_available(self) -> bool:
        """Check if a firewall driver is available."""
        return self.driver is not None
    
    def get_driver_name(self) -> Optional[str]:
        """Get the name of the active driver."""
        return self.driver.name() if self.driver else None
    
    def setup_nat(
        self,
        interface: str,
        ipv4_subnet: Optional[str] = None,
        ipv6_subnet: Optional[str] = None
    ) -> bool:
        """
        Set up NAT/masquerading for a WireGuard interface.
        
        Args:
            interface: WireGuard interface name (e.g., "wg0", "utun3")
            ipv4_subnet: IPv4 subnet in CIDR notation (e.g., "10.0.0.0/24")
            ipv6_subnet: IPv6 subnet in CIDR notation (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("No firewall driver available for NAT setup")
            return False
        
        # Get default interface
        default_interface = self.driver.get_default_interface()
        if not default_interface:
            logger.error("Could not determine default network interface")
            return False
        
        # Create config
        config = NATConfig(
            interface=interface,
            ipv4_subnet=ipv4_subnet,
            ipv6_subnet=ipv6_subnet,
            default_interface=default_interface
        )
        
        # Delegate to driver
        logger.info(f"Setting up NAT for {interface} using {self.driver.name()}")
        return self.driver.setup_nat(config)
    
    def cleanup_nat(
        self,
        interface: str,
        ipv4_subnet: Optional[str] = None,
        ipv6_subnet: Optional[str] = None
    ) -> bool:
        """
        Clean up NAT/masquerading rules for a WireGuard interface.
        
        Args:
            interface: WireGuard interface name
            ipv4_subnet: IPv4 subnet in CIDR notation
            ipv6_subnet: IPv6 subnet in CIDR notation (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.warning("No firewall driver available for NAT cleanup")
            return True  # Don't fail cleanup
        
        # Get default interface (best effort)
        default_interface = self.driver.get_default_interface()
        if not default_interface:
            logger.warning("Could not determine default interface for cleanup")
            # Try to use a reasonable default
            default_interface = "en0" if platform.system() == "Darwin" else "eth0"
        
        # Create config
        config = NATConfig(
            interface=interface,
            ipv4_subnet=ipv4_subnet,
            ipv6_subnet=ipv6_subnet,
            default_interface=default_interface
        )
        
        # Delegate to driver
        logger.info(f"Cleaning up NAT for {interface} using {self.driver.name()}")
        return self.driver.cleanup_nat(config)
