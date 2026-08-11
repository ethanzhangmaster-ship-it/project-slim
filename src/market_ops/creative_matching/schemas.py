"""E9.6: Creative → Archetype Matching Engine — Data Models.

Predicts which player archetype a creative DNA will attract,
and the expected LTV / D30 / payer_rate.

Core types:
  - DNAFeatureVector: encoded numeric features from Creative DNA
  - ArchetypeAffinity: rule-based affinity score per archetype
  - ArchetypePrediction: predicted probability + expected metrics
  - CreativePrediction: full prediction for one creative
  - CreativeArchetypeRank: ranking entry for sorting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════
# DNA Feature Vector
# ═══════════════════════════════════════════════════════════

@dataclass
class DNAFeatureVector:
    """Encoded numeric features extracted from Creative DNA.

    Each feature is 0-1 normalized, representing how strongly
    the creative DNA expresses that dimension.
    """
    creative_id: str = ""
    creative_genome_name: str = ""

    # Core attraction dimensions
    collection_strength: float = 0.0     # How strongly this appeals to collectors
    progression_strength: float = 0.0    # How strongly this appeals to progressors
    power_expression: float = 0.0        # How strongly this signals power/strength
    exploration_strength: float = 0.0    # How strongly this appeals to explorers

    # Creative quality signals
    emotion_intensity: float = 0.0       # Emotional hook strength
    reward_value: float = 0.0            # Reward attractiveness
    novelty_score: float = 0.0           # How novel/unique the creative is
    urgency_signal: float = 0.0          # Time pressure / scarcity cues

    # IAP signals
    payment_affinity: float = 0.0        # How likely to trigger payment
    retention_hook_strength: float = 0.0  # How well it hooks for retention

    # Source DNA fields (for traceability)
    fantasy_drives: list[str] = field(default_factory=list)
    mechanism_type: str = ""
    hook_type: str = ""
    reward_type: str = ""
    visual_style: str = ""
    payment_triggers: list[str] = field(default_factory=list)
    retention_hooks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_genome_name": self.creative_genome_name,
            "features": {
                "collection_strength": round(self.collection_strength, 3),
                "progression_strength": round(self.progression_strength, 3),
                "power_expression": round(self.power_expression, 3),
                "exploration_strength": round(self.exploration_strength, 3),
                "emotion_intensity": round(self.emotion_intensity, 3),
                "reward_value": round(self.reward_value, 3),
                "novelty_score": round(self.novelty_score, 3),
                "urgency_signal": round(self.urgency_signal, 3),
                "payment_affinity": round(self.payment_affinity, 3),
                "retention_hook_strength": round(self.retention_hook_strength, 3),
            },
            "source_dna": {
                "fantasy": self.fantasy_drives,
                "mechanism": self.mechanism_type,
                "hook": self.hook_type,
                "reward": self.reward_type,
                "visual": self.visual_style,
                "payment_triggers": self.payment_triggers,
                "retention_hooks": self.retention_hooks,
            },
        }


# ═══════════════════════════════════════════════════════════
# Archetype Affinity
# ═══════════════════════════════════════════════════════════

@dataclass
class ArchetypeAffinity:
    """Rule-based affinity between Creative DNA and an archetype."""
    archetype: str = ""
    raw_affinity: float = 0.0           # Raw rule-based score
    historical_prior: float = 0.0       # Global prior probability
    adjusted_probability: float = 0.0   # Bayesian-adjusted probability
    confidence: float = 0.0             # How confident we are in this prediction

    # Expected metrics if this archetype is attracted
    expected_ltv: float = 0.0
    expected_payer_rate: float = 0.0
    expected_retention: float = 0.0

    # Contributing factors (for explainability)
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype,
            "raw_affinity": round(self.raw_affinity, 3),
            "historical_prior": round(self.historical_prior, 3),
            "adjusted_probability": round(self.adjusted_probability, 3),
            "confidence": round(self.confidence, 3),
            "expected_metrics": {
                "ltv": round(self.expected_ltv, 2),
                "payer_rate": round(self.expected_payer_rate, 3),
                "retention": round(self.expected_retention, 3),
            },
            "factors": self.factors,
        }


# ═══════════════════════════════════════════════════════════
# Creative Prediction
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativePrediction:
    """Full prediction for one creative DNA."""
    creative_id: str = ""
    creative_genome_name: str = ""

    # Per-archetype predictions
    archetypes: dict[str, ArchetypeAffinity] = field(default_factory=dict)

    # Aggregate expected metrics
    expected_d30_retention: float = 0.0
    expected_payer_rate: float = 0.0
    expected_ltv: float = 0.0
    expected_iap_potential: float = 0.0   # Composite IAP score

    # Top archetype
    primary_archetype: str = ""
    primary_confidence: float = 0.0

    # DNA features
    dna_features: DNAFeatureVector | None = None

    def compute_aggregates(self) -> None:
        """Compute aggregate metrics from per-archetype predictions."""
        if not self.archetypes:
            return

        total_prob = sum(a.adjusted_probability for a in self.archetypes.values())
        if total_prob == 0:
            return

        self.expected_ltv = sum(
            a.adjusted_probability * a.expected_ltv
            for a in self.archetypes.values()
        ) / total_prob
        self.expected_payer_rate = sum(
            a.adjusted_probability * a.expected_payer_rate
            for a in self.archetypes.values()
        ) / total_prob
        self.expected_d30_retention = sum(
            a.adjusted_probability * a.expected_retention
            for a in self.archetypes.values()
        ) / total_prob

        # IAP potential = payer_rate × LTV scaled
        ltv_scaled = min(self.expected_ltv / 50.0, 1.0)
        self.expected_iap_potential = round(
            self.expected_payer_rate * 0.5 + ltv_scaled * 0.5, 3
        )

        # Primary archetype
        best = max(self.archetypes.values(), key=lambda a: a.adjusted_probability)
        self.primary_archetype = best.archetype
        self.primary_confidence = best.adjusted_probability

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_genome_name": self.creative_genome_name,
            "primary_archetype": self.primary_archetype,
            "primary_confidence": round(self.primary_confidence, 3),
            "prediction": {
                arch: a.to_dict()
                for arch, a in sorted(
                    self.archetypes.items(),
                    key=lambda x: -x[1].adjusted_probability,
                )
            },
            "expected": {
                "d30_retention": round(self.expected_d30_retention, 3),
                "payer_rate": round(self.expected_payer_rate, 3),
                "ltv": round(self.expected_ltv, 2),
                "iap_potential": round(self.expected_iap_potential, 3),
            },
            "dna_features": self.dna_features.to_dict() if self.dna_features else {},
        }


# ═══════════════════════════════════════════════════════════
# Creative Archetype Rank Entry
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeArchetypeRank:
    """Ranking entry for sorting creatives by archetype affinity."""
    creative_id: str = ""
    creative_genome_name: str = ""
    target_archetype: str = ""
    probability: float = 0.0
    expected_ltv: float = 0.0
    expected_payer_rate: float = 0.0
    expected_retention: float = 0.0
    iap_potential: float = 0.0
    rank_score: float = 0.0  # Composite ranking score

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_genome_name": self.creative_genome_name,
            "target_archetype": self.target_archetype,
            "probability": round(self.probability, 3),
            "expected_ltv": round(self.expected_ltv, 2),
            "expected_payer_rate": round(self.expected_payer_rate, 3),
            "expected_retention": round(self.expected_retention, 3),
            "iap_potential": round(self.iap_potential, 3),
            "rank_score": round(self.rank_score, 4),
        }