"""
E15.2.6 §10 — Optimization Memory.

Re-exports the proven OptimizationMemory (append-only JSONL of measured
outcomes) and adds a convenience to record an experiment verdict. New games /
geos showing the same (action, target) structure can then reference proven
priors via `query` / `prior_note`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from operation.optimizer.experiments.optimization_memory import OptimizationMemory


def record_outcome(memory: OptimizationMemory, *,
                   account: str, action: str, target: str,
                   net_impact_pct: Optional[float],
                   guardrail: str, decision: str, confidence: float,
                   applied_at: Optional[str] = None,
                   app: str = "", geo: str = "",
                   ad_format: str = "") -> Dict[str, Any]:
    return memory.record(
        account=account, action=action, target=target,
        net_impact_pct=net_impact_pct, guardrail=guardrail,
        decision=decision, confidence=confidence, applied_at=applied_at,
        app=app, geo=geo, ad_format=ad_format)


__all__ = ["OptimizationMemory", "record_outcome"]
