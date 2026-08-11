"""
E14.3.2 — Module 4: Change -> MAX Operation Mapper
===================================================

The translation brain. It turns the OS-internal `Change` (target / change_type
/ old / new) into a MAX-shaped `MaxOperation`. The Provider never sees MAX API
details; the Executor never sees geo parsing. This is the single place where
"US_android_reward_applovin_floor" becomes (country=US, ad_unit=reward, ...).

Target grammar:  <COUNTRY>_<platform>_<ad_unit>[_<network>][_<suffix>]
  e.g. "US_android_reward_applovin_floor"
       "US_android_reward_applovin_waterfall"

Rejects invalid input (bad geo, unsupported type) with MaxMappingError, which
the Provider converts into a success=False ProviderResult — never an exception
leak to the Executor.
"""
from __future__ import annotations

from typing import List

from monetization.providers.max.max_models import MaxMappingError, MaxOperation


# A geo is a 2-letter uppercase code (ISO-3166-1 alpha-2 subset we accept).
def _is_valid_geo(code: str) -> bool:
    return len(code) == 2 and code.isalpha() and code.isupper()


def parse_target(target: str):
    """Return (country, platform, ad_unit, network) or raise MaxMappingError."""
    parts = [p for p in target.split("_") if p]
    if len(parts) < 3:
        raise MaxMappingError(f"cannot parse target (need >=3 segments): {target!r}")
    country = parts[0]
    if not _is_valid_geo(country):
        raise MaxMappingError(f"invalid geo in target: {country!r}")
    platform = parts[1]
    ad_unit = parts[2]
    network = parts[3] if len(parts) > 3 else ""
    return country, platform, ad_unit, network


def parse_priority_change(spec) -> int:
    """'+1' = move up one position (toward index 0); '-1' = down one."""
    spec = str(spec).strip()
    if not spec:
        raise MaxMappingError("empty priority_change")
    sign = 1 if spec[0] == "+" else -1 if spec[0] == "-" else 1
    digits = spec.lstrip("+-")
    if not digits.isdigit():
        raise MaxMappingError(f"invalid priority_change: {spec!r}")
    return int(digits) * sign


def move_network(order: List[str], network: str, delta: int) -> List[str]:
    """Move `network` by `delta` positions (positive=up/closer to front)."""
    if network not in order:
        raise MaxMappingError(f"network {network!r} not present in waterfall order")
    idx = order.index(network)
    new_idx = max(0, min(len(order) - 1, idx - delta))
    order = list(order)
    order.pop(idx)
    order.insert(new_idx, network)
    return order


def _resolve_waterfall_new(change, old_order: List[str]) -> List[str]:
    new = change.new
    if isinstance(new, list):
        return list(new)
    if isinstance(new, dict):
        net = new.get("network")
        pc = new.get("priority_change")
        if net and pc is not None:
            return move_network(old_order, net, parse_priority_change(pc))
    raise MaxMappingError(
        "waterfall_priority requires new order (list) or "
        "{network, priority_change} spec"
    )


def map_change_to_operation(change, app_id: str) -> MaxOperation:
    """Translate an internal Change into a MAX operation."""
    country, platform, ad_unit, network = parse_target(change.target)
    ct = change.change_type

    if ct == "bid_floor":
        if change.old is None or change.new is None:
            raise MaxMappingError("bid_floor requires old and new values")
        try:
            old_v = float(change.old)
            new_v = float(change.new)
        except (TypeError, ValueError):
            raise MaxMappingError("bid_floor old/new must be numeric")
        multiplier = round(new_v / old_v, 4) if old_v else None
        return MaxOperation(
            operation="UPDATE_BID_FLOOR", app_id=app_id, country=country,
            ad_unit=ad_unit, network=network,
            old_value=old_v, new_value=new_v, multiplier=multiplier,
        )

    if ct == "waterfall_priority":
        old_order = change.old if isinstance(change.old, list) else []
        if not old_order:
            raise MaxMappingError("waterfall_priority requires a non-empty old order")
        new_order = _resolve_waterfall_new(change, old_order)
        return MaxOperation(
            operation="UPDATE_WATERFALL_PRIORITY", app_id=app_id, country=country,
            ad_unit=ad_unit, network=network, placement=ad_unit,
            old_order=list(old_order), new_order=list(new_order),
        )

    if ct == "revenue_read":
        return MaxOperation(
            operation="READ_REVENUE", app_id=app_id, country=country,
            ad_unit=ad_unit, network=network, placement=ad_unit,
            date=change.note or "",
        )

    raise MaxMappingError(f"unsupported change_type for MAX: {ct!r}")
