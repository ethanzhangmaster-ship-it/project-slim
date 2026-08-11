"""V5.0 EvolutionMemory — evolution history + lineage tracking.

EXTENDS: V4.1 Memory (creative knowledge) → adds evolution-specific memory.

Tracks:
  - Evolution runs (complete missions)
  - Generations (populations over time)
  - Lineage (parent → child genome chains)
  - Mutation records (what changed, when, with what result)
  - Fitness history (trends across generations)
  - Snapshots (for rollback)
  - Event log (full evolution event history)

Integrates with V4.4 EventBus for event-driven communication.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import (EvolutionSnapshot, EvolutionEvent, EvolutionRun,
                       Genome, Population, EvolutionPhase)


class EvolutionMemory:
    """Evolution-specific memory store extending V4.1 Memory."""

    def __init__(self) -> None:
        self._snapshots: dict[str, EvolutionSnapshot] = {}  # snapshot_id → snapshot
        self._snapshots_by_run: dict[str, list[str]] = {}   # run_id → [snapshot_ids]
        self._mutation_records: list[dict[str, Any]] = []
        self._lineage_graph: dict[str, list[str]] = {}      # parent_id → [child_ids]
        self._event_log: list[EvolutionEvent] = []
        self._run_history: dict[str, list[dict[str, Any]]] = {}  # run_id → events

    # ── Snapshots ───────────────────────────────────────────

    def snapshot(self, run_id: str, population: Population,
                 controller_phase: EvolutionPhase,
                 metadata: dict[str, Any] | None = None) -> EvolutionSnapshot:
        """Create an evolution snapshot for rollback.

        Args:
            run_id: Evolution run ID.
            population: Current population state.
            controller_phase: Current controller phase.
            metadata: Additional metadata.

        Returns:
            EvolutionSnapshot.
        """
        snapshot = EvolutionSnapshot(
            generation=population.generation,
            population_id=population.population_id,
            population_size=len(population.genomes),
            best_genome_id=population.get_best().genome_id if population.get_best() else "",
            best_fitness=population.best_fitness,
            avg_fitness=population.avg_fitness,
            diversity=population.diversity_score,
            controller_phase=controller_phase,
            metadata=metadata or {},
        )

        self._snapshots[snapshot.snapshot_id] = snapshot

        if run_id not in self._snapshots_by_run:
            self._snapshots_by_run[run_id] = []
        self._snapshots_by_run[run_id].append(snapshot.snapshot_id)

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> EvolutionSnapshot | None:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_latest_snapshot(self, run_id: str) -> EvolutionSnapshot | None:
        """Get the most recent snapshot for a run."""
        ids = self._snapshots_by_run.get(run_id, [])
        if not ids:
            return None
        return self._snapshots.get(ids[-1])

    def get_snapshots_by_run(self, run_id: str) -> list[EvolutionSnapshot]:
        """Get all snapshots for a run, ordered by time."""
        ids = self._snapshots_by_run.get(run_id, [])
        return [self._snapshots[sid] for sid in ids if sid in self._snapshots]

    def get_snapshots_by_generation(self, generation: int) -> list[EvolutionSnapshot]:
        """Get all snapshots at a specific generation."""
        return [s for s in self._snapshots.values() if s.generation == generation]

    # ── Mutation Records ────────────────────────────────────

    def record_mutation(self, genome_id: str, parent_id: str,
                        gene_type: str, old_value: str, new_value: str,
                        operator: str, generation: int,
                        fitness_before: float = 0.0,
                        fitness_after: float = 0.0) -> None:
        """Record a mutation event.

        Args:
            genome_id: Mutated genome ID.
            parent_id: Parent genome ID.
            gene_type: Which gene was mutated.
            old_value: Gene value before mutation.
            new_value: Gene value after mutation.
            operator: Mutation operator used.
            generation: Generation number.
            fitness_before: Fitness before mutation.
            fitness_after: Fitness after mutation.
        """
        record = {
            "genome_id": genome_id,
            "parent_id": parent_id,
            "gene_type": gene_type,
            "old_value": old_value,
            "new_value": new_value,
            "operator": operator,
            "generation": generation,
            "fitness_before": fitness_before,
            "fitness_after": fitness_after,
            "fitness_delta": round(fitness_after - fitness_before, 4),
            "timestamp": time.time(),
        }
        self._mutation_records.append(record)

        # Track lineage
        if parent_id not in self._lineage_graph:
            self._lineage_graph[parent_id] = []
        self._lineage_graph[parent_id].append(genome_id)

    def get_mutations_by_genome(self, genome_id: str) -> list[dict[str, Any]]:
        """Get all mutations for a genome."""
        return [m for m in self._mutation_records if m["genome_id"] == genome_id]

    def get_mutations_by_generation(self, generation: int) -> list[dict[str, Any]]:
        """Get all mutations in a generation."""
        return [m for m in self._mutation_records if m["generation"] == generation]

    def get_beneficial_mutations(self, min_improvement: float = 0.01) -> list[dict[str, Any]]:
        """Get mutations that improved fitness."""
        return [m for m in self._mutation_records if m["fitness_delta"] > min_improvement]

    def get_harmful_mutations(self) -> list[dict[str, Any]]:
        """Get mutations that decreased fitness."""
        return [m for m in self._mutation_records if m["fitness_delta"] < 0]

    def get_best_mutation_operators(self, top_n: int = 5) -> list[tuple[str, float]]:
        """Get the most effective mutation operators by average improvement."""
        operator_stats: dict[str, list[float]] = {}
        for m in self._mutation_records:
            op = m["operator"]
            if op not in operator_stats:
                operator_stats[op] = []
            operator_stats[op].append(m["fitness_delta"])

        averages = [(op, sum(deltas) / len(deltas)) for op, deltas in operator_stats.items()]
        averages.sort(key=lambda x: x[1], reverse=True)
        return averages[:top_n]

    # ── Lineage ─────────────────────────────────────────────

    def get_lineage(self, genome_id: str) -> list[str]:
        """Get the lineage chain of a genome (ancestors in order)."""
        # This is a backward lookup — we need genome_manager for full lineage
        # Here we just return what we know from mutation records
        chain = [genome_id]
        current = genome_id
        for _ in range(50):  # Safety limit
            parent = None
            for m in self._mutation_records:
                if m["genome_id"] == current:
                    parent = m["parent_id"]
                    break
            if parent is None:
                break
            chain.insert(0, parent)
            current = parent
        return chain

    def get_children(self, genome_id: str) -> list[str]:
        """Get all child genomes of a parent."""
        return self._lineage_graph.get(genome_id, [])

    def get_descendants(self, genome_id: str, max_depth: int = 10) -> list[str]:
        """Get all descendants (recursive) of a genome."""
        descendants = []
        queue = [genome_id]
        depth = 0
        while queue and depth < max_depth:
            current = queue.pop(0)
            children = self._lineage_graph.get(current, [])
            descendants.extend(children)
            queue.extend(children)
            depth += 1
        return descendants

    # ── Event Log ───────────────────────────────────────────

    def log_event(self, event: EvolutionEvent) -> None:
        """Log an evolution event."""
        self._event_log.append(event)

        # Also index by run
        if event.run_id:
            if event.run_id not in self._run_history:
                self._run_history[event.run_id] = []
            self._run_history[event.run_id].append(event.to_dict())

    def get_events(self, event_type: str | None = None,
                   run_id: str | None = None,
                   limit: int = 100) -> list[EvolutionEvent]:
        """Get events with optional filtering."""
        events = self._event_log
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if run_id:
            events = [e for e in events if e.run_id == run_id]
        return events[-limit:]

    def get_run_history(self, run_id: str) -> list[dict[str, Any]]:
        """Get complete event history for a run."""
        return self._run_history.get(run_id, [])

    # ── Stats ───────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get evolution memory statistics."""
        beneficial = len(self.get_beneficial_mutations())
        harmful = len(self.get_harmful_mutations())

        return {
            "total_snapshots": len(self._snapshots),
            "total_mutations": len(self._mutation_records),
            "beneficial_mutations": beneficial,
            "harmful_mutations": harmful,
            "neutral_mutations": len(self._mutation_records) - beneficial - harmful,
            "total_events": len(self._event_log),
            "lineage_trees": len(self._lineage_graph),
            "best_operators": [
                {"operator": op, "avg_improvement": round(avg, 4)}
                for op, avg in self.get_best_mutation_operators(3)
            ],
        }

    def get_mutation_stats(self) -> dict[str, Any]:
        """Get mutation-specific statistics."""
        by_gene: dict[str, dict[str, Any]] = {}
        for m in self._mutation_records:
            gt = m["gene_type"]
            if gt not in by_gene:
                by_gene[gt] = {"count": 0, "total_delta": 0.0, "beneficial": 0, "harmful": 0}
            by_gene[gt]["count"] += 1
            by_gene[gt]["total_delta"] += m["fitness_delta"]
            if m["fitness_delta"] > 0:
                by_gene[gt]["beneficial"] += 1
            elif m["fitness_delta"] < 0:
                by_gene[gt]["harmful"] += 1

        return {
            "by_gene_type": {
                gt: {
                    "count": s["count"],
                    "avg_delta": round(s["total_delta"] / max(1, s["count"]), 4),
                    "beneficial": s["beneficial"],
                    "harmful": s["harmful"],
                }
                for gt, s in by_gene.items()
            },
            "total": len(self._mutation_records),
        }