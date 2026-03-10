"""
Configuration loader for linguard.config.json.

This module handles loading the minimal configuration file that contains
ONLY the database connection settings. All other settings are stored in
the database's GlobalSettings table.
"""

import json
import os
from pathlib import Path
from typing import Literal


class ConfigLoader:
    """Loads configuration from linguard.config.json"""

    CONFIG_FILENAME = "linguard.config.json"
    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / CONFIG_FILENAME

    def __init__(self, config_path: str | Path | None = None):
        """Initialize config loader with optional custom path"""
        if config_path is None:
            self.config_path = self.DEFAULT_CONFIG_PATH
        else:
            self.config_path = Path(config_path)

    def load(self) -> dict:
        """Load configuration from file. Returns default config if file doesn't exist."""
        if not self.config_path.exists():
            return self._get_default_config()
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load {self.CONFIG_FILENAME}: {e}") from e

    def save(self, config: dict) -> None:
        """Save configuration to file"""
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save {self.CONFIG_FILENAME}: {e}") from e

    def _get_default_config(self) -> dict:
        """Get default configuration (SQLite). Does NOT create any directories or files."""
        data_dir = Path(__file__).parent.parent.parent / "data"
        db_path = data_dir / "linguard.db"

        return {
            "database": {
                "type": "sqlite",
                "url": f"sqlite+aiosqlite:///{db_path.absolute()}",
            }
        }

    def exists(self) -> bool:
        """Return True if the config file has been written (i.e. setup has run at least the DB step)."""
        return self.config_path.exists()

    def get_database_url(self) -> str:
        """Get database URL from config"""
        config = self.load()
        return config["database"]["url"]

    def get_database_type(self) -> Literal["sqlite", "postgresql", "mysql"]:
        """Get database type from config"""
        config = self.load()
        return config["database"]["type"]

    def set_database(self, db_type: str, db_url: str) -> None:
        """Set database configuration and save"""
        config = self.load()
        config["database"] = {"type": db_type, "url": db_url}
        self.save(config)


# Global instance
config_loader = ConfigLoader()
