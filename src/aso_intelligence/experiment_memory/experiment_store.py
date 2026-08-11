"""
E16.6.4 — ASO Experiment Store (append-only JSONL).

Mirrors E13.4 Growth Memory's store shape: append-only JSONL, bad-line
tolerant, living under ``data/aso`` alongside the other ASO stores.

Three files:
  * ``experiments.jsonl`` — every ASO experiment (what was changed)
  * ``results.jsonl``     — every experiment's measured outcome
  * ``patterns.jsonl``    — mined, reusable ASO patterns

Interface (per spec):
  * ``record(experiment)``
  * ``record_result(result)``
  * ``history(game_id)``
  * ``query_patterns(condition)``
Plus ``record_pattern`` / ``load_*`` used by the miner and retriever.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOExperiment,
    ASOExperimentResult,
    ASOPattern,
)


DEFAULT_BASE_DIR = "data/aso"
EXPERIMENTS_FILE = "experiments.jsonl"
RESULTS_FILE = "results.jsonl"
PATTERNS_FILE = "patterns.jsonl"


class ASOExperimentStore:
    """Append-only JSONL store for ASO experiments, results and patterns."""

    def __init__(
        self,
        base_dir: str = DEFAULT_BASE_DIR,
        experiments_file: str = EXPERIMENTS_FILE,
        results_file: str = RESULTS_FILE,
        patterns_file: str = PATTERNS_FILE,
    ):
        self.base_dir = base_dir
        self.experiments_file = experiments_file
        self.results_file = results_file
        self.patterns_file = patterns_file

    # ------------------------------------------------------------------ #
    @property
    def experiments_path(self) -> str:
        return os.path.join(self.base_dir, self.experiments_file)

    @property
    def results_path(self) -> str:
        return os.path.join(self.base_dir, self.results_file)

    @property
    def patterns_path(self) -> str:
        return os.path.join(self.base_dir, self.patterns_file)

    def _ensure(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        for p in (self.experiments_path, self.results_path, self.patterns_path):
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8"):
                    pass

    def _append(self, path: str, record: Dict[str, Any]) -> None:
        self._ensure()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_all(path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        out: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # bad line tolerated
        return out

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def record(self, experiment: ASOExperiment) -> None:
        """Persist one experiment (append-only)."""
        self._append(self.experiments_path, experiment.to_dict())

    def record_result(self, result: ASOExperimentResult) -> None:
        """Persist one experiment result (append-only)."""
        self._append(self.results_path, result.to_dict())

    def record_pattern(self, pattern: ASOPattern) -> None:
        """Persist one mined pattern (append-only)."""
        self._append(self.patterns_path, pattern.to_dict())

    def record_experiment_with_result(
        self, experiment: ASOExperiment, result: ASOExperimentResult
    ) -> None:
        """Convenience: persist both an experiment and its result atomically-ish."""
        self.record(experiment)
        self.record_result(result)

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def load_experiments(self) -> List[ASOExperiment]:
        return [ASOExperiment.from_dict(r) for r in self._read_all(self.experiments_path)]

    def load_results(self) -> List[ASOExperimentResult]:
        return [ASOExperimentResult.from_dict(r) for r in self._read_all(self.results_path)]

    def load_patterns(self) -> List[ASOPattern]:
        return [ASOPattern.from_dict(r) for r in self._read_all(self.patterns_path)]

    def history(self, game_id: str) -> List[ASOExperiment]:
        """All experiments recorded for a game (oldest → newest)."""
        return [e for e in self.load_experiments() if e.game_id == game_id]

    def query_patterns(self, condition: str) -> List[ASOPattern]:
        """All patterns whose ``condition`` contains ``condition`` (substring)."""
        return [
            p
            for p in self.load_patterns()
            if condition and condition in p.condition
        ]

    def clear(self) -> None:
        """Wipe all three stores (test helper)."""
        for p in (self.experiments_path, self.results_path, self.patterns_path):
            if os.path.exists(p):
                os.remove(p)


__all__ = ["ASOExperimentStore", "DEFAULT_BASE_DIR", "EXPERIMENTS_FILE", "RESULTS_FILE", "PATTERNS_FILE"]
