"""E9.8: Creative Mutation Engine — Data Models.

Core types for the Evolution Layer:
  - CreativeGenome: a complete creative DNA blueprint
  - MutationRecord: a single mutation operation
  - MutationCandidate: a generated genome with prediction
  - WinnerPattern: aggregated winner DNA patterns
  - FailurePattern: identified failure DNA patterns
  - MutationStrategy: mutation type + parameters
  - EvolutionReport: full evolution cycle summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════
# Creative Genome
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeGenome:
    """A complete creative DNA blueprint for generation."""
    genome_id: str = ""
    generation: int = 0  # evolution generation number

    # Core DNA
    hook: str = ""
    mechanism: str = ""
    reward: str = ""
    fantasy: str = ""
    visual_style: str = ""

    # Target
    target_archetype: str = ""
    target_ltv: float = 0.0

    # Source
    parent_genome_id: str = ""
    mutation_type: str = ""  # "hook_change", "reward_change", etc.

    # Metadata
    created_at: str = ""
    mutation_round: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "generation": self.generation,
            "hook": self.hook,
            "mechanism": self.mechanism,
            "reward": self.reward,
            "fantasy": self.fantasy,
            "visual_style": self.visual_style,
            "target_archetype": self.target_archetype,
            "target_ltv": round(self.target_ltv, 1),
            "parent_genome_id": self.parent_genome_id,
            "mutation_type": self.mutation_type,
            "created_at": self.created_at,
            "mutation_round": self.mutation_round,
        }


# ═══════════════════════════════════════════════════════════
# Winner Pattern
# ═══════════════════════════════════════════════════════════

@dataclass
class WinnerPattern:
    """Aggregated winner DNA patterns."""
    # Most common values
    top_hooks: list[dict[str, Any]] = field(default_factory=list)
    top_rewards: list[dict[str, Any]] = field(default_factory=list)
    top_visuals: list[dict[str, Any]] = field(default_factory=list)
    top_fantasies: list[dict[str, Any]] = field(default_factory=list)
    top_mechanisms: list[dict[str, Any]] = field(default_factory=list)

    # Archetype affinity
    archetype_affinity: dict[str, float] = field(default_factory=dict)

    # Performance
    avg_ltv: float = 0.0
    avg_payer_rate: float = 0.0
    avg_retention: float = 0.0

    # Sample size
    winner_count: int = 0
    total_analyzed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "top_hooks": self.top_hooks,
            "top_rewards": self.top_rewards,
            "top_visuals": self.top_visuals,
            "top_fantasies": self.top_fantasies,
            "top_mechanisms": self.top_mechanisms,
            "archetype_affinity": {
                k: round(v, 3) for k, v in self.archetype_affinity.items()
            },
            "avg_ltv": round(self.avg_ltv, 1),
            "avg_payer_rate": round(self.avg_payer_rate, 3),
            "avg_retention": round(self.avg_retention, 3),
            "winner_count": self.winner_count,
            "total_analyzed": self.total_analyzed,
        }


# ═══════════════════════════════════════════════════════════
# Failure Pattern
# ═══════════════════════════════════════════════════════════

@dataclass
class FailurePattern:
    """A single identified failure pattern."""
    feature: str = ""       # e.g. "weak_reward", "low_clarity"
    dimension: str = ""      # e.g. "hook", "reward", "visual"
    value: str = ""          # e.g. "unknown", "empty"
    impact: float = 0.0      # negative impact on LTV
    frequency: int = 0       # how often this pattern appears in losers
    loser_avg_ltv: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "dimension": self.dimension,
            "value": self.value,
            "impact": round(self.impact, 3),
            "frequency": self.frequency,
            "loser_avg_ltv": round(self.loser_avg_ltv, 1),
        }


@dataclass
class FailureAnalysis:
    """Complete failure pattern analysis."""
    patterns: list[FailurePattern] = field(default_factory=list)
    loser_count: int = 0
    total_analyzed: int = 0
    avg_loser_ltv: float = 0.0

    # What to avoid
    avoid_hooks: list[str] = field(default_factory=list)
    avoid_rewards: list[str] = field(default_factory=list)
    avoid_visuals: list[str] = field(default_factory=list)
    avoid_fantasies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patterns": [p.to_dict() for p in self.patterns],
            "loser_count": self.loser_count,
            "total_analyzed": self.total_analyzed,
            "avg_loser_ltv": round(self.avg_loser_ltv, 1),
            "avoid_hooks": self.avoid_hooks,
            "avoid_rewards": self.avoid_rewards,
            "avoid_visuals": self.avoid_visuals,
            "avoid_fantasies": self.avoid_fantasies,
        }


# ═══════════════════════════════════════════════════════════
# Mutation Record
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationRecord:
    """A single mutation operation applied to a parent genome."""
    parent_genome_id: str = ""
    mutation_type: str = ""   # "hook", "reward", "visual", "fantasy", "archetype"
    dimension: str = ""       # The dimension being mutated
    before: str = ""          # Original value
    after: str = ""           # New value
    strategy: str = ""        # "winner_emulation", "failure_avoidance", "exploration"
    confidence: float = 0.0   # How confident we are in this mutation

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_genome_id": self.parent_genome_id,
            "mutation_type": self.mutation_type,
            "dimension": self.dimension,
            "before": self.before,
            "after": self.after,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 3),
        }


# ═══════════════════════════════════════════════════════════
# Mutation Candidate (Genome + Prediction)
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationCandidate:
    """A generated genome with E9.6 prediction results."""
    genome: CreativeGenome = field(default_factory=CreativeGenome)
    mutations: list[MutationRecord] = field(default_factory=list)

    # Predicted archetype distribution
    predicted_archetypes: dict[str, float] = field(default_factory=dict)

    # Predicted metrics
    predicted_ltv: float = 0.0
    predicted_payer_rate: float = 0.0
    predicted_d30: float = 0.0

    # Scores
    dna_alignment_score: float = 0.0       # How well DNA matches winner patterns
    novelty_score: float = 0.0             # How different from existing creatives
    opportunity_score: float = 0.0         # Market opportunity alignment
    composite_score: float = 0.0           # Final ranking score

    # Risk
    risk_level: str = "medium"  # "low", "medium", "high"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome": self.genome.to_dict(),
            "mutations": [m.to_dict() for m in self.mutations],
            "predicted_archetypes": {
                k: round(v, 3) for k, v in self.predicted_archetypes.items()
            },
            "predicted_ltv": round(self.predicted_ltv, 1),
            "predicted_payer_rate": round(self.predicted_payer_rate, 3),
            "predicted_d30": round(self.predicted_d30, 3),
            "dna_alignment_score": round(self.dna_alignment_score, 3),
            "novelty_score": round(self.novelty_score, 3),
            "opportunity_score": round(self.opportunity_score, 3),
            "composite_score": round(self.composite_score, 3),
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 3),
        }


# ═══════════════════════════════════════════════════════════
# Mutation Strategy
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationStrategy:
    """A mutation strategy definition."""
    strategy_type: str = ""       # "winner_emulation", "failure_avoidance", "exploration"
    dimension: str = ""           # "hook", "reward", "visual", "fantasy", "archetype"
    from_value: str = ""          # Source value
    to_values: list[str] = field(default_factory=list)  # Target values
    weight: float = 0.0           # Strategy weight for selection
    reason: str = ""              # Why this strategy is applied

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "dimension": self.dimension,
            "from_value": self.from_value,
            "to_values": self.to_values,
            "weight": round(self.weight, 3),
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════════════
# Evolution Report
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionReport:
    """Full evolution cycle summary."""
    report_time: str = ""
    evolution_round: int = 0

    # Inputs
    winner_count: int = 0
    loser_count: int = 0
    total_dna_analyzed: int = 0

    # Winner patterns
    winner_pattern: WinnerPattern | None = None

    # Failure patterns
    failure_analysis: FailureAnalysis | None = None

    # Mutation stats
    total_strategies: int = 0
    total_candidates: int = 0
    mutations_by_type: dict[str, int] = field(default_factory=dict)
    mutations_by_dimension: dict[str, int] = field(default_factory=dict)

    # Top candidates
    top_candidates: list[MutationCandidate] = field(default_factory=list)

    # Summary
    avg_predicted_ltv: float = 0.0
    avg_confidence: float = 0.0
    archetype_coverage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_time": self.report_time,
            "evolution_round": self.evolution_round,
            "inputs": {
                "winner_count": self.winner_count,
                "loser_count": self.loser_count,
                "total_dna_analyzed": self.total_dna_analyzed,
            },
            "winner_pattern": self.winner_pattern.to_dict() if self.winner_pattern else {},
            "failure_analysis": self.failure_analysis.to_dict() if self.failure_analysis else {},
            "mutation_stats": {
                "total_strategies": self.total_strategies,
                "total_candidates": self.total_candidates,
                "by_type": self.mutations_by_type,
                "by_dimension": self.mutations_by_dimension,
            },
            "top_candidates": [c.to_dict() for c in self.top_candidates[:20]],
            "summary": {
                "avg_predicted_ltv": round(self.avg_predicted_ltv, 1),
                "avg_confidence": round(self.avg_confidence, 3),
                "archetype_coverage": self.archetype_coverage,
            },
        }


# ═══════════════════════════════════════════════════════════
# Market Opportunity (for opportunity_detector)
# ═══════════════════════════════════════════════════════════

@dataclass
class MarketOpportunity:
    """A detected market gap / opportunity."""
    opportunity_id: str = ""
    description: str = ""
    dimension: str = ""          # Which DNA dimension to explore
    target_value: str = ""       # Suggested DNA value
    target_archetype: str = ""   # Which archetype this targets
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "description": self.description,
            "dimension": self.dimension,
            "target_value": self.target_value,
            "target_archetype": self.target_archetype,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
        }