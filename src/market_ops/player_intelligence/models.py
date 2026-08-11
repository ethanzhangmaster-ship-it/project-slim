"""E9.4: Player Value Attribution Engine — Data Models.

Core data structures for connecting Creative DNA to real player behavior.

PlayerEvent: raw event from Adjust/AppsFlyer/Firebase/CSV
PlayerDNA: extracted behavior profile per player
PlayerCohort: group of players from same creative
IAPGenomeFitness: replacement for ROAS-based fitness
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ═══════════════════════════════════════════════════════════
# PlayerEvent — raw event from any source
# ═══════════════════════════════════════════════════════════

@dataclass
class PlayerEvent:
    """Unified player event from any data source (Adjust/AppsFlyer/Firebase/CSV).

    Event categories:
      - progression: level_start, level_complete, merge_create, merge_upgrade,
                     area_unlock, building_restore
      - collection: item_collect, rare_item_get, collection_complete
      - monetization: shop_open, offer_view, purchase_start, purchase_success
      - pressure: energy_empty, blocked_progress, missing_item, waiting_timer
      - engagement: session_start, daily_login, event_participate
    """
    player_id: str
    creative_id: str
    event_name: str
    event_time: datetime = field(default_factory=datetime.now)
    event_value: dict[str, Any] = field(default_factory=dict)
    source: str = "csv"  # adjust | appsflyer | firebase | csv

    @property
    def is_progression(self) -> bool:
        return self.event_name in {
            "level_start", "level_complete", "merge_create", "merge_upgrade",
            "area_unlock", "building_restore",
        }

    @property
    def is_collection(self) -> bool:
        return self.event_name in {
            "item_collect", "rare_item_get", "collection_complete",
        }

    @property
    def is_monetization(self) -> bool:
        return self.event_name in {
            "shop_open", "offer_view", "purchase_start", "purchase_success",
        }

    @property
    def is_pressure(self) -> bool:
        return self.event_name in {
            "energy_empty", "blocked_progress", "missing_item", "waiting_timer",
        }

    @property
    def is_engagement(self) -> bool:
        return self.event_name in {
            "session_start", "daily_login", "event_participate",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "creative_id": self.creative_id,
            "event_name": self.event_name,
            "event_time": self.event_time.isoformat(),
            "event_value": self.event_value,
            "source": self.source,
        }


# ═══════════════════════════════════════════════════════════
# Player DNA — extracted behavior profile
# ═══════════════════════════════════════════════════════════

@dataclass
class ProgressionDNA:
    """How the player progresses through the game."""
    merge_count: int = 0          # Total merge actions
    merge_speed: float = 0.0      # Merges per day
    max_level: int = 0            # Highest level reached
    areas_unlocked: int = 0       # Total areas unlocked
    buildings_restored: int = 0   # Buildings restored
    progression_velocity: float = 0.0  # Levels per day


@dataclass
class CollectionDNA:
    """How the player engages with collections."""
    items_collected: int = 0
    rare_items: int = 0
    collections_completed: int = 0
    collection_rate: float = 0.0       # Items per day
    rare_item_interest: float = 0.0    # Rare items / total items
    completion_bias: float = 0.0       # Collections completed / available


@dataclass
class PaymentDNA:
    """How and when the player pays."""
    is_payer: bool = False
    first_purchase_day: int = -1      # Day of first purchase (-1 = never)
    total_purchases: int = 0
    total_spend: float = 0.0
    purchase_frequency: float = 0.0    # Purchases per week
    avg_order_value: float = 0.0
    purchase_triggers: list[str] = field(default_factory=list)
    # e.g., ["blocked_progress", "missing_item", "time_gate"]


@dataclass
class RetentionDNA:
    """How the player stays engaged."""
    days_active: int = 0
    total_sessions: int = 0
    session_frequency: float = 0.0     # Sessions per day
    d1_retained: bool = False
    d7_retained: bool = False
    d30_retained: bool = False
    return_behavior: str = "unknown"   # daily | weekly | sporadic | churned
    event_participation: int = 0       # Special event participation count


@dataclass
class PlayerDNA:
    """Complete player behavior DNA profile."""
    player_id: str
    creative_id: str

    # Core behavior
    progression: ProgressionDNA = field(default_factory=ProgressionDNA)
    collection: CollectionDNA = field(default_factory=CollectionDNA)
    payment: PaymentDNA = field(default_factory=PaymentDNA)
    retention: RetentionDNA = field(default_factory=RetentionDNA)

    # Derived metrics
    lifetime_days: int = 0
    d30_ltv: float = 0.0
    d90_ltv: float = 0.0
    player_value_score: float = 0.0    # Composite 0-1 score

    def compute_derived(self) -> None:
        """Compute derived metrics from raw DNA."""
        self.d30_ltv = self.payment.total_spend
        self.d90_ltv = self.payment.total_spend * 1.3  # projection

        # Player Value Score: 0-1 composite
        retention_score = (
            (1.0 if self.retention.d1_retained else 0.0) * 0.3
            + (1.0 if self.retention.d7_retained else 0.0) * 0.3
            + (1.0 if self.retention.d30_retained else 0.0) * 0.4
        )
        payer_score = 1.0 if self.payment.is_payer else 0.0
        ltv_score = min(self.d30_ltv / 20.0, 1.0)  # $20 LTV = perfect

        self.player_value_score = (
            retention_score * 0.35
            + payer_score * 0.35
            + ltv_score * 0.30
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "creative_id": self.creative_id,
            "progression": {
                "merge_count": self.progression.merge_count,
                "merge_speed": round(self.progression.merge_speed, 2),
                "max_level": self.progression.max_level,
                "areas_unlocked": self.progression.areas_unlocked,
                "progression_velocity": round(self.progression.progression_velocity, 2),
            },
            "collection": {
                "items_collected": self.collection.items_collected,
                "rare_items": self.collection.rare_items,
                "collections_completed": self.collection.collections_completed,
                "collection_rate": round(self.collection.collection_rate, 2),
                "completion_bias": round(self.collection.completion_bias, 2),
            },
            "payment": {
                "is_payer": self.payment.is_payer,
                "first_purchase_day": self.payment.first_purchase_day,
                "total_purchases": self.payment.total_purchases,
                "total_spend": round(self.payment.total_spend, 2),
                "purchase_frequency": round(self.payment.purchase_frequency, 2),
                "purchase_triggers": self.payment.purchase_triggers,
            },
            "retention": {
                "days_active": self.retention.days_active,
                "session_frequency": round(self.retention.session_frequency, 2),
                "d1_retained": self.retention.d1_retained,
                "d7_retained": self.retention.d7_retained,
                "d30_retained": self.retention.d30_retained,
                "return_behavior": self.retention.return_behavior,
            },
            "derived": {
                "lifetime_days": self.lifetime_days,
                "d30_ltv": round(self.d30_ltv, 2),
                "player_value_score": round(self.player_value_score, 3),
            },
        }


# ═══════════════════════════════════════════════════════════
# Player Cohort — group of players from same creative
# ═══════════════════════════════════════════════════════════

@dataclass
class PlayerCohort:
    """Players acquired from the same creative, with aggregated metrics."""
    creative_id: str
    player_count: int = 0
    payer_count: int = 0

    # Aggregated metrics
    avg_d30_ltv: float = 0.0
    avg_d90_ltv: float = 0.0
    payer_rate: float = 0.0
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0
    avg_player_value: float = 0.0

    # Behavior averages
    avg_merge_count: float = 0.0
    avg_merge_speed: float = 0.0
    avg_areas_unlocked: float = 0.0
    avg_collection_rate: float = 0.0
    avg_progression_velocity: float = 0.0

    # Top payment triggers in this cohort
    top_payment_triggers: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "player_count": self.player_count,
            "payer_count": self.payer_count,
            "payer_rate": round(self.payer_rate, 3),
            "d1_retention": round(self.d1_retention, 3),
            "d7_retention": round(self.d7_retention, 3),
            "d30_retention": round(self.d30_retention, 3),
            "avg_d30_ltv": round(self.avg_d30_ltv, 2),
            "avg_player_value": round(self.avg_player_value, 3),
            "avg_merge_count": round(self.avg_merge_count, 1),
            "avg_merge_speed": round(self.avg_merge_speed, 2),
            "avg_areas_unlocked": round(self.avg_areas_unlocked, 1),
            "avg_collection_rate": round(self.avg_collection_rate, 2),
            "avg_progression_velocity": round(self.avg_progression_velocity, 2),
            "top_payment_triggers": [
                {"trigger": t, "count": c} for t, c in self.top_payment_triggers[:5]
            ],
        }


# ═══════════════════════════════════════════════════════════
# IAP Genome Fitness — replaces ROAS-based fitness
# ═══════════════════════════════════════════════════════════

@dataclass
class IAPGenomeFitness:
    """IAP-focused genome fitness based on PLAYER VALUE, not ad ROAS.

    Formula:
      Fitness = 0.25 × D30 Retention + 0.25 × Payer Rate
              + 0.25 × D30 LTV_scaled + 0.15 × Progression Velocity
              + 0.10 × Collection Engagement
    """
    genome_id: str = ""
    genome_name: str = ""

    # Fitness components
    d30_retention: float = 0.0
    payer_rate: float = 0.0
    avg_d30_ltv: float = 0.0
    avg_progression_velocity: float = 0.0
    avg_collection_rate: float = 0.0

    # Composite score
    fitness_score: float = 0.0
    confidence: float = 0.0
    sample_size: int = 0

    # Metadata
    creative_ids: list[str] = field(default_factory=list)
    player_count: int = 0

    def compute(self) -> None:
        """Compute composite IAP fitness score."""
        ltv_scaled = min(self.avg_d30_ltv / 20.0, 1.0)
        prog_scaled = min(self.avg_progression_velocity / 5.0, 1.0)
        coll_scaled = min(self.avg_collection_rate / 3.0, 1.0)

        self.fitness_score = (
            self.d30_retention * 0.25
            + self.payer_rate * 0.25
            + ltv_scaled * 0.25
            + prog_scaled * 0.15
            + coll_scaled * 0.10
        )
        self.confidence = min(self.player_count / 100.0, 1.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "genome_name": self.genome_name,
            "fitness_score": round(self.fitness_score, 4),
            "confidence": round(self.confidence, 3),
            "sample_size": self.sample_size,
            "player_count": self.player_count,
            "components": {
                "d30_retention": round(self.d30_retention, 3),
                "payer_rate": round(self.payer_rate, 3),
                "avg_d30_ltv": round(self.avg_d30_ltv, 2),
                "avg_progression_velocity": round(self.avg_progression_velocity, 2),
                "avg_collection_rate": round(self.avg_collection_rate, 2),
            },
            "creative_ids": self.creative_ids[:10],
        }