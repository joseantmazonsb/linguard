"""API endpoints for importing WireGuard configurations."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from ..core.database import get_db
from ..core.security import get_current_user
from ..services.config_parser import ConfigParser
from ..models.user import User
from ..models.server import Server
from ..models.peer import Peer
from ..schemas.server import ServerCreate, ServerResponse
from ..schemas.peer import PeerCreate, PeerResponse
from ..services.wireguard import WireGuardService
from ..services.audit_logger import AuditService
from ..core.events import EventType, event_bus
from dependency_injector.wiring import inject, Provide
from ..core.containers import Container

router = APIRouter()


@router.post("/parse")
async def parse_wireguard_config(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Parse a WireGuard configuration file and return parsed data.
    
    This endpoint analyzes the config file and returns:
    - type: 'server' or 'client'
    - parsed_data: extracted configuration values
    - missing_fields: fields that need to be provided by the user
    
    The user will then fill in the missing fields before final import.
    """
    # Read file content
    content = await file.read()
    try:
        config_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Expected UTF-8.")
    
    # Parse config
    parser = ConfigParser()
    
    # Try to determine if it's a server or client config
    # Heuristic: if it has ListenPort or multiple [Peer] sections, it's a server
    # If it has Endpoint in [Peer], it's a client
    is_server = 'ListenPort' in config_content and '[Interface]' in config_content
    has_endpoint = 'Endpoint' in config_content and '[Peer]' in config_content
    
    if is_server or not has_endpoint:
        # Server configuration
        parsed = parser.parse_server_config(config_content)
        server_data = parser.extract_server_data(parsed)
        peers_data = parser.extract_peers_data(parsed)
        
        return {
            "type": "server",
            "parsed_data": {
                "server": server_data,
                "peers": peers_data
            },
            "missing_fields": {
                "server": ["name", "interface", "endpoint", "description"],
                "peers": [
                    {
                        "public_key": peer.get("public_key"),
                        "missing": ["name", "description", "email"]
                    }
                    for peer in peers_data
                ]
            }
        }
    else:
        # Client/Peer configuration
        parsed = parser.parse_peer_config(config_content)
        peer_data = parser.extract_peer_client_data(parsed)
        
        return {
            "type": "client",
            "parsed_data": peer_data,
            "missing_fields": ["name", "server_id", "description", "email"]
        }


@router.post("/server", response_model=ServerResponse)
@inject
async def import_server(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wg_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
) -> Server:
    """
    Import a server configuration.
    
    Request body should contain:
    - parsed_data: The parsed configuration from parse_wireguard_config
    - additional_data: User-provided fields (name, interface, endpoint, description)
    """
    parsed_data = request.get("parsed_data", {})
    additional_data = request.get("additional_data", {})
    
    # Validate required fields
    if not additional_data.get("name"):
        raise HTTPException(status_code=400, detail="Server name is required")
    if not additional_data.get("interface"):
        raise HTTPException(status_code=400, detail="Interface name is required")
    
    # Get keys from parsed config
    private_key = parsed_data.get("private_key")
    if not private_key:
        raise HTTPException(status_code=400, detail="Private key not found in config")
    
    # If config doesn't have public key, generate new key pair
    public_key = parsed_data.get("public_key")
    if not public_key:
        # Generate new keypair since we can't derive public from private easily
        private_key, public_key = wg_service.generate_keypair()
    
    # Create server
    server = Server(
        name=additional_data["name"],
        interface=additional_data["interface"],
        endpoint=additional_data.get("endpoint"),
        description=additional_data.get("description"),
        private_key=private_key,
        public_key=public_key,
        listen_port=parsed_data.get("listen_port", 51820),
        ipv4_address=parsed_data.get("ipv4_address"),
        ipv6_address=parsed_data.get("ipv6_address"),
        dns_primary=parsed_data.get("dns_primary"),
        dns_secondary=parsed_data.get("dns_secondary"),
    )
    
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    # Audit log
    await audit_service.log_action(
        db=db,
        user=current_user,
        action="import_server",
        resource_type="server",
        resource_id=server.id,
        resource_name=server.name,
        details={"interface": server.interface}
    )
    
    # Emit event
    await event_bus.publish(
        event_type=EventType.SERVER_CREATED,
        source_type="server",
        source_id=server.id,
        payload={
            "server_id": server.id,
            "server_name": server.name,
            "user_id": current_user.id,
        }
    )
    
    return server


@router.post("/peer", response_model=PeerResponse)
@inject
async def import_peer(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    wg_service: WireGuardService = Depends(Provide[Container.wireguard_service]),
    audit_service: AuditService = Depends(Provide[Container.audit_service]),
) -> Peer:
    """
    Import a peer/client configuration.
    
    Request body should contain:
    - parsed_data: The parsed configuration from parse_wireguard_config
    - additional_data: User-provided fields (name, server_id, description, email)
    """
    parsed_data = request.get("parsed_data", {})
    additional_data = request.get("additional_data", {})
    
    # Validate required fields
    if not additional_data.get("name"):
        raise HTTPException(status_code=400, detail="Peer name is required")
    if not additional_data.get("server_id"):
        raise HTTPException(status_code=400, detail="server_id is required")
    
    # Verify server exists
    server_id = additional_data["server_id"]
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Get keys from parsed config
    private_key = parsed_data.get("private_key")
    if not private_key:
        raise HTTPException(status_code=400, detail="Private key not found in config")
    
    # If config doesn't have public key, generate new key pair
    public_key = parsed_data.get("public_key")
    if not public_key:
        # Generate new keypair since we can't derive public from private easily
        private_key, public_key = wg_service.generate_keypair()
    
    # Create peer
    peer = Peer(
        server_id=server_id,
        name=additional_data["name"],
        description=additional_data.get("description"),
        email=additional_data.get("email"),
        ipv4_address=parsed_data.get("ipv4_address"),
        ipv6_address=parsed_data.get("ipv6_address"),
        dns_primary=parsed_data.get("dns_primary"),
        dns_secondary=parsed_data.get("dns_secondary"),
        ipv4_allowed_ips=parsed_data.get("ipv4_allowed_ips"),
        ipv6_allowed_ips=parsed_data.get("ipv6_allowed_ips"),
        persistent_keepalive=parsed_data.get("persistent_keepalive", 25),
        private_key=private_key,
        public_key=public_key,
        preshared_key=parsed_data.get("preshared_key"),
        enabled=True,
    )
    
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    
    # Audit log
    await audit_service.log_action(
        db=db,
        user=current_user,
        action="import_peer",
        resource_type="peer",
        resource_id=peer.id,
        resource_name=peer.name,
        details={"server_id": server_id}
    )
    
    # Emit event
    await event_bus.publish(
        event_type=EventType.PEER_CREATED,
        source_type="peer",
        source_id=peer.id,
        payload={
            "peer_id": peer.id,
            "peer_name": peer.name,
            "server_id": server_id,
            "user_id": current_user.id,
        }
    )
    
    return peer
