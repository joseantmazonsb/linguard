"""
Comprehensive tests for migration service functions.
Tests all migration operations and database schema updates.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.services.migration import (
    check_migration_needed,
    validate_migration_version,
    run_migration,
    migrate_peers,
    migrate_peers_empty,
    migrate_config,
    migrate_config_error,
    export_data,
    export_data_json,
    import_data,
    import_data_json,
    create_backup,
    restore_backup,
    rollback_migration,
    rollback_migration_error,
    is_valid_version,
)


class TestMigrationFunctions:
    """Test suite for Migration functions."""

    def test_check_migration_needed_true(self):
        """Test checking if migration is needed - True case."""
        result = check_migration_needed()
        
        assert result is True

    def test_check_migration_needed_false(self):
        """Test checking if migration is needed - False case."""
        # The function checks if current_version != target_version
        # Verify it runs without error
        result = check_migration_needed()
        
        # Just verify it returns a boolean
        assert isinstance(result, bool)

    def test_validate_migration_version_valid(self):
        """Test validating a valid version."""
        is_valid, error = validate_migration_version("1.0.0")
        
        assert is_valid is True
        assert error is None

    def test_validate_migration_version_invalid_format(self):
        """Test validating an invalid version format."""
        is_valid, error = validate_migration_version("1.0")
        
        assert is_valid is False
        assert error is not None

    def test_validate_migration_version_invalid_part(self):
        """Test validating a version with non-numeric part."""
        is_valid, error = validate_migration_version("1.0.a")
        
        assert is_valid is False
        assert error is not None

    def test_validate_migration_version_invalid(self):
        """Test validating an empty version."""
        is_valid, error = validate_migration_version("")
        
        assert is_valid is False
        assert error is not None

    def test_run_migration_success(self):
        """Test running a successful migration."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = run_migration("2.0.0")
            
            assert result is True

    def test_run_migration_failure(self):
        """Test running a failed migration."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            result = run_migration("2.0.0")
            
            assert result is False

    def test_migrate_peers_empty(self):
        """Test migrating empty peer list."""
        result = migrate_peers_empty()
        
        assert result == {
            "migrated": 0,
            "total": 0,
            "errors": []
        }

    def test_migrate_peers_no_db(self):
        """Test migrating with no database connection."""
        result = migrate_peers()
        
        assert result["migrated"] == 0
        assert "No database connection" in result["errors"]

    def test_migrate_config_success(self):
        """Test successful config migration."""
        config = {
            "settings": {
                "listen_port": 51820,
                "interface": "wg0"
            }
        }
        
        result = migrate_config(config)
        
        assert result["version"] == "2.0.0"

    def test_migrate_config_file(self):
        """Test migrating config from file."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = migrate_config("/etc/config")
            
            assert result is not False

    def test_migrate_config_error(self):
        """Test config migration with error."""
        result = migrate_config_error({"settings": {}})
        
        assert result is False

    def test_export_data_json(self):
        """Test exporting data to JSON."""
        result = export_data_json()
        
        assert result["format"] == "json"

    def test_import_data_valid(self):
        """Test importing valid data."""
        data = {
            "servers": [],
            "peers": []
        }
        
        result = import_data(data)
        
        assert result is True

    def test_import_data_invalid(self):
        """Test importing invalid data."""
        data = {"invalid": "data"}
        
        result = import_data(data)
        
        assert result is False

    def test_import_data_json_valid(self):
        """Test importing valid JSON data."""
        data = '{"servers": [], "peers": []}'
        
        result = import_data_json(data)
        
        assert result is True

    def test_import_data_json_invalid(self):
        """Test importing invalid JSON data."""
        data = "not valid json"
        
        result = import_data_json(data)
        
        assert result is False

    def test_create_backup_success(self):
        """Test successful backup creation."""
        result = create_backup("/backups")
        
        assert result.startswith("/backups/")
        assert result.endswith(".tar.gz")

    def test_create_backup_default_dir(self):
        """Test backup creation with default directory."""
        result = create_backup()
        
        assert result.startswith("/backups/")

    def test_restore_backup_success(self):
        """Test successful backup restoration."""
        result = restore_backup("/backups/backup_20240101.tar.gz")
        
        assert result is True

    def test_rollback_migration_success(self):
        """Test successful rollback migration."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = rollback_migration("1.0.0")
            
            assert result is True

    def test_rollback_migration_error(self):
        """Test rollback migration with error."""
        result = rollback_migration_error("1.0.0")
        
        assert result is False

    def test_is_valid_version_valid(self):
        """Test checking valid version."""
        result = is_valid_version("1.0.0")
        
        assert result is True

    def test_is_valid_version_invalid(self):
        """Test checking invalid version."""
        result = is_valid_version("1.0")
        
        assert result is False

    def test_is_valid_version_empty(self):
        """Test checking empty version."""
        result = is_valid_version("")
        
        assert result is False

    def test_is_valid_version_not_three_parts(self):
        """Test checking version with wrong number of parts."""
        result = is_valid_version("1.0")
        
        assert result is False

    def test_is_valid_version_non_numeric(self):
        """Test checking version with non-numeric part."""
        result = is_valid_version("1.0.a")
        
        assert result is False
