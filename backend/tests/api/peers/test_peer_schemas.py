"""Unit tests for the peer Pydantic schemas (validation rules and serializers)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.peer import PeerBase, PeerCreate, PeerMigrationRequest, PeerResponse, PeerUpdate

BASE = {
    "server_id": 1,
    "name": "laptop",
    "ipv4_address": "10.8.0.2/24",
    "public_key": "P" * 44,
    "private_key": "p" * 44,
}


def _create(**overrides):
    return PeerCreate.model_validate({**BASE, **overrides})


def _message(excinfo):
    """Pydantic prefixes custom validator messages with ``Value error, ``."""
    return excinfo.value.errors()[0]["msg"].removeprefix("Value error, ")


def test_should_split_combined_allowed_ips_and_ignore_blank_entries_when_creating():
    peer = _create(allowed_ips="10.0.0.0/8, , ::/0,")

    assert peer.ipv4_allowed_ips == "10.0.0.0/8"
    assert peer.ipv6_allowed_ips == "::/0"


def test_should_keep_explicit_allowed_ips_when_combined_field_is_also_sent():
    peer = _create(allowed_ips="192.168.0.0/16", ipv4_allowed_ips="10.0.0.0/8")

    assert peer.ipv4_allowed_ips == "10.0.0.0/8"
    assert peer.ipv6_allowed_ips is None


def test_should_default_to_full_tunnel_when_no_allowed_ips_are_given():
    peer = _create()

    assert peer.ipv4_allowed_ips == "0.0.0.0/0"
    assert peer.ipv6_allowed_ips == "::/0"
    assert peer.persistent_keepalive == 25
    assert peer.enabled is True


def test_should_strip_name_and_normalise_empty_description_when_creating():
    peer = _create(name="  laptop  ", description="   ")

    assert peer.name == "laptop"
    assert peer.description is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ipv4_address", "10.8.0.2", "Invalid CIDR"),
        (
            "ipv6_address",
            "not-an-ipv6",
            "Invalid IPv6 CIDR format: At least 3 parts expected in 'not-an-ipv6'",
        ),
        ("ipv4_allowed_ips", "10.0.0.0/8, nonsense", "Invalid IP CIDR in allowed IPs: nonsense"),
        ("ipv6_allowed_ips", "fd00::/garbage", "Invalid IP CIDR in allowed IPs: fd00::/garbage"),
        (
            "dns_primary",
            "dns.example.com",
            "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)",
        ),
        ("dns_secondary", "1.1.1.1/32", "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"),
        ("name", "x", "Peer name must be at least 2 characters long"),
        ("name", "1234", "Peer name must contain at least one letter"),
        ("description", "d" * 501, "Peer description must not exceed 500 characters"),
        ("persistent_keepalive", 70000, "Persistent keepalive must be between 0 and 65535 seconds"),
    ],
)
def test_should_reject_invalid_field_when_creating(field, value, message):
    with pytest.raises(ValidationError) as excinfo:
        _create(**{field: value})

    assert _message(excinfo) == message


def test_should_accept_ipv6_dns_and_keepalive_zero_when_creating():
    peer = _create(dns_primary="fd00::53", dns_secondary="1.1.1.1", persistent_keepalive=0)

    assert peer.dns_primary == "fd00::53"
    assert peer.persistent_keepalive is None


def test_should_reject_peer_when_no_address_is_given():
    with pytest.raises(ValidationError) as excinfo:
        PeerBase.model_validate({"server_id": 1, "name": "laptop"})

    assert _message(excinfo) == "At least one IP address (IPv4 or IPv6) is required"


def test_should_keep_ipv6_only_peer_valid_when_creating():
    peer = _create(ipv4_address=None, ipv6_address="fd00:8::2/64")

    assert peer.ipv4_address is None
    assert peer.ipv6_address == "fd00:8::2/64"


def test_should_default_all_update_fields_to_none_when_payload_is_empty():
    update = PeerUpdate.model_validate({})

    assert update.model_dump(exclude_unset=True) == {}


def test_should_keep_explicit_nulls_when_update_sends_them():
    update = PeerUpdate.model_validate(
        {"name": None, "description": None, "ipv6_address": "", "persistent_keepalive": None}
    )

    assert update.model_dump(exclude_unset=True) == {
        "name": None,
        "description": None,
        "ipv6_address": "",
        "persistent_keepalive": None,
    }


def test_should_validate_update_fields_when_values_are_given():
    update = PeerUpdate.model_validate(
        {
            "name": "  renamed ",
            "description": " ",
            "ipv4_address": "10.8.0.3/24",
            "ipv6_address": None,
            "ipv4_allowed_ips": "0.0.0.0/0",
            "dns_primary": "8.8.8.8",
            "persistent_keepalive": 10,
            "enabled": False,
        }
    )

    assert update.name == "renamed"
    assert update.description is None
    assert update.ipv6_address is None
    assert update.dns_primary == "8.8.8.8"
    assert update.enabled is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "12", "Peer name must contain at least one letter"),
        ("description", "d" * 501, "Peer description must not exceed 500 characters"),
        ("ipv4_address", "10.8.0.3", "Invalid CIDR"),
        ("ipv6_address", "fd00:8::3", "IPv6 address must include CIDR notation (e.g., fd00::1/64)"),
        ("ipv4_allowed_ips", "0.0.0.0/0, bogus", "Invalid IP CIDR in allowed IPs: bogus"),
        ("ipv6_allowed_ips", "bogus", "Invalid IP CIDR in allowed IPs: bogus"),
        ("dns_primary", "300.1.1.1", "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"),
        ("persistent_keepalive", -1, "Persistent keepalive must be between 0 and 65535 seconds"),
    ],
)
def test_should_reject_invalid_field_when_updating(field, value, message):
    with pytest.raises(ValidationError) as excinfo:
        PeerUpdate.model_validate({field: value})

    assert _message(excinfo) == message


def test_should_accept_migration_request_when_address_and_options_are_valid():
    request = PeerMigrationRequest.model_validate(
        {
            "target_server_id": 2,
            "ipv6_address": "fd00:9::4/64",
            "dns_primary": "9.9.9.9",
            "dns_secondary": "149.112.112.112",
            "ipv4_allowed_ips": "10.0.0.0/8",
            "ipv6_allowed_ips": "::/0",
            "persistent_keepalive": 30,
        }
    )

    assert request.target_server_id == 2
    assert request.ipv4_address is None
    assert request.persistent_keepalive == 30

    without_keepalive = PeerMigrationRequest.model_validate(
        {"target_server_id": 2, "ipv4_address": "10.9.0.4/24", "persistent_keepalive": None}
    )
    assert without_keepalive.persistent_keepalive is None


def test_should_reject_migration_request_when_no_address_is_given():
    with pytest.raises(ValidationError) as excinfo:
        PeerMigrationRequest.model_validate({"target_server_id": 2})

    assert _message(excinfo) == "At least one IP address (IPv4 or IPv6) is required"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("ipv4_address", "10.9.0.4", "Invalid CIDR"),
        ("ipv6_address", "fd00:9::4", "IPv6 address must include CIDR notation (e.g., fd00::1/64)"),
        ("ipv4_allowed_ips", "not-a-cidr", "Invalid IP CIDR in allowed IPs: not-a-cidr"),
        ("ipv6_allowed_ips", "nope", "Invalid IP CIDR in allowed IPs: nope"),
        ("dns_primary", "dns.local", "Invalid IP address for DNS server. Must be IPv4 or IPv6 (without CIDR)"),
        ("persistent_keepalive", 99999, "Persistent keepalive must be between 0 and 65535 seconds"),
    ],
)
def test_should_reject_invalid_field_when_migrating(field, value, message):
    with pytest.raises(ValidationError) as excinfo:
        PeerMigrationRequest.model_validate({"target_server_id": 2, "ipv4_address": "10.9.0.4/24", field: value})

    assert _message(excinfo) == message


def test_should_serialize_naive_datetimes_as_utc_when_dumping_response():
    naive = datetime(2024, 5, 1, 12, 0, 0)
    aware = datetime(2024, 5, 2, 12, 0, 0, tzinfo=UTC)

    response = PeerResponse(
        id=1,
        server_id=1,
        name="laptop",
        public_key="P" * 44,
        allowed_ips="0.0.0.0/0",
        ipv4_address="10.8.0.2/24",
        last_handshake=naive,
        rx_bytes=10,
        tx_bytes=20,
        created_at=naive,
        updated_at=aware,
    )
    dumped = response.model_dump(mode="json")

    assert dumped["created_at"] == "2024-05-01T12:00:00Z"
    assert dumped["last_handshake"] == "2024-05-01T12:00:00Z"
    assert dumped["updated_at"] == "2024-05-02T12:00:00Z"
    assert dumped["updated_at"].endswith("Z")
    assert response.updated_at.tzinfo is not None
