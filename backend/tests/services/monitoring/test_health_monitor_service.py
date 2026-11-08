"""Tests for HealthMonitorService: component checks, change detection and the loop."""

import asyncio
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

import app.services.health_monitor_service as health_module
from app.models.settings import GlobalSettings
from app.services.health_monitor_service import HealthMonitorService


def ok(stdout="", returncode=0, stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


SYSCTL_IPV4_ON = ok(stdout="net.ipv4.ip_forward = 1\n")
SYSCTL_IPV6_ON = ok(stdout="net.ipv6.conf.all.forwarding = 1\n")
SYSCTL_OFF = ok(stdout="net.ipv4.ip_forward = 0\n")

# Healthy answers for every command, used unless a test overrides a component.
DEFAULTS = {
    "wg": ok(),
    "ipv4": SYSCTL_IPV4_ON,
    "ipv6": SYSCTL_IPV6_ON,
    "iptables": ok(),
}


def fake_run_factory(mapping):
    """Patch target for subprocess.run that answers per command family."""

    def fake_run(cmd, **kwargs):
        if "wg" in cmd:
            key = "wg"
        elif "net.ipv4.ip_forward" in cmd:
            key = "ipv4"
        elif "net.ipv6.conf.all.forwarding" in cmd:
            key = "ipv6"
        elif "iptables" in cmd:
            key = "iptables"
        else:  # pragma: no cover - guard against unexpected commands
            raise AssertionError(f"unexpected command {cmd}")
        value = mapping.get(key, DEFAULTS[key])
        if isinstance(value, BaseException):
            raise value
        return value

    return fake_run


async def _health(service, mapping, wg_found=True, platform_name="Linux", debug=False, db="SENTINEL"):
    """Run check_health with fully controlled subprocess results."""
    wg_paths = {"wg": "/usr/bin/wg" if wg_found else None}
    kwargs = {}
    if db == "SENTINEL":
        kwargs["db"] = None
    elif db is not None:
        kwargs["db"] = db
    with patch.object(health_module, "detect_wireguard_binaries", return_value=wg_paths), \
         patch.object(health_module.platform, "system", return_value=platform_name), \
         patch.object(health_module.settings, "DEBUG_BYPASS_FIREWALL", debug), \
         patch.object(health_module.subprocess, "run", side_effect=fake_run_factory(mapping)):
        return await service.check_health(**kwargs)


@pytest.fixture
def service():
    return HealthMonitorService(check_interval_seconds=30)


# ----------------------------------------------------------------------------
# Database check
# ----------------------------------------------------------------------------


async def test_should_report_database_healthy_when_session_can_query(service, api_db, db_session):
    health = await _health(service, {}, db=db_session)

    assert health["checks"]["database"] == {
        "status": "healthy",
        "message": "Database connection successful",
    }


async def test_should_use_global_engine_when_no_session_is_passed(service, api_db):
    health = await _health(service, {}, db=None)

    assert health["checks"]["database"]["status"] == "healthy"


async def test_should_report_database_unhealthy_when_query_fails(service):
    broken = MagicMock()
    broken.execute = AsyncMock(side_effect=RuntimeError("connection refused"))

    health = await _health(service, {}, db=broken)

    assert health["checks"]["database"]["status"] == "unhealthy"
    assert "connection refused" in health["checks"]["database"]["message"]
    assert health["status"] == "unhealthy"


# ----------------------------------------------------------------------------
# WireGuard check
# ----------------------------------------------------------------------------


async def test_should_report_wireguard_unhealthy_when_binary_missing(service):
    health = await _health(service, {}, wg_found=False)

    assert health["checks"]["wireguard"]["status"] == "unhealthy"
    assert "not found" in health["checks"]["wireguard"]["message"]


async def test_should_report_wireguard_healthy_when_wg_show_succeeds(service, api_db):
    health = await _health(service, {"wg": ok()})

    assert health["checks"]["wireguard"] == {
        "status": "healthy",
        "message": "WireGuard is accessible",
    }
    assert health["status"] == "healthy"


async def test_should_report_passwordless_sudo_required_when_sudo_asks_for_password(service):
    health = await _health(
        service, {"wg": ok(returncode=1, stderr="sudo: a password is required\n")}
    )

    assert health["checks"]["wireguard"]["status"] == "unhealthy"
    assert "passwordless sudo" in health["checks"]["wireguard"]["message"]


async def test_should_report_stderr_when_wg_command_fails(service):
    health = await _health(
        service, {"wg": ok(returncode=1, stderr="Unable to access interface: wg0\n")}
    )

    assert health["checks"]["wireguard"]["message"] == (
        "WireGuard command failed: Unable to access interface: wg0"
    )


async def test_should_report_sudo_missing_when_sudo_binary_absent(service):
    health = await _health(service, {"wg": FileNotFoundError("sudo")})

    assert "sudo command not found" in health["checks"]["wireguard"]["message"]


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired(["sudo"], 5), RuntimeError("timed out")])
async def test_should_report_timeout_when_wg_command_hangs(service, error):
    health = await _health(service, {"wg": error})

    assert health["checks"]["wireguard"]["status"] == "unhealthy"
    assert "timed out" in health["checks"]["wireguard"]["message"]


async def test_should_report_not_found_when_wg_missing_from_environment(service):
    health = await _health(service, {"wg": RuntimeError("wg: command not found")})

    assert "sudo command not found" in health["checks"]["wireguard"]["message"]


async def test_should_report_generic_wireguard_error_when_unexpected_failure(service):
    health = await _health(service, {"wg": RuntimeError("segfault")})

    assert health["checks"]["wireguard"]["message"].startswith("WireGuard check error:")


# ----------------------------------------------------------------------------
# IP forwarding check
# ----------------------------------------------------------------------------


async def test_should_report_forwarding_healthy_when_ipv4_and_ipv6_enabled(service):
    health = await _health(service, {"ipv4": SYSCTL_IPV4_ON, "ipv6": SYSCTL_IPV6_ON})

    assert health["checks"]["ip_forwarding"] == {
        "status": "healthy",
        "message": "IPv4 and IPv6 forwarding are enabled",
    }


async def test_should_warn_when_only_ipv4_forwarding_enabled(service, api_db):
    health = await _health(service, {"ipv4": SYSCTL_IPV4_ON, "ipv6": SYSCTL_OFF})

    assert health["checks"]["ip_forwarding"]["status"] == "warning"
    assert "IPv6 forwarding is disabled" in health["checks"]["ip_forwarding"]["message"]
    # Warnings do not make the whole system unhealthy
    assert health["status"] == "healthy"


async def test_should_warn_when_only_ipv6_forwarding_enabled(service):
    health = await _health(
        service,
        {"ipv4": SYSCTL_OFF, "ipv6": SYSCTL_IPV6_ON},
    )

    assert health["checks"]["ip_forwarding"]["status"] == "warning"
    assert "IPv4 forwarding is disabled" in health["checks"]["ip_forwarding"]["message"]


async def test_should_report_forwarding_unhealthy_when_both_disabled(service, api_db):
    health = await _health(service, {"ipv4": SYSCTL_OFF, "ipv6": SYSCTL_OFF})

    assert health["checks"]["ip_forwarding"]["status"] == "unhealthy"
    message = health["checks"]["ip_forwarding"]["message"]
    assert "IPv4 forwarding is disabled" in message
    assert "IPv6 forwarding is disabled" in message
    assert message.endswith("Traffic routing will not work.")
    assert health["status"] == "unhealthy"


async def test_should_report_forwarding_unhealthy_when_sysctl_returns_error(service):
    health = await _health(
        service, {"ipv4": ok(returncode=1), "ipv6": ok(returncode=1)}
    )

    message = health["checks"]["ip_forwarding"]["message"]
    assert "Could not check IPv4 forwarding" in message
    assert "Could not check IPv6 forwarding" in message


async def test_should_report_forwarding_unhealthy_when_sysctl_calls_fail(service):
    health = await _health(
        service,
        {"ipv4": RuntimeError("denied"), "ipv6": RuntimeError("denied")},
    )

    message = health["checks"]["ip_forwarding"]["message"]
    assert "IPv4 forwarding check failed: denied" in message
    assert "IPv6 forwarding check failed: denied" in message


async def test_should_skip_forwarding_check_when_debug_mode_on_non_linux(service):
    health = await _health(service, {}, platform_name="Darwin", debug=True)

    assert health["checks"]["ip_forwarding"]["status"] == "warning"
    assert "DEBUG MODE on Darwin" in health["checks"]["ip_forwarding"]["message"]
    assert health["checks"]["firewall"]["status"] == "warning"
    assert "dummy firewall driver" in health["checks"]["firewall"]["message"]


# ----------------------------------------------------------------------------
# Firewall check
# ----------------------------------------------------------------------------


async def test_should_report_firewall_healthy_when_iptables_accessible(service):
    health = await _health(service, {"iptables": ok()})

    assert health["checks"]["firewall"] == {
        "status": "healthy",
        "message": "iptables is accessible and functional",
    }


async def test_should_report_passwordless_sudo_required_for_iptables(service):
    health = await _health(
        service, {"iptables": ok(returncode=1, stderr="sudo: a password is required")}
    )

    assert health["checks"]["firewall"]["status"] == "unhealthy"
    assert "iptables requires passwordless sudo" in health["checks"]["firewall"]["message"]


async def test_should_report_stderr_when_iptables_command_fails(service):
    health = await _health(
        service, {"iptables": ok(returncode=1, stderr="iptables: Permission denied")}
    )

    assert health["checks"]["firewall"]["message"] == (
        "iptables command failed: iptables: Permission denied"
    )


async def test_should_report_iptables_missing_when_binary_absent(service):
    health = await _health(service, {"iptables": FileNotFoundError("iptables")})

    assert health["checks"]["firewall"]["message"] == "iptables command not found"


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired(["sudo"], 5), RuntimeError("timed out")])
async def test_should_report_firewall_timeout_when_iptables_hangs(service, error):
    health = await _health(service, {"iptables": error})

    assert "timed out" in health["checks"]["firewall"]["message"]


async def test_should_report_iptables_not_found_when_command_missing(service):
    health = await _health(service, {"iptables": RuntimeError("iptables: not found")})

    assert health["checks"]["firewall"]["message"] == "iptables command not found"


async def test_should_report_generic_firewall_error_when_unexpected_failure(service):
    health = await _health(service, {"iptables": RuntimeError("boom")})

    assert health["checks"]["firewall"]["message"].startswith("Firewall check error:")


async def test_should_report_platform_unsupported_when_not_linux_and_not_debug(service):
    health = await _health(service, {}, platform_name="Windows", debug=False)

    assert health["checks"]["firewall"]["status"] == "unhealthy"
    assert "Platform Windows not supported" in health["checks"]["firewall"]["message"]


# ----------------------------------------------------------------------------
# Cached status / change detection
# ----------------------------------------------------------------------------


async def test_should_return_true_when_server_is_healthy(service):
    with patch.object(service, "check_health", new=AsyncMock(return_value={
        "status": "healthy", "checks": {"database": {"status": "healthy"}}
    })):
        assert await service.check_server_status() is True


async def test_should_return_false_when_any_component_is_unhealthy(service):
    with patch.object(service, "check_health", new=AsyncMock(return_value={
        "status": "healthy",
        "checks": {"database": {"status": "healthy"}, "firewall": {"status": "unhealthy"}},
    })):
        assert await service.check_server_status() is False


async def test_should_return_dns_servers_when_global_settings_exist(service, seeded_db, db_session):
    settings_row = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings_row.dns_primary = "1.1.1.1"
    settings_row.dns_secondary = "9.9.9.9"
    await db_session.commit()

    assert await service.check_dns_resolution(db_session) == ("1.1.1.1", "9.9.9.9")


async def test_should_return_no_dns_servers_when_settings_missing(service, api_db, db_session):
    assert await service.check_dns_resolution(db_session) == (None, None)


async def test_should_return_full_health_when_server_health_requested(service):
    with patch.object(service, "check_health", new=AsyncMock(return_value={"status": "healthy"})):
        assert await service.get_server_health() == {"status": "healthy"}


def test_should_detect_change_when_this_is_the_first_check(service):
    assert service._has_status_changed(None, {"status": "healthy", "checks": {}}) is True


def test_should_detect_change_when_overall_status_differs(service):
    old = {"status": "healthy", "checks": {}}
    new = {"status": "unhealthy", "checks": {}}

    assert service._has_status_changed(old, new) is True


def test_should_detect_change_when_component_status_differs(service):
    old = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": None}}}
    new = {"status": "healthy", "checks": {"database": {"status": "unhealthy", "message": "x"}}}

    assert service._has_status_changed(old, new) is True


def test_should_detect_change_when_component_message_differs(service):
    old = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": "a"}}}
    new = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": "b"}}}

    assert service._has_status_changed(old, new) is True


def test_should_detect_change_when_new_component_appears(service):
    old = {"status": "healthy", "checks": {}}
    new = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": None}}}

    assert service._has_status_changed(old, new) is True


def test_should_report_no_change_when_status_and_components_are_identical(service):
    status = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": "ok"}}}

    assert service._has_status_changed(status, dict(status)) is False


# ----------------------------------------------------------------------------
# Broadcast / loop
# ----------------------------------------------------------------------------


async def test_should_broadcast_health_update_over_websocket(service):
    broadcast = AsyncMock()
    with patch("app.api.ws.broadcast_health_update", broadcast):
        await service._broadcast_health_update({"status": "healthy"})

    broadcast.assert_awaited_once_with({"status": "healthy"})


async def test_should_swallow_websocket_broadcast_errors(service):
    with patch("app.api.ws.broadcast_health_update", AsyncMock(side_effect=RuntimeError("closed"))):
        await service._broadcast_health_update({"status": "healthy"})  # must not raise


async def test_should_broadcast_on_first_check_and_skip_when_unchanged(service):
    health = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": None}}}
    service.check_health = AsyncMock(return_value=health)

    with patch.object(service, "_broadcast_health_update", new=AsyncMock()) as broadcast:
        await service._check_and_broadcast_health()
        await service._check_and_broadcast_health()

    assert broadcast.await_count == 1
    assert service._last_health_status == health


async def test_should_broadcast_again_when_status_changes(service):
    healthy = {"status": "healthy", "checks": {"database": {"status": "healthy", "message": None}}}
    unhealthy = {"status": "unhealthy", "checks": {"database": {"status": "unhealthy", "message": "down"}}}
    service.check_health = AsyncMock(side_effect=[healthy, unhealthy])

    with patch.object(service, "_broadcast_health_update", new=AsyncMock()) as broadcast:
        await service._check_and_broadcast_health()
        await service._check_and_broadcast_health()

    assert broadcast.await_count == 2
    broadcast.assert_awaited_with(unhealthy)


async def test_should_swallow_errors_when_checking_health(service):
    service.check_health = AsyncMock(side_effect=RuntimeError("boom"))

    await service._check_and_broadcast_health()  # must not raise


async def test_should_keep_monitoring_when_one_iteration_fails(service):
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        service._running = False
        raise RuntimeError("boom")

    service._check_and_broadcast_health = flaky
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    with patch.object(health_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitor_loop()

    assert calls["n"] == 1
    assert slept == [30]


async def test_should_check_health_each_interval_while_running(service):
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            service._running = False

    service._check_and_broadcast_health = AsyncMock()
    with patch.object(health_module.asyncio, "sleep", side_effect=fake_sleep):
        service._running = True
        await service._monitor_loop()

    assert service._check_and_broadcast_health.await_count == 2
    assert slept == [30, 30]


async def test_should_start_and_stop_monitor_task_when_requested(service):
    async def forever():
        while True:
            await asyncio.sleep(3600)

    with patch.object(service, "_monitor_loop", side_effect=forever):
        await service.start()
        assert service._running is True
        task = service._task
        assert task is not None and not task.done()

        await service.start()  # already running: no second task
        assert service._task is task

        await service.stop()

    assert service._running is False
    assert task.cancelled() or task.done()


async def test_should_do_nothing_when_stopping_monitor_that_is_not_running(service):
    await service.stop()

    assert service._running is False
    assert service._task is None
