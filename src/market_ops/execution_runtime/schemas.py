"""E10.1 Execution Runtime — Core Data Models.

Execution Plane Foundation: converts E9.9.5 GrowthAction
into executable ExecutionTask with state machine tracking.

Core entities:
  - ExecutionTask: growth action → executable task
  - ExecutionResult: task execution outcome
  - ApprovalRequest: human-in-the-loop approval
  - ExecutionEvent: audit trail event log
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════

class ExecutionStatus(str, Enum):
    """9-state execution lifecycle."""
    CREATED = "CREATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLBACK_PENDING = "ROLLBACK_PENDING"
    ROLLED_BACK = "ROLLED_BACK"


class ActionType(str, Enum):
    """Growth action types — MUST match E9.9.5 GrowthAction output.

    E10 does NOT define new actions. Only executes what E9.9.5 decides.
    """
    SCALE = "SCALE"
    KILL = "KILL"
    WATCH = "WATCH"
    RETEST = "RETEST"


class ExecutionTarget(str, Enum):
    """UA platform targets for execution.

    Phase 1: interface definition only, no real API calls.
    """
    META_ADS = "META_ADS"
    GOOGLE_ADS = "GOOGLE_ADS"
    APP_STORE = "APP_STORE"
    PLAY_STORE = "PLAY_STORE"


class ApprovalStatus(str, Enum):
    """Approval request lifecycle."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ESCALATED = "ESCALATED"


class ApprovalLevel(str, Enum):
    """Approval tier: who must approve."""
    AUTO = "AUTO"
    HUMAN = "HUMAN"
    MANAGER = "MANAGER"


class EventType(str, Enum):
    """Execution event types for audit trail."""
    TASK_CREATED = "TASK_CREATED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    ROLLBACK_STARTED = "ROLLBACK_STARTED"
    ROLLBACK_COMPLETED = "ROLLBACK_COMPLETED"
    STATE_CHANGED = "STATE_CHANGED"


class CollectionEventType(str, Enum):
    """Result collection event types."""
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    RESULT_COLLECTED = "RESULT_COLLECTED"
    PERFORMANCE_UPDATED = "PERFORMANCE_UPDATED"
    COLLECTION_FAILED = "COLLECTION_FAILED"


class FeedbackType(str, Enum):
    """Learning feedback signal classification."""
    SUCCESS = "SUCCESS"
    NEUTRAL = "NEUTRAL"
    WARNING = "WARNING"
    FAILURE = "FAILURE"


# ═══════════════════════════════════════════════════════════
# ExecutionTask
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutionTask:
    """Executable growth action derived from E9.9.5 GrowthAction.

    Represents a single growth operation to be executed on
    a target platform. Created by the execution engine from
    E9.9.5 GrowthActionResponse.
    """
    task_id: str = ""
    correlation_id: str = ""

    # Action
    action_type: str = ActionType.WATCH.value
    # SCALE / KILL / WATCH / RETEST

    # Source
    creative_id: str = ""
    experiment_id: str = ""
    growth_decision_id: str = ""

    # Target
    target_platform: str = ExecutionTarget.META_ADS.value
    target_object: str = ""           # campaign_id, adset_id, etc.

    # Budget
    budget_change: dict[str, float] = field(default_factory=lambda: {"before": 0.0, "after": 0.0})
    scale_multiplier: float = 1.0

    # Risk
    risk_level: str = "SAFE"          # from E9.9.5 RiskReport

    # Approval
    approval_required: bool = False

    # Status
    status: str = ExecutionStatus.CREATED.value

    # Timing
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "action_type": self.action_type,
            "creative_id": self.creative_id,
            "experiment_id": self.experiment_id,
            "growth_decision_id": self.growth_decision_id,
            "target_platform": self.target_platform,
            "target_object": self.target_object,
            "budget_change": {
                "before": round(self.budget_change.get("before", 0.0), 2),
                "after": round(self.budget_change.get("after", 0.0), 2),
            },
            "scale_multiplier": round(self.scale_multiplier, 2),
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ═══════════════════════════════════════════════════════════
# ExecutionResult
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutionResult:
    """Outcome of a single ExecutionTask.

    Captures platform response, actual changes, and any
    errors encountered during execution.
    """
    result_id: str = ""
    task_id: str = ""

    # Status
    status: str = ExecutionStatus.COMPLETED.value

    # Platform response
    platform_response: dict[str, Any] = field(default_factory=dict)

    # Actual changes
    actual_change: dict[str, float] = field(default_factory=lambda: {"before": 0.0, "after": 0.0})

    # Error
    error_message: str = ""
    retry_count: int = 0

    # Metrics
    metrics: dict[str, Any] = field(default_factory=dict)

    # Timing
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.result_id:
            self.result_id = str(uuid.uuid4())
        if not self.completed_at:
            self.completed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "status": self.status,
            "platform_response": self.platform_response,
            "actual_change": {
                "before": round(self.actual_change.get("before", 0.0), 2),
                "after": round(self.actual_change.get("after", 0.0), 2),
            },
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metrics": self.metrics,
            "completed_at": self.completed_at,
        }


# ═══════════════════════════════════════════════════════════
# ApprovalRequest
# ═══════════════════════════════════════════════════════════

@dataclass
class ApprovalRequest:
    """Human-in-the-loop approval request.

    Generated when an ExecutionTask exceeds auto-approval
    thresholds (risk level, budget change, action type).
    """
    request_id: str = ""
    task_id: str = ""

    # Risk
    risk_level: str = "SAFE"

    # Reason
    reason: str = ""

    # People
    requested_by: str = "E10.1"
    approved_by: str = ""

    # Status
    status: str = ApprovalStatus.PENDING.value

    # Timing
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "status": self.status,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# ApprovalDecision
# ═══════════════════════════════════════════════════════════

@dataclass
class ApprovalDecision:
    """Outcome of an approval gate check.

    Created by ApprovalGate to route tasks through the
    correct approval tier (AUTO / HUMAN / MANAGER).
    """
    decision_id: str = ""
    task_id: str = ""

    # Tier
    approval_level: str = ApprovalLevel.AUTO.value

    # Status
    status: str = ApprovalStatus.PENDING.value

    # Reasoning
    reason: str = ""

    # Timing
    created_at: str = ""
    resolved_at: str = ""

    def __post_init__(self) -> None:
        if not self.decision_id:
            self.decision_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "approval_level": self.approval_level,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


# ═══════════════════════════════════════════════════════════
# ExecutionEvent
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutionEvent:
    """Audit trail event for execution traceability.

    Every state transition and significant action generates
    an ExecutionEvent for full execution replay capability.
    """
    event_id: str = ""
    task_id: str = ""

    # Event type
    event_type: str = EventType.STATE_CHANGED.value

    # State transition
    old_state: str = ""
    new_state: str = ""

    # Timing
    timestamp: str = ""

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════
# ExecutionRecord
# ═══════════════════════════════════════════════════════════

@dataclass
class ExecutionRecord:
    """Record of a complete execution lifecycle.

    Created by ResultCollector from ExecutionResult.
    Captures what happened, when, and the final outcome.
    """
    record_id: str = ""
    task_id: str = ""

    action_type: str = ""
    target_platform: str = ""

    start_time: str = ""
    end_time: str = ""

    final_status: str = ExecutionStatus.COMPLETED.value
    approval_status: str = ApprovalStatus.APPROVED.value

    execution_duration_ms: int = 0

    platform_response: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.start_time:
            self.start_time = datetime.now(timezone.utc).isoformat()
        if not self.end_time:
            self.end_time = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "action_type": self.action_type,
            "target_platform": self.target_platform,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "final_status": self.final_status,
            "approval_status": self.approval_status,
            "execution_duration_ms": self.execution_duration_ms,
            "platform_response": self.platform_response,
            "error_message": self.error_message,
        }


# ═══════════════════════════════════════════════════════════
# PerformanceSnapshot
# ═══════════════════════════════════════════════════════════

@dataclass
class PerformanceSnapshot:
    """Post-execution performance metrics.

    Generated by PerformanceTracker from ExecutionResult.
    Captures business impact: impressions, clicks, spend, ROAS, etc.
    """
    snapshot_id: str = ""
    task_id: str = ""

    impressions: int = 0
    clicks: int = 0
    conversions: int = 0

    spend: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0

    ctr: float = 0.0
    cvr: float = 0.0

    status: str = ""

    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = str(uuid.uuid4())
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "task_id": self.task_id,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend": round(self.spend, 2),
            "revenue": round(self.revenue, 2),
            "roas": round(self.roas, 2),
            "ctr": round(self.ctr, 4),
            "cvr": round(self.cvr, 4),
            "status": self.status,
            "recorded_at": self.recorded_at,
        }


# ═══════════════════════════════════════════════════════════
# LearningSignal
# ═══════════════════════════════════════════════════════════

@dataclass
class LearningSignal:
    """Standardized learning feedback from execution results.

    Generated by FeedbackLoop from PerformanceSnapshot.
    Consumed by E9.9.5 Learning Layer for model updates.
    """
    signal_id: str = ""
    task_id: str = ""

    action_type: str = ""
    feedback_type: str = FeedbackType.NEUTRAL.value

    confidence: float = 0.0

    metrics: dict[str, Any] = field(default_factory=dict)

    recommendation: str = ""

    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "task_id": self.task_id,
            "action_type": self.action_type,
            "feedback_type": self.feedback_type,
            "confidence": round(self.confidence, 2),
            "metrics": self.metrics,
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# ContractVersion
# ═══════════════════════════════════════════════════════════

class ContractVersion:
    """Frozen schema version identifiers for JSON export contracts.

    Used by ExportService to tag output files with a version
    string, enabling consumers to detect breaking changes.
    """
    EXECUTION = "E10.1.execution.v1"
    PERFORMANCE = "E10.1.performance.v1"
    FEEDBACK = "E10.1.feedback.v1"
    API = "E10.1.v1"


# ═══════════════════════════════════════════════════════════
# APIResponse
# ═══════════════════════════════════════════════════════════

@dataclass
class APIResponse:
    """Standard wrapper for all RuntimeAPI responses.

    Provides a uniform envelope: success flag, version tag,
    data payload, and optional error message.
    """
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    version: str = ContractVersion.API

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "version": self.version,
            "data": self.data,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════
# Conversion Helpers
# ═══════════════════════════════════════════════════════════

def from_growth_action(action: dict[str, Any]) -> ExecutionTask:
    """Convert E9.9.5 GrowthAction dict to ExecutionTask.

    This is the bridge between E9.9.5 Decision Plane and
    E10.1 Execution Plane. Accepts a dict to avoid importing
    E9.9.5 internal schemas.

    Args:
        action: Dict with keys matching E9.9.5 GrowthActionItem:
            {creative_id, action, budget_change: {current, target},
             confidence, reason}

    Returns:
        ExecutionTask ready for execution
    """
    budget_change = action.get("budget_change", {})
    risk_level = "SAFE"
    reasons = action.get("reason", [])
    for r in reasons:
        if "risk CRITICAL" in str(r):
            risk_level = "CRITICAL"
        elif "risk WARNING" in str(r):
            risk_level = "WARNING"

    return ExecutionTask(
        task_id=str(uuid.uuid4()),
        action_type=action.get("action", "WATCH"),
        creative_id=action.get("creative_id", ""),
        budget_change={
            "before": budget_change.get("current", 0.0),
            "after": budget_change.get("target", 0.0),
        },
        scale_multiplier=(
            budget_change.get("target", 0.0) / max(1.0, budget_change.get("current", 1.0))
        ),
        risk_level=risk_level,
        approval_required=(
            risk_level in ("WARNING", "CRITICAL")
            or action.get("action") == "KILL"
        ),
        status=ExecutionStatus.CREATED.value,
    )