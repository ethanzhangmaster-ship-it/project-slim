"""E15.3.2 Autonomous Decision Loop — 模块导出."""

from .evaluator import GoalEvaluator, OpportunityEvaluator, PerformanceEvaluator
from .executor_bridge import ExecutorBridge
from .learner import Learner
from .loop import AutonomousDecisionLoop
from .models import (
    AnomalySignal,
    CycleOutcome,
    CycleResult,
    CycleState,
    CycleSummary,
    DecisionCycle,
    EnvironmentState,
    GoalEvaluation,
    GoalHealth,
    OpportunitySignal,
    TrendSignal,
)
from .planner_bridge import PlannerBridge
from .state_machine import (
    FORBIDDEN_TRANSITIONS,
    VALID_TRANSITIONS,
    CycleStateMachine,
)

__all__ = [
    # Models
    "CycleState",
    "GoalHealth",
    "CycleOutcome",
    "AnomalySignal",
    "TrendSignal",
    "OpportunitySignal",
    "EnvironmentState",
    "GoalEvaluation",
    "DecisionCycle",
    "CycleResult",
    "CycleSummary",
    # State Machine
    "VALID_TRANSITIONS",
    "FORBIDDEN_TRANSITIONS",
    "CycleStateMachine",
    # Evaluators
    "GoalEvaluator",
    "OpportunityEvaluator",
    "PerformanceEvaluator",
    # Bridges
    "PlannerBridge",
    "ExecutorBridge",
    "Learner",
    # Core Loop
    "AutonomousDecisionLoop",
]