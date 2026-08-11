"""V4.3 Exploration Manager — controls exploit vs explore ratio.

Default: Exploit 80% / Explore 20%

Auto-adjusts based on:
  - Market change detection
  - Trend shifts
  - Failure rate
  - Time since last exploration

If market is changing rapidly → increase explore to 40%.
If market is stable → decrease explore to 10%.
"""

from __future__ import annotations

from typing import Any

from .schemas import ExploreMode


class ExplorationManager:
    """Dynamic exploration ratio controller."""

    def __init__(self, explore_ratio: float = 0.20) -> None:
        self._explore_ratio: float = explore_ratio
        self._exploit_ratio: float = 1.0 - explore_ratio
        self._mode: ExploreMode = ExploreMode.BALANCED
        self._history: list[dict[str, Any]] = []
        self._market_change_score: float = 0.0  # 0=stable, 1=chaotic

    def get_ratio(self) -> tuple[float, float]:
        """Get current exploit/explore ratio."""
        return self._exploit_ratio, self._explore_ratio

    def adjust(self, market_change_score: float,
               failure_rate: float = 0.0,
               days_since_explore: int = 0) -> ExploreMode:
        """Adjust exploration ratio based on signals.

        Args:
            market_change_score: 0 (stable) to 1 (rapidly changing).
            failure_rate: Current prediction failure rate.
            days_since_explore: Days since last exploration round.

        Returns:
            Current ExploreMode.
        """
        self._market_change_score = market_change_score

        # Base explore ratio from market change
        if market_change_score > 0.6:
            target_explore = 0.40
            self._mode = ExploreMode.EXPLORE
        elif market_change_score > 0.3:
            target_explore = 0.25
            self._mode = ExploreMode.BALANCED
        else:
            target_explore = 0.10
            self._mode = ExploreMode.EXPLOIT

        # Adjust for failure rate
        if failure_rate > 0.3:
            # High failure → explore more (current strategy not working)
            target_explore = min(0.45, target_explore + 0.10)

        # Adjust for exploration drought
        if days_since_explore > 7:
            target_explore = min(0.45, target_explore + 0.05)

        # Smooth transition
        self._explore_ratio = self._explore_ratio * 0.7 + target_explore * 0.3
        self._exploit_ratio = 1.0 - self._explore_ratio

        self._history.append({
            "explore_ratio": self._explore_ratio,
            "exploit_ratio": self._exploit_ratio,
            "mode": self._mode.value,
            "market_change_score": market_change_score,
        })

        return self._mode

    def set_fixed_ratio(self, explore_ratio: float) -> None:
        """Set a fixed exploration ratio."""
        self._explore_ratio = max(0.05, min(0.45, explore_ratio))
        self._exploit_ratio = 1.0 - self._explore_ratio
        self._mode = ExploreMode.BALANCED

    @property
    def explore_ratio(self) -> float:
        return self._explore_ratio

    @property
    def exploit_ratio(self) -> float:
        return self._exploit_ratio

    @property
    def mode(self) -> ExploreMode:
        return self._mode

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)