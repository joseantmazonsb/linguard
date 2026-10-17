"""Firewall service for NAT/masquerading management."""

from .service import FirewallService
from .base import FirewallDriver, NATConfig
from .iptables_driver import IptablesDriver
from .dummy_driver import DummyFirewallDriver
from .rule import FirewallRule, FirewallRuleAction, validate_rule
from .rules import add_rule, remove_rule, update_rule, get_rules, get_rule, apply_rules

__all__ = [
    "FirewallService",
    "FirewallDriver",
    "NATConfig",
    "IptablesDriver",
    "DummyFirewallDriver",
    "FirewallRule",
    "FirewallRuleAction",
    "validate_rule",
    "add_rule",
    "remove_rule",
    "update_rule",
    "get_rules",
    "get_rule",
    "apply_rules",
]
