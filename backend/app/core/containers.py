"""Dependency Injection Container."""

from dependency_injector import containers, providers

from app.plugins.manager import PluginManager
from app.services.audit_logger import AuditService
from app.services.autofill import AutoFillService
from app.services.backup_cleanup_service import BackupCleanupService
from app.services.backup_service import BackupService
from app.services.bounce_routing import BounceServerService
from app.services.config_parser import ConfigParser
from app.services.dns_hierarchy import DNSHierarchyService
from app.services.firewall import FirewallService
from app.services.health_monitor_service import HealthMonitorService
from app.services.integration_service import IntegrationService
from app.services.interface_monitor import InterfaceMonitorService
from app.services.ip_management import IPManagementService
from app.services.metrics_collector import MetricsCollectorService
from app.services.metrics_monitor_service import MetricsMonitorService
from app.services.migration import MigrationService
from app.services.notification_service import NotificationService
from app.services.periodic_backup_service import PeriodicBackupService
from app.services.settings_service import SettingsService
from app.services.traffic_threshold_service import TrafficThresholdService
from app.services.version_service import VersionService
from app.services.wireguard import WireGuardService


class Container(containers.DeclarativeContainer):
    """Application DI Container."""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=["app.api"],
        modules=[
            "app.api.auth",
            "app.api.servers",
            "app.api.peers",
            "app.api.settings",
            "app.api.audit",
            "app.api.backup",
            "app.api.version",
            "app.api.integrations",
            "app.api.notifications",
            "app.api.plugins",
            "app.api.traffic_triggers",
        ],
    )

    # Core Services - No dependencies
    ip_management_service = providers.Singleton(IPManagementService)

    dns_hierarchy_service = providers.Singleton(DNSHierarchyService)

    config_parser_service = providers.Singleton(ConfigParser)

    audit_service = providers.Singleton(AuditService)

    bounce_routing_service = providers.Singleton(BounceServerService)

    version_service = providers.Singleton(VersionService)

    notification_service = providers.Singleton(NotificationService)
    
    metrics_collector_service = providers.Singleton(MetricsCollectorService)
    
    traffic_threshold_service = providers.Singleton(TrafficThresholdService)
    
    health_monitor_service = providers.Singleton(
        HealthMonitorService,
        check_interval_seconds=30,  # Check every 30 seconds
    )
    
    settings_service = providers.Singleton(SettingsService)
    
    firewall_service = providers.Singleton(FirewallService)
    
    # MetricsMonitorService depends on other services
    metrics_monitor_service = providers.Singleton(
        MetricsMonitorService,
        metrics_collector=metrics_collector_service,
        traffic_threshold_service=traffic_threshold_service,
        settings_service=settings_service,
    )
    
    # BackupService depends on SettingsService
    backup_service = providers.Singleton(
        BackupService,
        settings_service=settings_service,
    )

    # Services with dependencies
    wireguard_service = providers.Singleton(
        WireGuardService,
        dns_hierarchy_service=dns_hierarchy_service,
        firewall_service=firewall_service,
    )
    
    # Plugin Manager (defined before integration_service since it depends on it)
    plugin_manager = providers.Singleton(
        PluginManager,
        db_session_factory=providers.Callable(
            lambda: __import__('app.core.database', fromlist=['AsyncSessionLocal']).AsyncSessionLocal
        ),
    )
    
    integration_service = providers.Singleton(
        IntegrationService,
        notification_service=notification_service,
        plugin_manager=plugin_manager,
    )

    autofill_service = providers.Singleton(
        AutoFillService,
        ip_management_service=ip_management_service,
        dns_hierarchy_service=dns_hierarchy_service,
        wireguard_service=wireguard_service,
    )

    migration_service = providers.Singleton(
        MigrationService,
        ip_management_service=ip_management_service,
        dns_hierarchy_service=dns_hierarchy_service,
        audit_service=audit_service,
    )

    interface_monitor_service = providers.Singleton(
        InterfaceMonitorService,
        wireguard_service=wireguard_service,
        check_interval_seconds=10,  # Check every 10 seconds
    )

    backup_cleanup_service = providers.Singleton(
        BackupCleanupService,
        settings_service=settings_service,
        check_interval_hours=24,  # Check daily
    )

    periodic_backup_service = providers.Singleton(
        PeriodicBackupService,
        backup_service=backup_service,
        settings_service=settings_service,
    )

