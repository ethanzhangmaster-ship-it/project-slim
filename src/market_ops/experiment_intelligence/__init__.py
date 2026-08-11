"""Experiment Intelligence Layer — E9.9.

Converts E9.8 Creative Mutations into structured experiments,
analyzes results, and generates learning feedback for E9.7.

Modules:
  - schemas: ExperimentCandidate, ExperimentPlan, ExperimentResult, etc.
  - experiment_selector: ExperimentSelector
  - experiment_planner: ExperimentPlanner
  - ab_test_designer: ABTestDesigner
  - budget_allocator: BudgetAllocator, BudgetMode
  - experiment_tracker: ExperimentTracker, ExperimentStatus
  - result_analyzer: ResultAnalyzer
  - feedback_engine: FeedbackEngine
  - experiment_engine: ExperimentEngine, run_e99_pipeline
  - export: ExperimentExporter
"""

from .schemas import (
    ExperimentCandidate,
    ExperimentPlan,
    ExperimentResult,
    FeedbackSignal,
    PerformanceSnapshot,
    ExperimentStatus,
    BudgetMode,
    ExperimentDecision,
)
from .experiment_selector import ExperimentSelector
from .experiment_planner import ExperimentPlanner
from .ab_test_designer import ABTestDesigner
from .budget_allocator import BudgetAllocator
from .experiment_tracker import ExperimentTracker
from .result_analyzer import ResultAnalyzer
from .feedback_engine import FeedbackEngine
from .experiment_engine import ExperimentEngine, run_e99_pipeline
from .export import ExperimentExporter

__all__ = [
    # Schemas
    "ExperimentCandidate",
    "ExperimentPlan",
    "ExperimentResult",
    "FeedbackSignal",
    "PerformanceSnapshot",
    "ExperimentStatus",
    "BudgetMode",
    "ExperimentDecision",
    # Modules
    "ExperimentSelector",
    "ExperimentPlanner",
    "ABTestDesigner",
    "BudgetAllocator",
    "ExperimentTracker",
    "ResultAnalyzer",
    "FeedbackEngine",
    "ExperimentEngine",
    "run_e99_pipeline",
    # Export
    "ExperimentExporter",
]