"""Behavioral coverage for CLI commands."""

import json
from unittest.mock import Mock, call, patch

import dotenv
import httpx
import pytest
from click.testing import CliRunner

load_dotenv = dotenv.load_dotenv
with patch("dotenv.load_dotenv", return_value=False) as mocked_load_dotenv:
    from linguard_cli import main

if main.load_dotenv is mocked_load_dotenv:
    main.load_dotenv = load_dotenv


BASE = "http://cli.test"
HEADERS = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}


def response(status=200, data=None, text=""):
    result = Mock(status_code=status, text=text)
    result.json.return_value = data
    return result


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.delenv("LINGUARD_API_URL", raising=False)
    monkeypatch.delenv("LINGUARD_API_TOKEN", raising=False)
    monkeypatch.setattr(main, "BASE_URL", BASE)
    monkeypatch.setattr(main, "AUTH_TOKEN", "test-token")
    monkeypatch.setattr(main, "load_dotenv", lambda *args, **kwargs: False)
    request = Mock()
    monkeypatch.setattr(main.httpx, "request", request)
    return CliRunner(), request


def request_call(method, path, **kwargs):
    return call(method, BASE + path, follow_redirects=True, **kwargs)


def test_login_posts_form_credentials_and_prints_token(cli):
    runner, request = cli
    request.return_value = response(data={"access_token": "new-token"})

    result = runner.invoke(main.cli, ["auth", "login"], input=" alice \n secret \n")

    assert result.exit_code == 0
    assert "Login successful" in result.output
    assert "export LINGUARD_API_TOKEN='new-token'" in result.output
    request.assert_called_once_with(
        "POST", BASE + "/api/v1/auth/token", follow_redirects=True,
        data={"username": "alice", "password": "secret"},
        headers={"Authorization": "Bearer test-token"}, timeout=30.0,
    )


def test_login_rejects_insufficient_input_without_request(cli):
    runner, request = cli
    result = runner.invoke(main.cli, ["auth", "login"], input="alice\n")
    assert result.exit_code == 1
    assert "Not enough input data" in result.output
    request.assert_not_called()


@pytest.mark.parametrize(
    ("reply", "message"),
    [(response(data={}), "No token received"), (response(401, text="bad credentials"), "401 - bad credentials")],
)
def test_login_reports_missing_token_and_http_errors(cli, reply, message):
    runner, request = cli
    request.return_value = reply
    result = runner.invoke(main.cli, ["auth", "login"], input="alice\nwrong\n")
    assert result.exit_code == 1
    assert message in result.output
    assert request.call_count == 1


def test_login_reports_network_error(cli):
    runner, request = cli
    request.side_effect = httpx.ConnectError("offline")
    result = runner.invoke(main.cli, ["auth", "login"], input="alice\nsecret\n")
    assert result.exit_code == 1
    assert "HTTP request failed - offline" in result.output


def test_auth_status_uses_token_and_prints_profile(cli):
    runner, request = cli
    request.return_value = response(data={"username": "alice", "email": "a@example.test", "role": "admin"})
    result = runner.invoke(main.cli, ["auth", "status"])
    assert result.exit_code == 0
    assert all(value in result.output for value in ("Authentication successful", "alice", "a@example.test", "admin"))
    request.assert_called_once_with(
        "GET", BASE + "/api/v1/auth/profile", follow_redirects=True, headers=HEADERS, timeout=10.0,
    )


def test_auth_status_without_token_never_contacts_api(cli, monkeypatch):
    runner, request = cli
    monkeypatch.setattr(main, "AUTH_TOKEN", None)
    result = runner.invoke(main.cli, ["auth", "status"])
    assert result.exit_code == 1
    assert "No authentication token set" in result.output
    request.assert_not_called()


def test_auth_status_reports_rejected_token(cli):
    runner, request = cli
    request.return_value = response(403)
    result = runner.invoke(main.cli, ["auth", "status"])
    assert result.exit_code == 1
    assert "Authentication failed (HTTP 403)" in result.output


def test_global_options_override_defaults_for_auth_request(cli):
    runner, request = cli
    request.return_value = response(data={"username": "alice"})
    result = runner.invoke(main.cli, ["--base-url", "https://other.test", "--token", "other", "auth", "status"])
    assert result.exit_code == 0
    request.assert_called_once_with(
        "GET", "https://other.test/api/v1/auth/profile", follow_redirects=True,
        headers={"Authorization": "Bearer other", "Content-Type": "application/json"}, timeout=10.0,
    )


def test_logout_clears_in_memory_token(cli):
    runner, request = cli
    result = runner.invoke(main.cli, ["auth", "logout"])
    assert result.exit_code == 0
    assert "Token cleared" in result.output
    assert main.AUTH_TOKEN is None
    request.assert_not_called()


@pytest.mark.parametrize("action,past", [("start", "started"), ("stop", "stopped"), ("reload", "reloaded")])
def test_server_actions_check_health_and_post(cli, action, past):
    runner, request = cli
    request.side_effect = [response(), response(data={"name": "office", "status": "running"})]
    result = runner.invoke(main.cli, ["servers", action, "srv-1"])
    assert result.exit_code == 0
    assert f"Server srv-1 {past} successfully" in result.output
    assert "office" in result.output and "running" in result.output
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("POST", f"/api/v1/servers/srv-1/{action}", headers=HEADERS, timeout=30.0),
    ]


@pytest.mark.parametrize("action", ["start", "stop", "reload"])
def test_server_actions_report_api_error(cli, action):
    runner, request = cli
    request.side_effect = [response(), response(409, text="conflict")]
    result = runner.invoke(main.cli, ["servers", action, "7"])
    assert result.exit_code == 1
    assert "409 - conflict" in result.output
    assert request.call_count == 2


@pytest.mark.parametrize("group", ["servers", "peers"])
def test_list_stops_when_health_check_fails(cli, group):
    runner, request = cli
    request.side_effect = httpx.ConnectError("offline")
    result = runner.invoke(main.cli, [group, "list"])
    assert result.exit_code == 1
    assert "Cannot connect to API" in result.output and "offline" in result.output
    request.assert_called_once_with("GET", BASE + "/health", follow_redirects=True, timeout=10.0)


@pytest.mark.parametrize(
    "group,data,values",
    [
        ("servers", [{"name": "office", "interface": "wg0", "listen_port": 51820, "status": "up"}],
         ["Found 1 server(s)", "office", "wg0", "51820", "up"]),
        ("peers", {"items": [{"name": "phone", "server_id": 7, "ipv4_address": "10.0.0.2/32",
                              "allowed_ips": "0.0.0.0/0", "enabled": True, "rx_bytes": 1024, "tx_bytes": 5}]},
         ["Found 1 peer(s)", "phone", "10.0.0.2/32", "0.0.0.0/0", "1.00 KB", "5 B"]),
    ],
)
def test_list_renders_collection_table(cli, group, data, values):
    runner, request = cli
    request.side_effect = [response(), response(data=data)]
    result = runner.invoke(main.cli, [group, "list"])
    assert result.exit_code == 0
    assert all(value in result.output for value in values)
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("GET", f"/api/v1/{group}", headers=HEADERS, timeout=10.0),
    ]


@pytest.mark.parametrize("group", ["servers", "peers"])
def test_list_empty_collection(cli, group):
    runner, request = cli
    request.side_effect = [response(), response(data={"items": []})]
    result = runner.invoke(main.cli, [group, "list"])
    assert result.exit_code == 0
    assert f"No {group} found." in result.output


@pytest.mark.parametrize(
    "args,path,data",
    [
        (["servers", "list"], "/api/v1/servers", [{"id": 1, "name": "office"}]),
        (["peers", "list"], "/api/v1/peers", {"items": [{"id": 2, "name": "phone"}]}),
        (["traffic-triggers", "list"], "/api/v1/traffic-triggers", [{"name": "quota"}]),
        (["integrations", "list"], "/api/v1/integrations", [{"name": "webhook"}]),
        (["notifications", "list"], "/api/v1/notifications", [{"title": "alert"}]),
        (["metrics", "traffic", "--scope", "global"], "/api/v1/metrics/dashboard", {"servers": {"total": 3}}),
        (["metrics", "traffic", "--scope", "server"], "/api/v1/metrics/servers/aggregate", {"total": 4}),
        (["metrics", "traffic", "--scope", "server", "--server-id", "7"], "/api/v1/metrics/server/7", {"server": {"id": 7}}),
        (["metrics", "traffic", "--scope", "peer"], "/api/v1/metrics/peers/aggregate", {"total": 5}),
        (["metrics", "traffic", "--scope", "peer", "--peer-id", "8"], "/api/v1/metrics/peer/8", {"peer": {"id": 8}}),
    ],
)
def test_json_outputs_api_response(cli, args, path, data):
    runner, request = cli
    request.side_effect = [response(), response(data=data)]
    result = runner.invoke(main.cli, [*args, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == data
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("GET", path, headers=HEADERS, timeout=10.0),
    ]


@pytest.mark.parametrize("provider", ["cloudflare", "google", "quad9"])
def test_dns_provider_outputs_real_suggestions(cli, provider):
    from linguard_cli.completers import IPCompleter

    runner, request = cli
    servers = IPCompleter.suggest_dns(provider)
    result = runner.invoke(main.cli, ["completers", "dns", "--provider", provider])
    assert result.exit_code == 0, str(result.exception)
    assert f"{provider.capitalize()} DNS:" in result.output
    assert servers
    assert all(server in result.output for server in servers)
    assert result.output.count(" DNS:") == 1
    request.assert_not_called()


def test_dns_without_provider_outputs_all_real_suggestions(cli):
    from linguard_cli.completers import IPCompleter

    runner, request = cli
    providers = IPCompleter.suggest_all_dns()
    result = runner.invoke(main.cli, ["completers", "dns"])
    assert result.exit_code == 0, str(result.exception)
    assert providers
    for provider, servers in providers:
        assert f"{provider.capitalize()} DNS:" in result.output
        assert servers
        assert all(server in result.output for server in servers)
    request.assert_not_called()


@pytest.mark.parametrize("group,args,required", [
    ("servers", [], "--name, --port and --endpoint"),
    ("peers", ["7"], "--name and --endpoint"),
])
def test_create_validates_required_options_after_health(cli, group, args, required):
    runner, request = cli
    request.return_value = response()
    result = runner.invoke(main.cli, [group, "create", *args])
    assert result.exit_code == 2
    assert required in result.output
    request.assert_called_once_with("GET", BASE + "/health", follow_redirects=True, timeout=10.0)


@pytest.mark.parametrize("group,args", [("servers", ["--suggest-port"]), ("peers", ["7", "--suggest-range"])])
def test_create_suggestions_do_not_require_creation_options(cli, group, args):
    runner, request = cli
    request.return_value = response()
    result = runner.invoke(main.cli, [group, "create", *args])
    assert result.exit_code == 0
    assert ("Suggested ports:" if group == "servers" else "Common subnet ranges:") in result.output
    assert request.call_count == 1


def test_server_create_invalid_port_is_rejected_before_health_check(cli):
    runner, request = cli
    result = runner.invoke(main.cli, ["servers", "create", "--port", "not-a-number"])
    assert result.exit_code == 2
    assert "not-a-number" in result.output and "not a valid integer" in result.output
    request.assert_not_called()


def test_server_create_posts_keypair_options_and_autostarts(cli):
    runner, request = cli
    request.side_effect = [
        response(), response(data={"public_key": "pub", "private_key": "priv"}),
        response(201, {"id": 12, "name": "office", "interface": "wg0", "listen_port": 1234, "status": "down"}),
        response(),
    ]
    result = runner.invoke(main.cli, [
        "servers", "create", "--name", "office", "--port", "1234", "--endpoint", "vpn.example.test",
        "--ipv4", "10.0.0.1/24", "--ipv6", "fd00::1/64", "--dns-primary", "1.1.1.1",
        "--dns-secondary", "8.8.8.8", "--description", "work", "--autostart",
    ])
    assert result.exit_code == 0
    assert "Server created successfully" in result.output and "Server started successfully" in result.output
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("GET", "/api/v1/utils/generate-keypair", headers=HEADERS, timeout=10.0),
        request_call("POST", "/api/v1/servers", headers=HEADERS, timeout=30.0, json={
            "name": "office", "listen_port": 1234, "endpoint": "vpn.example.test", "public_key": "pub",
            "private_key": "priv", "autostart": True, "ipv4_address": "10.0.0.1/24",
            "ipv6_address": "fd00::1/64", "dns_primary": "1.1.1.1", "dns_secondary": "8.8.8.8",
            "description": "work",
        }),
        request_call("POST", "/api/v1/servers/12/start", headers=HEADERS, timeout=30.0),
    ]


def test_server_create_stops_if_key_generation_fails(cli):
    runner, request = cli
    request.side_effect = [response(), response(500)]
    result = runner.invoke(main.cli, ["servers", "create", "--name", "office", "--port", "51820", "--endpoint", "vpn"])
    assert result.exit_code == 1
    assert "Failed to generate keypair" in result.output
    assert request.call_count == 2


def test_server_create_reports_creation_error(cli):
    runner, request = cli
    request.side_effect = [response(), response(data={"public_key": "pub", "private_key": "priv"}),
                           response(422, text="invalid server")]
    result = runner.invoke(main.cli, ["servers", "create", "--name", "office", "--port", "10", "--endpoint", "vpn"])
    assert result.exit_code == 1
    assert "422 - invalid server" in result.output
    assert request.call_count == 3


def test_server_autostart_failure_is_reported_without_failing_create(cli):
    runner, request = cli
    request.side_effect = [response(), response(data={}), response(201, {"id": 12}), response(500)]
    result = runner.invoke(main.cli, ["servers", "create", "--name", "office", "--port", "10", "--endpoint", "vpn", "--autostart"])
    assert result.exit_code == 0
    assert "Failed to start server" in result.output


def test_peer_create_merges_defaults_and_explicit_options(cli):
    runner, request = cli
    defaults = {"public_key": "pub", "private_key": "priv", "ipv4_address": "10.0.0.2/32",
                "ipv6_address": "fd00::2/128", "dns_primary": "1.1.1.1", "dns_secondary": "8.8.8.8",
                "preshared_key": "default-psk"}
    request.side_effect = [response(), response(data={}), response(data=defaults),
                           response(201, {"name": "phone", "ipv4_address": "10.0.0.9/32", "public_key": "pub"})]
    result = runner.invoke(main.cli, [
        "peers", "create", "7", "--name", "phone", "--endpoint", "phone.example.test",
        "--ipv4", "10.0.0.9/32", "--dns-primary", "9.9.9.9", "--preshared-key", "custom-psk",
        "--allowed-ips", "10.0.0.0/24", "--port", "1234", "--persistent-keepalive", "25",
    ])
    assert result.exit_code == 0
    assert "Peer created successfully" in result.output and "10.0.0.9/32" in result.output
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("GET", "/api/v1/servers/7", headers=HEADERS, timeout=10.0),
        request_call("GET", "/api/v1/peers/defaults/7", headers=HEADERS, timeout=10.0),
        request_call("POST", "/api/v1/peers", headers=HEADERS, timeout=30.0, json={
            "server_id": "7", "name": "phone", "endpoint": "phone.example.test", "port": 1234,
            "persistent_keepalive": 25, "public_key": "pub", "private_key": "priv",
            "ipv4_address": "10.0.0.9/32", "ipv6_address": "fd00::2/128", "allowed_ips": "10.0.0.0/24",
            "dns_primary": "9.9.9.9", "dns_secondary": "8.8.8.8", "preshared_key": "custom-psk",
        }),
    ]


def test_peer_create_continues_when_defaults_endpoint_fails(cli):
    runner, request = cli
    request.side_effect = [response(), response(), response(500), response(201, {"name": "phone"})]
    result = runner.invoke(main.cli, ["peers", "create", "7", "--name", "phone", "--endpoint", "vpn"])
    assert result.exit_code == 0
    assert request.call_args.kwargs["json"] == {
        "server_id": "7", "name": "phone", "endpoint": "vpn", "port": 51820,
        "persistent_keepalive": 60, "public_key": None, "private_key": None,
    }
    assert "Allowed IPs: N/A" in result.output


def test_peer_create_uses_suggested_addresses_and_dns_when_omitted(cli):
    runner, request = cli
    defaults = {"public_key": "pub", "private_key": "priv", "ipv4_address": "10.0.0.2/32",
                "ipv6_address": "fd00::2/128", "dns_primary": "1.1.1.1", "dns_secondary": "8.8.8.8",
                "preshared_key": "default-psk"}
    request.side_effect = [response(), response(), response(data=defaults), response(201, {"name": "phone"})]
    result = runner.invoke(main.cli, ["peers", "create", "7", "--name", "phone", "--endpoint", "vpn"])
    assert result.exit_code == 0
    assert request.call_args.kwargs["json"] == {
        "server_id": "7", "name": "phone", "endpoint": "vpn", "port": 51820,
        "persistent_keepalive": 60, **defaults,
    }


def test_peer_create_reports_creation_error(cli):
    runner, request = cli
    request.side_effect = [response(), response(), response(data={}), response(400, text="invalid peer")]
    result = runner.invoke(main.cli, ["peers", "create", "7", "--name", "phone", "--endpoint", "vpn"])
    assert result.exit_code == 1
    assert "400 - invalid peer" in result.output
    assert request.call_count == 4


def test_peer_create_stops_when_server_missing(cli):
    runner, request = cli
    request.side_effect = [response(), response(404)]
    result = runner.invoke(main.cli, ["peers", "create", "7", "--name", "phone", "--endpoint", "vpn"])
    assert result.exit_code == 1
    assert "Server not found" in result.output
    assert request.call_count == 2


@pytest.mark.parametrize("group,singular", [("servers", "server"), ("peers", "peer")])
def test_delete_cancelled_never_deletes(cli, group, singular):
    runner, request = cli
    request.return_value = response()
    result = runner.invoke(main.cli, [group, "delete", "42"], input="n\n")
    assert result.exit_code == 0
    assert f"delete {singular} 42" in result.output
    assert "Delete cancelled" in result.output
    assert request.call_count == 1


@pytest.mark.parametrize("group,singular", [("servers", "Server"), ("peers", "Peer")])
@pytest.mark.parametrize("confirmation", ["flag", "prompt"])
def test_delete_confirmed_sends_delete(cli, group, singular, confirmation):
    runner, request = cli
    request.side_effect = [response(), response(204)]
    args = [group, "delete", "42"] + (["--yes"] if confirmation == "flag" else [])
    result = runner.invoke(main.cli, args, input="y\n" if confirmation == "prompt" else None)
    assert result.exit_code == 0
    assert f"{singular} 42 deleted successfully" in result.output
    assert request.call_args_list == [
        request_call("GET", "/health", timeout=10.0),
        request_call("DELETE", f"/api/v1/{group}/42", headers=HEADERS, timeout=10.0),
    ]


@pytest.mark.parametrize("group", ["servers", "peers"])
def test_delete_reports_api_failure(cli, group):
    runner, request = cli
    request.side_effect = [response(), response(403, text="forbidden")]
    result = runner.invoke(main.cli, [group, "delete", "42", "--yes"])
    assert result.exit_code == 1
    assert "403 - forbidden" in result.output
