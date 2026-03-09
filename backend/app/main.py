from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .api import (
    audit,
    auth,
    backup,
    import_config,
    integrations,
    logs,
    metrics,
    notifications,
    peers,
    plugins,
    servers,
    traffic_triggers,
    ws,
)
from .api import settings as settings_api
from .api import setup, utils, version
from .core.config import settings
from .core.containers import Container
from .core.database import Base, engine
from .core.events import EventType, event_bus
from .core.exceptions import (
    ValidationError,
    MultiFieldValidationError,
    validation_exception_handler,
    custom_validation_error_handler,
    custom_multi_field_validation_error_handler,
)

# Create logger for startup messages
logger = logging.getLogger("app.main")

def configure_logging(log_path: str | None = None):
    """Configure logging with optional file output."""
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure formatter
    formatter = logging.Formatter('%(levelname)s:     %(name)s - %(message)s')
    
    if log_path:
        # Resolve relative paths to absolute
        if not os.path.isabs(log_path):
            log_path = os.path.abspath(log_path)
        
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Add file handler
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        print(f"[STARTUP] Logging to file: {log_path}")
    else:
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        print("[STARTUP] Logging to console (stdout)")
    
    # Set log level
    root_logger.setLevel(logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)


# Initial logging configuration (will be updated during startup)
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Configure logging from database settings
    async_session = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        from sqlalchemy import select
        from .models.settings import GlobalSettings
        
        result = await async_session.execute(select(GlobalSettings))
        global_settings = result.scalar_one_or_none()
        
        if global_settings and global_settings.log_path:
            configure_logging(global_settings.log_path)
            print(f"[STARTUP] Logging configured from database: {global_settings.log_path}")
    except Exception as e:
        print(f"[STARTUP] Warning: Could not configure logging from database: {e}")
    finally:
        await async_session.close()

    # Connect event bus (in-memory mode)
    await event_bus.connect()

    # Get integration service from container
    integration_service = app.container.integration_service()
    
    # Ensure default "In-App Notifications" integration exists
    async_session = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        from sqlalchemy import select
        from .models.integration import Integration
        from .models.settings import GlobalSettings
        
        # Only create if setup is complete
        result = await async_session.execute(select(GlobalSettings))
        settings = result.scalar_one_or_none()
        
        if settings and settings.setup_completed:
            # Check if In-App Notifications integration exists
            result = await async_session.execute(
                select(Integration).where(Integration.name == "In-App Notifications")
            )
            existing_integration = result.scalar_one_or_none()
            
            if not existing_integration:
                logger.info("Creating default In-App Notifications integration...")
                await integration_service.create_integration(
                    db=async_session,
                    name="In-App Notifications",
                    type="notification",
                    config={},
                    events_subscribed=[
                        EventType.SERVER_RELOADED.value,
                        EventType.PEER_CONNECTED.value,
                        EventType.PEER_DISCONNECTED.value,
                    ],
                    description="Built-in notification system for important events",
                    enabled=True
                )
                logger.info("Default In-App Notifications integration created successfully")
            else:
                logger.info("In-App Notifications integration already exists")
        else:
            logger.info("Setup not complete - skipping default integration creation")
    except Exception as e:
        logger.warning(f"Failed to check/create default integration: {e}")
    finally:
        await async_session.close()

    # Subscribe to all events and dispatch to integrations
    async def handle_event(event_data: dict):
        """Handle events by dispatching them to integrations."""
        try:
            # Create a new async session with proper binding
            async_session = AsyncSession(bind=engine, expire_on_commit=False)
            try:
                event_type = EventType(event_data["event_type"])
                await integration_service.dispatch_event_to_integrations(
                    async_session, event_type, event_data
                )
                await async_session.commit()
            finally:
                await async_session.close()
        except Exception as e:
            print(f"Error handling event {event_data.get('event_type')}: {e}")
            import traceback

            traceback.print_exc()

    # Subscribe handler to all event types
    for event_type in EventType:
        event_bus.subscribe(event_type, handle_event)
    
    # Subscribe to server status events and broadcast via WebSocket
    async def handle_server_status_change(event_data: dict):
        """Broadcast server status changes to WebSocket clients."""
        try:
            from .api.ws import broadcast_server_status_change
            
            event_type = event_data.get("event_type")
            payload = event_data.get("payload", {})
            
            await broadcast_server_status_change({
                "server_id": event_data.get("source_id"),
                "name": payload.get("name"),
                "status": payload.get("status"),
                "event_type": event_type,
                "detected": payload.get("detected", False)
            })
        except Exception as e:
            print(f"Error broadcasting server status change: {e}")
    
    # Subscribe to server status events
    event_bus.subscribe(EventType.SERVER_STARTED, handle_server_status_change)
    event_bus.subscribe(EventType.SERVER_STOPPED, handle_server_status_change)
    event_bus.subscribe(EventType.SERVER_RELOADED, handle_server_status_change)
    
    # Start background update checker
    from .services.update_checker import UpdateCheckerService
    
    version_service = app.container.version_service()
    notification_service = app.container.notification_service()
    
    update_checker = UpdateCheckerService(
        version_service=version_service,
        notification_service=notification_service,
        check_interval_hours=6
    )
    await update_checker.start()
    
    # Start health monitor
    health_monitor = app.container.health_monitor_service()
    await health_monitor.start()
    
    # Start interface monitor
    interface_monitor = app.container.interface_monitor_service()
    await interface_monitor.start()
    
    # Start backup cleanup service
    backup_cleanup = app.container.backup_cleanup_service()
    await backup_cleanup.start()
    
    # Start periodic backup service
    periodic_backup = app.container.periodic_backup_service()
    await periodic_backup.start()
    
    # Start metrics monitor service
    metrics_monitor = app.container.metrics_monitor_service()
    await metrics_monitor.start()
    
    # Initialize plugin system
    plugin_manager = app.container.plugin_manager()
    async_session = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        from sqlalchemy import select
        from .models.settings import GlobalSettings
        
        # Get plugins directory from settings
        result = await async_session.execute(select(GlobalSettings))
        global_settings = result.scalar_one_or_none()
        
        if global_settings and global_settings.setup_completed:
            # Get plugins directory from settings
            plugins_dir = global_settings.plugins_directory or "./plugins"
            
            # Discover plugins from directory
            newly_discovered = await plugin_manager.discover_plugins(plugins_dir, async_session)
            await async_session.commit()
            
            if newly_discovered > 0:
                logger.info(f"Discovered {newly_discovered} new plugin(s)")
            
            # Load enabled plugins
            await plugin_manager.load_enabled_plugins(async_session)
            loaded_count = plugin_manager.loaded_count()
            logger.info(f"Plugin system initialized. Loaded {loaded_count} plugin(s)")
        else:
            logger.info("Setup not complete - skipping plugin initialization")
    except Exception as e:
        logger.warning(f"Failed to initialize plugin system: {e}")
    finally:
        await async_session.close()

    # Auto-start servers marked with autostart=True
    async_session = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        from sqlalchemy import select
        from .models.server import Server
        from .models.settings import GlobalSettings
        
        # Only auto-start if setup is complete
        result = await async_session.execute(select(GlobalSettings))
        global_settings = result.scalar_one_or_none()
        
        if global_settings and global_settings.setup_completed:
            # Get all servers with autostart enabled
            result = await async_session.execute(
                select(Server).where(Server.autostart == True)
            )
            autostart_servers = result.scalars().all()
            
            if autostart_servers:
                logger.info(f"Auto-starting {len(autostart_servers)} server(s)...")
                
                # Get wireguard service from container
                wireguard_service = app.container.wireguard_service()
                
                for server in autostart_servers:
                    try:
                        # Skip if already running
                        if server.status == "running":
                            logger.info(f"Server '{server.name}' already running - skipping")
                            continue
                        
                        logger.info(f"Auto-starting server: {server.name}")
                        
                        # Use a temporary interface name (wg0, wg1, etc.) for starting
                        temp_interface = f"wg{server.id}"
                        
                        # Start interface using wg commands directly
                        success = await wireguard_service.start_interface(async_session, server.id, temp_interface)
                        
                        if not success:
                            logger.error(f"✗ Failed to start interface for '{server.name}'")
                            await async_session.rollback()
                            continue
                        
                        # Update server status
                        server.status = "running"
                        await async_session.commit()
                        await async_session.refresh(server)
                        
                        # Find actual interface name for logging
                        actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
                        interface_info = f" on interface '{actual_interface}'" if actual_interface else ""
                        logger.info(f"✓ Server '{server.name}' started successfully{interface_info}")
                    except Exception as e:
                        logger.error(f"✗ Failed to auto-start server '{server.name}': {e}")
                        await async_session.rollback()
                
                logger.info("Auto-start completed")
            else:
                logger.info("No servers configured for auto-start")
        else:
            logger.info("Setup not complete - skipping server auto-start")
    except Exception as e:
        logger.warning(f"Failed to auto-start servers: {e}")
    finally:
        await async_session.close()

    yield

    # Shutdown
    # Unload all plugins
    try:
        plugin_manager = app.container.plugin_manager()
        await plugin_manager.unload_all()
        logger.info("Plugins unloaded")
    except Exception as e:
        logger.warning(f"Error unloading plugins: {e}")
    
    await metrics_monitor.stop()
    await periodic_backup.stop()
    await backup_cleanup.stop()
    await interface_monitor.stop()
    await health_monitor.stop()
    await update_checker.stop()
    await event_bus.disconnect()


# Create DI container
container = Container()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# Register custom exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ValidationError, custom_validation_error_handler)
app.add_exception_handler(MultiFieldValidationError, custom_multi_field_validation_error_handler)

# Wire the container to enable dependency injection
container.wire(packages=["app.api"])

# Store container in app state for access in tests
app.container = container

# CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["auth"])
app.include_router(
    setup.router, prefix=f"{settings.API_V1_PREFIX}/setup", tags=["setup"]
)
app.include_router(
    servers.router, prefix=f"{settings.API_V1_PREFIX}/servers", tags=["servers"]
)
app.include_router(
    peers.router, prefix=f"{settings.API_V1_PREFIX}/peers", tags=["peers"]
)
app.include_router(
    settings_api.router, prefix=f"{settings.API_V1_PREFIX}/settings", tags=["settings"]
)
app.include_router(
    audit.router, prefix=f"{settings.API_V1_PREFIX}/audit", tags=["audit"]
)
app.include_router(
    backup.router, prefix=f"{settings.API_V1_PREFIX}/backups", tags=["backups"]
)
app.include_router(
    version.router, prefix=f"{settings.API_V1_PREFIX}/version", tags=["version"]
)
app.include_router(
    integrations.router,
    prefix=f"{settings.API_V1_PREFIX}/integrations",
    tags=["integrations"],
)
app.include_router(
    notifications.router,
    prefix=f"{settings.API_V1_PREFIX}/notifications",
    tags=["notifications"],
)
app.include_router(
    plugins.router,
    prefix=f"{settings.API_V1_PREFIX}/plugins",
    tags=["plugins"],
)
app.include_router(logs.router, prefix=f"{settings.API_V1_PREFIX}/logs", tags=["logs"])
app.include_router(
    import_config.router, prefix=f"{settings.API_V1_PREFIX}/import", tags=["import"]
)
app.include_router(
    utils.router, prefix=f"{settings.API_V1_PREFIX}/utils", tags=["utilities"]
)
app.include_router(
    metrics.router, prefix=f"{settings.API_V1_PREFIX}/metrics", tags=["metrics"]
)
app.include_router(
    traffic_triggers.router,
    prefix=f"{settings.API_V1_PREFIX}/traffic-triggers",
    tags=["traffic-triggers"],
)
app.include_router(ws.router, tags=["websocket"])


@app.get("/")
async def root():
    return {"message": "Linguard API", "version": settings.APP_VERSION}


@app.get("/health")
async def health():
    """
    Health check endpoint that tests database, WireGuard, IP forwarding, and firewall accessibility.
    Returns overall status and details about each component.
    
    Uses the HealthMonitorService for consistent health checks across HTTP and WebSocket.
    """
    from .services.health_monitor_service import HealthMonitorService
    
    # Create a temporary instance to perform the health check
    health_monitor = HealthMonitorService()
    return await health_monitor.check_health()
