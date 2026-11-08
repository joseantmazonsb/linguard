"""Tests for ``app.services.firewall.iptables_driver``.

The contract here is the exact iptables/ip6tables command lines that get run,
including the ``sudo -n`` hardening, ordering of rules and tolerance of missing
rules during cleanup.
"""

import subprocess

import pytest

from app.services.firewall.base import NATConfig
from app.services.firewall.iptables_driver import IptablesDriver, _run_sudo_command


class Recorder:
    def __init__(self):
        self.calls = []
        self.fail_on = None      # substring matched against the argv
        self.timeout_on = None

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        joined = " ".join(argv)
        if self.timeout_on and self.timeout_on in joined:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 5))
        if self.fail_on and self.fail_on in joined:
            stderr = "iptables: Permission denied (you must be root)."
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(1, argv, "", stderr)
            return subprocess.CompletedProcess(list(argv), 1, "", stderr)
        return subprocess.CompletedProcess(list(argv), 0, "", "")

    @property
    def argv_list(self):
        return [argv for argv, _ in self.calls]


@pytest.fixture
def run(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", recorder)
    return recorder


NAT_V4 = NATConfig(interface="wg0", ipv4_subnet="10.8.0.0/24", ipv6_subnet=None, default_interface="eth0")
NAT_V6 = NATConfig(interface="wg0", ipv4_subnet=None, ipv6_subnet="fd00:8::/64", default_interface="eth0")
NAT_BOTH = NATConfig(interface="wg0", ipv4_subnet="10.8.0.0/24", ipv6_subnet="fd00:8::/64", default_interface="eth0")


class TestSudoWrapper:
    def test_should_insert_dash_n_after_sudo(self, run):
        result = _run_sudo_command(["sudo", "iptables", "-L"])

        assert result.returncode == 0
        argv, kwargs = run.calls[0]
        assert argv == ["sudo", "-n", "iptables", "-L"]
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["timeout"] == 5
        assert kwargs["check"] is True
        assert kwargs["env"]["SUDO_ASKPASS"] == "/bin/false"

    def test_should_keep_existing_dash_n(self, run):
        _run_sudo_command(["sudo", "-n", "iptables", "-L"])

        assert run.argv_list == [["sudo", "-n", "iptables", "-L"]]

    def test_should_raise_when_sudo_asks_for_password(self, run):
        run.fail_on = "iptables"

        with pytest.raises(subprocess.CalledProcessError):
            _run_sudo_command(["sudo", "iptables", "-L"])

    def test_should_return_result_without_raising_when_check_disabled(self, run):
        run.fail_on = "iptables"

        result = _run_sudo_command(["sudo", "iptables", "-L"], check=False)

        assert result.returncode == 1

    def test_should_reraise_timeout(self, run):
        run.timeout_on = "iptables"

        with pytest.raises(subprocess.TimeoutExpired):
            _run_sudo_command(["sudo", "iptables", "-L"], timeout=3)


class TestAvailability:
    def test_should_report_binary_and_sudo_checks(self, run):
        assert IptablesDriver().is_available() is True

        assert run.argv_list == [
            ["iptables", "--version"],
            ["sudo", "-n", "iptables", "-L", "-n", "-t", "nat"],
        ]
        assert run.calls[0][1]["timeout"] == 2

    def test_should_report_unavailable_when_binary_missing(self, run):
        run.fail_on = "--version"

        assert IptablesDriver().is_available() is False

    def test_should_report_unavailable_when_sudo_check_fails(self, run):
        run.fail_on = "-t nat"

        assert IptablesDriver().is_available() is False

    def test_should_report_unavailable_when_iptables_not_installed(self, run, monkeypatch):
        def raise_fnf(argv, **kwargs):
            raise FileNotFoundError(argv[0])

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", raise_fnf)

        assert IptablesDriver().is_available() is False

    def test_should_report_unavailable_when_check_times_out(self, run):
        run.timeout_on = "--version"

        assert IptablesDriver().is_available() is False

    def test_should_report_unavailable_on_called_process_error(self, run, monkeypatch):
        def raise_cpe(argv, **kwargs):
            raise subprocess.CalledProcessError(1, argv)

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", raise_cpe)

        assert IptablesDriver().is_available() is False

    def test_should_expose_driver_name(self):
        assert IptablesDriver().name() == "iptables"


class TestDefaultInterface:
    def test_should_parse_device_from_default_route(self, run, monkeypatch):
        def answer(argv, **kwargs):
            run.calls.append((list(argv), kwargs))
            return subprocess.CompletedProcess(
                list(argv), 0,
                "default via 192.168.1.1 dev wlp3s0 proto dhcp src 192.168.1.50 metric 600\n", "",
            )

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", answer)

        assert IptablesDriver().get_default_interface() == "wlp3s0"
        assert run.argv_list[0] == ["ip", "route", "show", "default"]

    def test_should_return_none_when_route_lookup_fails(self, run, monkeypatch):
        def raise_cpe(argv, **kwargs):
            raise subprocess.CalledProcessError(1, argv)

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", raise_cpe)

        assert IptablesDriver().get_default_interface() is None

    def test_should_return_none_when_no_device_in_output(self, run, monkeypatch):
        def answer(argv, **kwargs):
            return subprocess.CompletedProcess(list(argv), 0, "default proto static\n", "")

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", answer)

        assert IptablesDriver().get_default_interface() is None


class TestSetupNat:
    def test_should_install_masquerade_and_forwarding_for_ipv4(self, run):
        assert IptablesDriver().setup_nat(NAT_V4) is True

        assert run.argv_list == [
            ["sudo", "-n", "iptables", "-t", "nat", "-A", "POSTROUTING",
             "-s", "10.8.0.0/24", "-o", "eth0", "-j", "MASQUERADE"],
            ["sudo", "-n", "iptables", "-A", "FORWARD", "-i", "wg0", "-j", "ACCEPT"],
            ["sudo", "-n", "iptables", "-A", "FORWARD", "-o", "wg0", "-m", "state",
             "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ]

    def test_should_install_ip6tables_rules_for_ipv6(self, run):
        assert IptablesDriver().setup_nat(NAT_V6) is True

        assert run.argv_list == [
            ["sudo", "-n", "ip6tables", "-t", "nat", "-A", "POSTROUTING",
             "-s", "fd00:8::/64", "-o", "eth0", "-j", "MASQUERADE"],
            ["sudo", "-n", "ip6tables", "-A", "FORWARD", "-i", "wg0", "-j", "ACCEPT"],
            ["sudo", "-n", "ip6tables", "-A", "FORWARD", "-o", "wg0", "-m", "state",
             "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ]

    def test_should_apply_ipv4_then_ipv6_rules_for_dual_stack(self, run):
        assert IptablesDriver().setup_nat(NAT_BOTH) is True

        families = [argv[2] for argv in run.argv_list]
        assert families == ["iptables"] * 3 + ["ip6tables"] * 3

    def test_should_skip_everything_when_no_subnet_given(self, run):
        assert IptablesDriver().setup_nat(
            NATConfig(interface="wg0", ipv4_subnet=None, ipv6_subnet=None, default_interface="eth0")
        ) is True
        assert run.calls == []

    def test_should_tolerate_ipv6_being_unsupported(self, run):
        run.fail_on = "ip6tables"

        assert IptablesDriver().setup_nat(NAT_BOTH) is True
        assert run.argv_list[-1][2] == "ip6tables"

    def test_should_report_failure_when_ipv4_rule_is_rejected(self, run):
        run.fail_on = "POSTROUTING"

        assert IptablesDriver().setup_nat(NAT_V4) is False

    def test_should_report_failure_when_command_times_out(self, run):
        run.timeout_on = "iptables"

        assert IptablesDriver().setup_nat(NAT_V4) is False


class TestCleanupNat:
    def test_should_delete_ipv4_rules_in_reverse_order_without_failing(self, run):
        assert IptablesDriver().cleanup_nat(NAT_V4) is True

        assert run.argv_list == [
            ["sudo", "-n", "iptables", "-D", "FORWARD", "-o", "wg0", "-m", "state",
             "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
            ["sudo", "-n", "iptables", "-D", "FORWARD", "-i", "wg0", "-j", "ACCEPT"],
            ["sudo", "-n", "iptables", "-t", "nat", "-D", "POSTROUTING",
             "-s", "10.8.0.0/24", "-o", "eth0", "-j", "MASQUERADE"],
        ]
        assert all(kwargs["check"] is False for _, kwargs in run.calls)

    def test_should_delete_ip6tables_rules(self, run):
        assert IptablesDriver().cleanup_nat(NAT_V6) is True

        assert [argv[2] for argv in run.argv_list] == ["ip6tables"] * 3
        assert run.argv_list[2] == [
            "sudo", "-n", "ip6tables", "-t", "nat", "-D", "POSTROUTING",
            "-s", "fd00:8::/64", "-o", "eth0", "-j", "MASQUERADE",
        ]

    def test_should_still_succeed_when_rules_do_not_exist(self, run):
        run.fail_on = "iptables"

        assert IptablesDriver().cleanup_nat(NAT_V4) is True
        assert len(run.calls) == 3

    def test_should_still_succeed_when_cleanup_times_out(self, run):
        run.timeout_on = "iptables"

        assert IptablesDriver().cleanup_nat(NAT_V4) is True


class TestHardeningBranches:
    def test_should_raise_when_password_prompt_is_detected_in_result(self, monkeypatch):
        def answer(argv, **kwargs):
            return subprocess.CompletedProcess(list(argv), 1, "", "sudo: a password is required")

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", answer)

        with pytest.raises(subprocess.CalledProcessError):
            _run_sudo_command(["sudo", "iptables", "-L"])

    def test_should_report_unavailable_when_sudo_check_asks_for_password(self, monkeypatch):
        def answer(argv, **kwargs):
            if "--version" in argv:
                return subprocess.CompletedProcess(list(argv), 0, "iptables v1.8.7", "")
            return subprocess.CompletedProcess(list(argv), 1, "", "sudo: a password is required")

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", answer)

        assert IptablesDriver().is_available() is False

    def test_should_swallow_called_process_error_during_cleanup(self, monkeypatch):
        def answer(argv, **kwargs):
            raise subprocess.CalledProcessError(1, argv, "", "Bad rule (does a matching rule exist?)")

        monkeypatch.setattr("app.services.firewall.iptables_driver.subprocess.run", answer)

        assert IptablesDriver().cleanup_nat(NAT_BOTH) is True
