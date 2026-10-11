"""
Unit tests for Autofill Service.

Tests cover:
- Autofill configuration
- Autofill rules
- Autofill operations
"""

from unittest.mock import MagicMock, patch


class TestAutofillConfig:
    """Test Autofill configuration."""
    
    def test_config_initialization(self):
        """Test autofill config initialization."""
        from app.services.autofill import AutofillConfig
        
        config = AutofillConfig()
        
        assert config is not None
        
    def test_config_enabled(self):
        """Test autofill enabled status."""
        from app.services.autofill import AutofillConfig
        
        with patch('app.services.autofill.config') as mock_config:
            mock_config.autofill_enabled = True
            
            config = AutofillConfig()
            
            assert config.autofill_enabled is True
            
    def test_config_rules(self):
        """Test autofill rules configuration."""
        from app.services.autofill import AutofillConfig
        
        with patch('app.services.autofill.config') as mock_config:
            mock_config.autofill_rules = [
                {"field": "name", "default": "Test"},
                {"field": "email", "default": "test@example.com"},
            ]
            
            config = AutofillConfig()
            
            assert config.autofill_rules is not None


class TestAutofillRules:
    """Test autofill rules."""
    
    def test_rule_creation(self):
        """Test autofill rule creation."""
        from app.services.autofill import AutofillRule
        
        rule = AutofillRule(
            field="email",
            default="test@example.com",
            required=True
        )
        
        assert rule is not None
        assert rule.field == "email"
        assert rule.default == "test@example.com"
        assert rule.required is True
        
    def test_rule_serialization(self):
        """Test autofill rule serialization."""
        from app.services.autofill import AutofillRule
        import json
        
        rule = AutofillRule(
            field="name",
            default="Test User",
            required=True
        )
        
        data = rule.model_dump()
        
        assert data is not None
        assert "field" in data
        assert "default" in data
        assert "required" in data
        
    def test_rule_deserialization(self):
        """Test autofill rule deserialization."""
        from app.services.autofill import AutofillRule
        
        data = {
            "field": "phone",
            "default": "+1234567890",
            "required": False
        }
        
        rule = AutofillRule(**data)
        
        assert rule.field == "phone"
        assert rule.default == "+1234567890"
        assert rule.required is False
        
    def test_rule_equality(self):
        """Test autofill rule equality."""
        from app.services.autofill import AutofillRule
        
        rule1 = AutofillRule(
            field="email",
            default="test@example.com",
            required=True
        )
        
        rule2 = AutofillRule(
            field="email",
            default="test@example.com",
            required=True
        )
        
        assert rule1 == rule2


class TestAutofillOperations:
    """Test autofill operations."""
    
    @patch('app.services.autofill.db')
    def test_get_rules(self, mock_db):
        """Test getting autofill rules."""
        from app.services.autofill import get_autofill_rules
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {"field": "name", "default": "Test", "required": True},
            {"field": "email", "default": "test@example.com", "required": True},
        ]
        mock_db.execute.return_value = mock_result
        
        rules = get_autofill_rules()
        
        assert len(rules) == 2
        
    @patch('app.services.autofill.db')
    def test_add_rule(self, mock_db):
        """Test adding autofill rule."""
        from app.services.autofill import add_autofill_rule
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.insert.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        rule = {
            "field": "phone",
            "default": "+1234567890",
            "required": False
        }
        
        result = add_autofill_rule(rule)
        
        assert result == 1
        
    @patch('app.services.autofill.db')
    def test_remove_rule(self, mock_db):
        """Test removing autofill rule."""
        from app.services.autofill import remove_autofill_rule
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.delete.return_value.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        result = remove_autofill_rule(1)
        
        assert result == 1
        
    @patch('app.services.autofill.db')
    def test_update_rule(self, mock_db):
        """Test updating autofill rule."""
        from app.services.autofill import update_autofill_rule
        
        # Setup mock
        mock_result = MagicMock()
        mock_result.execute.return_value = 1
        mock_db.execute.return_value = mock_result
        
        rule_id = 1
        rule = {
            "field": "phone",
            "default": "+1234567890",
            "required": False
        }
        
        result = update_autofill_rule(rule_id, rule)
        
        assert result == 1


class TestAutofillValidation:
    """Test autofill validation."""
    
    def test_valid_rule(self):
        """Test valid autofill rule."""
        from app.services.autofill import validate_rule
        
        rule = {
            "field": "email",
            "default": "test@example.com",
            "required": True
        }
        
        result = validate_rule(rule)
        
        assert result is True
        
    def test_missing_field(self):
        """Test rule with missing field."""
        from app.services.autofill import validate_rule
        
        rule = {
            "default": "test@example.com",
            "required": True
        }
        
        result = validate_rule(rule)
        
        assert result is False
        
    def test_missing_default(self):
        """Test rule with missing default."""
        from app.services.autofill import validate_rule
        
        rule = {
            "field": "email",
            "required": True
        }
        
        result = validate_rule(rule)
        
        assert result is False
        
    def test_invalid_field_name(self):
        """Test rule with invalid field name."""
        from app.services.autofill import validate_rule
        
        rule = {
            "field": 123,
            "default": "test@example.com",
            "required": True
        }
        
        result = validate_rule(rule)
        
        assert result is False


class TestAutofillService:
    """Test Autofill Service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        from app.services.autofill import AutofillService
        
        service = AutofillService()
        
        assert service is not None
        
    def test_service_get_rules(self):
        """Test getting autofill rules."""
        from app.services.autofill import AutofillService
        
        with patch('app.services.autofill.db') as mock_db:
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"field": "name", "default": "Test"},
            ]
            mock_db.execute.return_value = mock_result
            
            service = AutofillService()
            
            rules = service.get_rules()
            
            assert len(rules) == 1
            
    def test_service_add_rule(self):
        """Test adding autofill rule."""
        from app.services.autofill import AutofillService
        
        with patch('app.services.autofill.db') as mock_db:
            mock_result = MagicMock()
            mock_result.insert.return_value.execute.return_value = 1
            mock_db.execute.return_value = mock_result
            
            service = AutofillService()
            
            rule = {
                "field": "email",
                "default": "test@example.com",
                "required": True
            }
            
            result = service.add_rule(rule)
            
            assert result == 1
            
    def test_service_remove_rule(self):
        """Test removing autofill rule."""
        from app.services.autofill import AutofillService
        
        with patch('app.services.autofill.db') as mock_db:
            mock_result = MagicMock()
            mock_result.delete.return_value.execute.return_value = 1
            mock_db.execute.return_value = mock_result
            
            service = AutofillService()
            
            result = service.remove_rule(1)
            
            assert result == 1


class TestAutofillApplication:
    """Test autofill application."""
    
    def test_apply_autofill(self):
        """Test applying autofill to form data."""
        from app.services.autofill import apply_autofill
        
        # Mock config
        with patch('app.services.autofill.config') as mock_config:
            mock_config.autofill_enabled = True
            mock_config.autofill_rules = [
                {"field": "name", "default": "Test"},
                {"field": "email", "default": "test@example.com"},
            ]
            
            # Form data
            form_data = {
                "name": "",
                "email": "",
            }
            
            # Apply autofill
            result = apply_autofill(form_data)
            
            assert "name" in result
            assert "email" in result
            assert result["name"] == "Test"
            assert result["email"] == "test@example.com"
            
    def test_skip_filled_fields(self):
        """Test skipping already filled fields."""
        from app.services.autofill import apply_autofill
        
        with patch('app.services.autofill.config') as mock_config:
            mock_config.autofill_enabled = True
            mock_config.autofill_rules = [
                {"field": "name", "default": "Test"},
                {"field": "email", "default": "test@example.com"},
            ]
            
            # Form data with some fields filled
            form_data = {
                "name": "User Name",  # Already filled
                "email": "",
            }
            
            # Apply autofill
            result = apply_autofill(form_data)
            
            # Should not override filled fields
            assert result["name"] == "User Name"
            assert result["email"] == "test@example.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.autofill", "--cov-report=term-missing"])
