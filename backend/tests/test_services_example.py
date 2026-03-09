"""
Example unit test for WireGuardService with dependency injection.

This demonstrates how the refactored services can be easily mocked for testing.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch


def test_wireguard_service_generate_keypair(mock_wireguard_service):
    """Test that WireGuardService.generate_keypair returns expected values."""
    # Act
    private_key, public_key = mock_wireguard_service.generate_keypair()
    
    # Assert
    assert private_key == "mock_private_key"
    assert public_key == "mock_public_key"
    mock_wireguard_service.generate_keypair.assert_called_once()


@pytest.mark.asyncio
async def test_wireguard_service_generate_config(mock_wireguard_service):
    """Test that WireGuardService.generate_server_config works with mocks."""
    # Arrange
    mock_db = Mock()
    server_id = 1
    
    # Act
    config = await mock_wireguard_service.generate_server_config(mock_db, server_id)
    
    # Assert
    assert "[Interface]" in config
    mock_wireguard_service.generate_server_config.assert_called_once_with(mock_db, server_id)


def test_config_parser_parse_server_config(mock_config_parser):
    """Test that ConfigParser.parse_server_config returns expected structure."""
    # Arrange
    config_text = "[Interface]\nPrivateKey = test\n"
    
    # Act
    result = mock_config_parser.parse_server_config(config_text)
    
    # Assert
    assert result["name"] == "test-server"
    assert result["listen_port"] == 51820
    mock_config_parser.parse_server_config.assert_called_once_with(config_text)


@pytest.mark.asyncio
async def test_autofill_service_get_server_defaults(mock_autofill_service):
    """Test that AutoFillService provides default values."""
    # Arrange
    mock_db = Mock()
    
    # Act
    defaults = await mock_autofill_service.get_server_defaults(mock_db)
    
    # Assert
    assert "listen_port" in defaults
    assert defaults["listen_port"] == 51820
    assert "address" in defaults
    mock_autofill_service.get_server_defaults.assert_called_once_with(mock_db)


@pytest.mark.asyncio
async def test_audit_service_logs_action(mock_audit_service):
    """Test that AuditService.log_action can be called without side effects."""
    # Arrange
    mock_db = Mock()
    mock_user = Mock(id=1, username="testuser")
    
    # Act
    await mock_audit_service.log_action(
        mock_db, mock_user, "CREATE", "server", 1, "test-server", 
        {"port": 51820}, None
    )
    
    # Assert
    mock_audit_service.log_action.assert_called_once()


# Example integration test structure (requires full setup)
"""
@pytest.mark.asyncio
async def test_create_server_endpoint_integration(
    mock_wireguard_service,
    mock_audit_service,
    mock_bounce_routing_service
):
    '''
    Example of how to test an API endpoint with mocked services.
    This would require a test client and database setup.
    '''
    # This demonstrates the pattern - actual implementation needs:
    # - Test FastAPI client
    # - Test database session
    # - Dependency overrides
    pass
"""
