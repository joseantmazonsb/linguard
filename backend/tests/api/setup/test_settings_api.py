"""Tests for GET/PUT /api/v1/settings/global."""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.settings import GlobalSettings
from app.models.user import User

GLOBAL_URL = "/api/v1/settings/global"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["key", "role"])
async def test_should_revalidate_admin_after_acquiring_settings_lock(api_db, db_session, seeded_db, change):
    from fastapi import HTTPException
    from jose import jwt
    from starlette.requests import Request
    from app.api.settings import update_global_settings
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    token = jwt.encode({"sub": "admin", "auth_method": "local", "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    async with api_db.sessionmaker() as session:
        stale_admin = (await session.execute(select(User).where(User.id == admin.id))).scalar_one()
        await session.execute(select(GlobalSettings))
        if change == "key":
            settings.secret_key = "new-key"
        else:
            admin.role = "standard"
        await db_session.commit()
        request = Request({"type": "http", "method": "PUT", "path": GLOBAL_URL,
                           "headers": [(b"authorization", f"Bearer {token}".encode())]})
        with pytest.raises(HTTPException) as exc:
            await update_global_settings(settings_data=GlobalSettingsUpdate(dns_primary="1.1.1.1"), request=request, db=session, current_user=stale_admin, audit_service=AuditService())
        assert exc.value.status_code in (401, 403)


@pytest.mark.asyncio
async def test_should_reject_oidc_only_without_oidc_admin_session(auth_client, db_session):
    response = auth_client.put(GLOBAL_URL, json={"auth_mode": "oidc_only"})
    assert response.status_code == 400
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.auth_mode == "both"


@pytest.mark.asyncio
async def test_should_roll_back_revocation_when_settings_commit_fails(auth_client, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    response = auth_client.put(GLOBAL_URL, json={"oidc_admin_groups": "admins", "backup_dir": None})
    assert response.status_code == 500
    await db_session.refresh(settings)
    assert settings.setup_current_step is None
    assert settings.oidc_admin_groups == ""
    assert auth_client.get("/api/v1/auth/profile").status_code == 200


@pytest.mark.asyncio
async def test_should_reject_oidc_only_through_settings_during_setup(auth_client, db_session):
    from jose import jwt

    from app.api.settings import oidc_configuration_fingerprint

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.setup_completed = False
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "sso-admin"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "exp": 9999999999, "oidc_config": oidc_configuration_fingerprint(settings)}, settings.secret_key, algorithm=settings.algorithm)
    response = auth_client.put(GLOBAL_URL, headers={"Authorization": f"Bearer {token}"}, json={"auth_mode": "oidc_only"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_should_reject_provider_changes_in_oidc_only(auth_client, db_session):
    from jose import jwt
    from app.core.security import oidc_configuration_fingerprint

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.auth_mode = "oidc_only"
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    await db_session.commit()
    token = jwt.encode({"sub": "admin", "auth_method": "oidc", "oidc_config": oidc_configuration_fingerprint(settings), "exp": 9999999999}, settings.secret_key, algorithm=settings.algorithm)
    response = auth_client.put(GLOBAL_URL, headers={"Authorization": f"Bearer {token}"}, json={"oidc_client_id": "different"})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.oidc_client_id == "client"


@pytest.mark.asyncio
async def test_should_not_reinterpret_existing_oidc_subjects_under_another_provider(auth_client, db_session):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.oidc_discovery_url = "https://idp.example.com/discovery"
    settings.oidc_client_id = "client"
    admin = (await db_session.execute(select(User).where(User.username == "admin"))).scalar_one()
    admin.oidc_sub = "existing-sub"
    await db_session.commit()
    response = auth_client.put(GLOBAL_URL, json={"oidc_discovery_url": "https://other.example.com/discovery"})
    assert response.status_code == 400
    await db_session.refresh(settings)
    assert settings.oidc_discovery_url == "https://idp.example.com/discovery"


def _headers(username, secret="test-secret-key-for-jwt-signing"):
    from datetime import datetime, timedelta

    from jose import jwt

    token = jwt.encode(
        {"sub": username, "exp": datetime.utcnow() + timedelta(minutes=30)},
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_should_return_global_settings_when_admin_requests_them(auth_client, isolated_config):
    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["database_type"] == "sqlite"
    assert body["database_url"].startswith("sqlite+aiosqlite:///")
    assert body["auth_mode"] == "both"
    assert body["setup_completed"] is True
    assert body["created_at"].endswith("Z")


@pytest.mark.asyncio
async def test_should_keep_existing_database_url_when_already_set(auth_client, db_session, isolated_config):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.database_url = "postgresql+asyncpg://db/linguard"
    settings.database_type = "postgresql"
    await db_session.commit()

    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    assert response.json()["database_url"] == "postgresql+asyncpg://db/linguard"
    assert response.json()["database_type"] == "postgresql"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "expected_type"),
    [
        ("postgresql+asyncpg://user:pass@db:5432/linguard", "postgresql"),
        ("mysql+aiomysql://user:pass@db/linguard", "mysql"),
        ("oracle+cx_oracle://user:pass@db:1521/xe", "unknown"),
    ],
)
async def test_should_detect_database_type_from_config_url_when_unset(
    auth_client, db_session, isolated_config, url, expected_type
):
    isolated_config.write_text(f'{{"database": {{"type": "x", "url": "{url}"}}}}')

    response = auth_client.get(GLOBAL_URL)

    assert response.status_code == 200
    assert response.json()["database_url"] == url
    assert response.json()["database_type"] == expected_type


@pytest.mark.asyncio
async def test_should_create_default_settings_row_when_none_exists_on_read(api_db, db_session, isolated_config):
    """Defensive path: the router can bootstrap settings when the row is missing.

    Unreachable through HTTP (authentication itself needs the settings row), so
    the handler is called directly against the real test database.
    """
    from app.api.settings import get_global_settings

    async with api_db.sessionmaker() as session:
        settings = await get_global_settings(db=session, current_user=None)

    assert settings.metrics_collection_interval_minutes == 5
    assert settings.metrics_retention_days == 90
    assert settings.metrics_global_notifications_per_hour == 50
    assert settings.database_type == "sqlite"

    rows = (await db_session.execute(select(GlobalSettings))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_should_create_default_settings_row_when_none_exists_on_update(api_db, db_session, isolated_config):
    """Defensive path: an update bootstraps the settings row before applying."""
    from starlette.requests import Request

    from app.api.settings import update_global_settings
    from app.schemas.settings import GlobalSettingsUpdate
    from app.services.audit_logger import AuditService

    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password="x",
        role="admin",
        auth_provider="local",
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    request = Request({"type": "http", "method": "PUT", "path": GLOBAL_URL, "headers": []})

    async with api_db.sessionmaker() as session:
        settings = await update_global_settings(
            settings_data=GlobalSettingsUpdate(dns_primary="1.0.0.1"),
            request=request,
            db=session,
            current_user=admin,
            audit_service=AuditService(),
        )

    assert settings.dns_primary == "1.0.0.1"
    rows = (await db_session.execute(select(GlobalSettings))).scalars().all()
    assert len(rows) == 1
    assert rows[0].dns_primary == "1.0.0.1"


@pytest.mark.asyncio
async def test_should_reject_global_settings_when_not_authenticated(api_client, seeded_db):
    response = api_client.get(GLOBAL_URL)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_should_return_503_when_setup_not_completed_and_settings_requested(api_client):
    response = api_client.get(GLOBAL_URL, headers=_headers("admin"))

    assert response.status_code == 503
    assert response.json()["detail"] == "Application not configured. Please complete setup first."


@pytest.mark.asyncio
async def test_should_deny_global_settings_update_when_user_is_not_admin(user_client):
    response = user_client.put(GLOBAL_URL, json={"dns_primary": "1.1.1.1"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


@pytest.mark.asyncio
async def test_should_update_dns_and_audit_when_admin_puts_settings(auth_client, db_session):
    response = auth_client.put(
        GLOBAL_URL,
        json={"dns_primary": "9.9.9.9", "dns_secondary": "149.112.112.112"},
    )

    assert response.status_code == 200
    assert response.json()["dns_primary"] == "9.9.9.9"
    assert response.json()["dns_secondary"] == "149.112.112.112"

    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.dns_primary == "9.9.9.9"

    audits = (await db_session.execute(select(AuditLog))).scalars().all()
    assert [a.action for a in audits] == ["UPDATE"]
    assert audits[0].resource_name == "Global Settings"
    assert audits[0].details["new"] == {
        "dns_primary": "9.9.9.9",
        "dns_secondary": "149.112.112.112",
    }


@pytest.mark.asyncio
async def test_should_reject_invalid_primary_dns_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"dns_primary": "not-an-ip"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid primary DNS address: not-an-ip"


@pytest.mark.asyncio
async def test_should_reject_invalid_secondary_dns_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"dns_secondary": "999.1.1.1"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid secondary DNS address: 999.1.1.1"


@pytest.mark.asyncio
async def test_should_reject_blank_log_path_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"log_path": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Log file path cannot be empty. Please provide a valid file path."
    )


@pytest.mark.asyncio
async def test_should_reject_unknown_backup_frequency_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_frequency": "hourly"})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Backup schedule frequency must be 'daily', 'weekly', or 'monthly'."
    )


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_hour_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_hour": 24})

    assert response.status_code == 400
    assert response.json()["detail"] == "Backup schedule hour must be between 0 and 23."


@pytest.mark.asyncio
async def test_should_reject_out_of_range_backup_minute_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"backup_schedule_minute": 60})

    assert response.status_code == 400
    assert response.json()["detail"] == "Backup schedule minute must be between 0 and 59."


@pytest.mark.asyncio
async def test_should_accept_null_backup_time_when_periodic_backups_disabled(auth_client, db_session):
    response = auth_client.put(
        GLOBAL_URL,
        json={
            "backup_periodic_enabled": False,
            "backup_schedule_hour": None,
            "backup_schedule_minute": None,
        },
    )

    assert response.status_code == 200
    assert response.json()["backup_periodic_enabled"] is False
    # The schedule columns are NOT NULL: a null value keeps the stored schedule.
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    await db_session.refresh(settings)
    assert settings.backup_schedule_hour == 2
    assert settings.backup_schedule_minute == 0


@pytest.mark.asyncio
async def test_should_reject_unknown_auth_mode_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"auth_mode": "saml"})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Authentication mode must be 'both', 'local_only', or 'oidc_only'."
    )


@pytest.mark.asyncio
async def test_should_reject_non_http_oidc_url_when_updating_settings(auth_client):
    response = auth_client.put(GLOBAL_URL, json={"oidc_discovery_url": "idp.example.com/discovery"})

    assert response.status_code == 400
    assert response.json()["detail"] == "OIDC discovery URL must start with http:// or https://."


@pytest.mark.asyncio
async def test_should_reconfigure_logging_when_log_path_changes(auth_client, tmp_path):
    new_log = tmp_path / "logs" / "linguard.log"

    with patch("app.main.configure_logging") as configure_logging:
        response = auth_client.put(GLOBAL_URL, json={"log_path": str(new_log)})

    assert response.status_code == 200
    configure_logging.assert_called_once_with(str(new_log))
