"""
E14.3.3 — Module 5: Remote Config Safety Validator
===================================================

The experience side controls RETENTION. A bad config value is worse than a bad
bid floor: shipping `reward_frequency = 0` (ads every action) or `= 100` (no
reward ads) silently destroys either retention or revenue for real players.

This validator is the guardrail: every RemoteConfigOperation is checked against
a safe operating bound BEFORE it reaches the client. A violation becomes a
success=False ProviderResult (never an exception leak to the Executor).

Bounds are intentionally conservative for casual puzzle/word IAA games and can
be widened per-game later without touching the contract.
"""
from __future__ import annotations

from monetization.providers.remote_config.config_models import (
    ConfigValidationError, RemoteConfigOperation,
)


# category -> (min, max) inclusive safe bounds
SAFE_BOUNDS = {
    "frequency": (1, 20),        # reward ad every N actions: 1..20
    "cooldown": (0, 600),        # reward cooldown seconds: 0..600 (10 min)
    "multiplier": (0.5, 10.0),   # reward multiplier: 0.5x..10x
    "interval": (0, 3600),       # interstitial interval seconds: 0..1h
}


def validate_config_op(op: RemoteConfigOperation) -> None:
    """Raise ConfigValidationError if op.new_value is outside its safe bound."""
    if op.new_value is None:
        raise ConfigValidationError(f"{op.key}: new value is None")

    bounds = SAFE_BOUNDS.get(op.category)
    if bounds is None:
        # generic keys have no numeric bound; only require a non-null value.
        return

    lo, hi = bounds
    try:
        v = float(op.new_value)
    except (TypeError, ValueError):
        raise ConfigValidationError(
            f"{op.key}: value {op.new_value!r} is not numeric")

    if v < lo or v > hi:
        raise ConfigValidationError(
            f"{op.key}={op.new_value} outside safe bound [{lo}, {hi}] "
            f"for category {op.category!r}")


def is_valid(op: RemoteConfigOperation) -> bool:
    try:
        validate_config_op(op)
        return True
    except ConfigValidationError:
        return False
