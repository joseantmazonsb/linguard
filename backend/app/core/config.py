"""
Minimal application configuration.

This module only contains application metadata and framework settings.
All user-configurable settings are stored in the database (GlobalSettings model).
Database connection info is stored in linguard.config.json.
"""

import os
from pathlib import Path


class Settings:
    """Minimal application settings (not user-configurable)"""
    
    # Application Metadata
    APP_NAME: str = "Linguard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Development/Debug Flags
    DEBUG_BYPASS_FIREWALL: bool = os.getenv("DEBUG_BYPASS_FIREWALL", "false").lower() == "true"
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # Data Directory (for database, backups, logs if using default paths)
    DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"


settings = Settings()

