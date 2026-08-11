"""
E15.2.6 §6 — Traffic Allocator.

Decides how a proposed change is rolled out. For IAA waterfall changes MAX
cannot cleanly A/B-split traffic, so the default mode is a guarded 100% rollout
with continuous ARPDAU/Retention guardrails and a fixed 7-day measurement
window. A "split" mode is provided for future SDK-driven in-game A/B.
"""
from __future__ import annotations

from typing import Any, Dict

from operation.revenue_optimizer.models import OptimizationExperiment


class TrafficAllocator:
    DEFAULT_DURATION_DAYS = 7
    GUARDRAIL = "arpdau"

    def allocate(self, exp: OptimizationExperiment,
                 mode: str = "full") -> Dict[str, Any]:
        if mode == "split":
            # future: in-game SDK can split; MAX waterfall uses full rollout
            control = 0.5
            variant = 0.5
        else:  # full rollout with guardrail
            control = 0.0
            variant = 1.0
        return {
            "experiment_id": exp.exp_id,
            "mode": mode,
            "control_share": control,
            "variant_share": variant,
            "primary_metric": exp.expected_metric or "revenue_per_dau",
            "guardrail": self.GUARDRAIL,
            "duration_days": self.DEFAULT_DURATION_DAYS,
            "min_days": exp.min_days,
            "max_days": exp.max_days,
        }
