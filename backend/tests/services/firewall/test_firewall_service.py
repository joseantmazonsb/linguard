"""Tests for ``app.services.firewall.service`` (driver selection + rule storage)."""

import logging
import subprocess
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.services.firewall.dummy_driver import DummyFirewallDriver
from app.services.firewall.iptables_driver import IptablesDriver
from app.services.firewall.rule import FirewallRule
from app.services.firewall.service import FirewallService


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    """Start every test from the production default (no debug bypass)."""
    monkeypatch.setattr(settings, "DEBUG_BYPASS_FIREWALL", False)
    return monkeypatch


class TestDriverDetection:
    def test_should_use_dummy_driver_when_debug_bypass_enabled(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "DEBUG_BYPASS_FIREWALL", True)

        with caplog.at_level(logging.WARNING):
            service = FirewallService()

        assert isinstance(service.driver, DummyFirewallDriver)
        assert service.is_available() is True
        assert service.get_driver_name() == "dummy (development mode)"
        assert "NAT will NOT work" in caplog.text

    def test_should_exit_when_platform_is_not_linux(self, monkeypatch):
        monkeypatch.setattr("app.services.firewall.service.platform.system", lambda: "Darwin")

        with pytest.raises(SystemExit) as exc:
            FirewallService()

        assert exc.value.code == 1

    def test_should_select_iptables_driver_when_available(self, monkeypatch):
        monkeypatch.setattr("app.services.firewall.service.platform.system", lambda: "Linux")
        monkeypatch.setattr(IptablesDriver, "is_available", lambda self: True)

        service = FirewallService()

        assert isinstance(service.driver, IptablesDriver)
        assert service.get_driver_name() == "iptables"

    def test_should_run_without_driver_when_iptables_is_unavailable(self, monkeypatch, caplog):
        monkeypatch.setattr("app.services.firewall.service.platform.system", lambda: "Linux")
        monkeypatch.setattr(IptablesDriver, "is_available", lambda self: False)

        with caplog.at_level(logging.WARNING):
            service = FirewallService()

        assert service.driver is None
        assert service.is_available() is False
        assert service.get_driver_name() is None
        assert "iptables not available" in caplog.text


class TestNatDelegation:
    class StubDriver:
        def __init__(self, default_interface="eth0", setup=True, cleanup=True):
            self.default_interface = default_interface
            self.setup_ok = setup
            self.cleanup_ok = cleanup
            self.configs = []

        def name(self):
            return "stub"

        def get_default_interface(self):
            return self.default_interface

        def setup_nat(self, config):
            self.configs.append(config)
            return self.setup_ok

        def cleanup_nat(self, config):
            self.configs.append(config)
            return self.cleanup_ok

    def _service(self, driver):
        service = FirewallService.__new__(FirewallService)
        service.driver = driver
        return service

    def test_should_build_nat_config_from_detected_default_interface(self):
        driver = self.StubDriver(default_interface="wlan0")
        service = self._service(driver)

        assert service.setup_nat("wg0", "10.8.0.0/24", "fd00::/64") is True

        config = driver.configs[0]
        assert (config.interface, config.ipv4_subnet, config.ipv6_subnet, config.default_interface) == (
            "wg0", "10.8.0.0/24", "fd00::/64", "wlan0",
        )

    def test_should_propagate_driver_failure_from_setup(self):
        service = self._service(self.StubDriver(setup=False))

        assert service.setup_nat("wg0", "10.8.0.0/24") is False

    def test_should_refuse_setup_without_driver(self):
        service = self._service(None)

        assert service.setup_nat("wg0", "10.8.0.0/24") is False

    def test_should_refuse_setup_when_default_interface_is_unknown(self):
        driver = self.StubDriver(default_interface=None)
        service = self._service(driver)

        assert service.setup_nat("wg0", "10.8.0.0/24") is False
        assert driver.configs == []

    def test_should_treat_cleanup_without_driver_as_success(self):
        assert self._service(None).cleanup_nat("wg0", "10.8.0.0/24") is True

    def test_should_fall_back_to_eth0_when_cleaning_up_without_default_route(self):
        driver = self.StubDriver(default_interface=None)
        service = self._service(driver)

        assert service.cleanup_nat("wg0", "10.8.0.0/24") is True
        assert driver.configs[0].default_interface == "eth0"

    def test_should_fall_back_to_en0_on_macos_when_cleaning_up(self, monkeypatch):
        monkeypatch.setattr("app.services.firewall.service.platform.system", lambda: "Darwin")
        driver = self.StubDriver(default_interface=None)
        service = self._service(driver)

        assert service.cleanup_nat("wg0", "10.8.0.0/24") is True
        assert driver.configs[0].default_interface == "en0"


class FakeDb:
    """Minimal sync DB stand-in implementing the calls FirewallService makes."""

    def __init__(self, rows=(), fail_on=None):
        self.rows = list(rows)
        self.fail_on = fail_on
        self.executed = []
        self.committed = 0
        self.rolled_back = 0

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed.append((sql, params))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError(f"boom on {self.fail_on}")
        result = MagicMock()
        result.fetchall.return_value = self.rows
        return result

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


class TestRuleStorage:
    def _service(self, db):
        service = FirewallService.__new__(FirewallService)
        service.driver = None
        service._mock_db = db
        return service

    def test_should_return_database_rows_as_dicts(self):
        db = FakeDb(rows=[{"id": 1, "name": "ssh"}, {"id": 2, "name": "web"}])

        rules = self._service(db).get_rules()

        assert rules == [{"id": 1, "name": "ssh"}, {"id": 2, "name": "web"}]
        assert db.executed[0][0] == "SELECT * FROM firewall_rule"

    def test_should_unwrap_row_mapping_objects(self):
        class Row:
            _mapping = {"id": 3, "name": "db"}

        assert self._service(FakeDb(rows=[Row()])).get_rules() == [{"id": 3, "name": "db"}]

    def test_should_return_empty_list_when_query_fails(self, caplog):
        with caplog.at_level(logging.ERROR):
            rules = self._service(FakeDb(fail_on="SELECT")).get_rules()

        assert rules == []
        assert "Error getting firewall rules" in caplog.text

    def test_should_insert_rule_with_normalised_values(self):
        db = FakeDb()

        assert self._service(db).add_rule(FirewallRule(name="ssh", src_ip="ANY", port="22")) == 1

        sql, params = db.executed[0]
        assert "INSERT INTO firewall_rule" in sql
        assert params == {
            "name": "ssh",
            "action": "accept",
            "protocol": "tcp",
            "src_ip": "any",
            "dst_ip": "any",
            "port": "22",
            "enabled": True,
        }
        assert db.committed == 1

    def test_should_roll_back_and_report_failure_when_insert_fails(self):
        db = FakeDb(fail_on="INSERT")

        assert self._service(db).add_rule(FirewallRule(name="ssh")) == 0
        assert db.rolled_back == 1
        assert db.committed == 0

    def test_should_delete_rule_by_name_and_action(self):
        db = FakeDb()
        rule = FirewallRule(name="ssh", action="drop")

        assert self._service(db).remove_rule(rule) is rule

        sql, params = db.executed[0]
        assert "DELETE FROM firewall_rule" in sql
        assert params == {"name": "ssh", "action": "drop"}
        assert db.committed == 1

    def test_should_raise_when_delete_fails(self):
        db = FakeDb(fail_on="DELETE")

        with pytest.raises(RuntimeError):
            self._service(db).remove_rule(FirewallRule(name="ssh"))
        assert db.rolled_back == 1

    def test_should_apply_only_enabled_rules(self, caplog):
        db = FakeDb()
        service = self._service(db)

        with caplog.at_level(logging.INFO):
            result = service.apply_rules([
                {"name": "on", "enabled": True},
                {"name": "off", "enabled": False},
            ])

        assert result is True
        assert "Applying firewall rule: on" in caplog.text
        assert "Applying firewall rule: off" not in caplog.text

    def test_should_succeed_without_rules(self, caplog):
        service = self._service(FakeDb())

        with caplog.at_level(logging.INFO):
            assert service.apply_rules([]) is True

        assert "No firewall rules to apply" in caplog.text

    def test_should_load_rules_from_database_when_none_passed(self):
        db = FakeDb(rows=[{"name": "from-db", "enabled": True}])

        assert self._service(db).apply_rules() is True
        assert "SELECT * FROM firewall_rule" in db.executed[0][0]

    def test_should_degrade_gracefully_when_no_database_is_configured(self, caplog):
        service = FirewallService.__new__(FirewallService)
        service.driver = None

        with caplog.at_level(logging.ERROR):
            assert service.get_rules() == []
            assert service.add_rule(FirewallRule(name="x")) == 0

        assert "Error getting firewall rules" in caplog.text


class TestDummyDriver:
    def test_should_report_success_for_every_operation(self, caplog):
        from app.services.firewall.base import NATConfig

        driver = DummyFirewallDriver()
        config = NATConfig(interface="wg0", ipv4_subnet="10.8.0.0/24", ipv6_subnet=None,
                           default_interface="eth0")

        with caplog.at_level(logging.WARNING):
            assert driver.is_available() is True
            assert driver.get_default_interface() == "eth0"
            assert driver.setup_nat(config) is True
            assert driver.cleanup_nat(config) is True

        assert "Pretending to set up NAT for interface 'wg0'" in caplog.text
        assert "(subnet: 10.8.0.0/24)" in caplog.text


def test_should_not_use_subprocess_when_dummy_driver_is_active(monkeypatch):
    """The dummy driver must never touch iptables."""
    monkeypatch.setattr(settings, "DEBUG_BYPASS_FIREWALL", True)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: calls.append(a))

    service = FirewallService()
    assert service.setup_nat("wg0", "10.8.0.0/24") is True
    assert calls == []
