"""
Plugin system for Linguard VPN.

This package provides a decorator-based plugin framework that allows users to
create custom integrations using Python code.
"""

from .base import PluginContext, PluginStorage, on_event, plugin
from .loader import PluginLoader
from .manager import PluginManager

__all__ = [
    "plugin",
    "on_event",
    "PluginContext",
    "PluginStorage",
    "PluginLoader",
    "PluginManager",
]
