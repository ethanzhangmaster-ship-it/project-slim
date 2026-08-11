"""Evolution Layer — Creative Evolution System.

E9.8: Creative Mutation Engine (NEW)
  - schemas: CreativeGenome, MutationRecord, MutationCandidate, etc.
  - winner_dna_analyzer: WinnerDNAAnalyzer
  - failure_pattern_analyzer: FailurePatternAnalyzer
  - mutation_strategy: MutationStrategyEngine
  - creative_genome_mutator: CreativeGenomeMutator
  - opportunity_detector: OpportunityDetector
  - mutation_ranker: MutationRanker
  - evolution_engine: EvolutionEngine, run_e98_pipeline

Phase D (legacy):
  - mutation_orchestrator: CreativeMutationOrchestrator
  - experiment_engine: AutonomousExperimentEngine
  - evolution_memory: EvolutionMemory
"""

# E9.8
from .schemas import (
    CreativeGenome, MutationRecord, MutationCandidate,
    WinnerPattern, FailurePattern, FailureAnalysis,
    MutationStrategy, EvolutionReport, MarketOpportunity,
)
from .winner_dna_analyzer import WinnerDNAAnalyzer
from .failure_pattern_analyzer import FailurePatternAnalyzer
from .mutation_strategy import MutationStrategyEngine
from .creative_genome_mutator import CreativeGenomeMutator
from .opportunity_detector import OpportunityDetector
from .mutation_ranker import MutationRanker
from .evolution_engine import EvolutionEngine, run_e98_pipeline
from .export import EvolutionExporter

# Phase D (legacy)
from .mutation_orchestrator import CreativeMutationOrchestrator
from .experiment_engine import AutonomousExperimentEngine, ExperimentDecision
from .evolution_memory import EvolutionMemory, CreativeIntelligenceModel

__all__ = [
    # E9.8
    "CreativeGenome", "MutationRecord", "MutationCandidate",
    "WinnerPattern", "FailurePattern", "FailureAnalysis",
    "MutationStrategy", "EvolutionReport", "MarketOpportunity",
    "WinnerDNAAnalyzer",
    "FailurePatternAnalyzer",
    "MutationStrategyEngine",
    "CreativeGenomeMutator",
    "OpportunityDetector",
    "MutationRanker",
    "EvolutionEngine", "run_e98_pipeline", "EvolutionExporter",
    # Phase D
    "CreativeMutationOrchestrator",
    "AutonomousExperimentEngine", "ExperimentDecision",
    "EvolutionMemory", "CreativeIntelligenceModel",
]
