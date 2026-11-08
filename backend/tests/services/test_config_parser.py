"""
Comprehensive tests for config_parser module.
Tests all code paths to achieve high coverage.
"""
from app.services.config_parser import ConfigParser


class TestConfigParser:
    """Test ConfigParser functions."""
    
    def test_parse_server_config_empty(self):
        """Test parsing empty config."""
        parser = ConfigParser()
        result = parser.parse_server_config("")
        
        assert isinstance(result, dict)
        assert result == {"interface": {}, "peers": []}
    
    def test_parse_server_config_with_interface(self):
        """Test parsing server config with interface section."""
        parser = ConfigParser()
        config = """
# Comment line
[Interface]
PrivateKey = abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
ListenPort = 51820
Address = 10.0.0.1/24
DNS = 8.8.8.8, 1.1.1.1
"""
        result = parser.parse_server_config(config)
        
        assert result["interface"]["PrivateKey"] == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        assert result["interface"]["ListenPort"] == "51820"
        assert result["interface"]["Address"] == "10.0.0.1/24"
        assert result["interface"]["DNS"] == "8.8.8.8, 1.1.1.1"
    
    def test_parse_server_config_with_peers(self):
        """Test parsing server config with peers."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc123
ListenPort = 51820
Address = 10.0.0.1/24
[Peer]
PublicKey = peerkey123
AllowedIPs = 192.168.1.10/32
PersistentKeepalive = 25
Endpoint = 192.168.1.1:51820
PresharedKey = presharekey123
"""
        result = parser.parse_server_config(config)
        
        assert len(result["peers"]) == 1
        assert result["peers"][0]["PublicKey"] == "peerkey123"
        assert result["peers"][0]["AllowedIPs"] == "192.168.1.10/32"
        assert result["peers"][0]["PersistentKeepalive"] == "25"
        assert result["peers"][0]["Endpoint"] == "192.168.1.1:51820"
        assert result["peers"][0]["PresharedKey"] == "presharekey123"
    
    def test_parse_server_config_empty_lines(self):
        """Test parsing config with empty lines."""
        parser = ConfigParser()
        config = """
[Interface]

PrivateKey = abc123

ListenPort = 51820
"""
        result = parser.parse_server_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc123"
        assert result["interface"]["ListenPort"] == "51820"
    
    def test_parse_server_config_comments(self):
        """Test parsing config with comment lines."""
        parser = ConfigParser()
        config = """
# This is a comment
[Interface]
# Another comment
PrivateKey = abc123
"""
        result = parser.parse_server_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc123"
    
    def test_parse_server_config_empty_peer_section(self):
        """Test parsing config with empty peer section."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc123
[Peer]
PublicKey = peerkey
"""
        result = parser.parse_server_config(config)
        
        assert len(result["peers"]) == 1
        assert result["peers"][0]["PublicKey"] == "peerkey"
    
    def test_parse_peer_config_empty(self):
        """Test parsing empty peer config."""
        parser = ConfigParser()
        result = parser.parse_peer_config("")
        
        assert isinstance(result, dict)
        assert result == {"interface": {}, "peer": {}}
    
    def test_parse_peer_config_with_interface(self):
        """Test parsing peer config with interface section."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc123
ListenPort = 51820
Address = 10.0.0.1/24
DNS = 8.8.8.8
"""
        result = parser.parse_peer_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc123"
        assert result["interface"]["ListenPort"] == "51820"
    
    def test_parse_peer_config_with_peer(self):
        """Test parsing peer config with peer section."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc123
[Peer]
PublicKey = peerkey123
AllowedIPs = 192.168.1.10/32
PersistentKeepalive = 25
"""
        result = parser.parse_peer_config(config)
        
        assert result["peer"]["PublicKey"] == "peerkey123"
        assert result["peer"]["AllowedIPs"] == "192.168.1.10/32"
    
    def test_parse_peer_config_empty_lines(self):
        """Test parsing peer config with empty lines."""
        parser = ConfigParser()
        config = """
[Interface]

PrivateKey = abc123

[Peer]

PublicKey = peerkey
"""
        result = parser.parse_peer_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc123"
        assert result["peer"]["PublicKey"] == "peerkey"
    
    def test_parse_peer_config_comments(self):
        """Test parsing peer config with comment lines."""
        parser = ConfigParser()
        config = """
# Comment
[Interface]
# Another comment
PrivateKey = abc123

[Peer]
PublicKey = peerkey
"""
        result = parser.parse_peer_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc123"
        assert result["peer"]["PublicKey"] == "peerkey"
    
    def test_extract_server_data_empty_config(self):
        """Test extracting server data from empty config."""
        parser = ConfigParser()
        parsed = {"interface": {}, "peers": []}
        result = parser.extract_server_data(parsed)
        
        assert result["private_key"] == ""
        assert result["listen_port"] == 51820
        assert result["ipv4_address"] == ""
        assert result["ipv6_address"] is None
        assert result["dns_primary"] is None
        assert result["dns_secondary"] is None
    
    def test_extract_server_data_with_values(self):
        """Test extracting server data with actual values."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "ListenPort": "51820",
                "Address": "10.0.0.1/24",
                "DNS": "8.8.8.8, 1.1.1.1"
            }
        }
        result = parser.extract_server_data(parsed)
        
        assert result["private_key"] == "abc123"
        assert result["listen_port"] == 51820
        assert result["ipv4_address"] == "10.0.0.1/24"
        assert result["ipv6_address"] is None
        assert result["dns_primary"] == "8.8.8.8"
        assert result["dns_secondary"] == "1.1.1.1"
    
    def test_extract_server_data_with_ipv6(self):
        """Test extracting server data with IPv6 address."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "ListenPort": "51820",
                "Address": "::1/128",
                "DNS": "2001:4860:4860::8888"
            }
        }
        result = parser.extract_server_data(parsed)
        
        assert result["private_key"] == "abc123"
        assert result["ipv4_address"] is None
        assert result["ipv6_address"] == "::1/128"
    
    def test_extract_server_data_with_both_ipv4_and_ipv6(self):
        """Test extracting server data with both IPv4 and IPv6 addresses."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "ListenPort": "51820",
                "Address": "10.0.0.1/24, ::1/128",
                "DNS": "8.8.8.8, 2001:4860:4860::8888"
            }
        }
        result = parser.extract_server_data(parsed)
        
        assert result["ipv4_address"] == "10.0.0.1/24"
        assert result["ipv6_address"] == "::1/128"
    
    def test_extract_peers_data_empty_peers(self):
        """Test extracting peers data from empty peers list."""
        parser = ConfigParser()
        parsed = {"interface": {}, "peers": []}
        result = parser.extract_peers_data(parsed)
        
        assert result == []
    
    def test_extract_peers_data_with_single_peer(self):
        """Test extracting peers data with single peer."""
        parser = ConfigParser()
        parsed = {
            "interface": {},
            "peers": [
                {
                    "PublicKey": "peerkey123",
                    "AllowedIPs": "192.168.1.10/32",
                    "PersistentKeepalive": "25",
                    "Endpoint": "192.168.1.1:51820",
                    "PresharedKey": "presharekey"
                }
            ]
        }
        result = parser.extract_peers_data(parsed)
        
        assert len(result) == 1
        peer = result[0]
        assert peer["public_key"] == "peerkey123"
        assert peer["ipv4_allowed_ips"] == "192.168.1.10/32"
        assert peer["ipv6_allowed_ips"] is None
        assert peer["persistent_keepalive"] == 25
        assert peer["endpoint"] == "192.168.1.1:51820"
        assert peer["preshared_key"] == "presharekey"
    
    def test_extract_peers_data_with_ipv6_allowed_ips(self):
        """Test extracting peers data with IPv6 allowed IPs."""
        parser = ConfigParser()
        parsed = {
            "interface": {},
            "peers": [
                {
                    "PublicKey": "peerkey123",
                    "AllowedIPs": "10.0.0.1/24,fd00::1/128"
                }
            ]
        }
        result = parser.extract_peers_data(parsed)
        
        assert len(result) == 1
        peer = result[0]
        assert peer["ipv4_allowed_ips"] == "10.0.0.1/24"
        assert peer["ipv6_allowed_ips"] == "fd00::1/128"
    
    def test_extract_peers_data_with_all_peer_fields(self):
        """Test extracting peers data with all peer fields."""
        parser = ConfigParser()
        parsed = {
            "interface": {},
            "peers": [
                {
                    "PublicKey": "peerkey123",
                    "PresharedKey": "presharekey",
                    "AllowedIPs": "10.0.0.1/32",
                    "PersistentKeepalive": "25",
                    "Endpoint": "server:51820"
                }
            ]
        }
        result = parser.extract_peers_data(parsed)
        
        assert len(result) == 1
        assert result[0]["public_key"] == "peerkey123"
        assert result[0]["preshared_key"] == "presharekey"
        assert result[0]["ipv4_allowed_ips"] == "10.0.0.1/32"
        assert result[0]["persistent_keepalive"] == 25
        assert result[0]["endpoint"] == "server:51820"
    
    def test_extract_peer_client_data_empty(self):
        """Test extracting client peer data from empty config."""
        parser = ConfigParser()
        parsed = {"interface": {}, "peer": {}}
        result = parser.extract_peer_client_data(parsed)
        
        assert result["private_key"] == ""
        assert result["server_public_key"] == ""
        assert result["persistent_keepalive"] == 25
        assert result["server_port"] is None
    
    def test_extract_peer_client_data_with_values(self):
        """Test extracting client peer data with actual values."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "Address": "10.0.0.1/24",
                "DNS": "8.8.8.8"
            },
            "peer": {
                "PublicKey": "serverkey",
                "AllowedIPs": "192.168.1.10/32",
                "Endpoint": "server:51820"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        assert result["private_key"] == "abc123"
        assert result["ipv4_address"] == "10.0.0.1/24"
        assert result["ipv6_address"] is None
        assert result["server_public_key"] == "serverkey"
        assert result["server_endpoint"] == "server"
        assert result["server_port"] == 51820
    
    def test_extract_peer_client_data_with_ipv6(self):
        """Test extracting client peer data with IPv6 address."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "Address": "::1/128"
            },
            "peer": {
                "PublicKey": "serverkey",
                "AllowedIPs": "fd00::1/128"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        assert result["ipv4_address"] is None
        assert result["ipv6_address"] == "::1/128"
        assert result["ipv4_allowed_ips"] is None
        assert result["ipv6_allowed_ips"] == "fd00::1/128"
    
    def test_extract_peer_client_data_with_preshared_key(self):
        """Test extracting client peer data with preshared key."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123"
            },
            "peer": {
                "PublicKey": "serverkey",
                "PresharedKey": "presharekey123",
                "PersistentKeepalive": "25"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        assert result["preshared_key"] == "presharekey123"
        assert result["persistent_keepalive"] == 25
    
    def test_extract_peer_client_data_with_multiple_dns(self):
        """Test extracting client peer data with multiple DNS servers."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123",
                "DNS": "8.8.8.8, 1.1.1.1"
            },
            "peer": {
                "PublicKey": "serverkey",
                "AllowedIPs": "10.0.0.1/32"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        assert result["dns_primary"] == "8.8.8.8"
        assert result["dns_secondary"] == "1.1.1.1"
    
    def test_extract_peer_client_data_with_no_endpoint(self):
        """Test extracting client peer data with no endpoint."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123"
            },
            "peer": {
                "PublicKey": "serverkey",
                "AllowedIPs": "10.0.0.1/32"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        assert result["server_endpoint"] is None
        assert result["server_port"] is None
    
    def test_extract_peer_client_data_with_zero_keepalive(self):
        """Test extracting client peer data with zero keepalive."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "abc123"
            },
            "peer": {
                "PublicKey": "serverkey",
                "PersistentKeepalive": "0"
            }
        }
        result = parser.extract_peer_client_data(parsed)
        
        # When PersistentKeepalive is 0, it's converted to integer 0
        assert result["persistent_keepalive"] == 0
    
    def test_parse_server_config_with_special_characters(self):
        """Test parsing config with special characters."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc@123!$%
ListenPort = 51820
Address = 10.0.0.1/24
DNS = 8.8.8.8, 1.1.1.1
[Peer]
PublicKey = peer@key!$
AllowedIPs = 192.168.1.10/32
PersistentKeepalive = 25
Endpoint = server:51820
PresharedKey = presh@are@key!$
"""
        result = parser.parse_server_config(config)
        
        assert result["interface"]["PrivateKey"] == "abc@123!$%"
        assert result["peers"][0]["PublicKey"] == "peer@key!$"
        assert result["peers"][0]["PresharedKey"] == "presh@are@key!$"
    
    def test_parse_server_config_with_unicode(self):
        """Test parsing config with unicode characters."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = abc123
ListenPort = 51820
Address = 10.0.0.1/24
DNS = 8.8.8.8, 1.1.1.1
[Peer]
PublicKey = peerkey
PresharedKey = prés@hare
"""
        result = parser.parse_server_config(config)
        
        assert result["peers"][0]["PresharedKey"] == "prés@hare"
    
    def test_parse_server_config_with_empty_values(self):
        """Test parsing config with empty values."""
        parser = ConfigParser()
        config = """
[Interface]
PrivateKey = 
ListenPort = 
Address = 
DNS = 
[Peer]
PublicKey = 
AllowedIPs = 
PersistentKeepalive = 
Endpoint = 
PresharedKey = 
"""
        result = parser.parse_server_config(config)
        
        assert result["interface"]["PrivateKey"] == ""
        assert result["interface"]["ListenPort"] == ""
        assert result["peers"][0]["PublicKey"] == ""
        assert result["peers"][0]["PresharedKey"] == ""
    
    def test_extract_server_data_with_empty_private_key(self):
        """Test extracting server data with empty private key."""
        parser = ConfigParser()
        parsed = {
            "interface": {
                "PrivateKey": "",
                "ListenPort": "51820",
                "Address": "10.0.0.1/24"
            }
        }
        result = parser.extract_server_data(parsed)
        
        assert result["private_key"] == ""
        assert result["listen_port"] == 51820

    def test_parse_server_config_multiple_peers_split_by_blank_line(self):
        """Consecutive [Peer] blocks separated by a blank line are collected."""
        parser = ConfigParser()
        config = """[Interface]
ListenPort = 51820

[Peer]
PublicKey = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=
AllowedIPs = 10.0.0.2/32

[Peer]
PublicKey = bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb=
AllowedIPs = 10.0.0.3/32
"""
        result = parser.parse_server_config(config)

        assert len(result["peers"]) == 2
        assert result["peers"][0]["PublicKey"].startswith("a" * 8)
        assert result["peers"][1]["PublicKey"].startswith("b" * 8)

    def test_parse_server_config_peer_before_interface_is_kept(self):
        """An [Interface] header after a [Peer] block must not drop that peer."""
        parser = ConfigParser()
        config = """[Peer]
PublicKey = ccccccccccccccccccccccccccccccccccccccccccc=

[Interface]
ListenPort = 51820
"""
        result = parser.parse_server_config(config)

        assert len(result["peers"]) == 1
        assert result["interface"]["ListenPort"] == "51820"
