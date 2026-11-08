"""
Plugin Manager for Linguard

This module provides functionality for managing installed plugins including
configuration, events, dependencies, and lifecycle management.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..plugins.base import PluginBase
from ..plugins.loader import PluginLoader
from ...services.audit_logger import AuditService
from ...models.plugin import Plugin, PluginData


class PluginManager:
    """
    Plugin Manager para Linguard.

    Gestiona el ciclo de vida, configuración y eventos de plugins instalados.
    """

    def __init__(
        self,
        plugin_directory: Path,
        db: AsyncSession,
        wireguard_service: Any = None,
        firewall_service: Any = None,
        audit_service: AuditService = None,
        integration_service: Any = None,
    ):
        """
        Inicializa el PluginManager.

        Args:
            plugin_directory: Directorio donde están los plugins.
            db: Session de base de datos.
            wireguard_service: Servicio de WireGuard.
            firewall_service: Servicio de Firewall.
            audit_service: Servicio de Auditoría.
            integration_service: Servicio de Integración.
        """
        if plugin_directory is None:
            raise TypeError("plugin_directory cannot be None")

        if not isinstance(plugin_directory, Path):
            raise TypeError(f"plugin_directory must be Path, got {type(plugin_directory).__name__}")

        if not plugin_directory.exists():
            raise FileNotFoundError(f"Plugin directory does not exist: {plugin_directory}")

        self.plugin_directory = plugin_directory
        self.db = db
        self.wireguard_service = wireguard_service
        self.firewall_service = firewall_service
        self.audit_service = audit_service
        self.integration_service = integration_service

        self.plugin_loader = PluginLoader(
            plugin_directory=plugin_directory,
            wireguard_service=wireguard_service,
            firewall_service=firewall_service,
            audit_service=audit_service,
            integration_service=integration_service,
        )

        # Diccionario de plugins por nombre de módulo
        self._plugins: Dict[str, PluginBase] = {}
        # Diccionario de plugins por ID
        self._plugins_by_id: Dict[int, PluginBase] = {}

    async def _discover_plugins_from_db(self) -> None:
        """Descubre plugins registrados en la base de datos."""
        result = await self.db.execute(select(Plugin))
        plugins = result.scalars().all()

        for plugin in plugins:
            try:
                plugin_instance = self._load_plugin_instance(plugin.module_name)
                if plugin_instance:
                    self._plugins[plugin.module_name] = plugin_instance
                    self._plugins_by_id[plugin.id] = plugin_instance
            except Exception as e:
                if self.audit_service:
                    await self.audit_service.audit_log(
                        action="plugin_db_discovery_error",
                        plugin_name=plugin.module_name,
                        error=str(e),
                    )

    async def _save_plugin_to_db(self, plugin: PluginBase) -> Plugin:
        """Guarda información del plugin en la base de datos."""
        plugin_instance = self._plugins[plugin.__module__.replace(".py", "")]
        plugin_info = self.plugin_loader.get_plugin_info(plugin_instance)

        # Verificar si el plugin ya existe en la base de datos
        result = await self.db.execute(
            select(Plugin).where(Plugin.module_name == plugin.module_name)
        )
        existing_plugin = result.scalar_one_or_none()

        if existing_plugin:
            # Actualizar plugin existente
            plugin_data = Plugin(
                id=existing_plugin.id,
                name=plugin.name,
                version=plugin.version,
                description=plugin.description,
                author=plugin.author,
                module_name=plugin.module_name,
                file_path=str(self.plugin_directory / f"{plugin.module_name}.py"),
                enabled=existing_plugin.enabled,
                config_schema=existing_plugin.config_schema,
                config=existing_plugin.config,
                subscribed_events=existing_plugin.subscribed_events,
                requirements=existing_plugin.requirements,
            )
            await self.db.refresh(plugin_data)
            return plugin_data
        else:
            # Crear nuevo plugin en la base de datos
            new_plugin = Plugin(
                name=plugin.name,
                version=plugin.version,
                description=plugin.description,
                author=plugin.author,
                module_name=plugin.module_name,
                file_path=str(self.plugin_directory / f"{plugin.module_name}.py"),
                enabled=plugin.enabled,
                config_schema=plugin.config_schema,
                config=plugin.config,
                subscribed_events=plugin.subscribed_events,
                requirements=plugin.requirements,
            )
            self.db.add(new_plugin)
            await self.db.flush()
            return new_plugin

    async def _load_plugin_instance(self, module_name: str) -> Optional[PluginBase]:
        """Carga instancia de un plugin desde el nombre de módulo."""
        plugin_path = self.plugin_directory / f"{module_name}.py"

        if not plugin_path.exists():
            return None

        try:
            return await self.plugin_loader.load_plugin(module_name)
        except Exception as e:
            if self.audit_service:
                await self.audit_service.audit_log(
                    action="plugin_instance_load_error",
                    plugin_name=module_name,
                    error=str(e),
                )
            return None

    async def discover(self) -> List[PluginBase]:
        """
        Descubre todos los plugins en el directorio.

        Returns:
            Lista de plugins descubiertos.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugins = await self.plugin_loader.discover_plugins()
        self._plugins.update({p.__module__.replace(".py", ""): p for p in plugins})
        self._plugins.update({p.__module__.replace(".py", ""): p for p in plugins})

        return plugins

    async def initialize(self) -> List[str]:
        """
        Inicializa todos los plugins.

        Returns:
            Lista de nombres de plugins que fallaron al inicializarse.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        if self.wireguard_service is None:
            raise ValueError("wireguard_service is required for initialization")

        if self.firewall_service is None:
            raise ValueError("firewall_service is required for initialization")

        failed_plugins = []

        for module_name, plugin in self._plugins.items():
            try:
                await plugin.initialize()
                if self.audit_service:
                    await self.audit_service.audit_log(
                        action="plugin_initialized",
                        plugin_name=plugin.name,
                        plugin_version=plugin.version,
                    )
            except Exception as e:
                await self.audit_service.audit_log(
                    action="plugin_init_error",
                    plugin_name=plugin.name,
                    error=str(e),
                )
                failed_plugins.append(module_name)
                continue

        return failed_plugins

    async def shutdown(self) -> List[str]:
        """
        Apaga todos los plugins.

        Returns:
            Lista de nombres de plugins que fallaron al apagarse.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        failed_plugins = []

        for module_name, plugin in self._plugins.items():
            try:
                await plugin.shutdown()
                if self.audit_service:
                    await self.audit_service.audit_log(
                        action="plugin_shutdown",
                        plugin_name=plugin.name,
                        plugin_version=plugin.version,
                    )
            except Exception as e:
                await self.audit_service.audit_log(
                    action="plugin_shutdown_error",
                    plugin_name=plugin.name,
                    error=str(e),
                )
                failed_plugins.append(module_name)
                continue

        return failed_plugins

    async def reload(self) -> List[str]:
        """
        Recarga todos los plugins.

        Returns:
            Lista de nombres de plugins que fallaron al recargarse.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        if self.wireguard_service is None:
            raise ValueError("wireguard_service is required for reload")

        if self.firewall_service is None:
            raise ValueError("firewall_service is required for reload")

        failed_plugins = []

        # Guardar plugins actuales
        current_plugins = list(self._plugins.items())

        # Detener todos
        stop_failed = await self.shutdown()

        # Limpiar
        self._plugins.clear()
        self._plugins_by_id.clear()

        # Recargar
        for module_name, _ in current_plugins:
            try:
                await self.plugin_loader.load_plugin(module_name)
            except Exception as e:
                if self.audit_service:
                    await self.audit_service.audit_log(
                        action="plugin_reload_error",
                        plugin_name=module_name,
                        error=str(e),
                    )
                failed_plugins.append(module_name)
                continue

        # Reinicializar
        init_failed = await self.initialize()

        failed_plugins.extend(init_failed)

        await self.audit_service.audit_log(
            action="all_plugins_reloaded",
        )

        return failed_plugins

    async def get_plugin(self, module_name: str) -> Optional[PluginBase]:
        """
        Obtiene un plugin por nombre de módulo.

        Args:
            module_name: Nombre del módulo del plugin (sin extensión).

        Returns:
            Instancia del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        if module_name in self._plugins:
            return self._plugins[module_name]

        return None

    async def get_all_plugins(self) -> List[PluginBase]:
        """
        Obtiene lista de todos los plugins.

        Returns:
            Lista de todos los plugins.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        return list(self._plugins.values())

    async def get_plugin_info(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Diccionario con información del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_info(plugin)

    async def get_all_plugin_info(self) -> List[Dict[str, Any]]:
        """
        Obtiene información de todos los plugins.

        Returns:
            Lista de diccionarios con información de todos los plugins.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        return [await self.get_plugin_info(module_name) for module_name in self._plugins]

    async def validate_plugin(self, module_name: str) -> bool:
        """
        Valida un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            True si es válido, False si no.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return False

        return await self.plugin_loader.validate_plugin(plugin)

    async def get_plugin_dependencies(self, module_name: str) -> List[str]:
        """
        Obtiene dependencias de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Lista de dependencias.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return []

        return await self.plugin_loader.get_dependencies(plugin)

    async def get_plugin_conflicts(self, module_name: str) -> List[str]:
        """
        Obtiene conflictos de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Lista de conflictos.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return []

        return await self.plugin_loader.get_conflicts(plugin)

    async def get_plugin_report(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene reporte de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Reporte del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_report(plugin)

    async def health_check(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Verifica estado de salud de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Estado de salud o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.health_check(plugin)

    async def monitor_plugin(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Monitorea un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Estado de monitoreo o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.monitor_plugin(plugin)

    async def get_plugin_metrics(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene métricas de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Métricas del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_metrics(plugin)

    async def on_server_started(self, server_id: str) -> List[str]:
        """
        Notifica que un servidor fue iniciado.

        Args:
            server_id: ID del servidor.

        Returns:
            Lista de plugins que fallaron al manejar el evento.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        failed_plugins = []

        for module_name, plugin in self._plugins.items():
            if hasattr(plugin, "on_server_started"):
                try:
                    await plugin.on_server_started(server_id)
                except Exception as e:
                    await self.audit_service.audit_log(
                        action="plugin_event_error",
                        plugin_name=plugin.name,
                        event="on_server_started",
                        error=str(e),
                    )
                    failed_plugins.append(module_name)
                continue

        return failed_plugins

    async def on_server_stopped(self, server_id: str) -> List[str]:
        """
        Notifica que un servidor fue detenido.

        Args:
            server_id: ID del servidor.

        Returns:
            Lista de plugins que fallaron al manejar el evento.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        failed_plugins = []

        for module_name, plugin in self._plugins.items():
            if hasattr(plugin, "on_server_stopped"):
                try:
                    await plugin.on_server_stopped(server_id)
                except Exception as e:
                    await self.audit_service.audit_log(
                        action="plugin_event_error",
                        plugin_name=plugin.name,
                        event="on_server_stopped",
                        error=str(e),
                    )
                    failed_plugins.append(module_name)
                continue

        return failed_plugins

    async def get_config(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene configuración de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Configuración del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_config(plugin)

    async def set_config(self, module_name: str, config: Dict[str, Any]) -> bool:
        """
        Establece configuración de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.
            config: Nueva configuración.

        Returns:
            True si se actualizó, False si no existe o falló.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return False

        if not await self.plugin_loader.validate_plugin(plugin):
            return False

        try:
            await self.plugin_loader.set_config(plugin, config)
            return True
        except Exception as e:
            await self.audit_service.audit_log(
                action="plugin_config_error",
                plugin_name=plugin.name,
                error=str(e),
            )
            return False

    async def get_metadata(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadata completa de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Metadata del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_metadata(plugin)

    async def validate_plugin_dependencies(
        self, module_name: str, available_plugins: List[str]
    ) -> bool:
        """
        Valida dependencias de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.
            available_plugins: Lista de plugins disponibles.

        Returns:
            True si dependencias son válidas.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return False

        return await self.plugin_loader.validate_plugin_dependencies(
            plugin, available_plugins
        )

    async def check_plugin_conflicts(
        self, module_name: str, installed_plugins: List[str]
    ) -> bool:
        """
        Verifica conflictos de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.
            installed_plugins: Lista de plugins instalados.

        Returns:
            True si no hay conflictos.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return False

        return await self.plugin_loader.check_plugin_conflicts(
            plugin, installed_plugins
        )

    async def reset_all_rules(self) -> None:
        """Resetea todas las reglas."""
        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        await self.firewall_service.reset_all_rules()

    def reset_all_rules_sync(self) -> None:
        """Resetea todas las reglas (síncrono)."""
        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        self.firewall_service.reset_all_rules()

    async def get_loaded_plugins_count(self) -> int:
        """
        Obtiene el número de plugins cargados.

        Returns:
            Número de plugins cargados.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        return len(self._plugins)

    async def get_loaded_plugins_list(self) -> List[str]:
        """
        Obtiene la lista de nombres de plugins cargados.

        Returns:
            Lista de nombres de módulos de plugins cargados.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        return list(self._plugins.keys())

    async def get_plugin_type(self, module_name: str) -> Optional[str]:
        """
        Obtiene el tipo de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Tipo del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_type(plugin)

    async def get_plugin_priority(self, module_name: str) -> Optional[int]:
        """
        Obtiene la prioridad de un plugin.

        Args:
            module_name: Nombre del módulo del plugin.

        Returns:
            Prioridad del plugin o None si no existe.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginManager not initialized")

        plugin = await self.get_plugin(module_name)
        if plugin is None:
            return None

        return await self.plugin_loader.get_plugin_priority(plugin)
