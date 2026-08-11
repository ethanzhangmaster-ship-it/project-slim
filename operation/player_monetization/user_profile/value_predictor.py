"""
E15.2.7 §2 — Player value prediction.

Estimates 30-day IAA value and lifetime value from profile features using
deterministic rules + optional country-level Adjust averages.

  predicted_30d = (daily_rev_baseline * expected_days) * (1 - churn_prob)
  predicted_ltv = predicted_30d / churn_rate_estimate

No ML framework. Tune with real SDK data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.player_monetization.models import (
    PlayerProfile, PlayerSegment, ValuePrediction,
)


class ValuePredictor:
    # global baselines (conservative casual-game defaults)
    BASE_REV_PER_DAY = 0.03       # $0.03 IAA/day for an avg user
    COUNTRY_MULTIPLIER = {"US": 1.5, "GB": 1.3, "AU": 1.2,
                          "CN": 0.3, "IN": 0.15, "BR": 0.2,
                          "DE": 1.1, "JP": 1.4, "KR": 0.8}

    def predict(self, profile: PlayerProfile,
                segment: Optional[PlayerSegment] = None
                ) -> ValuePrediction:
        seg = segment.segment if segment else "new_player"
        mult = self.COUNTRY_MULTIPLIER.get(profile.country.upper(), 1.0)
        daily = self.BASE_REV_PER_DAY * mult
        # segment modifiers
        if seg == "high_value_ad_player":
            daily *= 2.0; churn_r = 0.05; days = 25
        elif seg == "power_user":
            daily *= 1.2; churn_r = 0.08; days = 28
        elif seg == "moderate_ad_player":
            daily *= 1.0; churn_r = 0.15; days = 18
        elif seg == "casual_player":
            daily *= 0.4; churn_r = 0.35; days = 7
        elif seg == "at_risk_churn":
            daily *= 0.2; churn_r = 0.7; days = 3
        else:  # new_player
            daily *= 0.5; churn_r = 0.3; days = 10
        d30 = daily * min(days, 30 - profile.days_active) * (1 - churn_r)
        ltv = (daily * 30 / churn_r) if churn_r > 0 else (daily * 30)
        conf = max(0.3, 0.5 + (profile.days_active / 30) * 0.3
                   + (1 - churn_r) * 0.2)
        return ValuePrediction(
            user_id=profile.user_id, segment=seg,
            predicted_30d_iaa=round(d30, 2),
            predicted_ltv=round(ltv, 2),
            confidence=round(min(conf, 0.95), 2),
            features={"daily_rev": round(daily, 4), "churn_rate": round(churn_r, 2),
                      "country_mult": mult, "segment": seg},
        )
