"""Tests for ``app.services.firewall.rule`` (rule model + matching helpers)."""

import re

import pytest
from pydantic import ValidationError

from app.services.firewall.rule import (
    FirewallRule,
    _generate_id,
    _ip_in_cidr,
    _port_matches,
    validate_rule,
)


class TestRuleIdentity:
    def test_should_generate_stable_id_from_rule_name(self):
        assert _generate_id("allow-ssh") == _generate_id("allow-ssh")
        assert _generate_id("allow-ssh") != _generate_id("allow-http")
        assert 0 <= _generate_id("allow-ssh") < 1_000_000

    def test_should_compare_rules_by_serialized_fields(self):
        a = FirewallRule(name="ssh", port="22")
        b = FirewallRule(name="ssh", port="22")
        c = FirewallRule(name="ssh", port="2222")

        assert a == b
        assert not (a == c)
        assert a != "ssh"

    def test_should_serialize_defaults_in_model_dump(self):
        data = FirewallRule(name="ssh").model_dump()

        assert data == {
            "name": "ssh",
            "action": "accept",
            "protocol": "tcp",
            "src_ip": "any",
            "dst_ip": "any",
            "port": "any",
            "enabled": True,
        }


class TestRuleValidation:
    def test_should_lowercase_action_and_protocol(self):
        rule = FirewallRule(name="x", action="DROP", protocol="UDP")

        assert rule.action == "drop"
        assert rule.protocol == "udp"

    @pytest.mark.parametrize("action", ["allow", "deny", ""])
    def test_should_reject_unknown_action(self, action):
        with pytest.raises(ValidationError, match="Invalid action"):
            FirewallRule(name="x", action=action)

    @pytest.mark.parametrize("protocol", ["sctp", "gre", ""])
    def test_should_reject_unknown_protocol(self, protocol):
        with pytest.raises(ValidationError, match="Invalid protocol"):
            FirewallRule(name="x", protocol=protocol)

    def test_should_normalise_any_values(self):
        rule = FirewallRule(name="x", src_ip="ANY", dst_ip="Any", port="ANY")

        assert (rule.src_ip, rule.dst_ip, rule.port) == ("any", "any", "any")

    def test_should_keep_cidr_and_ports_verbatim(self):
        rule = FirewallRule(name="x", src_ip="10.0.0.0/8", dst_ip="192.168.1.5", port="8000-8100")

        assert rule.src_ip == "10.0.0.0/8"
        assert rule.dst_ip == "192.168.1.5"
        assert rule.port == "8000-8100"


class TestRuleMatching:
    def test_should_match_everything_for_wildcard_rule(self):
        rule = FirewallRule(name="all")

        assert rule.matches("8.8.8.8", "10.0.0.1", "tcp", "443")

    def test_should_match_source_subnet(self):
        rule = FirewallRule(name="lan", src_ip="192.168.0.0/16", port="22")

        assert rule.matches("192.168.4.10", "10.0.0.1", "tcp", "22")
        assert not rule.matches("172.16.0.5", "10.0.0.1", "tcp", "22")

    def test_should_match_exact_ip_without_prefix(self):
        rule = FirewallRule(name="host", dst_ip="10.8.0.2")

        assert rule.matches("1.2.3.4", "10.8.0.2", "tcp", "1")
        assert not rule.matches("1.2.3.4", "10.8.0.3", "tcp", "1")

    def test_should_ignore_peer_ip_when_side_is_wildcard(self):
        rule = FirewallRule(name="lan", src_ip="10.0.0.0/8")

        assert rule.matches("any", "10.0.0.1", "tcp", "80")

    def test_should_match_protocol_case_insensitively(self):
        rule = FirewallRule(name="udp", protocol="udp")

        assert rule.matches("any", "any", "UDP", "53")
        assert not rule.matches("any", "any", "tcp", "53")

    def test_should_match_any_protocol_when_rule_is_all(self):
        rule = FirewallRule(name="all-proto", protocol="all")

        assert rule.matches("any", "any", "icmp", "any")

    def test_should_match_port_ranges(self):
        rule = FirewallRule(name="range", port="1000-2000")

        assert rule.matches("any", "any", "tcp", "1500")
        assert rule.matches("any", "any", "tcp", "1000")
        assert rule.matches("any", "any", "tcp", "2000")
        assert not rule.matches("any", "any", "tcp", "2001")

    def test_should_reject_non_numeric_port_against_port_rule(self):
        rule = FirewallRule(name="ssh", port="22")

        assert not rule.matches("any", "any", "tcp", "https")


class TestMatchingHelpers:
    @pytest.mark.parametrize(
        "port, rule_port, expected",
        [
            ("22", "any", True),
            ("22", "22", True),
            ("22", "022", False),
            ("22", "20-25", True),
            ("26", "20-25", False),
            ("http", "80", False),
            ("80", "not-a-port", False),
        ],
    )
    def test_should_decide_port_membership(self, port, rule_port, expected):
        assert _port_matches(port, rule_port) is expected

    @pytest.mark.parametrize(
        "ip, cidr, expected",
        [
            ("10.0.0.5", "any", True),
            ("10.0.0.5", "10.0.0.5", True),
            ("10.0.0.6", "10.0.0.5", False),
            ("10.0.0.5", "10.0.0.0/24", True),
            ("10.0.1.5", "10.0.0.0/24", False),
            ("any", "10.0.0.0/24", True),
            ("10.0.0.5", "10.0.0.0/33", False),
            ("10.0.0.5", "10.0.0.0/x", False),
            ("10.0.0.5", "10.0.0/24", False),
            ("10.0.0.256", "10.0.0.0/24", False),
            ("10.0.0.5", "0.0.0.0/0", True),
        ],
    )
    def test_should_decide_cidr_membership(self, ip, cidr, expected):
        assert _ip_in_cidr(ip, cidr) is expected


class TestValidateRule:
    def test_should_accept_rule_instance(self):
        assert validate_rule(FirewallRule(name="ok")) is True

    def test_should_accept_complete_dict(self):
        assert validate_rule({"name": "ok", "action": "drop", "protocol": "udp"}) is True

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "missing-action", "protocol": "tcp"},
            {"action": "drop", "protocol": "tcp"},
            {"name": "bad-action", "action": "explode", "protocol": "tcp"},
            {"name": "bad-proto", "action": "drop", "protocol": "sctp"},
            42,
            None,
        ],
    )
    def test_should_reject_invalid_payloads(self, payload):
        assert validate_rule(payload) is False
