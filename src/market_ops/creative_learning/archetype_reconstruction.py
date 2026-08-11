"""E9.7: Archetype Reconstruction — Re-runs E9.5 classifier on real player data.

Takes raw player behavior events (from Adjust/Firebase/CSV) and re-runs
the full E9.5 pipeline to compute actual archetype distributions per creative.

Pipeline:
  PlayerEvent (raw)
      ↓
  PlayerDNAEngine.extract_all()
      ↓
  {player_id: PlayerDNA}
      ↓
  BehaviorFeatureEngine.extract_all()
      ↓
  {player_id: BehaviorFeatures}
      ↓
  ArchetypeClassifier.classify_all()
      ↓
  [PlayerGenome]
      ↓
  Group by creative_id → Archetype Distribution

Supports:
  - Real player events (from Adjust/Firebase CSV)
  - Mock mode (returns pre-computed distributions from PerformanceCollector)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from market_ops.player_intelligence.models import PlayerEvent, PlayerDNA
from market_ops.player_intelligence.player_dna_engine import PlayerDNAEngine
from market_ops.player_intelligence.behavior_feature_engine import BehaviorFeatureEngine
from market_ops.player_intelligence.archetype_classifier import ArchetypeClassifier
from market_ops.player_intelligence.player_genome import PlayerGenome
from market_ops.creative_learning.schemas import CreativeActualPerformance


# ═══════════════════════════════════════════════════════════
# Archetype Reconstruction Engine
# ═══════════════════════════════════════════════════════════

class ArchetypeReconstructionEngine:
    """Reconstructs actual archetype distributions from real player events.

    Usage:
        engine = ArchetypeReconstructionEngine()
        dists = engine.reconstruct_from_events(events_by_creative)
        # or
        dists = engine.reconstruct_from_performances(performances)
    """

    def __init__(self) -> None:
        self._dna_engine = PlayerDNAEngine()
        self._feature_engine = BehaviorFeatureEngine()
        self._classifier = ArchetypeClassifier()

    # ── Real Data Pipeline ─────────────────────────────────

    def reconstruct_from_events(
        self,
        events_by_creative: dict[str, list[PlayerEvent]],
    ) -> dict[str, dict[str, float]]:
        """Reconstruct archetype distributions from raw player events.

        Args:
            events_by_creative: {creative_id: [PlayerEvent, ...]}

        Returns:
            {creative_id: {archetype: proportion}}
        """
        result: dict[str, dict[str, float]] = {}

        for creative_id, events in events_by_creative.items():
            if not events:
                continue

            # Step 1: Extract PlayerDNA
            dna_map = self._dna_engine.extract_all(events)
            if not dna_map:
                continue

            # Step 2: Group events by player
            events_by_player: dict[str, list[PlayerEvent]] = defaultdict(list)
            for e in events:
                events_by_player[e.player_id].append(e)

            # Step 3: Extract BehaviorFeatures
            features_map = self._feature_engine.extract_all(dna_map, events_by_player)

            # Step 4: Classify into archetypes
            genomes = self._classifier.classify_all(dna_map, features_map)

            # Step 5: Compute distribution
            dist = self._compute_distribution(genomes)
            result[creative_id] = dist

        return result

    def reconstruct_from_dna_map(
        self,
        dna_map: dict[str, PlayerDNA],
        events_by_player: dict[str, list[PlayerEvent]] | None = None,
    ) -> dict[str, float]:
        """Reconstruct archetype distribution from a DNA map.

        Args:
            dna_map: {player_id: PlayerDNA}
            events_by_player: optional raw events for pressure features

        Returns:
            {archetype: proportion}
        """
        features_map = self._feature_engine.extract_all(dna_map, events_by_player)
        genomes = self._classifier.classify_all(dna_map, features_map)
        return self._compute_distribution(genomes)

    # ── Mock Data Pipeline ─────────────────────────────────

    def reconstruct_from_performances(
        self,
        performances: dict[str, CreativeActualPerformance],
    ) -> dict[str, dict[str, float]]:
        """Extract archetype distributions from pre-computed performances.

        When real player events aren't available, use the archetype distributions
        already stored in CreativeActualPerformance (from MockPerformanceGenerator
        or real attribution data).

        Args:
            performances: {creative_id: CreativeActualPerformance}

        Returns:
            {creative_id: {archetype: proportion}}
        """
        result = {}
        for creative_id, perf in performances.items():
            if perf.archetype_distribution:
                result[creative_id] = dict(perf.archetype_distribution)
        return result

    # ── Helpers ────────────────────────────────────────────

    @staticmethod
    def _compute_distribution(genomes: list[PlayerGenome]) -> dict[str, float]:
        """Compute archetype distribution from classified genomes."""
        if not genomes:
            return {}

        counts: dict[str, int] = defaultdict(int)
        for g in genomes:
            counts[g.archetype.value] += 1

        total = len(genomes)
        return {
            arch: round(count / total, 3)
            for arch, count in counts.items()
        }

    @staticmethod
    def merge_distributions(
        distributions: list[dict[str, float]],
        weights: list[float] | None = None,
    ) -> dict[str, float]:
        """Merge multiple archetype distributions (weighted average).

        Useful for aggregating distributions across multiple campaigns
        for the same creative.
        """
        if not distributions:
            return {}

        all_arches: set[str] = set()
        for d in distributions:
            all_arches.update(d.keys())

        if weights is None:
            weights = [1.0] * len(distributions)

        total_weight = sum(weights)
        if total_weight == 0:
            return {}

        result = {}
        for arch in all_arches:
            weighted_sum = sum(
                weights[i] * distributions[i].get(arch, 0)
                for i in range(len(distributions))
            )
            result[arch] = round(weighted_sum / total_weight, 3)

        return result

    # ── Summary ────────────────────────────────────────────

    def get_reconstruction_summary(
        self,
        distributions: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        """Get summary of reconstructed distributions."""
        if not distributions:
            return {"status": "empty", "total_creatives": 0}

        n = len(distributions)

        # Average distribution across all creatives
        avg_dist: dict[str, list[float]] = defaultdict(list)
        for dist in distributions.values():
            for arch, prop in dist.items():
                avg_dist[arch].append(prop)

        avg = {
            arch: round(sum(props) / len(props), 3)
            for arch, props in avg_dist.items()
        }

        # Dominant archetype per creative
        dominant_counts: dict[str, int] = defaultdict(int)
        for dist in distributions.values():
            if dist:
                dominant = max(dist.items(), key=lambda x: x[1])[0]
                dominant_counts[dominant] += 1

        return {
            "total_creatives": n,
            "avg_distribution": avg,
            "dominant_archetype_distribution": dict(dominant_counts),
        }