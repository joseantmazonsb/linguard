"""Firewall rule management functions."""

import logging
from typing import List, Optional
from .rule import FirewallRule, _ip_in_cidr, _port_matches, validate_rule

logger = logging.getLogger(__name__)


# In-memory storage for testing
_firewall_rules: List[FirewallRule] = []


def add_rule(rule: FirewallRule) -> dict:
    """
    Add a firewall rule.
    
    Args:
        rule: FirewallRule to add
        
    Returns:
        The added rule as dictionary with ID
        
    Raises:
        ValueError: If rule is invalid
    """
    if not validate_rule(rule):
        raise ValueError(f"Invalid rule: {rule}")
    
    # Create a copy with ID
    rule_dict = {
        "name": rule.name,
        "action": rule.action,
        "protocol": rule.protocol,
        "src_ip": rule.src_ip,
        "dst_ip": rule.dst_ip,
        "port": rule.port,
        "enabled": rule.enabled
    }
    rule_dict["id"] = len(_firewall_rules) + 1
    
    # Add to in-memory storage
    _firewall_rules.append(rule_dict)
    logger.info(f"Added firewall rule: {rule_dict['name']} (ID: {rule_dict['id']})")
    return rule_dict


def remove_rule(rule: FirewallRule) -> dict:
    """
    Remove a firewall rule.
    
    Args:
        rule: FirewallRule to remove
        
    Returns:
        The removed rule as dictionary
        
    Raises:
        ValueError: If rule is not found
    """
    global _firewall_rules
    for i, r in enumerate(_firewall_rules):
        if r.get("name") == rule.name and r.get("action") == rule.action:
            removed = _firewall_rules.pop(i)
            logger.info(f"Removed firewall rule: {removed['name']}")
            return removed
    logger.warning(f"Rule {rule.name} not found")
    raise ValueError(f"Rule {rule.name} not found")


def update_rule(rule: FirewallRule, updates: dict) -> dict:
    """
    Update a firewall rule.
    
    Args:
        rule: FirewallRule to update
        updates: Dictionary of fields to update
        
    Returns:
        Updated rule as dictionary
        
    Raises:
        ValueError: If rule is not found
    """
    global _firewall_rules
    for r in _firewall_rules:
        if r.get("name") == rule.name and r.get("action") == rule.action:
            # Create updated dictionary
            updated = r.copy()
            # Update fields
            for key, value in updates.items():
                if key in updated:
                    updated[key] = value
            logger.info(f"Updated firewall rule: {updated['name']}")
            return updated
    logger.warning(f"Rule {rule.name} not found")
    raise ValueError(f"Rule {rule.name} not found")


def get_rules() -> list:
    """
    Get all firewall rules.
    
    Returns:
        List of all firewall rules as dictionaries
    """
    return list(_firewall_rules)


def get_rule(rule: FirewallRule) -> dict:
    """
    Get a firewall rule.
    
    Args:
        rule: FirewallRule to get
        
    Returns:
        Rule as dictionary if found
        
    Raises:
        ValueError: If rule is not found
    """
    global _firewall_rules
    for r in _firewall_rules:
        if r.get("name") == rule.name and r.get("action") == rule.action:
            return r
    logger.warning(f"Rule {rule.name} not found")
    raise ValueError(f"Rule {rule.name} not found")


def apply_rules(rules: Optional[list] = None) -> bool:
    """
    Apply firewall rules to the system.
    
    Args:
        rules: List of rules to apply (uses all rules if None)
        
    Returns:
        True if rules were applied successfully
    """
    if rules is None:
        rules = _firewall_rules
    
    if not rules:
        logger.info("No firewall rules to apply")
        return True
    
    # In a real implementation, this would apply rules to iptables
    # For now, we just log that rules would be applied
    for rule in rules:
        if rule.get("enabled", True):
            logger.info(f"Applying firewall rule: {rule.get('name')}")
    
    return True
