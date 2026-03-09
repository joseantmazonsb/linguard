from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config_loader import config_loader
from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import get_password_hash
from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings
from ..models.user import User
from ..schemas.setup import (
    ConfigureDatabase,
    ConfigureGlobals,
    CreatePeer,
    CreateServer,
    InitializeSetup,
    SetupComplete,
    SetupStatus,
    UpdateSetupProgress,
)
from ..services.audit_logger import AuditService
from ..services.autofill import AutoFillService
from ..services.backup_service import BackupService
from ..services.integration_service import IntegrationService
from ..services.wireguard import WireGuardService
from ..utils.database_manager import DatabaseManager
from ..utils.wireguard_detect import detect_wireguard_binaries, get_wireguard_paths, verify_wireguard_binary

router = APIRouter()


@router.get("/status", response_model=SetupStatus)
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Check if initial setup has been completed."""
    # Check if any users exist
    result = await db.execute(select(User))
    users = result.scalars().all()
    has_users = len(users) > 0

    # Check setup_completed flag in global settings
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    # If setup_completed flag is set, setup is done
    if settings and settings.setup_completed:
        return SetupStatus(
            setup_completed=True, requires_setup=False, current_step=None
        )

    # Otherwise, setup is required
    return SetupStatus(
        setup_completed=False,
        requires_setup=True,
        current_step=settings.setup_current_step if settings else None,
    )


@router.post("/configure-database")
async def configure_database_backend(config_data: ConfigureDatabase):
    """Configure database backend (first step in setup)."""
    import os
    
    try:
        print(f"[SETUP] Received database config request")
        print(f"[SETUP] Database type: {config_data.database_type.value}")
        print(f"[SETUP] Database URL (raw): {config_data.database_url}")
        
        # Handle SQLite path conversion
        db_url = config_data.database_url
        if config_data.database_type.value == "sqlite":
            # If it's a relative path, convert it to absolute
            if not db_url.startswith("sqlite"):
                print(f"[SETUP] Converting relative path to absolute SQLite URL")
                # Remove leading './' if present
                path = db_url.lstrip("./")
                print(f"[SETUP] Cleaned path: {path}")
                # Get absolute path
                abs_path = os.path.abspath(os.path.join(os.getcwd(), path))
                print(f"[SETUP] Absolute path: {abs_path}")
                # Ensure directory exists
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                print(f"[SETUP] Directory created/verified")
                # Format as SQLite URL with aiosqlite driver
                db_url = f"sqlite+aiosqlite:///{abs_path}"
                print(f"[SETUP] Final SQLite URL: {db_url}")
        
        print(f"[SETUP] Saving config to file...")
        # Save database config to linguard.config.json
        config_loader.set_database(
            db_type=config_data.database_type.value, db_url=db_url
        )
        print(f"[SETUP] Config saved successfully")

        return {
            "success": True,
            "database_type": config_data.database_type.value,
            "database_url": db_url,
            "message": f"{config_data.database_type.value.upper()} database configured successfully.",
            "requires_restart": False,
        }
    except Exception as e:
        print(f"[SETUP ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure database: {str(e)}"
        )


@router.get("/detect-wireguard")
async def detect_wireguard():
    """Detect WireGuard binaries on the system."""
    try:
        detected = detect_wireguard_binaries()
        paths = get_wireguard_paths()
        
        # Verify the detected binaries
        wg_verified = verify_wireguard_binary(paths['wg']) if paths['wg'] else False
        wg_quick_verified = verify_wireguard_binary(paths['wg-quick']) if paths['wg-quick'] else False
        
        return {
            "success": True,
            "detected": {
                "wg": detected['wg'],
                "wg-quick": detected['wg-quick']
            },
            "recommended": {
                "wg": paths['wg'],
                "wg-quick": paths['wg-quick']
            },
            "verified": {
                "wg": wg_verified,
                "wg-quick": wg_quick_verified
            },
            "message": (
                "WireGuard binaries detected" if detected['wg'] and detected['wg-quick']
                else "WireGuard binaries not detected, using default paths"
            )
        }
    except Exception as e:
        return {
            "success": False,
            "detected": {"wg": None, "wg-quick": None},
            "recommended": {"wg": "/usr/bin/wg", "wg-quick": "/usr/bin/wg-quick"},
            "verified": {"wg": False, "wg-quick": False},
            "message": f"Error detecting WireGuard binaries: {str(e)}"
        }


@router.post("/initialize", response_model=dict)
async def initialize_setup(
    setup_data: InitializeSetup, db: AsyncSession = Depends(get_db)
):
    """Create the first admin account."""
    # Check if any users already exist
    result = await db.execute(select(User))
    existing_users = result.scalars().all()

    if existing_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users already exist. Setup cannot be initialized again.",
        )

    # Check if username is taken
    result = await db.execute(select(User).where(User.username == setup_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
        )

    # Check if email is taken
    result = await db.execute(select(User).where(User.email == setup_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create first admin user
    user = User(
        username=setup_data.username,
        email=setup_data.email,
        hashed_password=get_password_hash(setup_data.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Update setup progress - record database type from config
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()
    if not settings:
        # Create minimal settings record with database type
        settings = GlobalSettings(
            database_type=config_loader.get_database_type(),
            setup_current_step="globals",
            # Temporary required field values (will be set in configure-globals)
            secret_key="temporary-key-will-be-replaced",
            backup_dir="/tmp/linguard-backups",
            log_path="./linguard.log",
            # Traffic monitoring defaults
            metrics_collection_interval_minutes=5,
            metrics_retention_days=90,
            metrics_global_notifications_per_hour=50,
        )
        db.add(settings)
    else:
        settings.database_type = config_loader.get_database_type()
        settings.setup_current_step = "globals"
    await db.commit()

    return {"success": True, "user_id": user.id, "username": user.username}


@router.post("/configure-globals")
async def configure_global_settings(
    config_data: ConfigureGlobals, db: AsyncSession = Depends(get_db)
):
    """Configure global settings during setup."""
    # Get or create global settings
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        settings = GlobalSettings(
            # DNS Configuration
            dns_primary=config_data.dns_primary,
            dns_secondary=config_data.dns_secondary,
            # Security
            secret_key=config_data.secret_key,
            algorithm=config_data.algorithm,
            access_token_expire_minutes=config_data.access_token_expire_minutes,
            disable_auth=config_data.disable_auth,
            # Logging
            log_level=config_data.log_level,
            log_path=config_data.log_path,
            # Backup
            backup_dir=config_data.backup_dir,
            backup_retention_days=config_data.backup_retention_days,
            backup_auto_cleanup_enabled=config_data.backup_auto_cleanup_enabled,
            backup_periodic_enabled=config_data.backup_periodic_enabled,
            backup_schedule_frequency=config_data.backup_schedule_frequency,
            backup_schedule_hour=config_data.backup_schedule_hour,
            backup_schedule_minute=config_data.backup_schedule_minute,
            # Traffic Monitoring
            metrics_collection_interval_minutes=5,
            metrics_retention_days=90,
            metrics_global_notifications_per_hour=50,
            # Database type from config file
            database_type=config_loader.get_database_type(),
            # Setup state
            setup_completed=False,
            setup_current_step="server",  # Next step
        )
        db.add(settings)
    else:
        # Update all settings
        settings.dns_primary = config_data.dns_primary
        settings.dns_secondary = config_data.dns_secondary
        settings.secret_key = config_data.secret_key
        settings.algorithm = config_data.algorithm
        settings.access_token_expire_minutes = config_data.access_token_expire_minutes
        settings.disable_auth = config_data.disable_auth
        settings.log_level = config_data.log_level
        settings.log_path = config_data.log_path
        settings.backup_dir = config_data.backup_dir
        settings.backup_retention_days = config_data.backup_retention_days
        settings.backup_auto_cleanup_enabled = config_data.backup_auto_cleanup_enabled
        settings.backup_periodic_enabled = config_data.backup_periodic_enabled
        settings.backup_schedule_frequency = config_data.backup_schedule_frequency
        settings.backup_schedule_hour = config_data.backup_schedule_hour
        settings.backup_schedule_minute = config_data.backup_schedule_minute
        settings.database_type = config_loader.get_database_type()
        settings.setup_current_step = "server"

    await db.commit()
    await db.refresh(settings)

    return {"success": True, "settings_id": settings.id}


@router.post("/update-progress")
async def update_setup_progress(
    progress_data: UpdateSetupProgress, db: AsyncSession = Depends(get_db)
):
    """Update the current setup step for resume functionality."""
    # Get or create global settings
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        settings = GlobalSettings(setup_current_step=progress_data.current_step)
        db.add(settings)
    else:
        settings.setup_current_step = progress_data.current_step

    await db.commit()
    return {"success": True, "current_step": progress_data.current_step}


@router.post("/create-server", response_model=dict)
@inject
async def create_first_server(
    server_data: CreateServer,
    db: AsyncSession = Depends(get_db),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
):
    """Create the first WireGuard server during setup."""
    # Generate keys
    private_key, public_key = wireguard_service.generate_keypair()

    # Parse DNS if provided
    dns_primary = None
    dns_secondary = None
    if server_data.dns:
        dns_servers = [dns.strip() for dns in server_data.dns.split(",")]
        dns_primary = dns_servers[0] if len(dns_servers) > 0 else None
        dns_secondary = dns_servers[1] if len(dns_servers) > 1 else None

    # Create server
    server = Server(
        name=server_data.name,
        interface="wg0",  # Default interface name for first server
        endpoint=server_data.endpoint,
        listen_port=server_data.listen_port,
        private_key=private_key,
        public_key=public_key,
        ipv4_address=server_data.ipv4_address,
        ipv6_address=server_data.ipv6_address,
        dns_primary=dns_primary,
        dns_secondary=dns_secondary,
    )
    db.add(server)
    await db.flush()
    await db.refresh(server)

    # Update setup progress to server step completed
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()
    if settings:
        settings.setup_current_step = "peer"
        await db.commit()

    return {
        "success": True,
        "server_id": server.id,
        "server_name": server.name,
        "public_key": server.public_key,
    }


@router.post("/create-peer", response_model=dict)
@inject
async def create_first_peer(
    peer_data: CreatePeer,
    db: AsyncSession = Depends(get_db),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    autofill_service: AutoFillService = Depends(Provide[Container.autofill_service]),
):
    """Create the first peer during setup."""
    # Verify server exists
    result = await db.execute(select(Server).where(Server.id == peer_data.server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
        )

    # Generate keys
    private_key, public_key = wireguard_service.generate_keypair()

    # Generate preshared key if requested
    preshared_key = (
        wireguard_service.generate_preshared_key() if peer_data.preshared_key else None
    )

    # Auto-fill IPs if not provided
    ipv4_address = peer_data.ipv4_address
    ipv6_address = peer_data.ipv6_address

    if not ipv4_address or not ipv6_address:
        autofill_data = await autofill_service.get_peer_defaults(
            db=db, server_id=peer_data.server_id
        )
        if not ipv4_address:
            ipv4_address = autofill_data.get("ipv4_address")
        if not ipv6_address:
            ipv6_address = autofill_data.get("ipv6_address")

    # Parse DNS if provided
    dns_primary = None
    dns_secondary = None
    if peer_data.dns:
        dns_servers = [dns.strip() for dns in peer_data.dns.split(",")]
        dns_primary = dns_servers[0] if len(dns_servers) > 0 else None
        dns_secondary = dns_servers[1] if len(dns_servers) > 1 else None

    # Create peer
    peer = Peer(
        server_id=peer_data.server_id,
        name=peer_data.name,
        private_key=private_key,
        public_key=public_key,
        preshared_key=preshared_key,
        ipv4_address=ipv4_address,
        ipv6_address=ipv6_address,
        dns_primary=dns_primary,
        dns_secondary=dns_secondary,
    )
    db.add(peer)
    await db.flush()
    await db.refresh(peer)

    # Update setup progress to peer step completed
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()
    if settings:
        settings.setup_current_step = "complete"
        await db.commit()

    return {
        "success": True,
        "peer_id": peer.id,
        "peer_name": peer.name,
        "public_key": peer.public_key,
        "ipv4_address": peer.ipv4_address,
        "ipv6_address": peer.ipv6_address,
    }


@router.post("/complete", response_model=SetupComplete)
@inject
async def complete_setup(
    db: AsyncSession = Depends(get_db),
    backup_service: BackupService = Depends(Provide[Container.backup_service]),
    integration_service: IntegrationService = Depends(Provide[Container.integration_service]),
):
    """Mark setup as complete and create initial backup."""
    # Get global settings
    result = await db.execute(select(GlobalSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Global settings not configured. Please configure settings first.",
        )

    # Verify at least one user exists
    result = await db.execute(select(User))
    users = result.scalars().all()
    if not users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No admin user created. Please initialize setup first.",
        )

    # Mark setup as completed
    settings.setup_completed = True
    settings.setup_current_step = None  # Clear current step when setup is done
    await db.commit()

    # Create default In-App Notifications integration
    # Note: Also handled in startup event (main.py) for existing installations
    try:
        from sqlalchemy import select as sql_select
        from ..models.integration import Integration
        
        # Check if it already exists (shouldn't, but be safe)
        result = await db.execute(
            sql_select(Integration).where(Integration.name == "In-App Notifications")
        )
        existing = result.scalar_one_or_none()
        
        if not existing:
            await integration_service.create_integration(
                db=db,
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
    except Exception as e:
        print(f"Warning: Failed to create default in-app notifications integration: {e}")

    # Create initial backup
    backup_id = None
    try:
        backup = await backup_service.create_backup(
            db=db, description="Initial setup backup - auto-generated", user_id=users[0].id
        )
        backup_id = backup.id
    except Exception as e:
        # Don't fail setup if backup fails, just log it
        print(f"Warning: Failed to create initial backup: {e}")

    # Log setup completion event
    await event_bus.publish(
        EventType.SETTINGS_UPDATED,
        "settings",
        settings.id,
        {"action": "setup_completed"},
        users[0].id if users else None,
    )

    return SetupComplete(
        success=True,
        message="Setup completed successfully",
        backup_id=backup_id,
    )
