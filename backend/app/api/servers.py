from contextlib import suppress
from typing import Any
import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.exceptions import ValidationError, MultiFieldValidationError

logger = logging.getLogger(__name__)
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.security import get_current_user
from ..models.server import Server
from ..models.settings import GlobalSettings
from ..models.user import User
from ..schemas.server import ServerCreate, ServerResponse, ServerUpdate
from ..services.audit_logger import AuditService
from ..services.autofill import AutoFillService
from ..services.bounce_routing import BounceServerService
from ..services.config_parser import ConfigParser
from ..services.wireguard import WireGuardService
from ..utils.ip_validation import check_server_ip_subnet_conflicts

router = APIRouter()


async def sync_server_status(server: Server, wireguard_service: WireGuardService, db: AsyncSession) -> Server:
    """
    Sync server status with actual WireGuard interface state.
    
    This ensures that if a server is manually stopped outside the webapp,
    the database status reflects the actual state.
    
    Args:
        server: Server object
        wireguard_service: WireGuard service instance
        db: Database session
        
    Returns:
        Server object with synced status and interface field
    """
    # Check if interface exists by public key
    actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
    
    if actual_interface:
        # Interface exists, server is actually running
        server.interface = actual_interface
        if server.status != "running":
            # Database says stopped, but it's actually running - sync it
            server.status = "running"
            await db.commit()
    else:
        # Interface doesn't exist, server is actually stopped
        server.interface = None
        if server.status == "running":
            # Database says running, but it's actually stopped - sync it
            server.status = "stopped"
            await db.commit()
    
    return server


def populate_server_interface(server: Server, wireguard_service: WireGuardService) -> Server:
    """
    Dynamically populate the interface field for a running server.
    
    Args:
        server: Server object
        wireguard_service: WireGuard service instance
        
    Returns:
        Server object with interface field populated (if running)
    """
    if server.status == "running":
        actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
        server.interface = actual_interface
    return server


@router.get("/", response_model=list[ServerResponse])
@inject
async def list_servers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """List all WireGuard servers"""
    from sqlalchemy import func
    from ..models.peer import Peer
    
    # Query servers with peer count
    result = await db.execute(
        select(Server, func.count(Peer.id).label('peer_count'))
        .outerjoin(Peer, Server.id == Peer.server_id)
        .group_by(Server.id)
    )
    
    servers_with_counts = result.all()
    
    # Sync actual WireGuard status with database for all servers
    response_data = []
    for server, peer_count in servers_with_counts:
        await sync_server_status(server, wireguard_service, db)
        # Add peer_count as an attribute
        server.peer_count = peer_count
        response_data.append(server)
    
    return response_data


@router.get("/defaults/autofill", response_model=dict[str, Any])
@inject
async def get_server_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    autofill_service: AutoFillService = Depends(Provide[Container.autofill_service])
):
    """Get auto-filled defaults for creating a new server"""
    defaults = await autofill_service.get_server_defaults(db)
    return defaults


@router.get("/{server_id}", response_model=ServerResponse)
@inject
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """Get a specific server by ID"""
    from sqlalchemy import func
    from ..models.peer import Peer
    
    # Query server with peer count
    result = await db.execute(
        select(Server, func.count(Peer.id).label('peer_count'))
        .outerjoin(Peer, Server.id == Peer.server_id)
        .where(Server.id == server_id)
        .group_by(Server.id)
    )
    
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server, peer_count = row
    
    # Sync actual WireGuard status with database
    await sync_server_status(server, wireguard_service, db)
    
    # Add peer_count as an attribute
    server.peer_count = peer_count

    return server


@router.post("/", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_server(
    server_data: ServerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bounce_service: BounceServerService = Depends(Provide[Container.bounce_routing_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Create a new WireGuard server"""
    # Check for duplicate server name
    result = await db.execute(select(Server).where(Server.name == server_data.name))
    existing_server = result.scalar_one_or_none()
    if existing_server:
        raise ValidationError("name", f"Server name '{server_data.name}' is already in use")
    
    # Check for duplicate IP addresses and subnet conflicts
    if server_data.ipv4_address or server_data.ipv6_address:
        # Get all existing servers
        result = await db.execute(select(Server))
        existing_servers = result.scalars().all()
        
        # Check for exact duplicate IPs
        for existing_server in existing_servers:
            if server_data.ipv4_address and server_data.ipv4_address == existing_server.ipv4_address:
                raise ValidationError(
                    "ipv4_address",
                    f"IPv4 address already in use by server: {existing_server.name}"
                )
            if server_data.ipv6_address and server_data.ipv6_address == existing_server.ipv6_address:
                raise ValidationError(
                    "ipv6_address",
                    f"IPv6 address already in use by server: {existing_server.name}"
                )
        
        # Check for subnet conflicts (IPv4)
        if server_data.ipv4_address:
            existing_ipv4s = [(s.ipv4_address, s.name) for s in existing_servers if s.ipv4_address]
            is_valid, error_msg = check_server_ip_subnet_conflicts(server_data.ipv4_address, existing_ipv4s)
            if not is_valid:
                raise ValidationError("ipv4_address", error_msg)
        
        # Check for subnet conflicts (IPv6)
        if server_data.ipv6_address:
            existing_ipv6s = [(s.ipv6_address, s.name) for s in existing_servers if s.ipv6_address]
            is_valid, error_msg = check_server_ip_subnet_conflicts(server_data.ipv6_address, existing_ipv6s)
            if not is_valid:
                raise ValidationError("ipv6_address", error_msg)
    
    # Create server instance first (without committing)
    server = Server(**server_data.model_dump())
    db.add(server)
    
    # Validate bounce server if specified (before commit)
    if server_data.bounce_via_server_id:
        # Just check the bounce server exists and is valid
        result = await db.execute(select(Server).where(Server.id == server_data.bounce_via_server_id))
        bounce_server = result.scalar_one_or_none()
        if not bounce_server:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bounce server not found"
            )
        if not bounce_server.is_bounce_server:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified server is not configured as a bounce server"
            )
    
    await db.commit()
    await db.refresh(server)

    # Log audit event
    await audit_service.log_action(
        db, current_user, "CREATE", "server", server.id, server.name,
        {"endpoint": server.endpoint, "port": server.listen_port}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.SERVER_CREATED,
        "server",
        server.id,
        {"name": server.name, "interface": server.interface, "endpoint": server.endpoint},
        current_user.id
    )

    return server


@router.put("/{server_id}", response_model=ServerResponse)
@inject
async def update_server(
    server_id: int,
    server_data: ServerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    bounce_service: BounceServerService = Depends(Provide[Container.bounce_routing_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Update an existing WireGuard server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Get update data
    update_data = server_data.model_dump(exclude_unset=True)
    
    # Convert empty strings to None for IP addresses immediately
    if "ipv4_address" in update_data and update_data["ipv4_address"] == "":
        update_data["ipv4_address"] = None
    if "ipv6_address" in update_data and update_data["ipv6_address"] == "":
        update_data["ipv6_address"] = None
    
    # Check for duplicate server name if name is being updated
    if "name" in update_data:
        result = await db.execute(
            select(Server).where(
                Server.name == update_data["name"],
                Server.id != server_id
            )
        )
        existing_server = result.scalar_one_or_none()
        if existing_server:
            raise ValidationError("name", f"Server name '{update_data['name']}' is already in use")
    
    # Check for duplicate IP addresses and subnet conflicts (excluding current server)
    if "ipv4_address" in update_data or "ipv6_address" in update_data:
        # Get all existing servers except the one being updated
        result_all = await db.execute(select(Server).where(Server.id != server_id))
        existing_servers = result_all.scalars().all()
        
        ipv4 = update_data.get("ipv4_address")
        ipv6 = update_data.get("ipv6_address")
        
        # Check for exact duplicate IPs
        for existing_server in existing_servers:
            if ipv4 and ipv4 == existing_server.ipv4_address:
                raise ValidationError(
                    "ipv4_address",
                    f"IPv4 address already in use by server: {existing_server.name}"
                )
            if ipv6 and ipv6 == existing_server.ipv6_address:
                raise ValidationError(
                    "ipv6_address",
                    f"IPv6 address already in use by server: {existing_server.name}"
                )
        
        # Check for subnet conflicts (IPv4)
        if ipv4:
            existing_ipv4s = [(s.ipv4_address, s.name) for s in existing_servers if s.ipv4_address]
            is_valid, error_msg = check_server_ip_subnet_conflicts(ipv4, existing_ipv4s)
            if not is_valid:
                raise ValidationError("ipv4_address", error_msg)
        
        # Check for subnet conflicts (IPv6)
        if ipv6:
            existing_ipv6s = [(s.ipv6_address, s.name) for s in existing_servers if s.ipv6_address]
            is_valid, error_msg = check_server_ip_subnet_conflicts(ipv6, existing_ipv6s)
            if not is_valid:
                raise ValidationError("ipv6_address", error_msg)

    # Validate bounce server if being changed
    if server_data.bounce_via_server_id and server_data.bounce_via_server_id != server.bounce_via_server_id:
        is_valid = await bounce_service.validate_bounce_server(db, server_id, server_data.bounce_via_server_id)
        if not is_valid:
            raise ValidationError(
                "bounce_via_server_id",
                "Invalid bounce server configuration"
            )

    # Store old values for audit
    old_values = {
        "name": server.name,
        "endpoint": server.endpoint,
        "port": server.listen_port
    }
    
    # Validate that at least one IP address will remain after update
    final_ipv4 = server.ipv4_address if "ipv4_address" not in update_data else update_data.get("ipv4_address")
    final_ipv6 = server.ipv6_address if "ipv6_address" not in update_data else update_data.get("ipv6_address")
    
    if not final_ipv4 and not final_ipv6:
        raise MultiFieldValidationError({
            "ipv4_address": ["At least one IP address (IPv4 or IPv6) is required"],
            "ipv6_address": ["At least one IP address (IPv4 or IPv6) is required"]
        })

    # Update fields
    for field, value in update_data.items():
        setattr(server, field, value)

    await db.commit()
    await db.refresh(server)

    # Log audit event
    await audit_service.log_action(
        db, current_user, "UPDATE", "server", server.id, server.name,
        {"old": old_values, "new": update_data}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.SERVER_EDITED,
        "server",
        server.id,
        {"name": server.name, "interface": server.interface, "endpoint": server.endpoint, "changes": list(update_data.keys())},
        current_user.id
    )

    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Delete a WireGuard server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    # Stop the interface if running
    if server.status == "running":
        with suppress(Exception):
            wireguard_service.stop_interface(
                server.interface,
                ipv4_subnet=server.ipv4_address,
                ipv6_subnet=server.ipv6_address
            )

    server_name = server.name

    await db.delete(server)
    await db.commit()

    # Log audit event
    await audit_service.log_action(
        db, current_user, "DELETE", "server", server_id, server_name,
        {"endpoint": server.endpoint}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.SERVER_DELETED,
        "server",
        server_id,
        {"name": server_name},
        current_user.id
    )

    return None


@router.post("/{server_id}/start", response_model=ServerResponse)
@inject
async def start_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Start the WireGuard interface for a server"""
    logger.info(f"Received request to start server ID {server_id}")
    
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        logger.warning(f"Server ID {server_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    if server.status == "running":
        logger.warning(f"Server '{server.name}' (ID {server_id}) is already running")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server is already running"
        )

    try:
        logger.info(f"Starting server '{server.name}' (ID {server_id})")

        # Use a temporary interface name (wg0, wg1, etc.) for starting
        # The actual interface name will be determined by the OS
        temp_interface = f"wg{server.id}"
        
        # Start interface using wg commands directly
        success = await wireguard_service.start_interface(db, server.id, temp_interface)
        
        if not success:
            logger.error(f"Failed to start WireGuard interface for server '{server.name}'")
            raise Exception("Failed to start WireGuard interface")

        # Find the actual interface by querying WireGuard with public key
        actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
        if not actual_interface:
            logger.error(f"Could not find interface for server '{server.name}' after starting")
            raise Exception("Interface not found after starting")
        
        logger.info(f"Server '{server.name}' started successfully on interface '{actual_interface}'")
        
        # Update server status (don't store interface name)
        server.status = "running"
        server.needs_reload = False  # Clear needs_reload when starting (fresh start)
        await db.commit()
        await db.refresh(server)

        # Log audit event
        await audit_service.log_action(
            db, current_user, "START", "server", server.id, server.name,
            {"interface": actual_interface}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.SERVER_STARTED,
            "server",
            server.id,
            {"name": server.name, "interface": actual_interface},
            current_user.id
        )

        # Populate interface field for response
        populate_server_interface(server, wireguard_service)

        return server

    except Exception as e:
        logger.error(f"Error starting server '{server.name}' (ID {server_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start server: {e!s}"
        ) from e


@router.post("/{server_id}/stop", response_model=ServerResponse)
@inject
async def stop_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Stop the WireGuard interface for a server"""
    logger.info(f"Received request to stop server ID {server_id}")
    
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        logger.warning(f"Server ID {server_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    if server.status != "running":
        logger.warning(f"Server '{server.name}' (ID {server_id}) is not running")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server is not running"
        )

    try:
        logger.info(f"Stopping server '{server.name}' (ID {server_id})")
        
        # Find actual interface by public key
        actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
        if not actual_interface:
            # Fallback to stored interface name
            actual_interface = server.interface
        
        wireguard_service.stop_interface(
            actual_interface,
            ipv4_subnet=server.ipv4_address,
            ipv6_subnet=server.ipv6_address
        )

        # Update server status and clear interface (allows reuse)
        server.status = "stopped"
        server.interface = None
        server.needs_reload = False  # Clear needs_reload when stopping
        await db.commit()
        await db.refresh(server)

        logger.info(f"Server '{server.name}' stopped successfully")

        # Log audit event
        await audit_service.log_action(
            db, current_user, "STOP", "server", server.id, server.name,
            {"interface": actual_interface}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.SERVER_STOPPED,
            "server",
            server.id,
            {"name": server.name, "interface": actual_interface},
            current_user.id
        )

        return server

    except Exception as e:
        logger.error(f"Error stopping server '{server.name}' (ID {server_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop server: {e!s}"
        ) from e


@router.post("/{server_id}/reload", response_model=ServerResponse)
@inject
async def reload_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Reload the WireGuard configuration for a running server"""
    logger.info(f"Received request to reload server ID {server_id}")
    
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        logger.warning(f"Server ID {server_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    try:
        logger.info(f"Reloading server '{server.name}' (ID {server_id})")

        # Find actual interface by public key
        actual_interface = wireguard_service.find_interface_by_public_key(server.public_key)
        if not actual_interface:
            logger.error(f"Server '{server.name}' is not running (no interface found)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server is not running"
            )
        
        # Reload interface using wg commands directly (remove and re-add peers)
        success = await wireguard_service.reload_interface(db, server.id, actual_interface)
        if not success:
            raise Exception("Failed to reload WireGuard interface")
        
        # Clear needs_reload flag
        server.needs_reload = False
        await db.commit()
        await db.refresh(server)
        
        # Ensure server.name is loaded (force attribute access)
        server_name = str(server.name) if server.name else f"Server #{server.id}"

        logger.info(f"Server '{server_name}' reloaded successfully on interface '{actual_interface}'")

        # Log audit event
        await audit_service.log_action(
            db, current_user, "RELOAD", "server", server.id, server_name,
            {"interface": actual_interface}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.SERVER_RELOADED,
            "server",
            server.id,
            {"name": server_name, "interface": actual_interface},
            current_user.id
        )

        # Populate interface field for response
        populate_server_interface(server, wireguard_service)

        return server

    except Exception as e:
        logger.error(f"Error reloading server '{server.name}' (ID {server_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload server: {e!s}"
        ) from e


@router.get("/{server_id}/config", response_class=PlainTextResponse)
@inject
async def export_server_config(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """Export the WireGuard configuration file for a server"""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    try:
        config_content = await wireguard_service.generate_server_config(db, server.id)
        return config_content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate config: {e!s}"
        ) from e


@router.post("/import", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
@inject
async def import_server_config(
    config_file: UploadFile,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    config_parser: ConfigParser = Depends(Provide[Container.config_parser_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Import a WireGuard server from a configuration file"""
    try:
        # Read config file
        config_content = await config_file.read()
        config_text = config_content.decode('utf-8')

        # Parse config
        server_data = config_parser.parse_server_config(config_text)

        # Create server
        server = Server(**server_data)
        db.add(server)
        await db.commit()
        await db.refresh(server)

        # Log audit event
        await audit_service.log_action(
            db, current_user, "IMPORT", "server", server.id, server.name,
            {"filename": config_file.filename}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.SERVER_CREATED,
            "server",
            server.id,
            {"name": server.name, "imported": True},
            current_user.id
        )

        return server

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config file: {e!s}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import config: {e!s}"
        ) from e
