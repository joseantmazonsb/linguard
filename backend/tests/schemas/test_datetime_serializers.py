"""Datetime serialisation contract shared by the response schemas.

SQLite returns naive datetimes, while clients need an explicit UTC offset so
that browsers do not shift timestamps. These tests pin that behaviour for every
schema that implements it, plus the audit log computed aliases.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.audit import AuditLogResponse
from app.schemas.backup import BackupResponse
from app.schemas.integration import HookResponse, IntegrationResponse
from app.schemas.notification import NotificationResponse
from app.schemas.plugin import PluginResponse
from app.schemas.settings import GlobalSettingsResponse

NAIVE = datetime(2026, 1, 2, 3, 4, 5)
AWARE = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=2)))


def _audit(**overrides):
    data = dict(
        id=1,
        action="CREATE",
        resource_type="peer",
        resource_id=2,
        resource_name="laptop",
        timestamp=NAIVE,
    )
    data.update(overrides)
    return AuditLogResponse(**data)


def _backup(**overrides):
    data = dict(
        id=1,
        filename="b.json",
        size_bytes=10,
        is_encrypted=False,
        created_by_user_id=1,
        created_at=NAIVE,
    )
    data.update(overrides)
    return BackupResponse(**data)


def _integration(**overrides):
    data = dict(
        id=1,
        name="hooks",
        type="webhook",
        config={},
        events_subscribed=[],
        total_triggered=0,
        last_triggered_at=None,
        created_at=NAIVE,
        updated_at=None,
    )
    data.update(overrides)
    return IntegrationResponse(**data)


def _hook(**overrides):
    data = dict(
        id=1,
        integration_id=1,
        event_type="peer.created",
        created_at=NAIVE,
    )
    data.update(overrides)
    return HookResponse(**data)


def _notification(**overrides):
    data = dict(
        id=1,
        title="t",
        message="m",
        type="info",
        user_id=1,
        read=False,
        created_at=NAIVE,
        read_at=None,
    )
    data.update(overrides)
    return NotificationResponse(**data)


def _plugin(**overrides):
    data = dict(
        id=1,
        name="p",
        version="1.0.0",
        module_name="p",
        file_path="/p.py",
        enabled=True,
        loaded=True,
        created_at=NAIVE,
        updated_at=None,
    )
    data.update(overrides)
    return PluginResponse(**data)


def _settings(**overrides):
    data = dict(
        id=1,
        secret_key="k",
        backup_dir="./b",
        database_type="sqlite",
        setup_completed=True,
        setup_current_step=None,
        created_at=NAIVE,
        updated_at=None,
    )
    data.update(overrides)
    return GlobalSettingsResponse(**data)


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (_backup, "created_at"),
        (_integration, "created_at"),
        (_hook, "created_at"),
        (_notification, "created_at"),
        (_plugin, "created_at"),
        (_settings, "created_at"),
    ],
)
def test_should_serialise_naive_datetime_as_utc(factory, field):
    dumped = factory().model_dump(mode="json")

    assert dumped[field].startswith("2026-01-02T03:04:05")
    assert dumped[field][-1] == "Z" or dumped[field].endswith("+00:00")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (_backup, "created_at"),
        (_integration, "created_at"),
        (_notification, "created_at"),
        (_plugin, "created_at"),
        (_settings, "created_at"),
    ],
)
def test_should_preserve_timezone_of_aware_datetime(factory, field):
    dumped = factory(**{field: AWARE}).model_dump(mode="json")

    assert dumped[field].endswith("+02:00")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (_integration, "updated_at"),
        (_integration, "last_triggered_at"),
        (_notification, "read_at"),
        (_plugin, "updated_at"),
        (_settings, "updated_at"),
    ],
)
def test_should_keep_none_datetimes_as_none(factory, field):
    assert factory().model_dump(mode="json")[field] is None


class TestAuditResponseAliases:
    def test_should_expose_iso_created_at_alias(self):
        assert _audit().created_at == "2026-01-02T03:04:05"

    def test_should_expose_username_alias(self):
        assert _audit().username == "Unknown"


class TestPasswordChangeValidation:
    def test_should_validate_current_and_new_passwords(self):
        from app.schemas.auth import PasswordChange

        payload = PasswordChange(
            current_password="correct-horse-battery",
            new_password="another-strong-passphrase",
        )

        assert payload.new_password == "another-strong-passphrase"

    @pytest.mark.parametrize("field", ["current_password", "new_password"])
    def test_should_reject_too_short_password(self, field):
        from pydantic import ValidationError as PydanticValidationError

        from app.schemas.auth import PasswordChange

        values = {"current_password": "long-enough-pass", "new_password": "long-enough-pass"}
        values[field] = "short"

        with pytest.raises(PydanticValidationError) as exc_info:
            PasswordChange(**values)

        assert field in str(exc_info.value) or "password" in str(exc_info.value).lower()
