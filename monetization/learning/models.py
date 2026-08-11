"""
E13.4.1 — Module 1: Decision Memory Models
===========================================

Data contracts for the **Decision Memory Layer** — the long-term memory of the
E13.3 Autonomous Monetization Loop. Each record captures ONE full decision
lifecycle so future AI Strategy Ranking (E13.4.3) has real training data:

    Decision  (E13.3.2 StrategyDecision)
        |
        |  Simulation Prediction   (E13.2.9 StrategyPrediction)
        v
    Approval   (E13.3.3 Approval Gate verdict)
        |
        |  Execution Result       (E13.3.3 ExecutionResult)
        v
    Actual Monetization Outcome  (a later Reality Engine measurement)
        |
        v
    Learning Signal             (prediction error + success)

Hard constraints (per E13.4.1 scope):
  * NO AI model. NO machine-learning library. NO DB.
  * Pure-Python dataclasses + JSON/File store (Lean).
  * This layer only *remembers*; it never decides, simulates, or executes.

The `DecisionRecord.from_pipeline()` builder fuses the three upstream outputs
(Opportunity + StrategyDecision + ExecutionResult) into a single row. The
`actual` / `learning_signal` fields stay None until the OutcomeTracker closes
the loop (records the measured reality).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
# Success thresholds (conservative, tunable). A decision is a "success" only if
# it was actually executed AND produced a non-harmful outcome.
REV_FLOOR_PCT = 0.0        # actual revenue delta must be >= this to count success
RET_FLOOR_PCT = -1.0       # actual retention delta must be >= this (small loss tolerated)


# --------------------------------------------------------------------------- #
# Leaf models
# --------------------------------------------------------------------------- #
@dataclass
class ActualOutcome:
    """The measured reality after a decision had time to act.

    In production this is produced by a LATER Reality Engine run (E13.3.1)
    over the same segment — i.e. the feedback loop closing. For E13.4.1 we
    accept it as an explicit input (synthetic in tests).
    """
    revenue_delta_pct: float = 0.0
    retention_delta_pct: float = 0.0
    sample_size: int = 0           # users/days the measurement covers
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "reality_engine"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearningSignal:
    """Derived contrast between prediction and reality for one decision."""
    prediction_error_revenue: float    # actual - predicted (revenue delta pct)
    prediction_error_retention: float  # actual - predicted (retention delta pct)
    revenue_bias: float                # mean signed error (systematic optimism/pessimism)
    success: bool                      # executed AND non-harmful outcome
    slack: float                       # margin over the revenue floor (actual - REV_FLOOR)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Master record
# --------------------------------------------------------------------------- #
@dataclass
class DecisionRecord:
    """One complete decision lifecycle, stored as a row of long-term memory.

    `actual` / `learning_signal` are None until the loop closes.
    `closed_loop` is True once an actual outcome has been recorded.
    """
    decision_id: str
    opportunity_id: str
    opportunity_type: str
    segment: dict                      # {country, platform, ad_format, network}
    strategy_type: str
    strategy_score: float
    strategy_mutation: dict
    # ---- simulation prediction (flattened from E13.2.9) ----
    prediction: dict = field(default_factory=dict)
    prediction_confidence: float = 0.0
    prediction_revenue_delta: float = 0.0
    prediction_retention_delta: float = 0.0
    # ---- approval + execution (from E13.3.3) ----
    gate_verdict: str = ""             # approved | manual_review | rejected
    execution_status: str = ""         # executed | rolled_back | pending | rejected | failed
    execution_changes: int = 0
    # ---- reality (filled later) ----
    actual: Optional[ActualOutcome] = None
    learning_signal: Optional[LearningSignal] = None
    closed_loop: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        d = asdict(self)
        d["actual"] = self.actual.to_dict() if self.actual else None
        d["learning_signal"] = self.learning_signal.to_dict() if self.learning_signal else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionRecord":
        rec = cls(
            decision_id=d["decision_id"],
            opportunity_id=d.get("opportunity_id", ""),
            opportunity_type=d.get("opportunity_type", ""),
            segment=d.get("segment", {}) or {},
            strategy_type=d.get("strategy_type", ""),
            strategy_score=float(d.get("strategy_score", 0.0)),
            strategy_mutation=d.get("strategy_mutation", {}) or {},
            prediction=d.get("prediction", {}) or {},
            prediction_confidence=float(d.get("prediction_confidence", 0.0)),
            prediction_revenue_delta=float(d.get("prediction_revenue_delta", 0.0)),
            prediction_retention_delta=float(d.get("prediction_retention_delta", 0.0)),
            gate_verdict=d.get("gate_verdict", ""),
            execution_status=d.get("execution_status", ""),
            execution_changes=int(d.get("execution_changes", 0)),
            closed_loop=bool(d.get("closed_loop", False)),
            created_at=d.get("created_at", ""),
        )
        if d.get("actual"):
            a = d["actual"]
            rec.actual = ActualOutcome(
                revenue_delta_pct=float(a.get("revenue_delta_pct", 0.0)),
                retention_delta_pct=float(a.get("retention_delta_pct", 0.0)),
                sample_size=int(a.get("sample_size", 0)),
                measured_at=a.get("measured_at", ""),
                source=a.get("source", "reality_engine"),
            )
        if d.get("learning_signal"):
            s = d["learning_signal"]
            rec.learning_signal = LearningSignal(
                prediction_error_revenue=float(s.get("prediction_error_revenue", 0.0)),
                prediction_error_retention=float(s.get("prediction_error_retention", 0.0)),
                revenue_bias=float(s.get("revenue_bias", 0.0)),
                success=bool(s.get("success", False)),
                slack=float(s.get("slack", 0.0)),
            )
        return rec

    # ------------------------------------------------------------------ #
    @classmethod
    def from_pipeline(cls, opportunity: dict, decision: dict,
                      execution: Optional[dict] = None) -> "DecisionRecord":
        """Fuse an E13.3.1 Opportunity + E13.3.2 StrategyDecision + E13.3.3
        ExecutionResult into one memory row.

        Missing upstream fields are tolerated (e.g. a decision that was never
        executed has no execution result yet -> loop still open).
        """
        opp = opportunity or {}
        dec = decision or {}
        strat = dec.get("strategy", {}) or {}
        pred_wrap = strat.get("prediction", {}) or {}
        pred = pred_wrap.get("prediction", {}) or {}

        seg = opp.get("segment", {}) or {}
        # StrategyDecision.strategy does not carry the raw segment; recover a
        # coarse one from the prediction target string for memory grouping.
        if not seg and pred_wrap.get("target"):
            parts = [p for p in pred_wrap["target"].split("_") if p]
            if len(parts) >= 1:
                seg = {"country": parts[0]}
            if len(parts) >= 2:
                seg["platform"] = parts[1]
            if len(parts) >= 3:
                seg["ad_format"] = parts[2]
            if len(parts) >= 4:
                seg["network"] = parts[3]

        exec_status = ""
        gate_verdict = ""
        exec_changes = 0
        if execution:
            exec_status = execution.get("status", "")
            gate_verdict = execution.get("gate_verdict", "")
            exec_changes = len(execution.get("changes", []) or [])

        return cls(
            decision_id=dec.get("opportunity_id", "") or dec.get("decision_id", "") or new_id(),
            opportunity_id=opp.get("id", "") or dec.get("opportunity_id", ""),
            opportunity_type=opp.get("type", "") or dec.get("opportunity_type", ""),
            segment=seg,
            strategy_type=strat.get("type", ""),
            strategy_score=float(strat.get("score", 0.0)),
            strategy_mutation=strat.get("mutation", {}) or {},
            prediction=pred_wrap,
            prediction_confidence=float(pred.get("confidence", 0.0)),
            prediction_revenue_delta=float(pred.get("revenue_delta_pct", 0.0)),
            prediction_retention_delta=float(pred.get("retention_delta_pct", 0.0)),
            gate_verdict=gate_verdict,
            execution_status=exec_status,
            execution_changes=exec_changes,
        )


def new_id(prefix: str = "dec") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
