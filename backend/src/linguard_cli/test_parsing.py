#!/usr/bin/env python3
"""
Unit tests for Linguard CLI response parsing helpers.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from linguard_cli.main import extract_items


def test_extract_items_with_plain_list():
    """Backend collection endpoints return a plain JSON list."""
    data = [{"id": 1, "name": "wg0"}, {"id": 2, "name": "wg1"}]
    assert extract_items(data) == data


def test_extract_items_with_paginated_dict():
    """Some endpoints return a paginated object with an 'items' key."""
    data = {"items": [{"id": 1}], "total": 1}
    assert extract_items(data) == [{"id": 1}]


def test_extract_items_with_empty_list():
    assert extract_items([]) == []


def test_extract_items_with_itemsless_dict():
    """A dict without 'items' yields an empty list, not a crash."""
    assert extract_items({"total": 0}) == []


def test_extract_items_with_none():
    assert extract_items(None) == []


def run_all_tests():
    tests = [
        test_extract_items_with_plain_list,
        test_extract_items_with_paginated_dict,
        test_extract_items_with_empty_list,
        test_extract_items_with_itemsless_dict,
        test_extract_items_with_none,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
