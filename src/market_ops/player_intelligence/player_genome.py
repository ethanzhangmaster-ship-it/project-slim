"""E9.5: Player Genome — archetype + value segment + payment profile.

Extends E9.4 PlayerDNA with player classification and value segmentation.

5 Archetypes:
  Collector   — high collection, rare items, completion
  Progression — fast leveling, area unlock, merge depth
  Power       — high level, rare items, upgrades
  Explorer    — area discovery, events, story
  Casual      — low engagement, random pattern (baseline)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class PlayerArchetype(Enum):
    COLLECTOR = "collector"
    PROGRESSION = "progression"
    POWER = "power"
    EXPLORER = "explorer"
    CASUAL = "casual"

    def display_name(self) -> str:
        names = {
            PlayerArchetype.COLLECTOR: "收藏型玩家",
            PlayerArchetype.PROGRESSION: "成长推进型",
            PlayerArchetype.POWER: "成长强度型",
            PlayerArchetype.EXPLORER: "探索型",
            PlayerArchetype.CASUAL: "休闲型",
        }
        return names.get(self, self.value)


class ValueSegment(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ═══════════════════════════════════════════════════════════
# Behavior Features
# ═══════════════════════════════════════════════════════════

@dataclass
class BehaviorFeatures:
    """Normalized behavior features (0-1 scale) extracted from PlayerDNA."""
    # Progression
    merge_velocity: float = 0.0      # Merges per day relative to benchmark
    merge_depth: float = 0.0         # Max merge level relative to global max
    level_growth_rate: float = 0.0   # Levels per day
    area_unlock_speed: float = 0.0   # Areas unlocked per day

    # Collection
    collection_rate: float = 0.0     # Items collected per day
    rare_item_ratio: float = 0.0     # Rare items / total items
    completion_bias: float = 0.0     # Collections completed tendency
    missing_item_pressure: float = 0.0  # Missing item events frequency

    # Monetization
    purchase_intent: float = 0.0     # Purchase probability
    purchase_frequency: float = 0.0  # Purchases per week
    offer_conversion: float = 0.0    # Offer views → purchases
    spending_level: float = 0.0      # Total spend compared to benchmark

    # Engagement
    session_frequency: float = 0.0   # Sessions per day
    daily_return: float = 0.0        # Days active / lifetime
    event_participation: float = 0.0 # Event join rate
    retention_strength: float = 0.0  # D7+D30 composite

    # Archetype scores (computed)
    collector_score: float = 0.0
    progression_score: float = 0.0
    power_score: float = 0.0
    explorer_score: float = 0.0
    casual_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "progression": {
                "merge_velocity": round(self.merge_velocity, 3),
                "merge_depth": round(self.merge_depth, 3),
                "level_growth_rate": round(self.level_growth_rate, 3),
                "area_unlock_speed": round(self.area_unlock_speed, 3),
            },
            "collection": {
                "collection_rate": round(self.collection_rate, 3),
                "rare_item_ratio": round(self.rare_item_ratio, 3),
                "completion_bias": round(self.completion_bias, 3),
                "missing_item_pressure": round(self.missing_item_pressure, 3),
            },
            "monetization": {
                "purchase_intent": round(self.purchase_intent, 3),
                "purchase_frequency": round(self.purchase_frequency, 3),
                "offer_conversion": round(self.offer_conversion, 3),
                "spending_level": round(self.spending_level, 3),
            },
            "engagement": {
                "session_frequency": round(self.session_frequency, 3),
                "daily_return": round(self.daily_return, 3),
                "event_participation": round(self.event_participation, 3),
                "retention_strength": round(self.retention_strength, 3),
            },
            "archetype_scores": {
                "collector": round(self.collector_score, 3),
                "progression": round(self.progression_score, 3),
                "power": round(self.power_score, 3),
                "explorer": round(self.explorer_score, 3),
                "casual": round(self.casual_score, 3),
            },
        }


# ═══════════════════════════════════════════════════════════
# Payment Profile
# ═══════════════════════════════════════════════════════════

@dataclass
class PaymentProfile:
    """Payment behavior profile derived from triggers and patterns."""
    is_payer: bool = False
    trigger_type: str = "none"  # blocked_progress | missing_item | time_gate | exclusive_item | energy
    purchase_probability: float = 0.0
    avg_order_value: float = 0.0
    predicted_ltv_d30: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_payer": self.is_payer,
            "trigger_type": self.trigger_type,
            "purchase_probability": round(self.purchase_probability, 3),
            "avg_order_value": round(self.avg_order_value, 2),
            "predicted_ltv_d30": round(self.predicted_ltv_d30, 2),
        }


# ═══════════════════════════════════════════════════════════
# Player Genome
# ═══════════════════════════════════════════════════════════

@dataclass
class PlayerGenome:
    """Complete player identity: archetype + value + behavior + payment."""
    player_id: str
    creative_id: str

    # Classification
    archetype: PlayerArchetype = PlayerArchetype.CASUAL
    archetype_confidence: float = 0.0
    secondary_archetype: PlayerArchetype | None = None

    # Value
    value_segment: ValueSegment = ValueSegment.LOW

    # Scores
    features: BehaviorFeatures = field(default_factory=BehaviorFeatures)
    payment_profile: PaymentProfile = field(default_factory=PaymentProfile)

    # Explanation
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "creative_id": self.creative_id,
            "archetype": self.archetype.value,
            "archetype_display": self.archetype.display_name(),
            "archetype_confidence": round(self.archetype_confidence, 3),
            "secondary_archetype": self.secondary_archetype.value if self.secondary_archetype else None,
            "value_segment": self.value_segment.value,
            "features": self.features.to_dict(),
            "payment_profile": self.payment_profile.to_dict(),
            "explanation": self.explanation,
        }


# ═══════════════════════════════════════════════════════════
# Archetype Report
# ═══════════════════════════════════════════════════════════

@dataclass
class ArchetypeStats:
    """Aggregated statistics for one archetype."""
    archetype: PlayerArchetype
    player_count: int = 0
    payer_count: int = 0
    payer_rate: float = 0.0
    avg_d30_ltv: float = 0.0
    avg_d30_retention: float = 0.0
    avg_player_value: float = 0.0
    avg_merge_depth: float = 0.0
    avg_collection_rate: float = 0.0
    top_creative_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype": self.archetype.value,
            "display_name": self.archetype.display_name(),
            "player_count": self.player_count,
            "payer_count": self.payer_count,
            "payer_rate": round(self.payer_rate, 3),
            "avg_d30_ltv": round(self.avg_d30_ltv, 2),
            "avg_d30_retention": round(self.avg_d30_retention, 3),
            "avg_player_value": round(self.avg_player_value, 3),
            "avg_merge_depth": round(self.avg_merge_depth, 1),
            "avg_collection_rate": round(self.avg_collection_rate, 2),
            "top_creative_ids": self.top_creative_ids[:5],
        }


# ═══════════════════════════════════════════════════════════
# Creative-Archetype Matrix Entry
# ═══════════════════════════════════════════════════════════

@dataclass
class CreativeArchetypeEntry:
    """Which creative DNA attracts which player archetype."""
    creative_genome_signature: str
    creative_genome_name: str
    player_archetype: PlayerArchetype
    player_count: int = 0
    payer_rate: float = 0.0
    avg_d30_ltv: float = 0.0
    avg_retention: float = 0.0
    fitness_score: float = 0.0

    # Creative DNA details
    fantasy_drives: list[str] = field(default_factory=list)
    mechanism_type: str = ""
    hook_type: str = ""
    reward_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_genome": self.creative_genome_signature,
            "creative_genome_name": self.creative_genome_name,
            "player_archetype": self.player_archetype.value,
            "player_archetype_display": self.player_archetype.display_name(),
            "player_count": self.player_count,
            "payer_rate": round(self.payer_rate, 3),
            "avg_d30_ltv": round(self.avg_d30_ltv, 2),
            "avg_retention": round(self.avg_retention, 3),
            "fitness_score": round(self.fitness_score, 4),
            "creative_dna": {
                "fantasy": self.fantasy_drives,
                "mechanism": self.mechanism_type,
                "hook": self.hook_type,
                "reward": self.reward_type,
            },
        }