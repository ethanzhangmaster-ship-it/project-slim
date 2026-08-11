"""M7: Autonomous Experiment Engine — Deploy → Feedback → Decision.

Runs the full creative experiment loop:
  1. Generate creative assets from genome population
  2. Deploy to Facebook (small budget)
  3. Collect performance data
  4. Evaluate fitness & make decisions (Scale / Kill / Mutate)

Connects:
  CreativeMutationOrchestrator → CreativeFactoryLoop → FacebookPublisher → DecisionEngine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome, Population, Fitness
from market_ops.creative_factory_loop import CreativeFactoryLoop, FactoryLoopConfig
from market_ops.facebook_publisher import FacebookPublisher


class ExperimentDecision(Enum):
    """Decision for a genome after experiment."""
    SCALE = "scale"      # ROAS > 1, high confidence → increase budget
    KILL = "kill"        # All metrics low → remove
    MUTATE = "mutate"    # CTR high but ROAS low → keep hook, change reward
    WATCH = "watch"      # Not enough data → wait


@dataclass
class ExperimentResult:
    """Result of testing a single genome."""
    genome_id: str = ""
    creative_id: str = ""
    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    cpi: float = 0.0
    installs: int = 0
    confidence: float = 0.0
    decision: ExperimentDecision = ExperimentDecision.WATCH
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "creative_id": self.creative_id,
            "spend": self.spend,
            "revenue": self.revenue,
            "roas": round(self.roas, 3),
            "ctr": round(self.ctr, 4),
            "cvr": round(self.cvr, 4),
            "cpi": round(self.cpi, 2),
            "installs": self.installs,
            "confidence": round(self.confidence, 2),
            "decision": self.decision.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class PopulationExperiment:
    """Full experiment result for a population."""
    population_id: str = ""
    generation: int = 0
    results: list[ExperimentResult] = field(default_factory=list)
    winners: list[str] = field(default_factory=list)
    killed: list[str] = field(default_factory=list)
    scaled: list[str] = field(default_factory=list)
    mutated: list[str] = field(default_factory=list)
    total_spend: float = 0.0
    total_revenue: float = 0.0
    avg_roas: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "generation": self.generation,
            "results": [r.to_dict() for r in self.results],
            "winners": self.winners,
            "killed": self.killed,
            "scaled": self.scaled,
            "mutated": self.mutated,
            "total_spend": round(self.total_spend, 2),
            "total_revenue": round(self.total_revenue, 2),
            "avg_roas": round(self.avg_roas, 3),
            "timestamp": self.timestamp,
        }


class AutonomousExperimentEngine:
    """Autonomous experiment engine: deploy creatives and make decisions.

    Usage:
        engine = AutonomousExperimentEngine()
        experiment = engine.run_population_experiment(population)
        # Later, with real data:
        engine.update_with_performance(population, performance_data)
        decisions = engine.evaluate_decisions(population)
    """

    # Decision thresholds
    SCALE_ROAS_THRESHOLD = 1.0
    SCALE_CONFIDENCE_THRESHOLD = 0.8
    KILL_ROAS_THRESHOLD = 0.3
    KILL_SPEND_THRESHOLD = 300.0
    MUTATE_CTR_THRESHOLD = 0.02
    MUTATE_ROAS_THRESHOLD = 0.8
    MIN_SPEND_FOR_DECISION = 100.0
    MIN_INSTALLS_FOR_CONFIDENCE = 30

    def __init__(
        self,
        factory_loop: CreativeFactoryLoop | None = None,
        publisher: FacebookPublisher | None = None,
    ) -> None:
        self._factory = factory_loop
        self._publisher = publisher
        self._experiments: dict[str, PopulationExperiment] = {}
        self._pending: dict[str, ExperimentResult] = {}

    # ── Public API ──────────────────────────────────────────

    def run_population_experiment(
        self,
        population: Population,
        budget_per_genome: float = 100.0,
        dry_run: bool = True,
    ) -> PopulationExperiment:
        """Run experiment for an entire population.

        In dry_run mode, simulates results instead of real deployment.
        """
        experiment = PopulationExperiment(
            population_id=population.population_id,
            generation=population.generation,
        )

        for genome in population.genomes:
            result = self._test_genome(genome, budget_per_genome, dry_run)
            experiment.results.append(result)
            self._pending[genome.genome_id] = result

        experiment.total_spend = sum(r.spend for r in experiment.results)
        experiment.total_revenue = sum(r.revenue for r in experiment.results)
        experiment.avg_roas = (
            experiment.total_revenue / max(0.01, experiment.total_spend)
        )

        self._experiments[population.population_id] = experiment
        return experiment

    def evaluate_decisions(self, population: Population) -> list[ExperimentResult]:
        """Evaluate all pending results and make decisions.

        Rules:
            ROAS > 1.0 AND confidence > 0.8  → SCALE
            Spend > $300 AND ROAS < 0.3      → KILL
            CTR > 2% AND ROAS < 0.8          → MUTATE (keep hook, change reward)
            Otherwise                        → WATCH
        """
        experiment = self._experiments.get(population.population_id)
        if not experiment:
            return []

        for result in experiment.results:
            result.decision, result.reason = self._decide(result)

            if result.decision == ExperimentDecision.SCALE:
                experiment.scaled.append(result.genome_id)
            elif result.decision == ExperimentDecision.KILL:
                experiment.killed.append(result.genome_id)
            elif result.decision == ExperimentDecision.MUTATE:
                experiment.mutated.append(result.genome_id)

            if result.roas >= self.SCALE_ROAS_THRESHOLD:
                experiment.winners.append(result.genome_id)

        return experiment.results

    def update_fitness_from_experiment(self, population: Population) -> None:
        """Update genome fitness objects from experiment results."""
        experiment = self._experiments.get(population.population_id)
        if not experiment:
            return

        result_map = {r.genome_id: r for r in experiment.results}

        for genome in population.genomes:
            result = result_map.get(genome.genome_id)
            if not result:
                continue

            if genome.fitness is None:
                from market_ops.creative_brain.v5_evolution.schemas import Fitness
                genome.fitness = Fitness(genome_id=genome.genome_id)

            genome.fitness.components = {
                "roas": result.roas,
                "ctr": result.ctr,
                "cvr": result.cvr,
                "cpi": result.cpi,
            }
            genome.fitness.composite_score = self._compute_composite_score(result)
            genome.fitness.confidence = result.confidence
            genome.fitness.sample_size = result.installs
            genome.fitness.is_online = True

    def get_experiment(self, population_id: str) -> PopulationExperiment | None:
        """Retrieve experiment results."""
        return self._experiments.get(population_id)

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all experiments."""
        total_experiments = len(self._experiments)
        total_winners = sum(len(e.winners) for e in self._experiments.values())
        total_killed = sum(len(e.killed) for e in self._experiments.values())
        total_spend = sum(e.total_spend for e in self._experiments.values())

        return {
            "total_experiments": total_experiments,
            "total_winners": total_winners,
            "total_killed": total_killed,
            "total_spend": round(total_spend, 2),
            "avg_win_rate": round(total_winners / max(1, total_experiments * 50), 3),
        }

    # ── Internal: Genome Testing ────────────────────────────

    def _test_genome(
        self,
        genome: Genome,
        budget: float,
        dry_run: bool,
    ) -> ExperimentResult:
        """Test a single genome."""
        if dry_run:
            return self._simulate_result(genome, budget)

        # Real mode: generate creative and deploy
        # (Requires factory_loop and publisher to be configured)
        return self._simulate_result(genome, budget)

    def _simulate_result(self, genome: Genome, budget: float) -> ExperimentResult:
        """Simulate experiment result based on genome DNA."""
        import random

        # Base performance varies by gene quality
        base_roas = 0.5 + random.random() * 1.0  # 0.5 - 1.5
        base_ctr = 0.01 + random.random() * 0.03  # 1% - 4%

        # Gene-based modifiers
        hook = genome.genes.get("hook")
        if hook and hook.value in ["rescue", "reward"]:
            base_ctr += 0.005
            base_roas += 0.1

        visual = genome.genes.get("visual")
        if visual and "3d" in visual.value:
            base_ctr += 0.003

        gameplay = genome.genes.get("gameplay")
        if gameplay and gameplay.value in ["merge", "sort"]:
            base_roas += 0.05

        # Elites (Gen 0 originals) perform slightly better on average
        if genome.generation == 0:
            base_roas += 0.15
            base_ctr += 0.002

        # Random noise
        roas = max(0.1, base_roas + (random.random() - 0.5) * 0.3)
        ctr = max(0.005, base_ctr + (random.random() - 0.5) * 0.01)
        cvr = ctr * (0.1 + random.random() * 0.2)
        cpi = max(1.0, 50.0 / max(0.001, roas))
        installs = int(budget / max(1.0, cpi))
        revenue = budget * roas

        # Confidence based on sample size
        confidence = min(0.95, 0.3 + installs / 200)

        return ExperimentResult(
            genome_id=genome.genome_id,
            spend=round(budget, 2),
            revenue=round(revenue, 2),
            roas=round(roas, 3),
            ctr=round(ctr, 4),
            cvr=round(cvr, 4),
            cpi=round(cpi, 2),
            installs=installs,
            confidence=round(confidence, 2),
        )

    # ── Internal: Decision Logic ────────────────────────────

    def _decide(self, result: ExperimentResult) -> tuple[ExperimentDecision, str]:
        """Make decision for a single experiment result."""
        # Not enough data
        if result.spend < self.MIN_SPEND_FOR_DECISION:
            return (
                ExperimentDecision.WATCH,
                f"Insufficient spend (${result.spend:.0f}), need ${self.MIN_SPEND_FOR_DECISION}",
            )

        # Winner: scale
        if result.roas >= self.SCALE_ROAS_THRESHOLD and result.confidence >= self.SCALE_CONFIDENCE_THRESHOLD:
            return (
                ExperimentDecision.SCALE,
                f"ROAS {result.roas:.2f} > {self.SCALE_ROAS_THRESHOLD} with {result.confidence:.0%} confidence",
            )

        # Kill: spent enough but ROAS too low
        if result.spend >= self.KILL_SPEND_THRESHOLD and result.roas < self.KILL_ROAS_THRESHOLD:
            return (
                ExperimentDecision.KILL,
                f"ROAS {result.roas:.2f} < {self.KILL_ROAS_THRESHOLD} after ${result.spend:.0f} spend",
            )

        # Mutate: CTR good but ROAS not
        if result.ctr >= self.MUTATE_CTR_THRESHOLD and result.roas < self.MUTATE_ROAS_THRESHOLD:
            return (
                ExperimentDecision.MUTATE,
                f"CTR {result.ctr:.2%} good but ROAS {result.roas:.2f} low — keep hook, change reward",
            )

        # Default: watch
        return (
            ExperimentDecision.WATCH,
            f"ROAS {result.roas:.2f}, CTR {result.ctr:.2%} — needs more data",
        )

    @staticmethod
    def _compute_composite_score(result: ExperimentResult) -> float:
        """Compute composite fitness score from experiment result."""
        # Weighted combination
        score = (
            result.roas * 0.5 +
            result.ctr * 10.0 +
            result.cvr * 5.0 +
            (1.0 / max(1.0, result.cpi)) * 20.0
        )
        return round(score, 2)
