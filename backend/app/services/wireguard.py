import logging
import os
import secrets
import subprocess
import platform

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WireGuardService:
    """Service for WireGuard operations using direct wg commands."""

    def __init__(self, dns_hierarchy_service=None, firewall_service=None, wg_binary: str = "wg"):
        """
        Initialize WireGuard service with optional DNS hierarchy and firewall services.
        
        Args:
            dns_hierarchy_service: Optional DNS hierarchy service for DNS resolution
            firewall_service: Optional firewall service for NAT/routing setup
            wg_binary: Path to 'wg' binary (default: "wg" - uses PATH)
        """
        self.dns_hierarchy_service = dns_hierarchy_service
        self.wg_binary = wg_binary
        self.is_macos = platform.system() == "Darwin"
        
        # Import here to avoid circular dependency
        if firewall_service is None:
            from app.services.firewall import FirewallService
            firewall_service = FirewallService()
        self.firewall_service = firewall_service

    def _run_sudo_command(self, cmd: list[str], input_data: str | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
        """
        Run a sudo command with 4-layer protection against password prompts.
        
        This ensures commands fail fast instead of hanging on macOS/systems without passwordless sudo.
        
        Args:
            cmd: Command to run (should include "sudo")
            input_data: Optional stdin data
            timeout: Command timeout in seconds (default: 10)
            
        Returns:
            CompletedProcess result
        """
        # Ensure -n flag is present (non-interactive mode)
        if "sudo" in cmd and "-n" not in cmd:
            sudo_idx = cmd.index("sudo")
            cmd.insert(sudo_idx + 1, "-n")
        
        # Prepare environment to prevent password prompts
        env = os.environ.copy()
        env['SUDO_ASKPASS'] = '/bin/false'
        
        # When input_data is provided, don't set stdin (input parameter handles it)
        # When no input_data, close stdin to prevent any prompts
        if input_data:
            return subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
        else:
            return subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

    def generate_keypair(self) -> tuple[str, str]:
        """
        Generate WireGuard private and public key pair.

        Returns:
            Tuple of (private_key, public_key)
        """
        try:
            # Generate private key
            private_key = subprocess.run(
                [self.wg_binary, "genkey"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            # Generate public key from private key
            public_key = subprocess.run(
                [self.wg_binary, "pubkey"],
                input=private_key,
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()

            return private_key, public_key
        except subprocess.CalledProcessError:
            # Fallback to generating random keys if wg command fails
            private_key = secrets.token_urlsafe(32)
            public_key = secrets.token_urlsafe(32)
            return private_key, public_key

    def generate_preshared_key(self) -> str:
        """Generate WireGuard preshared key."""
        try:
            psk = subprocess.run(
                [self.wg_binary, "genpsk"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            return psk
        except subprocess.CalledProcessError:
            return secrets.token_urlsafe(32)

    def derive_public_key(self, private_key: str) -> str:
        """
        Derive public key from private key.

        Args:
            private_key: WireGuard private key

        Returns:
            Public key string

        Raises:
            ValueError: If private key is invalid
        """
        # Validate input
        if not private_key:
            raise ValueError("Private key is empty")
        
        # Trim whitespace
        private_key = private_key.strip()
        
        if not private_key:
            raise ValueError("Private key is empty after trimming whitespace")
        
        # WireGuard keys should be 44 characters (base64 encoded 32 bytes + padding)
        if len(private_key) != 44:
            raise ValueError(f"Invalid private key length: {len(private_key)} (expected 44 characters)")
        
        if not private_key.endswith('='):
            raise ValueError("Invalid private key format: should end with '='")
        
        try:
            # Ensure newline at end for wg command
            public_key = subprocess.run(
                [self.wg_binary, "pubkey"],
                input=private_key + "\n",
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            return public_key
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise ValueError(f"Failed to derive public key: {error_msg}") from e

    def _create_interface(self, interface: str) -> tuple[bool, str]:
        """
        Create a new WireGuard interface.
        
        Args:
            interface: Interface name (on macOS, will be converted to utun format)
            
        Returns:
            Tuple of (success, actual_interface_name)
        """
        try:
            if self.is_macos:
                # On macOS, wireguard-go requires utun naming
                # Convert wg0 -> utun10, wg1 -> utun11, etc.
                if interface.startswith('wg'):
                    # Extract number from wg0, wg1, etc.
                    try:
                        wg_num = int(interface[2:])
                        interface = f"utun{10 + wg_num}"
                    except ValueError:
                        # If can't parse, use utun10 as default
                        interface = "utun10"
                elif not interface.startswith('utun'):
                    # If not wg or utun format, default to utun10
                    interface = "utun10"
                
                # Check if interface already exists
                check_result = subprocess.run(
                    ["ifconfig", interface],
                    capture_output=True,
                    text=True
                )
                
                if check_result.returncode == 0:
                    # Interface exists, check if it's a WireGuard interface
                    wg_check = self._run_sudo_command(
                        ["sudo", self.wg_binary, "show", interface]
                    )
                    
                    if wg_check.returncode == 0:
                        # It's a WireGuard interface, reuse it
                        logger.info(f"Reusing existing WireGuard interface '{interface}'")
                        return True, interface
                    else:
                        # Interface exists but not WireGuard, find next available
                        logger.warning(f"Interface '{interface}' exists but is not WireGuard, finding next available")
                        # Try utun11, utun12, etc.
                        for i in range(10, 100):
                            test_interface = f"utun{i}"
                            test_result = subprocess.run(
                                ["ifconfig", test_interface],
                                capture_output=True,
                                text=True
                            )
                            if test_result.returncode != 0:
                                interface = test_interface
                                logger.info(f"Using available interface '{interface}'")
                                break
                
                # On macOS, wireguard-go creates utun interfaces automatically
                self._run_sudo_command(
                    ["sudo", "wireguard-go", interface],
                    timeout=15
                )
            else:
                # On Linux, use ip link to create the interface
                self._run_sudo_command(
                    ["sudo", "ip", "link", "add", "dev", interface, "type", "wireguard"],
                    timeout=10
                )
            
            logger.info(f"Created WireGuard interface '{interface}'")
            return True, interface
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to create interface '{interface}': {error_msg}")
            return False, interface

    def _set_interface_config(self, interface: str, private_key: str, listen_port: int) -> bool:
        """
        Configure interface with private key and listen port.
        
        Args:
            interface: Interface name
            private_key: WireGuard private key
            listen_port: Port to listen on
            
        Returns:
            True if successful
        """
        try:
            # Set private key
            self._run_sudo_command(
                ["sudo", self.wg_binary, "set", interface, "private-key", "/dev/stdin"],
                input_data=private_key,
                timeout=10
            )
            
            # Set listen port
            self._run_sudo_command(
                ["sudo", self.wg_binary, "set", interface, "listen-port", str(listen_port)],
                timeout=10
            )
            
            logger.debug(f"Configured interface '{interface}' with private key and port {listen_port}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to configure interface '{interface}': {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to configure interface '{interface}': {e}")
            return False

    def _set_interface_addresses(self, interface: str, ipv4_address: str | None, ipv6_address: str | None) -> bool:
        """
        Set IP addresses on the interface.
        
        Args:
            interface: Interface name
            ipv4_address: IPv4 address in CIDR notation (e.g., "10.0.0.1/24")
            ipv6_address: IPv6 address in CIDR notation (e.g., "fd00::1/64")
            
        Returns:
            True if successful
        """
        try:
            if self.is_macos:
                # On macOS, use ifconfig
                if ipv4_address:
                    # Extract IP and netmask from CIDR
                    ip, cidr = ipv4_address.split('/')
                    self._run_sudo_command(
                        ["sudo", "ifconfig", interface, "inet", ip, ip, "netmask", f"0x{'f' * (int(cidr) // 4)}{'0' * (8 - int(cidr) // 4)}"],
                        timeout=10
                    )
                
                if ipv6_address:
                    self._run_sudo_command(
                        ["sudo", "ifconfig", interface, "inet6", ipv6_address],
                        timeout=10
                    )
            else:
                # On Linux, use ip addr
                if ipv4_address:
                    self._run_sudo_command(
                        ["sudo", "ip", "addr", "add", ipv4_address, "dev", interface],
                        timeout=10
                    )
                
                if ipv6_address:
                    self._run_sudo_command(
                        ["sudo", "ip", "addr", "add", ipv6_address, "dev", interface],
                        timeout=10
                    )
            
            logger.debug(f"Set addresses on interface '{interface}': IPv4={ipv4_address}, IPv6={ipv6_address}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to set addresses on interface '{interface}': {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to set addresses on interface '{interface}': {e}")
            return False

    def _bring_interface_up(self, interface: str) -> bool:
        """
        Bring the interface up.
        
        Args:
            interface: Interface name
            
        Returns:
            True if successful
        """
        try:
            if self.is_macos:
                self._run_sudo_command(
                    ["sudo", "ifconfig", interface, "up"],
                    timeout=10
                )
            else:
                self._run_sudo_command(
                    ["sudo", "ip", "link", "set", interface, "up"],
                    timeout=10
                )
            
            logger.debug(f"Brought interface '{interface}' up")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to bring interface '{interface}' up: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to bring interface '{interface}' up: {e}")
            return False

    def _add_peer(self, interface: str, peer_config: dict) -> bool:
        """
        Add a peer to the interface.
        
        Args:
            interface: Interface name
            peer_config: Dict with 'public_key', 'allowed_ips', 'preshared_key' (optional), 'persistent_keepalive' (optional)
            
        Returns:
            True if successful
        """
        try:
            cmd = ["sudo", self.wg_binary, "set", interface, "peer", peer_config['public_key']]
            
            if peer_config.get('allowed_ips'):
                cmd.extend(["allowed-ips", peer_config['allowed_ips']])
            
            if peer_config.get('preshared_key'):
                # Write preshared key via stdin
                self._run_sudo_command(
                    cmd + ["preshared-key", "/dev/stdin"],
                    input_data=peer_config['preshared_key'],
                    timeout=10
                )
            else:
                self._run_sudo_command(cmd, timeout=10)
            
            # Set persistent keepalive if specified
            if peer_config.get('persistent_keepalive'):
                self._run_sudo_command(
                    ["sudo", self.wg_binary, "set", interface, "peer", peer_config['public_key'],
                     "persistent-keepalive", str(peer_config['persistent_keepalive'])],
                    timeout=10
                )
            
            logger.debug(f"Added peer {peer_config['public_key'][:20]}... to interface '{interface}'")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to add peer to interface '{interface}': {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to add peer to interface '{interface}': {e}")
            return False

    def _remove_all_peers(self, interface: str) -> bool:
        """
        Remove all peers from the interface.
        
        Args:
            interface: Interface name
            
        Returns:
            True if successful
        """
        try:
            # Get current peers
            output = self._run_sudo_command(
                ["sudo", self.wg_binary, "show", interface, "peers"],
                timeout=10
            ).stdout
            
            # Remove each peer
            for peer_pubkey in output.strip().splitlines():
                if peer_pubkey:
                    self._run_sudo_command(
                        ["sudo", self.wg_binary, "set", interface, "peer", peer_pubkey, "remove"],
                        timeout=10
                    )
            
            logger.debug(f"Removed all peers from interface '{interface}'")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to remove peers from interface '{interface}': {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to remove peers from interface '{interface}': {e}")
            return False

    def _setup_nat(self, interface: str, ipv4_subnet: str | None, ipv6_subnet: str | None) -> bool:
        """
        Set up NAT/masquerading for the WireGuard interface.
        
        Args:
            interface: WireGuard interface name
            ipv4_subnet: IPv4 subnet in CIDR notation (e.g., "10.0.0.0/24")
            ipv6_subnet: IPv6 subnet in CIDR notation (optional)
            
        Returns:
            True if successful
        """
        return self.firewall_service.setup_nat(interface, ipv4_subnet, ipv6_subnet)

    def _cleanup_nat(self, interface: str, ipv4_subnet: str | None, ipv6_subnet: str | None) -> bool:
        """
        Clean up NAT/masquerading rules for the WireGuard interface.
        
        Args:
            interface: WireGuard interface name
            ipv4_subnet: IPv4 subnet in CIDR notation (e.g., "10.0.0.0/24")
            ipv6_subnet: IPv6 subnet in CIDR notation (optional)
            
        Returns:
            True if successful
        """
        return self.firewall_service.cleanup_nat(interface, ipv4_subnet, ipv6_subnet)

    async def start_interface(self, db: AsyncSession, server_id: int, interface: str) -> bool:
        """
        Start WireGuard interface using wg commands directly.
        
        Args:
            db: Database session
            server_id: Server ID to get configuration from
            interface: Interface name to create
            
        Returns:
            True if successful
        """
        from ..models.peer import Peer
        from ..models.server import Server

        try:
            logger.info(f"Starting WireGuard interface '{interface}' for server ID {server_id}")
            
            # Get server configuration
            result = await db.execute(select(Server).where(Server.id == server_id))
            server = result.scalar_one_or_none()
            
            if not server:
                raise ValueError(f"Server {server_id} not found")
            
            # Step 1: Create interface
            success, actual_interface = self._create_interface(interface)
            if not success:
                return False
            
            # Use the actual interface name (on macOS, this might be different from requested)
            interface = actual_interface
            
            # Step 2: Configure interface (private key and port)
            if not self._set_interface_config(interface, server.private_key, server.listen_port):
                return False
            
            # Step 3: Set IP addresses
            if not self._set_interface_addresses(interface, server.ipv4_address, server.ipv6_address):
                return False
            
            # Step 4: Bring interface up
            if not self._bring_interface_up(interface):
                return False
            
            # Step 5: Set up NAT/masquerading
            # Extract subnet from server IP for NAT configuration
            ipv4_subnet = None
            ipv6_subnet = None
            if server.ipv4_address:
                # Convert single IP to subnet (e.g., "10.0.0.1/24" stays as is)
                ipv4_subnet = server.ipv4_address
            if server.ipv6_address:
                ipv6_subnet = server.ipv6_address
            
            if not self._setup_nat(interface, ipv4_subnet, ipv6_subnet):
                logger.error("Failed to set up NAT - cannot start server without proper routing")
                # Clean up the interface we just created
                self.stop_interface(interface, ipv4_subnet, ipv6_subnet)
                return False
            
            # Step 6: Add peers
            result = await db.execute(
                select(Peer).where(
                    Peer.server_id == server_id,
                    Peer.enabled == True
                )
            )
            peers = result.scalars().all()
            
            for peer in peers:
                # Build allowed IPs for this peer
                allowed_ips_list = []
                if peer.ipv4_address:
                    ip = peer.ipv4_address.split('/')[0]
                    allowed_ips_list.append(f"{ip}/32")
                if peer.ipv6_address:
                    ip = peer.ipv6_address.split('/')[0]
                    allowed_ips_list.append(f"{ip}/128")
                
                allowed_ips = ', '.join(allowed_ips_list) if allowed_ips_list else None
                
                if allowed_ips:
                    peer_config = {
                        'public_key': peer.public_key,
                        'allowed_ips': allowed_ips,
                        'preshared_key': peer.preshared_key,
                        'persistent_keepalive': peer.persistent_keepalive
                    }
                    
                    if not self._add_peer(interface, peer_config):
                        logger.warning(f"Failed to add peer {peer.name} to interface '{interface}'")
            
            logger.info(f"Interface '{interface}' started successfully with {len(peers)} peer(s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start interface '{interface}': {e}", exc_info=True)
            return False

    def stop_interface(self, interface: str, ipv4_subnet: str | None = None, ipv6_subnet: str | None = None) -> bool:
        """
        Stop WireGuard interface by bringing it down and removing it.
        Also cleans up NAT rules if subnets are provided.
        
        Args:
            interface: Interface name
            ipv4_subnet: IPv4 subnet to clean up NAT rules for (optional)
            ipv6_subnet: IPv6 subnet to clean up NAT rules for (optional)
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Stopping WireGuard interface '{interface}'")
            
            # Step 1: Clean up NAT rules if subnets provided
            if ipv4_subnet or ipv6_subnet:
                self._cleanup_nat(interface, ipv4_subnet, ipv6_subnet)
            
            # Step 2: Bring interface down and remove all peers
            if self.is_macos:
                # Remove all peers first
                self._remove_all_peers(interface)
                
                # Bring interface down
                self._run_sudo_command(
                    ["sudo", "ifconfig", interface, "down"],
                    timeout=10
                )
                
                # Note: On macOS, the wireguard-go process may remain running
                # but with the interface down and no peers, it's harmless
                # The interface will be properly cleaned up when a new one is started
                logger.debug(f"Interface '{interface}' brought down (wireguard-go process may remain)")
            else:
                self._run_sudo_command(
                    ["sudo", "ip", "link", "set", interface, "down"],
                    timeout=10
                )
                
                # On Linux, also delete the interface
                self._run_sudo_command(
                    ["sudo", "ip", "link", "delete", interface],
                    timeout=10
                )
            
            logger.info(f"Interface '{interface}' stopped successfully")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"Failed to stop interface '{interface}': {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Failed to stop interface '{interface}': {e}")
            return False

    async def reload_interface(self, db: AsyncSession, server_id: int, interface: str) -> bool:
        """
        Reload WireGuard interface configuration by removing and re-adding all peers.
        
        Args:
            db: Database session
            server_id: Server ID to get configuration from
            interface: Interface name
            
        Returns:
            True if successful
        """
        from ..models.peer import Peer
        
        try:
            logger.info(f"Reloading WireGuard interface '{interface}'")
            
            # Step 1: Remove all existing peers
            if not self._remove_all_peers(interface):
                return False
            
            # Step 2: Re-add all enabled peers from database
            result = await db.execute(
                select(Peer).where(
                    Peer.server_id == server_id,
                    Peer.enabled == True
                )
            )
            peers = result.scalars().all()
            
            for peer in peers:
                # Build allowed IPs for this peer
                allowed_ips_list = []
                if peer.ipv4_address:
                    ip = peer.ipv4_address.split('/')[0]
                    allowed_ips_list.append(f"{ip}/32")
                if peer.ipv6_address:
                    ip = peer.ipv6_address.split('/')[0]
                    allowed_ips_list.append(f"{ip}/128")
                
                allowed_ips = ', '.join(allowed_ips_list) if allowed_ips_list else None
                
                if allowed_ips:
                    peer_config = {
                        'public_key': peer.public_key,
                        'allowed_ips': allowed_ips,
                        'preshared_key': peer.preshared_key,
                        'persistent_keepalive': peer.persistent_keepalive
                    }
                    
                    if not self._add_peer(interface, peer_config):
                        logger.warning(f"Failed to add peer {peer.name} during reload")
            
            logger.info(f"Interface '{interface}' reloaded successfully with {len(peers)} peer(s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload interface '{interface}': {e}", exc_info=True)
            return False

    def get_interface_status(self, interface: str) -> dict | None:
        """Get WireGuard interface status."""
        try:
            output = self._run_sudo_command(
                ["sudo", self.wg_binary, "show", interface],
                timeout=10
            ).stdout

            return {"status": "running", "output": output}
        except subprocess.CalledProcessError:
            return {"status": "stopped", "output": ""}
        except Exception:
            return {"status": "stopped", "output": ""}

    def _is_interface_up(self, interface: str) -> bool:
        """
        Check if an interface is actually UP using ifconfig.
        
        Args:
            interface: Interface name
            
        Returns:
            True if interface is UP, False otherwise
        """
        try:
            result = subprocess.run(
                ["ifconfig", interface],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                return False
            
            # Check if the flags line contains "UP"
            for line in result.stdout.splitlines():
                if "flags=" in line and "UP" in line:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking if interface {interface} is up: {e}")
            return False

    def get_all_interfaces(self) -> list[dict]:
        """
        Get all running WireGuard interfaces with their public keys.
        Only returns interfaces that are actually UP (not just wireguard-go running).
        
        Returns:
            List of dicts with 'interface' and 'public_key' keys
        """
        try:
            output = self._run_sudo_command(
                ["sudo", self.wg_binary, "show", "all"],
                timeout=10
            ).stdout

            interfaces = []
            current_interface = None
            
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("interface:"):
                    current_interface = line.split(":", 1)[1].strip()
                elif line.startswith("public key:") and current_interface:
                    public_key = line.split(":", 1)[1].strip()
                    
                    # Check if interface is actually UP via ifconfig
                    if self._is_interface_up(current_interface):
                        interfaces.append({
                            "interface": current_interface,
                            "public_key": public_key
                        })
                        logger.debug(f"Interface {current_interface} is UP and running")
                    else:
                        logger.debug(f"Interface {current_interface} exists in wg but is not UP (ifconfig)")
                    
                    current_interface = None
            
            logger.debug(f"Found {len(interfaces)} UP WireGuard interface(s)")
            return interfaces
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to query WireGuard interfaces: {e}")
            return []
        except subprocess.TimeoutExpired:
            logger.error("Timeout querying WireGuard interfaces (sudo may require password)")
            return []
        except Exception as e:
            logger.error(f"Unexpected error querying WireGuard interfaces: {e}")
            return []

    def find_interface_by_public_key(self, public_key: str) -> str | None:
        """
        Find the interface name for a given public key.
        
        Args:
            public_key: WireGuard public key to search for
            
        Returns:
            Interface name if found, None otherwise
        """
        logger.debug(f"Looking up interface for public key: {public_key[:20]}...")
        interfaces = self.get_all_interfaces()
        for iface in interfaces:
            if iface["public_key"] == public_key:
                logger.info(f"Found interface '{iface['interface']}' for public key {public_key[:20]}...")
                return iface["interface"]
        logger.debug(f"No running interface found for public key {public_key[:20]}...")
        return None

    def get_next_available_interface(self, prefix: str = "wg") -> str:
        """
        Get the next available interface name.
        
        Args:
            prefix: Interface name prefix (default: "wg")
            
        Returns:
            Next available interface name (e.g., "wg0", "wg1", etc.)
        """
        interfaces = self.get_all_interfaces()
        existing_numbers = []
        
        for iface in interfaces:
            name = iface["interface"]
            # Extract number from interface name (e.g., "wg0" -> 0, "utun10" -> 10)
            if name.startswith(prefix):
                try:
                    num = int(name[len(prefix):])
                    existing_numbers.append(num)
                except ValueError:
                    continue
        
        # Find the lowest available number
        next_num = 0
        while next_num in existing_numbers:
            next_num += 1
        
        return f"{prefix}{next_num}"

    # ============================================================================
    # Config file generation methods (for downloads and QR codes only)
    # ============================================================================

    def generate_config_file(
        self,
        interface: str,
        private_key: str,
        address: str,
        listen_port: int,
        peers: list[dict]
    ) -> str:
        """
        Generate WireGuard configuration file content (for export/download only).

        Args:
            interface: Interface name
            private_key: Server private key
            address: Server IP address(es)
            listen_port: Server listen port
            peers: List of peer configurations

        Returns:
            Configuration file content as string
        """
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {address}
ListenPort = {listen_port}

"""

        for peer in peers:
            config += f"""[Peer]
PublicKey = {peer['public_key']}
"""
            if peer.get('preshared_key'):
                config += f"PresharedKey = {peer['preshared_key']}\n"

            if peer.get('allowed_ips'):
                config += f"AllowedIPs = {peer['allowed_ips']}\n"

            if peer.get('persistent_keepalive'):
                config += f"PersistentKeepalive = {peer['persistent_keepalive']}\n"

            config += "\n"

        return config

    def generate_peer_config(
        self,
        private_key: str,
        address: str,
        dns: str | None,
        server_public_key: str,
        server_endpoint: str,
        server_port: int,
        allowed_ips: str = "0.0.0.0/0, ::/0",
        persistent_keepalive: int = 25,
        preshared_key: str | None = None
    ) -> str:
        """
        Generate peer/client configuration file content (for export/download only).

        Returns:
            Configuration file content as string
        """
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {address}
"""

        if dns:
            config += f"DNS = {dns}\n"

        config += f"""
[Peer]
PublicKey = {server_public_key}
"""

        if preshared_key:
            config += f"PresharedKey = {preshared_key}\n"

        config += f"""Endpoint = {server_endpoint}:{server_port}
AllowedIPs = {allowed_ips}
PersistentKeepalive = {persistent_keepalive}
"""

        return config

    async def generate_server_config(self, db: AsyncSession, server_id: int) -> str:
        """
        Generate complete WireGuard server configuration from database (for export/download only).

        Args:
            db: Database session
            server_id: Server ID

        Returns:
            Configuration file content as string
        """
        from ..models.peer import Peer
        from ..models.server import Server

        # Get server
        result = await db.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()

        if not server:
            raise ValueError(f"Server {server_id} not found")

        # Get all enabled peers for this server
        result = await db.execute(
            select(Peer).where(
                Peer.server_id == server_id,
                Peer.enabled == True
            )
        )
        peers = result.scalars().all()

        # Build peer configurations
        peer_configs = []
        for peer in peers:
            # Combine IPv4 and IPv6 addresses for server-side AllowedIPs
            # (this is what IPs the server will accept from this peer)
            allowed_ips_list = []
            if peer.ipv4_address:
                # Extract IP from CIDR notation if present, then add /32
                ip = peer.ipv4_address.split('/')[0]
                allowed_ips_list.append(f"{ip}/32")
            if peer.ipv6_address:
                # Extract IP from CIDR notation if present, then add /128
                ip = peer.ipv6_address.split('/')[0]
                allowed_ips_list.append(f"{ip}/128")

            # Fallback to empty if no addresses (shouldn't happen but be safe)
            allowed_ips = ', '.join(allowed_ips_list) if allowed_ips_list else "0.0.0.0/32"

            peer_config = {
                'public_key': peer.public_key,
                'allowed_ips': allowed_ips,
                'preshared_key': peer.preshared_key,
                'persistent_keepalive': peer.persistent_keepalive
            }
            peer_configs.append(peer_config)

        # Combine server addresses (already in CIDR notation)
        address_list = []
        if server.ipv4_address:
            address_list.append(server.ipv4_address)
        if server.ipv6_address:
            address_list.append(server.ipv6_address)

        address = ', '.join(address_list) if address_list else server.ipv4_address

        return self.generate_config_file(
            interface=server.interface or "wg0",
            private_key=server.private_key,
            address=address,
            listen_port=server.listen_port,
            peers=peer_configs
        )

    async def generate_peer_config_from_db(self, db: AsyncSession, peer_id: int) -> str:
        """
        Generate complete peer configuration from database (for export/download only).

        Args:
            db: Database session
            peer_id: Peer ID

        Returns:
            Configuration file content as string
        """
        from ..models.peer import Peer
        from ..models.server import Server
        from ..services.dns_hierarchy import DNSHierarchyService

        # Get peer
        result = await db.execute(select(Peer).where(Peer.id == peer_id))
        peer = result.scalar_one_or_none()

        if not peer:
            raise ValueError(f"Peer {peer_id} not found")

        # Get server
        result = await db.execute(select(Server).where(Server.id == peer.server_id))
        server = result.scalar_one_or_none()

        if not server:
            raise ValueError(f"Server {peer.server_id} not found")

        # Get DNS settings from hierarchy
        dns_primary, dns_secondary = None, None
        if self.dns_hierarchy_service:
            dns_primary, dns_secondary = await self.dns_hierarchy_service.resolve_dns_for_peer(db, peer_id)

        # Combine DNS
        dns_list = []
        if dns_primary:
            dns_list.append(dns_primary)
        if dns_secondary:
            dns_list.append(dns_secondary)
        dns = ', '.join(dns_list) if dns_list else None

        # Combine peer addresses
        address_list = []
        if peer.ipv4_address:
            # Check if CIDR notation already present
            if '/' in peer.ipv4_address:
                address_list.append(peer.ipv4_address)
            else:
                address_list.append(f"{peer.ipv4_address}/32")
        if peer.ipv6_address:
            # Check if CIDR notation already present
            if '/' in peer.ipv6_address:
                address_list.append(peer.ipv6_address)
            else:
                address_list.append(f"{peer.ipv6_address}/128")
        address = ', '.join(address_list) if address_list else None

        if not address:
            raise ValueError(f"Peer {peer_id} has no IP address configured")

        # Combine allowed IPs (routes to send through VPN)
        allowed_ips_list = []
        if peer.ipv4_allowed_ips:
            allowed_ips_list.append(peer.ipv4_allowed_ips)
        if peer.ipv6_allowed_ips:
            allowed_ips_list.append(peer.ipv6_allowed_ips)
        allowed_ips = ', '.join(allowed_ips_list) if allowed_ips_list else "0.0.0.0/0, ::/0"

        return self.generate_peer_config(
            private_key=peer.private_key,
            address=address,
            dns=dns,
            server_public_key=server.public_key,
            server_endpoint=server.endpoint,
            server_port=server.listen_port,
            allowed_ips=allowed_ips,
            persistent_keepalive=peer.persistent_keepalive,
            preshared_key=peer.preshared_key
        )
