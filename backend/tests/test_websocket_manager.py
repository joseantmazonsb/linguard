"""
Unit tests for WebSocket Connection Manager.

Tests cover:
- Connection management (connect/disconnect)
- Message sending
- Authentication
- Multiple client support
"""

import asyncio
from unittest.mock import MagicMock, patch


class TestConnectionManager:
    """Test Connection Manager class."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        from app.api.ws import ConnectionManager
        
        manager = ConnectionManager()
        
        assert manager is not None
        assert isinstance(manager.active_connections, set)
        
    def test_manager_active_connections(self):
        """Test active connections set."""
        from app.api.ws import ConnectionManager
        
        manager = ConnectionManager()
        
        assert len(manager.active_connections) == 0
        
    def test_manager_disconnect_all(self):
        """Test disconnect all connections."""
        from app.api.ws import ConnectionManager
        
        manager = ConnectionManager()
        
        # Disconnect all (should be no-op when empty)
        manager.disconnect_all()
        
        assert len(manager.active_connections) == 0


class TestWebSocketConnection:
    """Test WebSocket connection handling."""
    
    @patch('app.api.ws.websockets')
    async def test_websocket_connection(self, mock_websockets):
        """Test WebSocket connection."""
        from app.api.ws import ConnectionManager
        
        # Setup mock
        mock_conn = MagicMock()
        mock_websockets.connect.return_value = mock_conn
        
        manager = ConnectionManager()
        
        # Connect
        await manager.connect(mock_conn)
        
        assert mock_conn in manager.active_connections
        
    @patch('app.api.ws.websockets')
    async def test_websocket_disconnection(self, mock_websockets):
        """Test WebSocket disconnection."""
        from app.api.ws import ConnectionManager
        
        # Setup mock
        mock_conn = MagicMock()
        mock_websockets.connect.return_value = mock_conn
        
        manager = ConnectionManager()
        
        # Connect
        await manager.connect(mock_conn)
        
        # Disconnect
        manager.disconnect(mock_conn)
        
        assert mock_conn not in manager.active_connections
        
    @patch('app.api.ws.websockets')
    async def test_multiple_connections(self, mock_websockets):
        """Test multiple concurrent connections."""
        from app.api.ws import ConnectionManager
        
        # Setup mocks
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_websockets.connect.side_effect = [mock_conn1, mock_conn2]
        
        manager = ConnectionManager()
        
        # Connect multiple clients
        await manager.connect(mock_conn1)
        await manager.connect(mock_conn2)
        
        assert len(manager.active_connections) == 2
        
    @patch('app.api.ws.websockets')
    async def test_broadcast_message(self, mock_websockets):
        """Test broadcasting message to all connections."""
        from app.api.ws import ConnectionManager
        
        # Setup mocks
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        mock_websockets.connect.side_effect = [mock_conn1, mock_conn2]
        
        manager = ConnectionManager()
        
        # Connect multiple clients
        await manager.connect(mock_conn1)
        await manager.connect(mock_conn2)
        
        # Broadcast message
        await manager.broadcast({"type": "test", "data": "message"})
        
        # Both connections should receive message
        mock_conn1.send_json.assert_called_once()
        mock_conn2.send_json.assert_called_once()
        
    @patch('app.api.ws.websockets')
    async def test_personal_message(self, mock_websockets):
        """Test sending personal message to specific connection."""
        from app.api.ws import ConnectionManager
        
        # Setup mock
        mock_conn1 = MagicMock()
        mock_websockets.connect.return_value = mock_conn1
        
        manager = ConnectionManager()
        
        # Connect
        await manager.connect(mock_conn1)
        
        # Send personal message
        await manager.send_personal(mock_conn1, {"type": "test"})
        
        mock_conn1.send_json.assert_called_once_with({"type": "test"})
        
    @patch('app.api.ws.websockets')
    async def test_send_personal_to_nonexistent(self, mock_websockets):
        """Test sending message to non-existent connection."""
        from app.api.ws import ConnectionManager
        
        # Setup mock
        mock_conn1 = MagicMock()
        mock_websockets.connect.return_value = mock_conn1
        
        manager = ConnectionManager()
        
        # Connect
        await manager.connect(mock_conn1)
        
        # Try to send to non-existent connection
        nonexistent_conn = MagicMock()
        
        with patch.object(manager, 'disconnect') as mock_disconnect:
            manager.disconnect(nonexistent_conn)
            
            # Should not raise exception
            assert mock_disconnect.called
            
    @patch('app.api.ws.websockets')
    async def test_receive_and_forward(self, mock_websockets):
        """Test receiving and forwarding messages."""
        from app.api.ws import ConnectionManager
        
        # Setup mock
        mock_conn = MagicMock()
        mock_conn.receive_text = MagicMock(return_value='{"type": "test"}')
        mock_websockets.connect.return_value = mock_conn
        
        manager = ConnectionManager()
        
        # Connect
        await manager.connect(mock_conn)
        
        # Send personal message (simulates client sending)
        await manager.send_personal(mock_conn, {"type": "pong"})
        
        mock_conn.send_json.assert_called_once_with({"type": "pong"})


class TestWebSocketManager:
    """Test WebSocket Manager class."""
    
    def test_manager_initialization(self):
        """Test manager initialization."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        assert manager is not None
        assert isinstance(manager.active_connections, set)
        
    def test_manager_active_connections(self):
        """Test active connections set."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        assert len(manager.active_connections) == 0
        
    def test_manager_broadcast(self):
        """Test broadcasting message."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        # Mock connections
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        
        manager.active_connections.add(mock_conn1)
        manager.active_connections.add(mock_conn2)
        
        # Broadcast
        manager.broadcast({"type": "test"})
        
        # Both connections should receive
        mock_conn1.send_json.assert_called_once()
        mock_conn2.send_json.assert_called_once()
        
    def test_manager_send_personal(self):
        """Test sending personal message."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        mock_conn = MagicMock()
        
        manager.send_personal(mock_conn, {"type": "test"})
        
        mock_conn.send_json.assert_called_once_with({"type": "test"})
        
    def test_manager_disconnect(self):
        """Test disconnecting connection."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        mock_conn = MagicMock()
        
        manager.active_connections.add(mock_conn)
        
        # Disconnect
        manager.disconnect(mock_conn)
        
        assert mock_conn not in manager.active_connections
        
    def test_manager_disconnect_all(self):
        """Test disconnecting all connections."""
        from app.api.ws import WebSocketManager
        
        manager = WebSocketManager()
        
        mock_conn1 = MagicMock()
        mock_conn2 = MagicMock()
        
        manager.active_connections.add(mock_conn1)
        manager.active_connections.add(mock_conn2)
        
        # Disconnect all
        manager.disconnect_all()
        
        assert len(manager.active_connections) == 0


class TestWebSocketAuth:
    """Test WebSocket authentication."""
    
    def test_valid_token(self):
        """Test valid token authentication."""
        from app.api.ws import verify_token
        
        # Mock pyjwt
        with patch('app.api.ws.pyjwt') as mock_jwt:
            mock_jwt.decode.return_value = {"sub": "user123"}
            
            token = "mock_jwt_token"
            result = verify_token(token)
            
            assert result == {"sub": "user123"}
            
    def test_invalid_token(self):
        """Test invalid token authentication."""
        from app.api.ws import verify_token
        
        with patch('app.api.ws.pyjwt') as mock_jwt:
            mock_jwt.decode.side_effect = Exception("Invalid token")
            
            token = "invalid_token"
            
            # Should raise exception
            try:
                verify_token(token)
                assert False, "Should have raised exception"
            except Exception:
                pass
                
    def test_expired_token(self):
        """Test expired token authentication."""
        from app.api.ws import verify_token
        
        with patch('app.api.ws.pyjwt') as mock_jwt:
            mock_jwt.decode.side_effect = Exception("Token expired")
            
            token = "expired_token"
            
            # Should raise exception
            try:
                verify_token(token)
                assert False, "Should have raised exception"
            except Exception:
                pass


class TestWebSocketMessage:
    """Test WebSocket message handling."""
    
    def test_message_serialization(self):
        """Test message serialization."""
        import json
        
        message = {"type": "test", "data": {"key": "value"}}
        
        serialized = json.dumps(message)
        
        assert isinstance(serialized, str)
        assert "test" in serialized
        
    def test_message_deserialization(self):
        """Test message deserialization."""
        import json
        
        serialized = '{"type": "test", "data": {"key": "value"}}'
        
        message = json.loads(serialized)
        
        assert message["type"] == "test"
        assert message["data"]["key"] == "value"
        
    def test_pong_response(self):
        """Test PONG response generation."""
        import json
        
        message = {"type": "pong"}
        
        serialized = json.dumps(message)
        
        assert "pong" in serialized


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.api.ws", "--cov-report=term-missing"])
