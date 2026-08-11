"""E10.2 Phase 5 — Optimization Engine.

Autonomous optimization loop that converts feedback signals
into executable campaign mutations. The system evolves from
an execution platform into a growth controller.

Modules:
  - policy_engine: LearningSignal → OptimizationDecision
  - scale_controller: Safe budget scaling (max 30%)
  - kill_controller: Campaign termination
  - experiment_allocator: Multi-campaign budget allocation
  - mutation_planner: OptimizationDecision → ExecutionTask
  - optimization_orchestrator: Full pipeline orchestrator
  - exceptions: Optimization error types
"""

from .policy_engine import OptimizationPolicy
from .scale_controller import ScaleController
from .kill_controller import KillController
from .experiment_allocator import ExperimentAllocator
from .mutation_planner import MutationPlanner
from .optimization_orchestrator import OptimizationOrchestrator
from .exceptions import (
    OptimizationError,
    PolicyViolationError,
    ScaleLimitError,
    NoScorableCampaignsError,
)

__all__ = [
    "OptimizationPolicy",
    "ScaleController",
    "KillController",
    "ExperimentAllocator",
    "MutationPlanner",
    "OptimizationOrchestrator",
    "OptimizationError",
    "PolicyViolationError",
    "ScaleLimitError",
    "NoScorableCampaignsError",
]