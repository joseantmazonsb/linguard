"""Behavioral coverage for operational CLI commands without a live API."""

from unittest.mock import Mock, call

import pytest
from click.testing import CliRunner

from linguard_cli import main


BASE = "https://linguard.example"
HEADERS = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


def response(status=200, data=None, text=""):
    result = Mock(status_code=status, text=text)
    result.json.return_value = data
    return result


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setattr(main, "BASE_URL", BASE)
    monkeypatch.setattr(main, "AUTH_TOKEN", "test-token")
    monkeypatch.delenv("LINGUARD_API_URL", raising=False)
    monkeypatch.delenv("LINGUARD_API_TOKEN", raising=False)
    api = Mock(side_effect=AssertionError("Unexpected API request"))
    monkeypatch.setattr(main, "api_request", api)
    return CliRunner(), api


def test_backups_list_renders_paginated_items(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={"items": [
        {"filename": "nightly.tar", "created_at": "2026-01-02", "file_size": 1536}
    ]})]

    result = runner.invoke(main.cli, ["backups", "list"])

    assert result.exit_code == 0, result.output
    assert "Found 1 backup(s)" in result.output
    assert "nightly.tar" in result.output
    assert "2026-01-02" in result.output
    assert "1.5 KB" in result.output
    assert api.call_args_list == [
        call("GET", f"{BASE}/health", timeout=10.0),
        call("GET", f"{BASE}/api/v1/backups", headers=HEADERS, timeout=10.0),
    ]


def test_backups_list_reports_empty_collection(cli):
    runner, api = cli
    api.side_effect = [response(), response(data=[])]
    result = runner.invoke(main.cli, ["backups", "list"])
    assert result.exit_code == 0
    assert "No backups found." in result.output


@pytest.mark.parametrize("options,payload", [([], {}), (["--name", "nightly"], {"name": "nightly"})])
def test_backup_create_sends_optional_name(cli, options, payload):
    runner, api = cli
    api.side_effect = [response(), response(201, {"id": 7, "filename": "backup.tar"})]
    result = runner.invoke(main.cli, ["backups", "create", *options])
    assert result.exit_code == 0, result.output
    assert "backup.tar" in result.output and "ID: 7" in result.output
    api.assert_called_with("POST", f"{BASE}/api/v1/backups", json=payload, headers=HEADERS, timeout=60.0)


def test_unhealthy_api_prevents_operation(cli):
    runner, api = cli
    api.return_value = response(503)
    api.side_effect = None
    result = runner.invoke(main.cli, ["backups", "create"])
    assert result.exit_code == 1
    api.assert_called_once_with("GET", f"{BASE}/health", timeout=10.0)


def test_api_error_is_reported_with_nonzero_exit(cli):
    runner, api = cli
    api.side_effect = [response(), response(403, text="permission denied")]
    result = runner.invoke(main.cli, ["backups", "list"])
    assert result.exit_code == 1
    assert "403" in result.output and "permission denied" in result.output


def test_connection_error_stops_before_operation(cli):
    runner, api = cli
    api.side_effect = OSError("offline")
    result = runner.invoke(main.cli, ["notifications", "list"])
    assert result.exit_code == 1
    assert "Cannot connect" in result.output and "offline" in result.output
    assert api.call_count == 1


def test_trigger_create_parses_options_and_integration_ids(cli):
    runner, api = cli
    api.side_effect = [response(), response(201, {"name": "quota", "scope": "peer", "direction": "rx", "enabled": False})]
    result = runner.invoke(main.cli, [
        "traffic-triggers", "create", "--name", "quota", "--scope", "peer", "--peer-id", "42",
        "--direction", "rx", "--threshold-bytes", "2048", "--window", "last_hour",
        "--cooldown-minutes", "15", "--integration-ids", "3, 5",
    ])
    assert result.exit_code == 0, result.output
    assert "quota" in result.output and "Enabled: no" in result.output
    api.assert_called_with("POST", f"{BASE}/api/v1/traffic-triggers", json={
        "name": "quota", "scope": "peer", "peer_id": "42", "direction": "rx",
        "threshold_bytes": 2048, "window": "last_hour", "cooldown_minutes": 15,
        "enabled": False, "integration_ids": [3, 5],
    }, headers=HEADERS, timeout=10.0)


def test_trigger_create_rejects_bad_integration_ids_without_posting(cli):
    runner, api = cli
    api.side_effect = [response()]
    result = runner.invoke(main.cli, [
        "traffic-triggers", "create", "--name", "quota", "--scope", "global",
        "--direction", "combined", "--threshold-bytes", "10", "--window", "last_hour",
        "--integration-ids", "not-a-number",
    ])
    assert result.exit_code == 1
    assert "invalid literal" in result.output
    assert api.call_count == 1


def test_trigger_test_displays_threshold_and_reason(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={
        "would_trigger": True, "current_bytes": 2048, "threshold_bytes": 1024, "reason": "over quota"
    })]
    result = runner.invoke(main.cli, ["traffic-triggers", "test", "9"])
    assert result.exit_code == 0, result.output
    assert "Would trigger: yes" in result.output
    assert "2.00 KB / threshold 1.00 KB" in result.output
    assert "over quota" in result.output
    api.assert_called_with("POST", f"{BASE}/api/v1/traffic-triggers/9/test", headers=HEADERS, timeout=30.0)


def test_trigger_list_displays_paginated_enabled_state(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={"items": [
        {"name": "quota", "enabled": True, "scope": "global", "direction": "rx",
         "threshold_bytes": 1024, "window": "last_hour"},
        {"name": "paused", "enabled": False},
    ]})]
    result = runner.invoke(main.cli, ["traffic-triggers", "list"])
    assert result.exit_code == 0, result.output
    assert "Found 2 trigger(s)" in result.output
    assert "quota" in result.output and "paused" in result.output
    assert "rx > 1.00 KB / last_hour" in result.output


def test_integrations_list_shows_types_and_event_counts(cli):
    runner, api = cli
    api.side_effect = [response(), response(data=[
        {"name": "alerts", "type": "webhook", "enabled": True, "events_subscribed": ["a", "b"]}
    ])]
    result = runner.invoke(main.cli, ["integrations", "list"])
    assert result.exit_code == 0, result.output
    assert "Found 1 integration(s)" in result.output
    assert "alerts" in result.output and "Type: webhook | Events: 2" in result.output


def test_integration_create_builds_config_and_event_list(cli):
    runner, api = cli
    api.side_effect = [response(), response(201, {"name": "alerts", "type": "webhook"})]
    result = runner.invoke(main.cli, [
        "integrations", "create", "--name", "alerts", "--type", "webhook",
        "--url", "https://example.test/hook", "--events", "peer.created, server.stopped",
    ])
    assert result.exit_code == 0, result.output
    assert "alerts" in result.output and "webhook" in result.output
    api.assert_called_with("POST", f"{BASE}/api/v1/integrations", json={
        "name": "alerts", "type": "webhook", "enabled": True,
        "config": {"url": "https://example.test/hook"},
        "events_subscribed": ["peer.created", "server.stopped"],
    }, headers=HEADERS, timeout=10.0)


@pytest.mark.parametrize("command,endpoint,success", [
    (["traffic-triggers", "delete", "4"], "traffic-triggers/4", 204),
    (["integrations", "delete", "4"], "integrations/4", 204),
    (["notifications", "clear-all"], "notifications/all", 200),
])
@pytest.mark.parametrize("confirm", [False, True])
def test_destructive_commands_require_confirmation(cli, command, endpoint, success, confirm):
    runner, api = cli
    api.side_effect = [response(), response(success)]
    result = runner.invoke(main.cli, command, input="y\n" if confirm else "n\n")
    assert result.exit_code == 0, result.output
    if confirm:
        assert "successfully" in result.output or "cleared" in result.output
        api.assert_called_with("DELETE", f"{BASE}/api/v1/{endpoint}", headers=HEADERS, timeout=10.0)
    else:
        assert "cancelled" in result.output
        assert api.call_count == 1


def test_clear_notifications_yes_skips_prompt(cli):
    runner, api = cli
    api.side_effect = [response(), response()]
    result = runner.invoke(main.cli, ["notifications", "clear-all", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Are you sure" not in result.output
    api.assert_called_with("DELETE", f"{BASE}/api/v1/notifications/all", headers=HEADERS, timeout=10.0)


def test_notifications_list_counts_unread(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={"items": [
        {"title": "First", "read": False, "created_at": "today"},
        {"title": "Second", "read": True, "created_at": "yesterday"},
    ]})]
    result = runner.invoke(main.cli, ["notifications", "list"])
    assert result.exit_code == 0, result.output
    assert "2 notification(s) (1 unread)" in result.output
    assert "First" in result.output and "Second" in result.output


def test_mark_all_notifications_read(cli):
    runner, api = cli
    api.side_effect = [response(), response()]
    result = runner.invoke(main.cli, ["notifications", "mark-all-read"])
    assert result.exit_code == 0, result.output
    assert "marked as read" in result.output
    api.assert_called_with("PUT", f"{BASE}/api/v1/notifications/read/all", headers=HEADERS, timeout=10.0)


@pytest.mark.parametrize("scope,extra,endpoint", [
    ("global", [], "metrics/dashboard"),
    ("server", [], "metrics/servers/aggregate"),
    ("server", ["--server-id", "12"], "metrics/server/12"),
    ("peer", [], "metrics/peers/aggregate"),
    ("peer", ["--peer-id", "34"], "metrics/peer/34"),
])
def test_metrics_selects_endpoint_for_scope(cli, scope, extra, endpoint):
    runner, api = cli
    api.side_effect = [response(), response(data={})]
    result = runner.invoke(main.cli, ["metrics", "traffic", "--scope", scope, *extra])
    assert result.exit_code == 0, result.output
    assert f"Scope: {scope}" in result.output
    api.assert_called_with("GET", f"{BASE}/api/v1/{endpoint}", headers=HEADERS, timeout=10.0)


def test_global_metrics_combines_server_and_peer_traffic(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={
        "servers": {"current_totals": {"total_rx_bytes": 1024, "total_tx_bytes": 512},
                    "top_servers": [{"name": "office", "rx_bytes": 1024}]},
        "peers": {"current_totals": {"total_rx_bytes": 1024, "total_tx_bytes": 512}},
    })]
    result = runner.invoke(main.cli, ["metrics", "traffic", "--scope", "global"])
    assert result.exit_code == 0, result.output
    assert "Total RX: 2.00 KB" in result.output
    assert "Total TX: 1.00 KB" in result.output
    assert "Top Server: office" in result.output


def test_system_status_formats_uptime_and_resources(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={
        "app": {"name": "Linguard", "version": "1.2", "uptime_seconds": 3660, "python_version": "3.12.0 build"},
        "host": {"hostname": "vpn-host", "os": "Linux", "os_release": "6", "cpu_count": 4,
                 "cpu_percent": 12, "ram_used_bytes": 1024, "ram_total_bytes": 2048, "ram_percent": 50},
    })]
    result = runner.invoke(main.cli, ["status", "system"])
    assert result.exit_code == 0, result.output
    for text in ("Linguard", "1.2", "1h 1m", "3.12.0", "vpn-host", "Linux 6", "1.00 KB / 2.00 KB (50%)"):
        assert text in result.output
    api.assert_called_with("GET", f"{BASE}/api/v1/system", headers=HEADERS, timeout=10.0)


def test_health_status_displays_detailed_checks(cli):
    runner, api = cli
    api.side_effect = [response(), response(data={
        "status": "degraded", "checks": {"database": {"status": "unhealthy", "message": "unavailable"}}
    })]
    result = runner.invoke(main.cli, ["status", "health"])
    assert result.exit_code == 0, result.output
    assert "Overall Status: degraded" in result.output
    assert "database: unhealthy" in result.output and "unavailable" in result.output
    api.assert_called_with("GET", f"{BASE}/health", headers=HEADERS, timeout=30.0)


def test_completer_dns_runs_without_api(cli):
    runner, api = cli
    result = runner.invoke(main.cli, ["completers", "dns"])
    assert result.exit_code == 0, result.output
    assert "Cloudflare DNS" in result.output and "1.1.1.1" in result.output
    api.assert_not_called()
