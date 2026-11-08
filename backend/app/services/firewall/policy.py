"""Firewall policy management functions."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# In-memory storage for testing
_default_policy: Optional[str] = "drop"  # Default to drop


def set_default_policy(policy: str) -> str:
    """
    Set the default firewall policy (accept or drop).
    
    Args:
        policy: "accept" or "drop"
        
    Returns:
        The set policy
    """
    valid_policies = ["accept", "drop"]
    if policy.lower() not in valid_policies:
        raise ValueError(f"Invalid policy: {policy}. Must be 'accept' or 'drop'")
    
    global _default_policy
    _default_policy = policy.lower()
    logger.info(f"Set default firewall policy to: {_default_policy}")
    return _default_policy


def get_default_policy() -> str:
    """
    Get the current default firewall policy.
    
    Returns:
        The current policy ("accept" or "drop")
    """
    return _default_policy


def apply_default_policy():
    """
    Apply the default policy to the firewall.
    
    In a real implementation, this would set the policy in iptables/nftables.
    """
    policy = get_default_policy()
    logger.info(f"Applying default firewall policy: {policy}")