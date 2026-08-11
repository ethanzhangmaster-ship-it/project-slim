"""
E14.3.3 — Module 4: Change -> Remote Config Operation Mapper
=============================================================

The translation brain for the experience side. It turns the OS-internal
`Change` (target / change_type / old / new) into a Remote-Config-shaped
`RemoteConfigOperation`. The Provider never sees a config key literal; the
Strategy Engine never sees Firebase. This is the single place where a mutation
gene like "frequency_gene" (or a direct parameter "ads.reward_frequency")
becomes a canonical Remote Config key.

Gene / target grammar (any of these resolve):
    "frequency_gene"          -> ads.reward_frequency
    "cooldown_gene"           -> ads.reward_cooldown
    "reward_gene"             -> ads.reward_multiplier
    "interstitial_gene"       -> ads.interstitial_interval
    a direct key ("ads.reward_frequency")             -> itself
    a bare alias ("reward_frequency" / "reward_multiplier" / ...)

New-value grammar (mirrors MAX flexibility):
    change.new is a scalar            -> absolute new value
    change.new == {"multiplier": m}   -> new = old * m   (rounded for int knobs)
    change.new == {"delta": d}        -> new = old + d
    change.new == {"delta_pct": p}    -> new = old * (1 + p/100)

Rejects unknown genes / missing values with ConfigMappingError, which the
Provider converts into a success=False ProviderResult — never an exception leak.
"""
from __future__ import annotations

from typing import Any

from monetization.providers.remote_config.config_models import (
    ConfigMappingError, RemoteConfigOperation,
)


# --------------------------------------------------------------------------- #
# Gene / alias -> canonical Remote Config key
# --------------------------------------------------------------------------- #
CONFIG_GENE_MAP = {
    # genes (Strategy Engine vocabulary)
    "frequency_gene": "ads.reward_frequency",
    "cooldown_gene": "ads.reward_cooldown",
    "reward_gene": "ads.reward_multiplier",
    "interstitial_gene": "ads.interstitial_interval",
    # bare aliases
    "reward_frequency": "ads.reward_frequency",
    "reward_cooldown": "ads.reward_cooldown",
    "reward_multiplier": "ads.reward_multiplier",
    "interstitial_interval": "ads.interstitial_interval",
    # direct canonical keys (identity)
    "ads.reward_frequency": "ads.reward_frequency",
    "ads.reward_cooldown": "ads.reward_cooldown",
    "ads.reward_multiplier": "ads.reward_multiplier",
    "ads.interstitial_interval": "ads.interstitial_interval",
    "ads.frequency": "ads.reward_frequency",
}

# canonical key -> knob family (drives validation + int/float coercion)
_KEY_CATEGORY = {
    "ads.reward_frequency": "frequency",
    "ads.reward_cooldown": "cooldown",
    "ads.reward_multiplier": "multiplier",
    "ads.interstitial_interval": "interval",
}

# families whose values are integers (frequency counts, seconds, intervals)
_INT_CATEGORIES = {"frequency", "cooldown", "interval"}


def resolve_key(target: str) -> str:
    """Resolve an OS gene / alias / direct key into a canonical config key."""
    if not target:
        raise ConfigMappingError("empty target: cannot resolve a config key")
    key = CONFIG_GENE_MAP.get(target)
    if key is None:
        # allow explicit dotted keys we simply haven't aliased, but refuse
        # anything that is clearly not a namespaced config key.
        if "." in target:
            return target
        raise ConfigMappingError(f"unknown config gene/key: {target!r}")
    return key


def category_for(key: str) -> str:
    return _KEY_CATEGORY.get(key, "generic")


def _coerce(category: str, value: Any) -> Any:
    if value is None:
        return None
    if category in _INT_CATEGORIES:
        return int(round(float(value)))
    if category == "multiplier":
        return round(float(value), 4)
    return value


def _resolve_new(category: str, old: Any, new_spec: Any) -> Any:
    """Compute the absolute new value from a scalar or a relative spec dict."""
    if isinstance(new_spec, dict):
        if old is None:
            raise ConfigMappingError(
                "relative config change requires an old value")
        base = float(old)
        if "multiplier" in new_spec:
            return _coerce(category, base * float(new_spec["multiplier"]))
        if "delta" in new_spec:
            return _coerce(category, base + float(new_spec["delta"]))
        if "delta_pct" in new_spec:
            return _coerce(category, base * (1.0 + float(new_spec["delta_pct"]) / 100.0))
        raise ConfigMappingError(
            "relative config change needs one of "
            "{multiplier|delta|delta_pct}")
    if new_spec is None:
        raise ConfigMappingError("config change requires a new value")
    return _coerce(category, new_spec)


def map_change_to_config_op(change) -> RemoteConfigOperation:
    """Translate an internal Change into a Remote Config operation."""
    ct = change.change_type

    # revenue_read etc. never belong here — routing should prevent it, but we
    # fail loud if a mis-routed Change arrives.
    if ct not in ("reward_frequency", "ad_frequency", "remote_param"):
        raise ConfigMappingError(
            f"unsupported change_type for Remote Config: {ct!r}")

    key = resolve_key(change.target)
    category = category_for(key)
    old_value = _coerce(category, change.old) if change.old is not None else None
    new_value = _resolve_new(category, change.old, change.new)

    return RemoteConfigOperation(
        operation="UPDATE_CONFIG", key=key, category=category,
        old_value=old_value, new_value=new_value,
    )
