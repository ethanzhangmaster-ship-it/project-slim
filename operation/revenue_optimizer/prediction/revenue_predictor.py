"""
E15.2.6 §5 — Revenue Predictor (entry point).

Composes LiftModel (absolute revenue impact) with ConfidenceEstimator
(how much to trust it). This is the module the autopilot calls right before
planning an experiment and before the Safety Gate.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from operation.revenue_optimizer.models import (
    PredictionResult, RevenueOpportunity,
)
from operation.revenue_optimizer.prediction.confidence import ConfidenceEstimator
from operation.revenue_optimizer.prediction.lift_model import LiftModel


class RevenuePredictor:
    def __init__(self) -> None:
        self._lift = LiftModel()
        self._conf = ConfidenceEstimator()

    def predict(self, opp: RevenueOpportunity,
                 ctx: Dict[str, Any],
                 memory=None) -> PredictionResult:
        pred = self._lift.predict(opp, ctx)
        pred.confidence = self._conf.estimate(opp, ctx, memory)
        pred.note = (pred.note + " | " if pred.note else "") \
            + f"confidence from estimator"
        return pred
