"""Pytest fixtures for DNS hierarchy tests."""

import pytest
from unittest.mock import MagicMock, patch
from app.services.dns_hierarchy import DNSHierarchyConfig, DNSHierarchyService, config


@pytest.fixture
def dns_config():
    """Create a mock DNS config."""
    return DNSHierarchyConfig(
        dns_servers=["8.8.8.8", "8.8.4.4"],
        dns_domain="linguard.local",
        wireguard_config="/etc/wireguard/wg0.conf"
    )


@pytest.fixture
def dns_service(dns_config):
    """Create a mock DNS hierarchy service."""
    service = MagicMock(spec=DNSHierarchyService)
    service.get_dns_servers.return_value = ["8.8.8.8", "8.8.4.4"]
    service.add_dns_server.return_value = True
    service.remove_dns_server.return_value = True
    service.update_dns_server.return_value = True
    service.validate_dns_server.return_value = True
    service.get_dns_config.return_value = {
        "dns_primary": "8.8.8.8",
        "dns_secondary": "8.8.4.4"
    }
    service.set_dns_config.return_value = True
    service.resolve_dns.return_value = "192.168.1.1"
    service.update_dns.return_value = True
    return service


@pytest.fixture
def patch_config():
    """Patch config module."""
    with patch('app.services.dns_hierarchy.config') as mock_config:
        mock_config.dns_servers = ["8.8.8.8", "8.8.4.4"]
        mock_config.dns_domain = "linguard.local"
        mock_config.wireguard_config = "/etc/wireguard/wg0.conf"
        mock_config.dns_config_path = "/etc/dns/config.json"
        yield mock_config


@pytest.fixture
def patch_subprocess():
    """Patch subprocess module."""
    with patch('app.services.dns_hierarchy.subprocess') as mock_subprocess:
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.check_output.return_value = b"192.168.1.1\n"
        yield mock_subprocess


@pytest.fixture
def mock_db():
    """Create a mock database."""
    mock_db_obj = MagicMock()
    mock_result = MagicMock()
    
    # Configure mock to return peer IPs for tests
    def execute_side_effect(query, **params):
        if "ipv4_address" in str(query):
            mock_result.scalars.return_value.first.side_effect = [
                MagicMock(ipv4_address="192.168.1.10"),
                MagicMock(ipv4_address="192.168.1.11"),
            ]
        return mock_result
    
    mock_db_obj.execute.side_effect = execute_side_effect
    return mock_db_obj


@pytest.fixture
def peer_data():
    """Create mock peer data."""
    return [
        {"name": "peer1", "ip": "192.168.1.10"},
        {"name": "peer2", "ip": "192.168.1.11"},
    ]
