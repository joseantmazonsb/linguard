"""Unit tests for the setup wizard request/response schemas."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.setup import (
    ConfigureAuth,
    ConfigureDatabase,
    ConfigureGlobals,
    CreatePeer,
    CreateServer,
    DatabaseType,
    InitializeSetup,
    SetupComplete,
    SetupStatus,
    UpdateSetupProgress,
)


def _errors(exc_info) -> dict:
    return {err["loc"][0]: err["msg"].removeprefix("Value error, ") for err in exc_info.value.errors()}


def test_should_accept_valid_admin_account_when_initializing():
    model = InitializeSetup(
        username="  admin  ", email="admin@example.com", password="secret123"
    )

    assert model.username == "admin"
    assert model.email == "admin@example.com"


def test_should_reject_username_with_spaces_when_initializing():
    with pytest.raises(PydanticValidationError) as exc_info:
        InitializeSetup(username="ad min", email="admin@example.com", password="secret123")

    assert "Username" in _errors(exc_info)["username"]


def test_should_reject_short_password_when_initializing():
    with pytest.raises(PydanticValidationError) as exc_info:
        InitializeSetup(username="admin", email="admin@example.com", password="12345")

    assert _errors(exc_info)["password"] == "Password must be at least 6 characters long"


def test_should_default_dns_and_security_values_when_configuring_globals():
    model = ConfigureGlobals(secret_key="k" * 32)

    assert model.dns_primary == "1.1.1.1"
    assert model.dns_secondary == "8.8.8.8"
    assert model.algorithm == "HS256"
    assert model.access_token_expire_minutes == 30
    assert model.disable_auth is False
    assert model.log_level == "INFO"
    assert model.backup_schedule_frequency == "weekly"


def test_should_reject_short_secret_key_when_configuring_globals():
    with pytest.raises(PydanticValidationError) as exc_info:
        ConfigureGlobals(secret_key="too-short")

    assert _errors(exc_info)["secret_key"] == (
        "Secret key must be at least 32 characters long for security"
    )


@pytest.mark.parametrize("minutes", [0, 43201])
def test_should_reject_out_of_range_token_expiry_when_configuring_globals(minutes):
    with pytest.raises(PydanticValidationError) as exc_info:
        ConfigureGlobals(secret_key="k" * 32, access_token_expire_minutes=minutes)

    assert _errors(exc_info)["access_token_expire_minutes"] == (
        "Access token expiry must be between 1 and 43200 minutes"
    )


@pytest.mark.parametrize("days", [0, 366])
def test_should_reject_out_of_range_retention_when_configuring_globals(days):
    with pytest.raises(PydanticValidationError) as exc_info:
        ConfigureGlobals(secret_key="k" * 32, backup_retention_days=days)

    assert _errors(exc_info)["backup_retention_days"] == (
        "Backup retention days must be between 1 and 365 days"
    )


def test_should_default_to_skipping_oidc_when_configure_auth_omits_fields():
    model = ConfigureAuth()

    assert model.skip is False
    assert model.auth_mode == "both"
    assert model.oidc_scopes == "openid email profile"
    assert model.oidc_auto_provision is True


@pytest.mark.parametrize("mode", ["both", "local_only", "oidc_only"])
def test_should_accept_known_auth_modes_when_configure_auth(mode):
    assert ConfigureAuth(auth_mode=mode).auth_mode == mode


def test_should_reject_unknown_auth_mode_when_configure_auth():
    with pytest.raises(PydanticValidationError) as exc_info:
        ConfigureAuth(auth_mode="saml")

    assert _errors(exc_info)["auth_mode"] == (
        "Authentication mode must be 'both', 'local_only', or 'oidc_only'"
    )


def test_should_reject_non_http_discovery_url_when_configure_auth():
    with pytest.raises(PydanticValidationError) as exc_info:
        ConfigureAuth(oidc_discovery_url="ldap://idp/discovery")

    assert _errors(exc_info)["oidc_discovery_url"] == (
        "OIDC discovery URL must start with http:// or https://"
    )


def test_should_accept_https_discovery_url_when_configure_auth():
    model = ConfigureAuth(oidc_discovery_url="https://idp.example.com/discovery")

    assert model.oidc_discovery_url == "https://idp.example.com/discovery"


@pytest.mark.parametrize(
    "endpoint",
    ["192.168.1.10", "2001:db8::1", "[2001:db8::1]", "vpn.example.com"],
)
def test_should_accept_valid_endpoints_when_creating_server(endpoint):
    model = CreateServer(
        name="main",
        endpoint=endpoint,
        listen_port=51820,
        ipv4_address="10.0.0.1/24",
    )

    assert model.endpoint == endpoint


def test_should_reject_purely_numeric_hostname_when_creating_server():
    with pytest.raises(PydanticValidationError) as exc_info:
        CreateServer(name="main", endpoint="12345", listen_port=51820, ipv4_address="10.0.0.1/24")

    assert _errors(exc_info)["endpoint"] == (
        "Endpoint hostname cannot be purely numeric"
    )


def test_should_reject_single_character_name_when_creating_server():
    with pytest.raises(PydanticValidationError) as exc_info:
        CreateServer(name="a", endpoint="vpn.example.com", listen_port=51820, ipv4_address="10.0.0.1/24")

    assert _errors(exc_info)["name"] == "Server name must be at least 2 characters long"


def test_should_reject_reserved_port_when_creating_server():
    with pytest.raises(PydanticValidationError) as exc_info:
        CreateServer(name="main", endpoint="vpn.example.com", listen_port=22, ipv4_address="10.0.0.1/24")

    assert _errors(exc_info)["listen_port"] == "Listen port must be between 1024 and 65535"


def test_should_reject_whitespace_name_when_creating_peer():
    with pytest.raises(PydanticValidationError) as exc_info:
        CreatePeer(server_id=1, name="   ")

    assert _errors(exc_info)["name"] == "Peer name cannot be empty or whitespace only"


def test_should_default_preshared_key_off_when_creating_peer():
    model = CreatePeer(server_id=3, name="laptop")

    assert model.preshared_key is False
    assert model.ipv4_address is None
    assert model.server_id == 3


def test_should_require_current_step_when_updating_progress():
    with pytest.raises(PydanticValidationError) as exc_info:
        UpdateSetupProgress()

    assert _errors(exc_info)["current_step"] == "Field required"


def test_should_serialize_setup_models_when_dumped():
    assert SetupStatus(setup_completed=True, requires_setup=False).model_dump() == {
        "setup_completed": True,
        "requires_setup": False,
        "current_step": None,
    }
    assert SetupComplete(success=True, message="ok").model_dump() == {
        "success": True,
        "message": "ok",
        "backup_id": None,
    }
    db_config = ConfigureDatabase(database_type=DatabaseType.SQLITE, database_url="sqlite://")
    assert db_config.database_type is DatabaseType.SQLITE
    assert db_config.model_dump()["database_type"] == "sqlite"
