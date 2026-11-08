"""Serialiser tails: None handling and PluginStats datetime fields."""
from datetime import datetime, timezone

from app.schemas.backup import BackupResponse
from app.schemas.integration import HookResponse
from app.schemas.plugin import PluginStats


def test_should_serialise_none_created_at_for_backup_construct():
    # ``created_at`` is required by the schema, but rows built with
    # model_construct (e.g. legacy/partial objects) may carry None.
    response = BackupResponse.model_construct(
        id=1, filename="f", size_bytes=1, is_encrypted=False,
        created_by_user_id=1, created_at=None,
    )

    assert response.model_dump(mode="json")["created_at"] is None


def test_should_serialise_none_created_at_for_hook_construct():
    response = HookResponse.model_construct(
        id=1, integration_id=1, event_type="peer.created", created_at=None
    )

    assert response.model_dump(mode="json")["created_at"] is None


def test_should_serialise_plugin_stats_without_timestamps():
    stats = PluginStats(total_invocations=3, total_errors=1)

    dumped = stats.model_dump(mode="json")

    assert dumped["last_invoked_at"] is None
    assert dumped["last_error_at"] is None


def test_should_serialise_naive_plugin_stats_timestamps_as_utc():
    stats = PluginStats(
        last_invoked_at=datetime(2026, 5, 6, 7, 8, 9),
        last_error_at=datetime(2026, 5, 6, 7, 8, 9),
    )

    dumped = stats.model_dump(mode="json")

    assert dumped["last_invoked_at"].startswith("2026-05-06T07:08:09")
    assert dumped["last_invoked_at"][-1] == "Z" or dumped["last_invoked_at"].endswith("+00:00")


def test_should_preserve_aware_plugin_stats_timestamps():
    stats = PluginStats(last_invoked_at=datetime(2026, 5, 6, tzinfo=timezone.utc))

    named = "2026-05-06T00:00:00"
    flat = stats.model_dump(by_alias=True)["last_invoked_at"]

    assert flat.isoformat().startswith(named)


def test_should_default_plugin_stats_counters_to_zero():
    stats = PluginStats()

    assert stats.total_invocations == 0
    assert stats.total_errors == 0
