"""
E15.2.7 §3/4/5 — Ad opportunity detection & prediction.

Given a player's profile + segment + recent gameplay context, decides whether
it's a good moment to show a reward or interstitial ad.

Core insight: not "every 30s pop an ad" but "AI judges the moment".
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.player_monetization.models import (
    AdOpportunity, PlayerProfile, PlayerSegment,
)


class RewardPredictor:
    """Predict the probability a user accepts a reward ad right now."""

    def predict(self, profile: PlayerProfile, segment: PlayerSegment,
                fail_streak: int = 0, session_early: bool = False) -> float:
        p = profile.reward_accept_rate or 0.5
        if fail_streak >= 2:
            p += 0.20
        if session_early:
            p += 0.10
        if segment.ad_tolerance == "high":
            p += 0.10
        elif segment.ad_tolerance == "low":
            p -= 0.10
        if segment.segment == "at_risk_churn":
            p -= 0.15
        return min(max(round(p, 2), 0.0), 1.0)


class InterstitialPredictor:
    """Predict interstitial value vs quit risk."""

    DEFAULT_ECPM_PROXY = 0.03   # $0.03 per interstitial (conservative)

    def predict(self, profile: PlayerProfile, segment: PlayerSegment,
                level_complete: bool = False,
                level_fail: bool = False,
                play_time_sec: int = 0) -> AdOpportunity:
        # expected revenue
        ecpm = profile.total_ad_revenue / profile.total_ad_shows \
            if profile.total_ad_shows else self.DEFAULT_ECPM_PROXY
        expected_rev = round(ecpm, 4)
        # quit risk
        risk = 0.15
        if level_complete:
            risk = 0.05  # natural break — low quit risk
        elif level_fail:
            risk = 0.30  # frustrated — higher quit risk
        if segment.ad_tolerance == "low":
            risk += 0.10
        elif segment.ad_tolerance == "high":
            risk -= 0.05
        if segment.segment == "at_risk_churn":
            risk += 0.20
        if play_time_sec < 60:   # barely started session
            risk += 0.10
        risk = min(max(round(risk, 2), 0.0), 1.0)
        decision = "show" if risk < 0.3 else ("skip" if risk > 0.5 else "defer")
        return AdOpportunity(
            user_id=profile.user_id, opportunity_type="interstitial",
            ad_probability=round(1.0 - risk, 2),
            expected_revenue=expected_rev,
            quit_risk=risk, decision=decision,
            reason=f"risk={risk:.2f} {'level_complete' if level_complete else 'mid_play'}")


class OpportunityDetector:
    """Top-level: for a given player, what ad(s) should we show right now?"""

    def __init__(self) -> None:
        self._reward = RewardPredictor()
        self._inter = InterstitialPredictor()

    def detect(self, profile: PlayerProfile, segment: PlayerSegment,
               fail_streak: int = 0, level_complete: bool = False,
               level_fail: bool = False, play_time_sec: int = 0,
               session_early: bool = False) -> List[AdOpportunity]:
        opps: List[AdOpportunity] = []
        # reward
        if fail_streak >= 1 or level_fail:
            rp = self._reward.predict(profile, segment, fail_streak,
                                      session_early)
            if rp > 0.5:
                opps.append(AdOpportunity(
                    user_id=profile.user_id, opportunity_type="reward",
                    ad_probability=rp,
                    expected_revenue=round(rp * 0.03, 4),
                    quit_risk=round(1.0 - rp, 2),
                    decision="show",
                    reason=f"fail_streak={fail_streak} accept_prob={rp:.0%}"))
        # interstitial
        ip = self._inter.predict(profile, segment, level_complete,
                                 level_fail, play_time_sec)
        if ip.decision in ("show", "defer"):
            opps.append(ip)
        return opps
