"""
Simple unit tests for Sudo utilities.

These tests cover the basic functionality of app/utils/sudo.py
"""

from unittest.mock import MagicMock, patch
import pytest

from app.utils.sudo import (
    run_sudo_command,
    check_sudo_access,
    SudoPasswordRequired,
    SudoTimeout,
    DEFAULT_SUDO_TIMEOUT,
)


class TestSudoExceptions:
    """Test sudo exception classes."""
    
    def test_sudo_password_required_exception(self):
        """Test SudoPasswordRequired exception."""
        with pytest.raises(SudoPasswordRequired):
            raise SudoPasswordRequired("Test message")
    
    def test_sudo_timeout_exception(self):
        """Test SudoTimeout exception."""
        with pytest.raises(SudoTimeout):
            raise SudoTimeout("Command timed out")


class TestRunSudoCommand:
    """Test run_sudo_command function."""
    
    def test_command_without_sudo_prefix_raises_error(self):
        """Test that command without sudo prefix raises ValueError."""
        with pytest.raises(ValueError, match="'sudo'"):
            run_sudo_command(["iptables", "-L"])
    
    @patch('subprocess.run')
    def test_successful_command(self, mock_run):
        """Test successful sudo command execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"output"
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        
        result = run_sudo_command(["sudo", "-n", "iptables", "-L"])
        
        assert result.returncode == 0
        assert result.stdout == b"output"
    
    @patch('subprocess.run')
    def test_command_with_input_data(self, mock_run):
        """Test sudo command with input data."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        
        result = run_sudo_command(
            ["sudo", "-n", "wg", "show"],
            input_data="private-key-data"
        )
        
        mock_run.assert_called()


class TestCheckSudoAccess:
    """Test check_sudo_access function."""
    
    def test_successful_access(self):
        """Test that successful access returns True."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = b""
            mock_run.return_value = mock_result
            
            result = check_sudo_access("iptables", ["-L"])
            
            assert result is True
    
    def test_password_required_access(self):
        """Test that password requirement returns False."""
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = b"password is required"
            mock_run.return_value = mock_result
            
            result = check_sudo_access("iptables", ["-L"])
            
            assert result is False
    
    def test_timeout_access(self):
        """Test that timeout returns False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("timeout")
            
            result = check_sudo_access("test")
            
            assert result is False


class TestDefaults:
    """Test default values."""
    
    def test_default_timeout(self):
        """Test that DEFAULT_SUDO_TIMEOUT is set correctly."""
        assert DEFAULT_SUDO_TIMEOUT == 5
