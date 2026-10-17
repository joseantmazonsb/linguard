"""
Unit tests for Firewall Service.

Tests cover:
- Firewall rule management
- Rule validation
- Rule application
- Default policies
"""

from unittest.mock import MagicMock, patch
import json


class TestFirewallRule:
    """Test firewall rule management."""
    
    def test_rule_creation(self):
        """Test firewall rule creation."""
        from app.services.firewall import FirewallRule
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="any"
        )
        
        assert rule is not None
        assert rule.name == "test_rule"
        assert rule.action == "accept"
        
    def test_rule_serialization(self):
        """Test firewall rule serialization."""
        from app.services.firewall import FirewallRule
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="10.0.0.0/8",
            port="443"
        )
        
        # Serialize
        data = rule.model_dump()
        
        assert data is not None
        assert "name" in data
        assert "action" in data
        assert "protocol" in data
        
    def test_rule_deserialization(self):
        """Test firewall rule deserialization."""
        from app.services.firewall import FirewallRule
        
        data = {
            "name": "test_rule",
            "action": "accept",
            "protocol": "tcp",
            "src_ip": "192.168.1.0/24",
            "dst_ip": "any",
            "port": "any"
        }
        
        rule = FirewallRule(**data)
        
        assert rule.name == "test_rule"
        assert rule.action == "accept"
        
    def test_rule_equality(self):
        """Test firewall rule equality."""
        from app.services.firewall import FirewallRule
        
        rule1 = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="any"
        )
        
        rule2 = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="any"
        )
        
        assert rule1 == rule2


class TestFirewallRuleValidation:
    """Test firewall rule validation."""
    
    def test_valid_rule(self):
        """Test valid firewall rule."""
        from app.services.firewall import validate_rule, FirewallRule
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        result = validate_rule(rule)
        
        assert result is True
        
    def test_invalid_action(self):
        """Test invalid action."""
        from app.services.firewall import validate_rule, FirewallRule
        
        # Create rule with invalid action (Pydantic V2 will validate immediately)
        try:
            rule = FirewallRule(
                name="test_rule",
                action="invalid_action",
                protocol="tcp",
                src_ip="192.168.1.0/24",
                dst_ip="any",
                port="any"
            )
            # If no exception was raised, validate using validate_rule
            result = validate_rule(rule)
        except Exception:
            # If validation failed during creation, result is False
            result = False
        
        assert result is False
        
    def test_invalid_protocol(self):
        """Test invalid protocol."""
        from app.services.firewall import validate_rule, FirewallRule
        
        # Create rule with invalid protocol (Pydantic V2 will validate immediately)
        try:
            rule = FirewallRule(
                name="test_rule",
                action="accept",
                protocol="invalid_protocol",
                src_ip="192.168.1.0/24",
                dst_ip="any",
                port="any"
            )
            # If no exception was raised, validate using validate_rule
            result = validate_rule(rule)
        except Exception:
            # If validation failed during creation, result is False
            result = False
        
        assert result is False
        
    def test_missing_name(self):
        """Test rule without name."""
        from app.services.firewall import validate_rule, FirewallRule
        
        # Create rule without name (Pydantic V2 will validate immediately)
        try:
            rule = FirewallRule(
                name=None,
                action="accept",
                protocol="tcp",
                src_ip="192.168.1.0/24",
                dst_ip="any",
                port="any"
            )
            # If no exception was raised, validate using validate_rule
            result = validate_rule(rule)
        except Exception:
            # If validation failed during creation, result is False
            result = False
        
        assert result is False
        
    def test_missing_required_fields(self):
        """Test rule without required fields."""
        from app.services.firewall import validate_rule, FirewallRule
        
        # Create rule without required fields (Pydantic V2 will validate immediately)
        try:
            rule = FirewallRule(
                name="test_rule",
                action=None,
                protocol=None,
                src_ip=None,
                dst_ip=None,
                port=None
            )
            # If no exception was raised, validate using validate_rule
            result = validate_rule(rule)
        except Exception:
            # If validation failed during creation, result is False
            result = False
        
        assert result is False


class TestFirewallRuleApplication:
    """Test firewall rule application."""
    
    @patch('app.services.firewall.subprocess')
    def test_add_rule(self, mock_subprocess):
        """Test adding firewall rule."""
        from app.services.firewall import add_rule
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        result = add_rule(rule)
        
        assert result is not None
        
    @patch('app.services.firewall.subprocess')
    def test_remove_rule(self, mock_subprocess):
        """Test removing firewall rule."""
        from app.services.firewall import remove_rule
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        result = remove_rule(rule)
        
        assert result is not None
        
    @patch('app.services.firewall.subprocess')
    def test_update_rule(self, mock_subprocess):
        """Test updating firewall rule."""
        from app.services.firewall import update_rule
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        result = update_rule(rule)
        
        assert result is not None
        
    @patch('app.services.firewall.subprocess')
    def test_apply_rules(self, mock_subprocess):
        """Test applying firewall rules."""
        from app.services.firewall import apply_rules
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        result = apply_rules()
        
        assert result is not None


class TestFirewallDefaultPolicy:
    """Test firewall default policy."""
    
    @patch('app.services.firewall.subprocess')
    def test_set_default_policy(self, mock_subprocess):
        """Test setting default policy."""
        from app.services.firewall import set_default_policy
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        policy = "drop"
        
        result = set_default_policy(policy)
        
        assert result is not None
        
    @patch('app.services.firewall.subprocess')
    def test_get_default_policy(self, mock_subprocess):
        """Test getting default policy."""
        from app.services.firewall import get_default_policy
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=b"drop\n")
        
        policy = get_default_policy()
        
        assert policy == "drop"


class TestFirewallService:
    """Test Firewall Service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        from app.services.firewall import FirewallService
        
        service = FirewallService()
        
        assert service is not None
        
    def test_service_get_rules(self):
        """Test getting firewall rules."""
        from app.services.firewall import FirewallService
        
        with patch('app.services.firewall.db') as mock_db:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [
                {"id": 1, "name": "rule1"},
                {"id": 2, "name": "rule2"},
            ]
            mock_db.execute.return_value = mock_result
            
            service = FirewallService()
            
            rules = service.get_rules()
            
            assert len(rules) == 2
            
    def test_service_add_rule(self):
        """Test adding firewall rule."""
        from app.services.firewall import FirewallService
        
        with patch('app.services.firewall.db') as mock_db:
            mock_result = MagicMock()
            mock_result.insert.return_value.execute.return_value = 1
            mock_db.execute.return_value = mock_result
            
            service = FirewallService()
            
            rule = FirewallRule(
                name="test_rule",
                action="accept",
                protocol="tcp",
                src_ip="192.168.1.0/24",
                dst_ip="any",
                port="443"
            )
            
            result = service.add_rule(rule)
            
            assert result == 1
            
    def test_service_remove_rule(self):
        """Test removing firewall rule."""
        from app.services.firewall import FirewallService
        
        with patch('app.services.firewall.db') as mock_db:
            mock_result = MagicMock()
            mock_result.delete.return_value.execute.return_value = 1
            mock_db.execute.return_value = mock_result
            
            service = FirewallService()
            
            result = service.remove_rule(1)
            
            assert result == 1
            
    def test_service_apply_rules(self):
        """Test applying firewall rules."""
        from app.services.firewall import FirewallService
        
        with patch('app.services.firewall.subprocess') as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(returncode=0)
            
            service = FirewallService()
            
            result = service.apply_rules()
            
            assert result is not None


class TestFirewallIntegration:
    """Test firewall integration."""
    
    @patch('app.services.firewall.subprocess')
    def test_wireguard_integration(self, mock_subprocess):
        """Test WireGuard integration with firewall."""
        from app.services.firewall import apply_wireguard_rules
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        result = apply_wireguard_rules("/etc/wireguard/wg0.conf")
        
        assert result is not None
        
    @patch('app.services.firewall.subprocess')
    def test_nftables_integration(self, mock_subprocess):
        """Test nftables integration with firewall."""
        from app.services.firewall import apply_nftables_rules
        
        # Setup mock
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        
        result = apply_nftables_rules()
        
        assert result is not None


class TestFirewallRules:
    """Test firewall rules."""
    
    def test_rule_matching(self):
        """Test rule matching."""
        from app.services.firewall import FirewallRule
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        # Test matching
        matching = rule.matches("192.168.1.100", "any", "tcp", "443")
        
        assert matching is True
        
    def test_rule_not_matching(self):
        """Test rule not matching."""
        from app.services.firewall import FirewallRule
        
        rule = FirewallRule(
            name="test_rule",
            action="accept",
            protocol="tcp",
            src_ip="192.168.1.0/24",
            dst_ip="any",
            port="443"
        )
        
        # Test not matching
        matching = rule.matches("10.0.0.100", "any", "tcp", "80")
        
        assert matching is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.firewall", "--cov-report=term-missing"])
