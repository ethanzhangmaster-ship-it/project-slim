"""E9.6: Creative Archetype Profile — Historical Archetype Distribution Database.

Loads E9.5 outputs (creative_archetype_matrix.json) and computes:
  - Global archetype priors: P(archetype) across all creatives
  - Per-archetype metric averages: avg LTV, payer_rate, retention
  - Per-creative-genome archetype distributions

Used by ArchetypePredictor for Bayesian prior calculation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════
# Creative Archetype Profile DB
# ═══════════════════════════════════════════════════════════

class CreativeArchetypeProfileDB:
    """Historical profile database for creative → archetype matching.

    Usage:
        db = CreativeArchetypeProfileDB()
        db.load()
        priors = db.get_global_priors()
        metrics = db.get_archetype_metrics("power")
        dist = db.get_creative_distribution("collect_dragons-become_powerful")
    """

    def __init__(self) -> None:
        # Raw matrix entries from E9.5
        self._entries: list[dict[str, Any]] = []

        # Global priors: {archetype: probability}
        self._global_priors: dict[str, float] = {}

        # Per-archetype metrics: {archetype: {ltv, payer_rate, retention}}
        self._archetype_metrics: dict[str, dict[str, float]] = {}

        # Per-creative archetype distributions:
        # {creative_genome_name: {archetype: probability}}
        self._creative_distributions: dict[str, dict[str, float]] = {}

        # Per-creative best archetype
        self._creative_best_archetype: dict[str, str] = {}

        # Total player counts
        self._total_players: int = 0

        self._matrix_path = Path("output/player_intelligence/creative_archetype_matrix.json")

    # ── Loading ────────────────────────────────────────────

    def load(self, path: str | Path | None = None) -> int:
        """Load creative-archetype matrix from E9.5 output.

        Returns: number of entries loaded.
        """
        p = Path(path) if path else self._matrix_path
        if not p.exists():
            return 0

        with open(p, 'r', encoding='utf-8') as f:
            self._entries = json.load(f)

        self._compute_priors()
        self._compute_archetype_metrics()
        self._compute_creative_distributions()

        return len(self._entries)

    def _compute_priors(self) -> None:
        """Compute global archetype prior probabilities."""
        archetype_counts: dict[str, int] = defaultdict(int)
        self._total_players = 0

        for entry in self._entries:
            arch = entry.get("player_archetype", "")
            count = entry.get("player_count", 0)
            archetype_counts[arch] += count
            self._total_players += count

        if self._total_players > 0:
            self._global_priors = {
                arch: count / self._total_players
                for arch, count in archetype_counts.items()
            }

    def _compute_archetype_metrics(self) -> None:
        """Compute per-archetype average metrics."""
        archetype_metrics: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: {"ltv": [], "payer_rate": [], "retention": []},
        )

        for entry in self._entries:
            arch = entry.get("player_archetype", "")
            count = entry.get("player_count", 1)
            ltv = entry.get("avg_d30_ltv", 0)
            payer_rate = entry.get("payer_rate", 0)
            retention = entry.get("avg_retention", 0)

            # Weight by player count
            for _ in range(count):
                archetype_metrics[arch]["ltv"].append(ltv)
                archetype_metrics[arch]["payer_rate"].append(payer_rate)
                archetype_metrics[arch]["retention"].append(retention)

        self._archetype_metrics = {}
        for arch, metrics in archetype_metrics.items():
            n = len(metrics["ltv"])
            if n == 0:
                continue
            self._archetype_metrics[arch] = {
                "avg_ltv": round(sum(metrics["ltv"]) / n, 2),
                "avg_payer_rate": round(sum(metrics["payer_rate"]) / n, 3),
                "avg_retention": round(sum(metrics["retention"]) / n, 3),
                "sample_size": n,
            }

    def _compute_creative_distributions(self) -> None:
        """Compute per-creative-genome archetype distributions."""
        creative_groups: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int),
        )
        creative_totals: dict[str, int] = defaultdict(int)

        for entry in self._entries:
            genome = entry.get("creative_genome_name", "unknown")
            arch = entry.get("player_archetype", "")
            count = entry.get("player_count", 0)
            creative_groups[genome][arch] += count
            creative_totals[genome] += count

        self._creative_distributions = {}
        self._creative_best_archetype = {}

        for genome, arch_counts in creative_groups.items():
            total = creative_totals[genome]
            if total == 0:
                continue
            dist = {
                arch: count / total
                for arch, count in arch_counts.items()
            }
            self._creative_distributions[genome] = dist

            # Best archetype for this creative
            best = max(arch_counts.items(), key=lambda x: x[1])
            self._creative_best_archetype[genome] = best[0]

    # ── Queries ────────────────────────────────────────────

    def get_global_priors(self) -> dict[str, float]:
        """Get global archetype prior probabilities.

        If historical data is too homogeneous (single creative genome),
        returns flat priors to avoid biasing predictions.
        """
        if len(self._creative_distributions) <= 1:
            # Flat priors when data is too homogeneous
            return {
                "power": 0.2, "collector": 0.2,
                "explorer": 0.2, "progression": 0.2,
                "casual": 0.2,
            }
        return dict(self._global_priors)

    def get_archetype_metrics(self, archetype: str) -> dict[str, float]:
        """Get average metrics for an archetype.

        Returns: {avg_ltv, avg_payer_rate, avg_retention, sample_size}
        """
        return dict(self._archetype_metrics.get(archetype, {
            "avg_ltv": 0.0, "avg_payer_rate": 0.0,
            "avg_retention": 0.0, "sample_size": 0,
        }))

    def get_creative_distribution(self, genome_name: str) -> dict[str, float]:
        """Get archetype distribution for a specific creative genome."""
        return dict(self._creative_distributions.get(genome_name, {}))

    def get_creative_best_archetype(self, genome_name: str) -> str:
        """Get the best archetype for a creative genome."""
        return self._creative_best_archetype.get(genome_name, "casual")

    def get_all_archetype_metrics(self) -> dict[str, dict[str, float]]:
        """Get all archetype metrics."""
        return dict(self._archetype_metrics)

    def has_historical_data(self) -> bool:
        return len(self._entries) > 0

    # ── Summary ────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Get profile database summary."""
        return {
            "total_entries": len(self._entries),
            "total_players": self._total_players,
            "global_priors": {
                arch: round(p, 3)
                for arch, p in self._global_priors.items()
            },
            "archetype_metrics": {
                arch: {
                    "avg_ltv": m["avg_ltv"],
                    "avg_payer_rate": m["avg_payer_rate"],
                    "avg_retention": m["avg_retention"],
                }
                for arch, m in self._archetype_metrics.items()
            },
            "num_creative_genomes": len(self._creative_distributions),
        }