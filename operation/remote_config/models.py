"""
E15.2.8 §5 — Remote Config data models.

Defines the run-time tunable parameters the AI Optimization Agent can change
without touching game code. Every parameter has a key, a type, and a default
so the SDK always has a safe fallback even if the config server is down.

reward / interstitial / segment configs are the primary levers for
the Player Monetization Agent (E15.2.7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RewardConfig:
    placement: str = "revive"
    enabled: bool = True
    cooldown_sec: int = 300
    multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "cooldown": self.cooldown_sec,
                "multiplier": self.multiplier}


@dataclass
class InterstitialConfig:
    enabled: bool = True
    min_interval_sec: int = 120
    after_level: bool = True
    max_daily: int = 10
    after_fail: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "min_interval": self.min_interval_sec,
                "after_level": self.after_level, "max_daily": self.max_daily,
                "after_fail": self.after_fail}


@dataclass
class SegmentOverride:
    segment: str = ""
    reward_multiplier: float = 1.0
    interstitial_frequency: float = 1.0  # 1.0=normal, 0.5=half as many
    cooldown_multiplier: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {"reward_multiplier": self.reward_multiplier,
                "interstitial_frequency": self.interstitial_frequency,
                "cooldown_multiplier": self.cooldown_multiplier}


@dataclass
class RemoteConfig:
    """Top-level config for one game — exactly what the SDK fetches."""
    game_id: str = ""
    version: str = "1.0"

    reward: Dict[str, RewardConfig] = field(default_factory=dict)
    interstitial: InterstitialConfig = field(default_factory=InterstitialConfig)
    segments: Dict[str, SegmentOverride] = field(default_factory=dict)

    experiment_id: Optional[str] = None
    variant: str = "control"           # control | variant

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flat key-value dict suitable for the Unity GFRemoteConfig parser."""
        d: Dict[str, Any] = {}
        for name, rc in self.reward.items():
            d[f"reward.{name}.enabled"] = rc.enabled
            d[f"reward.{name}.cooldown"] = rc.cooldown_sec
            d[f"reward.{name}.multiplier"] = rc.multiplier
        d["interstitial.enabled"] = self.interstitial.enabled
        d["interstitial.min_interval"] = self.interstitial.min_interval_sec
        d["interstitial.after_level"] = self.interstitial.after_level
        d["interstitial.max_daily"] = self.interstitial.max_daily
        d["interstitial.after_fail"] = self.interstitial.after_fail
        for seg, so in self.segments.items():
            d[f"segment.{seg}.reward_multiplier"] = so.reward_multiplier
            d[f"segment.{seg}.interstitial_frequency"] = so.interstitial_frequency
            d[f"segment.{seg}.cooldown_multiplier"] = so.cooldown_multiplier
        if self.experiment_id:
            d["_experiment_id"] = self.experiment_id
            d["_variant"] = self.variant
        return d

    @classmethod
    def default_for(cls, game_id: str) -> "RemoteConfig":
        return cls(
            game_id=game_id,
            reward={
                "revive": RewardConfig("revive", True, 300, 1.0),
                "daily_bonus": RewardConfig("daily_bonus", True, 600, 1.0),
            },
            interstitial=InterstitialConfig(),
            segments={
                "high_value": SegmentOverride("high_value", 1.5, 1.0, 0.8),
                "at_risk": SegmentOverride("at_risk", 0.5, 0.3, 2.0),
            },
        )
