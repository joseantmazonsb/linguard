from datetime import datetime, timezone

from pydantic import BaseModel, field_validator, model_validator, field_serializer, ValidationInfo
from pydantic_core import PydanticCustomError

from ..utils.ip_validation import validate_ipv4_cidr, validate_ipv6_cidr, validate_dns_ip
from ..utils.validation import validate_name, validate_description, validate_persistent_keepalive


class PeerBase(BaseModel):
    server_id: int
    name: str
    description: str | None = None
    email: str | None = None
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    ipv4_allowed_ips: str | None = None
    ipv6_allowed_ips: str | None = None
    dns_primary: str | None = None
    dns_secondary: str | None = None
    persistent_keepalive: int = 25
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        return validate_name(v, field_name="Peer name")

    @field_validator('description')
    @classmethod
    def validate_description_field(cls, v):
        return validate_description(v, field_name="Peer description")

    @field_validator('persistent_keepalive')
    @classmethod
    def validate_persistent_keepalive_field(cls, v):
        return validate_persistent_keepalive(v, field_name="Persistent keepalive")

    @field_validator('ipv4_address')
    @classmethod
    def validate_ipv4(cls, v):
        if v:
            is_valid, error_msg = validate_ipv4_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('ipv6_address')
    @classmethod
    def validate_ipv6(cls, v):
        if v:
            is_valid, error_msg = validate_ipv6_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('ipv4_allowed_ips', 'ipv6_allowed_ips')
    @classmethod
    def validate_allowed_ips(cls, v):
        # Allowed IPs can be comma-separated list of CIDR addresses
        if v:
            for ip_cidr in v.split(','):
                ip_cidr = ip_cidr.strip()
                # Try IPv4
                is_valid_v4, _ = validate_ipv4_cidr(ip_cidr)
                # Try IPv6
                is_valid_v6, _ = validate_ipv6_cidr(ip_cidr)
                if not (is_valid_v4 or is_valid_v6):
                    raise ValueError(f"Invalid IP CIDR in allowed IPs: {ip_cidr}")
        return v

    @field_validator('dns_primary', 'dns_secondary')
    @classmethod
    def validate_dns(cls, v):
        if v:
            is_valid, error_msg = validate_dns_ip(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @model_validator(mode='after')
    def validate_at_least_one_ip(self):
        """Ensure at least one IP address (IPv4 or IPv6) is provided."""
        if not self.ipv4_address and not self.ipv6_address:
            # This will be caught by the exception handler and attached to both IP fields
            raise PydanticCustomError(
                'value_error',
                'At least one IP address (IPv4 or IPv6) is required',
            )
        return self


class PeerCreate(PeerBase):
    public_key: str
    private_key: str
    preshared_key: str | None = None
    allowed_ips: str | None = None  # Accept combined allowed_ips from frontend

    @model_validator(mode='after')
    def split_allowed_ips_and_set_defaults(self):
        """Split allowed_ips into ipv4 and ipv6 fields, and set defaults if not provided."""
        # If frontend sent allowed_ips (combined), split it into separate fields
        if self.allowed_ips and not (self.ipv4_allowed_ips or self.ipv6_allowed_ips):
            ipv4_list = []
            ipv6_list = []
            
            for ip_cidr in self.allowed_ips.split(','):
                ip_cidr = ip_cidr.strip()
                if not ip_cidr:
                    continue
                    
                # Check if it's IPv6 (contains colons) or IPv4
                if ':' in ip_cidr:
                    ipv6_list.append(ip_cidr)
                else:
                    ipv4_list.append(ip_cidr)
            
            self.ipv4_allowed_ips = ', '.join(ipv4_list) if ipv4_list else None
            self.ipv6_allowed_ips = ', '.join(ipv6_list) if ipv6_list else None
        
        # Set defaults if no allowed IPs were provided at all
        if not self.ipv4_allowed_ips and not self.ipv6_allowed_ips:
            self.ipv4_allowed_ips = '0.0.0.0/0'
            self.ipv6_allowed_ips = '::/0'
        
        return self


class PeerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    email: str | None = None
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    ipv4_allowed_ips: str | None = None
    ipv6_allowed_ips: str | None = None
    dns_primary: str | None = None
    dns_secondary: str | None = None
    persistent_keepalive: int | None = None
    enabled: bool | None = None

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        if v is not None:
            return validate_name(v, field_name="Peer name")
        return v

    @field_validator('description')
    @classmethod
    def validate_description_field(cls, v):
        if v is not None:
            return validate_description(v, field_name="Peer description")
        return v

    @field_validator('ipv4_address')
    @classmethod
    def validate_ipv4(cls, v):
        if v:
            is_valid, error_msg = validate_ipv4_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('ipv6_address')
    @classmethod
    def validate_ipv6(cls, v):
        if v:
            is_valid, error_msg = validate_ipv6_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('persistent_keepalive')
    @classmethod
    def validate_persistent_keepalive_field(cls, v):
        if v is not None:
            return validate_persistent_keepalive(v, field_name="Persistent keepalive")
        return v

    @field_validator('ipv4_allowed_ips', 'ipv6_allowed_ips')
    @classmethod
    def validate_allowed_ips(cls, v):
        if v:
            for ip_cidr in v.split(','):
                ip_cidr = ip_cidr.strip()
                is_valid_v4, _ = validate_ipv4_cidr(ip_cidr)
                is_valid_v6, _ = validate_ipv6_cidr(ip_cidr)
                if not (is_valid_v4 or is_valid_v6):
                    raise ValueError(f"Invalid IP CIDR in allowed IPs: {ip_cidr}")
        return v

    @field_validator('dns_primary', 'dns_secondary')
    @classmethod
    def validate_dns(cls, v):
        if v:
            is_valid, error_msg = validate_dns_ip(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    # Note: No model validator for PeerUpdate because it's a partial update
    # and we can't validate without fetching the current state from the database


class PeerResponse(PeerBase):
    id: int
    public_key: str
    allowed_ips: str  # Computed property combining ipv4 + ipv6
    last_handshake: datetime | None
    rx_bytes: int
    tx_bytes: int
    created_at: datetime
    updated_at: datetime | None

    @field_serializer('created_at', 'updated_at', 'last_handshake')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True


class PeerMigrationRequest(BaseModel):
    """Request schema for peer migration with custom configuration."""
    target_server_id: int
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    dns_primary: str | None = None
    dns_secondary: str | None = None
    ipv4_allowed_ips: str | None = None
    ipv6_allowed_ips: str | None = None
    persistent_keepalive: int | None = None

    @field_validator('persistent_keepalive')
    @classmethod
    def validate_persistent_keepalive_field(cls, v):
        if v is not None:
            return validate_persistent_keepalive(v, field_name="Persistent keepalive")
        return v

    @field_validator('ipv4_address')
    @classmethod
    def validate_ipv4(cls, v):
        if v:
            is_valid, error_msg = validate_ipv4_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('ipv6_address')
    @classmethod
    def validate_ipv6(cls, v):
        if v:
            is_valid, error_msg = validate_ipv6_cidr(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @field_validator('ipv4_allowed_ips', 'ipv6_allowed_ips')
    @classmethod
    def validate_allowed_ips(cls, v):
        if v:
            for ip_cidr in v.split(','):
                ip_cidr = ip_cidr.strip()
                is_valid_v4, _ = validate_ipv4_cidr(ip_cidr)
                is_valid_v6, _ = validate_ipv6_cidr(ip_cidr)
                if not (is_valid_v4 or is_valid_v6):
                    raise ValueError(f"Invalid IP CIDR in allowed IPs: {ip_cidr}")
        return v

    @field_validator('dns_primary', 'dns_secondary')
    @classmethod
    def validate_dns(cls, v):
        if v:
            is_valid, error_msg = validate_dns_ip(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @model_validator(mode='after')
    def validate_at_least_one_ip_for_migration(self):
        """Ensure at least one IP address (IPv4 or IPv6) is provided for migration."""
        if not self.ipv4_address and not self.ipv6_address:
            # This will be caught by the exception handler and attached to both IP fields
            raise PydanticCustomError(
                'value_error',
                'At least one IP address (IPv4 or IPv6) is required',
            )
        return self


