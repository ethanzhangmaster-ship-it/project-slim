"""M8: Evolution Memory — What Works, Creative Intelligence Model.

Learns from experiment history to form a Creative Intelligence Model:
  - Which gene combinations produce winners
  - Which hooks/rewards/visuals correlate with high ROAS
  - Which mutations are high-risk vs high-reward

Outputs:
  - Pattern recommendations for future mutations
  - Gene-level success rates
  - Creative archetype templates
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict

from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType
from market_ops.creative_evolution.experiment_engine import ExperimentResult, ExperimentDecision


@dataclass
class GeneSuccessRate:
    """Success statistics for a specific gene value."""
    gene_type: str = ""
    value: str = ""
    total_tests: int = 0
    winner_count: int = 0
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_type": self.gene_type,
            "value": self.value,
            "total_tests": self.total_tests,
            "winner_count": self.winner_count,
            "avg_roas": round(self.avg_roas, 3),
            "avg_ctr": round(self.avg_ctr, 4),
            "success_rate": round(self.success_rate, 3),
        }


@dataclass
class CreativeArchetype:
    """A proven creative DNA pattern that works."""
    archetype_id: str = ""
    name: str = ""
    gene_signature: dict[str, str] = field(default_factory=dict)
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    total_appearances: int = 0
    win_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype_id": self.archetype_id,
            "name": self.name,
            "gene_signature": self.gene_signature,
            "avg_roas": round(self.avg_roas, 3),
            "avg_ctr": round(self.avg_ctr, 4),
            "total_appearances": self.total_appearances,
            "win_count": self.win_count,
            "win_rate": round(self.win_count / max(1, self.total_appearances), 3),
        }


@dataclass
class CreativeIntelligenceModel:
    """The accumulated intelligence from all experiments."""
    version: str = "1.0"
    total_experiments: int = 0
    total_winners: int = 0
    gene_success_rates: dict[str, list[GeneSuccessRate]] = field(default_factory=dict)
    archetypes: list[CreativeArchetype] = field(default_factory=list)
    top_hooks: list[str] = field(default_factory=list)
    top_rewards: list[str] = field(default_factory=list)
    top_visuals: list[str] = field(default_factory=list)
    mutation_effectiveness: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total_experiments": self.total_experiments,
            "total_winners": self.total_winners,
            "gene_success_rates": {
                k: [gsr.to_dict() for gsr in v]
                for k, v in self.gene_success_rates.items()
            },
            "archetypes": [a.to_dict() for a in self.archetypes],
            "top_hooks": self.top_hooks,
            "top_rewards": self.top_rewards,
            "top_visuals": self.top_visuals,
            "mutation_effectiveness": self.mutation_effectiveness,
        }


class EvolutionMemory:
    """Records experiment history and extracts creative intelligence.

    Usage:
        memory = EvolutionMemory()
        memory.record_experiment(genome, result)
        # After many experiments:
        model = memory.build_intelligence_model()
        suggestions = memory.suggest_for_genome(my_genome)
    """

    def __init__(self) -> None:
        self._history: list[tuple[Genome, ExperimentResult]] = []
        self._gene_stats: dict[str, dict[str, GeneSuccessRate]] = defaultdict(
            lambda: defaultdict(lambda: GeneSuccessRate())
        )
        self._archetypes: dict[str, CreativeArchetype] = {}

    # ── Recording ───────────────────────────────────────────

    def record_experiment(self, genome: Genome, result: ExperimentResult) -> None:
        """Record a single experiment result."""
        self._history.append((genome, result))
        self._update_gene_stats(genome, result)
        self._update_archetypes(genome, result)

    def record_batch(
        self, genomes: list[Genome], results: list[ExperimentResult]
    ) -> None:
        """Record a batch of experiments."""
        for genome, result in zip(genomes, results):
            self.record_experiment(genome, result)

    # ── Intelligence Building ───────────────────────────────

    def build_intelligence_model(self) -> CreativeIntelligenceModel:
        """Build the Creative Intelligence Model from all history."""
        model = CreativeIntelligenceModel()
        model.total_experiments = len(self._history)
        model.total_winners = sum(
            1 for _, r in self._history if r.decision == ExperimentDecision.SCALE
        )

        # Gene success rates
        for gene_type, values in self._gene_stats.items():
            model.gene_success_rates[gene_type] = list(values.values())

        # Sort by success rate
        model.gene_success_rates = {
            k: sorted(v, key=lambda x: x.success_rate, reverse=True)
            for k, v in model.gene_success_rates.items()
        }

        # Top performers per gene type
        model.top_hooks = self._top_values_for_type("hook", n=5)
        model.top_rewards = self._top_values_for_type("reward", n=5)
        model.top_visuals = self._top_values_for_type("visual", n=5)

        # Archetypes
        model.archetypes = sorted(
            self._archetypes.values(),
            key=lambda a: a.win_count / max(1, a.total_appearances),
            reverse=True,
        )[:20]

        # Mutation effectiveness
        model.mutation_effectiveness = self._calculate_mutation_effectiveness()

        return model

    def suggest_for_genome(self, genome: Genome) -> dict[str, Any]:
        """Suggest mutations/improvements for a genome based on learned patterns.

        Returns:
            Dict with suggestions like:
            {
                "recommended_hook": "rescue",
                "recommended_reward": "evolution",
                "risky_mutations": ["gameplay"],
                "high_confidence_changes": ["visual"],
            }
        """
        suggestions: dict[str, Any] = {
            "recommended_changes": {},
            "risky_mutations": [],
            "high_confidence_changes": [],
            "similar_winners": [],
        }

        # For each gene, check if there's a better alternative
        for key, gene in genome.genes.items():
            stats = self._gene_stats.get(key, {})
            if not stats:
                continue

            # Find best performing value for this gene type
            best = max(stats.values(), key=lambda s: s.success_rate, default=None)
            current = stats.get(gene.value)

            if best and best.value != gene.value:
                if best.success_rate > (current.success_rate if current else 0) + 0.1:
                    suggestions["recommended_changes"][key] = {
                        "current": gene.value,
                        "recommended": best.value,
                        "expected_improvement": round(
                            best.success_rate - (current.success_rate if current else 0), 2
                        ),
                    }
                    suggestions["high_confidence_changes"].append(key)

            # Check if current gene is high-risk
            if current and current.success_rate < 0.2 and current.total_tests > 5:
                suggestions["risky_mutations"].append(key)

        # Find similar winning archetypes
        sig = self._genome_signature(genome)
        for archetype in self._archetypes.values():
            similarity = self._signature_similarity(sig, archetype.gene_signature)
            if similarity > 0.7 and archetype.win_count > 0:
                suggestions["similar_winners"].append({
                    "archetype_id": archetype.archetype_id,
                    "name": archetype.name,
                    "similarity": round(similarity, 2),
                    "avg_roas": archetype.avg_roas,
                })

        return suggestions

    def get_gene_performance(self, gene_type: str, value: str) -> GeneSuccessRate | None:
        """Get performance stats for a specific gene value."""
        return self._gene_stats.get(gene_type, {}).get(value)

    def get_top_archetypes(self, n: int = 5) -> list[CreativeArchetype]:
        """Get top N winning archetypes."""
        sorted_archetypes = sorted(
            self._archetypes.values(),
            key=lambda a: a.win_count / max(1, a.total_appearances),
            reverse=True,
        )
        return sorted_archetypes[:n]

    # ── Internal: Statistics ────────────────────────────────

    def _update_gene_stats(self, genome: Genome, result: ExperimentResult) -> None:
        """Update per-gene success statistics."""
        is_winner = result.decision == ExperimentDecision.SCALE

        for key, gene in genome.genes.items():
            gsr = self._gene_stats[key][gene.value]
            gsr.gene_type = key
            gsr.value = gene.value
            gsr.total_tests += 1
            if is_winner:
                gsr.winner_count += 1
            # Running average
            gsr.avg_roas = (
                gsr.avg_roas * (gsr.total_tests - 1) + result.roas
            ) / gsr.total_tests
            gsr.avg_ctr = (
                gsr.avg_ctr * (gsr.total_tests - 1) + result.ctr
            ) / gsr.total_tests
            gsr.success_rate = gsr.winner_count / gsr.total_tests

    def _update_archetypes(self, genome: Genome, result: ExperimentResult) -> None:
        """Update archetype statistics."""
        sig = self._genome_signature(genome)
        sig_str = json.dumps(sig, sort_keys=True)
        archetype_id = f"arch_{hash(sig_str) % 100000:05d}"

        if archetype_id not in self._archetypes:
            self._archetypes[archetype_id] = CreativeArchetype(
                archetype_id=archetype_id,
                name=f"Archetype_{archetype_id[-5:]}",
                gene_signature=sig,
            )

        arch = self._archetypes[archetype_id]
        arch.total_appearances += 1
        if result.decision == ExperimentDecision.SCALE:
            arch.win_count += 1
        arch.avg_roas = (
            arch.avg_roas * (arch.total_appearances - 1) + result.roas
        ) / arch.total_appearances
        arch.avg_ctr = (
            arch.avg_ctr * (arch.total_appearances - 1) + result.ctr
        ) / arch.total_appearances

    def _top_values_for_type(self, gene_type: str, n: int = 5) -> list[str]:
        """Get top N values for a gene type by success rate."""
        stats = self._gene_stats.get(gene_type, {})
        sorted_stats = sorted(
            stats.values(),
            key=lambda s: s.success_rate,
            reverse=True,
        )
        return [s.value for s in sorted_stats[:n] if s.total_tests >= 3]

    def _calculate_mutation_effectiveness(self) -> dict[str, float]:
        """Calculate which mutation types are most effective."""
        # Placeholder: would track mutation operator → outcome correlation
        return {
            "point_mutation": 0.15,
            "random_reset": 0.12,
            "swap": 0.18,
            "crossover": 0.22,
        }

    @staticmethod
    def _genome_signature(genome: Genome) -> dict[str, str]:
        """Create a gene signature for archetype matching."""
        return {
            key: gene.value
            for key, gene in genome.genes.items()
        }

    @staticmethod
    def _signature_similarity(
        sig_a: dict[str, str], sig_b: dict[str, str]
    ) -> float:
        """Calculate similarity between two gene signatures (0-1)."""
        all_keys = set(sig_a.keys()) | set(sig_b.keys())
        if not all_keys:
            return 0.0
        matches = sum(1 for k in all_keys if sig_a.get(k) == sig_b.get(k))
        return matches / len(all_keys)
