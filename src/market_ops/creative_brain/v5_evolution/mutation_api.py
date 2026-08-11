"""V5.0 Mutation API — Freeze v1.4 (Interface Only, No Implementation).

Phase 2 Mutation Engine will implement these interfaces.
All implementations must accept and return the Contract types defined in schemas.py.

API Design:
  MutationPlanner   → decides WHAT to mutate (which genes, what strategy)
  MutationEngine    → executes HOW to mutate (applies operators)
  MutationEvaluator → judges mutation QUALITY (risk, expected gain, confidence)
  MutationSelector  → selects WHICH mutations to KEEP (top N, bandit, etc.)
  MutationReplay    → replays past mutations (deterministic, auditable)

============================================================================
  TYPICAL FLOW
============================================================================

  MutationPlanner.plan(genomes, population, context)
       |
       v
  list[MutationRequest]
       |
       v
  MutationEngine.mutate(request)
       |
       v
  MutationResult
       |
       v
  MutationEvaluator.evaluate(result)
       |
       v
  MutationEvaluator.evaluate_batch(results)
       |
       v
  MutationSelector.select(results, top_n)
       |
       v
  selected MutationResults
       |
       v
  MutationEngine.mutate_batch(population, requests)
       |
       v
  MutationReport
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .schemas import (
    Genome, Population, Gene, MutationOperator,
    MutationRequest, MutationResult, MutationReport, MutationStrategy,
    MutationStrategyType, EvolutionEvent,
)


# ═══════════════════════════════════════════════════════════
# 1. MutationPlanner
# ═══════════════════════════════════════════════════════════

class MutationPlanner(ABC):
    """Decides WHAT to mutate: which genes, what strategy, what constraints.

    The planner is the "brain" of the mutation system. It analyzes the
    current population, winner DNA, market gaps, and fitness trends to
    decide which genomes should be mutated and how.

    Implementations:
      - RandomPlanner: random selection with uniform strategy
      - GuidedPlanner: winner DNA + market gap guided
      - BanditPlanner: multi-armed bandit on strategy selection
      - HypothesisPlanner: hypothesis-driven mutation
    """

    @abstractmethod
    def plan(self, population: Population,
             context: dict[str, Any] | None = None) -> list[MutationRequest]:
        """Generate mutation requests for a population.

        Args:
            population: Current population to plan mutations for.
            context: Optional context (winner DNA, market data, fitness history).

        Returns:
            List of MutationRequest objects, one per genome to mutate.
        """
        ...

    @abstractmethod
    def plan_single(self, genome: Genome,
                    context: dict[str, Any] | None = None) -> MutationRequest | None:
        """Plan a mutation for a single genome.

        Args:
            genome: The genome to plan mutation for.
            context: Optional context.

        Returns:
            MutationRequest or None if no mutation is needed.
        """
        ...

    @abstractmethod
    def get_strategy(self, strategy_type: MutationStrategyType) -> MutationStrategy | None:
        """Get the configured strategy for a given strategy type."""
        ...

    @abstractmethod
    def set_strategy(self, strategy: MutationStrategy) -> None:
        """Register a mutation strategy configuration."""
        ...


# ═══════════════════════════════════════════════════════════
# 2. MutationEngine
# ═══════════════════════════════════════════════════════════

class MutationEngine(ABC):
    """Executes HOW to mutate: applies mutation operators to genomes.

    This is the core execution engine. It takes a MutationRequest and
    produces a mutated genome plus a MutationResult.

    Supports three mutation categories:
      - Gene Mutation: change existing gene value
      - Structural Mutation: add/delete/merge genes
      - Cross-over: combine two parent genomes

    Implementations:
      - GeneMutationEngine: single-gene mutation
      - StructuralMutationEngine: gene add/delete/merge
      - CrossoverEngine: two-parent crossover
      - CompositeMutationEngine: orchestrates all three
    """

    @abstractmethod
    def mutate(self, request: MutationRequest) -> MutationResult:
        """Execute a single mutation request.

        Args:
            request: What to mutate and how.

        Returns:
            MutationResult with the mutated genome and change details.
        """
        ...

    @abstractmethod
    def mutate_batch(self, requests: list[MutationRequest]) -> MutationReport:
        """Execute a batch of mutation requests.

        Args:
            requests: List of mutation requests.

        Returns:
            MutationReport aggregating all results.
        """
        ...

    @abstractmethod
    def validate(self, result: MutationResult) -> bool:
        """Validate a mutation result against quality gates.

        Checks:
          - No forbidden values
          - Required genes present
          - Mutation cost within budget
          - Mutation risk within threshold
        """
        ...

    @abstractmethod
    def get_available_operators(self) -> list[MutationOperator]:
        """Get the list of mutation operators this engine supports."""
        ...


# ═══════════════════════════════════════════════════════════
# 3. MutationEvaluator
# ═══════════════════════════════════════════════════════════

class MutationEvaluator(ABC):
    """Judges mutation QUALITY: risk, expected gain, and confidence.

    After a mutation is applied, the evaluator judges whether it was
    a good mutation. This is used by the MutationSelector to decide
    which mutations to keep.

    Key metrics:
      - risk_score: how risky was this mutation? (0-1)
      - expected_gain: predicted fitness improvement
      - confidence: how confident are we in this evaluation?
    """

    @abstractmethod
    def evaluate(self, result: MutationResult,
                 context: dict[str, Any] | None = None) -> MutationResult:
        """Evaluate a single mutation result.

        Updates result.risk_score, result.confidence based on:
          - Gene mutation risk (from Gene.mutation_risk)
          - Historical performance of this operator
          - Fitness trend of the original genome

        Returns the same MutationResult with updated risk/confidence.
        """
        ...

    @abstractmethod
    def evaluate_batch(self, results: list[MutationResult],
                       context: dict[str, Any] | None = None) -> list[MutationResult]:
        """Evaluate a batch of mutation results."""
        ...

    @abstractmethod
    def get_operator_effectiveness(self,
                                    operator: MutationOperator) -> dict[str, float]:
        """Get historical effectiveness stats for an operator.

        Returns: {"avg_improvement": 0.15, "success_rate": 0.7, "sample_size": 120}
        """
        ...

    @abstractmethod
    def get_strategy_effectiveness(self,
                                    strategy: MutationStrategyType) -> dict[str, float]:
        """Get historical effectiveness stats for a strategy type."""
        ...


# ═══════════════════════════════════════════════════════════
# 4. MutationSelector
# ═══════════════════════════════════════════════════════════

class MutationSelector(ABC):
    """Selects WHICH mutations to KEEP using multi-armed bandit or top-N.

    Not all mutations are kept. The selector decides which mutated genomes
    enter the next generation based on:
      - Evaluated risk/gain
      - Diversity contribution
      - Budget constraints
      - Exploration vs exploitation balance

    Implementations:
      - TopNSelector: keep top N by expected gain
      - BanditSelector: multi-armed bandit (Thompson sampling, UCB)
      - DiversitySelector: prioritize diversity
      - CompositeSelector: weighted combination
    """

    @abstractmethod
    def select(self, results: list[MutationResult],
               population: Population,
               top_n: int | None = None) -> list[MutationResult]:
        """Select which mutations to keep.

        Args:
            results: Evaluated mutation results.
            population: Current population context.
            top_n: Maximum number to keep (None = auto).

        Returns:
            Selected MutationResults.
        """
        ...

    @abstractmethod
    def select_genomes(self, results: list[MutationResult],
                       population: Population,
                       top_n: int | None = None) -> list[Genome]:
        """Select which mutated genomes to keep (convenience wrapper).

        Returns just the Genome objects from selected results.
        """
        ...

    @abstractmethod
    def get_selection_stats(self) -> dict[str, Any]:
        """Get selection statistics for the current generation.

        Returns: {"total_candidates": 50, "selected": 10, "avg_risk": 0.3, ...}
        """
        ...


# ═══════════════════════════════════════════════════════════
# 5. MutationReplay
# ═══════════════════════════════════════════════════════════

class MutationReplay(ABC):
    """Replays past mutations for audit, debugging, and reproducibility.

    Uses EvolutionEvent logs with random_seed to deterministically
    reproduce past mutation runs.

    Key capabilities:
      - Replay a single mutation from event log
      - Replay an entire generation
      - Compare replay output with original (drift detection)
      - Rollback to a specific generation state
    """

    @abstractmethod
    def replay_event(self, event: EvolutionEvent) -> MutationResult | None:
        """Replay a single mutation event.

        Uses event.random_seed for deterministic reproduction.
        Returns the reproduced MutationResult.
        """
        ...

    @abstractmethod
    def replay_generation(self, events: list[EvolutionEvent],
                          population: Population) -> MutationReport:
        """Replay all mutations for a generation.

        Args:
            events: Mutation events for this generation.
            population: The population state at that generation.

        Returns:
            MutationReport with reproduced results.
        """
        ...

    @abstractmethod
    def compare_replay(self, original: MutationReport,
                       replayed: MutationReport) -> dict[str, Any]:
        """Compare original vs replayed mutation results.

        Returns drift report:
          {"match_rate": 0.98, "drifted_genes": [...], "seed_mismatches": 0}
        """
        ...

    @abstractmethod
    def rollback(self, target_generation: int,
                 events: list[EvolutionEvent]) -> Population | None:
        """Rollback to a specific generation by replaying events up to that point.

        Args:
            target_generation: Generation to roll back to.
            events: All events from start to current.

        Returns:
            Reconstructed Population at target_generation.
        """
        ...


# ═══════════════════════════════════════════════════════════
# API Registry
# ═══════════════════════════════════════════════════════════

MUTATION_API_CLASSES = {
    "planner": MutationPlanner,
    "engine": MutationEngine,
    "evaluator": MutationEvaluator,
    "selector": MutationSelector,
    "replay": MutationReplay,
}

MUTATION_API_METHODS = {
    "MutationPlanner": ["plan", "plan_single", "get_strategy", "set_strategy"],
    "MutationEngine": ["mutate", "mutate_batch", "validate", "get_available_operators"],
    "MutationEvaluator": ["evaluate", "evaluate_batch", "get_operator_effectiveness", "get_strategy_effectiveness"],
    "MutationSelector": ["select", "select_genomes", "get_selection_stats"],
    "MutationReplay": ["replay_event", "replay_generation", "compare_replay", "rollback"],
}