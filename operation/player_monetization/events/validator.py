"""
E15.2.7 §1 — Event validator.

Sanity-checks incoming player and ad events, and validates aggregated
PlayerProfile objects for downstream model consumers.
"""
from __future__ import annotations

from typing import Any, Dict, List

from operation.player_monetization.events.event_schema import (
    validate_ad_event, validate_game_event, validate_player_event,
)
from operation.player_monetization.models import PlayerProfile


class EventValidator:
    def validate(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        ok, failed = [], []
        for e in events:
            tp = e.get("type", "")
            if tp == "player":
                r = validate_player_event(e)
            elif tp == "ad":
                r = validate_ad_event(e)
            elif tp == "game":
                r = validate_game_event(e)
            else:
                r = {"ok": False, "missing": ["type"]}
            if r["ok"]:
                ok.append(e)
            else:
                failed.append({**e, "error": r})
        return {"ok": len(failed) == 0, "accepted": len(ok),
                "rejected": len(failed), "errors": failed}


def validate_profile(profile: PlayerProfile) -> Dict[str, Any]:
    """Sanity-checks on an aggregated profile before feeding to a model."""
    issues = []
    if profile.total_ad_shows > profile.total_ad_requests:
        issues.append("shows > requests")
    if profile.reward_accept_rate < 0 or profile.reward_accept_rate > 1:
        issues.append(f"reward_accept_rate {profile.reward_accept_rate} out of range")
    if profile.fail_rate < 0 or profile.fail_rate > 1:
        issues.append(f"fail_rate {profile.fail_rate} out of range")
    if profile.total_ad_revenue < 0:
        issues.append("negative total_ad_revenue")
    return {"ok": len(issues) == 0, "issues": issues}
