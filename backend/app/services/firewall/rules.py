"""Firewall rule management functions."""

import logging
from typing import List, Optional
from .rule import FirewallRule

logger = logging.getLogger(__name__)


# In-memory storage for testing
_firewall_rules: List[FirewallRule] = []


def add_rule(rule: FirewallRule) -> FirewallRule:
    """
    Add a firewall rule.
    
    Args:
        rule: FirewallRule to add
        
    Returns:
        The added rule with ID
        
    Raises:
        ValueError: If rule is invalid
    """
    if not validate_rule(rule):
        raise ValueError(f"Invalid rule: {rule}")
    
    # Add ID to the rule
    rule.id = len(_firewall_rules) + 1
    
    # Add to in-memory storage
    _firewall_rules.append(rule)
    logger.info(f"Added firewall rule: {rule.name} (ID: {rule.id})")
    return rule


def remove_rule(rule_id: int) -> bool:
    """
    Remove a firewall rule by ID.
    
    Args:
        rule_id: ID of the rule to remove
        
    Returns:
        True if rule was removed, False otherwise
    """
    global _firewall_rules
    for i, rule in enumerate(_firewall_rules):
        if rule.id == rule_id:
            removed = _firewall_rules.pop(i)
            logger.info(f"Removed firewall rule: {removed.name}")
            return True
    logger.warning(f"Rule with ID {rule_id} not found")
    return False


def update_rule(rule_id: int, updates: dict) -> Optional[FirewallRule]:
    """
    Update a firewall rule.
    
    Args:
        rule_id: ID of the rule to update
        updates: Dictionary of fields to update
        
    Returns:
        Updated rule if found, None otherwise
    """
    global _firewall_rules
    for rule in _firewall_rules:
        if rule.id == rule_id:
            # Update fields
            for key, value in updates.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            logger.info(f"Updated firewall rule: {rule.name}")
            return rule
    logger.warning(f"Rule with ID {rule_id} not found")
    return None


def get_rules() -> List[FirewallRule]:
    """
    Get all firewall rules.
    
    Returns:
        List of all firewall rules
    """
    return list(_firewall_rules)


def get_rule(rule_id: int) -> Optional[FirewallRule]:
    """
    Get a firewall rule by ID.
    
    Args:
        rule_id: ID of the rule to get
        
    Returns:
        Rule if found, None otherwise
    """
    global _firewall_rules
    for rule in _firewall_rules:
        if rule.id == rule_id:
            return rule
    return None


def apply_rules(rules: Optional[List[FirewallRule]] = None) -> bool:
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
        if rule.enabled:
            logger.info(f"Applying firewall rule: {rule.name}")
    
    return True
