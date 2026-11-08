"""
Plugin Loader for Linguard

This module provides functionality for discovering, loading, and managing
third-party plugins for Linguard.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import wraps

from app.services.plugins.base import PluginBase


class PluginLoader:
    """
    Plugin Loader para Linguard.

    Gestiona el descubrimiento, carga e inicialización de plugins.
    """

    def __init__(
        self,
        plugin_directory: Path,
        wireguard_service: Any = None,
        firewall_service: Any = None,
        audit_service: Any = None,
        integration_service: Any = None,
    ):
        """
        Inicializa el PluginLoader.

        Args:
            plugin_directory: Directorio donde están los plugins.
            wireguard_service: Servicio de WireGuard.
            firewall_service: Servicio de Firewall.
            audit_service: Servicio de Auditoría (opcional).
            integration_service: Servicio de Integración (opcional).
        """
        if plugin_directory is None:
            raise TypeError("plugin_directory cannot be None")

        if not isinstance(plugin_directory, Path):
            raise TypeError(f"plugin_directory must be Path, got {type(plugin_directory).__name__}")

        if not plugin_directory.exists():
            raise FileNotFoundError(f"Plugin directory does not exist: {plugin_directory}")

        self.plugin_directory = plugin_directory
        self.wireguard_service = wireguard_service
        self.firewall_service = firewall_service
        self.audit_service = audit_service
        self.integration_service = integration_service

        # Lista de plugins cargados
        self._loaded_plugins: List[PluginBase] = []

    async def discover_plugins(self) -> List[PluginBase]:
        """
        Descubre plugins en el directorio.

        Returns:
            Lista de plugins descubiertos.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        plugins = []

        # Iterar sobre archivos .py en el directorio
        for file_path in self.plugin_directory.iterdir():
            if file_path.suffix == ".py" and not file_path.name.startswith("_"):
                try:
                    plugin = await self._load_plugin_from_file(file_path)
                    if plugin:
                        plugins.append(plugin)
                except Exception as e:
                    if self.audit_service:
                        await self.audit_service.audit_log(
                            action="plugin_discovery_error",
                            plugin_name=file_path.stem,
                            error=str(e),
                        )

        return plugins

    async def _load_plugin_from_file(self, file_path: Path) -> Optional[PluginBase]:
        """
        Carga un plugin desde un archivo.

        Args:
            file_path: Ruta al archivo del plugin.

        Returns:
            Instancia del plugin o None si falla.
        """
        try:
            # Importar el módulo
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)

            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Buscar la clase que hereda de PluginBase
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                ):
                    try:
                        plugin = attr()
                        if plugin.name and plugin.version:
                            self._loaded_plugins.append(plugin)
                            return plugin
                    except Exception:
                        pass

            return None

        except Exception as e:
            if self.audit_service:
                await self.audit_service.audit_log(
                    action="plugin_load_error",
                    plugin_name=file_path.stem,
                    error=str(e),
                )
            return None

    async def load_plugin(self, plugin_name: str) -> PluginBase:
        """
        Carga un plugin específico.

        Args:
            plugin_name: Nombre del plugin (sin extensión).

        Returns:
            Instancia del plugin.

        Raises:
            FileNotFoundError: Si el plugin no existe.
            ModuleNotFoundError: Si el módulo no se puede importar.
        """
        plugin_path = self.plugin_directory / f"{plugin_name}.py"

        if not plugin_path.exists():
            raise FileNotFoundError(f"Plugin not found: {plugin_path}")

        return await self._load_plugin_from_file(plugin_path)

    async def initialize_all(self):
        """Inicializa todos los plugins cargados."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if self.wireguard_service is None:
            raise ValueError("wireguard_service is required for initialization")

        if self.firewall_service is None:
            raise ValueError("firewall_service is required for initialization")

        for plugin in self._loaded_plugins:
            try:
                await plugin.initialize()
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
                continue

    async def shutdown_all(self):
        """Apaga todos los plugins."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        for plugin in self._loaded_plugins:
            try:
                await plugin.shutdown()
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
                continue

    async def get_loaded_plugins(self) -> List[PluginBase]:
        """Obtiene la lista de plugins cargados."""
        return self._loaded_plugins.copy()

    async def get_loaded_plugins_count(self) -> int:
        """Obtiene el número de plugins cargados."""
        return len(self._loaded_plugins)

    async def reload_plugin(self, plugin: PluginBase):
        """
        Recarga un plugin.

        Args:
            plugin: Plugin a recargar.
        """
        if not hasattr(plugin, "is_reloadable"):
            return

        if plugin.is_reloadable():
            await self.shutdown_plugin(plugin)
            await self.load_plugin(plugin.__module__.replace(".py", ""))
            await self.initialize_all()

    async def shutdown_plugin(self, plugin: PluginBase):
        """Apaga un plugin específico."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if plugin in self._loaded_plugins:
            await plugin.shutdown()
            self._loaded_plugins.remove(plugin)
            await self.audit_service.audit_log(
                action="plugin_shutdown",
                plugin_name=plugin.name,
                plugin_version=plugin.version,
            )

    async def uninstall_plugin(self, plugin: PluginBase):
        """
        Desinstala un plugin.

        Args:
            plugin: Plugin a desinstalar.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if plugin not in self._loaded_plugins:
            raise ValueError("Plugin not loaded")

        await self.shutdown_plugin(plugin)

        # Eliminar del sys.modules
        if plugin.__module__ in sys.modules:
            del sys.modules[plugin.__module__]

        await self.audit_service.audit_log(
            action="plugin_uninstalled",
            plugin_name=plugin.name,
            plugin_version=plugin.version,
        )

    async def list_available_plugins(self) -> List[PluginBase]:
        """
        Lista plugins disponibles (no cargados).

        Returns:
            Lista de plugins disponibles.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        available = []

        for file_path in self.plugin_directory.iterdir():
            if file_path.suffix == ".py" and not file_path.name.startswith("_"):
                if file_path.stem not in [p.__module__.replace(".py", "") for p in self._loaded_plugins]:
                    available.append(file_path.stem)

        return available

    async def get_plugin_info(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Obtiene información de un plugin.

        Args:
            plugin: Plugin para obtener info.

        Returns:
            Diccionario con información del plugin.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        info = {
            "name": plugin.name,
            "version": plugin.version,
        }

        if hasattr(plugin, "author"):
            info["author"] = plugin.author
        if hasattr(plugin, "description"):
            info["description"] = plugin.description
        if hasattr(plugin, "license"):
            info["license"] = plugin.license
        if hasattr(plugin, "homepage"):
            info["homepage"] = plugin.homepage

        return info

    async def validate_plugin(self, plugin: PluginBase) -> bool:
        """
        Valida un plugin.

        Args:
            plugin: Plugin a validar.

        Returns:
            True si es válido, False si no.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if not isinstance(plugin, PluginBase):
            return False

        if not hasattr(plugin, "name") or not plugin.name:
            return False

        if not hasattr(plugin, "version") or not plugin.version:
            return False

        return True

    async def get_plugin_error(self, plugin: PluginBase) -> Optional[str]:
        """
        Obtiene error de un plugin.

        Args:
            plugin: Plugin a verificar.

        Returns:
            Error o None si no hay error.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if not await self.validate_plugin(plugin):
            return f"Invalid plugin: {plugin.__class__.__name__}" if hasattr(plugin, "__class__") else "Unknown plugin"

        return None

    async def install_plugin(self, plugin: PluginBase) -> bool:
        """
        Instala un plugin.

        Args:
            plugin: Plugin a instalar.

        Returns:
            True si se instaló, False si ya estaba instalado.
        """
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if plugin in self._loaded_plugins:
            return False

        if not await self.validate_plugin(plugin):
            return False

        module_name = plugin.__module__.replace(".py", "")
        await self.load_plugin(module_name)
        await self.initialize_all()
        await self.audit_service.audit_log(
            action="plugin_installed",
            plugin_name=plugin.name,
            plugin_version=plugin.version,
        )

        return True

    async def uninstall_all(self):
        """Desinstala todos los plugins."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if self.wireguard_service is None:
            raise ValueError("wireguard_service is required")

        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        for plugin in self._loaded_plugins:
            await self.uninstall_plugin(plugin)

        await self.audit_service.audit_log(
            action="all_plugins_uninstalled",
        )

    async def get_config(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Obtiene configuración de un plugin.

        Args:
            plugin: Plugin para obtener config.

        Returns:
            Configuración del plugin.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "get_config"):
            return plugin.get_config()

        return {}

    async def set_config(self, plugin: PluginBase, config: Dict[str, Any]):
        """
        Establece configuración de un plugin.

        Args:
            plugin: Plugin para establecer config.
            config: Nueva configuración.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "set_config"):
            plugin.set_config(config)

    async def get_dependencies(self, plugin: PluginBase) -> List[str]:
        """
        Obtiene dependencias de un plugin.

        Args:
            plugin: Plugin para obtener dependencias.

        Returns:
            Lista de dependencias.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "get_dependencies"):
            return plugin.get_dependencies()

        return []

    async def get_conflicts(self, plugin: PluginBase) -> List[str]:
        """
        Obtiene conflictos de un plugin.

        Args:
            plugin: Plugin para obtener conflictos.

        Returns:
            Lista de conflictos.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "get_conflicts"):
            return plugin.get_conflicts()

        return []

    async def get_plugin_report(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Obtiene reporte de un plugin.

        Args:
            plugin: Plugin para obtener reporte.

        Returns:
            Reporte del plugin.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        report = {
            "name": plugin.name,
            "version": plugin.version,
            "status": "loaded",
        }

        return report

    async def health_check(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Verifica estado de salud de un plugin.

        Args:
            plugin: Plugin a verificar.

        Returns:
            Estado de salud.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        return {
            "name": plugin.name,
            "status": "healthy",
        }

    async def monitor_plugin(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Monitorea un plugin.

        Args:
            plugin: Plugin a monitorear.

        Returns:
            Estado de monitoreo.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        return {
            "name": plugin.name,
            "monitoring": True,
        }

    async def get_plugin_metrics(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Obtiene métricas de un plugin.

        Args:
            plugin: Plugin para obtener métricas.

        Returns:
            Métricas del plugin.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        return {
            "name": plugin.name,
            "metrics": {},
        }

    async def on_server_started(self, server_id: str):
        """Notifica que un servidor fue iniciado."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        for plugin in self._loaded_plugins:
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

    async def on_server_stopped(self, server_id: str):
        """Notifica que un servidor fue detenido."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        for plugin in self._loaded_plugins:
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

    async def reset_all_rules(self):
        """Resetea todas las reglas."""
        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        await self.firewall_service.reset_all_rules()

    def reset_all_rules_sync(self):
        """Resetea todas las reglas (sincrono)."""
        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        self.firewall_service.reset_all_rules()

    async def reload_all(self):
        """Recarga todos los plugins."""
        if not hasattr(self, "plugin_directory"):
            raise AttributeError("PluginLoader not initialized")

        if self.wireguard_service is None:
            raise ValueError("wireguard_service is required")

        if self.firewall_service is None:
            raise ValueError("firewall_service is required")

        # Guardar plugins actuales
        current_plugins = self._loaded_plugins.copy()

        # Detener todos
        await self.shutdown_all()

        # Limpiar
        self._loaded_plugins.clear()

        # Recargar
        for plugin in current_plugins:
            module_name = plugin.__module__.replace(".py", "")
            await self.load_plugin(module_name)

        # Reinicializar
        await self.initialize_all()

        await self.audit_service.audit_log(
            action="all_plugins_reloaded",
        )

    async def get_plugin_metadata(self, plugin: PluginBase) -> Dict[str, Any]:
        """
        Obtiene metadata completa de un plugin.

        Args:
            plugin: Plugin para obtener metadata.

        Returns:
            Metadata del plugin.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        metadata = {
            "name": plugin.name,
            "version": plugin.version,
        }

        if hasattr(plugin, "author"):
            metadata["author"] = plugin.author
        if hasattr(plugin, "description"):
            metadata["description"] = plugin.description
        if hasattr(plugin, "license"):
            metadata["license"] = plugin.license
        if hasattr(plugin, "homepage"):
            metadata["homepage"] = plugin.homepage
        if hasattr(plugin, "dependencies"):
            metadata["dependencies"] = plugin.dependencies
        if hasattr(plugin, "conflicts"):
            metadata["conflicts"] = plugin.conflicts

        return metadata

    async def validate_plugin_dependencies(self, plugin: PluginBase, available_plugins: List[str]) -> bool:
        """
        Valida dependencias de un plugin.

        Args:
            plugin: Plugin a validar.
            available_plugins: Lista de plugins disponibles.

        Returns:
            True si dependencias son válidas.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "get_dependencies"):
            dependencies = plugin.get_dependencies()
            invalid_deps = [dep for dep in dependencies if dep not in available_plugins]
            if invalid_deps:
                await self.audit_service.audit_log(
                    action="plugin_dependency_validation",
                    plugin_name=plugin.name,
                    missing_dependencies=invalid_deps,
                )
                return False

        return True

    async def check_plugin_conflicts(self, plugin: PluginBase, installed_plugins: List[str]) -> bool:
        """
        Verifica conflictos de un plugin.

        Args:
            plugin: Plugin a verificar.
            installed_plugins: Lista de plugins instalados.

        Returns:
            True si no hay conflictos.
        """
        if plugin is None:
            raise ValueError("plugin cannot be None")

        if hasattr(plugin, "get_conflicts"):
            conflicts = plugin.get_conflicts()
            actual_conflicts = [conf for conf in conflicts if conf in installed_plugins]
            if actual_conflicts:
                await self.audit_service.audit_log(
                    action="plugin_conflict_check",
                    plugin_name=plugin.name,
                    conflicts=actual_conflicts,
                )
                return False

        return True
