"""V5.0 FitnessCalculator — multi-dimensional fitness scoring.

EXTENDS: V4.2.1 Validation (offline metrics) → adds online ROAS/Retention.

Fitness = weighted sum of:
  CTR × 0.15 + CVR × 0.15 + ROAS_D7 × 0.25 + ROAS_D1 × 0.10
  + ROAS_D30 × 0.10 + Retention_D7 × 0.10 + Retention_D1 × 0.05
  - CPI × 0.05 + LTV × 0.05 + Diversity_Bonus × 0.03 + Novelty_Bonus × 0.02

Supports: online data (from UA), offline prediction (from V4.2.1), mixed mode.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import (Fitness, FitnessComponent, FitnessCategory, Genome, Population,
                       EvolutionEvent, DEFAULT_FITNESS_WEIGHTS, DEFAULT_FITNESS_CATEGORIES)


class FitnessCalculator:
    """Multi-dimensional fitness scoring engine."""

    def __init__(self, weights: dict[str, float] | None = None,
                 min_sample_size: int = 1000) -> None:
        self._weights = weights or DEFAULT_FITNESS_WEIGHTS
        self._min_sample_size = min_sample_size
        self._event_handlers: list[Any] = []
        self._fitness_history: list[dict[str, Any]] = []

    def set_weights(self, weights: dict[str, float]) -> None:
        """Update fitness component weights."""
        self._weights = weights

    def get_weights(self) -> dict[str, float]:
        """Get current fitness weights."""
        return dict(self._weights)

    # ── Online Fitness (from UA data) ───────────────────────

    def calculate_online(self, genome_id: str, generation: int,
                         components: dict[str, float],
                         sample_size: int = 0,
                         metadata: dict[str, Any] | None = None) -> Fitness:
        """Calculate fitness from live UA data.

        Args:
            genome_id: Genome being scored.
            generation: Generation number.
            components: {component_name: value} from real UA data.
            sample_size: Number of impressions/clicks.
            metadata: Additional metadata.

        Returns:
            Fitness with composite_score.
        """
        composite = self._compute_composite(components)
        category_scores = self._compute_category_scores(components)
        confidence = self._calculate_confidence(sample_size)

        fitness = Fitness(
            genome_id=genome_id,
            generation=generation,
            components=components,
            component_weights=dict(self._weights),
            composite_score=composite,
            category_scores=category_scores,
            confidence=confidence,
            sample_size=sample_size,
            is_online=True,
        )

        self._log(genome_id, composite, "online")
        self._emit("FITNESS_UPDATED", genome_id, generation=generation)
        return fitness

    def calculate_offline(self, genome_id: str, generation: int,
                          predicted_components: dict[str, float],
                          confidence: float = 0.5,
                          metadata: dict[str, Any] | None = None) -> Fitness:
        """Calculate fitness from predicted/offline data.

        Used when real UA data is not yet available.
        Extends V4.2.1 Validation predictions.
        """
        composite = self._compute_composite(predicted_components)
        category_scores = self._compute_category_scores(predicted_components)

        fitness = Fitness(
            genome_id=genome_id,
            generation=generation,
            components=predicted_components,
            component_weights=dict(self._weights),
            composite_score=composite,
            category_scores=category_scores,
            confidence=confidence,
            sample_size=0,
            is_online=False,
        )

        self._log(genome_id, composite, "offline")
        self._emit("FITNESS_UPDATED", genome_id, generation=generation)
        return fitness

    def calculate_mixed(self, genome_id: str, generation: int,
                        online_components: dict[str, float],
                        offline_components: dict[str, float],
                        online_weight: float = 0.7,
                        sample_size: int = 0) -> Fitness:
        """Calculate mixed fitness (online + offline).

        online_weight: weight for online data (0.7 = 70% online, 30% offline).
        """
        mixed = {}
        for comp in FitnessComponent:
            key = comp.value
            online_val = online_components.get(key, 0.0)
            offline_val = offline_components.get(key, 0.0)
            mixed[key] = online_val * online_weight + offline_val * (1 - online_weight)

        return self.calculate_online(genome_id, generation, mixed, sample_size)

    # ── Population Scoring ──────────────────────────────────

    def score_population(self, population: Population,
                         components_map: dict[str, dict[str, float]],
                         sample_sizes: dict[str, int] | None = None) -> int:
        """Score all genomes in a population.

        Args:
            population: Population to score.
            components_map: {genome_id: {component: value}}.
            sample_sizes: {genome_id: sample_size}.

        Returns:
            Number of genomes scored.
        """
        sample_sizes = sample_sizes or {}
        count = 0

        for genome in population.genomes:
            comps = components_map.get(genome.genome_id)
            if comps is None:
                continue

            sample = sample_sizes.get(genome.genome_id, 0)
            fitness = self.calculate_online(
                genome.genome_id, population.generation, comps, sample
            )
            genome.fitness = fitness
            genome.fitness_history.append(fitness.composite_score)
            count += 1

        # Recalculate population stats after scoring
        scored = [g for g in population.genomes if g.fitness is not None]
        if scored:
            population.best_fitness = max(g.fitness.composite_score for g in scored)
            population.avg_fitness = sum(g.fitness.composite_score for g in scored) / len(scored)
            sorted_scores = sorted(g.fitness.composite_score for g in scored)
            mid = len(sorted_scores) // 2
            population.median_fitness = sorted_scores[mid]

        return count

    def rank_population(self, population: Population) -> list[tuple[Genome, float]]:
        """Rank genomes in a population by fitness.

        Returns:
            List of (genome, fitness_score) sorted descending.
        """
        scored = [(g, g.fitness.composite_score) for g in population.genomes if g.fitness]
        scored.sort(key=lambda x: x[1], reverse=True)

        for rank, (genome, _) in enumerate(scored, 1):
            if genome.fitness:
                genome.fitness.rank_in_generation = rank

        return scored

    # ── Trend Detection ─────────────────────────────────────

    def detect_plateau(self, population: Population,
                       prev_population: Population | None = None,
                       improvement_threshold: float = 0.01) -> bool:
        """Detect if fitness has plateaued across generations.

        Returns:
            True if fitness improvement is below threshold.
        """
        if prev_population is None:
            return False

        improvement = population.avg_fitness - prev_population.avg_fitness
        if improvement < improvement_threshold:
            self._emit("PLATEAU_DETECTED", population.population_id, generation=population.generation)
            return True
        return False

    def get_trend(self, genome_id: str, genome_manager: Any) -> str:
        """Get fitness trend for a genome using its fitness_history."""
        genome = genome_manager.get(genome_id)
        if genome is None:
            return "unknown"
        return genome.fitness_trend

    # ── Stats ───────────────────────────────────────────────

    def get_component_importance(self) -> dict[str, float]:
        """Get component importance (absolute weight)."""
        total = sum(abs(w) for w in self._weights.values())
        return {k: abs(v) / max(1e-6, total) for k, v in self._weights.items()}

    def get_stats(self) -> dict[str, Any]:
        """Get fitness calculator statistics."""
        online = sum(1 for h in self._fitness_history if h["mode"] == "online")
        offline = sum(1 for h in self._fitness_history if h["mode"] == "offline")

        return {
            "total_calculations": len(self._fitness_history),
            "online": online,
            "offline": offline,
            "weights": self._weights,
            "component_importance": self.get_component_importance(),
            "min_sample_size": self._min_sample_size,
        }

    # ── Internal ────────────────────────────────────────────

    def _compute_composite(self, components: dict[str, float]) -> float:
        """Compute weighted composite score."""
        score = 0.0
        for comp_name, weight in self._weights.items():
            value = components.get(comp_name, 0.0)
            score += value * weight
        return max(0.0, score)  # Floor at 0

    def _compute_category_scores(self, components: dict[str, float]) -> dict[str, float]:
        """Compute composite scores for each fitness category.

        Categories: creative, business, user, long_term.
        Each category is a weighted sum of its component values.
        """
        category_scores: dict[str, float] = {}
        for category, comp_names in DEFAULT_FITNESS_CATEGORIES.items():
            cat_score = 0.0
            cat_weight_total = 0.0
            for comp_name in comp_names:
                if comp_name in self._weights:
                    value = components.get(comp_name, 0.0)
                    weight = abs(self._weights[comp_name])
                    cat_score += value * weight
                    cat_weight_total += weight
            # Normalize by total weight in this category
            category_scores[category] = cat_score / max(1e-6, cat_weight_total)
        return category_scores

    def _calculate_confidence(self, sample_size: int) -> float:
        """Calculate confidence based on sample size."""
        if sample_size <= 0:
            return 0.0
        # Confidence grows with sqrt(sample_size), maxes at 1.0
        ratio = (sample_size / self._min_sample_size) ** 0.5
        return min(1.0, ratio)

    def _log(self, genome_id: str, score: float, mode: str) -> None:
        self._fitness_history.append({
            "genome_id": genome_id,
            "score": round(score, 4),
            "mode": mode,
            "timestamp": time.time(),
        })

    def on_event(self, handler: Any) -> None:
        self._event_handlers.append(handler)

    def _emit(self, event_type: str, entity_id: str,
              generation: int = 0, actor: str = "") -> None:
        event = EvolutionEvent(
            event_type=event_type,
            entity_id=entity_id,
            generation=generation,
            source="fitness_calculator",
            actor=actor or "fitness_calculator",
        )
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass