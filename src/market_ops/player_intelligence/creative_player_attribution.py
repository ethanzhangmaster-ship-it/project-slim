"""E9.4: Creative-Player Attribution Engine.

Maps Creative DNA → Player Cohort → Revenue, forming the core
of the IAP value attribution pipeline.

Core question answered:
  "Which creative DNA attracts the highest-value players?"
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_ops.player_intelligence.models import (
    PlayerDNA, PlayerCohort, IAPGenomeFitness,
)
from market_ops.player_intelligence.player_dna_engine import PlayerDNAEngine


class CreativePlayerAttribution:
    """Attributes player value back to creative DNA.

    Pipeline:
      1. Load creative DNA from creative_dna_master.json
      2. Load player DNA from PlayerDNAEngine
      3. Group players by creative_id → compute cohort metrics
      4. Map creative DNA → cohort → IAPGenomeFitness
      5. Rank genomes by player value

    Usage:
        attr = CreativePlayerAttribution()
        attr.load_creative_dna()
        attr.attribute_player_dna(player_dna_map)
        genomes = attr.get_high_value_genomes(top_n=100)
        attr.export_high_value_genomes("output/active/high_value_genomes.json")
    """

    def __init__(self) -> None:
        # Creative DNA: {creative_id: {dna_dict}}
        self._creative_dna: dict[str, dict[str, Any]] = {}

        # Cohorts: {creative_id: PlayerCohort}
        self._cohorts: dict[str, PlayerCohort] = {}

        # Genome Fitness: {genome_key: IAPGenomeFitness}
        self._genome_fitness: dict[str, IAPGenomeFitness] = {}

        self._dna_master_path = Path("output/active/creative_dna_master.json")

    # ── Loading Creative DNA ─────────────────────────────────

    def load_creative_dna(self, path: str | Path | None = None) -> int:
        """Load creative DNA from master JSON.

        Returns: number of creative DNA records loaded.
        """
        p = Path(path) if path else self._dna_master_path
        if not p.exists():
            return 0

        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self._creative_dna = {}
        for item in data:
            creative_id = item.get("creative_id", "")
            if creative_id:
                self._creative_dna[creative_id] = item

        return len(self._creative_dna)

    # ── Attribution ──────────────────────────────────────────

    def attribute_player_dna(self, player_dna_map: dict[str, PlayerDNA]
                             ) -> dict[str, PlayerCohort]:
        """Attribute player DNA to creative cohorts.

        For each creative, aggregate all players' metrics into a PlayerCohort.
        """
        # Group by creative
        by_creative: dict[str, list[PlayerDNA]] = defaultdict(list)
        for dna in player_dna_map.values():
            by_creative[dna.creative_id].append(dna)

        self._cohorts = {}
        for creative_id, players in by_creative.items():
            n = len(players)
            if n == 0:
                continue

            payers = [p for p in players if p.payment.is_payer]
            payer_count = len(payers)
            payer_rate = payer_count / n

            # Retention averages
            d1_ret = sum(1 for p in players if p.retention.d1_retained) / n
            d7_ret = sum(1 for p in players if p.retention.d7_retained) / n
            d30_ret = sum(1 for p in players if p.retention.d30_retained) / n

            # LTV
            avg_d30_ltv = sum(p.d30_ltv for p in players) / n
            avg_d90_ltv = sum(p.d90_ltv for p in players) / n

            # Player value
            avg_player_value = sum(p.player_value_score for p in players) / n

            # Behavior averages
            avg_merge = sum(p.progression.merge_count for p in players) / n
            avg_merge_speed = sum(p.progression.merge_speed for p in players) / n
            avg_areas = sum(p.progression.areas_unlocked for p in players) / n
            avg_collection = sum(p.collection.collection_rate for p in players) / n
            avg_prog_vel = sum(p.progression.progression_velocity for p in players) / n

            # Top payment triggers
            trigger_counts: dict[str, int] = defaultdict(int)
            for p in payers:
                for t in p.payment.purchase_triggers:
                    trigger_counts[t] += 1
            top_triggers = sorted(trigger_counts.items(), key=lambda x: -x[1])[:5]

            cohort = PlayerCohort(
                creative_id=creative_id,
                player_count=n,
                payer_count=payer_count,
                avg_d30_ltv=round(avg_d30_ltv, 2),
                avg_d90_ltv=round(avg_d90_ltv, 2),
                payer_rate=round(payer_rate, 3),
                d1_retention=round(d1_ret, 3),
                d7_retention=round(d7_ret, 3),
                d30_retention=round(d30_ret, 3),
                avg_player_value=round(avg_player_value, 3),
                avg_merge_count=round(avg_merge, 1),
                avg_merge_speed=round(avg_merge_speed, 2),
                avg_areas_unlocked=round(avg_areas, 1),
                avg_collection_rate=round(avg_collection, 2),
                avg_progression_velocity=round(avg_prog_vel, 2),
                top_payment_triggers=top_triggers,
            )
            self._cohorts[creative_id] = cohort

        return self._cohorts

    # ── Genome Fitness ───────────────────────────────────────

    def compute_genome_fitness(self) -> dict[str, IAPGenomeFitness]:
        """Compute IAPGenomeFitness for each creative genome.

        Groups cohorts by creative DNA pattern → genome fitness.
        """
        self._genome_fitness = {}

        # Group cohorts by DNA signature
        dna_groups: dict[str, list[PlayerCohort]] = defaultdict(list)
        for creative_id, cohort in self._cohorts.items():
            dna = self._creative_dna.get(creative_id, {})
            signature = self._build_dna_signature(dna)
            dna_groups[signature].append(cohort)

        for signature, cohorts in dna_groups.items():
            if len(cohorts) == 0:
                continue

            # Aggregate across cohorts with same DNA
            total_players = sum(c.player_count for c in cohorts)
            total_payers = sum(c.payer_count for c in cohorts)

            payer_rate = total_payers / total_players if total_players > 0 else 0
            d30_ret = sum(c.d30_retention * c.player_count for c in cohorts) / total_players if total_players > 0 else 0
            avg_ltv = sum(c.avg_d30_ltv * c.player_count for c in cohorts) / total_players if total_players > 0 else 0
            avg_prog = sum(c.avg_progression_velocity * c.player_count for c in cohorts) / total_players if total_players > 0 else 0
            avg_coll = sum(c.avg_collection_rate * c.player_count for c in cohorts) / total_players if total_players > 0 else 0

            fitness = IAPGenomeFitness(
                genome_id=signature,
                genome_name=self._build_genome_name(signature),
                d30_retention=round(d30_ret, 3),
                payer_rate=round(payer_rate, 3),
                avg_d30_ltv=round(avg_ltv, 2),
                avg_progression_velocity=round(avg_prog, 2),
                avg_collection_rate=round(avg_coll, 2),
                sample_size=len(cohorts),
                player_count=total_players,
                creative_ids=[c.creative_id for c in cohorts],
            )
            fitness.compute()
            self._genome_fitness[signature] = fitness

        return self._genome_fitness

    def _build_dna_signature(self, dna: dict[str, Any]) -> str:
        """Build a unique DNA signature from creative DNA fields."""
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

    # ── Ranking ──────────────────────────────────────────────

    def get_high_value_genomes(self, top_n: int = 100
                               ) -> list[dict[str, Any]]:
        """Get top genomes ranked by IAP fitness score.

        Returns: list of genome dicts sorted by fitness_score descending.
        """
        if not self._genome_fitness:
            self.compute_genome_fitness()

        ranked = sorted(
            self._genome_fitness.values(),
            key=lambda g: (g.fitness_score, g.confidence),
            reverse=True,
        )
        return [g.to_dict() for g in ranked[:top_n]]

    def get_creative_cohorts(self) -> dict[str, dict[str, Any]]:
        """Get all creative cohorts as dicts."""
        return {cid: c.to_dict() for cid, c in self._cohorts.items()}

    # ── Export ───────────────────────────────────────────────

    def export_high_value_genomes(self, path: str | Path | None = None
                                  ) -> str:
        """Export top 100 high-value genomes to JSON."""
        p = Path(path) if path else Path("output/active/high_value_genomes.json")
        p.parent.mkdir(parents=True, exist_ok=True)

        genomes = self.get_high_value_genomes(100)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(genomes, f, ensure_ascii=False, indent=2)
        return str(p)

    def export_cohorts(self, path: str | Path | None = None) -> str:
        """Export all creative-player cohorts."""
        p = Path(path) if path else Path("output/active/creative_player_cohorts.json")
        p.parent.mkdir(parents=True, exist_ok=True)

        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self.get_creative_cohorts(), f, ensure_ascii=False, indent=2)
        return str(p)

    # ── Summary ──────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Get attribution summary."""
        total_cohorts = len(self._cohorts)
        total_players = sum(c.player_count for c in self._cohorts.values())
        total_payers = sum(c.payer_count for c in self._cohorts.values())
        total_genomes = len(self._genome_fitness)

        if total_cohorts == 0:
            return {"status": "empty", "cohorts": 0}

        avg_payer_rate = total_payers / total_players if total_players > 0 else 0
        avg_d30_ret = sum(c.d30_retention for c in self._cohorts.values()) / total_cohorts
        avg_ltv = sum(c.avg_d30_ltv for c in self._cohorts.values()) / total_cohorts

        top_genomes = self.get_high_value_genomes(5)

        return {
            "total_cohorts": total_cohorts,
            "total_players": total_players,
            "total_payers": total_payers,
            "total_genomes": total_genomes,
            "avg_payer_rate": round(avg_payer_rate, 3),
            "avg_d30_retention": round(avg_d30_ret, 3),
            "avg_d30_ltv": round(avg_ltv, 2),
            "top_genomes": top_genomes,
        }

    def run_full_pipeline(self, player_dna_map: dict[str, PlayerDNA]
                          ) -> dict[str, Any]:
        """Run the complete attribution pipeline.

        Returns: full pipeline report.
        """
        self.load_creative_dna()
        self.attribute_player_dna(player_dna_map)
        self.compute_genome_fitness()

        output_path = self.export_high_value_genomes()
        cohorts_path = self.export_cohorts()

        return {
            "summary": self.get_summary(),
            "high_value_genomes": str(output_path),
            "cohorts": str(cohorts_path),
        }