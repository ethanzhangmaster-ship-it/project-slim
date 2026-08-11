"""
E13.4.1 — Module 3: Outcome Tracker
====================================

Closes the autonomous loop: given a DecisionRecord and a later *measured*
reality (ActualOutcome), it computes the `LearningSignal` (prediction error +
success flag) and writes it back into the store.

This is the "Learn" step of the E12 Autonomous Growth Loop, finally materialised
as data. No model is involved — just arithmetic contrasts between what the
simulator predicted and what the Reality Engine later measured.

A `synthesize_actual()` helper fabricates a plausible actual outcome from a
prediction for demos/tests (seeded, deterministic). In production this input
comes from a real later Reality Engine run over the same segment.
"""
from __future__ import annotations

import random
from typing import Optional

from monetization.learning.decision_store import DecisionStore
from monetization.learning.models import (
    ActualOutcome, DecisionRecord, LearningSignal, REV_FLOOR_PCT, RET_FLOOR_PCT,
)


def compute_learning_signal(record: DecisionRecord,
                            actual: ActualOutcome) -> LearningSignal:
    """Derive the contrast between prediction and reality for one record."""
    pred_rev = record.prediction_revenue_delta
    pred_ret = record.prediction_retention_delta

    err_rev = round(actual.revenue_delta_pct - pred_rev, 3)
    err_ret = round(actual.retention_delta_pct - pred_ret, 3)

    # success: must have actually executed AND produced a non-harmful outcome
    executed = record.execution_status == "executed"
    success = (
        executed
        and actual.revenue_delta_pct >= REV_FLOOR_PCT
        and actual.retention_delta_pct >= RET_FLOOR_PCT
    )
    slack = round(actual.revenue_delta_pct - REV_FLOOR_PCT, 3)

    return LearningSignal(
        prediction_error_revenue=err_rev,
        prediction_error_retention=err_ret,
        revenue_bias=err_rev,        # single-sample bias == error; aggregated later
        success=success,
        slack=slack,
    )


def record_actual(store: DecisionStore, decision_id: str,
                  actual: ActualOutcome) -> Optional[DecisionRecord]:
    """Attach a measured outcome to a stored decision, compute its signal,
    and persist. Returns the updated record (or None if id unknown)."""
    rec = store.get(decision_id)
    if rec is None:
        return None
    rec.actual = actual
    rec.learning_signal = compute_learning_signal(rec, actual)
    rec.closed_loop = True
    store.update(rec)
    return rec


def synthesize_actual(record: DecisionRecord, realization: float = 0.8,
                      noise: float = 2.0, seed: Optional[int] = None,
                      sample_size: int = 5000) -> ActualOutcome:
    """Fabricate a plausible actual outcome from a prediction.

    `realization` in [0,1+]: fraction of the predicted revenue lift that
    'actually' showed up (e.g. 0.8 => reality delivered 80% of the forecast).
    `noise`: +/- random pct added to revenue & retention. Deterministic when
    `seed` is set (tests / reproducible demos).

    Used ONLY for demos/tests. Production feeds real measurements here.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    pred_rev = record.prediction_revenue_delta
    pred_ret = record.prediction_retention_delta

    actual_rev = round(pred_rev * realization + rng.uniform(-noise, noise), 3)
    # retention realisation tends to be closer to prediction (less variance)
    actual_ret = round(pred_ret * (realization * 0.5 + 0.5) + rng.uniform(-noise * 0.3, noise * 0.3), 3)

    return ActualOutcome(
        revenue_delta_pct=actual_rev,
        retention_delta_pct=actual_ret,
        sample_size=sample_size,
        source="synthetic_demo",
    )
