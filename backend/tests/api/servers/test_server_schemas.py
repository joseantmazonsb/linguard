"""Unit tests for the server Pydantic schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.server import ServerBase, ServerCreate, ServerResponse, ServerUpdate

BASE = {
    "name": "edge",
    "listen_port": 51820,
    "ipv4_address": "10.8.0.1/24",
    "public_key": "S" * 44,
    "private_key": "s" * 44,
}


def _create(**overrides):
    return ServerCreate.model_validate({**BASE, **overrides})


def _message(excinfo):
    """Pydantic prefixes custom validator messages with ``Value error, ``."""
    return excinfo.value.errors()[0]["msg"].removeprefix("Value error, ")


def test_should_build_server_create_when_payload_is_valid():
    server = _create(
        name="  edge  ",
        description="   ",
        endpoint="vpn.example.com",
        dns_primary="1.1.1.1",
        dns_secondary="8.8.8.8",
        is_bounce_server=True,
    )

    assert server.name == "edge"
    assert server.description is None
    assert server.endpoint == "vpn.example.com"
    assert server.dns_primary == "1.1.1.1"
    assert server.is_bounce_server is True
    assert server.enabled is True
    assert server.autostart is True


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ipv4_address", "10.8.0.1", "Invalid CIDR"),
        (
            "ipv6_address",
            "fd00:8::1",
            "IPv6 address must include CIDR notation (e.g., fd00::1/64)",
        ),
        (
            "dns_primary",
            "8.8.8.8/32",
            "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)",
        ),
        ("name", "1", "Server name must be at least 2 characters long"),
        ("name", "12", "Server name must contain at least one letter"),
        ("description", "d" * 501, "Server description must not exceed 500 characters"),
        ("listen_port", 80, "Listen port must be between 1024 and 65535"),
        (
            "endpoint",
            "https://vpn.example.com",
            "Endpoint must be a valid IPv4 address, IPv6 address, or hostname",
        ),
        ("endpoint", "12345", "Endpoint hostname cannot be purely numeric"),
    ],
)
def test_should_reject_invalid_field_when_creating(field, value, message):
    with pytest.raises(ValidationError) as excinfo:
        _create(**{field: value})

    assert _message(excinfo) == message


def test_should_reject_server_when_no_address_is_given():
    with pytest.raises(ValidationError) as excinfo:
        ServerBase.model_validate({"name": "edge", "listen_port": 51820})

    assert _message(excinfo) == "At least one IP address (IPv4 or IPv6) is required"


def test_should_accept_ipv6_only_server_when_creating():
    server = _create(ipv4_address=None, ipv6_address="fd00:8::1/64")

    assert server.ipv4_address is None
    assert server.ipv6_address == "fd00:8::1/64"


def test_should_keep_explicit_nulls_when_updating():
    update = ServerUpdate.model_validate(
        {
            "name": None,
            "description": None,
            "endpoint": None,
            "listen_port": None,
            "ipv4_address": "10.8.0.1/24",
            "ipv6_address": None,
            "bounce_via_server_id": None,
        }
    )

    assert update.model_dump(exclude_unset=True) == {
        "name": None,
        "description": None,
        "endpoint": None,
        "listen_port": None,
        "ipv4_address": "10.8.0.1/24",
        "ipv6_address": None,
        "bounce_via_server_id": None,
    }


def test_should_validate_update_values_when_given():
    update = ServerUpdate.model_validate(
        {
            "name": "  renamed ",
            "description": " new description ",
            "endpoint": "10.0.0.1",
            "listen_port": 51900,
            "ipv6_address": "fd00:8::1/64",
            "dns_primary": "9.9.9.9",
            "dns_secondary": "149.112.112.112",
            "is_bounce_server": True,
            "autostart": False,
        }
    )

    assert update.name == "renamed"
    assert update.description == "new description"
    assert update.endpoint == "10.0.0.1"
    assert update.listen_port == 51900
    assert update.dns_primary == "9.9.9.9"
    assert update.autostart is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "12", "Server name must contain at least one letter"),
        ("description", "d" * 501, "Server description must not exceed 500 characters"),
        ("ipv4_address", "10.8.0.1", "Invalid CIDR"),
        ("ipv6_address", "not-an-ipv6", "Invalid IPv6 CIDR format: At least 3 parts expected in 'not-an-ipv6'"),
        ("listen_port", 65536, "Listen port must be between 1024 and 65535"),
        (
            "endpoint",
            "bad endpoint",
            "Endpoint must be a valid IPv4 address, IPv6 address, or hostname",
        ),
        (
            "dns_secondary",
            "dns.local",
            "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)",
        ),
    ],
)
def test_should_reject_invalid_field_when_updating(field, value, message):
    with pytest.raises(ValidationError) as excinfo:
        ServerUpdate.model_validate({"ipv4_address": "10.8.0.1/24", field: value})

    assert _message(excinfo) == message


def test_should_reject_update_when_both_addresses_are_empty():
    with pytest.raises(ValidationError) as excinfo:
        ServerUpdate.model_validate({"ipv4_address": "", "ipv6_address": ""})

    assert _message(excinfo) == "At least one IP address (IPv4 or IPv6) is required"


def test_should_serialize_server_datetimes_as_utc_when_dumping_response():
    naive = datetime(2024, 6, 1, 8, 30, 0)

    response = ServerResponse(
        id=1,
        name="edge",
        listen_port=51820,
        public_key="S" * 44,
        ipv4_address="10.8.0.1/24",
        status="running",
        created_at=naive,
        updated_at=None,
        last_started_at=naive,
        last_stopped_at=None,
    )
    dumped = response.model_dump(mode="json")

    assert dumped["created_at"] == "2024-06-01T08:30:00Z"
    assert dumped["last_started_at"] == "2024-06-01T08:30:00Z"
    assert dumped["updated_at"] is None
    assert dumped["last_stopped_at"] is None
    assert dumped["needs_reload"] is False
    assert dumped["peer_count"] == 0


def test_should_preserve_aware_datetime_when_dumping_response():
    aware = datetime(2024, 6, 1, 8, 30, 0, tzinfo=UTC)

    response = ServerResponse(
        id=1,
        name="edge",
        listen_port=51820,
        public_key="S" * 44,
        ipv4_address="10.8.0.1/24",
        status="stopped",
        created_at=aware,
        updated_at=aware,
        last_started_at=None,
        last_stopped_at=None,
    )

    assert response.model_dump(mode="json")["updated_at"] == "2024-06-01T08:30:00Z"
