"""Tests for the account, globals, auth and progress steps of the setup wizard."""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt
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


async def _authorize_setup(client, session):
    settings = await _settings_row(session)
    session.add(User(username="setupadmin", email="setupadmin@example.com", hashed_password="unused", role="admin"))
    await session.commit()
    token = jwt.encode({"sub": "setupadmin", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}, settings.secret_key, algorithm=settings.algorithm)
    client.headers.update({"Authorization": f"Bearer {token}"})


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
async def test_should_reject_initialize_when_users_already_exist(api_client, seeded_db, db_session, admin_headers):
    settings = await _settings_row(db_session)
    settings.setup_completed = False
    await db_session.commit()
    response = api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD, headers=admin_headers)

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
async def test_setup_holds_key_lock_until_globals_commit(api_client, db_session, isolated_config, tmp_path, monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import patch

    import app.services.backup_crypto as crypto

    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    api_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    original_lock = crypto.key_lock
    released = []

    @asynccontextmanager
    async def tracked_lock():
        async with original_lock():
            try:
                yield
            finally:
                settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
                await db_session.refresh(settings)
                released.append(settings.backup_dir)

    with patch.object(crypto, "key_lock", tracked_lock):
        response = await asyncio.to_thread(api_client.post, GLOBALS_URL, json={**GLOBALS_PAYLOAD, "backup_dir": str(tmp_path / "selected")})
    assert response.status_code == 200
    assert released == [str(tmp_path / "selected")]


@pytest.mark.asyncio
async def test_setup_and_key_set_serialize_backup_directory_decisions(api_client, db_session, isolated_config, tmp_path, monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from threading import Event
    from unittest.mock import patch

    import app.services.backup_crypto as crypto

    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    original_lock = crypto.key_lock
    lock_released = Event()
    continue_setup = Event()

    @asynccontextmanager
    async def tracked_lock():
        async with original_lock():
            yield
        lock_released.set()
        await asyncio.to_thread(continue_setup.wait, 5)

    with patch.object(crypto, "key_lock", tracked_lock):
        setup = asyncio.create_task(asyncio.to_thread(api_client.post, GLOBALS_URL, headers=headers,
                                    json={**GLOBALS_PAYLOAD, "backup_dir": str(isolated_config.parent)}))
        try:
            assert await asyncio.to_thread(lock_released.wait, 3)
            key_result = await asyncio.to_thread(api_client.put, "/api/v1/settings/backup-key", headers=headers, json={"key": "secret"})
        finally:
            continue_setup.set()
            setup_result = await asyncio.wait_for(setup, 5)
    assert setup_result.status_code == 200
    assert key_result.status_code == 401
    assert not crypto.key_path().exists()


@pytest.mark.asyncio
async def test_setup_revalidates_admin_after_waiting_for_key_lock(api_client, db_session, isolated_config):
    import asyncio
    from app.models.user import User
    from app.services.backup_crypto import key_lock

    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    async with key_lock():
        request = asyncio.create_task(asyncio.to_thread(api_client.post, GLOBALS_URL, headers=headers, json=GLOBALS_PAYLOAD))
        await asyncio.sleep(0.25)
        admin = (await db_session.execute(select(User).where(User.username == "firstadmin"))).scalar_one()
        admin.role = "standard"
        await db_session.commit()
    response = await asyncio.wait_for(request, 5)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_setup_accepts_backup_directory_containing_default_key_path_when_no_key(api_client, db_session, isolated_config, tmp_path):
    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    api_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    response = api_client.post(GLOBALS_URL, json={**GLOBALS_PAYLOAD, "backup_dir": str(tmp_path)})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_should_reject_backup_directory_containing_key_before_mutation(api_client, db_session, isolated_config, tmp_path):
    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    api_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    assert api_client.put("/api/v1/settings/backup-key", json={"key": "key"}).status_code == 200
    settings = await _settings_row(db_session)
    old_key, old_dir = settings.secret_key, settings.backup_dir
    response = api_client.post(GLOBALS_URL, json={**GLOBALS_PAYLOAD, "backup_dir": str(tmp_path)})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert (settings.secret_key, settings.backup_dir) == (old_key, old_dir)

@pytest.mark.asyncio
async def test_should_create_settings_row_when_configuring_globals_first_time(
    api_client, db_session, isolated_config
):
    assert api_client.post(INITIALIZE_URL, json=ADMIN_PAYLOAD).status_code == 200
    login = api_client.post("/api/v1/auth/token", data={"username": "firstadmin", "password": "SuperSecret123"})
    api_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    response = api_client.post(GLOBALS_URL, json=GLOBALS_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    settings = await _settings_row(db_session)
    await db_session.refresh(settings)
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
    await _authorize_setup(api_client, db_session)

    response = api_client.post(GLOBALS_URL, json=GLOBALS_PAYLOAD)

    assert response.status_code == 200
    settings = await _settings_row(db_session)
    assert settings.dns_primary == "9.9.9.9"
    assert settings.backup_dir == "./backups-custom"
    assert settings.setup_current_step == "auth"


@pytest.mark.asyncio
async def test_should_reject_short_secret_key_when_configuring_globals(api_client, db_session):
    db_session.add(GlobalSettings(secret_key="k" * 40, backup_dir="./b"))
    await db_session.commit()
    await _authorize_setup(api_client, db_session)
    response = api_client.post(GLOBALS_URL, json={**GLOBALS_PAYLOAD, "secret_key": "short"})

    assert response.status_code == 422
    assert response.json()["errors"]["body.secret_key"] == [
        "Secret key must be at least 32 characters long for security"
    ]


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_retention_when_configuring_globals(api_client, db_session):
    db_session.add(GlobalSettings(secret_key="k" * 40, backup_dir="./b"))
    await db_session.commit()
    await _authorize_setup(api_client, db_session)
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

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_should_advance_to_server_step_when_configure_auth_skipped(api_client, db_session, isolated_config):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="auth")
    )
    await db_session.commit()
    await _authorize_setup(api_client, db_session)

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
    await _authorize_setup(api_client, db_session)

    response = api_client.post(
        AUTH_URL,
        json={
            "skip": False,
            "auth_mode": "both",
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
    assert settings.auth_mode == "both"
    assert settings.oidc_discovery_url == "https://idp.example.com/.well-known/openid-configuration"
    assert settings.oidc_client_id == "linguard"
    assert settings.oidc_client_secret == "shhh"
    assert settings.oidc_scopes == "openid email"
    assert settings.oidc_auto_provision is False
    assert settings.oidc_admin_groups == "admins"
    assert settings.setup_current_step == "server"


@pytest.mark.asyncio
async def test_should_reject_oidc_only_during_setup_and_keep_local_login(api_client, db_session, seeded_db, admin_headers):
    settings = await _settings_row(db_session)
    settings.setup_completed = False
    await db_session.commit()
    response = api_client.post(AUTH_URL, headers=admin_headers, json={
        "skip": False, "auth_mode": "oidc_only",
        "oidc_discovery_url": "https://idp.example.com/discovery", "oidc_client_id": "client",
    })
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.auth_mode == "both"
    assert api_client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"}).status_code == 200


@pytest.mark.asyncio
async def test_should_recover_stranded_oidc_only_when_skipping_auth_setup(api_client, db_session, seeded_db, admin_headers):
    settings = await _settings_row(db_session)
    settings.setup_completed = False
    settings.auth_mode = "oidc_only"
    await db_session.commit()
    assert api_client.post(AUTH_URL, json={"skip": True}, headers=admin_headers).status_code == 200
    await db_session.refresh(settings)
    assert settings.auth_mode == "both"


@pytest.mark.asyncio
async def test_should_not_complete_stranded_oidc_only_setup(api_client, db_session, seeded_db, admin_headers):
    settings = await _settings_row(db_session)
    settings.setup_completed = False
    settings.auth_mode = "oidc_only"
    await db_session.commit()
    response = api_client.post("/api/v1/setup/complete", headers=admin_headers)
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.setup_completed is False


@pytest.mark.asyncio
async def test_should_reject_configure_auth_when_oidc_client_id_missing(api_client, db_session):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="auth")
    )
    await db_session.commit()
    await _authorize_setup(api_client, db_session)

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
async def test_should_reject_non_http_discovery_url_when_configure_auth(api_client, db_session):
    db_session.add(GlobalSettings(secret_key="k" * 40, backup_dir="./b"))
    await db_session.commit()
    await _authorize_setup(api_client, db_session)
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
    assert len(settings.secret_key) >= 32
    assert settings.secret_key != "temporary-key-will-be-replaced"


@pytest.mark.asyncio
async def test_should_overwrite_current_step_when_updating_progress_on_existing_settings(
    api_client, db_session, isolated_config
):
    db_session.add(
        GlobalSettings(secret_key="k" * 40, backup_dir="./b", setup_current_step="globals")
    )
    await db_session.commit()
    await _authorize_setup(api_client, db_session)

    response = api_client.post(PROGRESS_URL, json={"current_step": "peer"})

    assert response.status_code == 200
    settings = await _settings_row(db_session)
    assert settings.setup_current_step == "peer"

    status = api_client.get("/api/v1/setup/status")
    assert status.json()["current_step"] == "peer"
