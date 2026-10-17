"""
Unit tests for Migration Service.

Tests cover:
- Database migrations
- Peer migration
- Configuration migration
- Data export/import
"""

from unittest.mock import MagicMock, patch
import json


class TestMigrationService:
    """Test Migration Service."""
    
    @patch('app.services.migration.db')
    def test_service_initialization(self, mock_db):
        """Test service initialization."""
        from app.services.migration import MigrationService
        
        service = MigrationService(
            ip_management_service=MagicMock(),
            dns_hierarchy_service=MagicMock(),
            audit_service=MagicMock(),
        )
        
        assert service is not None
        
    @patch('app.services.migration.db')
    def test_service_version(self, mock_db):
        """Test service version."""
        from app.services.migration import MigrationService
        
        service = MigrationService(
            ip_management_service=MagicMock(),
            dns_hierarchy_service=MagicMock(),
            audit_service=MagicMock(),
        )
        
        # Should have version attribute
        assert hasattr(service, 'version')
        
    @patch('app.services.migration.db')
    def test_service_get_current_version(self, mock_db):
        """Test getting current version."""
        from app.services.migration import MigrationService
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"version": "1.0.0"}
        mock_db.execute.return_value = mock_result
        
        service = MigrationService(
            ip_management_service=MagicMock(),
            dns_hierarchy_service=MagicMock(),
            audit_service=MagicMock(),
        )
        
        version = service.get_current_version()
        
        assert version == "1.0.0"


class TestDatabaseMigration:
    """Test database migration."""
    
    @patch('app.services.migration.subprocess')
    def test_run_migration(self, mock_subprocess):
        """Test running database migration."""
        from app.services.migration import run_migration
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Run migration
        result = run_migration("1.0.0")
        
        assert result is not None
        
    @patch('app.services.migration.subprocess')
    def test_run_migration_error(self, mock_subprocess):
        """Test running database migration with error."""
        from app.services.migration import run_migration
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=1)
        
        # Run migration with error
        result = run_migration("1.0.0")
        
        # Should return False on error
        assert result is False
        
    @patch('app.services.migration.subprocess')
    @patch('app.services.migration.db')
    def test_check_migration_needed(self, mock_db, mock_subprocess):
        """Test checking if migration is needed."""
        from app.services.migration import check_migration_needed
        
        # Setup mock
        mock_subprocess.check_output.return_value = b"1.0.0\n"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"version": "0.9.0"}
        mock_db.execute.return_value = mock_result
        
        # Check if migration is needed
        result = check_migration_needed()
        
        assert result is True


class TestPeerMigration:
    """Test peer migration."""
    
    @patch('app.services.migration.db')
    def test_migrate_peers(self, mock_db):
        """Test migrating peers."""
        from app.services.migration import migrate_peers
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"id": 1, "name": "peer1", "public_key": "key1"},
            {"id": 2, "name": "peer2", "public_key": "key2"},
        ]
        mock_db.execute.return_value = mock_result
        
        # Migrate peers
        result = migrate_peers()
        
        assert result is not None
        
    @patch('app.services.migration.db')
    def test_migrate_peers_empty(self, mock_db):
        """Test migrating empty peers."""
        from app.services.migration import migrate_peers
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result
        
        # Migrate peers
        result = migrate_peers()
        
        assert result is not None


class TestConfigurationMigration:
    """Test configuration migration."""
    
    @patch('app.services.migration.subprocess')
    def test_migrate_config(self, mock_subprocess):
        """Test migrating configuration."""
        from app.services.migration import migrate_config
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Migrate config
        result = migrate_config("/etc/wireguard/wg0.conf")
        
        assert result is not None
        
    @patch('app.services.migration.subprocess')
    def test_migrate_config_error(self, mock_subprocess):
        """Test migrating configuration with error."""
        from app.services.migration import migrate_config
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=1)
        
        # Migrate config with error
        result = migrate_config("/etc/wireguard/wg0.conf")
        
        assert result is False


class TestDataExport:
    """Test data export."""
    
    @patch('app.services.migration.db')
    def test_export_data(self, mock_db):
        """Test exporting data."""
        from app.services.migration import export_data
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"id": 1, "name": "peer1"},
            {"id": 2, "name": "peer2"},
        ]
        mock_db.execute.return_value = mock_result
        
        # Export data
        data = export_data()
        
        assert data is not None
        
    @patch('app.services.migration.db')
    def test_export_data_json(self, mock_db):
        """Test exporting data as JSON."""
        from app.services.migration import export_data
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"id": 1, "name": "peer1"},
        ]
        mock_db.execute.return_value = mock_result
        
        # Export data as JSON
        data = export_data(as_json=True)
        
        assert isinstance(data, str)
        assert "peer1" in data


class TestDataImport:
    """Test data import."""
    
    @patch('app.services.migration.db')
    @patch('app.services.migration.subprocess')
    def test_import_data(self, mock_subprocess, mock_db):
        """Test importing data."""
        from app.services.migration import import_data
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Import data
        data = {"peers": [{"name": "peer1", "public_key": "key1"}]}
        result = import_data(data)
        
        assert result is not None
        
    @patch('app.services.migration.db')
    @patch('app.services.migration.subprocess')
    def test_import_data_json(self, mock_subprocess, mock_db):
        """Test importing JSON data."""
        from app.services.migration import import_data
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Import JSON data
        data = json.dumps({"peers": [{"name": "peer1", "public_key": "key1"}]})
        result = import_data(data)
        
        assert result is not None


class TestMigrationValidation:
    """Test migration validation."""
    
    def test_valid_migration_version(self):
        """Test valid migration version."""
        from app.services.migration import is_valid_version
        
        # Valid versions
        valid_versions = ["1.0.0", "2.0.0", "10.0.0"]
        
        for version in valid_versions:
            assert is_valid_version(version) is True
            
    def test_invalid_migration_version(self):
        """Test invalid migration version."""
        from app.services.migration import is_valid_version
        
        # Invalid versions
        invalid_versions = ["1.0", "abc", "", None]
        
        for version in invalid_versions:
            assert is_valid_version(version) is False


class TestMigrationBackup:
    """Test migration backup."""
    
    @patch('app.services.migration.subprocess')
    def test_create_backup(self, mock_subprocess):
        """Test creating backup before migration."""
        from app.services.migration import create_backup
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Create backup
        result = create_backup()
        
        assert result is not None
        
    @patch('app.services.migration.subprocess')
    def test_restore_backup(self, mock_subprocess):
        """Test restoring backup after migration failure."""
        from app.services.migration import restore_backup
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Restore backup
        result = restore_backup("/tmp/backup.sql")
        
        assert result is not None


class TestMigrationRollback:
    """Test migration rollback."""
    
    @patch('app.services.migration.subprocess')
    def test_rollback_migration(self, mock_subprocess):
        """Test rolling back migration."""
        from app.services.migration import rollback_migration
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        # Rollback migration
        result = rollback_migration("1.0.0")
        
        assert result is not None
        
    @patch('app.services.migration.subprocess')
    def test_rollback_migration_error(self, mock_subprocess):
        """Test rolling back migration with error."""
        from app.services.migration import rollback_migration
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=1)
        
        # Rollback migration with error
        result = rollback_migration("1.0.0")
        
        assert result is False


class TestMigrationServiceIntegration:
    """Test migration service integration."""
    
    @patch('app.services.migration.subprocess')
    @patch('app.services.migration.db')
    def test_full_migration_flow(self, mock_db, mock_subprocess):
        """Test full migration flow."""
        from app.services.migration import MigrationService
        
        # Setup mocks
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"version": "0.9.0"}
        mock_db.execute.return_value = mock_result
        
        # Create service
        service = MigrationService(
            ip_management_service=MagicMock(),
            dns_hierarchy_service=MagicMock(),
            audit_service=MagicMock(),
        )
        
        # Check if migration needed
        needs_migration = service.check_migration_needed()
        
        assert needs_migration is True
        
    @patch('app.services.migration.subprocess')
    @patch('app.services.migration.db')
    def test_migration_with_peers(self, mock_db, mock_subprocess):
        """Test migration with peer data."""
        from app.services.migration import MigrationService
        
        # Setup mocks
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"id": 1, "name": "peer1", "public_key": "key1"},
        ]
        mock_db.execute.return_value = mock_result
        
        # Create service
        service = MigrationService(
            ip_management_service=MagicMock(),
            dns_hierarchy_service=MagicMock(),
            audit_service=MagicMock(),
        )
        
        # Migrate peers
        peers = service.migrate_peers()
        
        assert peers is not None
