"""Database connection manager for multiple database backends."""
import os
from pathlib import Path
from typing import Optional


class DatabaseManager:
    """Manages database connections for different backends."""
    
    # Default database configurations
    DEFAULT_SQLITE_PATH = "/app/data/linguard.db"
    DEFAULT_POSTGRES_URL = "postgresql+asyncpg://wireguard:wireguard@postgres:5432/wireguard"
    DEFAULT_MYSQL_URL = "mysql+aiomysql://wireguard:wireguard@mysql:3306/wireguard"
    
    @staticmethod
    def get_database_url(
        db_type: str,
        custom_url: Optional[str] = None,
        sqlite_path: Optional[str] = None
    ) -> str:
        """
        Get the appropriate database URL based on type.
        
        Args:
            db_type: Database type (postgresql, sqlite, mysql)
            custom_url: Custom database URL if provided
            sqlite_path: Custom SQLite path if provided
            
        Returns:
            Formatted database URL string
        """
        if custom_url:
            return custom_url
            
        if db_type == "sqlite":
            path = sqlite_path or DatabaseManager.DEFAULT_SQLITE_PATH
            # Ensure directory exists
            db_dir = Path(path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{path}"
            
        elif db_type == "postgresql":
            # Check for environment variables first
            host = os.getenv("POSTGRES_HOST", "postgres")
            port = os.getenv("POSTGRES_PORT", "5432")
            user = os.getenv("POSTGRES_USER", "wireguard")
            password = os.getenv("POSTGRES_PASSWORD", "wireguard")
            database = os.getenv("POSTGRES_DB", "wireguard")
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
            
        elif db_type == "mysql":
            # Check for environment variables first
            host = os.getenv("MYSQL_HOST", "mysql")
            port = os.getenv("MYSQL_PORT", "3306")
            user = os.getenv("MYSQL_USER", "wireguard")
            password = os.getenv("MYSQL_PASSWORD", "wireguard")
            database = os.getenv("MYSQL_DATABASE", "wireguard")
            return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"
            
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    @staticmethod
    def validate_database_url(db_url: str) -> bool:
        """
        Validate database URL format.
        
        Args:
            db_url: Database URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        valid_prefixes = [
            "postgresql+asyncpg://",
            "sqlite+aiosqlite://",
            "mysql+aiomysql://",
        ]
        return any(db_url.startswith(prefix) for prefix in valid_prefixes)
    
    @staticmethod
    def get_driver_name(db_type: str) -> str:
        """
        Get the async driver name for the database type.
        
        Args:
            db_type: Database type
            
        Returns:
            Driver name
        """
        drivers = {
            "postgresql": "asyncpg",
            "sqlite": "aiosqlite",
            "mysql": "aiomysql",
        }
        return drivers.get(db_type, "")
    
    @staticmethod
    def get_required_packages(db_type: str) -> list[str]:
        """
        Get required Python packages for the database type.
        
        Args:
            db_type: Database type
            
        Returns:
            List of required package names
        """
        packages = {
            "postgresql": ["asyncpg"],
            "sqlite": ["aiosqlite"],
            "mysql": ["aiomysql", "cryptography"],
        }
        return packages.get(db_type, [])
