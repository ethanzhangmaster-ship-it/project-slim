"""
E15.2.7 §1 — Event schemas and validation contracts.

Defines the exact field requirements for Unity SDK events so both the game
client (when wired) and the collector agree on the contract.

Deterministic — just schema validation, no I/O.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

PLAYER_REQUIRED = {"user_id", "timestamp"}
PLAYER_OPTIONAL = {"country", "level", "session_count", "play_time_sec"}

AD_REQUIRED = {"user_id", "ad_type", "timestamp"}
AD_OPTIONAL = {"request", "show", "complete", "revenue"}
AD_TYPES = {"reward", "interstitial", "banner"}

GAME_REQUIRED = {"user_id", "timestamp"}
GAME_OPTIONAL = {"level_start", "level_fail", "level_complete", "fail_streak"}


def validate_player_event(e: Dict[str, Any]) -> Dict[str, Any]:
    """Return {"ok": True} or {"ok": False, "missing": [...]}."""
    return _check(e, PLAYER_REQUIRED)


def validate_ad_event(e: Dict[str, Any]) -> Dict[str, Any]:
    r = _check(e, AD_REQUIRED)
    if r["ok"] and e.get("ad_type", "") not in AD_TYPES:
        return {"ok": False, "reason": f"unknown ad_type {e.get('ad_type')}"}
    return r


def validate_game_event(e: Dict[str, Any]) -> Dict[str, Any]:
    return _check(e, GAME_REQUIRED)


def _check(e: Dict[str, Any], required: Set[str]) -> Dict[str, Any]:
    missing = [k for k in required if k not in e or e[k] is None]
    if missing:
        return {"ok": False, "missing": missing}
    return {"ok": True}
