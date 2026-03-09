"""
Unit tests for WebSocket ConnectionManager.

Tests cover:
- Connection management (connect/disconnect)
- Broadcasting to multiple clients
- Personal message sending
- Error handling and cleanup
- Connection resilience
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import WebSocket

from app.api.ws import ConnectionManager


@pytest.fixture
def connection_manager():
    """Create a fresh ConnectionManager instance for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = Mock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.fixture
def multiple_mock_websockets():
    """Create multiple mock WebSocket connections."""
    websockets = []
    for i in range(3):
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.id = i  # Add ID for identification in tests
        websockets.append(ws)
    return websockets


class TestConnectionManager:
    """Test suite for ConnectionManager class."""
    
    @pytest.mark.asyncio
    async def test_connect_adds_websocket(self, connection_manager, mock_websocket):
        """Test that connect() adds websocket to active connections."""
        # Act
        await connection_manager.connect(mock_websocket)
        
        # Assert
        assert mock_websocket in connection_manager.active_connections
        assert len(connection_manager.active_connections) == 1
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_multiple_websockets(self, connection_manager, multiple_mock_websockets):
        """Test that multiple websockets can be connected."""
        # Act
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)
        
        # Assert
        assert len(connection_manager.active_connections) == 3
        for ws in multiple_mock_websockets:
            assert ws in connection_manager.active_connections
            ws.accept.assert_called_once()
    
    def test_disconnect_removes_websocket(self, connection_manager, mock_websocket):
        """Test that disconnect() removes websocket from active connections."""
        # Arrange
        connection_manager.active_connections.add(mock_websocket)
        
        # Act
        connection_manager.disconnect(mock_websocket)
        
        # Assert
        assert mock_websocket not in connection_manager.active_connections
        assert len(connection_manager.active_connections) == 0
    
    def test_disconnect_nonexistent_websocket(self, connection_manager, mock_websocket):
        """Test that disconnecting a non-existent websocket doesn't raise error."""
        # Act & Assert - should not raise
        connection_manager.disconnect(mock_websocket)
        assert len(connection_manager.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, connection_manager, multiple_mock_websockets):
        """Test that broadcast() sends message to all active connections."""
        # Arrange
        for ws in multiple_mock_websockets:
            connection_manager.active_connections.add(ws)
        
        message = {"type": "test", "data": "hello"}
        
        # Act
        await connection_manager.broadcast(message)
        
        # Assert
        for ws in multiple_mock_websockets:
            ws.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self, connection_manager):
        """Test that broadcast() with no connections doesn't raise error."""
        # Arrange
        message = {"type": "test", "data": "hello"}
        
        # Act & Assert - should not raise
        await connection_manager.broadcast(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_handles_send_error(self, connection_manager, multiple_mock_websockets):
        """Test that broadcast() handles errors and removes failed connections."""
        # Arrange
        for ws in multiple_mock_websockets:
            connection_manager.active_connections.add(ws)
        
        # Make the second websocket fail
        multiple_mock_websockets[1].send_json.side_effect = Exception("Connection failed")
        
        message = {"type": "test", "data": "hello"}
        
        # Act
        await connection_manager.broadcast(message)
        
        # Assert
        # First and third should have received message
        multiple_mock_websockets[0].send_json.assert_called_once_with(message)
        multiple_mock_websockets[2].send_json.assert_called_once_with(message)
        
        # Failed connection should be removed
        assert multiple_mock_websockets[1] not in connection_manager.active_connections
        assert len(connection_manager.active_connections) == 2
    
    @pytest.mark.asyncio
    async def test_send_personal_sends_to_specific_connection(self, connection_manager, mock_websocket):
        """Test that send_personal() sends message to specific connection only."""
        # Arrange
        connection_manager.active_connections.add(mock_websocket)
        message = {"type": "personal", "data": "private message"}
        
        # Act
        await connection_manager.send_personal(message, mock_websocket)
        
        # Assert
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_personal_handles_error(self, connection_manager, mock_websocket):
        """Test that send_personal() handles errors and removes failed connection."""
        # Arrange
        connection_manager.active_connections.add(mock_websocket)
        mock_websocket.send_json.side_effect = Exception("Connection failed")
        message = {"type": "personal", "data": "private message"}
        
        # Act
        await connection_manager.send_personal(message, mock_websocket)
        
        # Assert
        mock_websocket.send_json.assert_called_once_with(message)
        assert mock_websocket not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_broadcast_metrics_update_format(self, connection_manager, mock_websocket):
        """Test broadcasting metrics update with correct format."""
        # Arrange
        connection_manager.active_connections.add(mock_websocket)
        
        metrics_data = {
            "servers": {
                "total_rx_bytes": 1000,
                "total_tx_bytes": 2000
            },
            "peers": {
                "total_rx_bytes": 500,
                "total_tx_bytes": 1500
            }
        }
        
        message = {
            "type": "metrics_update",
            "data": metrics_data
        }
        
        # Act
        await connection_manager.broadcast(message)
        
        # Assert
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "metrics_update"
        assert "servers" in call_args["data"]
        assert "peers" in call_args["data"]
    
    @pytest.mark.asyncio
    async def test_broadcast_notification_format(self, connection_manager, mock_websocket):
        """Test broadcasting notification with correct format."""
        # Arrange
        connection_manager.active_connections.add(mock_websocket)
        
        notification_data = {
            "id": 1,
            "title": "New Peer Connected",
            "message": "Peer 'laptop' connected to server 'main'",
            "type": "success"
        }
        
        message = {
            "type": "notification",
            "data": notification_data
        }
        
        # Act
        await connection_manager.broadcast(message)
        
        # Assert
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "notification"
        assert call_args["data"]["title"] == "New Peer Connected"
    
    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self, connection_manager, multiple_mock_websockets):
        """Test that multiple broadcasts work correctly."""
        # Arrange
        for ws in multiple_mock_websockets:
            connection_manager.active_connections.add(ws)
        
        messages = [
            {"type": "metrics_update", "data": {"value": 1}},
            {"type": "notification", "data": {"msg": "test"}},
            {"type": "pong", "data": {}}
        ]
        
        # Act
        for msg in messages:
            await connection_manager.broadcast(msg)
        
        # Assert
        for ws in multiple_mock_websockets:
            assert ws.send_json.call_count == 3
    
    def test_connection_manager_state_isolation(self):
        """Test that separate ConnectionManager instances are isolated."""
        # Arrange
        manager1 = ConnectionManager()
        manager2 = ConnectionManager()
        
        ws1 = Mock(spec=WebSocket)
        ws2 = Mock(spec=WebSocket)
        
        # Act
        manager1.active_connections.add(ws1)
        manager2.active_connections.add(ws2)
        
        # Assert
        assert ws1 in manager1.active_connections
        assert ws1 not in manager2.active_connections
        assert ws2 in manager2.active_connections
        assert ws2 not in manager1.active_connections
    
    @pytest.mark.asyncio
    async def test_broadcast_removes_all_failed_connections(self, connection_manager, multiple_mock_websockets):
        """Test that all failed connections are removed in one broadcast."""
        # Arrange
        for ws in multiple_mock_websockets:
            connection_manager.active_connections.add(ws)
        
        # Make all websockets fail
        for ws in multiple_mock_websockets:
            ws.send_json.side_effect = Exception("Connection failed")
        
        message = {"type": "test", "data": "hello"}
        
        # Act
        await connection_manager.broadcast(message)
        
        # Assert
        assert len(connection_manager.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_send_personal_to_disconnected_websocket(self, connection_manager, mock_websocket):
        """Test sending personal message to websocket not in active connections."""
        # Arrange - websocket is NOT added to active_connections
        mock_websocket.send_json.side_effect = Exception("Not connected")
        message = {"type": "personal", "data": "test"}
        
        # Act
        await connection_manager.send_personal(message, mock_websocket)
        
        # Assert - should handle gracefully, not crash
        mock_websocket.send_json.assert_called_once_with(message)
        assert mock_websocket not in connection_manager.active_connections


class TestConnectionManagerIntegration:
    """Integration tests for ConnectionManager with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, connection_manager, mock_websocket):
        """Test complete connection lifecycle: connect -> send -> disconnect."""
        # Connect
        await connection_manager.connect(mock_websocket)
        assert mock_websocket in connection_manager.active_connections
        
        # Send message
        message = {"type": "test", "data": "hello"}
        await connection_manager.broadcast(message)
        mock_websocket.send_json.assert_called_once_with(message)
        
        # Disconnect
        connection_manager.disconnect(mock_websocket)
        assert mock_websocket not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_multiple_clients_with_partial_failures(self, connection_manager, multiple_mock_websockets):
        """Test realistic scenario with multiple clients and some failures."""
        # Connect all clients
        for ws in multiple_mock_websockets:
            await connection_manager.connect(ws)
        
        assert len(connection_manager.active_connections) == 3
        
        # First broadcast succeeds for all
        await connection_manager.broadcast({"type": "msg1", "data": "hello"})
        assert len(connection_manager.active_connections) == 3
        
        # Second client fails on next broadcast
        multiple_mock_websockets[1].send_json.side_effect = Exception("Network error")
        await connection_manager.broadcast({"type": "msg2", "data": "world"})
        
        # Only 2 clients remain
        assert len(connection_manager.active_connections) == 2
        assert multiple_mock_websockets[1] not in connection_manager.active_connections
        
        # Third broadcast succeeds for remaining clients
        multiple_mock_websockets[1].send_json.side_effect = None  # Reset
        await connection_manager.broadcast({"type": "msg3", "data": "test"})
        assert len(connection_manager.active_connections) == 2
