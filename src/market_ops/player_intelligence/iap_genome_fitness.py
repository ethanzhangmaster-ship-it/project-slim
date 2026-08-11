"""E9.4: IAP Genome Fitness Calculator.

Replaces ROAS-based fitness with player-value-based fitness.
Used by the CreativePlayerAttribution engine.

Formula:
  Fitness = 0.25 × D30 Retention + 0.25 × Payer Rate
          + 0.25 × D30 LTV_scaled + 0.15 × Progression Velocity
          + 0.10 × Collection Engagement
"""

from __future__ import annotations

from typing import Any

from market_ops.player_intelligence.models import IAPGenomeFitness
from market_ops.player_intelligence.creative_player_attribution import CreativePlayerAttribution


class IAPGenomeFitnessCalculator:
    """Computes IAP-focused genome fitness scores.

    Differences from old ROAS-based fitness:
      - ROAS → replaced by D30 LTV (actual player revenue)
      - CTR/CPI → replaced by Retention (player quality)
      - Winner rate → replaced by Payer Rate (monetization)
      - New: Progression Velocity + Collection Engagement

    Usage:
        calc = IAPGenomeFitnessCalculator()
        calc.load_attribution(attribution_engine)
        genomes = calc.rank_genomes(top_n=100)
        calc.export("output/active/high_value_genomes.json")
    """

    def __init__(self) -> None:
        self._attribution: CreativePlayerAttribution | None = None
        self._genomes: dict[str, IAPGenomeFitness] = {}

    def load_attribution(self, attribution: CreativePlayerAttribution) -> None:
        """Load from a CreativePlayerAttribution engine."""
        self._attribution = attribution
        self._genomes = attribution._genome_fitness

    def compute(self, genome_id: str, **metrics: float) -> IAPGenomeFitness:
        """Compute fitness for a single genome.

        Args:
            genome_id: unique genome identifier
            **metrics: d30_retention, payer_rate, avg_d30_ltv,
                      avg_progression_velocity, avg_collection_rate,
                      player_count, sample_size
        """
        fitness = IAPGenomeFitness(
            genome_id=genome_id,
            genome_name=metrics.get("genome_name", genome_id),
            d30_retention=metrics.get("d30_retention", 0.0),
            payer_rate=metrics.get("payer_rate", 0.0),
            avg_d30_ltv=metrics.get("avg_d30_ltv", 0.0),
            avg_progression_velocity=metrics.get("avg_progression_velocity", 0.0),
            avg_collection_rate=metrics.get("avg_collection_rate", 0.0),
            player_count=int(metrics.get("player_count", 0)),
            sample_size=int(metrics.get("sample_size", 0)),
        )
        fitness.compute()
        self._genomes[genome_id] = fitness
        return fitness

    def rank_genomes(self, top_n: int = 100) -> list[IAPGenomeFitness]:
        """Rank genomes by fitness score (highest first)."""
        return sorted(
            self._genomes.values(),
            key=lambda g: (g.fitness_score, g.confidence),
            reverse=True,
        )[:top_n]

    def compare_with_roas(
        self, roas_fitness_map: dict[str, float]
    ) -> dict[str, dict[str, Any]]:
        """Compare IAP fitness with old ROAS-based fitness.

        Returns: {genome_id: {iap_fitness, roas_fitness, delta}}
        """
        comparison: dict[str, dict[str, Any]] = {}
        for genome_id, fitness in self._genomes.items():
            roas_fit = roas_fitness_map.get(genome_id, 0)
            comparison[genome_id] = {
                "iap_fitness": round(fitness.fitness_score, 4),
                "roas_fitness": round(roas_fit, 4),
                "delta": round(fitness.fitness_score - roas_fit, 4),
                "player_count": fitness.player_count,
                "d30_retention": fitness.d30_retention,
                "payer_rate": fitness.payer_rate,
            }

        return comparison

    def get_summary(self) -> dict[str, Any]:
        """Get fitness summary statistics."""
        if not self._genomes:
            return {"status": "empty", "genomes": 0}

        scores = [g.fitness_score for g in self._genomes.values()]
        top5 = self.rank_genomes(5)

        return {
            "total_genomes": len(self._genomes),
            "avg_fitness": round(sum(scores) / len(scores), 4),
            "max_fitness": round(max(scores), 4),
            "min_fitness": round(min(scores), 4),
            "top_5": [g.to_dict() for g in top5],
        }

    def export(self, path: str | None = None) -> str:
        """Export ranked genomes to JSON."""
        from pathlib import Path
        p = Path(path) if path else Path("output/active/high_value_genomes.json")
        p.parent.mkdir(parents=True, exist_ok=True)

        import json
        genomes = [g.to_dict() for g in self.rank_genomes(100)]
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(genomes, f, ensure_ascii=False, indent=2)
        return str(p)