"""
E15.2.7 — Anti-corruption layer between the Unity SDK event envelope and the
player_monetization event contract.

The Unity SDK emits a single canonical envelope (see GameFactory.Analytics.Events.GameEvent):

    { "event": "ad_show", "game": "...", "country": "US", "user_id": "u1",
      "session_id": "...", "timestamp_ms": 123, "timestamp": "2026-07-27T...",
      "props": { "ad_format": "reward", "placement": "rv_1" } }

The downstream validators/collector expect a `type`-keyed shape:

    { "type": "ad", "user_id": "u1", "ad_type": "reward", "show": true, ... }

This module maps one into the other so neither side has to change its contract.
Deterministic, no I/O, no external deps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

AD_EVENTS = {"ad_request", "ad_show", "ad_complete", "ad_revenue"}
GAME_EVENTS = {"level_start", "level_complete"}

# Envelope envelope keys that are NOT event props.
_ENVELOPE_KEYS = frozenset({
    "event", "game", "platform", "country", "user_id", "session_id",
    "timestamp_ms", "timestamp", "props",
})

# Envelope event_name -> python type
_TYPE_MAP = {
    "install": "player",
    "session_start": "player",
    "purchase": "player",
}


def _ms_to_iso(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _extract_props(env: Dict[str, Any]) -> Dict[str, Any]:
    """Reconcile the envelope's event-specific fields.

    The Unity SDK (GameFactory.Analytics.Events.GameEvent.ToDictionary) FLATTENS
    its ``props`` bag onto the top level of the envelope. This function accepts
    BOTH the flattened shape and an explicit nested ``"props"`` object, so the
    client and downstream consumers never have to agree on a single layout.
    """
    nested = env.get("props") or {}
    top = {k: v for k, v in env.items() if k not in _ENVELOPE_KEYS}
    merged = dict(nested)
    merged.update(top)  # top-level (flattened) props win on conflict
    return merged


def normalize_envelope(env: Dict[str, Any]) -> Dict[str, Any]:
    """Map one Unity envelope dict into the player_monetization `type`-shaped event.

    Events whose `event` name is unknown still pass through as `player` (the
    validator will reject or accept based on required fields) so nothing is
    silently dropped before reaching the validator.
    """
    env = env or {}
    ev = (env.get("event") or "").lower()
    props = _extract_props(env)
    out: Dict[str, Any] = {
        "user_id": env.get("user_id", ""),
        "timestamp": env.get("timestamp") or _ms_to_iso(env.get("timestamp_ms")),
        "country": env.get("country", ""),
        "game": env.get("game", ""),
        "session_id": env.get("session_id", ""),
    }

    if ev in AD_EVENTS:
        out["type"] = "ad"
        out["ad_type"] = props.get("ad_format") or props.get("format") or ""
        # Carry the channel context downstream (waterfall / network mix analysis
        # in the IAA Revenue OS needs network + placement, not just ad_type).
        out["network"] = props.get("network", "")
        out["placement"] = props.get("placement", "")
        if ev == "ad_request":
            out["request"] = True
        elif ev == "ad_show":
            out["show"] = True
        elif ev == "ad_complete":
            out["show"] = True
            out["complete"] = bool(props.get("completed", False))
        elif ev == "ad_revenue":
            out["show"] = True
            out["complete"] = True
            if "revenue" in props:
                try:
                    out["revenue"] = float(props["revenue"])
                except (TypeError, ValueError):
                    pass
            if "ecpm" in props:
                try:
                    out["ecpm"] = float(props["ecpm"])
                except (TypeError, ValueError):
                    pass
            if "latency" in props:
                try:
                    out["latency"] = int(props["latency"])
                except (TypeError, ValueError):
                    pass
            if "ad_unit" in props:
                out["ad_unit"] = props["ad_unit"]
    elif ev in GAME_EVENTS:
        out["type"] = "game"
        if "level" in props:
            try:
                out["level_start"] = int(props["level"])
            except (TypeError, ValueError):
                pass
        out["level_fail"] = 0
        out["fail_streak"] = 0
        out["level_complete"] = ev == "level_complete"
    else:
        out["type"] = _TYPE_MAP.get(ev, "player")
        if "level" in props:
            try:
                out["level"] = int(props["level"])
            except (TypeError, ValueError):
                pass
        if "play_time_sec" in props:
            try:
                out["play_time_sec"] = int(props["play_time_sec"])
            except (TypeError, ValueError):
                pass
        if "session_count" in props:
            try:
                out["session_count"] = int(props["session_count"])
            except (TypeError, ValueError):
                pass
    return out


def normalize_batch(envelopes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_envelope(e) for e in envelopes]
