"""V5.0 EvolutionRunManager — cross-lifecycle evolution task management.

Manages concurrent EvolutionRuns:
  Run A: "Find next Merge Puzzle opportunity" → 12 gens, winner genome_0831
  Run B: "Explore Sort Puzzle space" → 8 gens, winner genome_1204

Each run is a complete evolution mission with its own lifecycle.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import EvolutionRun, EvolutionPhase


class EvolutionRunManager:
    """Manages multiple concurrent evolution runs."""

    def __init__(self) -> None:
        self._runs: dict[str, EvolutionRun] = {}  # run_id → EvolutionRun
        self._active_runs: set[str] = set()
        self._run_history: list[dict[str, Any]] = []

    def create_run(self, objective: str, category: str = "",
                   max_generations: int = 100,
                   tags: list[str] | None = None,
                   metadata: dict[str, Any] | None = None) -> EvolutionRun:
        """Create a new evolution run.

        Args:
            objective: "Find next Merge Puzzle opportunity"
            category: "merge_puzzle", "sort_puzzle", etc.
            max_generations: Max generations before forced stop.
            tags: Optional tags for filtering.
            metadata: Additional metadata.

        Returns:
            The created EvolutionRun.
        """
        run = EvolutionRun(
            objective=objective,
            category=category,
            max_generations=max_generations,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._runs[run.run_id] = run
        self._active_runs.add(run.run_id)
        self._log("created", run.run_id)
        return run

    def get_run(self, run_id: str) -> EvolutionRun | None:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def get_active_runs(self) -> list[EvolutionRun]:
        """Get all active (non-terminal) runs."""
        return [self._runs[rid] for rid in self._active_runs if rid in self._runs]

    def get_runs_by_category(self, category: str) -> list[EvolutionRun]:
        """Get all runs for a category."""
        return [r for r in self._runs.values() if r.category == category]

    def get_runs_by_tag(self, tag: str) -> list[EvolutionRun]:
        """Get all runs with a specific tag."""
        return [r for r in self._runs.values() if tag in r.tags]

    def update_phase(self, run_id: str, phase: EvolutionPhase) -> bool:
        """Update a run's evolution phase."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.phase = phase
        self._log("phase_updated", run_id, {"phase": phase.value})
        return True

    def advance_generation(self, run_id: str) -> bool:
        """Advance to the next generation."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.current_generation += 1
        if run.current_generation >= run.max_generations:
            self._complete_run(run_id)
        self._log("generation_advanced", run_id, {"gen": run.current_generation})
        return True

    def set_winner(self, run_id: str, genome_id: str) -> bool:
        """Set the winner genome for a run."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.winner_genome_id = genome_id
        self._log("winner_set", run_id, {"winner": genome_id})
        return True

    def record_genome(self, run_id: str, count: int = 1) -> bool:
        """Record genomes created in this run."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.total_genomes_created += count
        return True

    def record_experiment(self, run_id: str, budget: float = 0.0) -> bool:
        """Record an experiment and its budget."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.total_experiments_run += 1
        run.total_budget_spent += budget
        return True

    def complete_run(self, run_id: str) -> bool:
        """Mark a run as completed."""
        return self._complete_run(run_id)

    def fail_run(self, run_id: str, reason: str = "") -> bool:
        """Mark a run as failed."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.status = "failed"
        run.ended_at = time.time()
        self._active_runs.discard(run_id)
        self._log("failed", run_id, {"reason": reason})
        return True

    def archive_run(self, run_id: str) -> bool:
        """Archive a completed run."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.status = "archived"
        self._active_runs.discard(run_id)
        self._log("archived", run_id)
        return True

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all runs."""
        active = len(self._active_runs)
        total = len(self._runs)
        return {
            "total_runs": total,
            "active_runs": active,
            "completed": total - active,
            "by_category": self._get_category_counts(),
            "by_status": self._get_status_counts(),
            "total_genomes": sum(r.total_genomes_created for r in self._runs.values()),
            "total_experiments": sum(r.total_experiments_run for r in self._runs.values()),
            "total_budget": round(
                sum(r.total_budget_spent for r in self._runs.values()), 2
            ),
        }

    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs as dicts."""
        return [r.to_dict() for r in self._runs.values()]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get run event history."""
        return self._run_history[-limit:]

    def _complete_run(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        run.status = "completed"
        run.ended_at = time.time()
        self._active_runs.discard(run_id)
        self._log("completed", run_id)
        return True

    def _get_category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._runs.values():
            cat = r.category or "uncategorized"
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _get_status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._runs.values():
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    def _log(self, action: str, run_id: str,
             extra: dict[str, Any] | None = None) -> None:
        self._run_history.append({
            "action": action,
            "run_id": run_id,
            "timestamp": time.time(),
            **(extra or {}),
        })