"""
Base class for Linguard plugins.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class PluginBase(ABC):
    """
    Clase base para todos los plugins de Linguard.

    Todos los plugins deben heredar de esta clase e implementar
    los métodos initialize() y shutdown().
    """

    name: str = ""
    version: str = ""
    author: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    dependencies: Optional[list] = None
    conflicts: Optional[list] = None

    def __init__(self, *args, **kwargs):
        """Inicializa el plugin."""
        self._initialized = False
        self._config: Dict[str, Any] = {}
        super().__init__(*args, **kwargs)

    @property
    def is_initialized(self) -> bool:
        """Verifica si el plugin está inicializado."""
        return self._initialized

    @abstractmethod
    async def initialize(self):
        """
        Método abstracto para inicializar el plugin.

        Debe ser implementado por cada plugin.
        """
        pass

    @abstractmethod
    async def shutdown(self):
        """
        Método abstracto para apagar el plugin.

        Debe ser implementado por cada plugin.
        """
        pass

    def is_reloadable(self) -> bool:
        """
        Verifica si el plugin puede ser recargado.

        Returns:
            True si el plugin puede ser recargado.
        """
        return True

    def get_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuración del plugin.

        Returns:
            Diccionario con la configuración.
        """
        return self._config.copy()

    def set_config(self, config: Dict[str, Any]):
        """
        Establece la configuración del plugin.

        Args:
            config: Nueva configuración.
        """
        self._config = config.copy() if config else {}

    def get_dependencies(self) -> list:
        """
        Obtiene las dependencias del plugin.

        Returns:
            Lista de dependencias.
        """
        return self.dependencies if self.dependencies else []

    def get_conflicts(self) -> list:
        """
        Obtiene los conflictos del plugin.

        Returns:
            Lista de conflictos.
        """
        return self.conflicts if self.conflicts else []

    def get_plugin_type(self) -> str:
        """
        Obtiene el tipo del plugin.

        Returns:
            Tipo del plugin.
        """
        return "standard"

    def get_priority(self) -> int:
        """
        Obtiene la prioridad del plugin.

        Returns:
            Prioridad del plugin (mayor = más prioridad).
        """
        return 0

    async def on_server_started(self, server_id: str):
        """
        Notifica que un servidor fue iniciado.

        Args:
            server_id: ID del servidor.
        """
        pass

    async def on_server_stopped(self, server_id: str):
        """
        Notifica que un servidor fue detenido.

        Args:
            server_id: ID del servidor.
        """
        pass
