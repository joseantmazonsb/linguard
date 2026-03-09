"""Utilities for safely running sudo commands with timeout and password detection."""

import subprocess
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default timeout for sudo operations (seconds)
DEFAULT_SUDO_TIMEOUT = 5


class SudoPasswordRequired(Exception):
    """Raised when sudo requires a password (passwordless sudo not configured)."""
    pass


class SudoTimeout(Exception):
    """Raised when sudo command times out (likely waiting for password)."""
    pass


def run_sudo_command(
    cmd: List[str],
    timeout: int = DEFAULT_SUDO_TIMEOUT,
    check: bool = True,
    input_data: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Run a sudo command with timeout and password prompt detection.
    
    This function ensures sudo commands don't hang waiting for password input
    and fail fast with clear error messages.
    
    Args:
        cmd: Command to run (should start with "sudo")
        timeout: Command timeout in seconds (default: 5)
        check: Whether to raise exception on non-zero return code
        input_data: Optional stdin data to pass to command
        
    Returns:
        CompletedProcess result
        
    Raises:
        SudoPasswordRequired: If sudo asks for a password
        SudoTimeout: If command times out (likely waiting for password)
        subprocess.CalledProcessError: If check=True and command fails
        
    Example:
        >>> run_sudo_command(["sudo", "iptables", "-L"])
        >>> run_sudo_command(["sudo", "wg", "set", "wg0", "private-key", "/dev/stdin"], 
        ...                  input_data=private_key)
    """
    if not cmd or cmd[0] != "sudo":
        raise ValueError("Command must start with 'sudo'")
    
    # Ensure -n flag is present (non-interactive mode)
    if "-n" not in cmd:
        cmd.insert(1, "-n")
    
    # Prepare environment to prevent any password prompts
    import os
    env = os.environ.copy()
    env['SUDO_ASKPASS'] = '/bin/false'  # Prevent GUI password prompts
    
    try:
        # Use DEVNULL for stdin if no input_data to prevent any interactive prompts
        stdin_arg = subprocess.PIPE if input_data else subprocess.DEVNULL
        
        result = subprocess.run(
            cmd,
            stdin=stdin_arg,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
            env=env
        )
        
        # Detect password prompts in stderr
        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if any(keyword in stderr_lower for keyword in ["password", "sudo:", "authentication"]):
                # Check for explicit password requirement messages
                if "password is required" in stderr_lower or "a password must be entered" in stderr_lower:
                    logger.error(f"❌ Passwordless sudo not configured for: {' '.join(cmd)}")
                    logger.error("   See documentation for sudoers configuration")
                    raise SudoPasswordRequired(f"Command requires password: {' '.join(cmd)}")
        
        return result
        
    except subprocess.TimeoutExpired as e:
        logger.error(f"❌ Command timed out after {timeout}s (likely waiting for password): {' '.join(cmd)}")
        logger.error("   Configure passwordless sudo for WireGuard and iptables commands")
        logger.error("   See /etc/sudoers.d/linguard configuration in documentation")
        raise SudoTimeout(f"Command timed out: {' '.join(cmd)}") from e


def check_sudo_access(command: str, args: Optional[List[str]] = None) -> bool:
    """
    Check if a command can be run with sudo without password.
    
    Uses 'sudo -n' (non-interactive) to test if passwordless sudo is configured.
    
    Args:
        command: Command to check (e.g., "iptables", "wg")
        args: Optional arguments to test with the command
        
    Returns:
        True if command can be run with sudo, False otherwise
        
    Example:
        >>> check_sudo_access("iptables", ["-L", "-n"])
        True
    """
    import os
    
    try:
        test_cmd = ["sudo", "-n", command]
        if args:
            test_cmd.extend(args)
        
        # Prevent any password prompts
        env = os.environ.copy()
        env['SUDO_ASKPASS'] = '/bin/false'
        
        result = subprocess.run(
            test_cmd,
            stdin=subprocess.DEVNULL,  # Close stdin to prevent interactive prompts
            capture_output=True,
            text=True,
            timeout=2,
            env=env
        )
        
        # Check for password requirement in stderr
        if "password is required" in result.stderr.lower():
            return False
        
        # Return code 0 means success, command is accessible
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        # Timeout likely means waiting for password
        return False
    except FileNotFoundError:
        # Command or sudo not found
        return False
    except Exception as e:
        logger.debug(f"sudo access check failed: {e}")
        return False
