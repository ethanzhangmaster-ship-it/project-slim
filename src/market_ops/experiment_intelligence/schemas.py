"""E9.9: Experiment Intelligence Layer — Data Models.

Core types for the Experiment Intelligence Layer:
  - ExperimentCandidate: E9.8 mutation selected for experiment
  - ExperimentPlan: full experiment design (hypothesis, control, variant, budget)
  - ExperimentResult: experiment outcome (lift, p-value, decision)
  - FeedbackSignal: learning signal to E9.7
  - PerformanceSnapshot: UA platform performance data at a point in time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class ExperimentStatus(str, Enum):
    """Experiment lifecycle states."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WINNER = "WINNER"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class BudgetMode(str, Enum):
    """Budget allocation strategy."""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    BANDIT = "bandit"


class ExperimentDecision(str, Enum):
    """Final decision for an experiment."""
    WINNER = "WINNER"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


# ═══════════════════════════════════════════════════════════
# Experiment Candidate
# ═══════════════════════════════════════════════════════════

@dataclass
class ExperimentCandidate:
    """Selected from E9.8 top_mutations for experiment.

    Acts as an adapter/bridge between E9.8 MutationCandidate
    and E9.9 ExperimentPlan. Does NOT modify E9.8 schema.
    """
    id: str = ""                     # generated UUID
    creative_id: str = ""            # parent_genome_id from E9.8
    genome_id: str = ""              # genome_id from E9.8
    hook: str = ""
    reward: str = ""
    visual_style: str = ""
    fantasy: str = ""
    predicted_ltv: float = 0.0
    predicted_archetype: str = ""    # top-1 from predicted_archetypes dict
    mutation_score: float = 0.0      # composite_score from E9.8
    mutation_type: str = ""
    before: str = ""
    after: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "hook": self.hook,
            "reward": self.reward,
            "visual_style": self.visual_style,
            "fantasy": self.fantasy,
            "predicted_ltv": round(self.predicted_ltv, 1),
            "predicted_archetype": self.predicted_archetype,
            "mutation_score": round(self.mutation_score, 3),
            "mutation_type": self.mutation_type,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_e98_mutation(cls, mutation: dict[str, Any]) -> ExperimentCandidate:
        """Adapt E9.8 top_mutations entry to ExperimentCandidate."""
        genome = mutation.get("genome", {})
        mutations = mutation.get("mutations", [{}])
        first_mutation = mutations[0] if mutations else {}

        # Resolve predicted_archetype: dict → top-1 string
        archetypes = mutation.get("predicted_archetypes", {})
        predicted_archetype = ""
        if archetypes:
            predicted_archetype = max(archetypes, key=archetypes.get)

        return cls(
            id=genome.get("genome_id", ""),
            creative_id=genome.get("parent_genome_id", ""),
            genome_id=genome.get("genome_id", ""),
            hook=genome.get("hook", ""),
            reward=genome.get("reward", ""),
            visual_style=genome.get("visual_style", ""),
            fantasy=genome.get("fantasy", ""),
            predicted_ltv=mutation.get("predicted_ltv", 0.0),
            predicted_archetype=predicted_archetype,
            mutation_score=mutation.get("composite_score", 0.0),
            mutation_type=first_mutation.get("mutation_type", ""),
            before=first_mutation.get("before", ""),
            after=first_mutation.get("after", ""),
        )


# ═══════════════════════════════════════════════════════════
# Experiment Plan
# ═══════════════════════════════════════════════════════════

@dataclass
class ExperimentPlan:
    """Full experiment design.

    Answers: why test? what to test? how to test? how much? how long?
    """
    experiment_id: str = ""
    mutation_id: str = ""            # genome_id from ExperimentCandidate

    # Hypothesis
    hypothesis: str = ""             # "Changing X from A to B will improve Y by Z%"

    # Control vs Variant
    control: str = ""                # Original creative_id
    variant: dict[str, Any] = field(default_factory=dict)
    # variant = {genome_id, hook, reward, visual_style, fantasy}

    # Metrics
    metrics: list[str] = field(default_factory=list)
    # e.g., ["CTR", "CPI", "D7_ROAS", "D30_LTV"]

    # Budget
    budget: float = 0.0              # Total experiment budget
    daily_budget: float = 0.0

    # Duration
    duration_days: int = 7

    # Statistical parameters
    confidence_level: float = 0.95
    statistical_power: float = 0.80
    sample_size_required: int = 0

    # Status
    status: str = "CREATED"          # ExperimentStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "mutation_id": self.mutation_id,
            "hypothesis": self.hypothesis,
            "control": self.control,
            "variant": self.variant,
            "metrics": self.metrics,
            "budget": round(self.budget, 2),
            "daily_budget": round(self.daily_budget, 2),
            "duration_days": self.duration_days,
            "confidence_level": self.confidence_level,
            "statistical_power": self.statistical_power,
            "sample_size_required": self.sample_size_required,
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════
# Experiment Result
# ═══════════════════════════════════════════════════════════

@dataclass
class ExperimentResult:
    """Final experiment outcome — what actually happened."""
    experiment_id: str = ""
    control_creative_id: str = ""
    variant_genome_id: str = ""

    # Performance metrics
    spend: float = 0.0
    installs: int = 0
    ctr: float = 0.0
    cpi: float = 0.0
    roas: float = 0.0
    d7_retention: float = 0.0

    # Statistical results
    lift: float = 0.0                # (variant - control) / control
    p_value: float = 1.0
    confidence: float = 0.0

    # Decision
    decision: str = "INCONCLUSIVE"   # ExperimentDecision

    # Sample size
    sample_size_required: int = 0
    sample_size_achieved: int = 0

    # Metadata
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "control_creative_id": self.control_creative_id,
            "variant_genome_id": self.variant_genome_id,
            "spend": round(self.spend, 2),
            "installs": self.installs,
            "ctr": round(self.ctr, 4),
            "cpi": round(self.cpi, 2),
            "roas": round(self.roas, 3),
            "d7_retention": round(self.d7_retention, 3),
            "lift": round(self.lift, 4),
            "p_value": round(self.p_value, 4),
            "confidence": round(self.confidence, 3),
            "decision": self.decision,
            "sample_size_required": self.sample_size_required,
            "sample_size_achieved": self.sample_size_achieved,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════
# Feedback Signal
# ═══════════════════════════════════════════════════════════

@dataclass
class FeedbackSignal:
    """Learning signal from experiment → E9.7 Learning Loop.

    Does NOT modify E9.7 source code. Writes to JSON files
    that E9.7 reads on its next run.
    """
    creative_id: str = ""
    experiment_id: str = ""

    # DNA weight updates
    dna_weight_update: dict[str, float] = field(default_factory=dict)
    # e.g., {"hook.challenge": 0.06, "reward.discovery": -0.03}

    # Mutation strategy updates
    mutation_strategy_update: dict[str, str] = field(default_factory=dict)
    # e.g., {"hook": "increase", "reward": "maintain"}

    # Prediction weight updates
    prediction_weight_update: dict[str, float] = field(default_factory=dict)
    # e.g., {"ltv_weight": 1.05, "retention_weight": 0.98}

    # Metadata
    confidence: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "experiment_id": self.experiment_id,
            "dna_weight_update": {
                k: round(v, 4) for k, v in self.dna_weight_update.items()
            },
            "mutation_strategy_update": self.mutation_strategy_update,
            "prediction_weight_update": {
                k: round(v, 4) for k, v in self.prediction_weight_update.items()
            },
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════
# Performance Snapshot
# ═══════════════════════════════════════════════════════════

@dataclass
class PerformanceSnapshot:
    """UA platform performance data at a point in time.

    Shared schema for both real UA data (E10) and mock data (E9.9 v1.0).
    """
    creative_id: str = ""
    timestamp: str = ""
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    revenue: float = 0.0
    ctr: float = 0.0
    cpi: float = 0.0
    roas: float = 0.0
    d7_retention: float = 0.0
    d30_ltv: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "timestamp": self.timestamp,
            "spend": round(self.spend, 2),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "revenue": round(self.revenue, 2),
            "ctr": round(self.ctr, 4),
            "cpi": round(self.cpi, 2),
            "roas": round(self.roas, 3),
            "d7_retention": round(self.d7_retention, 3),
            "d30_ltv": round(self.d30_ltv, 1),
        }