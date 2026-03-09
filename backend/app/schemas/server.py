from datetime import datetime, timezone

from pydantic import BaseModel, field_validator, model_validator, field_serializer, ValidationInfo
from pydantic_core import PydanticCustomError

from ..utils.ip_validation import validate_ipv4_cidr, validate_ipv6_cidr, validate_dns_ip
from ..utils.validation import validate_name, validate_description, validate_endpoint, validate_port


class ServerBase(BaseModel):
    name: str
    interface: str | None = None  # Auto-detected from running WireGuard interfaces
    description: str | None = None
    endpoint: str | None = None
    listen_port: int
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    dns_primary: str | None = None
    dns_secondary: str | None = None
    is_bounce_server: bool = False
    bounce_via_server_id: int | None = None
    enabled: bool = True
    autostart: bool = True

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        return validate_name(v, field_name="Server name")

    @field_validator('description')
    @classmethod
    def validate_description_field(cls, v):
        return validate_description(v, field_name="Server description")

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_field(cls, v):
        return validate_endpoint(v, field_name="Endpoint")

    @field_validator('listen_port')
    @classmethod
    def validate_listen_port_field(cls, v):
        return validate_port(v, field_name="Listen port")

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
            # Attach error to ipv4_address field for frontend display
            raise PydanticCustomError(
                'value_error',
                'At least one IP address (IPv4 or IPv6) is required',
            )
        return self


class ServerCreate(ServerBase):
    public_key: str
    private_key: str


class ServerUpdate(BaseModel):
    name: str | None = None
    interface: str | None = None
    description: str | None = None
    endpoint: str | None = None
    listen_port: int | None = None
    ipv4_address: str | None = None
    ipv6_address: str | None = None
    dns_primary: str | None = None
    dns_secondary: str | None = None
    is_bounce_server: bool | None = None
    bounce_via_server_id: int | None = None
    enabled: bool | None = None
    autostart: bool | None = None

    @field_validator('name')
    @classmethod
    def validate_name_field(cls, v):
        if v is not None:
            return validate_name(v, field_name="Server name")
        return v

    @field_validator('description')
    @classmethod
    def validate_description_field(cls, v):
        if v is not None:
            return validate_description(v, field_name="Server description")
        return v

    @field_validator('endpoint')
    @classmethod
    def validate_endpoint_field(cls, v):
        if v is not None:
            return validate_endpoint(v, field_name="Endpoint")
        return v

    @field_validator('listen_port')
    @classmethod
    def validate_listen_port_field(cls, v):
        if v is not None:
            return validate_port(v, field_name="Listen port")
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

    @field_validator('dns_primary', 'dns_secondary')
    @classmethod
    def validate_dns(cls, v):
        if v:
            is_valid, error_msg = validate_dns_ip(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v

    @model_validator(mode='after')
    def validate_at_least_one_ip_on_update(self):
        """
        For updates, we only validate if both IPs are explicitly set to None/empty.
        This allows partial updates without requiring all fields.
        """
        # Only validate if both fields are present in the update and both are empty
        # If neither field is in the update dict, skip validation (partial update)
        if hasattr(self, 'ipv4_address') and hasattr(self, 'ipv6_address'):
            # Check if both are explicitly empty (None or empty string)
            if not self.ipv4_address and not self.ipv6_address:
                raise ValueError("At least one IP address (IPv4 or IPv6) is required")
        return self


class ServerResponse(ServerBase):
    id: int
    public_key: str
    status: str
    autostart: bool = True
    needs_reload: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    peer_count: int = 0
    created_at: datetime
    updated_at: datetime | None
    last_started_at: datetime | None
    last_stopped_at: datetime | None

    @field_serializer('created_at', 'updated_at', 'last_started_at', 'last_stopped_at')
    def serialize_datetime(self, dt: datetime | None, _info):
        """Ensure datetimes are timezone-aware (UTC) for proper client-side parsing."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    class Config:
        from_attributes = True
