from io import BytesIO
from typing import Any

import qrcode
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.containers import Container
from ..core.database import get_db
from ..core.events import EventType, event_bus
from ..core.exceptions import ValidationError, MultiFieldValidationError
from ..core.security import get_current_user
from ..models.peer import Peer
from ..models.server import Server
from ..models.settings import GlobalSettings
from ..models.user import User
from ..schemas.peer import PeerCreate, PeerMigrationRequest, PeerResponse, PeerUpdate
from ..services.audit_logger import AuditService
from ..services.autofill import AutoFillService
from ..services.config_parser import ConfigParser
from ..services.migration import MigrationService
from ..services.wireguard import WireGuardService
from ..utils.ip_validation import is_ip_in_subnet
from ..utils.wireguard_detect import detect_wireguard_binaries

router = APIRouter()


@router.get("/", response_model=list[PeerResponse])
async def list_peers(
    server_id: int | None = Query(None, description="Filter by server ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List peers with pagination, optionally filtered by server"""
    query = select(Peer).order_by(Peer.id)
    if server_id:
        query = query.where(Peer.server_id == server_id)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    peers = result.scalars().all()
    return peers


@router.get("/count", response_model=dict)
async def count_peers(
    server_id: int | None = Query(None, description="Filter by server ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get total count of peers, optionally filtered by server"""
    query = select(func.count(Peer.id))
    if server_id:
        query = query.where(Peer.server_id == server_id)
    
    result = await db.execute(query)
    count = result.scalar()
    
    return {"total": count}


@router.get("/{peer_id}", response_model=PeerResponse)
async def get_peer(
    peer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific peer by ID"""
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    return peer


@router.get("/defaults/{server_id}", response_model=dict[str, Any])
@inject
async def get_peer_defaults(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    autofill_service: AutoFillService = Depends(Provide[Container.autofill_service])
):
    """Get auto-filled defaults for creating a new peer on a specific server"""
    # Verify server exists
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    defaults = await autofill_service.get_peer_defaults(db, server_id)
    return defaults


@router.post("/", response_model=PeerResponse, status_code=status.HTTP_201_CREATED)
@inject
async def create_peer(
    peer_data: PeerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Create a new WireGuard peer"""
    # Check WireGuard is available
    wg_paths = detect_wireguard_binaries()
    if not wg_paths.get("wg"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="WireGuard is not installed or not found on this system. Install WireGuard before creating peers."
        )

    # Verify server exists
    result = await db.execute(select(Server).where(Server.id == peer_data.server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check for duplicate peer name on the same server
    result = await db.execute(
        select(Peer).where(
            Peer.server_id == peer_data.server_id,
            Peer.name == peer_data.name
        )
    )
    existing_peer = result.scalar_one_or_none()
    if existing_peer:
        raise ValidationError("name", f"Peer name '{peer_data.name}' is already in use on this server")

    # Validate peer IPs belong to server subnet
    if peer_data.ipv4_address and server.ipv4_address:
        is_valid, error_msg = is_ip_in_subnet(peer_data.ipv4_address, server.ipv4_address)
        if not is_valid:
            raise ValidationError("ipv4_address", error_msg)
    
    if peer_data.ipv6_address and server.ipv6_address:
        is_valid, error_msg = is_ip_in_subnet(peer_data.ipv6_address, server.ipv6_address)
        if not is_valid:
            raise ValidationError("ipv6_address", error_msg)
    
    # Check that peer IPs don't match server IPs
    if peer_data.ipv4_address and server.ipv4_address:
        # Extract IP without CIDR notation for comparison
        peer_ip = peer_data.ipv4_address.split('/')[0]
        server_ip = server.ipv4_address.split('/')[0]
        if peer_ip == server_ip:
            raise ValidationError("ipv4_address", "Peer IP address cannot be the same as the server IP address")
    
    if peer_data.ipv6_address and server.ipv6_address:
        # Extract IP without CIDR notation for comparison
        peer_ip = peer_data.ipv6_address.split('/')[0]
        server_ip = server.ipv6_address.split('/')[0]
        if peer_ip == server_ip:
            raise ValidationError("ipv6_address", "Peer IP address cannot be the same as the server IP address")

    # Check for duplicate IPs within the same server
    # Build conditions dynamically to avoid matching NULL values
    duplicate_conditions = []
    if peer_data.ipv4_address:
        duplicate_conditions.append(Peer.ipv4_address == peer_data.ipv4_address)
    if peer_data.ipv6_address:
        duplicate_conditions.append(Peer.ipv6_address == peer_data.ipv6_address)
    
    if duplicate_conditions:
        duplicate_query = select(Peer).where(
            Peer.server_id == peer_data.server_id,
            or_(*duplicate_conditions)
        )
        result = await db.execute(duplicate_query)
        existing_peer = result.scalar_one_or_none()
        
        if existing_peer:
            # Determine which address is duplicate
            field = "ipv4_address" if existing_peer.ipv4_address == peer_data.ipv4_address else "ipv6_address"
            raise ValidationError(
                field,
                f"IP address already in use by peer: {existing_peer.name} on this server"
            )

    # Create peer instance (exclude allowed_ips as it's a computed property)
    peer_dict = peer_data.model_dump(exclude={'allowed_ips'})
    peer = Peer(**peer_dict)
    db.add(peer)
    
    # Mark server as needing reload if it's running
    if server.status == "running":
        server.needs_reload = True
    
    await db.commit()
    await db.refresh(peer)

    # Log audit event
    await audit_service.log_action(
        db, current_user, "CREATE", "peer", peer.id, peer.name,
        {"server": server.name, "allowed_ips": peer.allowed_ips}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.PEER_CREATED,
        "peer",
        peer.id,
        {"name": peer.name, "server_id": server.id, "server_name": server.name},
        current_user.id
    )

    return peer


@router.put("/{peer_id}", response_model=PeerResponse)
@inject
async def update_peer(
    peer_id: int,
    peer_data: PeerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Update an existing WireGuard peer"""
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    # Get server for reloading config and validation
    result = await db.execute(select(Server).where(Server.id == peer.server_id))
    server = result.scalar_one_or_none()

    # Get update data
    update_data = peer_data.model_dump(exclude_unset=True)
    
    # Store old values for audit
    old_values = {
        "name": peer.name,
        "allowed_ips": peer.allowed_ips,
        "enabled": peer.enabled
    }
    
    # Check for duplicate peer name on the same server if name is being updated
    if "name" in update_data:
        result = await db.execute(
            select(Peer).where(
                Peer.server_id == peer.server_id,
                Peer.name == update_data["name"],
                Peer.id != peer_id
            )
        )
        existing_peer = result.scalar_one_or_none()
        if existing_peer:
            raise ValidationError("name", f"Peer name '{update_data['name']}' is already in use on this server")
    
    # Validate IP addresses if being updated
    if 'ipv4_address' in update_data and update_data['ipv4_address'] and server and server.ipv4_address:
        is_valid, error_msg = is_ip_in_subnet(update_data['ipv4_address'], server.ipv4_address)
        if not is_valid:
            raise ValidationError("ipv4_address", error_msg)
    
    if 'ipv6_address' in update_data and update_data['ipv6_address'] and server and server.ipv6_address:
        is_valid, error_msg = is_ip_in_subnet(update_data['ipv6_address'], server.ipv6_address)
        if not is_valid:
            raise ValidationError("ipv6_address", error_msg)
    
    # Check that peer IPs don't match server IPs if being updated
    if 'ipv4_address' in update_data and update_data['ipv4_address'] and server and server.ipv4_address:
        peer_ip = update_data['ipv4_address'].split('/')[0]
        server_ip = server.ipv4_address.split('/')[0]
        if peer_ip == server_ip:
            raise ValidationError("ipv4_address", "Peer IP address cannot be the same as the server IP address")
    
    if 'ipv6_address' in update_data and update_data['ipv6_address'] and server and server.ipv6_address:
        peer_ip = update_data['ipv6_address'].split('/')[0]
        server_ip = server.ipv6_address.split('/')[0]
        if peer_ip == server_ip:
            raise ValidationError("ipv6_address", "Peer IP address cannot be the same as the server IP address")
    
    # Check for duplicate IPs within the same server (excluding current peer)
    # Build conditions dynamically to avoid matching NULL values
    if 'ipv4_address' in update_data or 'ipv6_address' in update_data:
        duplicate_conditions = []
        if update_data.get('ipv4_address'):
            duplicate_conditions.append(Peer.ipv4_address == update_data.get('ipv4_address'))
        if update_data.get('ipv6_address'):
            duplicate_conditions.append(Peer.ipv6_address == update_data.get('ipv6_address'))
        
        if duplicate_conditions:
            duplicate_query = select(Peer).where(
                Peer.server_id == peer.server_id,
                Peer.id != peer_id,
                or_(*duplicate_conditions)
            )
            result = await db.execute(duplicate_query)
            existing_peer = result.scalar_one_or_none()
            
            if existing_peer:
                # Determine which address is duplicate
                field = "ipv4_address" if existing_peer.ipv4_address == update_data.get('ipv4_address') else "ipv6_address"
                raise ValidationError(
                    field,
                    f"IP address already in use by peer: {existing_peer.name} on this server"
                )

    # Convert empty strings to None for IP addresses BEFORE validation
    if "ipv4_address" in update_data and update_data["ipv4_address"] == "":
        update_data["ipv4_address"] = None
    if "ipv6_address" in update_data and update_data["ipv6_address"] == "":
        update_data["ipv6_address"] = None

    # Validate that at least one IP address will remain after update
    # Check the final state BEFORE applying updates
    final_ipv4 = peer.ipv4_address if "ipv4_address" not in update_data else update_data.get("ipv4_address")
    final_ipv6 = peer.ipv6_address if "ipv6_address" not in update_data else update_data.get("ipv6_address")
    
    if not final_ipv4 and not final_ipv6:
        raise MultiFieldValidationError({
            "ipv4_address": ["At least one IP address (IPv4 or IPv6) is required"],
            "ipv6_address": ["At least one IP address (IPv4 or IPv6) is required"]
        })

    # Update fields
    for field, value in update_data.items():
        setattr(peer, field, value)

    # Mark server as needing reload if it's running
    if server and server.status == "running":
        server.needs_reload = True

    await db.commit()
    await db.refresh(peer)

    # Log audit event
    await audit_service.log_action(
        db, current_user, "UPDATE", "peer", peer.id, peer.name,
        {"old": old_values, "new": update_data}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.PEER_EDITED,
        "peer",
        peer.id,
        {"name": peer.name, "changes": list(update_data.keys())},
        current_user.id
    )

    return peer


@router.delete("/{peer_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_peer(
    peer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Delete a WireGuard peer"""
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    # Get server for reloading config
    result = await db.execute(select(Server).where(Server.id == peer.server_id))
    server = result.scalar_one_or_none()

    peer_name = peer.name
    server_id = peer.server_id

    # Mark server as needing reload if it's running
    if server and server.status == "running":
        server.needs_reload = True

    await db.delete(peer)
    await db.commit()

    # Log audit event
    await audit_service.log_action(
        db, current_user, "DELETE", "peer", peer_id, peer_name,
        {"server_id": server_id}, request
    )

    # Publish event
    await event_bus.publish(
        EventType.PEER_DELETED,
        "peer",
        peer_id,
        {"name": peer_name},
        current_user.id
    )

    return None


@router.get("/{peer_id}/migration-preview")
@inject
async def get_migration_preview(
    peer_id: int,
    target_server_id: int = Query(..., description="Target server ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ip_management_service = Depends(Provide[Container.ip_management_service]),
    dns_hierarchy_service = Depends(Provide[Container.dns_hierarchy_service])
):
    """Get suggested configuration for peer migration to a target server"""
    # Verify peer exists
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    # Verify target server exists
    result = await db.execute(select(Server).where(Server.id == target_server_id))
    target_server = result.scalar_one_or_none()

    if not target_server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target server not found"
        )

    # Get suggested IPs
    suggested_ipv4 = await ip_management_service.get_next_available_ipv4(db, target_server_id)
    suggested_ipv6 = await ip_management_service.get_next_available_ipv6(db, target_server_id)
    
    # Get target server DNS
    dns_primary, dns_secondary = await dns_hierarchy_service.get_default_dns_for_server(db, target_server_id)

    return {
        "suggested_ipv4_address": suggested_ipv4,
        "suggested_ipv6_address": suggested_ipv6,
        "suggested_dns_primary": dns_primary,
        "suggested_dns_secondary": dns_secondary,
        "current_ipv4_address": peer.ipv4_address,
        "current_ipv6_address": peer.ipv6_address,
        "current_dns_primary": peer.dns_primary,
        "current_dns_secondary": peer.dns_secondary,
        "current_ipv4_allowed_ips": peer.ipv4_allowed_ips,
        "current_ipv6_allowed_ips": peer.ipv6_allowed_ips,
        "current_persistent_keepalive": peer.persistent_keepalive,
    }


@router.post("/{peer_id}/migrate", response_model=PeerResponse)
@inject
async def migrate_peer(
    peer_id: int,
    migration_request: PeerMigrationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    migration_service: MigrationService = Depends(Provide[Container.migration_service]),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Migrate a peer to a different server with optional custom configuration"""
    # Verify peer exists
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    # Verify target server exists
    result = await db.execute(select(Server).where(Server.id == migration_request.target_server_id))
    target_server = result.scalar_one_or_none()

    if not target_server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target server not found"
        )

    if peer.server_id == migration_request.target_server_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Peer is already on this server"
        )

    # Get source server
    result = await db.execute(select(Server).where(Server.id == peer.server_id))
    source_server = result.scalar_one_or_none()
    
    # Validate custom IPs if provided
    if migration_request.ipv4_address or migration_request.ipv6_address:
        # Check peer IPs belong to target server subnet
        if migration_request.ipv4_address and target_server.ipv4_address:
            is_valid, error_msg = is_ip_in_subnet(migration_request.ipv4_address, target_server.ipv4_address)
            if not is_valid:
                raise ValidationError("ipv4_address", error_msg)
        
        if migration_request.ipv6_address and target_server.ipv6_address:
            is_valid, error_msg = is_ip_in_subnet(migration_request.ipv6_address, target_server.ipv6_address)
            if not is_valid:
                raise ValidationError("ipv6_address", error_msg)
        
        # Check that peer IPs don't match target server IPs
        if migration_request.ipv4_address and target_server.ipv4_address:
            peer_ip = migration_request.ipv4_address.split('/')[0]
            server_ip = target_server.ipv4_address.split('/')[0]
            if peer_ip == server_ip:
                raise ValidationError("ipv4_address", "Peer IP address cannot be the same as the server IP address")
        
        if migration_request.ipv6_address and target_server.ipv6_address:
            peer_ip = migration_request.ipv6_address.split('/')[0]
            server_ip = target_server.ipv6_address.split('/')[0]
            if peer_ip == server_ip:
                raise ValidationError("ipv6_address", "Peer IP address cannot be the same as the server IP address")
        
        # Check for duplicate peer IPs on target server
        # Build conditions dynamically to avoid matching NULL values
        duplicate_conditions = []
        if migration_request.ipv4_address:
            duplicate_conditions.append(Peer.ipv4_address == migration_request.ipv4_address)
        if migration_request.ipv6_address:
            duplicate_conditions.append(Peer.ipv6_address == migration_request.ipv6_address)
        
        if duplicate_conditions:
            duplicate_query = select(Peer).where(
                Peer.server_id == migration_request.target_server_id,
                Peer.id != peer_id,
                or_(*duplicate_conditions)
            )
            result = await db.execute(duplicate_query)
            existing_peer = result.scalar_one_or_none()
            
            if existing_peer:
                field = "ipv4_address" if existing_peer.ipv4_address == migration_request.ipv4_address else "ipv6_address"
                raise ValidationError(
                    field,
                    f"IP address already in use by peer: {existing_peer.name} on target server"
                )
        
        # Check for duplicate peer name on target server
        name_check_query = select(Peer).where(
            Peer.server_id == migration_request.target_server_id,
            Peer.name == peer.name,
            Peer.id != peer_id
        )
        result = await db.execute(name_check_query)
        existing_peer = result.scalar_one_or_none()
        
        if existing_peer:
            raise ValidationError("name", f"Peer name '{peer.name}' is already in use on target server")

    try:
        # Build custom config dict from request
        custom_config = {}
        if migration_request.ipv4_address is not None:
            custom_config['ipv4_address'] = migration_request.ipv4_address
        if migration_request.ipv6_address is not None:
            custom_config['ipv6_address'] = migration_request.ipv6_address
        if migration_request.dns_primary is not None:
            custom_config['dns_primary'] = migration_request.dns_primary
        if migration_request.dns_secondary is not None:
            custom_config['dns_secondary'] = migration_request.dns_secondary
        if migration_request.ipv4_allowed_ips is not None:
            custom_config['ipv4_allowed_ips'] = migration_request.ipv4_allowed_ips
        if migration_request.ipv6_allowed_ips is not None:
            custom_config['ipv6_allowed_ips'] = migration_request.ipv6_allowed_ips
        if migration_request.persistent_keepalive is not None:
            custom_config['persistent_keepalive'] = migration_request.persistent_keepalive
        
        # Perform migration with custom config (or None for auto-config)
        await migration_service.migrate_peer(
            db, 
            peer_id, 
            migration_request.target_server_id, 
            current_user.id,
            custom_config if custom_config else None
        )

        await db.refresh(peer)

        # Reload both servers if active
        if source_server and source_server.status == "running":
            try:
                await wireguard_service.reload_interface(db, source_server.id, source_server.interface)
            except Exception as e:
                print(f"Warning: Failed to reload source server: {e}")

        if target_server.status == "running":
            try:
                await wireguard_service.reload_interface(db, target_server.id, target_server.interface)
            except Exception as e:
                print(f"Warning: Failed to reload target server: {e}")

        # Log audit event
        await audit_service.log_action(
            db, current_user, "MIGRATE", "peer", peer.id, peer.name,
            {
                "from_server": source_server.name if source_server else None,
                "to_server": target_server.name,
                "new_ipv4": peer.ipv4_address,
                "new_ipv6": peer.ipv6_address
            },
            request
        )

        # Publish event
        await event_bus.publish(
            EventType.PEER_MIGRATED,
            "peer",
            peer.id,
            {
                "name": peer.name,
                "from_server_id": source_server.id if source_server else None,
                "to_server_id": migration_request.target_server_id
            },
            current_user.id
        )

        return peer

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {e!s}"
        ) from e


@router.get("/{peer_id}/config", response_class=PlainTextResponse)
@inject
async def export_peer_config(
    peer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """Export the WireGuard configuration file for a peer"""
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    try:
        config_content = await wireguard_service.generate_peer_config_from_db(db, peer.id)
        return config_content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate config: {e!s}"
        ) from e


@router.get("/{peer_id}/qrcode")
@inject
async def get_peer_qrcode(
    peer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """Generate a QR code for the peer configuration"""
    result = await db.execute(select(Peer).where(Peer.id == peer_id))
    peer = result.scalar_one_or_none()

    if not peer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peer not found"
        )

    try:
        # Generate peer config
        config_content = await wireguard_service.generate_peer_config_from_db(db, peer.id)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(config_content)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to bytes
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        return Response(content=img_io.getvalue(), media_type="image/png")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {e!s}"
        ) from e


@router.post("/import", response_model=PeerResponse, status_code=status.HTTP_201_CREATED)
@inject
async def import_peer_config(
    server_id: int,
    request: Request,
    config_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    config_parser: ConfigParser = Depends(Provide[Container.config_parser_service]),
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service])
):
    """Import a WireGuard peer from a configuration file"""
    # Check WireGuard is available
    wg_paths = detect_wireguard_binaries()
    if not wg_paths.get("wg"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="WireGuard is not installed or not found on this system. Install WireGuard before importing peers."
        )

    # Verify server exists
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()

    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )

    try:
        # Read config file
        config_content = await config_file.read()
        config_text = config_content.decode('utf-8')

        # Parse config
        parsed_config = config_parser.parse_peer_config(config_text)
        peer_data = config_parser.extract_peer_client_data(parsed_config)
        
        # Add server_id and generate name from filename
        peer_data['server_id'] = server_id
        
        # Generate name from filename (remove .conf extension)
        if config_file.filename:
            peer_name = config_file.filename.replace('.conf', '').replace('.wg', '')
        else:
            peer_name = f"Imported Peer"
        peer_data['name'] = peer_name
        
        # Generate public key from private key
        # Note: In production, you'd use wg pubkey command or a library
        # For now, we'll require it to be in the peer data or generate a placeholder
        if not peer_data.get('public_key'):
            # Try to derive from private key using wireguard service
            from subprocess import run, PIPE
            try:
                result = run(['wg', 'pubkey'], input=peer_data['private_key'].encode(), 
                           stdout=PIPE, stderr=PIPE, check=True)
                peer_data['public_key'] = result.stdout.decode().strip()
            except Exception:
                raise ValueError("Could not derive public key from private key. Config must include public key or valid private key.")

        # Create peer
        peer = Peer(**peer_data)
        db.add(peer)
        await db.commit()
        await db.refresh(peer)

        # Reload server config if server is active
        if server and server.status == "running":
            try:
                await wireguard_service.reload_interface(db, server.id, server.interface)
            except Exception as e:
                print(f"Warning: Failed to reload server: {e}")

        # Log audit event
        await audit_service.log_action(
            db, current_user, "IMPORT", "peer", peer.id, peer.name,
            {"filename": config_file.filename, "server": server.name}, request
        )

        # Publish event
        await event_bus.publish(
            EventType.PEER_CREATED,
            "peer",
            peer.id,
            {"name": peer.name, "server_id": server.id, "imported": True},
            current_user.id
        )

        return peer

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
