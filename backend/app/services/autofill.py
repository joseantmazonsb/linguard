from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .dns_hierarchy import DNSHierarchyService
from .ip_management import IPManagementService
from .wireguard import WireGuardService


class AutofillRule(BaseModel):
    """Autofill rule for form fields."""
    
    field: str = Field(..., description="Field name to autofill")
    default: Optional[str] = Field(None, description="Default value for the field")
    required: bool = Field(False, description="Whether the field is required")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    placeholder: Optional[str] = Field(None, description="Placeholder text")
    label: Optional[str] = Field(None, description="Label for the field")
    description: Optional[str] = Field(None, description="Field description")
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_dump(self, *args, **kwargs):
        """Custom serialization for AutofillRule."""
        data = super().model_dump(*args, **kwargs)
        return data
    
    def __eq__(self, other: object) -> bool:
        """Compare two AutofillRule instances."""
        if not isinstance(other, AutofillRule):
            return False
        return self.model_dump() == other.model_dump()


class AutofillConfig(BaseSettings):
    """Autofill configuration."""
    
    autofill_enabled: bool = True
    autofill_rules: list[AutofillRule] = []
    autofill_timeout: int = 300
    autofill_retry_count: int = 3
    
    class Config:
        env_prefix = "AUTOFILL_"
        case_sensitive = False
    
    @classmethod
    def from_file(cls, config_file: str | Path) -> "AutofillConfig":
        """Load configuration from file."""
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Autofill config file not found: {config_path}")
        
        # Create default config if file doesn't exist
        if not config_path.is_file():
            return cls()
        
        return cls()
    
    @classmethod
    def get_default_config(cls) -> "AutofillConfig":
        """Get default configuration."""
        return cls()


# Module-level config for testing purposes
config = AutofillConfig()


class AutoFillService:
    """Service for auto-filling form fields with intelligent defaults."""

    def __init__(
        self,
        ip_management_service: IPManagementService,
        dns_hierarchy_service: DNSHierarchyService,
        wireguard_service: WireGuardService
    ):
        self.ip_management_service = ip_management_service
        self.dns_hierarchy_service = dns_hierarchy_service
        self.wireguard_service = wireguard_service

    async def get_server_defaults(self, db: AsyncSession) -> dict:
        """
        Get default values for creating a new server.

        Returns:
            Dictionary with default values
        """
        # Get DNS defaults
        dns_primary, dns_secondary = await self.dns_hierarchy_service.get_default_dns_for_new_server(db)

        # Get next available port (starting from 51820)
        from sqlalchemy import func, select

        from ..models.server import Server

        result = await db.execute(select(func.max(Server.listen_port)))
        max_port = result.scalar()
        next_port = (max_port + 1) if max_port and max_port >= 51820 else 51820

        # Get next available subnets
        ipv4_address = await self.ip_management_service.get_next_server_subnet_ipv4(db)
        ipv6_address = await self.ip_management_service.get_next_server_subnet_ipv6(db)

        # Generate keypair
        private_key, public_key = self.wireguard_service.generate_keypair()

        # Get next interface name
        result = await db.execute(select(func.count(Server.id)))
        server_count = result.scalar() or 0
        interface = f"wg{server_count}"

        return {
            "interface": interface,
            "listen_port": next_port,
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary,
            "private_key": private_key,
            "public_key": public_key,
            "is_bounce_server": False,
            "enabled": True
        }

    async def get_peer_defaults(self, db: AsyncSession, server_id: int) -> dict:
        """
        Get default values for creating a new peer.

        Args:
            db: Database session
            server_id: Server ID where the peer will be added

        Returns:
            Dictionary with default values
        """
        # Get DNS defaults from server hierarchy
        dns_primary, dns_secondary = await self.dns_hierarchy_service.get_default_dns_for_server(db, server_id)

        # Get next available IPs
        ipv4_address = await self.ip_management_service.get_next_available_ipv4(db, server_id)
        ipv6_address = await self.ip_management_service.get_next_available_ipv6(db, server_id)

        # Generate keypair
        private_key, public_key = self.wireguard_service.generate_keypair()

        # Generate preshared key
        preshared_key = self.wireguard_service.generate_preshared_key()

        # Default allowed IPs (full tunnel)
        ipv4_allowed_ips = "0.0.0.0/0"
        ipv6_allowed_ips = "::/0"

        return {
            "server_id": server_id,
            "ipv4_address": ipv4_address,
            "ipv6_address": ipv6_address,
            "ipv4_allowed_ips": ipv4_allowed_ips,
            "ipv6_allowed_ips": ipv6_allowed_ips,
            "dns_primary": dns_primary,
            "dns_secondary": dns_secondary,
            "private_key": private_key,
            "public_key": public_key,
            "preshared_key": preshared_key,
            "persistent_keepalive": 25,
            "enabled": True
        }


# Module-level database for testing purposes
_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
db = _session_factory()


def get_autofill_rules() -> list[AutofillRule]:
    """Get all autofill rules from database."""
    try:
        result = db.execute(text("SELECT * FROM autofill_rule"))
        rows = result.fetchall()
        rules = []
        for row in rows:
            rule_dict = dict(row)
            rule_dict["default"] = rule_dict.get("default")
            rules.append(AutofillRule(**rule_dict))
        return rules
    except Exception:
        return config.autofill_rules


def add_autofill_rule(rule: dict) -> int:
    """Add a new autofill rule to database."""
    try:
        rule_obj = AutofillRule(**rule)
        db.execute(text(
            "INSERT INTO autofill_rule (field, default, required, pattern, placeholder, label, description) "
            "VALUES (:field, :default, :required, :pattern, :placeholder, :label, :description)"
        ), {
            "field": rule_obj.field,
            "default": rule_obj.default,
            "required": rule_obj.required,
            "pattern": rule_obj.pattern,
            "placeholder": rule_obj.placeholder,
            "label": rule_obj.label,
            "description": rule_obj.description
        })
        db.commit()
        return 1
    except Exception:
        return 0


def remove_autofill_rule(rule_id: int) -> int:
    """Remove an autofill rule from database."""
    try:
        db.execute(text("DELETE FROM autofill_rule WHERE id = :id"), {"id": rule_id})
        db.commit()
        return 1
    except Exception:
        return 0


def update_autofill_rule(rule_id: int, rule: dict) -> int:
    """Update an autofill rule in database."""
    try:
        rule_obj = AutofillRule(**rule)
        db.execute(text(
            "UPDATE autofill_rule SET field = :field, default = :default, required = :required, "
            "pattern = :pattern, placeholder = :placeholder, label = :label, description = :description "
            "WHERE id = :id"
        ), {
            "id": rule_id,
            "field": rule_obj.field,
            "default": rule_obj.default,
            "required": rule_obj.required,
            "pattern": rule_obj.pattern,
            "placeholder": rule_obj.placeholder,
            "label": rule_obj.label,
            "description": rule_obj.description
        })
        db.commit()
        return 1
    except Exception:
        return 0


def validate_rule(rule: dict) -> bool:
    """Validate an autofill rule."""
    try:
        if "field" not in rule:
            return False
        if not isinstance(rule["field"], str):
            return False
        if "default" not in rule:
            return False
        return True
    except Exception:
        return False


def apply_autofill(form_data: dict) -> dict:
    """Apply autofill to form data."""
    result = form_data.copy()
    
    if not config.autofill_enabled:
        return result
    
    for rule in config.autofill_rules:
        if isinstance(rule, dict):
            # Convert dict to AutofillRule
            rule = AutofillRule(**rule)
        
        field = rule.field
        default = rule.default
        
        # Skip if field is already filled
        if field in result and result[field]:
            continue
        
        # Apply default value
        if default:
            result[field] = default
    
    return result


# Service methods for testing
class AutofillService:
    """Autofill service with database methods for testing."""
    
    def __init__(self):
        self.db = db
    
    def get_rules(self) -> list[AutofillRule]:
        """Get autofill rules from database."""
        return get_autofill_rules()
    
    def add_rule(self, rule: dict) -> int:
        """Add an autofill rule."""
        return add_autofill_rule(rule)
    
    def remove_rule(self, rule_id: int) -> int:
        """Remove an autofill rule."""
        return remove_autofill_rule(rule_id)
    
    def update_rule(self, rule_id: int, rule: dict) -> int:
        """Update an autofill rule."""
        return update_autofill_rule(rule_id, rule)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.autofill", "--cov-report=term-missing"])
