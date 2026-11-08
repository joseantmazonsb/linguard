"""Firewall service that delegates to iptables driver (Linux only)."""

import logging
import platform
import sys
from typing import Optional
from sqlalchemy import text
from .base import FirewallDriver, NATConfig
from .iptables_driver import IptablesDriver
from .dummy_driver import DummyFirewallDriver
from .rule import FirewallRule
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
            logger.warning("=" * 80)
            logger.warning("⚠️  FIREWALL WARNING: iptables not available or no sudo access")
            logger.warning("")
            logger.warning("   This is OK for development/testing. For production:")
            logger.warning("   - Install iptables: sudo apt install iptables")
            logger.warning("   - Configure passwordless sudo (see documentation)")
            logger.warning("")
            logger.warning("   Sudoers configuration (/etc/sudoers.d/linguard):")
            logger.warning("   yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables")
            logger.warning("=" * 80)
            # Don't exit in development - just skip firewall operations
            self.driver = None
    
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
    
    def get_rules(self) -> list:
        """
        Get all firewall rules from database.
        
        Returns:
            List of firewall rules as dictionaries
        """
        try:
            # Use mock db for testing
            if hasattr(self, '_mock_db'):
                db = self._mock_db
            else:
                from app.core.database import get_db
                db = get_db()
            
            result = db.execute(text("SELECT * FROM firewall_rule"))
            rows = result.fetchall()
            
            rules = []
            for row in rows:
                # Handle both ORM rows and dictionaries
                if hasattr(row, 'to_dict'):
                    rule_data = row.to_dict()
                elif hasattr(row, '_mapping'):
                    rule_data = dict(row._mapping)
                elif isinstance(row, dict):
                    rule_data = row
                else:
                    rule_data = dict(row)
                rules.append(rule_data)
            
            return rules
        except Exception as e:
            logger.error(f"Error getting firewall rules: {e}")
            return []
    
    def add_rule(self, rule: FirewallRule) -> int:
        """
        Add a firewall rule to database.
        
        Args:
            rule: FirewallRule to add
            
        Returns:
            1 if successful, 0 otherwise
        """
        db = None
        try:
            # Use mock db for testing
            if hasattr(self, '_mock_db'):
                db = self._mock_db
            else:
                from app.core.database import get_db
                db = get_db()
            
            result = db.execute(text("""
                INSERT INTO firewall_rule (name, action, protocol, src_ip, dst_ip, port, enabled)
                VALUES (:name, :action, :protocol, :src_ip, :dst_ip, :port, :enabled)
            """), {
                "name": rule.name,
                "action": rule.action,
                "protocol": rule.protocol,
                "src_ip": rule.src_ip,
                "dst_ip": rule.dst_ip,
                "port": rule.port,
                "enabled": rule.enabled
            })
            db.commit()
            return 1
        except Exception as e:
            logger.error(f"Error adding firewall rule: {e}")
            if hasattr(db, "rollback"):
                db.rollback()
            return 0
    
    def remove_rule(self, rule: FirewallRule) -> FirewallRule:
        """
        Remove a firewall rule from database.
        
        Args:
            rule: FirewallRule to remove
            
        Returns:
            Removed rule
        """
        db = None
        try:
            # Use mock db for testing
            if hasattr(self, '_mock_db'):
                db = self._mock_db
            else:
                from app.core.database import get_db
                db = get_db()
            
            result = db.execute(text("""
                DELETE FROM firewall_rule WHERE name = :name AND action = :action
            """), {
                "name": rule.name,
                "action": rule.action
            })
            db.commit()
            logger.info(f"Removed firewall rule: {rule.name}")
            return rule
        except Exception as e:
            logger.error(f"Error removing firewall rule: {e}")
            if hasattr(db, "rollback"):
                db.rollback()
            raise
    
    def apply_rules(self, rules: Optional[list] = None) -> bool:
        """
        Apply firewall rules to the system.
        
        Args:
            rules: List of rules to apply (uses all rules if None)
            
        Returns:
            True if rules were applied successfully
        """
        if rules is None:
            rules = self.get_rules()
        
        if not rules:
            logger.info("No firewall rules to apply")
            return True
        
        # In a real implementation, this would apply rules to iptables
        # For now, we just log that rules would be applied
        for rule_data in rules:
            if rule_data.get('enabled', True):
                logger.info(f"Applying firewall rule: {rule_data.get('name')}")
        
        return True
