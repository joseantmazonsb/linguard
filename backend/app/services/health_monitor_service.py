"""
Health Monitor Service

Monitors system health in the background and broadcasts status changes via WebSocket.
Runs periodic health checks and notifies connected clients when health status changes.
"""

import asyncio
import logging
import platform
import subprocess
from datetime import datetime
from typing import Dict, Optional

from ..core import database as _db
from ..core.config import settings
from ..utils.wireguard_detect import detect_wireguard_binaries

logger = logging.getLogger(__name__)


class HealthMonitorService:
    """
    Background service that monitors system health and broadcasts updates.
    
    Runs periodic health checks (every 30 seconds by default) and broadcasts
    via WebSocket only when health status changes, reducing network traffic.
    """
    
    def __init__(self, check_interval_seconds: int = 30):
        """
        Initialize the health monitor service.
        
        Args:
            check_interval_seconds: How often to check health (default: 30 seconds)
        """
        self.check_interval_seconds = check_interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_health_status: Optional[Dict] = None
        
    async def start(self):
        """Start the background health monitoring task."""
        if self._running:
            logger.warning("Health monitor is already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Health monitor started (checking every {self.check_interval_seconds}s)")
        
    async def stop(self):
        """Stop the background health monitoring task."""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitor stopped")
        
    async def _monitor_loop(self):
        """Main monitoring loop that runs periodically."""
        while self._running:
            try:
                await self._check_and_broadcast_health()
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
            
            # Wait before next check
            await asyncio.sleep(self.check_interval_seconds)
            
    async def _check_and_broadcast_health(self):
        """Check health status and broadcast if changed."""
        try:
            # Perform health check
            health_status = await self.check_health()
            
            # Check if status has changed
            if self._has_status_changed(self._last_health_status, health_status):
                logger.info(f"Health status changed to: {health_status['status']}")
                
                # Broadcast the update
                await self._broadcast_health_update(health_status)
                
                # Update last known status
                self._last_health_status = health_status
            else:
                logger.debug("Health status unchanged, skipping broadcast")
                
        except Exception as e:
            logger.error(f"Error checking health: {e}", exc_info=True)
    
    def _has_status_changed(self, old_status: Optional[Dict], new_status: Dict) -> bool:
        """
        Check if health status has changed.
        
        Compares overall status and individual component statuses.
        Returns True if this is the first check or if any status changed.
        
        Args:
            old_status: Previous health status (None if first check)
            new_status: Current health status
            
        Returns:
            True if status changed, False otherwise
        """
        # First check - always broadcast
        if old_status is None:
            return True
        
        # Check overall status
        if old_status.get("status") != new_status.get("status"):
            return True
        
        # Check individual component statuses
        old_checks = old_status.get("checks", {})
        new_checks = new_status.get("checks", {})
        
        for component in new_checks.keys():
            old_component = old_checks.get(component, {})
            new_component = new_checks.get(component, {})
            
            # Compare status
            if old_component.get("status") != new_component.get("status"):
                return True
            
            # Compare message (in case message changed but status didn't)
            if old_component.get("message") != new_component.get("message"):
                return True
        
        return False
    
    async def _broadcast_health_update(self, health_data: Dict):
        """Broadcast health update to all connected WebSocket clients."""
        try:
            # Import here to avoid circular dependency
            from ..api.ws import broadcast_health_update
            
            await broadcast_health_update(health_data)
            logger.debug("Health update broadcasted via WebSocket")
            
        except Exception as e:
            logger.error(f"Error broadcasting health update: {e}", exc_info=True)
    
    async def check_health(self) -> Dict:
        """
        Perform comprehensive health check.
        
        Tests database, WireGuard, IP forwarding, and firewall accessibility.
        Returns overall status and details about each component.
        
        Returns:
            Dictionary with health status and component checks
        """
        current_platform = platform.system()
        is_linux = current_platform == "Linux"
        in_debug_mode = settings.DEBUG_BYPASS_FIREWALL
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": {"status": "healthy", "message": None},
                "wireguard": {"status": "healthy", "message": None},
                "ip_forwarding": {"status": "healthy", "message": None},
                "firewall": {"status": "healthy", "message": None}
            }
        }
        
        # Check database connectivity
        try:
            from sqlalchemy import text
            async with _db.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            health_status["checks"]["database"]["status"] = "healthy"
            health_status["checks"]["database"]["message"] = "Database connection successful"
        except Exception as e:
            health_status["checks"]["database"]["status"] = "unhealthy"
            health_status["checks"]["database"]["message"] = f"Database error: {str(e)}"
        
        # Check WireGuard availability
        import os
        
        # Prevent password prompts
        env = os.environ.copy()
        env['SUDO_ASKPASS'] = '/bin/false'
        
        wg_paths = detect_wireguard_binaries()
        if not wg_paths.get("wg"):
            health_status["checks"]["wireguard"]["status"] = "unhealthy"
            health_status["checks"]["wireguard"]["message"] = "WireGuard (wg) command not found. Install WireGuard to use Linguard."
        else:
            try:
                result = subprocess.run(
                    ["sudo", "-n", "wg", "show"],
                    stdin=subprocess.DEVNULL,  # Close stdin to prevent hanging
                    capture_output=True,
                    text=True,
                    timeout=5,  # Add timeout to prevent hanging
                    env=env
                )
                
                if result.returncode == 0:
                    health_status["checks"]["wireguard"]["status"] = "healthy"
                    health_status["checks"]["wireguard"]["message"] = "WireGuard is accessible"
                else:
                    # Check if password is required
                    if "password" in result.stderr.lower():
                        health_status["checks"]["wireguard"]["status"] = "unhealthy"
                        health_status["checks"]["wireguard"]["message"] = "WireGuard requires passwordless sudo (configure /etc/sudoers.d/linguard)"
                    else:
                        health_status["checks"]["wireguard"]["status"] = "unhealthy"
                        health_status["checks"]["wireguard"]["message"] = f"WireGuard command failed: {result.stderr.strip()}"
            except subprocess.TimeoutExpired:
                health_status["checks"]["wireguard"]["status"] = "unhealthy"
                health_status["checks"]["wireguard"]["message"] = "WireGuard command timed out (likely waiting for password - configure passwordless sudo)"
            except FileNotFoundError:
                health_status["checks"]["wireguard"]["status"] = "unhealthy"
                health_status["checks"]["wireguard"]["message"] = "sudo command not found. Cannot run WireGuard with elevated privileges."
            except Exception as e:
                health_status["checks"]["wireguard"]["status"] = "unhealthy"
                health_status["checks"]["wireguard"]["message"] = f"WireGuard check error: {str(e)}"
        
        # Check IP forwarding status
        try:
            # Skip check in debug mode on non-Linux platforms
            if in_debug_mode and not is_linux:
                health_status["checks"]["ip_forwarding"]["status"] = "warning"
                health_status["checks"]["ip_forwarding"]["message"] = f"DEBUG MODE on {current_platform}: IP forwarding check skipped"
            else:
                ipv4_forwarding_enabled = False
                ipv6_forwarding_enabled = False
                errors = []
                
                # Check Linux IPv4 forwarding
                try:
                    result = subprocess.run(
                        ["sysctl", "net.ipv4.ip_forward"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False
                    )
                    if result.returncode == 0:
                        value = result.stdout.strip().split("=")[-1].strip()
                        ipv4_forwarding_enabled = (value == "1")
                        if not ipv4_forwarding_enabled:
                            errors.append("IPv4 forwarding is disabled")
                    else:
                        errors.append("Could not check IPv4 forwarding")
                except Exception as e:
                    errors.append(f"IPv4 forwarding check failed: {str(e)}")
                
                # Check Linux IPv6 forwarding
                try:
                    result = subprocess.run(
                        ["sysctl", "net.ipv6.conf.all.forwarding"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=False
                    )
                    if result.returncode == 0:
                        value = result.stdout.strip().split("=")[-1].strip()
                        ipv6_forwarding_enabled = (value == "1")
                        if not ipv6_forwarding_enabled:
                            errors.append("IPv6 forwarding is disabled")
                    else:
                        errors.append("Could not check IPv6 forwarding")
                except Exception as e:
                    errors.append(f"IPv6 forwarding check failed: {str(e)}")
                
                # Determine status based on both checks
                if ipv4_forwarding_enabled and ipv6_forwarding_enabled:
                    health_status["checks"]["ip_forwarding"]["status"] = "healthy"
                    health_status["checks"]["ip_forwarding"]["message"] = "IPv4 and IPv6 forwarding are enabled"
                elif ipv4_forwarding_enabled:
                    health_status["checks"]["ip_forwarding"]["status"] = "warning"
                    health_status["checks"]["ip_forwarding"]["message"] = "IPv4 forwarding is enabled. IPv6 forwarding is disabled (IPv6 traffic will not work)."
                elif ipv6_forwarding_enabled:
                    health_status["checks"]["ip_forwarding"]["status"] = "warning"
                    health_status["checks"]["ip_forwarding"]["message"] = "IPv6 forwarding is enabled. IPv4 forwarding is disabled (IPv4 traffic will not work)."
                elif errors:
                    health_status["checks"]["ip_forwarding"]["status"] = "unhealthy"
                    health_status["checks"]["ip_forwarding"]["message"] = "; ".join(errors) + ". Traffic routing will not work."
                else:
                    health_status["checks"]["ip_forwarding"]["status"] = "unhealthy"
                    health_status["checks"]["ip_forwarding"]["message"] = "IP forwarding could not be verified"
                
        except FileNotFoundError:
            health_status["checks"]["ip_forwarding"]["status"] = "unhealthy"
            health_status["checks"]["ip_forwarding"]["message"] = "sysctl command not found. Cannot configure IP forwarding."
        except Exception as e:
            health_status["checks"]["ip_forwarding"]["status"] = "unhealthy"
            health_status["checks"]["ip_forwarding"]["message"] = f"Error checking IP forwarding: {str(e)}"
        
        # Check firewall/iptables accessibility
        try:
            # Handle debug mode on non-Linux platforms
            if in_debug_mode and not is_linux:
                health_status["checks"]["firewall"]["status"] = "warning"
                health_status["checks"]["firewall"]["message"] = f"DEBUG MODE on {current_platform}: Using dummy firewall driver (NAT will NOT work)"
            elif not is_linux:
                # Non-Linux without debug mode (shouldn't happen as app would exit on startup)
                health_status["checks"]["firewall"]["status"] = "unhealthy"
                health_status["checks"]["firewall"]["message"] = f"Platform {current_platform} not supported. Linguard requires Linux with iptables."
            else:
                # Linux - check iptables with -n flag to prevent password prompt
                result = subprocess.run(
                    ["sudo", "-n", "iptables", "-L", "-n"],
                    stdin=subprocess.DEVNULL,  # Close stdin to prevent hanging
                    capture_output=True,
                    text=True,
                    timeout=5,  # Add timeout
                    env=env  # Use env from WireGuard check above
                )
                if result.returncode == 0:
                    health_status["checks"]["firewall"]["status"] = "healthy"
                    health_status["checks"]["firewall"]["message"] = "iptables is accessible and functional"
                else:
                    # Check if password is required
                    if "password" in result.stderr.lower():
                        health_status["checks"]["firewall"]["status"] = "unhealthy"
                        health_status["checks"]["firewall"]["message"] = "iptables requires passwordless sudo (configure /etc/sudoers.d/linguard)"
                    else:
                        health_status["checks"]["firewall"]["status"] = "unhealthy"
                        health_status["checks"]["firewall"]["message"] = f"iptables command failed: {result.stderr.strip()}"
        except FileNotFoundError:
            health_status["checks"]["firewall"]["status"] = "unhealthy"
            health_status["checks"]["firewall"]["message"] = "iptables command not found"
        except subprocess.TimeoutExpired:
            health_status["checks"]["firewall"]["status"] = "unhealthy"
            health_status["checks"]["firewall"]["message"] = "Firewall check timed out (likely waiting for password - configure passwordless sudo)"
        except Exception as e:
            health_status["checks"]["firewall"]["status"] = "unhealthy"
            health_status["checks"]["firewall"]["message"] = f"Firewall check error: {str(e)}"
        
        # Determine overall status based on all component checks
        # Only unhealthy checks affect overall status, warnings are ignored
        has_unhealthy = any(
            check["status"] == "unhealthy"
            for check in health_status["checks"].values()
        )
        health_status["status"] = "unhealthy" if has_unhealthy else "healthy"
        
        return health_status
