"""
E15.2.7 §6 — Ad fatigue detector.

When a player's reward-accept rate or overall ad engagement starts declining
over recent sessions, fatigue is setting in — reduce frequency.
"""
from __future__ import annotations

from typing import List


class FatigueDetector:
    FATIGUE_THRESHOLD = 0.15       # drop in accept rate → fatigue rising
    RECENT_SESSIONS = 3

    def detect(self, accept_rates: List[float]) -> float:
        """accept_rates: per-session reward accept rates, most recent last.
        Returns fatigue in 0..1 (0 = fresh, 1 = burned out)."""
        if len(accept_rates) < 3:
            return 0.0
        recent = accept_rates[-self.RECENT_SESSIONS:]
        first = recent[0]
        last = recent[-1]
        if first <= 0:
            return 1.0 if last <= 0 else 0.5
        drop = (first - last) / first
        if drop >= self.FATIGUE_THRESHOLD:
            return min(round(drop / 0.3, 2), 1.0)  # scale proportionally
        return 0.0
