"""
E15.2.4 — Frequency Optimizer

Balances ad frequency against retention.
Increase frequency if revenue upside >> retention risk.
Block if retention risk >> revenue upside.
Uses Safety Layer integration for final gating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FrequencyChange:
    """Proposed ad frequency change."""
    game_id: str
    format: str
    current_interval_s: float
    proposed_interval_s: float
    current_frequency: str       # human-readable
    proposed_frequency: str
    revenue_impact_pct: float
    retention_risk_pct: float
    tradeoff_score: float        # positive = good trade-off
    recommendation: str          # "approve", "review", "block"
    reason: str


class FrequencyOptimizer:
    """Evaluates ad frequency adjustments against revenue/retention trade-off."""

    # Format-specific safe intervals (seconds)
    SAFE_INTERVALS = {
        "interstitial": 90,
        "rewarded": 45,
        "banner": 30,
        "app_open": 120,
    }

    # Absolute hard caps (from Safety Layer)
    HARD_CAPS = {
        "interstitial": 90,
        "rewarded": 30,
        "banner": 1,
        "app_open": 120,
    }

    # Trade-off scoring weights
    REVENUE_WEIGHT = 1.0
    RETENTION_WEIGHT = 2.0     # retention 2x more important

    def evaluate(
        self,
        game_id: str,
        format: str,
        current_interval_s: float,
        proposed_interval_s: float,
        current_metrics: Optional[Dict[str, Any]] = None,
    ) -> FrequencyChange:
        """Evaluate a proposed frequency change."""

        m = current_metrics or {}

        # Estimated impact
        interval_change_pct = (proposed_interval_s - current_interval_s) / current_interval_s
        # Decreasing interval = more ads = more revenue
        revenue_impact = -interval_change_pct * 0.4 * 100  # crude estimate
        # Decreasing interval = more ads = worse retention
        retention_risk = interval_change_pct * 0.6 * 100

        # Trade-off score: positive = net benefit
        tradeoff = (revenue_impact * self.REVENUE_WEIGHT +
                    retention_risk * self.RETENTION_WEIGHT)

        # Check hard caps
        hard_cap = self.HARD_CAPS.get(format)
        if hard_cap and proposed_interval_s < hard_cap:
            return FrequencyChange(
                game_id=game_id, format=format,
                current_interval_s=current_interval_s,
                proposed_interval_s=proposed_interval_s,
                current_frequency=f"1/{current_interval_s:.0f}s",
                proposed_frequency=f"1/{proposed_interval_s:.0f}s",
                revenue_impact_pct=round(revenue_impact, 1),
                retention_risk_pct=round(retention_risk, 1),
                tradeoff_score=round(tradeoff, 1),
                recommendation="block",
                reason=f"{format} interval {proposed_interval_s:.0f}s below hard cap {hard_cap}s",
            )

        # Decision
        if tradeoff > 3:
            recommendation = "approve"
            reason = f"Net benefit: revenue +{revenue_impact:.0f}%, retention risk {retention_risk:.0f}%"
        elif tradeoff > -3:
            recommendation = "review"
            reason = f"Marginal: revenue +{revenue_impact:.0f}%, retention risk {retention_risk:.0f}%"
        else:
            recommendation = "block"
            reason = f"Net negative: retention risk {abs(retention_risk):.0f}% outweighs revenue +{revenue_impact:.0f}%"

        return FrequencyChange(
            game_id=game_id, format=format,
            current_interval_s=current_interval_s,
            proposed_interval_s=proposed_interval_s,
            current_frequency=f"1/{current_interval_s:.0f}s",
            proposed_frequency=f"1/{proposed_interval_s:.0f}s",
            revenue_impact_pct=round(revenue_impact, 1),
            retention_risk_pct=round(retention_risk, 1),
            tradeoff_score=round(tradeoff, 1),
            recommendation=recommendation,
            reason=reason,
        )

    def suggest_optimization(
        self, game_id: str, format: str, current_interval_s: float
    ) -> Optional[FrequencyChange]:
        """Auto-suggest a safe frequency increase if room exists."""
        safe = self.SAFE_INTERVALS.get(format)
        if not safe:
            return None

        # If we're above the safe interval, room to increase (decrease interval)
        if current_interval_s > safe:
            proposed = max(safe, current_interval_s * 0.85)
            return self.evaluate(game_id, format, current_interval_s, proposed)

        return None

    def to_operation(self, change: FrequencyChange) -> Dict[str, Any]:
        return {
            "operation": "change_frequency_cap",
            "provider": "max",
            "game_id": change.game_id,
            "ad_format": change.format,
            "current_interval_s": change.current_interval_s,
            "proposed_interval_s": change.proposed_interval_s,
            "recommendation": change.recommendation,
        }


__all__ = ["FrequencyOptimizer", "FrequencyChange"]
