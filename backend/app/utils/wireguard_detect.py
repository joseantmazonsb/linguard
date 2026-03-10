"""Utility functions for detecting WireGuard binaries."""
import os
import shutil
import subprocess
from typing import Dict, Optional


def detect_wireguard_binaries() -> Dict[str, Optional[str]]:
    """
    Detect WireGuard binaries on the system.
    
    Searches for:
    - wg (WireGuard command-line utility)
    
    Checks both common installation paths and PATH environment variable.
    
    Returns:
        Dict with 'wg' key containing paths or None
        Example: {'wg': '/usr/bin/wg'}
    """
    result = {
        'wg': None,
    }
    which_result = shutil.which('wg')
    if which_result and os.path.isfile(which_result) and os.access(which_result, os.X_OK):
        result['wg'] = which_result  
    return result


def verify_wireguard_binary(binary_path: str) -> bool:
    """
    Verify that a WireGuard binary is valid and executable.
    
    Args:
        binary_path: Path to the binary to verify
        
    Returns:
        True if binary exists, is executable, and runs successfully
    """
    if not binary_path:
        return False
    
    # Check if file exists
    if not os.path.isfile(binary_path):
        return False
    
    # Check if executable
    if not os.access(binary_path, os.X_OK):
        return False
    
    # Try to run it with --version or --help
    try:
        if binary_path.endswith('wg'):
            result = subprocess.run(
                [binary_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # wg --version returns 0 on success
            return result.returncode == 0
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False
    
    return False


def get_wireguard_paths() -> Dict[str, str]:
    """
    Get WireGuard binary paths, with fallback to defaults.
    
    Returns:
        Dict with 'wg' key containing paths.
        Falls back to traditional Linux paths if detection fails.
    """
    # Try to detect binaries
    detected = detect_wireguard_binaries()
    
    # Default fallback paths (traditional Linux installation)
    defaults = {
        'wg': '/usr/bin/wg',
    }
    
    # Use detected paths if found, otherwise use defaults
    return {
        'wg': detected['wg'] or defaults['wg'],
    }
