"""WebSocket endpoints for real-time updates."""
from typing import Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import database as _db
from ..models.user import User
from ..models.settings import GlobalSettings

router = APIRouter()

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending message to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
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
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    Unified WebSocket endpoint for real-time updates.
    
    Query params:
    - token: JWT authentication token (optional for now)
    
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
    user = None
    
    # Authenticate if token provided
    if token:
        try:
            # Create database session
            async with _db.AsyncSessionLocal() as db:
                try:
                    # Get settings for JWT validation
                    result = await db.execute(select(GlobalSettings))
                    settings = result.scalar_one_or_none()
                    
                    if settings and not settings.disable_auth:
                        # Validate JWT token
                        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
                        username: str | None = payload.get("sub")
                        
                        if username:
                            # Get user
                            result = await db.execute(select(User).where(User.username == username))
                            user = result.scalar_one_or_none()
                            
                            if user:
                                print(f"WebSocket authenticated: {username}")
                            else:
                                print(f"WebSocket auth failed: user not found")
                        else:
                            print("WebSocket auth failed: no username in token")
                    else:
                        print("WebSocket: Auth disabled or no settings")
                        
                except JWTError as e:
                    print(f"WebSocket JWT error: {e}")
                    
        except Exception as e:
            print(f"WebSocket authentication error: {e}")
    else:
        print("WebSocket: No token provided (accepting anyway for now)")
    
    try:
        # Accept connection (for now, accept even without auth)
        # TODO: Make auth required in production
        await manager.connect(websocket)
        
        # Send initial connection success message
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connection established",
            "authenticated": user is not None
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
    Broadcast metrics update to all connected clients.
    
    This function should be called by the metrics collector service
    after collecting new metrics.
    """
    await manager.broadcast({
        "type": "metrics_update",
        "data": metrics_data
    })


async def broadcast_notification(notification_data: dict):
    """
    Broadcast notification to all connected clients.
    
    This function should be called when a new notification is created.
    
    Args:
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
    })


async def broadcast_server_status_change(server_data: dict):
    """
    Broadcast server status change to all connected clients.
    
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
    Broadcast health status update to all connected clients.
    
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
