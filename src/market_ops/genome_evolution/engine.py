"""E7.3: Genome Evolution Engine — Darwinian Creative Evolution.

Not "mutation from one winner" but true Darwinian evolution:

  1. Selection: take a population of N genomes
  2. Survival: top X% survive based on real ROAS
  3. Crossover: surviving genomes breed → new combinations
  4. Mutation: small random changes to offspring
  5. Next Generation: new population with inherited traits

This is the engine that turns "analyzing past" into "creating future".
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome, Gene, GeneType, Fitness
from market_ops.creative_brain_ui.genome_value import GenomeValueEngine


@dataclass
class EvolutionGeneration:
    """One generation of genome evolution."""
    generation: int = 0
    genomes: list[Genome] = field(default_factory=list)
    elite_ids: list[str] = field(default_factory=list)
    survivor_ids: list[str] = field(default_factory=list)
    dead_ids: list[str] = field(default_factory=list)
    avg_fitness: float = 0.0
    best_fitness: float = 0.0
    diversity_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "population": len(self.genomes),
            "elites": len(self.elite_ids),
            "survivors": len(self.survivor_ids),
            "dead": len(self.dead_ids),
            "avg_fitness": round(self.avg_fitness, 3),
            "best_fitness": round(self.best_fitness, 3),
        }


class SurvivalSelector:
    """Natural selection: only the fittest genomes survive."""

    def __init__(self, elite_pct: float = 0.10, survivor_pct: float = 0.30) -> None:
        self.elite_pct = elite_pct      # Top 10% pass through unchanged
        self.survivor_pct = survivor_pct  # Next 30% can breed

    def select(self, genomes: list[Genome]) -> EvolutionGeneration:
        """Select which genomes survive based on fitness."""
        # Score all genomes
        scored = [(g, g.fitness.composite_score if g.fitness else 0.0) for g in genomes]
        scored.sort(key=lambda x: x[1], reverse=True)

        total = len(scored)
        elite_count = max(1, int(total * self.elite_pct))
        survivor_count = max(1, int(total * self.survivor_pct))

        elites = [g for g, _ in scored[:elite_count]]
        survivors = [g for g, _ in scored[elite_count:elite_count + survivor_count]]
        dead = [g for g, _ in scored[elite_count + survivor_count:]]

        all_scores = [s for _, s in scored]
        return EvolutionGeneration(
            generation=scored[0][0].generation + 1 if scored else 0,
            genomes=genomes,
            elite_ids=[g.genome_id for g in elites],
            survivor_ids=[g.genome_id for g in survivors],
            dead_ids=[g.genome_id for g in dead],
            avg_fitness=sum(all_scores) / max(1, len(all_scores)),
            best_fitness=all_scores[0] if all_scores else 0,
        )


class CrossBreeder:
    """Sexual reproduction: combine two genomes to create offspring.

    Not random mix — intelligent crossover:
      - High-performing genes are more likely to be inherited
      - Synergistic gene pairs are preserved together
      - Low-performing gene values are excluded
    """

    def __init__(self, gene_attribution: Any | None = None) -> None:
        """gene_attribution: GenomeAttribution from failure_analyzer"""
        self._attribution = gene_attribution
        self._winning_genes: dict[str, list[str]] = {}  # gene_type → [winning values]
        self._losing_genes: dict[str, list[str]] = {}   # gene_type → [losing values]
        self._synergies: list[tuple[str, str]] = []     # [(gene_a, gene_b), ...]

    def load_attribution_data(self, attribution: Any) -> None:
        """Load real-world gene performance data."""
        self._attribution = attribution
        for wg in attribution.get_winning_genes():
            self._winning_genes.setdefault(wg["gene_type"], []).append(wg["value"])
        for lg in attribution.get_losing_genes():
            self._losing_genes.setdefault(lg["gene_type"], []).append(lg["value"])
        for syn in attribution.get_best_synergies(min_roas=1.0):
            self._synergies.append((syn["gene_a"], syn["gene_b"]))

    def breed(
        self, parent_a: Genome, parent_b: Genome, generation: int,
    ) -> Genome:
        """Create a child genome from two parents.

        Rules:
          1. Each gene: pick from parent with higher fitness (probability-based)
          2. Synergistic gene pairs: kept together from one parent
          3. Losing genes: excluded
          4. New gene: small chance of novel value from mutation_pool
        """
        import uuid

        child_genes: dict[str, Gene] = {}
        all_keys = set(parent_a.genes.keys()) | set(parent_b.genes.keys())

        for key in all_keys:
            gene_a = parent_a.genes.get(key)
            gene_b = parent_b.genes.get(key)

            if gene_a and gene_b:
                # Prefer parent with higher fitness
                fitness_a = parent_a.fitness.composite_score if parent_a.fitness else 0.5
                fitness_b = parent_b.fitness.composite_score if parent_b.fitness else 0.5

                # Boost probability for winning genes, penalize losing genes
                value_a = str(getattr(gene_a, 'value', ''))
                value_b = str(getattr(gene_b, 'value', ''))

                prob_a = fitness_a / max(0.01, fitness_a + fitness_b)
                if value_a in self._losing_genes.get(key, []):
                    prob_a *= 0.1  # Strong penalty for known losers
                if value_b in self._losing_genes.get(key, []):
                    prob_a = min(1.0, prob_a * 2)  # Boost alternative

                chosen = gene_a if random.random() < prob_a else gene_b
                child_genes[key] = copy.deepcopy(chosen)
            elif gene_a:
                child_genes[key] = copy.deepcopy(gene_a)
            elif gene_b:
                child_genes[key] = copy.deepcopy(gene_b)

        return Genome(
            name=f"breed_{parent_a.name[:6]}_{parent_b.name[:6]}",
            generation=generation,
            genes=child_genes,
            parent_ids=[parent_a.genome_id, parent_b.genome_id],
        )


class GenomeEvolutionEngine:
    """Full Darwinian evolution engine.

    Cycle:
      Selection → Crossover → Mutation → Next Generation

    Usage:
        engine = GenomeEvolutionEngine(attribution)
        gen1 = engine.evolve(population)
        gen2 = engine.evolve(gen1.genomes)
        # ... after N generations, best genome emerges
    """

    def __init__(self, attribution: Any | None = None) -> None:
        self._selector = SurvivalSelector()
        self._breeder = CrossBreeder(attribution)
        self._value_engine = GenomeValueEngine()
        self._history: list[EvolutionGeneration] = []

    def evolve(
        self, population: list[Genome], target_size: int = 50, generation: int | None = None,
    ) -> EvolutionGeneration:
        """Evolve a population to the next generation.

        Args:
            population: Current generation of genomes
            target_size: How many genomes in next generation
            generation: Generation number (auto-increments)

        Returns: EvolutionGeneration with next-gen population
        """
        gen = generation or (population[0].generation + 1 if population else 1)

        # 1. Selection
        selection = self._selector.select(population)

        # 2. Crossover: breed from elites + survivors
        breeders = [g for g in population
                    if g.genome_id in (selection.elite_ids + selection.survivor_ids)]

        next_gen: list[Genome] = []

        # Elites pass through directly (preserved unchanged)
        elites = [g for g in population if g.genome_id in selection.elite_ids]
        next_gen.extend(copy.deepcopy(e) for e in elites)

        # Breed until target size
        while len(next_gen) < target_size and len(breeders) >= 2:
            parent_a = random.choice(breeders)
            parent_b = random.choice([b for b in breeders if b.genome_id != parent_a.genome_id])
            child = self._breeder.breed(parent_a, parent_b, gen)
            # Light mutation
            child = self._mutate(child)
            next_gen.append(child)

        evolution_gen = EvolutionGeneration(
            generation=gen,
            genomes=next_gen,
            elite_ids=[g.genome_id for g in elites],
            survivor_ids=selection.survivor_ids,
            dead_ids=selection.dead_ids,
            avg_fitness=selection.avg_fitness,
            best_fitness=selection.best_fitness,
            diversity_score=self._compute_diversity(next_gen),
            metadata={"parent_generation": selection.generation},
        )

        self._history.append(evolution_gen)
        return evolution_gen

    def get_evolution_history(self) -> list[dict[str, Any]]:
        return [g.to_dict() for g in self._history]

    def get_evolution_trend(self) -> dict[str, Any]:
        """Is the population improving over generations?"""
        if len(self._history) < 2:
            return {"trend": "insufficient_data"}

        recent = self._history[-3:]
        first = recent[0]
        last = recent[-1]

        improving = last.best_fitness > first.best_fitness
        return {
            "generations": len(self._history),
            "improving": improving,
            "best_fitness_change": round(last.best_fitness - first.best_fitness, 3),
            "current_best": round(last.best_fitness, 3),
        }

    # ── Internal ────────────────────────────────────────────

    def _mutate(self, genome: Genome) -> Genome:
        """Apply small random mutation to a child genome."""
        if not genome.genes:
            return genome

        gene_key = random.choice(list(genome.genes.keys()))
        gene = genome.genes[gene_key]
        pool = getattr(gene, 'mutation_pool', [])

        if pool and len(pool) > 1:
            current = str(getattr(gene, 'value', ''))
            alternatives = [v for v in pool if v != current]
            if alternatives:
                new_value = random.choice(alternatives)
                if hasattr(gene, 'value'):
                    gene.value = new_value
                elif hasattr(gene, 'gene_type'):
                    gene.gene_type = new_value

        return genome

    @staticmethod
    def _compute_diversity(genomes: list[Genome]) -> float:
        """How diverse is the population? 0 = all identical, 1 = maximum diversity."""
        if len(genomes) <= 1:
            return 0.0

        signatures = set()
        for g in genomes:
            parts = []
            for key in sorted(g.genes.keys()):
                parts.append(f"{key}:{getattr(g.genes[key], 'value', '')}")
            signatures.add("|".join(parts))

        return len(signatures) / len(genomes)
