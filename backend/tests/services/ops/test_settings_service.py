"""Tests for SettingsService against a real (SQLite) database."""

import pytest
from sqlalchemy import select

from app.models.settings import GlobalSettings
from app.services.settings_service import SettingsService


@pytest.fixture
def service():
    return SettingsService()


async def test_should_return_settings_row_when_settings_exist(service, seeded_db, db_session):
    settings = await service.get_settings(db_session)

    assert isinstance(settings, GlobalSettings)
    assert settings.setup_completed is True


async def test_should_raise_runtime_error_when_no_settings_exist(service, api_db, db_session):
    with pytest.raises(RuntimeError, match="setup wizard"):
        await service.get_settings(db_session)


async def test_should_return_configured_values_when_settings_overridden(service, db_session):
    db_session.add(
        GlobalSettings(
            secret_key="a-different-secret",
            algorithm="HS512",
            access_token_expire_minutes=90,
            disable_auth=True,
            auth_mode="local_only",
            log_level="DEBUG",
            log_path="/var/log/linguard/x.log",
            backup_dir="/srv/backups",
            backup_retention_days=7,
            backup_auto_cleanup_enabled=False,
            backup_periodic_enabled=True,
            backup_schedule_frequency="weekly",
            backup_schedule_hour=3,
            backup_schedule_minute=45,
            setup_completed=True,
        )
    )
    await db_session.commit()

    assert await service.get_secret_key(db_session) == "a-different-secret"
    assert await service.get_algorithm(db_session) == "HS512"
    assert await service.get_access_token_expire_minutes(db_session) == 90
    assert await service.is_auth_disabled(db_session) is True
    assert await service.get_log_level(db_session) == "DEBUG"
    assert await service.get_log_path(db_session) == "/var/log/linguard/x.log"
    assert await service.get_backup_dir(db_session) == "/srv/backups"
    assert await service.get_backup_retention_days(db_session) == 7
    assert await service.is_backup_auto_cleanup_enabled(db_session) is False
    assert await service.is_backup_periodic_enabled(db_session) is True
    assert await service.get_backup_schedule_frequency(db_session) == "weekly"
    assert await service.get_backup_schedule_hour(db_session) == 3
    assert await service.get_backup_schedule_minute(db_session) == 45


async def test_should_return_hardcoded_values_when_cors_and_prefix_requested(service, api_db, db_session):
    # These getters never touch the database, so they work without a settings row.
    assert await service.get_cors_origins(db_session) == ["*"]
    assert await service.get_wireguard_interface_prefix(db_session) == "wg"


async def test_should_return_defaults_when_settings_use_column_defaults(service, seeded_db, db_session):
    await db_session.execute(select(GlobalSettings))

    settings = await service.get_settings(db_session)
    assert await service.get_backup_retention_days(db_session) == settings.backup_retention_days
    assert await service.get_backup_retention_days(db_session) == 30
    assert await service.get_log_level(db_session) == "INFO"
    assert await service.get_backup_schedule_hour(db_session) == 2
    assert await service.get_backup_schedule_minute(db_session) == 0
    assert await service.get_backup_schedule_frequency(db_session) == "daily"
    assert await service.is_backup_periodic_enabled(db_session) is False
    assert await service.is_auth_disabled(db_session) is False
