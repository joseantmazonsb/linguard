"""Pytest configuration and global fixtures."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load global fixtures
pytest_plugins = [
    "tests.fixtures",
]
