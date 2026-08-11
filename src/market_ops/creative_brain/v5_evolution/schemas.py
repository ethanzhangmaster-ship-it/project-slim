"""V5.0 Autonomous Creative Evolution Layer — Architecture Freeze v1.3

================================================================================
  V4/V5 INTEGRATION: EVENT-DRIVEN (NOT DIRECT IMPORT)
================================================================================

V4 and V5 communicate through V4.4 EventBus, not direct imports:

  V4 Runtime (ArtifactManager, ValidationEngine, etc.)
       |
       |  publish events via EventBus
       v
  V4.4 EventBus ──────────────────────────────┐
       |                                       |
       |  subscribe to events                  |
       v                                       v
  V5 EvolutionMemory    V5 FitnessCalculator   V5 GenomeManager

This keeps V4 unaware of V5's existence. Clean architecture.

================================================================================
  MODULE BOUNDARIES
================================================================================

V5.0 is NOT a replacement for V4.x. It is an Orchestrator + Evolution State layer.

  V5 Evolution Controller (Orchestrator)
       |
       +---> EvolutionRunManager (tracks complete evolution tasks)
       +---> GenomeManager (genome CRUD + fitness history)
       +---> PopulationManager (generation management + elite selection)
       +---> MutationEngine (EXTEND V4.1 Retriever)
       +---> ExperimentManager (EXTEND V4.2.1 Bandit)
       +---> FitnessCalculator (EXTEND V4.2.1 Validation)
       +---> EvolutionMemory (EXTEND V4.1 Memory)
       +---> OpportunityEngine (NEW)
       +---> HypothesisEngine (NEW)

================================================================================
  EVOLUTION STATE MACHINE (v1.1)
================================================================================

  IDLE → SCANNING → OPPORTUNITY_FOUND → GENOME_INITIALIZED
       → POPULATION_CREATED → MUTATING → GENERATING → VALIDATING
       → RUNNING_EXPERIMENT → WAITING_FEEDBACK → FITNESS_EVALUATING
       → CONVERGING → EXPLOITING → EXPLORING → IDLE

  Terminal states: CONVERGED, EXTINCT, ROLLED_BACK

  WAITING_FEEDBACK: creative launched, waiting 7 days for ROAS data.
  Not RUNNING, not SUCCESS — waiting for real-world UA feedback.

================================================================================
  EVENT DEFINITIONS (via V4.4 EventBus, unified EvolutionEvent format)
================================================================================

  All events use the unified EvolutionEvent dataclass with:
    event_id, event_type, run_id, entity_id, timestamp, payload, source, confidence
"""

from __future__ import annotations

import uuid
import time
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class EvolutionPhase(str, Enum):
    """Evolution controller state machine phases (v1.1)."""
    IDLE = "idle"
    SCANNING = "scanning"                       # Market scanning
    OPPORTUNITY_FOUND = "opportunity_found"     # Opportunity detected
    GENOME_INITIALIZED = "genome_initialized"   # Genomes extracted from winners
    POPULATION_CREATED = "population_created"   # Initial population
    MUTATING = "mutating"                       # Mutation in progress
    GENERATING = "generating"                   # Creative assets being generated
    VALIDATING = "validating"                   # Quality gate validation
    RUNNING_EXPERIMENT = "running_experiment"   # Experiment live on UA
    WAITING_FEEDBACK = "waiting_feedback"       # Waiting for ROAS data (7 days)
    FITNESS_EVALUATING = "fitness_evaluating"   # Evaluating fitness scores
    CONVERGING = "converging"                   # Converging toward optimum
    EXPLOITING = "exploiting"                   # Exploiting winners
    EXPLORING = "exploring"                     # Exploring new directions
    CONVERGED = "converged"                     # Terminal: converged
    EXTINCT = "extinct"                         # Terminal: all failed
    ROLLED_BACK = "rolled_back"                 # Terminal: rolled back


class GeneType(str, Enum):
    """Types of evolvable genes."""
    HOOK = "hook"               # Hook type (rescue, escape, protect)
    CHARACTER = "character"     # Character (dragon, cat, monster)
    EMOTION = "emotion"         # Emotional trigger (cute, fear, curiosity)
    REWARD = "reward"           # Reward mechanism (growth, evolution, collection)
    GAMEPLAY = "gameplay"       # Gameplay mechanic (merge, puzzle, sort)
    VISUAL = "visual"           # Visual style (color, camera, lighting)
    STORY = "story"             # Narrative arc
    PACING = "pacing"           # Video pacing (fast, slow, build-up)
    PLATFORM = "platform"       # Target platform (Facebook, TikTok, Google)
    AUDIENCE = "audience"       # Target audience segment


class MutationOperator(str, Enum):
    """Genetic algorithm mutation operators."""
    POINT_MUTATION = "point_mutation"       # Change single gene value
    CROSSOVER = "crossover"                 # Combine two parent genomes
    INVERSION = "inversion"                 # Reverse gene order
    DUPLICATION = "duplication"             # Duplicate a gene
    DELETION = "deletion"                   # Remove a gene
    INSERTION = "insertion"                 # Insert new gene from pool
    SWAP = "swap"                           # Swap two genes
    RANDOM_RESET = "random_reset"           # Random gene from mutation pool


class HypothesisStatus(str, Enum):
    """Hypothesis lifecycle."""
    PROPOSED = "proposed"           # Just formulated
    DESIGNED = "designed"           # Experiment designed
    TESTING = "testing"             # Experiment running
    CONFIRMED = "confirmed"         # Hypothesis supported
    REJECTED = "rejected"           # Hypothesis disproven
    INCONCLUSIVE = "inconclusive"   # Not enough data
    ARCHIVED = "archived"           # Stored for future reference


class ExperimentStatus(str, Enum):
    """Experiment lifecycle."""
    DRAFT = "draft"
    ALLOCATING_BUDGET = "allocating_budget"
    RUNNING = "running"
    COLLECTING_DATA = "collecting_data"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


class OpportunitySource(str, Enum):
    """Sources for market opportunity discovery."""
    APP_STORE = "app_store"
    GOOGLE_PLAY = "google_play"
    FACEBOOK_ADS_LIBRARY = "facebook_ads_library"
    TIKTOK_CREATIVE_CENTER = "tiktok_creative_center"
    SENSOR_TOWER = "sensor_tower"
    APP_MAGIC = "app_magic"
    YOUTUBE = "youtube"
    REDDIT = "reddit"
    INTERNAL_DATA = "internal_data"


class OpportunityCategory(str, Enum):
    """Categories of market opportunities."""
    NEW_GENRE = "new_genre"             # Emerging game genre
    GAMEPLAY_TREND = "gameplay_trend"   # New mechanic trend
    CREATIVE_GAP = "creative_gap"       # Underserved creative space
    AUDIENCE_SHIFT = "audience_shift"   # Audience preference change
    PLATFORM_OPPORTUNITY = "platform_opportunity"  # New platform opening
    COMPETITOR_WEAKNESS = "competitor_weakness"    # Competitor gap


class EvolutionDecisionType(str, Enum):
    """Types of evolution controller decisions."""
    EXPLOIT = "exploit"           # Double down on winners
    EXPLORE = "explore"           # Try new directions
    MUTATE = "mutate"             # Increase mutation rate
    STOP = "stop"                 # Stop current direction
    ROLLBACK = "rollback"         # Revert to previous generation
    CREATE_HYPOTHESIS = "create_hypothesis"  # Form new hypothesis
    INCREASE_DIVERSITY = "increase_diversity"
    ARCHIVE_POPULATION = "archive_population"


class FitnessComponent(str, Enum):
    """Components of the multi-dimensional fitness score."""
    CTR = "ctr"                   # Click-through rate
    CVR = "cvr"                   # Conversion rate
    ROAS_D1 = "roas_d1"           # Day 1 ROAS
    ROAS_D7 = "roas_d7"           # Day 7 ROAS
    ROAS_D30 = "roas_d30"         # Day 30 ROAS
    RETENTION_D1 = "retention_d1" # Day 1 retention
    RETENTION_D7 = "retention_d7" # Day 7 retention
    CPI = "cpi"                   # Cost per install
    LTV = "ltv"                   # Lifetime value
    DIVERSITY_BONUS = "diversity_bonus"  # Diversity bonus
    NOVELTY_BONUS = "novelty_bonus"      # Novelty bonus


class FitnessCategory(str, Enum):
    """Composite fitness categories for different monetization models."""
    CREATIVE = "creative"           # CTR, CVR, engagement
    BUSINESS = "business"           # ROAS, CPI, revenue
    USER = "user"                   # Retention, session length
    LONG_TERM = "long_term"         # LTV, D30 ROAS, D7 retention


# ═══════════════════════════════════════════════════════════
# Core Data Structures
# ═══════════════════════════════════════════════════════════

@dataclass
class Gene:
    """A single evolvable gene in the genome.

    Difference from V4 Winner DNA:
      Winner DNA = "why did this work?"  (analysis)
      Gene       = "what can we change?" (evolvable parameter)

    Mutation risk varies by gene type:
      character: dragon→cat     = LOW risk
      gameplay:  merge→shooter  = HIGH risk
    """
    gene_id: str = ""
    gene_type: GeneType = GeneType.HOOK
    value: str = ""                          # Current value (e.g., "rescue")
    mutation_pool: list[str] = field(default_factory=list)  # Possible mutations
    mutation_operator: MutationOperator = MutationOperator.POINT_MUTATION
    mutation_probability: float = 0.1        # P(mutation) per generation
    mutation_cost: float = 0.0               # 0-1, how expensive to mutate (higher = riskier)
    mutation_risk: float = 0.0               # 0-1, risk of performance degradation
    mutation_history: list[str] = field(default_factory=list)  # Past values
    is_locked: bool = False                  # If True, gene cannot mutate
    confidence: float = 0.0                  # Confidence in current value (0-1)
    source: str = ""                         # Where this gene came from

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_id": self.gene_id,
            "type": self.gene_type.value,
            "value": self.value,
            "mutation_pool": self.mutation_pool,
            "mutation_operator": self.mutation_operator.value,
            "mutation_probability": self.mutation_probability,
            "mutation_cost": self.mutation_cost,
            "mutation_risk": self.mutation_risk,
            "is_locked": self.is_locked,
            "confidence": self.confidence,
        }


@dataclass
class Genome:
    """A complete evolvable genome = a creative's genetic blueprint.

    This is the core unit of evolution. Each creative in the population
    has one Genome. The Genome is what gets mutated, crossed over, and
    selected for fitness.

    fitness_history tracks performance across generations:
      [0.52, 0.61, 0.78, 0.82] → improving trend
    This enables judgment of whether mutation is valuable.

    schema_version enables forward compatibility — old genomes remain
    readable when new gene types (AI Prompt, Camera, UI, Economy, etc.)
    are added in future versions.
    """
    genome_id: str = ""
    name: str = ""                           # Human-readable name
    generation: int = 0                      # Which generation this belongs to
    genes: dict[str, Gene] = field(default_factory=dict)  # gene_type → Gene
    parent_ids: list[str] = field(default_factory=list)   # Parent genome IDs
    fitness: Fitness | None = None           # Current fitness score
    fitness_history: list[float] = field(default_factory=list)  # [0.52, 0.61, 0.78, ...]
    schema_version: str = "1.3"              # Genome schema version for forward compat
    created_at: float = 0.0
    mutation_count: int = 0                  # Total mutations applied
    generation_history: list[int] = field(default_factory=list)  # Which gens it existed in
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.genome_id:
            self.genome_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def get_gene(self, gene_type: GeneType) -> Gene | None:
        return self.genes.get(gene_type.value)

    def get_gene_value(self, gene_type: GeneType) -> str:
        gene = self.genes.get(gene_type.value)
        return gene.value if gene else ""

    def get_mutable_genes(self) -> list[Gene]:
        return [g for g in self.genes.values() if not g.is_locked]

    @property
    def fitness_trend(self) -> str:
        """Determine fitness trend from history."""
        if len(self.fitness_history) < 2:
            return "stable"
        recent = self.fitness_history[-3:]
        if len(recent) >= 2 and recent[-1] > recent[0] * 1.02:
            return "improving"
        if len(recent) >= 2 and recent[-1] < recent[0] * 0.98:
            return "declining"
        return "stable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "name": self.name,
            "generation": self.generation,
            "genes": {k: v.to_dict() for k, v in self.genes.items()},
            "parent_ids": self.parent_ids,
            "schema_version": self.schema_version,
            "fitness": self.fitness.to_dict() if self.fitness else None,
            "fitness_trend": self.fitness_trend,
            "mutation_count": self.mutation_count,
        }

    def clone(self) -> Genome:
        """Deep clone for mutation."""
        import copy
        return copy.deepcopy(self)


@dataclass
class Species:
    """A sub-group within a Population sharing a common gameplay/mechanic.

    Species enable separate evolution tracks for different game types
    within the same population. For example:
      Species A: Merge Puzzle genomes
      Species B: Sort Puzzle genomes
      Species C: Simulation genomes

    Each species has its own diversity, fitness, and novelty metrics.
    Cross-breeding between species is possible via CROSSOVER operator.

    Species can evolve over time via split/merge:
      parent_species_id:  which species this was split from
      children_species_ids: species that were split from this one
      merge_history: list of species that merged into this one
    """
    species_id: str = ""
    name: str = ""                           # e.g., "merge_puzzle", "sort_puzzle"
    gameplay_type: str = ""                  # Primary gameplay mechanic
    genomes: list[Genome] = field(default_factory=list)
    centroid_genome_id: str = ""             # Representative genome for this species
    parent_species_id: str = ""              # Split from this species
    children_species_ids: list[str] = field(default_factory=list)  # Split into these
    merge_history: list[str] = field(default_factory=list)  # Species IDs that merged in
    diversity_score: float = 0.0
    avg_fitness: float = 0.0
    best_fitness: float = 0.0
    size: int = 0
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.species_id:
            self.species_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "species_id": self.species_id,
            "name": self.name,
            "gameplay_type": self.gameplay_type,
            "size": len(self.genomes),
            "diversity": round(self.diversity_score, 3),
            "avg_fitness": round(self.avg_fitness, 4),
            "best_fitness": round(self.best_fitness, 4),
        }


@dataclass
class Population:
    """A generation of creative genomes.

    Managed by PopulationManager. Contains all genomes in one generation,
    plus metadata about diversity, convergence, and elite selection.

    Species support: genomes can be grouped by gameplay type (merge, sort,
    simulation, etc.) to enable parallel evolution tracks within one generation.
    """
    population_id: str = ""
    generation: int = 0
    genomes: list[Genome] = field(default_factory=list)
    species: dict[str, Species] = field(default_factory=dict)  # species_id → Species
    size: int = 100                            # Target population size
    elite_count: int = 10                      # Number of elites to preserve
    created_at: float = 0.0
    diversity_score: float = 0.0               # 0-1, higher = more diverse
    convergence_score: float = 0.0             # 0-1, higher = more converged
    novelty_score: float = 0.0                 # 0-1, higher = more novel (vs previous gens)
    survival_rate: float = 0.0                 # 0-1, proportion of genomes surviving to next gen
    avg_fitness: float = 0.0
    best_fitness: float = 0.0
    median_fitness: float = 0.0
    extinction_risk: float = 0.0               # 0-1, higher = at risk
    status: str = "active"                     # active, converged, extinct, archived
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.population_id:
            self.population_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def get_elites(self) -> list[Genome]:
        """Get top N genomes by fitness."""
        sorted_genomes = sorted(
            [g for g in self.genomes if g.fitness],
            key=lambda g: g.fitness.composite_score if g.fitness else 0,
            reverse=True,
        )
        return sorted_genomes[:self.elite_count]

    def get_best(self) -> Genome | None:
        elites = self.get_elites()
        return elites[0] if elites else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "population_id": self.population_id,
            "generation": self.generation,
            "size": len(self.genomes),
            "elite_count": self.elite_count,
            "diversity": round(self.diversity_score, 3),
            "convergence": round(self.convergence_score, 3),
            "novelty": round(self.novelty_score, 3),
            "survival_rate": round(self.survival_rate, 3),
            "avg_fitness": round(self.avg_fitness, 4),
            "best_fitness": round(self.best_fitness, 4),
            "extinction_risk": round(self.extinction_risk, 3),
            "status": self.status,
        }


@dataclass
class Fitness:
    """Multi-dimensional fitness score for a genome.

    Combines multiple signals: CTR, CVR, ROAS, Retention, CPI, LTV.
    Extends V4.2.1 Validation (which handles offline metrics).

    Composite categories (for multi-monetization models):
      creative_score: CTR, CVR, engagement (creative quality)
      business_score: ROAS_D1, ROAS_D7, ROAS_D30, CPI (monetization)
      user_score:    Retention_D1, Retention_D7 (user experience)
      long_term_score: LTV, ROAS_D30, Retention_D7 (sustainability)
    """
    genome_id: str = ""
    generation: int = 0
    components: dict[str, float] = field(default_factory=dict)  # component → value
    component_weights: dict[str, float] = field(default_factory=dict)  # component → weight
    composite_score: float = 0.0            # Weighted sum
    category_scores: dict[str, float] = field(default_factory=dict)  # creative/business/user/long_term
    explanation: list[str] = field(default_factory=list)  # Why this score (e.g., "Reward stronger", "Hook weaker")
    confidence: float = 0.0                 # Data confidence (sample size)
    sample_size: int = 0                    # Number of impressions/clicks
    calculated_at: float = 0.0
    is_online: bool = False                 # True = from live data, False = predicted
    rank_in_generation: int = 0
    trend: str = "stable"                   # improving, declining, stable
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.calculated_at:
            self.calculated_at = time.time()

    def get_component(self, comp: FitnessComponent) -> float:
        return self.components.get(comp.value, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "generation": self.generation,
            "composite_score": round(self.composite_score, 4),
            "category_scores": {k: round(v, 4) for k, v in self.category_scores.items()},
            "explanation": self.explanation,
            "confidence": round(self.confidence, 3),
            "sample_size": self.sample_size,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "trend": self.trend,
            "rank": self.rank_in_generation,
        }


@dataclass
class Hypothesis:
    """A testable causal claim about creative performance.

    Example:
      "Users are not responding to 'dragon' specifically,
       but to 'weak creature rescue' as a narrative pattern."
    """
    hypothesis_id: str = ""
    statement: str = ""                      # Human-readable hypothesis
    causal_claim: str = ""                   # "X causes Y" formulation
    independent_variable: str = ""           # What we're testing
    dependent_variable: str = ""             # What we're measuring
    control_genome_id: str = ""              # Baseline genome
    test_genome_ids: list[str] = field(default_factory=list)  # Test genomes
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.0                  # P(hypothesis is true)
    evidence_strength: float = 0.0           # How much evidence supports
    experiment_id: str = ""                  # Linked experiment
    proposed_at: float = 0.0
    resolved_at: float = 0.0
    source: str = ""                         # Which module proposed it
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.hypothesis_id:
            self.hypothesis_id = str(uuid.uuid4())[:12]
        if not self.proposed_at:
            self.proposed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "causal_claim": self.causal_claim,
            "status": self.status.value,
            "confidence": round(self.confidence, 3),
            "evidence_strength": round(self.evidence_strength, 3),
        }


@dataclass
class EvolutionExperiment:
    """A creative evolution experiment.

    Extends V4.2.1 Bandit Engine with joint state space:
      DNA × Audience × Placement × Country
    """
    experiment_id: str = ""
    name: str = ""
    hypothesis_id: str = ""                  # Linked hypothesis
    population_id: str = ""                  # Population being tested
    arms: list[dict[str, Any]] = field(default_factory=list)  # [{genome_id, budget, ...}]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    budget_total: float = 0.0
    budget_per_arm: float = 0.0
    platform: str = "facebook"
    countries: list[str] = field(default_factory=list)
    audiences: list[str] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float = 0.0
    results: dict[str, Any] = field(default_factory=dict)  # {genome_id: fitness}
    winner_id: str = ""
    winner_confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.experiment_id:
            self.experiment_id = str(uuid.uuid4())[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "status": self.status.value,
            "arms": len(self.arms),
            "budget_total": self.budget_total,
            "winner_id": self.winner_id,
            "winner_confidence": round(self.winner_confidence, 3),
        }


@dataclass
class EvolutionDecision:
    """A decision made by the Evolution Controller.

    Not "AI CEO" — it's an orchestrator. Decides:
      - When to exploit vs explore
      - When to increase mutation rate
      - When to form new hypotheses
      - When to stop a direction
    """
    decision_id: str = ""
    decision_type: EvolutionDecisionType = EvolutionDecisionType.EXPLOIT
    reason: str = ""
    confidence: float = 0.0
    population_id: str = ""
    generation: int = 0
    context: dict[str, Any] = field(default_factory=dict)  # State that led to decision
    decided_at: float = 0.0
    executed_at: float = 0.0
    outcome: str = ""                        # What happened after

    def __post_init__(self):
        if not self.decision_id:
            self.decision_id = str(uuid.uuid4())[:12]
        if not self.decided_at:
            self.decided_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "type": self.decision_type.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "generation": self.generation,
        }


@dataclass
class MarketOpportunity:
    """A discovered market opportunity.

    Output of Market Intelligence → Opportunity Engine pipeline.
    """
    opportunity_id: str = ""
    category: OpportunityCategory = OpportunityCategory.CREATIVE_GAP
    title: str = ""
    description: str = ""
    source: OpportunitySource = OpportunitySource.FACEBOOK_ADS_LIBRARY
    growth_score: float = 0.0               # 0-1, how fast is this growing
    competition_score: float = 0.0          # 0-1, 1 = very competitive
    creative_gap_score: float = 0.0         # 0-1, 1 = big creative gap
    ua_efficiency_score: float = 0.0        # 0-1, how efficient is UA here
    development_cost_score: float = 0.0     # 0-1, 1 = very expensive to develop
    opportunity_score: float = 0.0          # Composite: higher = better opportunity
    market_size_estimate: int = 0           # Estimated addressable market
    trend_direction: str = "stable"         # rising, stable, declining
    discovered_at: float = 0.0
    confidence: float = 0.0
    competitor_count: int = 0
    top_competitors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.opportunity_id:
            self.opportunity_id = str(uuid.uuid4())[:12]
        if not self.discovered_at:
            self.discovered_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "category": self.category.value,
            "title": self.title,
            "opportunity_score": round(self.opportunity_score, 3),
            "growth": round(self.growth_score, 3),
            "competition": round(self.competition_score, 3),
            "creative_gap": round(self.creative_gap_score, 3),
            "trend": self.trend_direction,
        }


@dataclass
class EvolutionSnapshot:
    """A complete snapshot of evolution state at a point in time.

    Used for rollback, comparison, and lineage tracking.
    """
    snapshot_id: str = ""
    generation: int = 0
    population_id: str = ""
    population_size: int = 0
    best_genome_id: str = ""
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    diversity: float = 0.0
    active_hypotheses: int = 0
    active_experiments: int = 0
    controller_phase: EvolutionPhase = EvolutionPhase.IDLE
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generation": self.generation,
            "best_fitness": round(self.best_fitness, 4),
            "avg_fitness": round(self.avg_fitness, 4),
            "diversity": round(self.diversity, 3),
            "phase": self.controller_phase.value,
        }


@dataclass
class EvolutionRun:
    """A complete evolution task — cross-lifecycle identity.

    Tracks one full evolution mission from start to end.
    Supports concurrent runs for different game categories.

    Example:
      Run A: "Find next Merge Puzzle opportunity" → 12 gens, winner genome_0831
      Run B: "Explore Sort Puzzle space" → 8 gens, winner genome_1204
      Run C: "AI Home Design opportunity" → 5 gens, winner genome_1501
    """
    run_id: str = ""
    objective: str = ""                      # "Find next Merge Puzzle opportunity"
    category: str = ""                       # "merge_puzzle", "sort_puzzle"
    phase: EvolutionPhase = EvolutionPhase.IDLE
    current_generation: int = 0
    max_generations: int = 100
    started_at: float = 0.0
    ended_at: float = 0.0
    winner_genome_id: str = ""
    total_genomes_created: int = 0
    total_experiments_run: int = 0
    total_budget_spent: float = 0.0
    status: str = "active"                   # active, completed, failed, archived
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""                 # Links all events in one cycle (Planner→Mutation→Eval→Select→Update)

    def __post_init__(self):
        if not self.run_id:
            self.run_id = f"run_{str(uuid.uuid4())[:8]}"
        if not self.started_at:
            self.started_at = time.time()
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "category": self.category,
            "phase": self.phase.value,
            "generation": f"{self.current_generation}/{self.max_generations}",
            "winner": self.winner_genome_id,
            "genomes_created": self.total_genomes_created,
            "experiments": self.total_experiments_run,
            "status": self.status,
            "correlation_id": self.correlation_id,
        }


@dataclass
class EvolutionEvent:
    """Unified evolution event format for V4.4 EventBus.

    All evolution events use this single format.
    event_type determines the event kind (OPPORTUNITY_DISCOVERED, etc.).

    Replay support: generation, actor, version, random_seed enable full
    event replay and audit trail for evolution debugging.
    random_seed is critical for deterministic mutation replay.

    correlation_id links all events within one evolution cycle
    (Planner → Mutation → Evaluation → Selection → Population Update).
    Critical for debugging and tracing full evolution pipelines.
    """
    event_id: str = ""
    event_type: str = ""                     # e.g., "GENOME_CREATED"
    run_id: str = ""                         # Which EvolutionRun
    correlation_id: str = ""                 # Links all events in one cycle (Planner→Mutation→Eval→Select→Update)
    entity_id: str = ""                      # genome_id, population_id, etc.
    generation: int = 0                      # Which generation this event belongs to
    timestamp: float = 0.0
    payload: Any = None
    source: str = ""                         # Which module emitted
    actor: str = ""                          # Which agent/strategy triggered (e.g., "guided_mutation")
    random_seed: int = 0                     # Random seed for deterministic replay
    confidence: float = 0.0                  # Confidence in this event's data
    version: str = "1.0"                     # Schema version for replay compatibility

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())[:8]
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "entity_id": self.entity_id,
            "generation": self.generation,
            "timestamp": self.timestamp,
            "source": self.source,
            "actor": self.actor,
            "random_seed": self.random_seed,
            "confidence": self.confidence,
            "version": self.version,
        }


class MutationStrategyType(str, Enum):
    """Types of mutation strategies for different gene dimensions."""
    PROMPT = "prompt"               # Hook, emotion, story text mutation
    GAMEPLAY = "gameplay"           # Game mechanic mutation
    REWARD = "reward"               # Reward mechanism mutation
    VISUAL = "visual"               # Visual style, camera, color mutation
    CHARACTER = "character"         # Character type mutation
    AUDIENCE = "audience"           # Target audience mutation
    HYBRID = "hybrid"               # Multi-gene combined mutation


# ═══════════════════════════════════════════════════════════
# Evolution Events (published via V4.4 EventBus)
#   All use the unified EvolutionEvent format above
# ═══════════════════════════════════════════════════════════

EVOLUTION_EVENT_TYPES = {
    "OPPORTUNITY_DISCOVERED": "Market opportunity found",
    "GENOME_CREATED": "New genome registered",
    "POPULATION_CREATED": "New generation created",
    "MUTATION_APPLIED": "Mutation applied to genome",
    "HYPOTHESIS_FORMED": "New hypothesis proposed",
    "HYPOTHESIS_VALIDATED": "Hypothesis confirmed/rejected",
    "EXPERIMENT_STARTED": "Experiment launched",
    "EXPERIMENT_COMPLETED": "Experiment completed",
    "FITNESS_UPDATED": "Fitness scores updated",
    "GENERATION_FINISHED": "Generation cycle completed",
    "EVOLUTION_CONVERGED": "Population converged",
    "EVOLUTION_DIVERGED": "Population lost diversity",
    "EXTINCTION_DETECTED": "All genomes failed",
    "CONTROLLER_DECISION": "Controller decision made",
    "ROLLBACK_TRIGGERED": "Rollback to previous generation",
    "ELITE_SELECTED": "Elite genomes selected",
    "DIVERSITY_WARNING": "Population diversity below threshold",
    "PLATEAU_DETECTED": "Fitness plateau detected",
}


# ═══════════════════════════════════════════════════════════
# Mutation Contract (Phase 2.0 — Interface Freeze)
#   All Mutation Engines must implement this contract.
#   Supports: Prompt, Gameplay, Hook, Reward, Visual, Character,
#             Audience, Hybrid mutation strategies.
# ═══════════════════════════════════════════════════════════

@dataclass
class MutationRequest:
    """Request to mutate a genome.

    Frozen interface — all mutation strategies use this.

    Supports three mutation categories:
      Gene Mutation:     change existing gene value (e.g., hook="rescue"→"escape")
      Structural Mutation: add/delete/merge genes (e.g., add new "reward" gene)
      Cross-over:        combine two genomes to produce offspring
    """
    request_id: str = ""
    genome_id: str = ""                      # Primary genome to mutate
    source_genomes: list[str] = field(default_factory=list)  # Additional parents (cross-over)
    strategy: MutationStrategyType = MutationStrategyType.PROMPT
    operators: list[MutationOperator] = field(default_factory=list)  # Allowed operators
    target_genes: list[str] = field(default_factory=list)  # Specific genes to mutate
    new_genes: list[dict[str, Any]] = field(default_factory=list)  # [{gene_type, value, ...}] for structural insert
    mutation_rate: float = 0.1               # P(mutation) per gene
    temperature: float = 1.0                 # 0 = conservative, 1 = aggressive
    constraints: dict[str, Any] = field(default_factory=dict)
    # Expected structure:
    #   "locked_genes": ["character", "emotion"]           # Cannot mutate
    #   "forbidden_values": {"hook": ["angry", "violent"]}  # Must not use
    #   "required_values": {"reward": True}                 # Must exist
    #   "max_cost": 0.5, "max_risk": 0.8
    context: dict[str, Any] = field(default_factory=dict)  # e.g., winner DNA, market data
    created_at: float = 0.0

    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "genome_id": self.genome_id,
            "source_genomes": self.source_genomes,
            "strategy": self.strategy.value,
            "operators": [o.value for o in self.operators],
            "target_genes": self.target_genes,
            "new_genes": self.new_genes,
            "mutation_rate": self.mutation_rate,
            "temperature": self.temperature,
        }


@dataclass
class MutationResult:
    """Result of a mutation operation.

    Includes the mutated genome, what changed, and risk assessment.

    mutation_hash is deterministic: hash(parent_genome + operator + params).
    Used for: dedup, replay verification, cache, A/B comparison.
    """
    result_id: str = ""
    request_id: str = ""
    original_genome_id: str = ""
    mutated_genome: Genome | None = None     # The mutated genome
    mutated_genes: list[str] = field(default_factory=list)  # Which genes changed
    gene_changes: list[dict[str, str]] = field(default_factory=list)  # [{gene, old, new}]
    operators_used: list[str] = field(default_factory=list)  # Which operators applied
    mutation_hash: str = ""                  # Deterministic hash for dedup/replay/cache
    mutation_cost: float = 0.0               # Actual cost incurred
    risk_score: float = 0.0                  # 0-1, actual risk
    confidence: float = 0.0                  # Confidence in mutation quality
    is_valid: bool = True                    # Whether mutation passed quality gate
    validation_errors: list[str] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self):
        if not self.result_id:
            self.result_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "original_genome_id": self.original_genome_id,
            "mutated_genome_id": self.mutated_genome.genome_id if self.mutated_genome else "",
            "mutated_genes": self.mutated_genes,
            "gene_changes": self.gene_changes,
            "operators_used": self.operators_used,
            "mutation_hash": self.mutation_hash,
            "mutation_cost": round(self.mutation_cost, 3),
            "risk_score": round(self.risk_score, 3),
            "confidence": round(self.confidence, 3),
            "is_valid": self.is_valid,
        }


@dataclass
class MutationStrategy:
    """Configuration for a mutation strategy.

    Defines how a specific gene type should be mutated.
    Different strategies for: Prompt, Gameplay, Hook, Reward, Visual, etc.
    """
    strategy_id: str = ""
    strategy_type: MutationStrategyType = MutationStrategyType.PROMPT
    name: str = ""                           # Human-readable name
    description: str = ""
    default_operators: list[MutationOperator] = field(default_factory=list)
    default_rate: float = 0.1
    default_temperature: float = 1.0
    max_cost: float = 0.5                    # Max mutation cost allowed
    max_risk: float = 0.8                    # Max mutation risk allowed
    quality_gate: dict[str, Any] = field(default_factory=dict)  # Validation rules
    target_gene_types: list[GeneType] = field(default_factory=list)
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.strategy_id:
            self.strategy_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "name": self.name,
            "default_operators": [o.value for o in self.default_operators],
            "default_rate": self.default_rate,
            "max_cost": self.max_cost,
            "max_risk": self.max_risk,
            "target_gene_types": [g.value for g in self.target_gene_types],
        }


@dataclass
class MutationReport:
    """Batch mutation report for a generation.

    Aggregates results from all mutations in one generation cycle.
    """
    report_id: str = ""
    run_id: str = ""
    generation: int = 0
    strategy_reports: dict[str, Any] = field(default_factory=dict)  # strategy → stats
    total_requests: int = 0
    total_mutations: int = 0
    valid_mutations: int = 0
    invalid_mutations: int = 0
    avg_cost: float = 0.0
    avg_risk: float = 0.0
    avg_confidence: float = 0.0
    beneficial_rate: float = 0.0              # Proportion that improved fitness
    harmful_rate: float = 0.0                # Proportion that decreased fitness
    best_operator: str = ""                  # Most effective operator this gen
    best_strategy: str = ""                  # Most effective strategy this gen
    results: list[MutationResult] = field(default_factory=list)
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.report_id:
            self.report_id = str(uuid.uuid4())[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "generation": self.generation,
            "total_requests": self.total_requests,
            "total_mutations": self.total_mutations,
            "valid": self.valid_mutations,
            "invalid": self.invalid_mutations,
            "avg_cost": round(self.avg_cost, 3),
            "avg_risk": round(self.avg_risk, 3),
            "beneficial_rate": round(self.beneficial_rate, 3),
            "harmful_rate": round(self.harmful_rate, 3),
            "best_operator": self.best_operator,
            "best_strategy": self.best_strategy,
        }


# ═══════════════════════════════════════════════════════════
# Default Fitness Weights
# ═══════════════════════════════════════════════════════════

DEFAULT_FITNESS_WEIGHTS: dict[str, float] = {
    FitnessComponent.CTR.value: 0.15,
    FitnessComponent.CVR.value: 0.15,
    FitnessComponent.ROAS_D1.value: 0.10,
    FitnessComponent.ROAS_D7.value: 0.25,
    FitnessComponent.ROAS_D30.value: 0.10,
    FitnessComponent.RETENTION_D1.value: 0.05,
    FitnessComponent.RETENTION_D7.value: 0.10,
    FitnessComponent.CPI.value: -0.05,         # Negative weight (lower is better)
    FitnessComponent.LTV.value: 0.05,
    FitnessComponent.DIVERSITY_BONUS.value: 0.03,
    FitnessComponent.NOVELTY_BONUS.value: 0.02,
}

# Composite fitness categories (for multi-monetization models)
DEFAULT_FITNESS_CATEGORIES: dict[str, list[str]] = {
    FitnessCategory.CREATIVE.value: [
        FitnessComponent.CTR.value,
        FitnessComponent.CVR.value,
        FitnessComponent.DIVERSITY_BONUS.value,
        FitnessComponent.NOVELTY_BONUS.value,
    ],
    FitnessCategory.BUSINESS.value: [
        FitnessComponent.ROAS_D1.value,
        FitnessComponent.ROAS_D7.value,
        FitnessComponent.ROAS_D30.value,
        FitnessComponent.CPI.value,
    ],
    FitnessCategory.USER.value: [
        FitnessComponent.RETENTION_D1.value,
        FitnessComponent.RETENTION_D7.value,
    ],
    FitnessCategory.LONG_TERM.value: [
        FitnessComponent.LTV.value,
        FitnessComponent.ROAS_D30.value,
        FitnessComponent.RETENTION_D7.value,
    ],
}


# ═══════════════════════════════════════════════════════════
# Default Evolution Parameters
# ═══════════════════════════════════════════════════════════

DEFAULT_EVOLUTION_CONFIG: dict[str, Any] = {
    "population": {
        "default_size": 100,
        "elite_count": 10,
        "min_diversity": 0.05,          # Below this → increase mutation
        "max_convergence": 0.95,        # Above this → explore new directions
        "extinction_threshold": 0.02,   # Below this avg fitness → extinction risk
    },
    "mutation": {
        "base_rate": 0.1,               # Base mutation probability
        "max_rate": 0.5,                # Max mutation probability (when diversity low)
        "min_rate": 0.02,               # Min mutation probability (when converged)
        "crossover_probability": 0.3,   # P(crossover) per generation
        "elite_preservation": 0.1,      # Top 10% preserved unchanged
    },
    "fitness": {
        "min_sample_size": 1000,        # Minimum impressions for reliable fitness
        "online_weight": 0.7,           # Weight for online vs offline fitness
        "plateau_generations": 5,       # Generations without improvement = plateau
        "improvement_threshold": 0.01,  # Min fitness improvement to not be plateau
    },
    "controller": {
        "exploit_threshold": 0.8,       # Confidence above this → exploit
        "explore_threshold": 0.3,       # Diversity below this → explore
        "max_generations": 100,         # Max generations before forced stop
        "rollback_window": 5,           # Max generations to rollback
    },
    "experiment": {
        "min_budget_per_arm": 50.0,     # Minimum budget per test arm
        "max_arms": 20,                 # Maximum concurrent test arms
        "min_runtime_hours": 24,        # Minimum experiment duration
        "confidence_level": 0.95,       # Statistical confidence for winner
    },
}


# ═══════════════════════════════════════════════════════════
# Mutation Hash — Deterministic SHA256 (Freeze v1.3)
# ═══════════════════════════════════════════════════════════

def compute_mutation_hash(parent_genome_id: str,
                          operator: str,
                          parameters: dict[str, Any] | None = None,
                          schema_version: str = "1.3") -> str:
    """Compute a deterministic SHA256 hash for a mutation.

    Hash = SHA256(schema_version + parent_genome_id + operator + normalized_params)

    Normalization rules:
      - JSON keys sorted alphabetically
      - Float values rounded to 6 decimal places
      - String values UTF-8 encoded
      - All inputs lowercased before hashing

    Uses:
      - Mutation dedup (same parent + same operator + same params → same hash)
      - Replay verification (hash must match original)
      - Cache key (mutation cache via hash)
      - A/B comparison (same hash = same mutation)
      - Mutation history indexing

    Deterministic guarantee: same input → same output every time.
    """
    params = parameters or {}

    # Normalize: sort keys, round floats, convert to canonical JSON
    normalized = _normalize_params(params)
    params_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)

    # Build canonical input string
    canonical = f"{schema_version}|{parent_genome_id}|{operator}|{params_json}"
    canonical_bytes = canonical.encode("utf-8")

    return hashlib.sha256(canonical_bytes).hexdigest()[:16]


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Normalize mutation parameters for deterministic hashing.

    - Sort keys alphabetically
    - Round floats to 6 decimal places
    - Recurse into nested dicts
    """
    result: dict[str, Any] = {}
    for key in sorted(params.keys()):
        value = params[key]
        if isinstance(value, float):
            result[key] = round(value, 6)
        elif isinstance(value, dict):
            result[key] = _normalize_params(value)
        elif isinstance(value, list):
            result[key] = [_normalize_params(v) if isinstance(v, dict)
                           else round(v, 6) if isinstance(v, float)
                           else v
                           for v in value]
        else:
            result[key] = value
    return result