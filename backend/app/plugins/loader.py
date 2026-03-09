"""
Plugin loader for discovering and loading plugins from the filesystem.
"""
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type

from .base import _plugin_registry, PluginMetadata

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Handles discovery and loading of plugins from the filesystem.
    """
    
    def __init__(self):
        self.discovered_plugins: Dict[str, Dict] = {}  # module_name -> plugin_info
    
    def discover_plugins(self, plugins_directory: str) -> List[Dict]:
        """
        Scan the plugins directory for valid plugin files.
        
        Returns a list of discovered plugin info dictionaries.
        
        Args:
            plugins_directory: Path to the directory containing plugins
            
        Returns:
            List of plugin info dicts with keys:
            - module_name: str
            - file_path: str
            - plugin_class: type
            - metadata: PluginMetadata
            - requirements: List[str] (from requirements.txt)
        """
        plugins_path = Path(plugins_directory)
        
        if not plugins_path.exists():
            logger.warning(f"Plugins directory does not exist: {plugins_directory}")
            os.makedirs(plugins_path, exist_ok=True)
            logger.info(f"Created plugins directory: {plugins_directory}")
            return []
        
        if not plugins_path.is_dir():
            logger.error(f"Plugins path is not a directory: {plugins_directory}")
            return []
        
        discovered = []
        
        # Scan for plugin subdirectories
        for item in plugins_path.iterdir():
            if not item.is_dir():
                continue
            
            # Skip hidden directories and __pycache__
            if item.name.startswith('.') or item.name == '__pycache__':
                continue
            
            # Look for plugin.py in this directory
            plugin_file = item / "plugin.py"
            if not plugin_file.exists():
                logger.debug(f"Skipping {item.name}: no plugin.py found")
                continue
            
            # Try to load this plugin
            try:
                plugin_info = self._load_plugin_file(item.name, str(plugin_file))
                if plugin_info:
                    # Check for requirements.txt
                    requirements_file = item / "requirements.txt"
                    if requirements_file.exists():
                        plugin_info['requirements'] = self._parse_requirements(
                            str(requirements_file)
                        )
                    else:
                        plugin_info['requirements'] = []
                    
                    discovered.append(plugin_info)
                    self.discovered_plugins[item.name] = plugin_info
                    logger.info(f"Discovered plugin: {plugin_info['metadata'].name} ({item.name})")
            except Exception as e:
                logger.error(f"Error loading plugin from {item.name}: {e}", exc_info=True)
                continue
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    def _load_plugin_file(self, module_name: str, file_path: str) -> Optional[Dict]:
        """
        Load a plugin file and extract metadata.
        
        Args:
            module_name: Name for the module (e.g., "slack_notifier")
            file_path: Full path to the plugin.py file
            
        Returns:
            Plugin info dict or None if invalid
        """
        # Import the module
        spec = importlib.util.spec_from_file_location(f"linguard_plugin_{module_name}", file_path)
        if not spec or not spec.loader:
            logger.error(f"Could not load spec for {file_path}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        
        # Add to sys.modules so relative imports work
        sys.modules[f"linguard_plugin_{module_name}"] = module
        
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error executing module {module_name}: {e}", exc_info=True)
            return None
        
        # Find plugin classes (those decorated with @plugin)
        plugin_classes = []
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj in _plugin_registry:
                plugin_classes.append(obj)
        
        if not plugin_classes:
            logger.warning(f"No @plugin decorated classes found in {file_path}")
            return None
        
        if len(plugin_classes) > 1:
            logger.warning(f"Multiple plugin classes found in {file_path}, using first one")
        
        plugin_class = plugin_classes[0]
        metadata = _plugin_registry[plugin_class]
        
        # Extract event handlers from the class
        self._extract_event_handlers(plugin_class, metadata)
        
        # Get config schema if available
        config_schema = None
        if hasattr(plugin_class, 'get_config_schema'):
            try:
                # Try to call it as a static/class method
                if callable(plugin_class.get_config_schema):
                    config_schema = plugin_class.get_config_schema()
            except Exception as e:
                logger.warning(f"Could not get config schema for {metadata.name}: {e}")
        
        return {
            'module_name': module_name,
            'file_path': file_path,
            'plugin_class': plugin_class,
            'metadata': metadata,
            'config_schema': config_schema,
            'requirements': []  # Will be populated by caller
        }
    
    def _extract_event_handlers(self, plugin_class: Type, metadata: PluginMetadata):
        """
        Extract event handlers from plugin class methods.
        
        Looks for methods decorated with @on_event and registers them.
        """
        for name, method in inspect.getmembers(plugin_class, inspect.isfunction):
            if hasattr(method, '_is_event_handler'):
                event_types = getattr(method, '_event_types', [])
                metadata.add_event_handler(event_types, method)
                logger.debug(f"Registered handler {name} for events: {event_types}")
    
    def _parse_requirements(self, requirements_file: str) -> List[str]:
        """
        Parse a requirements.txt file.
        
        Returns list of package specifications.
        """
        requirements = []
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        requirements.append(line)
        except Exception as e:
            logger.error(f"Error parsing requirements file {requirements_file}: {e}")
        
        return requirements
    
    def get_plugin_subscribed_events(self, plugin_class: Type) -> List[str]:
        """
        Get list of event types this plugin subscribes to.
        
        Args:
            plugin_class: The plugin class
            
        Returns:
            List of event type strings (e.g., ["server.created", "peer.connected"])
        """
        if plugin_class not in _plugin_registry:
            return []
        
        metadata = _plugin_registry[plugin_class]
        event_types = list(metadata.event_handlers.keys())
        
        # Expand "*" wildcard if present
        if "*" in event_types:
            # For now, we'll keep "*" as-is and handle it in the manager
            pass
        
        return event_types
    
    def instantiate_plugin(self, plugin_class: Type, context) -> object:
        """
        Create an instance of a plugin class.
        
        Args:
            plugin_class: The plugin class to instantiate
            context: PluginContext to pass to the plugin
            
        Returns:
            Plugin instance
        """
        try:
            # Check if __init__ takes a context parameter
            sig = inspect.signature(plugin_class.__init__)
            params = list(sig.parameters.keys())
            
            if len(params) > 1:  # More than just 'self'
                # Assume it takes context
                return plugin_class(context)
            else:
                # No parameters, just instantiate
                return plugin_class()
        except Exception as e:
            logger.error(f"Error instantiating plugin {plugin_class._plugin_name}: {e}", exc_info=True)
            raise
