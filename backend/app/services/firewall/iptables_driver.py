"""Firewall driver for iptables (Linux)."""

import subprocess
import logging
from typing import Optional, List
from .base import FirewallDriver, NATConfig

logger = logging.getLogger(__name__)

# Timeout for all sudo operations (seconds)
SUDO_TIMEOUT = 5


def _run_sudo_command(cmd: List[str], timeout: int = SUDO_TIMEOUT, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a sudo command with timeout and password prompt detection.
    
    Args:
        cmd: Command to run (should start with "sudo")
        timeout: Command timeout in seconds
        check: Whether to raise exception on non-zero return code
        
    Returns:
        CompletedProcess result
        
    Raises:
        subprocess.TimeoutExpired: If command times out (likely waiting for password)
        subprocess.CalledProcessError: If check=True and command fails
    """
    import os
    
    # Ensure -n flag is present for non-interactive mode
    if "-n" not in cmd:
        cmd_with_n = cmd[:1] + ["-n"] + cmd[1:]
    else:
        cmd_with_n = cmd
    
    # Prevent any password prompts
    env = os.environ.copy()
    env['SUDO_ASKPASS'] = '/bin/false'  # Prevent GUI password prompts
    
    try:
        result = subprocess.run(
            cmd_with_n,
            stdin=subprocess.DEVNULL,  # Close stdin to prevent interactive prompts
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
            env=env
        )
        
        # Check if sudo is asking for password
        if result.returncode != 0 and "password" in result.stderr.lower():
            logger.error(f"❌ Command requires password: {' '.join(cmd)}")
            logger.error("   Configure passwordless sudo (see documentation)")
            if check:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        
        return result
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"❌ Command timed out after {timeout}s (likely waiting for password): {' '.join(cmd)}")
        logger.error("   Configure passwordless sudo for all WireGuard and iptables commands")
        raise


class IptablesDriver(FirewallDriver):
    """Firewall driver for iptables (Linux)."""
    
    def name(self) -> str:
        return "iptables"
    
    def is_available(self) -> bool:
        """Check if iptables is available with sudo privileges."""
        import os
        
        # Prevent password prompts
        env = os.environ.copy()
        env['SUDO_ASKPASS'] = '/bin/false'
        
        try:
            # Step 1: Check iptables binary exists
            result = subprocess.run(
                ["iptables", "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=2,
                env=env
            )
            if result.returncode != 0:
                logger.error("iptables command not found")
                return False
            
            # Step 2: Check sudo access (non-interactive with -n flag)
            result = subprocess.run(
                ["sudo", "-n", "iptables", "-L", "-n", "-t", "nat"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=2,
                env=env
            )
            
            if result.returncode != 0:
                if "password" in result.stderr.lower():
                    logger.error("❌ iptables requires passwordless sudo")
                    logger.error("   Configure /etc/sudoers.d/linguard with:")
                    logger.error("   yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables")
                else:
                    logger.error(f"❌ iptables sudo check failed: {result.stderr}")
                return False
            
            logger.debug("✓ iptables available with sudo access")
            return True
            
        except FileNotFoundError:
            logger.error("❌ iptables or sudo command not found on system")
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ iptables check timed out (passwordless sudo not configured)")
            return False
        except subprocess.CalledProcessError:
            logger.error("❌ iptables requires passwordless sudo")
            logger.error("   Configure /etc/sudoers.d/linguard with:")
            logger.error("   yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables")
            return False
    
    def get_default_interface(self) -> Optional[str]:
        """Get default interface using 'ip route show default'."""
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                check=True,
                timeout=2
            )
            # Parse: "default via 192.168.1.1 dev eth0 ..."
            parts = result.stdout.split()
            if "dev" in parts:
                idx = parts.index("dev")
                return parts[idx + 1]
        except (subprocess.CalledProcessError, FileNotFoundError, IndexError, subprocess.TimeoutExpired):
            logger.warning("Could not determine default interface")
        
        return None
    
    def setup_nat(self, config: NATConfig) -> bool:
        """Set up NAT using iptables."""
        try:
            # IPv4 NAT setup
            if config.ipv4_subnet:
                # 1. MASQUERADE rule
                _run_sudo_command([
                    "sudo", "iptables", "-t", "nat", "-A", "POSTROUTING",
                    "-s", config.ipv4_subnet, "-o", config.default_interface,
                    "-j", "MASQUERADE"
                ])
                
                # 2. Allow forwarding FROM WireGuard
                _run_sudo_command([
                    "sudo", "iptables", "-A", "FORWARD",
                    "-i", config.interface, "-j", "ACCEPT"
                ])
                
                # 3. Allow return traffic TO WireGuard
                _run_sudo_command([
                    "sudo", "iptables", "-A", "FORWARD",
                    "-o", config.interface, "-m", "state",
                    "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"
                ])
                
                logger.info(f"iptables: Set up IPv4 NAT for {config.ipv4_subnet} on {config.interface}")
            
            # IPv6 NAT setup
            if config.ipv6_subnet:
                try:
                    _run_sudo_command([
                        "sudo", "ip6tables", "-t", "nat", "-A", "POSTROUTING",
                        "-s", config.ipv6_subnet, "-o", config.default_interface,
                        "-j", "MASQUERADE"
                    ])
                    
                    _run_sudo_command([
                        "sudo", "ip6tables", "-A", "FORWARD",
                        "-i", config.interface, "-j", "ACCEPT"
                    ])
                    
                    _run_sudo_command([
                        "sudo", "ip6tables", "-A", "FORWARD",
                        "-o", config.interface, "-m", "state",
                        "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"
                    ])
                    
                    logger.info(f"iptables: Set up IPv6 NAT for {config.ipv6_subnet} on {config.interface}")
                except subprocess.CalledProcessError:
                    logger.debug("iptables: IPv6 NAT not available on this system")
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("iptables: NAT setup timed out (check passwordless sudo configuration)")
            return False
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"iptables: Failed to set up NAT: {error_msg}")
            return False
    
    def cleanup_nat(self, config: NATConfig) -> bool:
        """Clean up NAT rules using iptables."""
        try:
            # IPv4 cleanup
            if config.ipv4_subnet:
                # Remove in reverse order (best practice)
                # Don't fail if rules don't exist (check=False)
                _run_sudo_command([
                    "sudo", "iptables", "-D", "FORWARD",
                    "-o", config.interface, "-m", "state",
                    "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"
                ], check=False)
                
                _run_sudo_command([
                    "sudo", "iptables", "-D", "FORWARD",
                    "-i", config.interface, "-j", "ACCEPT"
                ], check=False)
                
                _run_sudo_command([
                    "sudo", "iptables", "-t", "nat", "-D", "POSTROUTING",
                    "-s", config.ipv4_subnet, "-o", config.default_interface,
                    "-j", "MASQUERADE"
                ], check=False)
                
                logger.info(f"iptables: Cleaned up IPv4 NAT for {config.ipv4_subnet}")
            
            # IPv6 cleanup
            if config.ipv6_subnet:
                _run_sudo_command([
                    "sudo", "ip6tables", "-D", "FORWARD",
                    "-o", config.interface, "-m", "state",
                    "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"
                ], check=False)
                
                _run_sudo_command([
                    "sudo", "ip6tables", "-D", "FORWARD",
                    "-i", config.interface, "-j", "ACCEPT"
                ], check=False)
                
                _run_sudo_command([
                    "sudo", "ip6tables", "-t", "nat", "-D", "POSTROUTING",
                    "-s", config.ipv6_subnet, "-o", config.default_interface,
                    "-j", "MASQUERADE"
                ], check=False)
                
                logger.info(f"iptables: Cleaned up IPv6 NAT for {config.ipv6_subnet}")
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.warning("iptables: Cleanup timed out (check passwordless sudo configuration)")
            # Don't fail cleanup completely
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"iptables: Cleanup warning (rules may not exist): {e}")
            # Don't fail cleanup
            return True
