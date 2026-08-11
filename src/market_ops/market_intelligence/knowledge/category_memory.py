"""E6.1: Category Memory — tracks category evolution over time.

Remembers: how fast categories grow, when they peak, what mechanics dominate,
and what signals preceded breakout success.

This enables "category timing" — knowing when to enter a market.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class CategoryMemory:
    """Time-series memory of category evolution.

    Tracks: lifecycle transitions, timing patterns, leading indicators.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, list[dict[str, Any]]] = {}  # category → timeline
        self._transitions: dict[str, list[dict[str, Any]]] = {}  # category → transition log
        # Learning: what signals preceded breakout?
        self._breakout_patterns: list[dict[str, Any]] = []

    def record_snapshot(self, category: str, heat: float, growth: float,
                        competition: float, signals: list[str]) -> None:
        """Record a point-in-time snapshot of a category."""
        snap = {
            "timestamp": datetime.now().isoformat(),
            "heat": heat, "growth": growth,
            "competition": competition, "signals": signals,
        }
        self._snapshots.setdefault(category, []).append(snap)

        # Detect transition
        if len(self._snapshots[category]) >= 2:
            prev = self._snapshots[category][-2]
            self._detect_transition(category, prev, snap)

    def _detect_transition(self, category: str, prev: dict, curr: dict) -> None:
        """Detect lifecycle transitions."""
        growth_change = curr["growth"] - prev["growth"]
        if abs(growth_change) < 10:
            return

        transition = {
            "category": category,
            "timestamp": curr["timestamp"],
            "growth_change": round(growth_change, 1),
            "from_stage": self._classify_lifecycle(prev["growth"], prev["competition"]),
            "to_stage": self._classify_lifecycle(curr["growth"], curr["competition"]),
            "triggers": curr["signals"],
        }

        self._transitions.setdefault(category, []).append(transition)

        # If breakout: learn the pattern
        if transition["from_stage"] in ("stable", "emerging") and \
           transition["to_stage"] in ("growing", "exploding"):
            self._breakout_patterns.append({
                "category": category,
                "growth_spike": transition["growth_change"],
                "leading_indicators": transition["triggers"],
                "pre_breakout_growth": prev["growth"],
            })

    def get_timing_insight(self, category: str) -> dict[str, Any]:
        """When is the best time to enter this category?"""
        snapshots = self._snapshots.get(category, [])
        transitions = self._transitions.get(category, [])

        if not snapshots:
            return {"timing": "unknown", "confidence": 0.0}

        current = snapshots[-1]
        stage = self._classify_lifecycle(current["growth"], current["competition"])

        timing_advice = {
            "emerging": "Enter now — first-mover advantage",
            "growing": "Enter with differentiation",
            "mature": "Niche entry only",
            "declining": "Avoid",
        }

        patterns = [p for p in self._breakout_patterns if p["category"] == category]
        confidence = min(0.9, 0.3 + len(patterns) * 0.1 + len(transitions) * 0.05)

        return {
            "category": category,
            "current_stage": stage,
            "timing_recommendation": timing_advice.get(stage, "monitor"),
            "confidence": round(confidence, 2),
            "breakout_precedents": len(patterns),
        }

    @staticmethod
    def _classify_lifecycle(growth: float, competition: float) -> str:
        if growth > 100 and competition < 50:
            return "emerging"
        if growth > 50:
            return "growing"
        if growth > 10:
            return "mature"
        return "declining"
