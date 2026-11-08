"""WebSocket endpoints for real-time updates."""
from typing import Set, Optional
from secrets import token_urlsafe
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy import select

from ..core import database as _db
from ..core.security import get_current_user, security, require_secure_signing_key, validate_auth_method
from ..models.user import User
from ..models.settings import GlobalSettings

router = APIRouter()
TICKET_TTL = 30
MAX_TICKETS = 10000
_tickets = {}
_ticket_lock = Lock()


async def authenticate(token: Optional[str]):
    """Resolve the current authentication mode and identity from the database."""
    async with _db.AsyncSessionLocal() as db:
        result = await db.execute(select(GlobalSettings))
        settings = result.scalar_one_or_none()
        require_secure_signing_key(settings)
        if settings is None:
            raise ValueError("Missing authentication settings")
        auth_disabled = settings.setup_completed is True and settings.disable_auth is True
        if auth_disabled:
            # Match get_current_user's identity selection in auth-disabled mode.
            result = await db.execute(select(User).limit(1))
        else:
            if not token:
                raise ValueError("Missing token")
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[settings.algorithm], options={"require_exp": True}
            )
            username = payload.get("sub")
            if not isinstance(username, str) or not username:
                raise ValueError("Missing token subject")
            result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None and not auth_disabled:
            raise ValueError("User not found")
        if not auth_disabled:
            validate_auth_method(payload, settings, user)
        return auth_disabled, user.id if user else None, user.role == "admin" if user else False


@router.post("/api/v1/ws/ticket")
async def issue_ticket(
    response: Response,
    current_user: User = Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    token = credentials.credentials if credentials else None
    try:
        auth_disabled, user_id, _ = await authenticate(token)
        if user_id != current_user.id:
            raise ValueError("Authentication identity changed")
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials") from None

    ticket = token_urlsafe(32)
    now = monotonic()
    with _ticket_lock:
        for key, value in list(_tickets.items()):
            if value[0] <= now:
                del _tickets[key]
        if len(_tickets) >= MAX_TICKETS:
            raise HTTPException(status_code=503, detail="WebSocket ticket capacity reached")
        _tickets[ticket] = (now + TICKET_TTL, token if not auth_disabled else None, auth_disabled, user_id)
    response.headers["Cache-Control"] = "no-store"
    return {"ticket": ticket}


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.identities = {}
    
    async def connect(self, websocket: WebSocket, token: Optional[str], auth_disabled: bool, user_id: Optional[int]):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.identities[websocket] = (token, auth_disabled, user_id)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        self.identities.pop(websocket, None)
    
    async def broadcast(self, message: dict, user_id: Optional[int] = None):
        """Deliver notifications to their owner and system events to admins."""
        for connection in self.active_connections.copy():
            try:
                token, initial_auth_disabled, initial_user_id = self.identities[connection]
                auth_disabled, connection_user_id, is_admin = await authenticate(token)
                if auth_disabled != initial_auth_disabled or connection_user_id != initial_user_id:
                    raise ValueError("Authentication identity or mode changed")
            except Exception as e:
                print(f"WebSocket reauthentication failed: {e}")
                self.disconnect(connection)
                try:
                    await connection.close(code=status.WS_1008_POLICY_VIOLATION)
                except Exception:
                    pass
                continue
            if message.get("type") == "notification":
                if user_id is None or connection_user_id != user_id:
                    continue
            elif not is_admin:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending message to client: {e}")
                self.disconnect(connection)
    
    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, ticket: Optional[str] = None):
    """
    Unified WebSocket endpoint for real-time updates.
    
    Query params:
    - ticket: short-lived, single-use WebSocket ticket
    
    Message types (from server to client):
    1. metrics_update - Real-time metrics data
    2. notification - New notification
    3. health_update - System health status update
    4. server_status_change - Server status changed
    5. connected - Connection established
    6. pong - Response to ping
    
    Message format:
    {
        "type": "metrics_update" | "notification" | "health_update" | "server_status_change" | "connected" | "pong",
        "data": {...}
    }
    """
    try:
        with _ticket_lock:
            entry = _tickets.pop(ticket, None) if ticket else None
        if entry is None or entry[0] <= monotonic():
            raise ValueError("Invalid or expired ticket")
        _, token, expected_auth_disabled, expected_user_id = entry
        auth_disabled, user_id, _ = await authenticate(token)
        if auth_disabled != expected_auth_disabled or user_id != expected_user_id:
            raise ValueError("Authentication identity or mode changed")
    except Exception as e:
        print(f"WebSocket authentication failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        await manager.connect(websocket, token, auth_disabled, user_id)
        
        # Send initial connection success message
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connection established",
            "authenticated": not auth_disabled
        })
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for messages from client (like ping/pong)
                data = await websocket.receive_text()
                
                # Handle client messages (if any)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in WebSocket loop: {e}")
                break
                
    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        manager.disconnect(websocket)


async def broadcast_metrics_update(metrics_data: dict):
    """
    Broadcast metrics update to administrators.
    
    This function should be called by the metrics collector service
    after collecting new metrics.
    """
    await manager.broadcast({
        "type": "metrics_update",
        "data": metrics_data
    })


async def broadcast_notification(notification_data: dict, user_id: int):
    """
    Broadcast notification only to the intended user.
    
    This function should be called when a new notification is created.
    
    Args:
        user_id: Recipient user ID
        notification_data: Dictionary with notification details
            {
                "id": int,
                "title": str,
                "message": str,
                "type": str (success, warning, error, info),
                "link": str (optional),
                "created_at": str (ISO format)
            }
    """
    await manager.broadcast({
        "type": "notification",
        "data": notification_data
    }, user_id=user_id)


async def broadcast_server_status_change(server_data: dict):
    """
    Broadcast server status change to administrators.
    
    This function should be called when a server status changes
    (started, stopped, reloaded).
    
    Args:
        server_data: Dictionary with server status details
            {
                "server_id": int,
                "name": str,
                "status": str (running, stopped, error),
                "event_type": str (server.started, server.stopped, server.reloaded),
                "detected": bool (optional, True if auto-detected)
            }
    """
    await manager.broadcast({
        "type": "server_status_change",
        "data": server_data
    })


async def broadcast_health_update(health_data: dict):
    """
    Broadcast health status update to administrators.
    
    This function should be called by the HealthMonitorService
    when system health status changes.
    
    Args:
        health_data: Dictionary with health status details
            {
                "status": str (healthy, unhealthy),
                "timestamp": str (ISO format),
                "checks": {
                    "database": {"status": str, "message": str},
                    "wireguard": {"status": str, "message": str},
                    "ip_forwarding": {"status": str, "message": str},
                    "firewall": {"status": str, "message": str}
                }
            }
    """
    await manager.broadcast({
        "type": "health_update",
        "data": health_data
    })
