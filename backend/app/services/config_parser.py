

class ConfigParser:
    """Parser for WireGuard configuration files."""

    def parse_server_config(self, config_content: str) -> dict:
        """
        Parse WireGuard server configuration file.

        Args:
            config_content: Content of the config file

        Returns:
            Dictionary with parsed configuration
        """
        config = {
            "interface": {},
            "peers": []
        }

        current_section = None
        current_peer = None

        for line in config_content.split('\n'):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Section headers
            if line == '[Interface]':
                current_section = 'interface'
                continue
            elif line == '[Peer]':
                current_section = 'peer'
                current_peer = {}
                continue

            # Parse key-value pairs
            if '=' in line:
                key, value = (x.strip() for x in line.split('=', 1))

                if current_section == 'interface':
                    config['interface'][key] = value
                elif current_section == 'peer' and current_peer is not None:
                    current_peer[key] = value

            # End of peer section
            if current_section == 'peer' and current_peer and (line == '' or line.startswith('[')):
                config['peers'].append(current_peer)
                current_peer = {}

        # Add last peer if exists
        if current_peer:
            config['peers'].append(current_peer)

        return config

    def parse_peer_config(self, config_content: str) -> dict:
        """
        Parse WireGuard peer/client configuration file.

        Args:
            config_content: Content of the config file

        Returns:
            Dictionary with parsed configuration
        """
        config = {
            "interface": {},
            "peer": {}
        }

        current_section = None

        for line in config_content.split('\n'):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Section headers
            if line == '[Interface]':
                current_section = 'interface'
                continue
            elif line == '[Peer]':
                current_section = 'peer'
                continue

            # Parse key-value pairs
            if '=' in line:
                key, value = (x.strip() for x in line.split('=', 1))

                if current_section == 'interface':
                    config['interface'][key] = value
                elif current_section == 'peer':
                    config['peer'][key] = value

        return config

    def extract_server_data(self, parsed_config: dict) -> dict:
        """
        Extract server data from parsed config into database format.

        Args:
            parsed_config: Parsed configuration dictionary

        Returns:
            Dictionary ready for server model
        """
        interface = parsed_config.get('interface', {})

        # Parse Address field for IPv4 and IPv6
        address = interface.get('Address', '')
        addresses = [addr.strip() for addr in address.split(',')]

        ipv4_address = None
        ipv6_address = None

        for addr in addresses:
            if ':' in addr:  # IPv6
                ipv6_address = addr
            else:  # IPv4
                ipv4_address = addr

        # Parse DNS
        dns = interface.get('DNS', '')
        dns_list = [d.strip() for d in dns.split(',') if d.strip()]
        dns_primary = dns_list[0] if len(dns_list) > 0 else None
        dns_secondary = dns_list[1] if len(dns_list) > 1 else None

        return {
            "private_key": interface.get('PrivateKey', ''),
            "listen_port": int(interface.get('ListenPort', 51820)),
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary
        }

    def extract_peers_data(self, parsed_config: dict) -> list:
        """
        Extract peers data from parsed server config.

        Args:
            parsed_config: Parsed configuration dictionary

        Returns:
            List of peer dictionaries
        """
        peers_data = []

        for peer in parsed_config.get('peers', []):
            # Parse AllowedIPs for IPv4 and IPv6
            allowed_ips = peer.get('AllowedIPs', '')
            allowed_list = [ip.strip() for ip in allowed_ips.split(',')]

            ipv4_allowed = []
            ipv6_allowed = []

            for ip in allowed_list:
                if ':' in ip:  # IPv6
                    ipv6_allowed.append(ip)
                else:  # IPv4
                    ipv4_allowed.append(ip)

            peer_data = {
                "public_key": peer.get('PublicKey', ''),
                "preshared_key": peer.get('PresharedKey'),
                "ipv4_allowed_ips": ','.join(ipv4_allowed) if ipv4_allowed else None,
                "ipv6_allowed_ips": ','.join(ipv6_allowed) if ipv6_allowed else None,
                "persistent_keepalive": int(peer.get('PersistentKeepalive', 0)) if peer.get('PersistentKeepalive') else None,
                "endpoint": peer.get('Endpoint')
            }

            peers_data.append(peer_data)

        return peers_data

    def extract_peer_client_data(self, parsed_config: dict) -> dict:
        """
        Extract client peer data from parsed config.

        Args:
            parsed_config: Parsed configuration dictionary

        Returns:
            Dictionary with peer data
        """
        interface = parsed_config.get('interface', {})
        peer = parsed_config.get('peer', {})

        # Parse Address field
        address = interface.get('Address', '')
        addresses = [addr.strip() for addr in address.split(',')]

        ipv4_address = None
        ipv6_address = None

        for addr in addresses:
            if ':' in addr:  # IPv6
                ipv6_address = addr
            else:  # IPv4
                ipv4_address = addr

        # Parse DNS
        dns = interface.get('DNS', '')
        dns_list = [d.strip() for d in dns.split(',') if d.strip()]
        dns_primary = dns_list[0] if len(dns_list) > 0 else None
        dns_secondary = dns_list[1] if len(dns_list) > 1 else None

        # Parse AllowedIPs
        allowed_ips = peer.get('AllowedIPs', '')
        allowed_list = [ip.strip() for ip in allowed_ips.split(',')]

        ipv4_allowed = []
        ipv6_allowed = []

        for ip in allowed_list:
            if ':' in ip:  # IPv6
                ipv6_allowed.append(ip)
            else:  # IPv4
                ipv4_allowed.append(ip)

        # Parse Endpoint
        endpoint = peer.get('Endpoint', '')
        server_endpoint = None
        server_port = None
        if endpoint and ':' in endpoint:
            parts = endpoint.rsplit(':', 1)
            server_endpoint = parts[0]
            server_port = int(parts[1]) if len(parts) > 1 else None

        return {
            "private_key": interface.get('PrivateKey', ''),
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary,
            "server_public_key": peer.get('PublicKey', ''),
            "preshared_key": peer.get('PresharedKey'),
            "ipv4_allowed_ips": ','.join(ipv4_allowed) if ipv4_allowed else None,
            "ipv6_allowed_ips": ','.join(ipv6_allowed) if ipv6_allowed else None,
            "persistent_keepalive": int(peer.get('PersistentKeepalive', 25)) if peer.get('PersistentKeepalive') else 25,
            "server_endpoint": server_endpoint,
            "server_port": server_port
        }
