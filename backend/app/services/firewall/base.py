"""Base interface for firewall drivers."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class NATConfig:
    """Configuration for NAT/masquerading setup."""
    interface: str              # WireGuard interface (e.g., "wg0", "utun3")
    ipv4_subnet: Optional[str]  # IPv4 subnet in CIDR (e.g., "10.0.0.0/24")
    ipv6_subnet: Optional[str]  # IPv6 subnet in CIDR (e.g., "fd00::/64")
    default_interface: str      # Default internet interface (e.g., "eth0", "en0")


class FirewallDriver(ABC):
    """Abstract base class for firewall drivers."""
    
    @abstractmethod
    def name(self) -> str:
        """Return the driver name (e.g., 'iptables', 'dummy')."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this firewall driver is available on the system.
        
        Returns:
            True if the firewall tool is installed and usable
        """
        pass
    
    @abstractmethod
    def setup_nat(self, config: NATConfig) -> bool:
        """
        Set up NAT/masquerading for the WireGuard interface.
        
        Args:
            config: NAT configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cleanup_nat(self, config: NATConfig) -> bool:
        """
        Clean up NAT/masquerading rules for the WireGuard interface.
        
        Args:
            config: NAT configuration
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_default_interface(self) -> Optional[str]:
        """
        Get the default network interface for internet access.
        
        Returns:
            Interface name (e.g., "eth0", "en0") or None if not found
        """
        pass
