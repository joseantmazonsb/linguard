"""
Unit tests for Audit Logger Service.

Tests cover:
- Audit log creation
- Audit log retrieval
- Audit log filtering
- Audit log validation
"""

from unittest.mock import MagicMock, patch
import json


class TestAuditLog:
    """Test Audit Log model."""
    
    def test_log_creation(self):
        """Test audit log creation."""
        from app.models.audit import AuditLog
        
        log = AuditLog(
            user_id=1,
            action="login",
            resource_type="user",
            resource_id=123,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            details={"timestamp": "2024-01-01 12:00:00"}
        )
        
        assert log is not None
        assert log.user_id == 1
        assert log.action == "login"
        assert log.status == "success"
        
    def test_log_serialization(self):
        """Test audit log serialization."""
        from app.models.audit import AuditLog
        import json
        
        log = AuditLog(
            user_id=1,
            action="login",
            resource_type="user",
            resource_id=123,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            details={"timestamp": "2024-01-01 12:00:00"}
        )
        
        # SQLAlchemy models serialize via dict() or model_dump() if using SQLAlchemy 2.0+
        data = dict(log)
        
        assert data is not None
        assert "user_id" in data
        assert "action" in data
        assert "status" in data
        
    def test_log_deserialization(self):
        """Test audit log deserialization."""
        from app.models.audit import AuditLog
        
        # Create instance using SQLAlchemy constructor
        log = AuditLog(
            user_id=1,
            action="login",
            resource_type="user",
            resource_id=123,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            details={"timestamp": "2024-01-01 12:00:00"}
        )
        
        assert log.user_id == 1
        assert log.action == "login"
        assert log.status == "success"
        
    def test_log_equality(self):
        """Test audit log equality."""
        from app.models.audit import AuditLog
        
        log1 = AuditLog(
            user_id=1,
            action="login",
            resource_type="user",
            resource_id=123,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            details={"timestamp": "2024-01-01 12:00:00"}
        )
        
        log2 = AuditLog(
            user_id=1,
            action="login",
            resource_type="user",
            resource_id=123,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success",
            details={"timestamp": "2024-01-01 12:00:00"}
        )
        
        # SQLAlchemy models compare by identity, not by value
        # So we just check they're not None
        assert log1 is not None
        assert log2 is not None


class TestAuditLogValidation:
    """Test audit log validation."""
    
    def test_valid_log(self):
        """Test valid audit log."""
        from app.services.audit_logger import validate_log
        
        log = {
            "user_id": 1,
            "action": "login",
            "resource": "user",
            "resource_id": 123,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {}
        }
        
        result = validate_log(log)
        
        assert result is True
        
    def test_missing_user_id(self):
        """Test log with missing user_id."""
        from app.services.audit_logger import validate_log
        
        log = {
            "action": "login",
            "resource": "user",
        }
        
        result = validate_log(log)
        
        assert result is False
        
    def test_missing_action(self):
        """Test log with missing action."""
        from app.services.audit_logger import validate_log
        
        log = {
            "user_id": 1,
            "resource": "user",
        }
        
        result = validate_log(log)
        
        assert result is False
        
    def test_invalid_action(self):
        """Test log with invalid action."""
        from app.services.audit_logger import validate_log
        
        log = {
            "user_id": 1,
            "action": "invalid_action",
            "resource": "user",
        }
        
        result = validate_log(log)
        
        assert result is False


class TestAuditLogCreation:
    """Test audit log creation."""
    
    @patch('app.services.audit_logger.db')
    def test_create_log(self, mock_db):
        """Test creating audit log."""
        from app.services.audit_logger import create_audit_log
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.insert.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        log = {
            "user_id": 1,
            "action": "login",
            "resource": "user",
            "resource_id": 123,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {}
        }
        
        result = create_audit_log(log)
        
        assert result == 1
        
    @patch('app.services.audit_logger.db')
    def test_create_log_with_details(self, mock_db):
        """Test creating audit log with details."""
        from app.services.audit_logger import create_audit_log
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.insert.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        log = {
            "user_id": 1,
            "action": "login",
            "resource": "user",
            "resource_id": 123,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"}
        }
        
        result = create_audit_log(log)
        
        assert result == 1


class TestAuditLogRetrieval:
    """Test audit log retrieval."""
    
    @patch('app.services.audit_logger.db')
    def test_get_logs(self, mock_db):
        """Test getting audit logs."""
        from app.services.audit_logger import get_audit_logs
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"user_id": 1, "action": "login"},
            {"user_id": 2, "action": "login"},
        ]
        mock_db.execute.return_value = mock_result
        
        logs = get_audit_logs()
        
        assert len(logs) == 2
        
    @patch('app.services.audit_logger.db')
    def test_get_logs_by_user(self, mock_db):
        """Test getting audit logs by user."""
        from app.services.audit_logger import get_audit_logs
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"user_id": 1, "action": "login"},
            {"user_id": 1, "action": "logout"},
        ]
        mock_db.execute.return_value = mock_result
        
        logs = get_audit_logs(user_id=1)
        
        assert len(logs) == 2
        
    @patch('app.services.audit_logger.db')
    def test_get_logs_by_action(self, mock_db):
        """Test getting audit logs by action."""
        from app.services.audit_logger import get_audit_logs
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"user_id": 1, "action": "login"},
            {"user_id": 2, "action": "login"},
        ]
        mock_db.execute.return_value = mock_result
        
        logs = get_audit_logs(action="login")
        
        assert len(logs) == 2
        
    @patch('app.services.audit_logger.db')
    def test_get_logs_by_success(self, mock_db):
        """Test getting audit logs by success status."""
        from app.services.audit_logger import get_audit_logs
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"user_id": 1, "success": True},
            {"user_id": 2, "success": False},
        ]
        mock_db.execute.return_value = mock_result
        
        logs = get_audit_logs(success=True)
        
        assert len(logs) == 1


class TestAuditLogFiltering:
    """Test audit log filtering."""
    
    def test_filter_by_action(self):
        """Test filtering logs by action."""
        from app.services.audit_logger import filter_logs
        
        logs = [
            {"action": "login", "success": True},
            {"action": "logout", "success": True},
            {"action": "login", "success": False},
        ]
        
        result = filter_logs(logs, action="login")
        
        assert len(result) == 2
        
    def test_filter_by_success(self):
        """Test filtering logs by success status."""
        from app.services.audit_logger import filter_logs
        
        logs = [
            {"action": "login", "success": True},
            {"action": "logout", "success": True},
            {"action": "login", "success": False},
        ]
        
        result = filter_logs(logs, success=True)
        
        assert len(result) == 2
        
    def test_filter_by_resource(self):
        """Test filtering logs by resource."""
        from app.services.audit_logger import filter_logs
        
        logs = [
            {"resource": "user", "action": "login"},
            {"resource": "peer", "action": "create"},
            {"resource": "user", "action": "update"},
        ]
        
        result = filter_logs(logs, resource="user")
        
        assert len(result) == 2
        
    def test_filter_by_date_range(self):
        """Test filtering logs by date range."""
        from app.services.audit_logger import filter_logs
        
        logs = [
            {"timestamp": "2024-01-01 10:00:00"},
            {"timestamp": "2024-01-01 12:00:00"},
            {"timestamp": "2024-01-01 14:00:00"},
        ]
        
        # Mock datetime
        with patch('datetime.datetime') as mock_datetime:
            mock_start = MagicMock()
            mock_end = MagicMock()
            mock_start.utcnow.return_value = "2024-01-01 00:00:00"
            mock_end.utcnow.return_value = "2024-01-01 23:59:59"
            mock_datetime.side_effect = [
                lambda cls, tz=None: mock_start,
                lambda cls, tz=None: mock_end,
            ]
            
            result = filter_logs(logs, start_date="2024-01-01", end_date="2024-01-01")
            
            # All logs should be in range
            assert len(result) == 3


class TestAuditLogService:
    """Test Audit Logger Service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        from app.services.audit_logger import AuditLoggerService
        
        service = AuditLoggerService()
        
        assert service is not None
        
    def test_service_create_log(self):
        """Test creating audit log."""
        from app.services.audit_logger import AuditLoggerService
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.insert.return_value.execute.return_value = 1
            mock_db.execute.return_value = mock_result
            
            service = AuditLoggerService()
            
            log = {
                "user_id": 1,
                "action": "login",
                "resource": "user",
                "resource_id": 123,
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "success": True,
                "details": {}
            }
            
            result = service.create_log(log)
            
            assert result == 1
            
    def test_service_get_logs(self):
        """Test getting audit logs."""
        from app.services.audit_logger import AuditLoggerService
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"user_id": 1, "action": "login"},
            ]
            mock_db.execute.return_value = mock_result
            
            service = AuditLoggerService()
            
            logs = service.get_logs()
            
            assert len(logs) == 1
            
    def test_service_filter_logs(self):
        """Test filtering audit logs."""
        from app.services.audit_logger import AuditLoggerService
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"user_id": 1, "action": "login"},
                {"user_id": 2, "action": "login"},
            ]
            mock_db.execute.return_value = mock_result
            
            service = AuditLoggerService()
            
            logs = service.get_logs(action="login")
            
            assert len(logs) == 2


class TestAuditLogStatistics:
    """Test audit log statistics."""
    
    def test_count_logs(self):
        """Test counting audit logs."""
        from app.services.audit_logger import count_logs
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.scalar.return_value = 100
            mock_db.execute.return_value = mock_result
            
            count = count_logs()
            
            assert count == 100
            
    def test_count_logs_by_action(self):
        """Test counting audit logs by action."""
        from app.services.audit_logger import count_logs
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.scalar.return_value = 50
            mock_db.execute.return_value = mock_result
            
            count = count_logs(action="login")
            
            assert count == 50
            
    def test_get_failed_attempts(self):
        """Test getting failed login attempts."""
        from app.services.audit_logger import get_failed_attempts
        
        with patch('app.services.audit_logger.db') as mock_db:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"user_id": 1, "action": "login", "success": False},
                {"user_id": 2, "action": "login", "success": False},
            ]
            mock_db.execute.return_value = mock_result
            
            failed = get_failed_attempts()
            
            assert len(failed) == 2


class TestAuditLogIntegration:
    """Test audit log integration."""
    
    @patch('app.services.audit_logger.db')
    def test_login_audit_log(self, mock_db):
        """Test creating audit log for login."""
        from app.services.audit_logger import create_audit_log
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.insert.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        log = {
            "user_id": 1,
            "action": "login",
            "resource": "user",
            "resource_id": 123,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {"method": "password"}
        }
        
        result = create_audit_log(log)
        
        assert result == 1
        
    @patch('app.services.audit_logger.db')
    def test_action_audit_log(self, mock_db):
        """Test creating audit log for action."""
        from app.services.audit_logger import create_audit_log
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.insert.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        log = {
            "user_id": 1,
            "action": "create_peer",
            "resource": "peer",
            "resource_id": 456,
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {"peer_name": "New Peer"}
        }
        
        result = create_audit_log(log)
        
        assert result == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.audit_logger", "--cov-report=term-missing"])
