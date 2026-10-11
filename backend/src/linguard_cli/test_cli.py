#!/usr/bin/env python3
"""Test script to verify CLI works."""

import py_compile
import os

cli_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

print("Testing Linguard CLI...")
print()

print("1. Testing syntax...")
try:
    py_compile.compile(cli_path, doraise=True)
    print("   ✓ CLI syntax is valid")
    print()
    print("✓ Basic test passed!")
    print()
    print("To use the CLI:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Install CLI: pip install -e .")
    print("  3. Use: linguard --help")
except py_compile.PyCompileError as e:
    print(f"   ✗ Syntax error: {e}")
    print()
    print("✗ Some tests failed")
