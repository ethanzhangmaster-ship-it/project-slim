"""
E15.2.4 — Bid Floor Optimizer

Adjusts MAX bid floors based on eCPM vs fill rate trade-offs.
Guard rails prevent over-aggressive floor changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FloorChange:
    """Proposed bid floor adjustment."""
    game_id: str
    format: str
    country: str
    old_floor: float
    new_floor: float
    change_pct: float
    reason: str
    expected_impact: Dict[str, Any] = field(default_factory=dict)


class BidFloorOptimizer:
    """Adjusts bid floors with safety guard rails."""

    # Floor change limits
    MAX_FLOOR_INCREASE_PCT = 20.0    # max +20% per adjustment
    MAX_FLOOR_DECREASE_PCT = 15.0    # max -15% per adjustment
    MIN_FLOOR = 0.50                 # absolute minimum floor
    MAX_FLOOR = 50.0                 # absolute maximum floor

    # Trigger rules
    ECPM_ABOVE_FLOOR_RATIO = 1.5     # raise if eCPM > floor * 1.5
    FILL_DROP_THRESHOLD = 0.80       # lower if fill < 80%
    CONSECUTIVE_DAYS = 7             # need this many days of signal

    def analyze(
        self,
        game_id: str,
        format: str,
        country: str,
        current_floor: float,
        ecpm_recent: float,
        fill_rate_recent: float,
        ecpm_trend: Optional[List[float]] = None,
    ) -> Optional[FloorChange]:
        """Determine if floor should be raised or lowered."""

        # Rule 1: Raise floor if eCPM consistently above floor
        if current_floor > 0 and ecpm_recent > current_floor * self.ECPM_ABOVE_FLOOR_RATIO:
            if ecpm_trend and len(ecpm_trend) >= self.CONSECUTIVE_DAYS:
                above = all(e > current_floor * self.ECPM_ABOVE_FLOOR_RATIO
                           for e in ecpm_trend[-self.CONSECUTIVE_DAYS:])
                if not above:
                    return None

            suggested_floor = current_floor * 1.10  # +10%
            increase = min(suggested_floor - current_floor,
                          current_floor * self.MAX_FLOOR_INCREASE_PCT / 100)
            new_floor = min(current_floor + increase, self.MAX_FLOOR)
            new_floor = round(new_floor, 2)

            if new_floor == current_floor:
                return None

            return FloorChange(
                game_id=game_id, format=format, country=country,
                old_floor=current_floor, new_floor=new_floor,
                change_pct=round((new_floor - current_floor) / current_floor * 100, 1),
                reason=f"eCPM {ecpm_recent} significantly above floor {current_floor}",
                expected_impact={
                    "revenue_change_pct": 5.0,
                    "ecpm_change_pct": 3.0,
                    "fill_risk": "low",
                },
            )

        # Rule 2: Lower floor if fill rate is dropping
        if fill_rate_recent < self.FILL_DROP_THRESHOLD:
            decrease = min(current_floor * self.MAX_FLOOR_DECREASE_PCT / 100,
                          current_floor - self.MIN_FLOOR)
            new_floor = max(current_floor - decrease, self.MIN_FLOOR)
            new_floor = round(new_floor, 2)

            if new_floor == current_floor:
                return None

            return FloorChange(
                game_id=game_id, format=format, country=country,
                old_floor=current_floor, new_floor=new_floor,
                change_pct=round((new_floor - current_floor) / current_floor * 100, 1),
                reason=f"Fill rate {fill_rate_recent:.0%} below {self.FILL_DROP_THRESHOLD:.0%} threshold",
                expected_impact={
                    "revenue_change_pct": -3.0,
                    "fill_change_pct": 10.0,
                },
            )

        return None

    def to_operation(self, change: FloorChange) -> Dict[str, Any]:
        """Convert FloorChange to executable monetization operation."""
        return {
            "operation": "raise_bid_floor" if change.new_floor > change.old_floor else "lower_bid_floor",
            "provider": "max",
            "game_id": change.game_id,
            "format": change.format,
            "country": change.country,
            "old_floor": change.old_floor,
            "new_floor": change.new_floor,
            "change_pct": change.change_pct,
            "reason": change.reason,
        }


__all__ = ["BidFloorOptimizer", "FloorChange"]
