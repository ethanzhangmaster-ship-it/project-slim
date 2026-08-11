"""
E13.4.2 — Module 1: Experiment Models
======================================

Data contracts for the **Monetization Experiment Engine** — the layer that
turns a Strategy Candidate into *structured evidence* (A/B/n tests) instead of
a single guess. Where E13.3.2 picks ONE candidate and E13.4.1 remembers what
happened, E13.4.2 deliberately *manufactures* comparable samples so the future
E13.4.3 model learns from cause→effect, not just from history.

    Strategy Candidate (E13.3.2)
            |
            |  build variants (baseline + treatments, swept magnitudes)
            v
    Experiment  -> Variant Allocation -> Simulated Traffic
            |
            |  E13.2.9 Simulator per variant (NO real ad platform)
            v
    ExperimentResult  (winner + lift + learning signal)
            |
            v
    Decision Memory   (E13.4.1 — one closed-loop sample per treatment arm)

Hard constraints (per E13.4.2 scope):
  * NO MAX API. NO LevelPlay API. NO RemoteConfig write. NO execution.
  * Uses the E13.2.9 Simulator as the *traffic simulator* — i.e. we simulate
    what each variant would have done to the monetisation metrics. This is the
    "simulated traffic" the PRD requires.
  * Lean: pure-Python dataclasses, no DB, no ML.

Why experiments > passive memory
--------------------------------
Passive memory records "what happened". An experiment records "which strategy
* caused * what result" by comparing arms on the *same* baseline under the
*same* traffic. That causal contrast is what makes future AI ranking honest.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

# Success metrics an experiment can optimise for (higher value = better for
# every one of these — revenue/arpdau/ad_arpdau/ecpm/retention all want up).
SUCCESS_METRICS = ("revenue", "arpdau", "ad_arpdau", "ecpm", "retention")

# A sane default baseline metric for a segment when none is supplied. Mirrors
# what a real E13.3.1 ad-segment fact would carry (the E13.2.9 simulator reads
# ecpm / fill_rate / impressions / dau).
DEFAULT_BASELINE: Dict[str, float] = {
    "ecpm": 12.0,          # $ per 1000 impressions
    "fill_rate": 0.85,
    "impressions": 50000,  # daily impressions for the whole segment
    "dau": 5000,
    "ads_per_dau": 6.0,
    "d1_retention_pct": 42.0,
}


# --------------------------------------------------------------------------- #
# Leaf models
# --------------------------------------------------------------------------- #
@dataclass
class Variant:
    """One arm of an experiment (baseline or a treatment)."""
    variant_id: str
    name: str                  # e.g. "A_baseline", "B_floor_36"
    is_baseline: bool
    strategy_type: str
    action_type: str           # E13.2.9 simulator action; "" for baseline
    params: dict               # E13.2.9 simulator params (empty for baseline)
    mutation: dict             # E13.3.2-style mutation (for memory traceability)
    allocation: float = 0.0    # traffic share [0,1]
    description: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VariantMetric:
    """Simulated measurement of one variant (the experiment's observed effect)."""
    variant_id: str
    name: str
    is_baseline: bool
    action_type: str
    lever: str
    # ---- deltas (predicted effect of the variant vs baseline) ----
    deltas: dict               # revenue/ecpm/fill/impressions/retention delta pct
    # ---- absolute projected metrics (ad-segment aware) ----
    projected: dict            # ecpm/fill_rate/impressions/revenue/arpdau/retention_pct
    confidence: float = 0.0
    retention_risk: str = "low"
    allocation: float = 0.0
    sample_size: int = 0       # users exposed to this arm
    impressions: int = 0       # impressions exposed to this arm
    notes: str = ""

    def metric_value(self, kind: str) -> float:
        """Extract the experiment's success-metric value for this variant."""
        p = self.projected
        if kind == "revenue":
            return float(p.get("revenue", 0.0))
        if kind in ("arpdau", "ad_arpdau"):
            return float(p.get("arpdau", 0.0))
        if kind == "ecpm":
            return float(p.get("ecpm", 0.0))
        if kind == "retention":
            return float(p.get("retention_pct", 0.0))
        raise ValueError(f"unknown success_metric: {kind}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Experiment:
    """A designed A/B/n test of a monetisation strategy on a segment."""
    id: str
    name: str
    hypothesis: str
    target_segment: dict
    success_metric: str
    opportunity_id: str = ""
    opportunity_type: str = ""
    status: str = "draft"          # draft | running | completed
    baseline_variant_id: str = ""
    variants: List[Variant] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "hypothesis": self.hypothesis,
            "target_segment": self.target_segment,
            "success_metric": self.success_metric,
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type,
            "status": self.status,
            "baseline_variant_id": self.baseline_variant_id,
            "variants": [v.to_dict() for v in self.variants],
            "created_at": self.created_at,
        }


@dataclass
class ExperimentResult:
    """Outcome of running an Experiment: winner, lift, learning signal."""
    experiment_id: str
    name: str
    opportunity_type: str
    target_segment: dict
    success_metric: str
    baseline_metric: dict
    per_variant: Dict[str, dict]          # variant_id -> VariantMetric.to_dict()
    baseline_variant_id: str
    winner_variant_id: str
    winner_strategy_type: str
    winner_name: str
    winner_metric_value: float
    baseline_metric_value: float
    lift_pct: float                        # winner vs baseline on success_metric
    conclusion: str
    learning_signal: dict
    variants_count: int
    status: str = "completed"

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "opportunity_type": self.opportunity_type,
            "target_segment": self.target_segment,
            "success_metric": self.success_metric,
            "baseline_metric": self.baseline_metric,
            "per_variant": self.per_variant,
            "baseline_variant_id": self.baseline_variant_id,
            "winner_variant_id": self.winner_variant_id,
            "winner_strategy_type": self.winner_strategy_type,
            "winner_name": self.winner_name,
            "winner_metric_value": round(self.winner_metric_value, 4),
            "baseline_metric_value": round(self.baseline_metric_value, 4),
            "lift_pct": round(self.lift_pct, 3),
            "conclusion": self.conclusion,
            "learning_signal": self.learning_signal,
            "variants_count": self.variants_count,
            "status": self.status,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def synthetic_baseline(segment: dict, **overrides) -> dict:
    """Build a plausible baseline metric dict for a segment.

    The E13.2.9 simulator reads ecpm / fill_rate / impressions / dau; we also
    keep d1_retention_pct (for retention experiments) and ads_per_dau.
    """
    base = dict(DEFAULT_BASELINE)
    base.update(overrides)
    return base


def new_id(prefix: str = "exp") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
