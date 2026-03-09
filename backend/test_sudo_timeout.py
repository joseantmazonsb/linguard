#!/usr/bin/env python3
"""
Test script to verify sudo commands don't hang without passwordless sudo.

This script tests that:
1. Commands timeout quickly (within 5 seconds)
2. No interactive password prompts appear
3. Clear error messages are shown
"""

import subprocess
import time
import os

def test_sudo_hang():
    """Test if sudo command hangs or fails fast."""
    print("=" * 60)
    print("Testing sudo command behavior WITHOUT passwordless sudo")
    print("=" * 60)
    print()
    
    # Prepare environment to prevent password prompts
    env = os.environ.copy()
    env['SUDO_ASKPASS'] = '/bin/false'
    
    test_commands = [
        ["sudo", "-n", "iptables", "-L", "-n"],
        ["sudo", "-n", "wg", "show"],
    ]
    
    for cmd in test_commands:
        print(f"Testing: {' '.join(cmd)}")
        print(f"  Timeout: 5 seconds")
        print(f"  stdin: DEVNULL (closed)")
        print(f"  SUDO_ASKPASS: /bin/false")
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=5,
                env=env
            )
            elapsed = time.time() - start_time
            
            print(f"  ✓ Completed in {elapsed:.2f}s")
            print(f"  Return code: {result.returncode}")
            
            if result.returncode != 0:
                print(f"  stderr: {result.stderr[:200]}")
                if "password" in result.stderr.lower():
                    print("  ✓ Password requirement detected in stderr")
            print()
            
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            print(f"  ✗ TIMEOUT after {elapsed:.2f}s - COMMAND HUNG!")
            print("  This means stdin was not properly closed or -n flag didn't work")
            print()
            return False
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ✗ Error after {elapsed:.2f}s: {e}")
            print()
            return False
    
    print("=" * 60)
    print("✅ All commands failed fast (no hanging)")
    print("=" * 60)
    return True

if __name__ == "__main__":
    print()
    print("This test verifies that sudo commands don't hang when")
    print("passwordless sudo is NOT configured.")
    print()
    print("Expected behavior:")
    print("  - Commands complete within 1-2 seconds")
    print("  - No password prompts appear")
    print("  - Clear error messages in stderr")
    print()
    
    success = test_sudo_hang()
    exit(0 if success else 1)
