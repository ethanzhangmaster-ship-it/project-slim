"""Production Hardening Module for V4.5.4.

Provides production-grade reliability:
- State Machine: Generation state tracking
- Queue System: Priority and retry queues
- Cost Intelligence: Budget and cost control
- Asset Lineage: Video-to-Blueprint tracking
- QA Agent: Visual and Marketing quality assessment
- Recovery: Failure detection and auto recovery
- Load Test: Production stress and resilience testing
"""

from .state_machine import (
    GenerationState,
    StateTransition,
    TransitionRecord,
    StateStore
)

from .queue import (
    Job,
    JobQueue,
    PriorityQueue,
    RetryQueue,
    DeadLetterQueue
)

from .cost import (
    CostController,
    CostEstimate,
    CostPredictor,
    BudgetPolicy,
    BudgetPolicyManager
)

from .lineage import (
    AssetNode,
    AssetGraph,
    LineageStore
)

from .qa_agent import (
    QAScorer,
    QAScore,
    QAGrade,
    VisualChecker,
    MarketingChecker
)

from .recovery import (
    FailureDetector,
    AutoRecovery,
    RecoveryPlan,
    CheckpointManager,
    FailureType,
    FailureSeverity
)

from .load_test import (
    RuntimeStressTest,
    FailureInjectionTest,
    FailureScenario
)

__all__ = [
    # State Machine
    "GenerationState",
    "StateTransition",
    "TransitionRecord",
    "StateStore",
    
    # Queue
    "Job",
    "JobQueue",
    "PriorityQueue",
    "RetryQueue",
    "DeadLetterQueue",
    
    # Cost
    "CostController",
    "CostEstimate",
    "CostPredictor",
    "BudgetPolicy",
    "BudgetPolicyManager",
    
    # Lineage
    "AssetNode",
    "AssetGraph",
    "LineageStore",
    
    # QA Agent
    "QAScorer",
    "QAScore",
    "QAGrade",
    "VisualChecker",
    "MarketingChecker",
    
    # Recovery
    "FailureDetector",
    "AutoRecovery",
    "RecoveryPlan",
    "CheckpointManager",
    "FailureType",
    "FailureSeverity",
    
    # Load Test
    "RuntimeStressTest",
    "FailureInjectionTest",
    "FailureScenario"
]