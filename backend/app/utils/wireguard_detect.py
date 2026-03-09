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
    - wg-quick (WireGuard quick configuration script)
    
    Checks both common installation paths and PATH environment variable.
    
    Returns:
        Dict with 'wg' and 'wg-quick' keys containing paths or None
        Example: {'wg': '/usr/bin/wg', 'wg-quick': '/usr/bin/wg-quick'}
    """
    result = {
        'wg': None,
        'wg-quick': None
    }
    
    # List of common paths to check for each binary
    common_paths = {
        'wg': [
            '/usr/bin/wg',
            '/usr/local/bin/wg',
            '/bin/wg',
            '/opt/homebrew/bin/wg',  # macOS Homebrew (Apple Silicon)
            '/usr/local/opt/wireguard-tools/bin/wg',  # macOS Homebrew (Intel)
            '/opt/local/bin/wg',  # MacPorts
        ],
        'wg-quick': [
            '/usr/bin/wg-quick',
            '/usr/local/bin/wg-quick',
            '/bin/wg-quick',
            '/opt/homebrew/bin/wg-quick',  # macOS Homebrew (Apple Silicon)
            '/usr/local/opt/wireguard-tools/bin/wg-quick',  # macOS Homebrew (Intel)
            '/opt/local/bin/wg-quick',  # MacPorts
        ]
    }
    
    # Check each binary
    for binary_name, paths in common_paths.items():
        # First, try to find it in PATH using shutil.which
        which_result = shutil.which(binary_name)
        if which_result and os.path.isfile(which_result) and os.access(which_result, os.X_OK):
            result[binary_name] = which_result
            continue
        
        # If not found in PATH, check common paths
        for path in paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                result[binary_name] = path
                break
    
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
        # For 'wg' binary, try 'wg --version'
        if binary_path.endswith('wg') and not binary_path.endswith('wg-quick'):
            result = subprocess.run(
                [binary_path, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # wg --version returns 0 on success
            return result.returncode == 0
        
        # For 'wg-quick', just check if it exists and is executable
        # (wg-quick doesn't have a --version flag in all versions)
        elif 'wg-quick' in binary_path:
            return True
            
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return False
    
    return False


def get_wireguard_paths() -> Dict[str, str]:
    """
    Get WireGuard binary paths, with fallback to defaults.
    
    Returns:
        Dict with 'wg' and 'wg-quick' keys containing paths.
        Falls back to traditional Linux paths if detection fails.
    """
    # Try to detect binaries
    detected = detect_wireguard_binaries()
    
    # Default fallback paths (traditional Linux installation)
    defaults = {
        'wg': '/usr/bin/wg',
        'wg-quick': '/usr/bin/wg-quick'
    }
    
    # Use detected paths if found, otherwise use defaults
    return {
        'wg': detected['wg'] or defaults['wg'],
        'wg-quick': detected['wg-quick'] or defaults['wg-quick']
    }
