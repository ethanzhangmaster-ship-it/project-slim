"""E5.3: Genome Value Engine — Asset valuation for Genome Marketplace.

Calculates the asset value of a creative genome:

  Genome Value =
    Performance  × 0.40   (D7 ROAS, CTR, IPM, installs)
  + Market Trend × 0.30   (category momentum, signal velocity)
  + Creative Reusability × 0.20  (mutation surface, combo potential)
  + Build Efficiency  × 0.10  (prototype speed, asset reuse)

Output:
  - Genome Value Score (0-100)
  - Value tier (Platinum/Gold/Silver/Bronze)
  - Recommended reuse strategy
  - Combinability report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome


class GenomeTier(Enum):
    PLATINUM = "platinum"  # Value >= 85
    GOLD = "gold"         # Value >= 70
    SILVER = "silver"     # Value >= 50
    BRONZE = "bronze"     # Value < 50


@dataclass
class GenomeValuation:
    """Complete valuation of a creative genome."""
    genome_id: str = ""
    genome_name: str = ""
    total_value: float = 0.0       # 0-100
    tier: GenomeTier = GenomeTier.BRONZE
    # Components
    performance_value: float = 0.0   # /40
    market_value: float = 0.0       # /30
    reusability_value: float = 0.0   # /20
    efficiency_value: float = 0.0    # /10
    # Details
    roas_normalized: float = 0.0
    mutation_surface: int = 0       # How many genes can be mutated
    combo_potential: int = 0        # How many combos possible
    recommendation: str = ""
    combinable_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "genome_name": self.genome_name,
            "total_value": round(self.total_value, 1),
            "tier": self.tier.value,
            "components": {
                "performance": round(self.performance_value, 1),
                "market": round(self.market_value, 1),
                "reusability": round(self.reusability_value, 1),
                "efficiency": round(self.efficiency_value, 1),
            },
            "roas_normalized": round(self.roas_normalized, 3),
            "mutation_surface": self.mutation_surface,
            "combo_potential": self.combo_potential,
            "recommendation": self.recommendation,
            "combinable_with": self.combinable_with,
        }


class GenomeValueEngine:
    """Calculates creative genome asset value.

    Usage:
        engine = GenomeValueEngine()
        valuation = engine.evaluate(genome, d7_roas=1.2, market_heat=85)
        print(f"{valuation.total_value}/100 → {valuation.tier.value}")
    """

    def __init__(self) -> None:
        self._market_heat: dict[str, float] = {
            "sort": 92, "merge": 78, "simulation": 85,
            "puzzle": 65, "decorate": 70, "battle": 45,
        }

    def evaluate(
        self,
        genome: Genome,
        d7_roas: float = 0.0,
        ctr: float = 0.0,
        installs: int = 0,
        market_heat: float = 50,
        trend_velocity: float = 0,
    ) -> GenomeValuation:
        """Evaluate a genome's asset value.

        Args:
            genome: V5 Genome object
            d7_roas: Day 7 ROAS
            ctr: Click-through rate
            installs: Total installs
            market_heat: Category market heat (0-100)
            trend_velocity: Category trend velocity (0-100)
        """
        # 1. Performance Value (0-40)
        roas_norm = self._normalize_roas(d7_roas)
        ctr_norm = min(1.0, ctr / 0.05) if ctr > 0 else 0.3
        install_norm = min(1.0, installs / 100000) if installs > 0 else 0.2
        perf = (roas_norm * 0.5 + ctr_norm * 0.3 + install_norm * 0.2) * 40

        # 2. Market Value (0-30)
        market = (market_heat / 100 * 0.6 + trend_velocity / 100 * 0.4) * 30

        # 3. Creative Reusability (0-20)
        gene_count = len(genome.genes)
        mutation_surface = gene_count  # Each gene can mutate
        has_reward = any(
            hasattr(g, 'gene_type') and g.gene_type.value in ('reward',)
            or (hasattr(g, 'value') and 'reward' in str(getattr(g, 'value', '')))
            or (hasattr(g, 'value') and 'evolution' in str(getattr(g, 'value', '')))
            or (hasattr(g, 'value') and 'collection' in str(getattr(g, 'value', '')))
            for g in genome.genes.values()
        )
        reusability = min(20, gene_count * 2 + (3 if has_reward else 0))

        # 4. Build Efficiency (0-10)
        core = ""
        for g in genome.genes.values():
            val = ""
            if hasattr(g, 'value'):
                val = g.value
            elif hasattr(g, 'gene_type'):
                val = g.gene_type.value
            if val in ["merge", "sort"]:
                core = val
                break
        efficiency = 8 if core else 5  # proven mechanics = easier to rebuild

        total = perf + market + reusability + efficiency
        tier = self._classify_tier(total)

        # Combinability
        combinable = self._find_combinable(genome)

        return GenomeValuation(
            genome_id=genome.genome_id,
            genome_name=genome.name,
            total_value=total,
            tier=tier,
            performance_value=perf, market_value=market,
            reusability_value=reusability, efficiency_value=efficiency,
            roas_normalized=roas_norm,
            mutation_surface=mutation_surface,
            combo_potential=len(combinable),
            recommendation=self._recommend(tier, genome),
            combinable_with=combinable,
        )

    def evaluate_from_genome_data(
        self, genome: Genome, category: str = "unknown",
    ) -> GenomeValuation:
        """Quick evaluation using only genome + category.

        Uses market heat map for category context.
        """
        heat = self._market_heat.get(category, 50)
        return self.evaluate(genome, market_heat=heat)

    def rank_genomes(self, valuations: list[GenomeValuation]) -> list[GenomeValuation]:
        """Rank genomes by total value."""
        return sorted(valuations, key=lambda v: v.total_value, reverse=True)

    def get_platinum_genomes(self, vals: list[GenomeValuation]) -> list[GenomeValuation]:
        return [v for v in vals if v.tier == GenomeTier.PLATINUM]

    # ── Internal ────────────────────────────────────────────

    @staticmethod
    def _normalize_roas(roas: float) -> float:
        if roas <= 0:
            return 0.1
        if roas >= 3.0:
            return 1.0
        return roas / 3.0

    @staticmethod
    def _classify_tier(value: float) -> GenomeTier:
        if value >= 85:
            return GenomeTier.PLATINUM
        if value >= 70:
            return GenomeTier.GOLD
        if value >= 50:
            return GenomeTier.SILVER
        return GenomeTier.BRONZE

    @staticmethod
    def _recommend(tier: GenomeTier, genome: Genome) -> str:
        if tier == GenomeTier.PLATINUM:
            return "Scale aggressively. Use as template for cross-category hybrids."
        if tier == GenomeTier.GOLD:
            return "Invest more budget. Test 3-5 mutation variants."
        if tier == GenomeTier.SILVER:
            return "Keep testing. Mutate 1-2 genes to find winner."
        return "Archive. Not worth further investment without major mutation."

    @staticmethod
    def _find_combinable(genome: Genome) -> list[str]:
        """Suggest categories this genome could combine with."""
        genes = {}
        for k, v in genome.genes.items():
            if hasattr(v, 'value'):
                genes[k] = v.value
            elif hasattr(v, 'gene_type'):
                genes[k] = v.gene_type.value
        combos = []
        if genes.get("core_loop") == "sort":
            combos.extend(["merge", "simulation", "collection"])
        if genes.get("core_loop") == "merge":
            combos.extend(["simulation", "decorate", "battle"])
        if "rescue" in genes.get("hook", ""):
            combos.append("simulation_rescue")
        if "collection" in genes.get("reward", ""):
            combos.append("collection_meta")
        return combos
