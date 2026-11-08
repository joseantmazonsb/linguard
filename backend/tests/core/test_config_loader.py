"""Test configuration loader module."""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

from app.core.config_loader import ConfigLoader


def test_load_config_file_exists(tmp_path):
    """Test loading existing config file."""
    # Create a temporary config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create a test config file
    config_file = config_dir / "linguard.config.json"
    config_content = {
        "database": {
            "type": "sqlite",
            "url": "sqlite+aiosqlite:///test.db"
        }
    }
    
    config_file.write_text(json.dumps(config_content))
    
    # Create config loader pointing to our test file
    loader = ConfigLoader(config_path=str(config_file))
    result = loader.load()
    
    assert result["database"]["type"] == "sqlite"
    assert result["database"]["url"] == "sqlite+aiosqlite:///test.db"


def test_load_config_file_missing(tmp_path):
    """Test loading config file when it doesn't exist (returns defaults)."""
    # Create a temporary directory (no config file)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create config loader pointing to non-existent file
    loader = ConfigLoader(config_path=config_dir / "linguard.config.json")
    result = loader.load()
    
    assert result["database"]["type"] == "sqlite"


def test_load_config_file_invalid_json(tmp_path):
    """Test loading config file with invalid JSON."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create config file with invalid JSON
    config_file = config_dir / "linguard.config.json"
    config_file.write_text("this is not valid json {{{")
    
    loader = ConfigLoader(config_path=str(config_file))
    
    with pytest.raises(RuntimeError):
        loader.load()


def test_load_config_file_not_found_returns_defaults(tmp_path):
    """Test loading config file that doesn't exist (returns defaults)."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create loader pointing to non-existent file
    loader = ConfigLoader(config_path=config_dir / "linguard.config.json")
    
    # When file doesn't exist, return default config
    result = loader.load()
    
    assert result["database"]["type"] == "sqlite"


def test_save_config(tmp_path):
    """Test saving configuration to file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    
    config_content = {
        "database": {
            "type": "postgresql",
            "url": "postgresql://user:pass@localhost:5432/test"
        }
    }
    
    loader = ConfigLoader(config_path=str(config_file))
    loader.save(config_content)
    
    assert config_file.exists()
    
    # Verify the file content
    with open(config_file) as f:
        saved_config = json.load(f)
    
    assert saved_config["database"]["type"] == "postgresql"
    assert saved_config["database"]["url"] == "postgresql://user:pass@localhost:5432/test"


def test_save_config_creates_parent_dirs(tmp_path):
    """Test that save creates parent directories if they don't exist."""
    # Create a temporary directory
    tmp_dir = tmp_path / "parent"
    tmp_dir.mkdir(parents=True)
    
    # Create a new subdirectory
    new_dir = tmp_dir / "new" / "subdir"
    new_dir.mkdir(parents=True, exist_ok=True)
    
    # Set config path to a new temporary directory
    loader = ConfigLoader(config_path=str(new_dir / "config.json"))
    
    config_content = {"database": {"type": "sqlite", "url": "sqlite:///test.db"}}
    
    loader.save(config_content)
    
    # Verify the file was created
    assert loader.config_path.exists()


def test_save_config_overwrites(tmp_path):
    """Test that save overwrites existing config file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    
    config_content = {
        "database": {
            "type": "sqlite",
            "url": "sqlite:///old.db"
        }
    }
    
    loader = ConfigLoader(config_path=str(config_file))
    loader.save(config_content)
    
    # Verify the content
    with open(config_file) as f:
        saved_config = json.load(f)
    
    assert saved_config["database"]["url"] == "sqlite:///old.db"
    
    # Now overwrite with new content
    config_loader = ConfigLoader(config_path=str(config_file))
    config_loader.save({
        "database": {
            "type": "postgresql",
            "url": "postgresql://new:pass@localhost:5432/new"
        }
    })
    
    # Verify it was updated
    with open(config_file) as f:
        saved_config = json.load(f)
    
    assert saved_config["database"]["type"] == "postgresql"
    assert saved_config["database"]["url"] == "postgresql://new:pass@localhost:5432/new"


def test_exists_config_file_exists(tmp_path):
    """Test exists() when config file exists."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    config_file.write_text(json.dumps({}))
    
    loader = ConfigLoader(config_path=str(config_file))
    
    assert loader.exists() is True


def test_exists_config_file_missing(tmp_path):
    """Test exists() when config file doesn't exist."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    loader = ConfigLoader(config_path=config_dir / "linguard.config.json")
    
    assert loader.exists() is False


def test_get_database_url(tmp_path):
    """Test get_database_url() method."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    config_file.write_text(json.dumps({
        "database": {
            "type": "sqlite",
            "url": "sqlite:///test.db"
        }
    }))
    
    loader = ConfigLoader(config_path=str(config_file))
    url = loader.get_database_url()
    
    assert url == "sqlite:///test.db"


def test_get_database_type(tmp_path):
    """Test get_database_type() method."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    config_file.write_text(json.dumps({
        "database": {
            "type": "postgresql",
            "url": "postgresql://user:pass@localhost:5432/test"
        }
    }))
    
    loader = ConfigLoader(config_path=str(config_file))
    db_type = loader.get_database_type()
    
    assert db_type == "postgresql"


def test_get_default_database_url(tmp_path):
    """Test get_database_url() with default SQLite config."""
    tmp_dir = tmp_path / "temp_config"
    tmp_dir.mkdir()
    
    loader = ConfigLoader(config_path=str(tmp_dir / "linguard.config.json"))
    
    # Remove any existing config file
    if loader.config_path.exists():
        os.remove(loader.config_path)
    
    url = loader.get_database_url()
    
    assert "sqlite" in url
    assert "aiosqlite" in url


def test_set_database(tmp_path):
    """Test set_database() method."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    config_file = config_dir / "linguard.config.json"
    
    # Ensure no config file exists
    if config_file.exists():
        os.remove(config_file)
    
    loader = ConfigLoader(config_path=str(config_file))
    loader.set_database("mysql", "mysql://root:pass@localhost:3306/linguard")
    
    # Verify the config was saved
    assert config_file.exists()
    
    with open(config_file) as f:
        config = json.load(f)
    
    assert config["database"]["type"] == "mysql"
    assert config["database"]["url"] == "mysql://root:pass@localhost:3306/linguard"
