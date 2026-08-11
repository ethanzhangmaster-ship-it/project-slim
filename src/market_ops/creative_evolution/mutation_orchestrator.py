"""M4: Creative Mutation Engine Orchestrator — Winner → 50 Mutants.

Bridges existing GeneMutationEngine + PopulationManager to produce
a full mutated population from a single winner genome.

Strategies:
  1. Winner Exploitation: clone winner, mutate single genes
  2. Exploration: apply multiple operators to same genome
  3. Crossover: combine two winner genomes
  4. Diverse seeding: inject new gene values from mutation pools

API note: GeneMutationEngine.mutate(genome, request, rng) — 3 positional args.
           MutationRequest uses genome_id (not genome object).
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import (
    Genome,
    Population,
    MutationRequest,
    MutationOperator,
    GeneType,
)
from market_ops.creative_brain.v5_evolution.gene_mutation import GeneMutationEngine
from market_ops.creative_brain.v5_evolution.population_manager import PopulationManager
from market_ops.creative_brain.v5_evolution.mutation_utils import clone_genome
from market_ops.creative_brain.v5_evolution.random_context import RandomContext


class CreativeMutationOrchestrator:
    """Orchestrates mutation from winner genome to full population.

    Usage:
        orchestrator = CreativeMutationOrchestrator()
        population = orchestrator.evolve_from_winner(winner_genome, target_count=50)
    """

    SEED_BASE = 20260719  # Deterministic base seed

    def __init__(
        self,
        gene_engine: GeneMutationEngine | None = None,
        population_manager: PopulationManager | None = None,
    ) -> None:
        self._gene_engine = gene_engine or GeneMutationEngine()
        self._pop_manager = population_manager or PopulationManager()
        self._mutation_seq = 0

    # ── Public API ──────────────────────────────────────────

    def evolve_from_winner(
        self,
        winner: Genome,
        target_count: int = 50,
        generation: int = 1,
    ) -> Population:
        """Generate a mutated population from a single winner genome."""
        mutants: list[Genome] = []

        # Strategy 1: Winner preservation (elite clone)
        elite = self._clone_genome(winner, generation=generation)
        mutants.append(elite)

        # Strategy 2: Single-gene exploitation (mutate one gene at a time)
        single_gene_mutants = self._generate_single_gene_mutants(winner, generation)
        mutants.extend(single_gene_mutants)

        # Strategy 3: Multi-gene exploration (combined operators)
        multi_gene_mutants = self._generate_multi_gene_mutants(
            winner, generation, count=target_count // 3
        )
        mutants.extend(multi_gene_mutants)

        # Strategy 4: Random reset mutants
        reset_mutants = self._generate_reset_mutants(
            winner, generation, count=target_count // 4
        )
        mutants.extend(reset_mutants)

        # Deduplicate & fill
        mutants = self._deduplicate(mutants)[:target_count]

        while len(mutants) < target_count:
            req = MutationRequest(
                genome_id=winner.genome_id,
                operators=[MutationOperator.POINT_MUTATION],
                mutation_rate=0.15,
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(
                    self._clone_genome(winner, generation=generation), req, rng
                )
            if result and result.mutated_genome:
                mutants.append(result.mutated_genome)
            else:
                break

        return self._pop_manager.create_population(
            generation=generation,
            genomes=mutants,
            size=target_count,
            metadata={
                "parent_genome_id": winner.genome_id,
                "parent_fitness": winner.fitness.composite_score if winner.fitness else 0.0,
                "mutation_strategy": "winner_exploitation",
            },
        )

    def evolve_from_parents(
        self,
        parent_a: Genome,
        parent_b: Genome,
        target_count: int = 50,
        generation: int = 1,
    ) -> Population:
        """Generate population by crossing over two parent genomes."""
        offspring: list[Genome] = []

        for i in range(target_count):
            child = self._crossover(parent_a, parent_b, generation)
            req = MutationRequest(
                genome_id=child.genome_id,
                operators=[MutationOperator.POINT_MUTATION],
                mutation_rate=0.1,
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(child, req, rng)
            offspring.append(result.mutated_genome if result and result.mutated_genome else child)

        offspring = self._deduplicate(offspring)

        return self._pop_manager.create_population(
            generation=generation,
            genomes=offspring,
            size=target_count,
            metadata={
                "parent_a": parent_a.genome_id,
                "parent_b": parent_b.genome_id,
                "mutation_strategy": "crossover",
            },
        )

    def evolve_next_generation(
        self,
        current_pop: Population,
        elite_count: int = 5,
        target_count: int = 50,
    ) -> Population:
        """Evolve a population to the next generation using elite selection."""
        next_gen = current_pop.generation + 1

        # Elite selection
        scored = [g for g in current_pop.genomes if g.fitness is not None]
        scored.sort(key=lambda g: g.fitness.composite_score, reverse=True)
        elites = scored[:elite_count]

        mutants: list[Genome] = []
        for elite in elites:
            mutants.append(self._clone_genome(elite, generation=next_gen))

        top_n = min(10, len(scored))
        for i in range(target_count - len(mutants)):
            parent = scored[i % top_n] if scored else elites[0]
            req = MutationRequest(
                genome_id=parent.genome_id,
                operators=[MutationOperator.POINT_MUTATION, MutationOperator.SWAP],
                mutation_rate=0.2,
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(
                    self._clone_genome(parent, generation=next_gen), req, rng
                )
            if result and result.mutated_genome:
                mutants.append(result.mutated_genome)
            else:
                break

        mutants = self._deduplicate(mutants)[:target_count]

        return self._pop_manager.create_population(
            generation=next_gen,
            genomes=mutants,
            size=target_count,
            metadata={
                "parent_population": current_pop.population_id,
                "elite_count": elite_count,
                "mutation_strategy": "elitist_evolution",
            },
        )

    # ── Internal: Mutation Strategies ───────────────────────

    def _generate_single_gene_mutants(
        self, winner: Genome, generation: int
    ) -> list[Genome]:
        """Mutate one gene at a time."""
        mutants: list[Genome] = []
        gene_keys = list(winner.genes.keys())

        for key in gene_keys:
            req = MutationRequest(
                genome_id=winner.genome_id,
                operators=[MutationOperator.POINT_MUTATION],
                target_genes=[key],
                mutation_rate=1.0,  # Always mutate targeted gene
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(
                    self._clone_genome(winner, generation=generation), req, rng
                )
            if result and result.mutated_genome:
                mutants.append(result.mutated_genome)

        return mutants

    def _generate_multi_gene_mutants(
        self, winner: Genome, generation: int, count: int
    ) -> list[Genome]:
        """Apply multiple mutations."""
        mutants: list[Genome] = []
        for _ in range(count):
            req = MutationRequest(
                genome_id=winner.genome_id,
                operators=[MutationOperator.POINT_MUTATION, MutationOperator.SWAP],
                mutation_rate=0.3,
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(
                    self._clone_genome(winner, generation=generation), req, rng
                )
            if result and result.mutated_genome:
                mutants.append(result.mutated_genome)
        return mutants

    def _generate_reset_mutants(
        self, winner: Genome, generation: int, count: int
    ) -> list[Genome]:
        """Random reset: resample genes from pools."""
        mutants: list[Genome] = []
        for _ in range(count):
            req = MutationRequest(
                genome_id=winner.genome_id,
                operators=[MutationOperator.RANDOM_RESET],
                mutation_rate=0.3,
            )
            with RandomContext(seed=self._next_seed()) as rng:
                result = self._gene_engine.mutate(
                    self._clone_genome(winner, generation=generation), req, rng
                )
            if result and result.mutated_genome:
                mutants.append(result.mutated_genome)
        return mutants

    # ── Internal: Helpers ───────────────────────────────────

    @staticmethod
    def _clone_genome(genome: Genome, generation: int) -> Genome:
        """Clone a genome for mutation (preserves original)."""
        cloned = copy.deepcopy(genome)
        cloned.genome_id = f"gen_{str(uuid.uuid4())[:8]}"
        cloned.generation = generation
        cloned.parent_ids = [genome.genome_id] if genome.genome_id else []
        return cloned

    def _next_seed(self) -> int:
        self._mutation_seq += 1
        return self.SEED_BASE + self._mutation_seq

    @staticmethod
    def _crossover(parent_a: Genome, parent_b: Genome, generation: int) -> Genome:
        """Create child by mixing genes from two parents."""
        import random

        child_genes = {}
        all_keys = set(parent_a.genes.keys()) | set(parent_b.genes.keys())

        for key in all_keys:
            if key in parent_a.genes and key in parent_b.genes:
                source = parent_a if random.random() < 0.5 else parent_b
                child_genes[key] = copy.deepcopy(source.genes[key])
            elif key in parent_a.genes:
                child_genes[key] = copy.deepcopy(parent_a.genes[key])
            else:
                child_genes[key] = copy.deepcopy(parent_b.genes[key])

        return Genome(
            name=f"x_{parent_a.name[:8]}_{parent_b.name[:8]}",
            generation=generation,
            genes=child_genes,
            parent_ids=[parent_a.genome_id, parent_b.genome_id],
        )

    @staticmethod
    def _deduplicate(genomes: list[Genome]) -> list[Genome]:
        """Remove genomes with identical gene signatures."""
        seen: set[str] = set()
        unique: list[Genome] = []
        for g in genomes:
            parts = []
            for key in sorted(g.genes.keys()):
                parts.append(f"{key}:{g.genes[key].value}")
            sig = "|".join(parts)
            if sig not in seen:
                seen.add(sig)
                unique.append(g)
        return unique
