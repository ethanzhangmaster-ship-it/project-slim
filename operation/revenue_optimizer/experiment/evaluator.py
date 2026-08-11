"""
E15.2.6 §9 — Experiment Evaluator (Impact Measurement).

Runs the proven diff-in-diff measurement (ImpactMeasurer) and verdict
(WinnerSelector) and maps the result into the autopilot's ExperimentResult:
  WINNER  -> winner=True,  decision="WINNER"   (keep)
  ROLLBACK-> winner=False, decision="LOSER"   (rollback)
  other   -> winner=False, decision="UNKNOWN" (continue observing)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from operation.optimizer.experiments.impact import ImpactMeasurer
from operation.optimizer.experiments.winner_selector import WinnerSelector
from operation.revenue_optimizer.models import (
    ExperimentResult, OptimizationExperiment,
)


class ExperimentEvaluator:
    def __init__(self) -> None:
        self._measurer = ImpactMeasurer()
        self._selector = WinnerSelector()

    def evaluate(self, rows: List[Dict[str, Any]],
                 exp: OptimizationExperiment,
                 applied_at: Optional[str],
                 guardrail: str = "pending") -> ExperimentResult:
        m = self._measurer.measure(rows, exp.exp_id, exp.target, applied_at or "")
        d = self._selector.decide(m, guardrail)
        if d.verdict == "WINNER":
            decision, winner = "WINNER", True
        elif d.verdict == "ROLLBACK":
            decision, winner = "LOSER", False
        else:
            decision, winner = "UNKNOWN", False
        return ExperimentResult(
            exp_id=exp.exp_id, target=exp.target, winner=winner,
            lift=d.net_impact_pct, confidence=d.confidence,
            decision=decision, note=d.note)
