"""V5.0 PopulationManager — generation management + elite selection.

Manages populations (generations of genomes) for genetic algorithm evolution.

Core operations:
  - Create population (initial or from previous gen)
  - Elite selection (top N genomes survive)
  - Diversity calculation
  - Convergence detection
  - Extinction risk assessment
  - Population archiving
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import (Population, Species, Genome, Fitness, EvolutionEvent,
                       EvolutionPhase, DEFAULT_EVOLUTION_CONFIG)


class PopulationManager:
    """Manages evolutionary populations (generations)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or DEFAULT_EVOLUTION_CONFIG
        self._pop_config = cfg.get("population", {})
        self._default_size = self._pop_config.get("default_size", 100)
        self._elite_count = self._pop_config.get("elite_count", 10)
        self._min_diversity = self._pop_config.get("min_diversity", 0.05)
        self._max_convergence = self._pop_config.get("max_convergence", 0.95)
        self._extinction_threshold = self._pop_config.get("extinction_threshold", 0.02)

        self._populations: dict[str, Population] = {}  # population_id → Population
        self._by_generation: dict[int, str] = {}        # generation → population_id
        self._event_handlers: list[Any] = []

    def create_population(self, generation: int,
                          genomes: list[Genome] | None = None,
                          size: int | None = None,
                          elite_count: int | None = None,
                          metadata: dict[str, Any] | None = None) -> Population:
        """Create a new population for a generation.

        Args:
            generation: Generation number (0 = seed).
            genomes: Initial genomes (optional).
            size: Target population size.
            metadata: Additional metadata.

        Returns:
            The created Population.
        """
        pop = Population(
            generation=generation,
            genomes=genomes or [],
            size=size or self._default_size,
            elite_count=elite_count if elite_count is not None else self._elite_count,
            metadata=metadata or {},
        )

        if genomes:
            self._recalculate_stats(pop)

        self._populations[pop.population_id] = pop
        self._by_generation[generation] = pop.population_id

        self._emit("POPULATION_CREATED", pop.population_id, generation=generation)
        return pop

    def get_population(self, population_id: str) -> Population | None:
        """Get a population by ID."""
        return self._populations.get(population_id)

    def get_by_generation(self, generation: int) -> Population | None:
        """Get a population by generation number."""
        pop_id = self._by_generation.get(generation)
        return self._populations.get(pop_id) if pop_id else None

    def get_current_generation(self) -> int:
        """Get the highest generation number."""
        return max(self._by_generation.keys()) if self._by_generation else 0

    def add_genome(self, population_id: str, genome: Genome) -> bool:
        """Add a genome to a population."""
        pop = self._populations.get(population_id)
        if pop is None:
            return False
        pop.genomes.append(genome)
        self._recalculate_stats(pop)
        return True

    def add_genomes(self, population_id: str, genomes: list[Genome]) -> int:
        """Add multiple genomes to a population."""
        pop = self._populations.get(population_id)
        if pop is None:
            return 0
        pop.genomes.extend(genomes)
        self._recalculate_stats(pop)
        return len(genomes)

    # ── Elite Selection ─────────────────────────────────────

    def select_elites(self, population_id: str) -> list[Genome]:
        """Select elite genomes (top N by fitness) for next generation.

        Returns:
            List of elite genomes (sorted by fitness, descending).
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return []

        elites = pop.get_elites()
        self._emit("ELITE_SELECTED", population_id, generation=pop.generation)
        return elites

    def create_next_generation(self, population_id: str,
                               elites: list[Genome] | None = None) -> Population | None:
        """Create the next generation population from current elites.

        Args:
            population_id: Current population.
            elites: Optional pre-selected elites.

        Returns:
            New Population for the next generation.
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return None

        if elites is None:
            elites = self.select_elites(population_id)

        next_gen = pop.generation + 1
        new_pop = self.create_population(
            generation=next_gen,
            genomes=elites,  # Elites carry over
            size=pop.size,
            metadata={"parent_population_id": population_id},
        )

        return new_pop

    # ── Diversity & Convergence ─────────────────────────────

    def calculate_diversity(self, population_id: str) -> float:
        """Calculate population diversity (0-1).

        Based on gene value uniqueness across all genomes, per gene type.
        0.0 = all genomes have identical genes.
        1.0 = all genomes have completely different genes.

        Formula: For each gene type, diversity = (unique_values - 1) / (n_genomes - 1).
        Averaged across all gene types.
        """
        pop = self._populations.get(population_id)
        if pop is None or len(pop.genomes) < 2:
            return 0.0

        n = len(pop.genomes)
        if n <= 1:
            return 0.0

        gene_type_values: dict[str, set[str]] = {}

        for genome in pop.genomes:
            for gene_type, gene in genome.genes.items():
                if gene_type not in gene_type_values:
                    gene_type_values[gene_type] = set()
                gene_type_values[gene_type].add(gene.value)

        if not gene_type_values:
            return 0.0

        # Per gene type: (unique - 1) / (n - 1) → 0 = identical, 1 = all different
        diversities = []
        for values in gene_type_values.values():
            div = (len(values) - 1) / (n - 1) if n > 1 else 0.0
            diversities.append(div)

        diversity = sum(diversities) / len(diversities)
        pop.diversity_score = diversity
        return diversity

    def calculate_convergence(self, population_id: str) -> float:
        """Calculate convergence score (0-1).

        1.0 = population has fully converged (all similar).
        Inverse of diversity.
        """
        diversity = self.calculate_diversity(population_id)
        pop = self._populations.get(population_id)
        if pop:
            pop.convergence_score = 1.0 - diversity
        return 1.0 - diversity

    def is_converged(self, population_id: str) -> bool:
        """Check if population has converged."""
        pop = self._populations.get(population_id)
        if pop is None:
            return False
        return pop.convergence_score >= self._max_convergence

    def is_diversity_low(self, population_id: str) -> bool:
        """Check if diversity is below minimum threshold."""
        pop = self._populations.get(population_id)
        if pop is None:
            return False
        return pop.diversity_score <= self._min_diversity

    # ── Extinction Detection ────────────────────────────────

    def detect_extinction_risk(self, population_id: str) -> float:
        """Calculate extinction risk (0-1).

        Factors:
          - Low avg fitness
          - Low diversity
          - Declining trend
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return 0.0

        risk = 0.0

        # Low fitness factor
        if pop.avg_fitness < self._extinction_threshold:
            risk += 0.5

        # Low diversity factor
        if pop.diversity_score < self._min_diversity * 2:
            risk += 0.3

        # Declining trend factor
        prev_pop = self.get_by_generation(pop.generation - 1)
        if prev_pop and pop.avg_fitness < prev_pop.avg_fitness:
            risk += 0.2

        pop.extinction_risk = min(risk, 1.0)

        if pop.extinction_risk > 0.8:
            self._emit("EXTINCTION_DETECTED", population_id, generation=pop.generation)

        return pop.extinction_risk

    def is_extinct(self, population_id: str) -> bool:
        """Check if population is extinct."""
        pop = self._populations.get(population_id)
        if pop is None:
            return False
        return pop.extinction_risk >= 0.9

    # ── Stats ───────────────────────────────────────────────

    def _recalculate_stats(self, pop: Population) -> None:
        """Recalculate population statistics."""
        scored = [g for g in pop.genomes if g.fitness is not None]
        if scored:
            pop.best_fitness = max(g.fitness.composite_score for g in scored)
            pop.avg_fitness = sum(g.fitness.composite_score for g in scored) / len(scored)
            sorted_scores = sorted(g.fitness.composite_score for g in scored)
            mid = len(sorted_scores) // 2
            pop.median_fitness = sorted_scores[mid]

        self.calculate_diversity(pop.population_id)
        self.calculate_convergence(pop.population_id)
        self.calculate_novelty(pop.population_id)
        self.calculate_survival_rate(pop.population_id)
        self.detect_extinction_risk(pop.population_id)

    # ── Novelty & Survival ──────────────────────────────────

    def calculate_novelty(self, population_id: str) -> float:
        """Calculate novelty score (0-1) vs previous generation.

        1.0 = all gene values are new (never seen in previous gens).
        0.0 = all gene values already existed in previous gens.

        Used by Evolution Controller to adjust mutation rate:
          low novelty → increase mutation rate
          high novelty → reduce mutation rate
        """
        pop = self._populations.get(population_id)
        if pop is None or not pop.genomes:
            return 0.0

        prev_pop = self.get_by_generation(pop.generation - 1)
        if prev_pop is None:
            pop.novelty_score = 1.0  # First generation: all novel
            return 1.0

        # Collect all gene values from previous generation
        prev_values: dict[str, set[str]] = {}
        for genome in prev_pop.genomes:
            for gene_type, gene in genome.genes.items():
                if gene_type not in prev_values:
                    prev_values[gene_type] = set()
                prev_values[gene_type].add(gene.value)

        # Count novel gene values in current population
        total_genes = 0
        novel_genes = 0
        for genome in pop.genomes:
            for gene_type, gene in genome.genes.items():
                total_genes += 1
                prev_set = prev_values.get(gene_type, set())
                if gene.value not in prev_set:
                    novel_genes += 1

        novelty = novel_genes / max(1, total_genes)
        pop.novelty_score = novelty
        return novelty

    def calculate_survival_rate(self, population_id: str) -> float:
        """Calculate survival rate (0-1) from previous generation.

        1.0 = all genomes from previous gen survived to current gen.
        0.0 = no genomes from previous gen survived.

        Used by Evolution Controller to assess extinction risk
        and adjust elite preservation.
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return 0.0

        prev_pop = self.get_by_generation(pop.generation - 1)
        if prev_pop is None or not prev_pop.genomes:
            pop.survival_rate = 1.0  # First generation
            return 1.0

        # Count genomes that have parent_ids pointing to previous gen
        prev_genome_ids = {g.genome_id for g in prev_pop.genomes}
        survived = 0
        for genome in pop.genomes:
            if any(pid in prev_genome_ids for pid in genome.parent_ids):
                survived += 1

        total_prev = len(prev_pop.genomes)
        survival = survived / max(1, total_prev)
        pop.survival_rate = survival
        return survival

    def get_stats(self, population_id: str) -> dict[str, Any] | None:
        """Get population statistics."""
        pop = self._populations.get(population_id)
        if pop is None:
            return None
        return pop.to_dict()

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all populations."""
        return {
            "total_populations": len(self._populations),
            "generations": list(sorted(self._by_generation.keys())),
            "current_gen": self.get_current_generation(),
            "populations": {pid: p.to_dict() for pid, p in self._populations.items()},
        }

    def archive_population(self, population_id: str) -> bool:
        """Archive a population (mark as inactive)."""
        pop = self._populations.get(population_id)
        if pop is None:
            return False
        pop.status = "archived"
        self._emit("CONTROLLER_DECISION", population_id, generation=pop.generation)
        return True

    # ── Species Management ───────────────────────────────────

    def create_species(self, population_id: str, name: str,
                       gameplay_type: str = "",
                       genomes: list[Genome] | None = None) -> Species | None:
        """Create a new species within a population.

        Species group genomes by gameplay type (merge, sort, simulation, etc.)
        to enable parallel evolution tracks within one generation.
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return None

        species = Species(
            name=name,
            gameplay_type=gameplay_type,
            genomes=genomes or [],
        )
        pop.species[species.species_id] = species

        if genomes:
            for g in genomes:
                pop.genomes.append(g)
            self._recalculate_species_stats(species)

        return species

    def add_to_species(self, population_id: str, species_id: str,
                       genome: Genome) -> bool:
        """Add a genome to a species."""
        pop = self._populations.get(population_id)
        if pop is None or species_id not in pop.species:
            return False

        species = pop.species[species_id]
        species.genomes.append(genome)
        self._recalculate_species_stats(species)
        return True

    def get_species(self, population_id: str,
                    species_id: str) -> Species | None:
        """Get a species by ID."""
        pop = self._populations.get(population_id)
        if pop is None:
            return None
        return pop.species.get(species_id)

    def get_all_species(self, population_id: str) -> list[Species]:
        """Get all species in a population."""
        pop = self._populations.get(population_id)
        if pop is None:
            return []
        return list(pop.species.values())

    def classify_into_species(self, population_id: str,
                              species_key: str = "gameplay") -> dict[str, Species]:
        """Auto-classify genomes into species by a gene key.

        For example, if species_key="gameplay", all genomes with gameplay="merge"
        go into one species, gameplay="sort" into another, etc.
        """
        pop = self._populations.get(population_id)
        if pop is None:
            return {}

        pop.species.clear()
        for genome in pop.genomes:
            gene = genome.genes.get(species_key)
            classification = gene.value if gene else "unknown"

            # Find or create species
            species_name = f"{classification}_{pop.generation}"
            existing = None
            for s in pop.species.values():
                if s.name == species_name:
                    existing = s
                    break

            if existing is None:
                existing = Species(
                    name=species_name,
                    gameplay_type=classification,
                )
                pop.species[existing.species_id] = existing

            existing.genomes.append(genome)

        for s in pop.species.values():
            self._recalculate_species_stats(s)

        return pop.species

    def _recalculate_species_stats(self, species: Species) -> None:
        """Recalculate species-level statistics."""
        scored = [g for g in species.genomes if g.fitness is not None]
        if scored:
            species.best_fitness = max(g.fitness.composite_score for g in scored)
            species.avg_fitness = sum(g.fitness.composite_score for g in scored) / len(scored)
        species.size = len(species.genomes)
        species.diversity_score = self._calc_species_diversity(species)

    def _calc_species_diversity(self, species: Species) -> float:
        """Calculate diversity within a species."""
        if len(species.genomes) < 2:
            return 0.0

        gene_values: dict[str, set[str]] = {}
        for genome in species.genomes:
            for gene_type, gene in genome.genes.items():
                if gene_type not in gene_values:
                    gene_values[gene_type] = set()
                gene_values[gene_type].add(gene.value)

        if not gene_values:
            return 0.0

        n = len(species.genomes)
        diversities = []
        for values in gene_values.values():
            div = (len(values) - 1) / (n - 1) if n > 1 else 0.0
            diversities.append(div)

        return sum(diversities) / len(diversities) if diversities else 0.0

    # ── Events ──────────────────────────────────────────────

    def on_event(self, handler: Any) -> None:
        self._event_handlers.append(handler)

    def _emit(self, event_type: str, entity_id: str,
              generation: int = 0, actor: str = "") -> None:
        event = EvolutionEvent(
            event_type=event_type,
            entity_id=entity_id,
            generation=generation,
            source="population_manager",
            actor=actor or "population_manager",
        )
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass