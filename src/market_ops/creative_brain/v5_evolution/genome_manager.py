"""V5.0 GenomeManager — genome CRUD + fitness history.

EXTENDS: V4.0 Knowledge (Pattern) — uses Winner DNA patterns as seed genomes.

Core operations:
  - Create genome from Winner DNA (V4.0 Pattern → V5.0 Genome)
  - Track fitness history across generations
  - Clone genomes for mutation
  - Query genomes by fitness, generation, tags
"""

from __future__ import annotations

import uuid
import time
from typing import Any

from .schemas import (Genome, Gene, GeneType, Fitness,
                       MutationOperator, EvolutionEvent)


class GenomeManager:
    """Genome registry — CRUD operations for evolvable genomes."""

    def __init__(self) -> None:
        self._genomes: dict[str, Genome] = {}       # genome_id → Genome
        self._by_generation: dict[int, set[str]] = {}  # generation → {genome_ids}
        self._by_tag: dict[str, set[str]] = {}       # tag → {genome_ids}
        self._event_handlers: list[Any] = []          # Callbacks for EvolutionEvents

    # ── CRUD ───────────────────────────────────────────────

    def create(self, name: str, generation: int = 0,
               genes: list[Gene] | None = None,
               parent_ids: list[str] | None = None,
               tags: list[str] | None = None,
               metadata: dict[str, Any] | None = None) -> Genome:
        """Create a new genome.

        Args:
            name: Human-readable name.
            generation: Generation number (0 = seed).
            genes: List of Gene objects.
            parent_ids: Parent genome IDs (for lineage).
            tags: Tags for discovery.
            metadata: Additional metadata.

        Returns:
            The created Genome.
        """
        genome = Genome(
            name=name,
            generation=generation,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        )

        # Register genes
        if genes:
            for gene in genes:
                genome.genes[gene.gene_type.value] = gene

        # Store
        self._genomes[genome.genome_id] = genome

        # Index by generation
        if generation not in self._by_generation:
            self._by_generation[generation] = set()
        self._by_generation[generation].add(genome.genome_id)

        # Index by tag
        for tag in (tags or []):
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(genome.genome_id)

        self._emit("GENOME_CREATED", genome.genome_id, generation=genome.generation)
        return genome

    def create_from_winner_dna(self, name: str, winner_dna: dict[str, Any],
                               generation: int = 0) -> Genome:
        """Create a genome from V4.0 Winner DNA.

        Converts V4 analysis output to V5 evolvable genome.
        Winner DNA: {"hook": "rescue", "character": "dragon", ...}
        → Genome with evolvable genes.
        """
        genes = []
        for key, value in winner_dna.items():
            if isinstance(value, str):
                gene_type = self._infer_gene_type(key)
                gene = Gene(
                    gene_type=gene_type,
                    value=value,
                    mutation_pool=[value],  # Start with current value
                    mutation_probability=0.1,
                    mutation_cost=0.1,
                    mutation_risk=0.1,
                    confidence=0.5,
                    source="winner_dna",
                )
                genes.append(gene)

        return self.create(name=name, generation=generation, genes=genes)

    def get(self, genome_id: str) -> Genome | None:
        """Get a genome by ID."""
        return self._genomes.get(genome_id)

    def update(self, genome: Genome) -> bool:
        """Update an existing genome (e.g., after fitness update)."""
        if genome.genome_id not in self._genomes:
            return False
        self._genomes[genome.genome_id] = genome
        return True

    def delete(self, genome_id: str) -> bool:
        """Delete a genome."""
        if genome_id not in self._genomes:
            return False
        genome = self._genomes.pop(genome_id)
        # Remove from indices
        gen_set = self._by_generation.get(genome.generation, set())
        gen_set.discard(genome_id)
        return True

    def clone(self, genome_id: str, new_name: str = "",
              new_generation: int = 0) -> Genome | None:
        """Clone a genome for mutation (deep copy)."""
        original = self._genomes.get(genome_id)
        if original is None:
            return None

        cloned = original.clone()
        cloned.genome_id = str(uuid.uuid4())[:12]  # Force new ID
        cloned.name = new_name or f"{original.name}_clone"
        cloned.generation = new_generation
        cloned.parent_ids = [genome_id]
        cloned.fitness = None
        cloned.fitness_history = list(original.fitness_history)  # Copy history

        # Re-register with new ID
        self._genomes[cloned.genome_id] = cloned
        if new_generation not in self._by_generation:
            self._by_generation[new_generation] = set()
        self._by_generation[new_generation].add(cloned.genome_id)

        self._emit("GENOME_CREATED", cloned.genome_id, generation=cloned.generation)
        return cloned

    # ── Fitness ─────────────────────────────────────────────

    def update_fitness(self, genome_id: str, fitness: Fitness) -> bool:
        """Update a genome's fitness score.

        Appends to fitness_history for trend tracking.
        """
        genome = self._genomes.get(genome_id)
        if genome is None:
            return False

        # Archive current fitness to history
        if genome.fitness is not None:
            genome.fitness_history.append(genome.fitness.composite_score)

        genome.fitness = fitness
        self._emit("FITNESS_UPDATED", genome_id, generation=genome.generation)
        return True

    def update_fitness_batch(self, fitness_map: dict[str, Fitness]) -> int:
        """Batch update fitness for multiple genomes.

        Returns:
            Number of genomes updated.
        """
        count = 0
        for genome_id, fitness in fitness_map.items():
            if self.update_fitness(genome_id, fitness):
                count += 1
        return count

    # ── Query ───────────────────────────────────────────────

    def get_by_generation(self, generation: int) -> list[Genome]:
        """Get all genomes in a generation."""
        ids = self._by_generation.get(generation, set())
        return [self._genomes[gid] for gid in ids if gid in self._genomes]

    def get_by_tag(self, tag: str) -> list[Genome]:
        """Get genomes by tag."""
        ids = self._by_tag.get(tag, set())
        return [self._genomes[gid] for gid in ids if gid in self._genomes]

    def get_top_by_fitness(self, n: int = 10,
                           generation: int | None = None) -> list[Genome]:
        """Get top N genomes by fitness score."""
        if generation is not None:
            genomes = self.get_by_generation(generation)
        else:
            genomes = list(self._genomes.values())

        scored = [g for g in genomes if g.fitness is not None]
        scored.sort(key=lambda g: g.fitness.composite_score, reverse=True)
        return scored[:n]

    def get_improving_genomes(self, min_improvement: float = 0.02) -> list[Genome]:
        """Get genomes with improving fitness trend."""
        result = []
        for g in self._genomes.values():
            if g.fitness_trend == "improving":
                result.append(g)
        return result

    def get_declining_genomes(self) -> list[Genome]:
        """Get genomes with declining fitness trend."""
        return [g for g in self._genomes.values() if g.fitness_trend == "declining"]

    def get_lineage(self, genome_id: str) -> list[Genome]:
        """Get the full lineage chain (parents → this genome)."""
        lineage = []
        current = self._genomes.get(genome_id)
        while current:
            lineage.append(current)
            if current.parent_ids:
                current = self._genomes.get(current.parent_ids[0])
            else:
                break
        return list(reversed(lineage))

    # ── Stats ───────────────────────────────────────────────

    def get_count(self) -> int:
        """Total genomes registered."""
        return len(self._genomes)

    def get_counts_by_generation(self) -> dict[int, int]:
        """Genome count per generation."""
        return {g: len(ids) for g, ids in self._by_generation.items()}

    def get_stats(self) -> dict[str, Any]:
        """Get genome statistics."""
        scored = [g for g in self._genomes.values() if g.fitness is not None]
        avg_fitness = (
            sum(g.fitness.composite_score for g in scored) / len(scored)
            if scored else 0.0
        )

        return {
            "total_genomes": len(self._genomes),
            "generations": len(self._by_generation),
            "with_fitness": len(scored),
            "avg_fitness": round(avg_fitness, 4),
            "improving": len(self.get_improving_genomes()),
            "declining": len(self.get_declining_genomes()),
            "by_generation": self.get_counts_by_generation(),
        }

    # ── Events ──────────────────────────────────────────────

    def on_event(self, handler: Any) -> None:
        """Register an event handler (receives EvolutionEvent)."""
        self._event_handlers.append(handler)

    def _emit(self, event_type: str, entity_id: str,
              generation: int = 0, actor: str = "",
              confidence: float = 1.0) -> None:
        """Emit an EvolutionEvent to all handlers."""
        event = EvolutionEvent(
            event_type=event_type,
            entity_id=entity_id,
            generation=generation,
            source="genome_manager",
            actor=actor or "genome_manager",
            confidence=confidence,
        )
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def _infer_gene_type(self, key: str) -> GeneType:
        """Infer GeneType from Winner DNA key."""
        key_lower = key.lower()
        if key_lower in ("hook", "opening"):
            return GeneType.HOOK
        if key_lower in ("character", "protagonist", "hero"):
            return GeneType.CHARACTER
        if key_lower in ("emotion", "feeling", "mood"):
            return GeneType.EMOTION
        if key_lower in ("reward", "prize", "outcome"):
            return GeneType.REWARD
        if key_lower in ("gameplay", "mechanic", "mechanism"):
            return GeneType.GAMEPLAY
        if key_lower in ("visual", "color", "style", "camera"):
            return GeneType.VISUAL
        if key_lower in ("story", "narrative", "plot"):
            return GeneType.STORY
        if key_lower in ("pacing", "tempo", "speed"):
            return GeneType.PACING
        return GeneType.HOOK