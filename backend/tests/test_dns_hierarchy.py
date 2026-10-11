"""
Unit tests for DNS Hierarchy Service.

Tests cover:
- DNS hierarchy configuration
- DNS resolution
- DNS update
- DNS validation
"""

from unittest.mock import MagicMock, patch
import json


class TestDNSHierarchyConfig:
    """Test DNS hierarchy configuration."""
    
    def test_config_initialization(self):
        """Test DNS hierarchy configuration initialization."""
        from app.services.dns_hierarchy import DNSHierarchyConfig
        
        config = DNSHierarchyConfig()
        
        assert config is not None
        
    def test_config_dns_servers(self):
        """Test DNS servers configuration."""
        from app.services.dns_hierarchy import DNSHierarchyConfig
        
        config = DNSHierarchyConfig()
        
        # Should have DNS servers
        assert hasattr(config, 'dns_servers')
        
    def test_config_dns_domain(self):
        """Test DNS domain configuration."""
        from app.services.dns_hierarchy import DNSHierarchyConfig
        
        config = DNSHierarchyConfig()
        
        # Should have DNS domain
        assert hasattr(config, 'dns_domain')
        
    def test_config_wireguard_config(self):
        """Test WireGuard config path."""
        from app.services.dns_hierarchy import DNSHierarchyConfig
        
        config = DNSHierarchyConfig()
        
        # Should have WireGuard config path
        assert hasattr(config, 'wireguard_config')


class TestDNSResolution:
    """Test DNS resolution."""
    
    @patch('app.services.dns_hierarchy.subprocess')
    def test_dns_resolve(self, mock_subprocess):
        """Test DNS resolution."""
        from app.services.dns_hierarchy import resolve_dns
        
        # Setup mock
        mock_subprocess.check_output.return_value = b"192.168.1.1\n"
        
        # Resolve DNS
        result = resolve_dns("example.com")
        
        assert result is not None
        
    @patch('app.services.dns_hierarchy.subprocess')
    def test_dns_resolve_invalid(self, mock_subprocess):
        """Test DNS resolution with error."""
        from app.services.dns_hierarchy import resolve_dns
        
        # Setup mock
        mock_subprocess.check_output.side_effect = Exception("DNS error")
        
        # Resolve DNS with error
        result = resolve_dns("invalid.example.com")
        
        # Should return None on error
        assert result is None or result == []


class TestDNSUpdate:
    """Test DNS update."""
    
    @patch('app.services.dns_hierarchy.subprocess')
    @patch('app.services.dns_hierarchy.db')
    def test_update_dns(self, mock_db, mock_subprocess):
        """Test DNS update."""
        from app.services.dns_hierarchy import update_dns
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_domain = "linguard.local"
            
            # Update DNS
            result = update_dns()
            
            assert result is not None
            
    @patch('app.services.dns_hierarchy.subprocess')
    @patch('app.services.dns_hierarchy.db')
    def test_update_dns_with_peers(self, mock_db, mock_subprocess):
        """Test DNS update with peer information."""
        from app.services.dns_hierarchy import update_dns
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_domain = "linguard.local"
            
            # Update DNS with peers
            peers = [
                {"name": "peer1", "ip": "192.168.1.10"},
                {"name": "peer2", "ip": "192.168.1.11"},
            ]
            
            result = update_dns(peers)
            
            assert result is not None


class TestDNSValidation:
    """Test DNS validation."""
    
    @patch('app.services.dns_hierarchy.subprocess')
    def test_dns_valid(self, mock_subprocess):
        """Test valid DNS configuration."""
        from app.services.dns_hierarchy import is_dns_valid
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Valid DNS
        result = is_dns_valid("/etc/wireguard/wg0.conf")
        
        assert result is not None
        
    @patch('app.services.dns_hierarchy.subprocess')
    def test_dns_invalid(self, mock_subprocess):
        """Test invalid DNS configuration."""
        from app.services.dns_hierarchy import is_dns_valid
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=1)
        
        # Invalid DNS
        result = is_dns_valid("/etc/wireguard/wg0.conf")
        
        assert result is False


class TestDNSHierarchyService:
    """Test DNS Hierarchy Service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        from app.services.dns_hierarchy import DNSHierarchyService
        
        service = DNSHierarchyService()
        
        assert service is not None
        
    def test_service_get_dns_servers(self):
        """Test getting DNS servers."""
        from app.services.dns_hierarchy import DNSHierarchyService
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_servers = ["8.8.8.8", "8.8.4.4"]
            
            service = DNSHierarchyService()
            
            servers = service.get_dns_servers()
            
            assert servers == ["8.8.8.8", "8.8.4.4"]
            
    def test_service_add_dns_server(self):
        """Test adding DNS server."""
        from app.services.dns_hierarchy import DNSHierarchyService
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_servers = ["8.8.8.8"]
            
            service = DNSHierarchyService()
            
            service.add_dns_server("1.1.1.1")
            
            servers = service.get_dns_servers()
            
            assert "1.1.1.1" in servers
            
    def test_service_remove_dns_server(self):
        """Test removing DNS server."""
        from app.services.dns_hierarchy import DNSHierarchyService
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_servers = ["8.8.8.8", "1.1.1.1"]
            
            service = DNSHierarchyService()
            
            service.remove_dns_server("1.1.1.1")
            
            servers = service.get_dns_servers()
            
            assert "1.1.1.1" not in servers


class TestDNSConfiguration:
    """Test DNS configuration."""
    
    def test_dns_config_structure(self):
        """Test DNS config structure."""
        from app.services.dns_hierarchy import generate_dns_config
        
        # Mock config
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_servers = ["8.8.8.8", "1.1.1.1"]
            mock_config.dns_domain = "linguard.local"
            
            config = generate_dns_config()
            
            assert config is not None
            assert isinstance(config, dict)
            
    def test_dns_config_with_wireguard(self):
        """Test DNS config with WireGuard integration."""
        from app.services.dns_hierarchy import generate_dns_config
        
        with patch('app.services.dns_hierarchy.config') as mock_config:
            mock_config.dns_servers = ["8.8.8.8"]
            mock_config.dns_domain = "linguard.local"
            mock_config.wireguard_config = "/etc/wireguard/wg0.conf"
            
            config = generate_dns_config()
            
            assert config is not None


class TestDNSPeers:
    """Test DNS peer management."""
    
    @patch('app.services.dns_hierarchy.db')
    def test_get_peer_ips(self, mock_db):
        """Test getting peer IPs."""
        from app.services.dns_hierarchy import get_peer_ips
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.side_effect = [
            "192.168.1.10",
            "192.168.1.11",
        ]
        mock_db.execute.return_value = mock_result
        
        peers = get_peer_ips()
        
        assert len(peers) == 2
        
    @patch('app.services.dns_hierarchy.db')
    def test_get_peer_ips_empty(self, mock_db):
        """Test getting empty peer IPs."""
        from app.services.dns_hierarchy import get_peer_ips
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result
        
        peers = get_peer_ips()
        
        assert len(peers) == 0


if __name__ == "__main__":
    import datetime
    datetime_mock = datetime.datetime(2024, 1, 1, 0, 0, 0)
    
    pytest.main([__file__, "-v", "--cov=app.services.dns_hierarchy", "--cov-report=term-missing"])
