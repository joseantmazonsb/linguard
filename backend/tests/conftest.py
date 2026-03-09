"""
Test fixtures for Linguard tests.

This module provides common fixtures for testing with mocked services.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from app.services.audit_logger import AuditService
from app.services.autofill import AutoFillService
from app.services.backup_service import BackupService
from app.services.bounce_routing import BounceServerService
from app.services.config_parser import ConfigParser
from app.services.dns_hierarchy import DNSHierarchyService
from app.services.ip_management import IPManagementService
from app.services.migration import MigrationService
from app.services.version_service import VersionService
from app.services.wireguard import WireGuardService


@pytest.fixture
def mock_wireguard_service():
    """Mock WireGuardService for testing."""
    mock = Mock(spec=WireGuardService)
    # Setup common return values
    mock.generate_keypair.return_value = ("mock_private_key", "mock_public_key")
    mock.generate_preshared_key.return_value = "mock_preshared_key"
    mock.generate_server_config = AsyncMock(
        return_value="[Interface]\nPrivateKey = mock_key\n"
    )
    mock.generate_peer_config_from_db = AsyncMock(
        return_value="[Interface]\nPrivateKey = mock_key\n"
    )
    mock.apply_config.return_value = None
    mock.start_interface.return_value = None
    mock.stop_interface.return_value = None
    mock.reload_interface.return_value = None
    return mock


@pytest.fixture
def mock_audit_service():
    """Mock AuditService for testing."""
    mock = Mock(spec=AuditService)
    mock.log_action = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_backup_service():
    """Mock BackupService for testing."""
    mock = Mock(spec=BackupService)
    # Add mock return values as needed
    mock.create_backup = AsyncMock(
        return_value=Mock(
            id=1,
            description="Test backup",
            encrypted=False,
            size_bytes=1024,
            file_path="/tmp/backup.json",
        )
    )
    mock.restore_backup = AsyncMock(return_value={"restored": True})
    return mock


@pytest.fixture
def mock_config_parser():
    """Mock ConfigParser for testing."""
    mock = Mock(spec=ConfigParser)
    mock.parse_server_config.return_value = {
        "name": "test-server",
        "interface_name": "wg0",
        "listen_port": 51820,
        "address": "10.0.0.1/24",
    }
    mock.parse_peer_config.return_value = {
        "name": "test-peer",
        "address": "10.0.0.2/32",
        "public_key": "mock_public_key",
    }
    return mock


@pytest.fixture
def mock_ip_management_service():
    """Mock IPManagementService for testing."""
    mock = Mock(spec=IPManagementService)
    mock.get_next_available_ip = AsyncMock(return_value="10.0.0.2")
    mock.validate_ip_address.return_value = True
    mock.is_ip_in_use = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_dns_hierarchy_service():
    """Mock DNSHierarchyService for testing."""
    mock = Mock(spec=DNSHierarchyService)
    mock.get_effective_dns_servers = AsyncMock(return_value=["8.8.8.8", "8.8.4.4"])
    mock.validate_dns_server.return_value = True
    return mock


@pytest.fixture
def mock_autofill_service():
    """Mock AutoFillService for testing."""
    mock = Mock(spec=AutoFillService)
    mock.get_server_defaults = AsyncMock(
        return_value={
            "listen_port": 51820,
            "address": "10.0.0.1/24",
            "dns_servers": "8.8.8.8,8.8.4.4",
        }
    )
    mock.get_peer_defaults = AsyncMock(
        return_value={
            "address": "10.0.0.2/32",
            "dns_servers": "8.8.8.8,8.8.4.4",
            "allowed_ips": "0.0.0.0/0",
        }
    )
    return mock


@pytest.fixture
def mock_migration_service():
    """Mock MigrationService for testing."""
    mock = Mock(spec=MigrationService)
    mock.migrate_peer = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_bounce_routing_service():
    """Mock BounceServerService for testing."""
    mock = Mock(spec=BounceServerService)
    mock.validate_bounce_server = AsyncMock(return_value=True)
    mock.configure_bounce_routing = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_version_service():
    """Mock VersionService for testing."""
    mock = Mock(spec=VersionService)
    mock.get_current_version.return_value = {
        "version": "1.0.0",
        "name": "Linguard",
        "repository": "https://github.com/example/wireguard-webgui",
    }
    mock.check_for_updates = AsyncMock(
        return_value={"current_version": "1.0.0", "update_available": False}
    )
    mock.get_changelog.return_value = []
    return mock
    return mock
