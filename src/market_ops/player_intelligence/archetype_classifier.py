"""E9.5: Archetype Classifier — Rule-based Player Classification + Creative-Archetype Matrix.

Core pipeline:
  1. BehaviorFeatures → PlayerArchetype (5 types)
  2. PlayerDNA → ValueSegment (high/medium/low)
  3. PlayerDNA → PaymentProfile (trigger + probability)
  4. Creative DNA + Player Archetype → Creative-Archetype Matrix

Outputs:
  - player_genomes.json: all players with archetype + value
  - archetype_report.json: per-archetype aggregated stats
  - creative_archetype_matrix.json: creative DNA → best player type
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_ops.player_intelligence.models import PlayerDNA
from market_ops.player_intelligence.player_genome import (
    PlayerArchetype, ValueSegment,
    BehaviorFeatures, PaymentProfile, PlayerGenome,
    ArchetypeStats, CreativeArchetypeEntry,
)


# ═══════════════════════════════════════════════════════════
# Classification Thresholds
# ═══════════════════════════════════════════════════════════

# Minimum archetype score to be classified (vs Casual)
_MIN_ARCHETYPE_SCORE = 0.04

# Minimum score gap between primary and secondary for high confidence
_HIGH_CONFIDENCE_GAP = 0.10

# Value segment thresholds
_HIGH_VALUE_D30_RETENTION = 0.50     # D30 retention benchmark
_HIGH_VALUE_PAYER_RATE = 0.05        # Payer rate benchmark
_HIGH_VALUE_LTV = 5.0                # LTV benchmark ($)

# Archetype explanation labels
_ARCHETYPE_REASONS: dict[PlayerArchetype, list[str]] = {
    PlayerArchetype.COLLECTOR: [
        "high_collection_rate", "rare_item_interest",
        "completion_bias", "collection_events",
    ],
    PlayerArchetype.PROGRESSION: [
        "fast_leveling", "area_unlock_speed",
        "merge_depth", "progression_velocity",
    ],
    PlayerArchetype.POWER: [
        "high_merge_depth", "high_merge_velocity",
        "high_spending", "upgrade_frequency",
    ],
    PlayerArchetype.EXPLORER: [
        "area_discovery", "event_joining",
        "high_session_frequency", "story_progress",
    ],
    PlayerArchetype.CASUAL: [
        "low_engagement", "random_pattern",
        "no_specialization", "baseline_player",
    ],
}


# ═══════════════════════════════════════════════════════════
# Archetype Classifier
# ═══════════════════════════════════════════════════════════

class ArchetypeClassifier:
    """Rule-based player archetype classifier.

    Usage:
        classifier = ArchetypeClassifier()
        genomes = classifier.classify_all(dna_map, features_map)
        report = classifier.build_archetype_report(genomes)
        matrix = classifier.build_creative_archetype_matrix(genomes, creative_dna)
    """

    def __init__(self) -> None:
        self._genomes: list[PlayerGenome] = []
        self._archetype_stats: dict[PlayerArchetype, ArchetypeStats] = {}
        self._creative_matrix: list[CreativeArchetypeEntry] = []

    # ── Single Classification ──────────────────────────────

    def classify(
        self,
        features: BehaviorFeatures,
    ) -> tuple[PlayerArchetype, float, PlayerArchetype | None, list[str]]:
        """Classify a single player from BehaviorFeatures.

        Returns:
            (primary_archetype, confidence, secondary_archetype, explanation)
        """
        # Rank archetypes by score
        scores = [
            (PlayerArchetype.COLLECTOR, features.collector_score),
            (PlayerArchetype.PROGRESSION, features.progression_score),
            (PlayerArchetype.POWER, features.power_score),
            (PlayerArchetype.EXPLORER, features.explorer_score),
            (PlayerArchetype.CASUAL, features.casual_score),
        ]
        scores.sort(key=lambda x: -x[1])

        top_arch, top_score = scores[0]
        second_arch, second_score = scores[1]

        # If top score is below threshold, classify as Casual
        if top_score < _MIN_ARCHETYPE_SCORE or top_arch == PlayerArchetype.CASUAL:
            primary = PlayerArchetype.CASUAL
            secondary = None
            # Confidence = how much higher casual is vs next non-casual
            non_casual = [(a, s) for a, s in scores if a != PlayerArchetype.CASUAL]
            if non_casual:
                confidence = round(1.0 - non_casual[0][1], 3)
            else:
                confidence = 0.95
        else:
            primary = top_arch
            secondary = second_arch if second_arch != PlayerArchetype.CASUAL else None
            gap = top_score - second_score
            confidence = round(min(gap / _HIGH_CONFIDENCE_GAP, 1.0), 3)

        # Build explanation
        explanation = self._build_explanation(primary, features)

        return primary, confidence, secondary, explanation

    def _build_explanation(
        self, archetype: PlayerArchetype, features: BehaviorFeatures,
    ) -> list[str]:
        """Build human-readable explanation for archetype classification."""
        reasons: list[str] = []

        # Feature → reason mapping
        feature_checks: list[tuple[float, str, str]] = [
            (features.collection_rate, "high_collection_rate", "collection_rate"),
            (features.rare_item_ratio, "rare_item_interest", "rare_item_ratio"),
            (features.completion_bias, "completion_bias", "completion_bias"),
            (features.merge_velocity, "high_merge_velocity", "merge_velocity"),
            (features.merge_depth, "high_merge_depth", "merge_depth"),
            (features.level_growth_rate, "fast_leveling", "level_growth_rate"),
            (features.area_unlock_speed, "area_discovery", "area_unlock_speed"),
            (features.spending_level, "high_spending", "spending_level"),
            (features.purchase_intent, "purchase_intent", "purchase_intent"),
            (features.session_frequency, "high_session_frequency", "session_frequency"),
            (features.event_participation, "event_joining", "event_participation"),
            (features.retention_strength, "strong_retention", "retention_strength"),
        ]

        for value, reason, _label in feature_checks:
            if value > 0.5:
                reasons.append(reason)

        if not reasons:
            reasons = ["low_engagement", "random_pattern"]

        return reasons[:5]  # top 5 reasons

    # ── Value Segmentation ─────────────────────────────────

    def _determine_value_segment(
        self, dna: PlayerDNA, archetype: PlayerArchetype,
    ) -> ValueSegment:
        """Determine player value segment based on retention + payer + LTV."""
        is_d30 = dna.retention.d30_retained
        is_payer = dna.payment.is_payer
        ltv = dna.d30_ltv

        # High value: D30 retained AND (payer OR LTV > benchmark)
        if is_d30 and (is_payer or ltv > _HIGH_VALUE_LTV):
            return ValueSegment.HIGH

        # Low value: early churn, no progression, no payment
        if (not is_d30 and not is_payer
                and dna.progression.merge_count < 5
                and dna.retention.days_active < 3):
            return ValueSegment.LOW

        return ValueSegment.MEDIUM

    # ── Payment Profile ────────────────────────────────────

    def _build_payment_profile(self, dna: PlayerDNA) -> PaymentProfile:
        """Build payment profile from PlayerDNA."""
        pm = dna.payment
        r = dna.retention

        # Determine trigger type
        trigger_type = "none"
        if pm.purchase_triggers:
            # Map event names to trigger categories
            trigger_map = {
                "blocked_progress": "blocked_progress",
                "missing_item": "missing_item",
                "energy_empty": "energy",
                "waiting_timer": "time_gate",
            }
            for t in pm.purchase_triggers:
                if t in trigger_map:
                    trigger_type = trigger_map[t]
                    break
            if trigger_type == "none" and pm.purchase_triggers:
                trigger_type = "exclusive_item"

        # Purchase probability: based on payer status + frequency
        if pm.is_payer:
            purchase_probability = min(pm.purchase_frequency / 3.0, 0.95)
        else:
            # Non-payer probability based on engagement signals
            signals = 0
            if r.d7_retained:
                signals += 0.05
            if r.d30_retained:
                signals += 0.05
            if pm.total_purchases == 0 and r.session_frequency > 2.0:
                signals += 0.03  # engaged but not paying yet
            purchase_probability = signals

        # Predicted D30 LTV
        predicted_ltv = dna.d30_ltv
        if not pm.is_payer and purchase_probability > 0.05:
            # Estimate: probability × avg order × frequency
            predicted_ltv = purchase_probability * 5.0 * 2.0  # $5 avg × 2 purchases

        return PaymentProfile(
            is_payer=pm.is_payer,
            trigger_type=trigger_type,
            purchase_probability=round(purchase_probability, 3),
            avg_order_value=round(pm.avg_order_value, 2),
            predicted_ltv_d30=round(predicted_ltv, 2),
        )

    # ── Batch Classification ───────────────────────────────

    def classify_all(
        self,
        dna_map: dict[str, PlayerDNA],
        features_map: dict[str, BehaviorFeatures],
    ) -> list[PlayerGenome]:
        """Classify all players into PlayerGenomes.

        Args:
            dna_map: {player_id: PlayerDNA}
            features_map: {player_id: BehaviorFeatures}

        Returns:
            list of PlayerGenome (one per player)
        """
        self._genomes = []

        for player_id, dna in dna_map.items():
            features = features_map.get(player_id)
            if features is None:
                continue

            archetype, confidence, secondary, explanation = self.classify(features)
            value_segment = self._determine_value_segment(dna, archetype)
            payment_profile = self._build_payment_profile(dna)

            genome = PlayerGenome(
                player_id=player_id,
                creative_id=dna.creative_id,
                archetype=archetype,
                archetype_confidence=confidence,
                secondary_archetype=secondary,
                value_segment=value_segment,
                features=features,
                payment_profile=payment_profile,
                explanation=explanation,
            )
            self._genomes.append(genome)

        return self._genomes

    # ── Archetype Report ───────────────────────────────────

    def build_archetype_report(
        self,
        genomes: list[PlayerGenome] | None = None,
    ) -> dict[str, ArchetypeStats]:
        """Build per-archetype aggregated statistics.

        Returns:
            {archetype_value: ArchetypeStats}
        """
        genomes = genomes or self._genomes
        if not genomes:
            return {}

        # Group by archetype
        by_archetype: dict[PlayerArchetype, list[PlayerGenome]] = defaultdict(list)
        for g in genomes:
            by_archetype[g.archetype].append(g)

        self._archetype_stats = {}
        for arch, players in by_archetype.items():
            n = len(players)
            payers = [p for p in players if p.payment_profile.is_payer]
            payer_count = len(payers)

            payer_rate = payer_count / n if n > 0 else 0
            avg_ltv = sum(p.payment_profile.predicted_ltv_d30 for p in players) / n if n > 0 else 0
            avg_retention = sum(p.features.retention_strength for p in players) / n if n > 0 else 0
            avg_pv = sum(
                (1.0 if p.value_segment == ValueSegment.HIGH else
                 0.5 if p.value_segment == ValueSegment.MEDIUM else 0.0)
                for p in players
            ) / n if n > 0 else 0
            avg_merge = sum(p.features.merge_depth for p in players) / n if n > 0 else 0
            avg_collection = sum(p.features.collection_rate for p in players) / n if n > 0 else 0

            # Top creative IDs for this archetype
            creative_counts: dict[str, int] = defaultdict(int)
            for p in players:
                creative_counts[p.creative_id] += 1
            top_creative = [
                cid for cid, _ in sorted(creative_counts.items(), key=lambda x: -x[1])[:5]
            ]

            stats = ArchetypeStats(
                archetype=arch,
                player_count=n,
                payer_count=payer_count,
                payer_rate=round(payer_rate, 3),
                avg_d30_ltv=round(avg_ltv, 2),
                avg_d30_retention=round(avg_retention, 3),
                avg_player_value=round(avg_pv, 3),
                avg_merge_depth=round(avg_merge, 1),
                avg_collection_rate=round(avg_collection, 2),
                top_creative_ids=top_creative,
            )
            self._archetype_stats[arch] = stats

        return self._archetype_stats

    # ── Creative-Archetype Matrix ──────────────────────────

    def build_creative_archetype_matrix(
        self,
        genomes: list[PlayerGenome] | None = None,
        creative_dna_map: dict[str, dict[str, Any]] | None = None,
    ) -> list[CreativeArchetypeEntry]:
        """Build Creative DNA → Player Archetype mapping matrix.

        Answers: "Which creative DNA attracts which player archetype?"

        Args:
            genomes: classified player genomes
            creative_dna_map: {creative_id: dna_dict} from creative_dna_master.json

        Returns:
            list of CreativeArchetypeEntry sorted by fitness_score descending
        """
        genomes = genomes or self._genomes
        creative_dna_map = creative_dna_map or {}
        if not genomes:
            return []

        # Group by (creative_signature, player_archetype)
        groups: dict[tuple[str, PlayerArchetype], list[PlayerGenome]] = defaultdict(list)
        for g in genomes:
            dna = creative_dna_map.get(g.creative_id, {})
            signature = self._build_dna_signature(dna)
            key = (signature, g.archetype)
            groups[key].append(g)

        self._creative_matrix = []
        for (signature, archetype), players in groups.items():
            n = len(players)
            if n < 3:  # minimum sample size
                continue

            payers = [p for p in players if p.payment_profile.is_payer]
            payer_rate = len(payers) / n
            avg_ltv = sum(p.payment_profile.predicted_ltv_d30 for p in players) / n
            avg_retention = sum(p.features.retention_strength for p in players) / n

            # Fitness = player value composite
            ltv_scaled = min(avg_ltv / 20.0, 1.0)
            fitness = round(
                payer_rate * 0.35
                + avg_retention * 0.35
                + ltv_scaled * 0.30,
                4,
            )

            # Extract creative DNA details from the first player's creative
            sample_dna = creative_dna_map.get(players[0].creative_id, {})
            fantasy_drives: list[str] = []
            mechanism_type = ""
            hook_type = ""
            reward_type = ""

            fantasy = sample_dna.get("fantasy", {})
            if isinstance(fantasy, dict):
                fantasy_drives = fantasy.get("drives", []) or fantasy.get("loops", []) or []
            elif isinstance(fantasy, str) and fantasy:
                fantasy_drives = [fantasy]

            for field in ["mechanism", "hook", "reward"]:
                val = sample_dna.get(field, {})
                if isinstance(val, dict):
                    t = val.get("type", "")
                elif isinstance(val, str):
                    t = val
                else:
                    t = ""
                if field == "mechanism":
                    mechanism_type = t
                elif field == "hook":
                    hook_type = t
                elif field == "reward":
                    reward_type = t

            entry = CreativeArchetypeEntry(
                creative_genome_signature=signature,
                creative_genome_name=self._build_genome_name(signature),
                player_archetype=archetype,
                player_count=n,
                payer_rate=round(payer_rate, 3),
                avg_d30_ltv=round(avg_ltv, 2),
                avg_retention=round(avg_retention, 3),
                fitness_score=fitness,
                fantasy_drives=fantasy_drives,
                mechanism_type=mechanism_type,
                hook_type=hook_type,
                reward_type=reward_type,
            )
            self._creative_matrix.append(entry)

        # Sort by fitness descending
        self._creative_matrix.sort(key=lambda e: -e.fitness_score)
        return self._creative_matrix

    def _build_dna_signature(self, dna: dict[str, Any]) -> str:
        """Build a unique DNA signature from creative DNA fields."""
        if not dna:
            return "unknown"
        parts = []
        for field in ["mechanism", "hook", "reward", "fantasy", "progression"]:
            val = dna.get(field, {})
            if isinstance(val, dict):
                t = val.get("type", "")
                if not t:
                    drives = val.get("drives", []) or val.get("loops", [])
                    if drives:
                        parts.append(f"{field}={'+'.join(drives[:2])}")
                else:
                    parts.append(f"{field}={t}")
            elif isinstance(val, str) and val:
                parts.append(f"{field}={val}")
        return "|".join(sorted(parts)) if parts else "unknown"

    def _build_genome_name(self, signature: str) -> str:
        """Build a human-readable genome name from signature."""
        parts = signature.split("|")
        name_parts = []
        for p in parts:
            if "=" in p:
                _, val = p.split("=", 1)
                name_parts.append(val.replace("+", "-"))
        return "_".join(name_parts[:4]) if name_parts else "unknown_genome"

    # ── Top Answers ────────────────────────────────────────

    def get_top_creative_for_archetype(
        self, archetype: PlayerArchetype, top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Get top creative genomes for a specific player archetype.

        Answers: "Which creative attracts the highest value Collector players?"
        """
        if not self._creative_matrix:
            return []

        matching = [
            e for e in self._creative_matrix
            if e.player_archetype == archetype
        ]
        matching.sort(key=lambda e: -e.fitness_score)
        return [e.to_dict() for e in matching[:top_n]]

    def get_top_archetype_for_creative(
        self, creative_signature: str, top_n: int = 3,
    ) -> list[dict[str, Any]]:
        """Get top player archetypes for a specific creative genome.

        Answers: "What type of players does this creative attract?"
        """
        if not self._creative_matrix:
            return []

        matching = [
            e for e in self._creative_matrix
            if e.creative_genome_signature == creative_signature
        ]
        matching.sort(key=lambda e: -e.fitness_score)
        return [e.to_dict() for e in matching[:top_n]]

    # ── Export ─────────────────────────────────────────────

    def export_player_genomes(
        self,
        output_dir: str | Path | None = None,
        genomes: list[PlayerGenome] | None = None,
    ) -> str:
        """Export all player genomes to JSON.

        → output/player_intelligence/player_genomes.json
        """
        genomes = genomes or self._genomes
        p = Path(output_dir) if output_dir else Path("output/player_intelligence")
        p.mkdir(parents=True, exist_ok=True)

        out_file = p / "player_genomes.json"
        data = [g.to_dict() for g in genomes]
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(out_file)

    def export_archetype_report(
        self,
        output_dir: str | Path | None = None,
        stats: dict[PlayerArchetype, ArchetypeStats] | None = None,
    ) -> str:
        """Export archetype report to JSON.

        → output/player_intelligence/archetype_report.json
        """
        stats = stats or self._archetype_stats
        p = Path(output_dir) if output_dir else Path("output/player_intelligence")
        p.mkdir(parents=True, exist_ok=True)

        out_file = p / "archetype_report.json"
        # Sort by player count descending
        sorted_stats = sorted(stats.values(), key=lambda s: -s.player_count)
        data = [s.to_dict() for s in sorted_stats]
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(out_file)

    def export_creative_archetype_matrix(
        self,
        output_dir: str | Path | None = None,
        matrix: list[CreativeArchetypeEntry] | None = None,
    ) -> str:
        """Export creative-archetype matrix to JSON.

        → output/player_intelligence/creative_archetype_matrix.json
        """
        matrix = matrix or self._creative_matrix
        p = Path(output_dir) if output_dir else Path("output/player_intelligence")
        p.mkdir(parents=True, exist_ok=True)

        out_file = p / "creative_archetype_matrix.json"
        data = [e.to_dict() for e in matrix]
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(out_file)

    def export_all(
        self,
        output_dir: str | Path | None = None,
        genomes: list[PlayerGenome] | None = None,
        creative_dna_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        """Export all 3 output files.

        Returns: {file_type: file_path}
        """
        genomes = genomes or self._genomes

        # Build report and matrix if not already done
        if not self._archetype_stats:
            self.build_archetype_report(genomes)
        if not self._creative_matrix:
            self.build_creative_archetype_matrix(genomes, creative_dna_map)

        return {
            "player_genomes": self.export_player_genomes(output_dir, genomes),
            "archetype_report": self.export_archetype_report(output_dir),
            "creative_archetype_matrix": self.export_creative_archetype_matrix(output_dir),
        }

    # ── Summary ────────────────────────────────────────────

    def get_summary(
        self,
        genomes: list[PlayerGenome] | None = None,
    ) -> dict[str, Any]:
        """Get classification summary."""
        genomes = genomes or self._genomes
        if not genomes:
            return {"status": "empty", "total_players": 0}

        # Count by archetype
        arch_counts: dict[str, int] = defaultdict(int)
        for g in genomes:
            arch_counts[g.archetype.value] += 1

        # Count by value segment
        value_counts: dict[str, int] = defaultdict(int)
        for g in genomes:
            value_counts[g.value_segment.value] += 1

        # Average confidence
        avg_confidence = sum(g.archetype_confidence for g in genomes) / len(genomes)

        # Top findings
        top_findings: list[dict[str, Any]] = []
        if self._creative_matrix:
            for entry in self._creative_matrix[:5]:
                top_findings.append({
                    "creative_genome": entry.creative_genome_name,
                    "player_archetype": entry.player_archetype.value,
                    "player_count": entry.player_count,
                    "payer_rate": entry.payer_rate,
                    "avg_d30_ltv": entry.avg_d30_ltv,
                    "fitness": entry.fitness_score,
                })

        return {
            "total_players": len(genomes),
            "archetype_distribution": dict(arch_counts),
            "value_segments": dict(value_counts),
            "avg_confidence": round(avg_confidence, 3),
            "top_creative_archetype_pairs": top_findings,
        }

    # ── Properties ─────────────────────────────────────────

    @property
    def genomes(self) -> list[PlayerGenome]:
        return self._genomes

    @property
    def archetype_stats(self) -> dict[PlayerArchetype, ArchetypeStats]:
        return self._archetype_stats

    @property
    def creative_matrix(self) -> list[CreativeArchetypeEntry]:
        return self._creative_matrix


# ═══════════════════════════════════════════════════════════
# Full Pipeline Runner
# ═══════════════════════════════════════════════════════════

def run_e95_pipeline(
    dna_map: dict[str, PlayerDNA],
    events_by_player: dict[str, list[Any]] | None = None,
    creative_dna_map: dict[str, dict[str, Any]] | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the complete E9.5 pipeline: Feature Extraction → Classification → Export.

    Args:
        dna_map: {player_id: PlayerDNA} from E9.4 pipeline
        events_by_player: optional raw events for pressure features
        creative_dna_map: optional creative DNA map for matrix
        output_dir: output directory (default: output/player_intelligence/)

    Returns:
        Full pipeline report with paths and summary
    """
    from market_ops.player_intelligence.behavior_feature_engine import BehaviorFeatureEngine

    # Step 1: Extract features
    feature_engine = BehaviorFeatureEngine()
    features_map = feature_engine.extract_all(dna_map, events_by_player)

    # Step 2: Classify
    classifier = ArchetypeClassifier()
    genomes = classifier.classify_all(dna_map, features_map)

    # Step 3: Build reports
    classifier.build_archetype_report(genomes)
    classifier.build_creative_archetype_matrix(genomes, creative_dna_map)

    # Step 4: Export
    export_paths = classifier.export_all(output_dir, genomes, creative_dna_map)

    # Step 5: Population stats
    pop_stats = feature_engine.compute_population_stats(features_map)

    return {
        "summary": classifier.get_summary(genomes),
        "export_paths": export_paths,
        "population_stats": pop_stats,
    }