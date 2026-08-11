"""E9.9 Module 1: Experiment Selector.

Selects top experiments from E9.8 mutation candidates.
Scores candidates by: mutation_score * 0.4 + ltv * 0.3 + novelty * 0.2 + risk_inv * 0.1
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from market_ops.experiment_intelligence.schemas import ExperimentCandidate


class ExperimentSelector:
    """Selects experiments from E9.8 top_mutations output.

    Usage:
        selector = ExperimentSelector()
        candidates = selector.select("output/creative_evolution/top_mutations.json", top_n=20)
    """

    def __init__(self) -> None:
        self._novelty_cache: dict[str, float] = {}  # genome_id → novelty_score

    def select(
        self,
        mutations_path: str | Path,
        top_n: int = 20,
    ) -> list[ExperimentCandidate]:
        """Load E9.8 mutations, score, and select top N candidates.

        Args:
            mutations_path: Path to top_mutations.json (E9.8 output)
            top_n: Number of experiments to select

        Returns:
            Sorted list of ExperimentCandidate (highest priority first)
        """
        raw = self._load_mutations(mutations_path)
        candidates = self._convert_to_candidates(raw)
        scored = self._score_candidates(candidates)
        scored.sort(key=lambda c: c.mutation_score, reverse=True)
        return scored[:top_n]

    # ── Load ───────────────────────────────────────────────

    def _load_mutations(self, path: str | Path) -> list[dict[str, Any]]:
        """Load E9.8 top_mutations.json."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Handle both list and dict wrapper
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("top_mutations", data.get("mutations", []))
        return []

    # ── Convert ────────────────────────────────────────────

    def _convert_to_candidates(
        self, raw: list[dict[str, Any]]
    ) -> list[ExperimentCandidate]:
        """Convert raw E9.8 mutations to ExperimentCandidate objects."""
        candidates = []
        for mutation in raw:
            candidate = ExperimentCandidate.from_e98_mutation(mutation)
            if candidate.genome_id:
                candidates.append(candidate)
        return candidates

    # ── Score ──────────────────────────────────────────────

    def _score_candidates(
        self, candidates: list[ExperimentCandidate]
    ) -> list[ExperimentCandidate]:
        """Score candidates using priority formula.

        Priority = mutation_score * 0.4 + ltv_normalized * 0.3
                 + novelty * 0.2 + risk_inverse * 0.1
        """
        if not candidates:
            return candidates

        ltv_values = [c.predicted_ltv for c in candidates if c.predicted_ltv > 0]
        max_ltv = max(ltv_values) if ltv_values else 1.0
        min_ltv = min(ltv_values) if ltv_values else 0.0
        ltv_range = max_ltv - min_ltv if max_ltv > min_ltv else 1.0

        for c in candidates:
            ltv_norm = (c.predicted_ltv - min_ltv) / ltv_range if c.predicted_ltv > 0 else 0.0
            novelty = self._calculate_novelty(c)
            risk_inv = 1.0 - self._calculate_risk(c)

            c.mutation_score = (
                c.mutation_score * 0.4
                + ltv_norm * 0.3
                + novelty * 0.2
                + risk_inv * 0.1
            )

        return candidates

    def _calculate_novelty(self, candidate: ExperimentCandidate) -> float:
        """Calculate novelty based on mutation type and distance."""
        # Higher novelty for exploration mutations, lower for winner emulation
        novelty_map = {
            "exploration": 0.9,
            "archetype": 0.7,
            "fantasy": 0.6,
            "hook": 0.5,
            "reward": 0.5,
            "visual": 0.4,
            "winner_emulation": 0.2,
            "failure_avoidance": 0.3,
        }
        return novelty_map.get(candidate.mutation_type, 0.5)

    def _calculate_risk(self, candidate: ExperimentCandidate) -> float:
        """Calculate risk score (higher = riskier)."""
        # Archetype mutations are riskier (changing target audience)
        # Visual mutations are safer (visual change only)
        risk_map = {
            "archetype": 0.7,
            "winner_emulation": 0.2,
            "failure_avoidance": 0.3,
            "exploration": 0.5,
            "hook": 0.4,
            "reward": 0.4,
            "fantasy": 0.5,
            "visual": 0.3,
        }
        return risk_map.get(candidate.mutation_type, 0.5)

    # ── Summary ────────────────────────────────────────────

    def get_selection_summary(
        self, candidates: list[ExperimentCandidate]
    ) -> dict[str, Any]:
        """Get summary of selected candidates."""
        by_type: dict[str, int] = {}
        by_archetype: dict[str, int] = {}
        for c in candidates:
            by_type[c.mutation_type] = by_type.get(c.mutation_type, 0) + 1
            by_archetype[c.predicted_archetype] = (
                by_archetype.get(c.predicted_archetype, 0) + 1
            )

        return {
            "total_selected": len(candidates),
            "by_mutation_type": by_type,
            "by_archetype": by_archetype,
            "avg_score": (
                round(sum(c.mutation_score for c in candidates) / len(candidates), 3)
                if candidates else 0.0
            ),
            "avg_ltv": (
                round(sum(c.predicted_ltv for c in candidates) / len(candidates), 1)
                if candidates else 0.0
            ),
        }