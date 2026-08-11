"""E10.1 Execution Runtime — Execution Plane Foundation.

Converts E9.9.5 GrowthAction into executable ExecutionTask
with state machine tracking and human-in-the-loop approval.

  E9.9.5 GrowthAction
        │
        ▼
  ExecutionTask
        │
        ▼
  Execution Status Machine
        │
        ▼
  ExecutionResult

Modules:
  - schemas: ExecutionTask, ExecutionResult, ApprovalRequest, ExecutionEvent
  - export: ExecutionExporter
  - (Phase 2+) execution_engine, approval_gate, etc.
"""

from .schemas import (
    ExecutionTask,
    ExecutionResult,
    ExecutionRecord,
    PerformanceSnapshot,
    ApprovalRequest,
    ApprovalDecision,
    ExecutionEvent,
    ExecutionStatus,
    ActionType,
    ExecutionTarget,
    ApprovalStatus,
    ApprovalLevel,
    EventType,
    CollectionEventType,
    FeedbackType,
    LearningSignal,
    ContractVersion,
    APIResponse,
    from_growth_action,
)
from .export import ExecutionExporter
from .mock_adapter import MockPlatformAdapter
from .execution_engine import ExecutionEngine
from .approval_workflow import ApprovalWorkflow
from .approval_gate import ApprovalGate
from .performance_tracker import PerformanceTracker
from .result_collector import ResultCollector
from .feedback_loop import FeedbackLoop
from .contract_schema import SchemaValidator
from .export_service import ExportService
from .runtime_api import RuntimeAPI
from .adapter_executor import AdapterExecutor
from .adapters import (
    PlatformAdapter,
    AdapterResult,
    AdapterRegistry,
    AdapterError,
    AdapterNotFoundError,
    AdapterAuthenticationError,
    AdapterRateLimitError,
)
from .campaign_schema import (
    CampaignIdentity,
    CampaignMutation,
    CampaignSnapshot,
    CampaignStatus,
)
from .campaign_registry import CampaignRegistry
from .budget_guard import BudgetGuard, BudgetGuardResult, BudgetGuardError
from .result_mapper import PlatformResultMapper
from .rate_limit_controller import RateLimitController, RateLimitStatus
from .adapter_retry import RetryEngine, RetryExhaustedError, RetryDecision
from .feedback_mapper import FeedbackMapper
from .attribution import (
    AttributionTracker,
    AttributionMetrics,
    AdjustTracker,
    AdjustConfig,
    AppsFlyerTracker,
    AppsFlyerConfig,
    MetricNormalizer,
    PerformanceCollector,
    AttributionError,
)
from .optimization_schema import (
    OptimizationDecision,
    MutationPlan,
    CampaignScore,
)
from .optimization import (
    OptimizationPolicy,
    ScaleController,
    KillController,
    ExperimentAllocator,
    MutationPlanner,
    OptimizationOrchestrator,
    OptimizationError,
)

__all__ = [
    # Schemas
    "ExecutionTask",
    "ExecutionResult",
    "ExecutionRecord",
    "PerformanceSnapshot",
    "ApprovalRequest",
    "ApprovalDecision",
    "ExecutionEvent",
    "LearningSignal",
    "APIResponse",
    # Enums
    "ExecutionStatus",
    "ActionType",
    "ExecutionTarget",
    "ApprovalStatus",
    "ApprovalLevel",
    "EventType",
    "CollectionEventType",
    "FeedbackType",
    # Helpers
    "from_growth_action",
    "ContractVersion",
    # Export
    "ExecutionExporter",
    # E10.1 Modules
    "MockPlatformAdapter",
    "ExecutionEngine",
    "ApprovalWorkflow",
    "ApprovalGate",
    "PerformanceTracker",
    "ResultCollector",
    "FeedbackLoop",
    "SchemaValidator",
    "ExportService",
    "RuntimeAPI",
    # E10.2 Adapter Layer
    "AdapterExecutor",
    "PlatformAdapter",
    "AdapterResult",
    "AdapterRegistry",
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterAuthenticationError",
    "AdapterRateLimitError",
    # E10.2 Phase 3 — Campaign Lifecycle
    "CampaignIdentity",
    "CampaignMutation",
    "CampaignSnapshot",
    "CampaignStatus",
    "CampaignRegistry",
    "BudgetGuard",
    "BudgetGuardResult",
    "BudgetGuardError",
    "PlatformResultMapper",
    "RateLimitController",
    "RateLimitStatus",
    "RetryEngine",
    "RetryExhaustedError",
    "RetryDecision",
    # E10.2 Phase 4 — Attribution + Feedback
    "FeedbackMapper",
    # E10.2 Phase 4 — Attribution
    "AttributionTracker",
    "AttributionMetrics",
    "AdjustTracker",
    "AdjustConfig",
    "AppsFlyerTracker",
    "AppsFlyerConfig",
    "MetricNormalizer",
    "PerformanceCollector",
    "AttributionError",
    # E10.2 Phase 5 — Optimization Engine
    "OptimizationDecision",
    "MutationPlan",
    "CampaignScore",
    "OptimizationPolicy",
    "ScaleController",
    "KillController",
    "ExperimentAllocator",
    "MutationPlanner",
    "OptimizationOrchestrator",
    "OptimizationError",
]