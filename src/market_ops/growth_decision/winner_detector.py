"""E9.9.5 Module 1: Winner Detector.

Converts E9.9 experiment results into 4-level growth decisions.

Classification logic:
  WINNER:       lift >= 10%, confidence >= 95%, sample sufficient
  PROMISING:    lift > 0, confidence >= 80%, not yet winner
  FAILED:       lift < 0, confidence >= 80%, sample sufficient
  INCONCLUSIVE: insufficient data / confidence

Output: GrowthDecision with SCALE / WATCH / KILL / RETEST action.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, GrowthAction, WinnerLevel,
)

# ── Thresholds ─────────────────────────────────────────────

WINNER_LIFT_THRESHOLD = 0.10
WINNER_CONFIDENCE_THRESHOLD = 0.95
PROMISING_CONFIDENCE_THRESHOLD = 0.80
MIN_SAMPLE_SIZE = 50


class WinnerDetector:
    """Classifies E9.9 experiment results into 4 winner levels.

    Usage:
        detector = WinnerDetector()
        decisions = detector.detect("output/experiment_intelligence/experiment_results.json")
    """

    def __init__(self) -> None:
        pass

    def detect(
        self,
        results_path: str | Path,
    ) -> list[GrowthDecision]:
        """Load E9.9 results and classify each experiment.

        Args:
            results_path: Path to experiment_results.json (E9.9 output)

        Returns:
            List of GrowthDecision objects (one per experiment)
        """
        raw = self._load_results(results_path)
        decisions = []

        for entry in raw:
            decision = self._classify(entry)
            decisions.append(decision)

        return decisions

    def detect_from_dicts(
        self, results: list[dict[str, Any]]
    ) -> list[GrowthDecision]:
        """Classify pre-loaded experiment results.

        Args:
            results: List of experiment result dicts

        Returns:
            List of GrowthDecision objects
        """
        return [self._classify(r) for r in results]

    # ── Load ───────────────────────────────────────────────

    def _load_results(self, path: str | Path) -> list[dict[str, Any]]:
        """Load E9.9 experiment_results.json."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("results", []) if isinstance(data, dict) else data

    # ── Classification ─────────────────────────────────────

    def _classify(self, result: dict[str, Any]) -> GrowthDecision:
        """Classify a single experiment result into a GrowthDecision.

        Decision tree:
          WINNER:       lift>=0.10, confidence>=0.95, sample>=required
          PROMISING:    lift>0, confidence>=0.80, not winner
          FAILED:       lift<0, confidence>=0.80, sample>=50
          INCONCLUSIVE: everything else
        """
        lift = result.get("lift", 0.0)
        confidence = result.get("confidence", 0.0)
        sample_achieved = result.get("sample_size_achieved", 0)
        sample_required = result.get("sample_size_required", 0)

        winner_level = self._determine_level(
            lift, confidence, sample_achieved, sample_required
        )
        action = self._level_to_action(winner_level)

        return GrowthDecision(
            decision_id=f"GD_{uuid.uuid4().hex[:8]}",
            experiment_id=result.get("experiment_id", ""),
            creative_id=result.get("control_creative_id", ""),
            decision=action,
            winner_level=winner_level,
            reason=self._build_reason(winner_level, lift, confidence, sample_achieved),
            confidence=confidence,
            budget_before=result.get("spend", 0.0),
            budget_after=0.0,  # filled by ScaleEngine later
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _determine_level(
        self,
        lift: float,
        confidence: float,
        sample_achieved: int,
        sample_required: int,
    ) -> str:
        """Determine winner level from experiment metrics."""
        sample_sufficient = (
            sample_achieved >= sample_required
            and sample_achieved >= MIN_SAMPLE_SIZE
        )

        # WINNER: strong positive signal + sufficient data
        if (
            lift >= WINNER_LIFT_THRESHOLD
            and confidence >= WINNER_CONFIDENCE_THRESHOLD
            and sample_sufficient
        ):
            return WinnerLevel.WINNER.value

        # PROMISING: positive lift with decent confidence, not yet winner
        if lift > 0 and confidence >= PROMISING_CONFIDENCE_THRESHOLD:
            return WinnerLevel.PROMISING.value

        # FAILED: negative lift with sufficient confidence and data
        min_sample_for_fail = max(sample_achieved, 0) >= MIN_SAMPLE_SIZE
        if lift < 0 and confidence >= PROMISING_CONFIDENCE_THRESHOLD and min_sample_for_fail:
            return WinnerLevel.FAILED.value

        # INCONCLUSIVE: everything else
        return WinnerLevel.INCONCLUSIVE.value

    def _level_to_action(self, level: str) -> str:
        """Map winner level to growth action."""
        mapping = {
            WinnerLevel.WINNER.value: GrowthAction.SCALE.value,
            WinnerLevel.PROMISING.value: GrowthAction.WATCH.value,
            WinnerLevel.FAILED.value: GrowthAction.KILL.value,
            WinnerLevel.INCONCLUSIVE.value: GrowthAction.RETEST.value,
        }
        return mapping.get(level, GrowthAction.WATCH.value)

    def _build_reason(
        self,
        level: str,
        lift: float,
        confidence: float,
        sample_achieved: int,
    ) -> str:
        """Build human-readable reason string."""
        if level == WinnerLevel.WINNER.value:
            return (
                f"Strong winner: lift={lift:.1%}, confidence={confidence:.0%}, "
                f"n={sample_achieved}"
            )
        elif level == WinnerLevel.PROMISING.value:
            return (
                f"Promising: lift={lift:.1%}, confidence={confidence:.0%}, "
                f"need more data (n={sample_achieved})"
            )
        elif level == WinnerLevel.FAILED.value:
            return (
                f"Failed: lift={lift:.1%}, confidence={confidence:.0%}, "
                f"n={sample_achieved}"
            )
        else:
            return (
                f"Inconclusive: lift={lift:.1%}, confidence={confidence:.0%}, "
                f"insufficient evidence (n={sample_achieved})"
            )

    # ── Summary ────────────────────────────────────────────

    def get_detection_summary(
        self, decisions: list[GrowthDecision]
    ) -> dict[str, Any]:
        """Get summary of winner detection results."""
        by_level: dict[str, int] = {}
        by_action: dict[str, int] = {}

        for d in decisions:
            by_level[d.winner_level] = by_level.get(d.winner_level, 0) + 1
            by_action[d.decision] = by_action.get(d.decision, 0) + 1

        total = len(decisions)
        return {
            "total_experiments": total,
            "by_level": by_level,
            "by_action": by_action,
            "scale_rate": round(by_action.get("SCALE", 0) / max(1, total), 3),
            "kill_rate": round(by_action.get("KILL", 0) / max(1, total), 3),
            "avg_confidence": round(
                sum(d.confidence for d in decisions) / max(1, total), 3
            ),
        }