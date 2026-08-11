"""E9.5: Behavior Feature Engine — PlayerDNA → Normalized Feature Vector.

Transforms raw PlayerDNA (from E9.4) into normalized 0-1 BehaviorFeatures
ready for archetype classification.

4 Feature Dimensions (16 features total):
  - Progression: merge_velocity, merge_depth, level_growth_rate, area_unlock_speed
  - Collection: collection_rate, rare_item_ratio, completion_bias, missing_item_pressure
  - Monetization: purchase_intent, purchase_frequency, offer_conversion, spending_level
  - Engagement: session_frequency, daily_return, event_participation, retention_strength

+ 5 Archetype Scores (computed):
  - collector_score, progression_score, power_score, explorer_score, casual_score
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from market_ops.player_intelligence.models import PlayerDNA, PlayerEvent, ProgressionDNA, CollectionDNA, PaymentDNA, RetentionDNA
from market_ops.player_intelligence.player_genome import BehaviorFeatures


# ═══════════════════════════════════════════════════════════
# Normalization Benchmarks (calibrated for Merge Witch)
# ═══════════════════════════════════════════════════════════

_BENCHMARKS = {
    # Progression
    "merge_velocity": 15.0,       # merges/day (15 = power user)
    "merge_depth": 10.0,          # max merge level (10 = high)
    "level_growth_rate": 0.5,     # levels/day (0.5 = steady)
    "area_unlock_speed": 0.3,     # areas/day (0.3 = explorer)

    # Collection
    "collection_rate": 1.5,       # items/day (1.5 = collector)
    "rare_item_ratio": 1.0,       # already 0-1, bench for reference
    "completion_bias": 1.0,       # already 0-1

    # Monetization
    "purchase_frequency": 3.0,    # purchases/week (3 = whale)
    "spending_level": 50.0,       # total spend $ (50 = whale)

    # Engagement
    "session_frequency": 5.0,     # sessions/day (5 = heavy)
    "event_participation": 10.0,  # events joined (10 = active)
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _norm(value: float, benchmark: float) -> float:
    """Normalize a value to 0-1 using benchmark as ceiling."""
    if benchmark <= 0:
        return 0.0
    return _clamp(value / benchmark)


# ═══════════════════════════════════════════════════════════
# Behavior Feature Engine
# ═══════════════════════════════════════════════════════════

class BehaviorFeatureEngine:
    """Transforms PlayerDNA into normalized BehaviorFeatures.

    Usage:
        engine = BehaviorFeatureEngine()
        features = engine.extract_features(dna)

        # Batch
        all_features = engine.extract_all(dna_map)
    """

    def __init__(self) -> None:
        self._features: dict[str, BehaviorFeatures] = {}

    # ── Single Player Extraction ──────────────────────────

    def extract_features(
        self,
        dna: PlayerDNA,
        raw_events: list[PlayerEvent] | None = None,
    ) -> BehaviorFeatures:
        """Extract normalized behavior features from a single PlayerDNA.

        Args:
            dna: PlayerDNA from E9.4 pipeline
            raw_events: optional raw events for pressure/offer features

        Returns:
            BehaviorFeatures with all 16 normalized scores + 5 archetype scores
        """
        p = dna.progression
        c = dna.collection
        pm = dna.payment
        r = dna.retention
        lifetime = max(dna.lifetime_days, 1)

        # ── Progression Features ──
        merge_velocity = _norm(p.merge_speed, _BENCHMARKS["merge_velocity"])
        merge_depth = _norm(p.max_level, _BENCHMARKS["merge_depth"])
        level_growth_rate = _norm(p.progression_velocity, _BENCHMARKS["level_growth_rate"])
        area_unlock_speed = _norm(p.areas_unlocked / lifetime, _BENCHMARKS["area_unlock_speed"])

        # ── Collection Features ──
        collection_rate = _norm(c.collection_rate, _BENCHMARKS["collection_rate"])
        rare_item_ratio = c.rare_item_interest  # already 0-1
        completion_bias = _clamp(c.completion_bias)  # already 0-1

        # missing_item_pressure: from raw events or purchase triggers
        missing_item_pressure = 0.0
        if raw_events:
            missing_count = sum(1 for e in raw_events if e.event_name == "missing_item")
            missing_item_pressure = _norm(missing_count / lifetime, 0.5)  # 0.5/day = high
        elif "missing_item" in pm.purchase_triggers:
            missing_item_pressure = 0.5  # moderate if triggered purchase

        # ── Monetization Features ──
        purchase_intent = _clamp(pm.purchase_frequency / 2.0) if pm.is_payer else 0.0
        purchase_frequency = _norm(pm.purchase_frequency, _BENCHMARKS["purchase_frequency"])
        spending_level = _norm(pm.total_spend, _BENCHMARKS["spending_level"])

        # offer_conversion: from raw events (offer_view → purchase_success)
        offer_conversion = 0.0
        if raw_events:
            offer_views = sum(1 for e in raw_events if e.event_name == "offer_view")
            purchases = sum(1 for e in raw_events if e.event_name == "purchase_success")
            if offer_views > 0:
                offer_conversion = _clamp(purchases / offer_views)
        elif pm.is_payer and pm.total_purchases > 0:
            # Estimate: assume 3 offers seen per purchase
            offer_conversion = _clamp(pm.total_purchases / max(pm.total_purchases * 3, 1))

        # ── Engagement Features ──
        session_frequency = _norm(r.session_frequency, _BENCHMARKS["session_frequency"])
        daily_return = _clamp(r.days_active / lifetime) if lifetime > 0 else 0.0
        event_participation = _norm(r.event_participation, _BENCHMARKS["event_participation"])
        retention_strength = (float(r.d7_retained) * 0.4 + float(r.d30_retained) * 0.6)

        # ── Build Features ──
        features = BehaviorFeatures(
            merge_velocity=round(merge_velocity, 3),
            merge_depth=round(merge_depth, 3),
            level_growth_rate=round(level_growth_rate, 3),
            area_unlock_speed=round(area_unlock_speed, 3),

            collection_rate=round(collection_rate, 3),
            rare_item_ratio=round(rare_item_ratio, 3),
            completion_bias=round(completion_bias, 3),
            missing_item_pressure=round(missing_item_pressure, 3),

            purchase_intent=round(purchase_intent, 3),
            purchase_frequency=round(purchase_frequency, 3),
            offer_conversion=round(offer_conversion, 3),
            spending_level=round(spending_level, 3),

            session_frequency=round(session_frequency, 3),
            daily_return=round(daily_return, 3),
            event_participation=round(event_participation, 3),
            retention_strength=round(retention_strength, 3),
        )

        # ── Compute Archetype Scores ──
        self._compute_archetype_scores(features)

        return features

    # ── Archetype Score Formulas ───────────────────────────

    def _compute_archetype_scores(self, f: BehaviorFeatures) -> None:
        """Compute 5 archetype scores from normalized features.

        PRD formulas:
          collector    = 0.35×collection_rate + 0.25×rare_item_ratio
                       + 0.20×completion_bias + 0.20×event_participation
          progression  = 0.40×level_growth_rate + 0.30×area_unlock_speed
                       + 0.30×merge_depth
          power        = 0.40×spending_level + 0.30×merge_depth
                       + 0.30×purchase_frequency
          explorer     = 0.40×area_unlock_speed + 0.30×event_participation
                       + 0.30×session_frequency
          casual       = 1.0 - max(others)  (inverse baseline)
        """
        f.collector_score = round(
            0.35 * f.collection_rate
            + 0.25 * f.rare_item_ratio
            + 0.20 * f.completion_bias
            + 0.20 * f.event_participation,
            3,
        )

        f.progression_score = round(
            0.40 * f.level_growth_rate
            + 0.30 * f.area_unlock_speed
            + 0.30 * f.merge_depth,
            3,
        )

        f.power_score = round(
            0.40 * f.spending_level
            + 0.30 * f.merge_depth
            + 0.30 * f.purchase_frequency,
            3,
        )

        f.explorer_score = round(
            0.40 * f.area_unlock_speed
            + 0.30 * f.event_participation
            + 0.30 * f.session_frequency,
            3,
        )

        max_active = max(
            f.collector_score, f.progression_score,
            f.power_score, f.explorer_score,
        )
        # Casual = inverse of max active archetype.
        # When max_active is high, the player is specialized (low casual).
        # When max_active is low, the player has no strong pattern (high casual).
        # Scale: casual_score reaches 1.0 only when max_active ≤ 0.02.
        f.casual_score = round(max(0.0, 1.0 - max_active / 0.02), 3)

    # ── Batch Extraction ──────────────────────────────────

    def extract_all(
        self,
        dna_map: dict[str, PlayerDNA],
        events_by_player: dict[str, list[PlayerEvent]] | None = None,
    ) -> dict[str, BehaviorFeatures]:
        """Extract features for all players.

        Args:
            dna_map: {player_id: PlayerDNA}
            events_by_player: optional {player_id: [PlayerEvent]}

        Returns:
            {player_id: BehaviorFeatures}
        """
        self._features = {}
        for pid, dna in dna_map.items():
            raw = events_by_player.get(pid) if events_by_player else None
            self._features[pid] = self.extract_features(dna, raw)
        return self._features

    # ── Population Statistics ──────────────────────────────

    def compute_population_stats(
        self,
        features_map: dict[str, BehaviorFeatures],
    ) -> dict[str, dict[str, float]]:
        """Compute population-level statistics for feature distributions.

        Returns:
            {
                "progression": {"merge_velocity_avg": 0.45, ...},
                "collection": {...},
                ...
            }
        """
        if not features_map:
            return {}

        n = len(features_map)
        dims = {
            "progression": ["merge_velocity", "merge_depth", "level_growth_rate", "area_unlock_speed"],
            "collection": ["collection_rate", "rare_item_ratio", "completion_bias", "missing_item_pressure"],
            "monetization": ["purchase_intent", "purchase_frequency", "offer_conversion", "spending_level"],
            "engagement": ["session_frequency", "daily_return", "event_participation", "retention_strength"],
        }

        stats: dict[str, dict[str, float]] = {}
        for dim, fields in dims.items():
            dim_stats: dict[str, float] = {}
            for field in fields:
                values = [getattr(f, field) for f in features_map.values()]
                dim_stats[f"{field}_avg"] = round(sum(values) / n, 3)
                dim_stats[f"{field}_max"] = round(max(values), 3)
                dim_stats[f"{field}_min"] = round(min(values), 3)
            stats[dim] = dim_stats

        return stats

    @property
    def features(self) -> dict[str, BehaviorFeatures]:
        return self._features