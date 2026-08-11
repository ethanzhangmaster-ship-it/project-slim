"""
E15.2.7 §2 — Player lifecycle stage.

Determines where the player is in their lifecycle based on days_active and
recent activity. Stages: NEW → ENGAGED → CHURNING → LAPSED.

The lifecycle feeds into frequency caps (be gentler with NEW / CHURNING) and
ad opportunity logic (don't hammer a CHURNING player).
"""
from __future__ import annotations

from typing import Optional

from operation.player_monetization.models import PlayerProfile


class LifecycleDetector:
    NEW_DAYS = 2
    CHURN_INACTIVE_DAYS = 3
    LAPSED_INACTIVE_DAYS = 14

    def stage(self, profile: PlayerProfile,
              days_since_last_active: Optional[int] = None) -> str:
        if profile.days_active <= self.NEW_DAYS:
            return "NEW"
        d = days_since_last_active
        if d is not None:
            if d >= self.LAPSED_INACTIVE_DAYS:
                return "LAPSED"
            if d >= self.CHURN_INACTIVE_DAYS:
                return "CHURNING"
        if profile.active:
            return "ENGAGED"
        return "CHURNING"
