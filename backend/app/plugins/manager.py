"""
Plugin manager for loading, managing, and dispatching events to plugins.
"""
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..models.plugin import Plugin
from .base import PluginContext, PluginStorage, _plugin_registry
from .loader import PluginLoader

logger = logging.getLogger(__name__)


class LoadedPluginInstance:
    """Represents a loaded plugin instance with its metadata."""
    
    def __init__(
        self,
        db_id: int,
        name: str,
        plugin_class: type,
        instance: object,
        context: PluginContext,
        subscribed_events: List[str]
    ):
        self.db_id = db_id
        self.name = name
        self.plugin_class = plugin_class
        self.instance = instance
        self.context = context
        self.subscribed_events = subscribed_events
    
    def get_handlers_for_event(self, event_type: str) -> List[Callable]:
        """Get all handler methods for a specific event type."""
        if self.plugin_class not in _plugin_registry:
            return []
        
        metadata = _plugin_registry[self.plugin_class]
        handlers = []
        
        # Check for exact match
        if event_type in metadata.event_handlers:
            handlers.extend(metadata.event_handlers[event_type])
        
        # Check for wildcard subscription
        if "*" in metadata.event_handlers:
            handlers.extend(metadata.event_handlers["*"])
        
        return handlers


class PluginManager:
    """
    Manages the lifecycle of plugins: discovery, loading, execution, and error handling.
    """
    
    def __init__(self, db_session_factory: Callable):
        """
        Initialize the plugin manager.
        
        Args:
            db_session_factory: Callable that returns a new AsyncSession
        """
        self._db_session_factory = db_session_factory
        self.loader = PluginLoader()
        self.loaded_plugins: Dict[int, LoadedPluginInstance] = {}  # plugin_id -> instance
        self._event_handlers_registered = False
    
    async def discover_plugins(self, plugins_directory: str, db: AsyncSession) -> int:
        """
        Discover plugins in the directory and register them in the database.
        
        Args:
            plugins_directory: Path to plugins directory
            db: Database session
            
        Returns:
            Number of newly discovered plugins
        """
        logger.info(f"Discovering plugins in: {plugins_directory}")
        
        # Discover plugins from filesystem
        discovered = self.loader.discover_plugins(plugins_directory)
        
        newly_added = 0
        
        for plugin_info in discovered:
            metadata = plugin_info['metadata']
            module_name = plugin_info['module_name']
            
            # Check if plugin already exists in database
            result = await db.execute(
                select(Plugin).where(Plugin.module_name == module_name)
            )
            existing_plugin = result.scalar_one_or_none()
            
            # Get subscribed events
            subscribed_events = self.loader.get_plugin_subscribed_events(
                plugin_info['plugin_class']
            )
            
            if existing_plugin:
                # Update existing plugin info
                existing_plugin.name = metadata.name
                existing_plugin.version = metadata.version
                existing_plugin.description = metadata.description
                existing_plugin.author = metadata.author
                existing_plugin.file_path = plugin_info['file_path']
                existing_plugin.config_schema = plugin_info['config_schema']
                existing_plugin.subscribed_events = subscribed_events
                existing_plugin.requirements = plugin_info['requirements']
                logger.info(f"Updated existing plugin: {metadata.name}")
            else:
                # Create new plugin entry
                new_plugin = Plugin(
                    name=metadata.name,
                    version=metadata.version,
                    description=metadata.description,
                    author=metadata.author,
                    module_name=module_name,
                    file_path=plugin_info['file_path'],
                    config_schema=plugin_info['config_schema'],
                    config={},  # Empty config initially
                    enabled=False,  # Disabled by default
                    subscribed_events=subscribed_events,
                    requirements=plugin_info['requirements']
                )
                db.add(new_plugin)
                newly_added += 1
                logger.info(f"Added new plugin: {metadata.name}")
        
        await db.commit()
        logger.info(f"Plugin discovery complete: {newly_added} new, {len(discovered) - newly_added} updated")
        
        return newly_added
    
    async def load_enabled_plugins(self, db: AsyncSession):
        """
        Load all enabled plugins into memory.
        
        Args:
            db: Database session
        """
        logger.info("Loading enabled plugins...")
        
        # Get all enabled plugins
        result = await db.execute(
            select(Plugin).where(Plugin.enabled == True)
        )
        enabled_plugins = result.scalars().all()
        
        loaded_count = 0
        for plugin in enabled_plugins:
            try:
                success = await self.load_plugin(plugin, db)
                if success:
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin.name}: {e}", exc_info=True)
                plugin.loaded = False
                await db.commit()
        
        logger.info(f"Loaded {loaded_count}/{len(enabled_plugins)} enabled plugins")
        
        # Register event handlers with event bus
        if loaded_count > 0:
            self._register_event_handlers()
    
    async def load_plugin(self, plugin: Plugin, db: AsyncSession) -> bool:
        """
        Load a single plugin into memory.
        
        Args:
            plugin: Plugin database model
            db: Database session
            
        Returns:
            True if successfully loaded
        """
        try:
            logger.info(f"Loading plugin: {plugin.name}")
            
            # Re-discover this specific plugin to get the class
            plugin_info = self.loader._load_plugin_file(
                plugin.module_name,
                plugin.file_path
            )
            
            if not plugin_info:
                logger.error(f"Failed to load plugin file for {plugin.name}")
                return False
            
            # Create plugin storage
            storage = PluginStorage(plugin.id, self._db_session_factory)
            
            # Create plugin context
            context = PluginContext(
                plugin_id=plugin.id,
                plugin_name=plugin.name,
                config=plugin.config or {},
                storage=storage,
                db_session_factory=self._db_session_factory
            )
            
            # Instantiate the plugin
            instance = self.loader.instantiate_plugin(
                plugin_info['plugin_class'],
                context
            )
            
            # Store loaded plugin
            loaded_plugin = LoadedPluginInstance(
                db_id=plugin.id,
                name=plugin.name,
                plugin_class=plugin_info['plugin_class'],
                instance=instance,
                context=context,
                subscribed_events=plugin.subscribed_events or []
            )
            
            self.loaded_plugins[plugin.id] = loaded_plugin
            
            # Update database
            plugin.loaded = True
            await db.commit()
            
            logger.info(f"Successfully loaded plugin: {plugin.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading plugin {plugin.name}: {e}", exc_info=True)
            plugin.loaded = False
            await db.commit()
            return False
    
    async def unload_plugin(self, plugin_id: int, db: AsyncSession) -> bool:
        """
        Unload a plugin from memory.
        
        Args:
            plugin_id: Database ID of the plugin
            db: Database session
            
        Returns:
            True if successfully unloaded
        """
        if plugin_id not in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_id} not loaded")
            return False
        
        try:
            loaded_plugin = self.loaded_plugins[plugin_id]
            logger.info(f"Unloading plugin: {loaded_plugin.name}")
            
            # Clean up (close HTTP client, etc.)
            if hasattr(loaded_plugin.context, 'http_client'):
                await loaded_plugin.context.http_client.aclose()
            
            # Remove from loaded plugins
            del self.loaded_plugins[plugin_id]
            
            # Update database
            result = await db.execute(
                select(Plugin).where(Plugin.id == plugin_id)
            )
            plugin = result.scalar_one_or_none()
            if plugin:
                plugin.loaded = False
                await db.commit()
            
            logger.info(f"Successfully unloaded plugin: {loaded_plugin.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}", exc_info=True)
            return False
    
    async def unload_all(self):
        """Unload all plugins (called during shutdown)."""
        logger.info("Unloading all plugins...")
        plugin_ids = list(self.loaded_plugins.keys())
        
        async with self._db_session_factory() as db:
            for plugin_id in plugin_ids:
                await self.unload_plugin(plugin_id, db)
        
        logger.info("All plugins unloaded")
    
    async def enable_plugin(self, plugin_id: int, db: AsyncSession) -> bool:
        """
        Enable a plugin and load it.
        
        Args:
            plugin_id: Database ID of the plugin
            db: Database session
            
        Returns:
            True if successfully enabled and loaded
        """
        result = await db.execute(
            select(Plugin).where(Plugin.id == plugin_id)
        )
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            logger.error(f"Plugin {plugin_id} not found")
            return False
        
        plugin.enabled = True
        await db.commit()
        
        # Load the plugin
        success = await self.load_plugin(plugin, db)
        
        if success and not self._event_handlers_registered:
            self._register_event_handlers()
        
        return success
    
    async def disable_plugin(self, plugin_id: int, db: AsyncSession) -> dict:
        """
        Disable a plugin and unload it.
        Also disables all integrations that use this plugin.
        
        Args:
            plugin_id: Database ID of the plugin
            db: Database session
            
        Returns:
            Dictionary with success status and count of disabled integrations
        """
        from ..models.integration import Integration
        
        result = await db.execute(
            select(Plugin).where(Plugin.id == plugin_id)
        )
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            logger.error(f"Plugin {plugin_id} not found")
            return {"success": False, "disabled_integrations": 0}
        
        # Disable all integrations that use this plugin
        integration_result = await db.execute(
            select(Integration).where(Integration.plugin_id == plugin_id)
        )
        integrations = integration_result.scalars().all()
        
        disabled_count = 0
        for integration in integrations:
            if integration.enabled:
                integration.enabled = False
                disabled_count += 1
                logger.info(f"Disabled integration '{integration.name}' (ID: {integration.id}) because plugin '{plugin.name}' was disabled")
        
        plugin.enabled = False
        await db.commit()
        
        # Unload the plugin
        unload_success = await self.unload_plugin(plugin_id, db)
        
        return {
            "success": unload_success,
            "disabled_integrations": disabled_count
        }
    
    def _register_event_handlers(self):
        """Register this manager to listen to all events from the event bus."""
        if self._event_handlers_registered:
            return
        
        logger.info("Registering plugin event handlers with event bus")
        
        for event_type in EventType:
            event_bus.subscribe(event_type, self._create_event_handler(event_type))
        
        self._event_handlers_registered = True
        logger.info("Plugin event handlers registered")
    
    def _create_event_handler(self, event_type: EventType):
        """Create an event handler function for a specific event type."""
        async def handler(event_data: dict):
            await self._dispatch_event_to_plugins(event_type, event_data)
        return handler
    
    async def _dispatch_event_to_plugins(self, event_type: EventType, event_data: Dict[str, Any]):
        """
        Dispatch an event to all subscribed plugins.
        
        Args:
            event_type: The event type
            event_data: Event payload
        """
        # Find all plugins subscribed to this event
        subscribed_plugins = []
        for plugin_id, loaded_plugin in self.loaded_plugins.items():
            # Check if this plugin subscribes to this event
            if event_type.value in loaded_plugin.subscribed_events or "*" in loaded_plugin.subscribed_events:
                subscribed_plugins.append(loaded_plugin)
        
        if not subscribed_plugins:
            return
        
        logger.debug(f"Dispatching {event_type.value} to {len(subscribed_plugins)} plugins")
        
        # Invoke each plugin
        for loaded_plugin in subscribed_plugins:
            await self._invoke_plugin(loaded_plugin, event_type, event_data)
    
    async def _invoke_plugin(
        self,
        loaded_plugin: LoadedPluginInstance,
        event_type: EventType,
        event_data: Dict[str, Any]
    ):
        """
        Invoke a plugin's event handlers.
        
        Handles errors and updates statistics.
        """
        try:
            # Get handlers for this event
            handlers = loaded_plugin.get_handlers_for_event(event_type.value)
            
            if not handlers:
                return
            
            # Invoke each handler
            for handler in handlers:
                try:
                    # Bind handler to instance and call with context and event_data
                    bound_handler = handler.__get__(loaded_plugin.instance, loaded_plugin.plugin_class)
                    await bound_handler(event_data)
                except Exception as e:
                    logger.error(
                        f"Error in plugin '{loaded_plugin.name}' handler '{handler.__name__}': {e}",
                        exc_info=True
                    )
                    await self._record_plugin_error(loaded_plugin.db_id, str(e))
            
            # Update success statistics
            await self._update_plugin_stats(loaded_plugin.db_id, success=True)
            
        except Exception as e:
            logger.error(f"Error invoking plugin '{loaded_plugin.name}': {e}", exc_info=True)
            await self._record_plugin_error(loaded_plugin.db_id, str(e))
    
    async def _update_plugin_stats(self, plugin_id: int, success: bool = True):
        """Update plugin invocation statistics."""
        try:
            async with self._db_session_factory() as db:
                result = await db.execute(
                    select(Plugin).where(Plugin.id == plugin_id)
                )
                plugin = result.scalar_one_or_none()
                
                if plugin:
                    plugin.total_invocations += 1
                    plugin.last_invoked_at = datetime.utcnow()
                    
                    if not success:
                        plugin.total_errors += 1
                    
                    await db.commit()
        except Exception as e:
            logger.error(f"Error updating plugin stats: {e}")
    
    async def _record_plugin_error(self, plugin_id: int, error_message: str):
        """Record a plugin error."""
        try:
            async with self._db_session_factory() as db:
                result = await db.execute(
                    select(Plugin).where(Plugin.id == plugin_id)
                )
                plugin = result.scalar_one_or_none()
                
                if plugin:
                    plugin.total_errors += 1
                    plugin.last_error_at = datetime.utcnow()
                    plugin.last_error_message = error_message[:1000]  # Truncate if too long
                    
                    await db.commit()
        except Exception as e:
            logger.error(f"Error recording plugin error: {e}")
    
    async def _handle_plugin_error(self, loaded_plugin: LoadedPluginInstance, error: Exception):
        """
        Handle a plugin error (isolate and potentially disable).
        
        For now, just logs the error. In the future, could implement:
        - Auto-disable after N errors
        - Retry with exponential backoff
        - Send notification to admins
        """
        logger.error(
            f"Plugin '{loaded_plugin.name}' encountered error: {error}",
            exc_info=True
        )
        
        # Record the error
        await self._record_plugin_error(loaded_plugin.db_id, str(error))
        
        # TODO: Implement auto-disable logic
        # if loaded_plugin.consecutive_errors > 5:
        #     await self.disable_plugin(loaded_plugin.db_id)
    
    def loaded_count(self) -> int:
        """Get the number of currently loaded plugins."""
        return len(self.loaded_plugins)
    
    def get_loaded_plugin_names(self) -> List[str]:
        """Get names of all loaded plugins."""
        return [p.name for p in self.loaded_plugins.values()]
    
    async def trigger_plugin_for_integration(
        self,
        plugin_id: int,
        event_data: Dict[str, Any]
    ):
        """
        Trigger a specific plugin for an integration.
        Used when plugins are invoked through integrations instead of direct event subscription.
        
        Args:
            plugin_id: Database ID of the plugin
            event_data: Event data to pass to the plugin
        """
        loaded_plugin = self.loaded_plugins.get(plugin_id)
        
        if not loaded_plugin:
            logger.warning(f"Plugin {plugin_id} not loaded, cannot trigger for integration")
            return
        
        # Extract event type from event_data
        event_type_str = event_data.get("event_type")
        if not event_type_str:
            logger.error("Event data missing 'event_type' field")
            return
        
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            logger.error(f"Invalid event type: {event_type_str}")
            return
        
        # Invoke the plugin using the existing invocation method
        await self._invoke_plugin(loaded_plugin, event_type, event_data)
