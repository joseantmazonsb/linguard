"""
Unit tests for sudo utilities.
These tests verify the behavior of sudo command execution helpers.
"""

import subprocess
import pytest
from unittest.mock import patch, MagicMock
from app.utils.sudo import (
    run_sudo_command,
    check_sudo_access,
    SudoPasswordRequired,
    SudoTimeout,
    DEFAULT_SUDO_TIMEOUT,
)


class TestSudoPasswordRequired:
    """Test SudoPasswordRequired exception."""

    def test_exception_raised(self):
        """Test that exception can be raised."""
        with pytest.raises(SudoPasswordRequired):
            raise SudoPasswordRequired("Test error message")


class TestSudoTimeout:
    """Test SudoTimeout exception."""

    def test_exception_raised(self):
        """Test that exception can be raised."""
        with pytest.raises(SudoTimeout):
            raise SudoTimeout("Test timeout")


class TestSudoTimeoutDefault:
    """Test DEFAULT_SUDO_TIMEOUT constant."""

    def test_timeout_value(self):
        """Test default timeout is 5 seconds."""
        assert DEFAULT_SUDO_TIMEOUT == 5


class TestRunSudoCommandValidCommand:
    """Test run_sudo_command with valid command."""

    @patch("subprocess.run")
    def test_valid_command_returns_result(self, mock_run):
        """Test that valid command returns subprocess result."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        cmd = ["sudo", "iptables", "-L"]
        result = run_sudo_command(cmd)

        assert result == mock_result
        mock_run.assert_called_once()


class TestRunSudoCommandInvalidCommand:
    """Test run_sudo_command with invalid command."""

    def test_command_without_sudo_raises_error(self):
        """Test that command without sudo raises ValueError."""
        with pytest.raises(ValueError):
            run_sudo_command(["iptables", "-L"])

    def test_empty_command_raises_error(self):
        """Test that empty command raises ValueError."""
        with pytest.raises(ValueError):
            run_sudo_command([])


class TestRunSudoCommandAddsNonInteractiveFlag:
    """Test run_sudo_command adds -n flag."""

    @patch("subprocess.run")
    def test_adds_non_interactive_flag(self, mock_run):
        """Test that -n flag is added if not present."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Command without -n flag
        cmd = ["sudo", "iptables", "-L"]
        run_sudo_command(cmd)

        # Check that -n was added
        call_args = mock_run.call_args
        assert "-n" in call_args[0][0]


class TestRunSudoCommandWithInput:
    """Test run_sudo_command with input data."""

    @patch("subprocess.run")
    def test_passes_input_to_command(self, mock_run):
        """Test that input_data is passed to subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        cmd = ["sudo", "wg", "set", "wg0", "private-key", "/dev/stdin"]
        input_data = "test_private_key"
        run_sudo_command(cmd, input_data=input_data)

        # Check that PIPE was used for stdin
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["stdin"] == subprocess.PIPE
        assert call_kwargs["input"] == input_data


class TestRunSudoCommandWithoutInput:
    """Test run_sudo_command without input data."""

    @patch("subprocess.run")
    def test_uses_devnull_for_stdin(self, mock_run):
        """Test that DEVNULL is used when no input_data."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        cmd = ["sudo", "iptables", "-L"]
        run_sudo_command(cmd)

        # Check that DEVNULL was used for stdin
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["stdin"] == subprocess.DEVNULL


class TestRunSudoCommandDetectsPasswordError:
    """Test run_sudo_command detects password requirement."""

    @patch("subprocess.run")
    def test_detects_password_message(self, mock_run):
        """Test that password messages are detected."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "sudo: a password is required"
        mock_run.return_value = mock_result

        with pytest.raises(SudoPasswordRequired):
            run_sudo_command(["sudo", "iptables", "-L"])


class TestRunSudoCommandHandlesTimeout:
    """Test run_sudo_command handles timeout."""

    @patch("subprocess.run")
    def test_timeout_raises_exception(self, mock_run):
        """Test that timeout raises SudoTimeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sudo", "test"], timeout=5)

        with pytest.raises(SudoTimeout):
            run_sudo_command(["sudo", "test"], timeout=5)


class TestRunSudoCommandCustomTimeout:
    """Test run_sudo_command with custom timeout."""

    @patch("subprocess.run")
    def test_custom_timeout_is_used(self, mock_run):
        """Test that custom timeout is passed to subprocess."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        run_sudo_command(["sudo", "test"], timeout=10)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 10


class TestCheckSudoAccessSuccess:
    """Test check_sudo_access when command works."""

    @patch("subprocess.run")
    def test_command_returns_true_when_successful(self, mock_run):
        """Test that True is returned when command succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = check_sudo_access("iptables", ["-L"])

        assert result is True


class TestCheckSudoAccessPasswordRequired:
    """Test check_sudo_access when password is required."""

    @patch("subprocess.run")
    def test_returns_false_when_password_required(self, mock_run):
        """Test that False is returned when password is required."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "password is required"
        mock_run.return_value = mock_result

        result = check_sudo_access("iptables", ["-L"])

        assert result is False


class TestCheckSudoAccessTimeout:
    """Test check_sudo_access when command times out."""

    @patch("subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        """Test that False is returned on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sudo", "test"], timeout=2)

        result = check_sudo_access("test")

        assert result is False


class TestCheckSudoAccessCommandNotFound:
    """Test check_sudo_access when command not found."""

    @patch("subprocess.run")
    def test_returns_false_on_file_not_found(self, mock_run):
        """Test that False is returned when command not found."""
        mock_run.side_effect = FileNotFoundError("Command not found")

        result = check_sudo_access("nonexistent_command")

        assert result is False


class TestCheckSudoAccessWithArgs:
    """Test check_sudo_access with command arguments."""

    @patch("subprocess.run")
    def test_passes_args_to_command(self, mock_run):
        """Test that args are passed to command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = check_sudo_access("iptables", ["-L", "-n"])

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "sudo" in call_args
        assert "-n" in call_args
        assert "iptables" in call_args
        assert "-L" in call_args
        assert "-n" in call_args  # Second -n from args


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
