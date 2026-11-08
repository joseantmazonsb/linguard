"""Tests for the account, globals, auth and progress steps of the setup wizard."""

import pytest
from sqlalchemy import select

from app.core.security import verify_password
from app.models.settings import GlobalSettings
from app.models.user import User

INITIALIZE_URL = "/api/v1/setup/initialize"
GLOBALS_URL = "/api/v1/setup/configure-globals"
AUTH_URL = "/api/v1/setup/configure-auth"
PROGRESS_URL = "/api/v1/setup/update-progress"

ADMIN_PAYLOAD = {
    "username": "firstadmin",
    "email": "firstadmin@example.com",
    "password": "SuperSecret123",
}

GLOBALS_PAYLOAD = {
    "secret_key": "s" * 48,
    "dns_primary": "9.9.9.9",
    "dns_secondary": "1.1.1.1",
    "access_token_expire_minutes": 60,
    "disable_auth": False,
    "log_level": "DEBUG",
    "log_path": "./custom.log",
    "backup_dir": "./backups-custom",
    "backup_retention_days": 14,
    "backup_auto_cleanup_enabled": False,
    "backup_periodic_enabled": True,
    "backup_schedule_frequency": "daily",
    "backup_schedule_hour": 4,
    "backup_schedule_minute": 30,
}


async def _settings_row(session):
    return (await session.execute(select(GlobalSettings))).scalar_one_or_none()


# ---------------------------------------------------------------------------
# /initialize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_create_first_admin_and_settings_when_initializing(api_client, db_session, isolated_config):
    response = api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["username"] == "firstadmin"

    user = (await db_session.execute(select(User))).scalars().one()
    assert user.id == body["user_id"]
    assert user.email == "firstadmin@example.com"
    assert verify_password("SuperSecret123", user.hashed_password)

    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "globals"
    assert settings.setup_completed is False
    assert settings.database_type == "sqlite"


@pytest.mark.asyncio
async def test_should_update_existing_settings_when_initializing_again_after_wipe(
    api_client, db_session, isolated_config
):
    db_session.add(
        GlobalSettings(
            secret_key="temporary-key-will-be-replaced-aaaaaaaa",
            backup_dir="/tmp/linguard-backups",
            setup_current_step="database",
            database_type="postgresql",
        )
    )
    await db_session.commit()

    response = api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD)

    assert response.status_code == 200
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "globals"
    assert settings.database_type == "sqlite"


@pytest.mark.asyncio
async def test_should_reject_initialize_when_users_already_exist(api_client, seeded_db):
    response = api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD)

    assert response.status_code == 400
    assert response.json()["detail"] == "Users already exist. Setup cannot be initialized again."


@pytest.mark.asyncio
async def test_should_reject_initialize_when_password_is_too_short(api_client, db_session):
    response = api_client.post(
        INITIALIZE_URL,
        json={**ADMIN_PAYLOAD, "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.password"] == ["Password must be at least 6 characters long"]
    assert (await db_session.execute(select(User))).scalars().all() == []


@pytest.mark.asyncio
async def test_should_reject_initialize_when_email_is_invalid(api_client):
    response = api_client.post(
        INITIALIZE_URL, json={**ADMIN_PAYLOAD, "email": "not-an-email"}
    )

    assert response.status_code == 422
    assert "body.email" in response.json()["errors"]


# ---------------------------------------------------------------------------
# /configure-globals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_create_settings_row_when_configuring_globals_first_time(
    api_client, db_session, isolated_config
):
    response = api_client.post(GLOBALS_URL, json=GLOBALS_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    settings = await _settings_row(db_session)
    assert settings.id == body["settings_id"]
    assert settings.secret_key == "s" * 48
    assert settings.dns_primary == "9.9.9.9"
    assert settings.dns_secondary == "1.1.1.1"
    assert settings.access_token_expire_minutes == 60
    assert settings.log_level == "DEBUG"
    assert settings.log_path == "./custom.log"
    assert settings.backup_dir == "./backups-custom"
    assert settings.backup_retention_days == 14
    assert settings.backup_auto_cleanup_enabled is False
    assert settings.backup_schedule_frequency == "daily"
    assert settings.backup_schedule_hour == 4
    assert settings.backup_schedule_minute == 30
    assert settings.setup_completed is False
    assert settings.setup_current_step == "auth"


@pytest.mark.asyncio
async def test_should_update_existing_settings_when_configuring_globals_again(
    api_client, db_session, isolated_config
):
    db_session.add(
        GlobalSettings(
            secret_key="old-key-old-key-old-key-old-key-11",
            backup_dir="./old-backups",
            setup_current_step="globals",
            dns_primary="8.8.8.8",
        )
    )
    await db_session.commit()

    response = api_client.post(GLOBALS_URL, json=GLOBALS_PAYLOAD)

    assert response.status_code == 200
    settings = await _settings_row(db_session)
    assert settings.dns_primary == "9.9.9.9"
    assert settings.backup_dir == "./backups-custom"
    assert settings.setup_current_step == "auth"


@pytest.mark.asyncio
async def test_should_reject_short_secret_key_when_configuring_globals(api_client):
    response = api_client.post(GLOBALS_URL, json={**GLOBALS_PAYLOAD, "secret_key": "short"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.secret_key"] == [
        "Secret key must be at least 32 characters long for security"
    ]


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_retention_when_configuring_globals(api_client):
    response = api_client.post(
        GLOBALS_URL, json={**GLOBALS_PAYLOAD, "backup_retention_days": 0}
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.backup_retention_days"] == [
        "Backup retention days must be between 1 and 365 days"
    ]


# ---------------------------------------------------------------------------
# /configure-auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_reject_configure_auth_when_settings_do_not_exist(api_client, isolated_config):
    response = api_client.post(AUTH_URL, json={"skip": True})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Setup has not been initialized yet. Complete the previous steps first."
    )


@pytest.mark.asyncio
async def test_should_advance_to_server_step_when_configure_auth_skipped(api_client, db_session, isolated_config):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="auth")
    )
    await db_session.commit()

    response = api_client.post(AUTH_URL, json={"skip": True})

    assert response.status_code == 200
    assert response.json() == {"success": True, "skipped": True}
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "server"
    assert settings.oidc_discovery_url is None


@pytest.mark.asyncio
async def test_should_store_oidc_settings_when_configure_auth_with_oidc(api_client, db_session, isolated_config):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="auth")
    )
    await db_session.commit()

    response = api_client.post(
        AUTH_URL,
        json={
            "skip": False,
            "auth_mode": "oidc_only",
            "oidc_discovery_url": "https://idp.example.com/.well-known/openid-configuration",
            "oidc_client_id": "linguard",
            "oidc_client_secret": "shhh",
            "oidc_scopes": "openid email",
            "oidc_auto_provision": False,
            "oidc_admin_groups": "admins",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "skipped": False}
    settings = await _settings_row(db_session)
    assert settings.auth_mode == "oidc_only"
    assert settings.oidc_discovery_url == "https://idp.example.com/.well-known/openid-configuration"
    assert settings.oidc_client_id == "linguard"
    assert settings.oidc_client_secret == "shhh"
    assert settings.oidc_scopes == "openid email"
    assert settings.oidc_auto_provision is False
    assert settings.oidc_admin_groups == "admins"
    assert settings.setup_current_step == "server"


@pytest.mark.asyncio
async def test_should_reject_configure_auth_when_oidc_client_id_missing(api_client, db_session):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="auth")
    )
    await db_session.commit()

    response = api_client.post(
        AUTH_URL,
        json={
            "skip": False,
            "oidc_discovery_url": "https://idp.example.com/.well-known/openid-configuration",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "OIDC discovery URL and client ID are required when configuring Single Sign-On."
    )
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "auth"


@pytest.mark.asyncio
async def test_should_reject_non_http_discovery_url_when_configure_auth(api_client):
    response = api_client.post(
        AUTH_URL,
        json={
            "skip": False,
            "oidc_discovery_url": "ftp://idp/discovery",
            "oidc_client_id": "linguard",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"]["body.oidc_discovery_url"] == [
        "OIDC discovery URL must start with http:// or https://"
    ]


# ---------------------------------------------------------------------------
# /update-progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_create_settings_row_when_updating_progress_on_fresh_install(
    api_client, db_session, isolated_config
):
    response = api_client.post(PROGRESS_URL, json={"current_step": "database"})

    assert response.status_code == 200
    assert response.json() == {"success": True, "current_step": "database"}
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "database"
    assert settings.secret_key == "temporary-key-will-be-replaced"


@pytest.mark.asyncio
async def test_should_overwrite_current_step_when_updating_progress_on_existing_settings(
    api_client, db_session, isolated_config
):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="globals")
    )
    await db_session.commit()

    response = api_client.post(PROGRESS_URL, json={"current_step": "peer"})

    assert response.status_code == 200
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "peer"

    status = api_client.get("/api/v1/setup/status")
    assert status.json()["current_step"] == "peer"
