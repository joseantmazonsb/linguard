#!/usr/bin/env python3
"""Script to run tests and generate a progress report."""

import subprocess
import sys

def run_tests():
    """Run all tests and capture output."""
    cmd = [
        sys.executable,
        "-m", "pytest",
        "tests/",
        "--tb=no",
        "-q",
        "--no-cov",
        "-p", "no:cacheprovider"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    print(result.stdout)
    print(result.stderr)
    return result

if __name__ == "__main__":
    run_tests()
