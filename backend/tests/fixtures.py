"""Pytest fixtures for DI services - simplified for testing."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def async_test_db():
    """Create in-memory SQLite database for tests."""
    # Just return the engine - tables will be created by individual tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    return engine


@pytest.fixture
def ip_management_service():
    """IP Management Service mock."""
    service = MagicMock()
    service.get_next_ip.return_value = "10.0.0.100"
    service.get_available_ip.return_value = "10.0.0.101"
    service.reserve_ip.return_value = True
    return service


@pytest.fixture
def dns_hierarchy_service():
    """DNS Hierarchy Service mock."""
    service = MagicMock()
    service.generate_unique_ip.return_value = "10.0.0.1"
    service.get_dns_server.return_value = "8.8.8.8"
    return service


@pytest.fixture
def audit_service():
    """Audit Service mock."""
    service = MagicMock()
    return service


@pytest.fixture
def notification_service():
    """Notification Service mock."""
    service = MagicMock()
    service.send_email = AsyncMock()
    service.send_push = AsyncMock()
    service.send_webhook = AsyncMock()
    return service


@pytest.fixture
def firewall_service():
    """Firewall Service mock."""
    service = MagicMock()
    service.setup_interface_rules = AsyncMock()
    service.setup_peer_rules = AsyncMock()
    service.setup_global_rules = AsyncMock()
    service.remove_interface_rules = AsyncMock()
    service.remove_peer_rules = AsyncMock()
    service.remove_global_rules = AsyncMock()
    service.check_interface_rules = AsyncMock(return_value=True)
    service.check_peer_rules = AsyncMock(return_value=True)
    service.check_global_rules = AsyncMock(return_value=True)
    return service


@pytest.fixture
def wireguard_service(ip_management_service, dns_hierarchy_service, firewall_service):
    """WireGuard Service mock."""
    service = MagicMock()
    service.create_interface = AsyncMock(return_value={"name": "wg0", "path": "/etc/wireguard/wg0.conf"})
    service.delete_interface = AsyncMock()
    service.start_interface = AsyncMock()
    service.stop_interface = AsyncMock()
    service.reload_interface = AsyncMock()
    service.get_interface_status = AsyncMock(return_value={"status": "running"})
    return service


@pytest.fixture
def autofill_service(ip_management_service, dns_hierarchy_service, wireguard_service):
    """AutoFill Service mock."""
    service = MagicMock()
    service.fill_config = MagicMock()
    return service


@pytest.fixture
def migration_service(ip_management_service, dns_hierarchy_service, audit_service):
    """Migration Service mock."""
    service = MagicMock()
    service.version = "2.0.0"
    service.get_current_version = AsyncMock(return_value="1.0.0")
    service.check_migration_needed = AsyncMock(return_value=True)
    service.run_migration = AsyncMock(return_value=True)
    service.migrate_peers = AsyncMock(return_value=[])
    service.migrate_config = AsyncMock(return_value=True)
    service.export_data = AsyncMock(return_value={})
    service.import_data = AsyncMock(return_value=True)
    service.create_backup = AsyncMock(return_value=True)
    service.restore_backup = AsyncMock(return_value=True)
    service.rollback_migration = AsyncMock(return_value=True)
    return service


@pytest.fixture
def metrics_collector_service():
    """Metrics Collector Service mock."""
    service = MagicMock()
    service.collect_metrics = AsyncMock(return_value={"rx_bytes": 1000, "tx_bytes": 500})
    return service


@pytest.fixture
def traffic_threshold_service():
    """Traffic Threshold Service mock."""
    service = MagicMock()
    service.get_threshold = AsyncMock(return_value=1000000)
    return service


@pytest.fixture
def settings_service():
    """Settings Service mock."""
    service = MagicMock()
    service.get_settings = AsyncMock(return_value={"backup_enabled": True})
    return service


@pytest.fixture
def metrics_monitor_service(metrics_collector_service, traffic_threshold_service, settings_service):
    """Metrics Monitor Service mock."""
    service = MagicMock()
    service.start = AsyncMock()
    service.stop = AsyncMock()
    return service


@pytest.fixture
def backup_service(settings_service):
    """Backup Service mock."""
    service = MagicMock()
    service.create_backup = AsyncMock(return_value="/backups/backup.tar.gz")
    service.restore_backup = AsyncMock(return_value=True)
    service.list_backups = AsyncMock(return_value=[])
    return service


@pytest.fixture
def health_monitor_service():
    """Health Monitor Service mock."""
    service = MagicMock()
    service.start = AsyncMock()
    service.stop = AsyncMock()
    service.check_health = AsyncMock(return_value=True)
    return service


@pytest.fixture
def interface_monitor_service(wireguard_service):
    """Interface Monitor Service mock."""
    service = MagicMock()
    service.start = AsyncMock()
    service.stop = AsyncMock()
    service.check_interface = AsyncMock(return_value=True)
    return service


@pytest.fixture
def backup_cleanup_service(backup_service, settings_service):
    """Backup Cleanup Service mock."""
    service = MagicMock()
    service.cleanup_old_backups = AsyncMock(return_value=True)
    return service


@pytest.fixture
def periodic_backup_service(backup_service, settings_service):
    """Periodic Backup Service mock."""
    service = MagicMock()
    service.start = AsyncMock()
    service.stop = AsyncMock()
    return service


@pytest.fixture
def integration_service(notification_service):
    """Integration Service mock."""
    service = MagicMock()
    service.create_integration = AsyncMock(return_value={"id": 1, "name": "test"})
    service.delete_integration = AsyncMock()
    service.get_integrations = AsyncMock(return_value=[])
    return service


@pytest.fixture
def plugin_manager():
    """Plugin Manager mock."""
    service = MagicMock()
    service.load_plugins = AsyncMock()
    service.get_plugins = AsyncMock(return_value=[])
    return service


@pytest.fixture
def bouncer_service():
    """Bounce Server Service mock."""
    service = MagicMock()
    service.is_bouncer = AsyncMock(return_value=False)
    service.enable_bouncer = AsyncMock()
    service.disable_bouncer = AsyncMock()
    return service


@pytest.fixture
def version_service():
    """Version Service mock."""
    service = MagicMock()
    service.get_version = AsyncMock(return_value="1.0.0")
    service.check_for_updates = AsyncMock(return_value=False)
    return service


@pytest.fixture
def mock_wireguard_service():
    """WireGuard Service mock for simple tests."""
    service = MagicMock()
    service.generate_keypair.return_value = ("mock_private_key", "mock_public_key")
    service.generate_server_config = AsyncMock(return_value="[Interface]\nPrivateKey = test\n")
    return service


@pytest.fixture
def mock_config_parser():
    """Config Parser mock for simple tests."""
    parser = MagicMock()
    parser.parse_server_config.return_value = {
        "name": "test-server",
        "listen_port": 51820,
    }
    return parser


@pytest.fixture
def mock_autofill_service():
    """AutoFill Service mock for simple tests."""
    service = MagicMock()
    service.get_server_defaults = AsyncMock(return_value={
        "listen_port": 51820,
        "address": "10.0.0.1",
        "ipv4_allowed_ips": ["10.0.0.0/24"],
        "ipv6_allowed_ips": ["fd00:1::/104"],
        "keepalive": 60,
    })
    return service


@pytest.fixture
def mock_audit_service():
    """Audit Service mock for simple tests."""
    service = MagicMock()
    service.log_action = AsyncMock()
    return service
