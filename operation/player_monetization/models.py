"""
E15.2.7 — Player Monetization Intelligence data models.

Pure-Python dataclasses for player events, profiles, segments, predictions,
ad opportunities, frequency rules, and learning records.

Deterministic. No numpy/pandas. No LLM. No external calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlayerEvent:
    """Spec §1 — user-level session event (from Unity SDK)."""
    user_id: str
    country: str = ""
    level: int = 0
    session_count: int = 0
    play_time_sec: int = 0
    timestamp: str = ""


@dataclass
class AdEvent:
    """Spec §1 — single ad impression event."""
    user_id: str
    ad_type: str = ""       # reward | interstitial | banner
    request: bool = False
    show: bool = False
    complete: bool = False
    revenue: float = 0.0
    timestamp: str = ""


@dataclass
class GameEvent:
    """Spec §1 — gameplay progression event."""
    user_id: str
    level_start: int = 0
    level_fail: int = 0
    level_complete: bool = False
    fail_streak: int = 0
    timestamp: str = ""


@dataclass
class PlayerProfile:
    """Aggregated player state — the features layer for all downstream models."""
    user_id: str
    country: str = ""
    level: int = 0
    session_count: int = 0
    total_play_time_sec: int = 0
    total_ad_requests: int = 0
    total_ad_shows: int = 0
    total_ad_completions: int = 0
    total_ad_revenue: float = 0.0
    reward_accept_rate: float = 0.0
    avg_session_sec: float = 0.0
    fail_rate: float = 0.0
    days_active: int = 0
    active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id, "country": self.country,
            "level": self.level, "session_count": self.session_count,
            "total_play_time_sec": self.total_play_time_sec,
            "total_ad_requests": self.total_ad_requests,
            "total_ad_shows": self.total_ad_shows,
            "total_ad_revenue": round(self.total_ad_revenue, 4),
            "reward_accept_rate": round(self.reward_accept_rate, 4),
            "avg_session_sec": round(self.avg_session_sec, 1),
            "fail_rate": round(self.fail_rate, 4),
            "days_active": self.days_active, "active": self.active,
        }


@dataclass
class PlayerSegment:
    """Spec §2 — user segment + value tier."""
    user_id: str
    segment: str = "new_player"
    # high_value_ad_player | casual_player | at_risk_churn | new_player
    # power_user | moderate_ad_player
    value_score: float = 0.0    # 0..100
    churn_risk: float = 0.0     # 0..1
    ad_tolerance: str = "medium"  # high | medium | low
    confidence: float = 0.0


@dataclass
class ValuePrediction:
    """Spec §2 — predicted IAA value for this player."""
    user_id: str
    segment: str = ""
    predicted_30d_iaa: float = 0.0
    predicted_ltv: float = 0.0
    confidence: float = 0.0
    features: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id, "segment": self.segment,
            "predicted_30d_IAA": round(self.predicted_30d_iaa, 2),
            "predicted_LTV": round(self.predicted_ltv, 2),
            "confidence": round(self.confidence, 2),
            "features": self.features,
        }


@dataclass
class AdOpportunity:
    """Spec §3/4/5 — should we show an ad to this user right now?"""
    user_id: str
    opportunity_type: str = ""  # reward | interstitial
    ad_probability: float = 0.0   # 0..1 — quality of this moment for an ad
    expected_revenue: float = 0.0
    quit_risk: float = 0.0        # 0..1
    decision: str = "skip"        # show | skip | defer
    reason: str = ""


@dataclass
class FrequencyRule:
    """Spec §6 — per-user, per-ad-type frequency cap."""
    user_id: str
    ad_type: str = ""
    max_per_session: int = 3
    cooldown_sec: int = 180
    max_per_day: int = 10
    fatigue_level: float = 0.0  # 0..1
    last_shown_at: str = ""


@dataclass
class PlayerLearningRecord:
    """Spec §10 — what worked for this player segment."""
    user_id: str
    segment: str = ""
    action: str = ""
    ad_type: str = ""
    arpdau_before: float = 0.0
    arpdau_after: float = 0.0
    retention_before: float = 0.0
    retention_after: float = 0.0
    decision: str = ""       # positive | negative | neutral
    confidence: float = 0.0
    recorded_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id, "segment": self.segment,
            "action": self.action, "ad_type": self.ad_type,
            "arpdau_before": self.arpdau_before,
            "arpdau_after": self.arpdau_after,
            "retention_before": self.retention_before,
            "retention_after": self.retention_after,
            "decision": self.decision,
            "confidence": round(self.confidence, 2),
            "recorded_at": self.recorded_at,
        }
