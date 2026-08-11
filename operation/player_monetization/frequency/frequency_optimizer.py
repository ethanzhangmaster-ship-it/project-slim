"""
E15.2.7 §6 — Dynamic per-user frequency caps.

Replaces static "every 3 minutes" rules with segment-aware per-user limits.
Higher-value players get more ads; at-risk players get fewer (protect retention).
"""
from __future__ import annotations

from operation.player_monetization.models import FrequencyRule, PlayerSegment

_RULES = {
    "high_value_ad_player": (5, 120, 20),
    "power_user":             (3, 180, 15),
    "moderate_ad_player":     (3, 180, 10),
    "casual_player":          (2, 300, 5),
    "new_player":             (2, 240, 6),
    "at_risk_churn":          (1, 600, 2),
}


class FrequencyOptimizer:
    def optimize(self, user_id: str, segment: PlayerSegment,
                 fatigue: float = 0.0) -> FrequencyRule:
        mps, cd, mpd = _RULES.get(segment.segment,
                                  _RULES["moderate_ad_player"])
        if fatigue > 0.5:
            mps = max(1, mps - 1)
            cd = int(cd * 1.5)
            mpd = max(1, mpd - 2)
        return FrequencyRule(
            user_id=user_id, ad_type="all",
            max_per_session=mps, cooldown_sec=cd,
            max_per_day=mpd, fatigue_level=fatigue,
            last_shown_at="")
