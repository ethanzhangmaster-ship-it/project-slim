"""
E15.2.6 — IAA Revenue Optimization Autopilot.

Orchestration layer on top of the proven operation.optimizer engine. See
operation/revenue_optimizer/scheduler/revenue_cycle.py for the daily loop.

Key reuse (single source of truth, no rewrite):
  * Opportunity detection -> 6 intel rules inside MonetizationDailyReport
  * Lift math             -> ABExperimentGenerator (identical formulas)
  * Impact measurement    -> ImpactMeasurer (diff-in-diff)
  * Verdict               -> WinnerSelector (KEEP/ROLLBACK)
  * Memory                -> OptimizationMemory (JSONL)
"""
from operation.revenue_optimizer.models import (
    ChangeAction, ChangePackage, ExperimentResult, OptimizationExperiment,
    PredictionResult, RevenueOpportunity,
)
from operation.revenue_optimizer.opportunity import (
    OpportunityDetector, OpportunityRanker, OpportunityScorer,
)
from operation.revenue_optimizer.prediction import (
    ConfidenceEstimator, LiftModel, RevenuePredictor,
)
from operation.revenue_optimizer.experiment import (
    ExperimentEvaluator, ExperimentPlanner, TrafficAllocator,
)
from operation.revenue_optimizer.executor import (
    ApprovalGate, ChangePackageBuilder, RollbackPlanner,
)
from operation.revenue_optimizer.optimizer import (
    BidFloorOptimizer, NetworkOptimizer, WaterfallOptimizer,
)
from operation.revenue_optimizer.scheduler import RevenueCycle

__all__ = [
    "RevenueOpportunity", "PredictionResult", "ExperimentResult",
    "OptimizationExperiment", "ChangeAction", "ChangePackage",
    "OpportunityDetector", "OpportunityScorer", "OpportununityRanker",
    "LiftModel", "ConfidenceEstimator", "RevenuePredictor",
    "ExperimentPlanner", "TrafficAllocator", "ExperimentEvaluator",
    "ChangePackageBuilder", "ApprovalGate", "RollbackPlanner",
    "NetworkOptimizer", "BidFloorOptimizer", "WaterfallOptimizer",
    "RevenueCycle",
]
