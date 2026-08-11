"""
E15.2.7 §2 — Player segmentation.

Classifies each player into one of 6 segments based on their aggregated
profile features. The segments drive downstream decisions:

  high_value_ad_player — frequent, high-revenue ad viewers
  moderate_ad_player   — average ad engagement
  casual_player        — low engagement, occasional ads
  new_player           — first 1-2 sessions
  power_user           — high retention, high play time, not necessarily ads
  at_risk_churn        — fail rate high, recency dropping

Deterministic rules. No ML. Tune thresholds later when real SDK data flows.
"""
from __future__ import annotations

from typing import Any, Dict

from operation.player_monetization.models import PlayerProfile, PlayerSegment

SEGMENTS = ["high_value_ad_player", "moderate_ad_player", "casual_player",
            "new_player", "power_user", "at_risk_churn"]


class PlayerSegmenter:
    # thresholds (calibrated for puzzle/word casual)
    HIGH_REV_PER_SESSION = 0.05     # >$0.05 ad rev per session
    POWER_SESSION_MIN = 10
    POWER_LEVEL_MIN = 30
    HIGH_PLAY_MIN = 600             # 10 min/session avg

    def classify(self, profile: PlayerProfile) -> PlayerSegment:
        if profile.session_count <= 1:
            return self._seg(profile, "new_player", self._score(profile, 0.2))
        if profile.fail_rate > 0.5:
            return self._seg(profile, "at_risk_churn", self._score(profile, 0.3))
        if (profile.session_count >= self.POWER_SESSION_MIN
                and profile.level >= self.POWER_LEVEL_MIN):
            return self._seg(profile, "power_user", self._score(profile, 0.7))
        rev_per_sess = (profile.total_ad_revenue / profile.session_count
                        if profile.session_count else 0)
        if (rev_per_sess >= self.HIGH_REV_PER_SESSION
                and profile.session_count >= 3
                and profile.reward_accept_rate >= 0.5):
            return self._seg(profile, "high_value_ad_player",
                             self._score(profile, 0.9))
        if profile.session_count <= 3:
            return self._seg(profile, "casual_player", self._score(profile, 0.4))
        return self._seg(profile, "moderate_ad_player", self._score(profile, 0.5))

    def _score(self, p: PlayerProfile, base: float) -> float:
        s = base
        if p.total_ad_revenue > 0.5:
            s += 0.1
        if p.level > 20:
            s += 0.05
        if p.reward_accept_rate > 0.6:
            s += 0.05
        return min(round(s, 2), 1.0)

    def _seg(self, p: PlayerProfile, segment: str, score: float) -> PlayerSegment:
        tol = "high" if score > 0.7 else ("low" if score < 0.4 else "medium")
        risk = 0.7 if segment == "at_risk_churn" else (0.3 if segment == "new_player"
                     else 0.1)
        return PlayerSegment(user_id=p.user_id, segment=segment,
                             value_score=round(score * 100),
                             churn_risk=risk, ad_tolerance=tol,
                             confidence=score)
