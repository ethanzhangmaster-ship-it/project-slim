"""
E13.4.3 — Module 0: Intelligence Data Models
=============================================

Pure-Python dataclasses describing the *judgement* objects produced by the
Strategy Intelligence Layer. No ML, no DB.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class StrategyFeature:
    """Model feature vector for ranking one (opportunity, strategy) pair.

    Carries the context (segment + current monetisation metrics) plus the
    learned signals (Bayesian prior, experiment evidence, rule priors) so the
    ranker / lightweight model can score the pair consistently.
    """
    opportunity_id: str
    opportunity_type: str
    segment: dict
    strategy_type: str
    # ---- context ----
    issue_type: str = ""
    current_ecpm: float = 0.0
    current_fill: float = 0.0
    current_retention: float = 0.0
    # ---- history prior (Bayesian Beta) ----
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    prior_mean: float = 0.5
    prior_samples: int = 0
    history_success_rate: Dict[str, float] = field(default_factory=dict)
    # ---- experiment evidence (causal) ----
    exp_observed_lift: Optional[float] = None
    exp_retention_impact: Optional[float] = None
    exp_samples: int = 0
    # ---- rule prior ----
    rule_expected_effect: str = ""
    rule_confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StrategyProbability:
    """Output row: a strategy scored for one opportunity.

    `probability` is the final fused score in [0,1] — the value the acceptance
    criterion asks for ("Top3 Strategy Probability").
    """
    strategy_type: str
    action_type: str
    simulation_score: float
    safety_score: float
    confidence: float
    historical_prior: float
    experiment_evidence: float
    final_score: float
    probability: float
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IntelligenceResult:
    """Full ranking output for one opportunity."""
    opportunity_id: str
    opportunity_type: str
    target_segment: dict
    ranked: List[dict]                 # StrategyProbability.to_dict()
    top: Optional[dict] = None
    weights: dict = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CalibrationFactor:
    """A learned Simulator correction factor for one (strategy, parameter) key."""
    key: str
    strategy_type: str
    action_type: str
    parameter: str
    correction: float
    samples: int
    sum_predicted: float = 0.0
    sum_actual: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
