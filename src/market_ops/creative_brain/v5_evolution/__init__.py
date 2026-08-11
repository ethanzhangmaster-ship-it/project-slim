"""V5.0 Autonomous Creative Evolution Layer.

Phase 1 — Evolution Core (6 modules):
  - EvolutionRunManager: cross-lifecycle evolution task management
  - GenomeManager: genome CRUD + fitness history
  - PopulationManager: generation management + elite selection
  - FitnessCalculator: multi-dimensional fitness scoring
  - EvolutionMemory: evolution history + lineage tracking

Phase 2 — Mutation Engine (9 modules):
  - Foundation: exceptions, random context, registry, validator, utils
  - gene_mutation, structural_mutation, crossover_engine
  - mutation_planner, mutation_engine, mutation_evaluator
  - mutation_selector, mutation_pipeline

Architecture: event-driven with V4.4 EventBus.
  V4 Runtime → EventBus → V5 Evolution (V4 doesn't know V5 exists)
"""

from .schemas import (
    # Enums
    EvolutionPhase,
    GeneType,
    MutationOperator,
    MutationStrategyType,
    HypothesisStatus,
    ExperimentStatus,
    OpportunitySource,
    OpportunityCategory,
    EvolutionDecisionType,
    FitnessComponent,
    FitnessCategory,
    # Schemas
    Gene,
    Genome,
    Species,
    Population,
    Fitness,
    Hypothesis,
    EvolutionExperiment,
    EvolutionDecision,
    MarketOpportunity,
    EvolutionSnapshot,
    EvolutionRun,
    EvolutionEvent,
    # Mutation Contract
    MutationRequest,
    MutationResult,
    MutationStrategy,
    MutationReport,
    # Config
    EVOLUTION_EVENT_TYPES,
    DEFAULT_FITNESS_WEIGHTS,
    DEFAULT_FITNESS_CATEGORIES,
    DEFAULT_EVOLUTION_CONFIG,
    # Utility
    compute_mutation_hash,
)

from .evolution_run import EvolutionRunManager
from .genome_manager import GenomeManager
from .population_manager import PopulationManager
from .fitness_calculator import FitnessCalculator
from .evolution_memory import EvolutionMemory

# Mutation API v1.4
from .mutation_api import (
    MutationPlanner,
    MutationEngine,
    MutationEvaluator,
    MutationSelector,
    MutationReplay,
    MUTATION_API_CLASSES,
    MUTATION_API_METHODS,
)

# Phase 2 — Mutation Engine Foundation
from .mutation_exceptions import (
    MutationError,
    MutationValidationError,
    MutationOperatorError,
    MutationRegistryError,
    MutationReplayError,
    MutationConstraintError,
)
from .random_context import RandomContext, with_seed
from .mutation_registry import (
    register,
    get_operator,
    list_operators,
    get_operator_meta,
    get_all_metadata,
    unregister,
    clear_registry,
    is_registered,
)
from .constraint_validator import validate, validate_strict
from .mutation_utils import (
    clone_genome,
    build_mutation_result,
    track_gene_change,
    pick_random_gene,
    pick_random_value,
    should_mutate,
    calculate_mutation_cost,
)

# Phase 2.1 — Gene Mutation
from .gene_mutation import GeneMutationEngine

__all__ = [
    # Enums
    "EvolutionPhase",
    "GeneType",
    "MutationOperator",
    "MutationStrategyType",
    "HypothesisStatus",
    "ExperimentStatus",
    "OpportunitySource",
    "OpportunityCategory",
    "EvolutionDecisionType",
    "FitnessComponent",
    "FitnessCategory",
    # Schemas
    "Gene",
    "Genome",
    "Species",
    "Population",
    "Fitness",
    "Hypothesis",
    "EvolutionExperiment",
    "EvolutionDecision",
    "MarketOpportunity",
    "EvolutionSnapshot",
    "EvolutionRun",
    "EvolutionEvent",
    # Mutation Contract
    "MutationRequest",
    "MutationResult",
    "MutationStrategy",
    "MutationReport",
    # Config
    "EVOLUTION_EVENT_TYPES",
    "DEFAULT_FITNESS_WEIGHTS",
    "DEFAULT_FITNESS_CATEGORIES",
    "DEFAULT_EVOLUTION_CONFIG",
    # Phase 1 Core
    "EvolutionRunManager",
    "GenomeManager",
    "PopulationManager",
    "FitnessCalculator",
    "EvolutionMemory",
    # Mutation API v1.4
    "MutationPlanner",
    "MutationEngine",
    "MutationEvaluator",
    "MutationSelector",
    "MutationReplay",
    "MUTATION_API_CLASSES",
    "MUTATION_API_METHODS",
    # Utility
    "compute_mutation_hash",
    # Phase 2 — Foundation Exceptions
    "MutationError",
    "MutationValidationError",
    "MutationOperatorError",
    "MutationRegistryError",
    "MutationReplayError",
    "MutationConstraintError",
    # Phase 2 — Foundation Random Context
    "RandomContext",
    "with_seed",
    # Phase 2 — Foundation Registry
    "register",
    "get_operator",
    "list_operators",
    "get_operator_meta",
    "get_all_metadata",
    "unregister",
    "clear_registry",
    "is_registered",
    # Phase 2 — Foundation Validator
    "validate",
    "validate_strict",
    # Phase 2 — Foundation Utils
    "clone_genome",
    "build_mutation_result",
    "track_gene_change",
    "pick_random_gene",
    "pick_random_value",
    "should_mutate",
    "calculate_mutation_cost",
    # Phase 2.1 — Gene Mutation
    "GeneMutationEngine",
]