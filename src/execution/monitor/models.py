"""P2.5.1 ExecutionEvent Model + 核心域模型（Execution Observability Layer）。

P2.5 的定位：Execution Observability Layer（执行可观测层）。
解决「执行之后，系统不知道发生了什么」——只观察，不做决策、不修改结果、
不绕过 Approval、不直接调用平台 API。链路：

    E17.3 Decision -> P1.7 Audit -> P2.1 Contract -> P2.2 Provider
    -> P2.3 Approval -> P2.4 SafeExecutor -> ExecutionResult
    -> **P2.5 Monitor** -> E17.7 Memory

本模块定义：
- ExecutionEvent（10 类事件）
- ExecutionSummary（一次执行的可观测摘要，供 Metrics/Anomaly/Health 复用）
- ExecutionMetrics（聚合指标）
- ExecutionState / ExecutionHealth 等级常量与状态机迁移表

设计纪律（与 P2.4 一致）：纯 dataclass + 常量，无 I/O、无网络、无 LLM；
所有时间戳 ISO-8601 UTC；枚举用 str 常量（py3.11 str(Enum) 坑）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# ExecutionEvent 10 类事件
# ---------------------------------------------------------------------------
EVENT_CREATED = "CREATED"
EVENT_APPROVAL_GRANTED = "APPROVAL_GRANTED"
EVENT_EXECUTION_STARTED = "EXECUTION_STARTED"
EVENT_PROVIDER_CALLED = "PROVIDER_CALLED"
EVENT_PROVIDER_SUCCESS = "PROVIDER_SUCCESS"
EVENT_PROVIDER_FAILED = "PROVIDER_FAILED"
EVENT_ROLLBACK_STARTED = "ROLLBACK_STARTED"
EVENT_ROLLBACK_SUCCESS = "ROLLBACK_SUCCESS"
EVENT_ROLLBACK_FAILED = "ROLLBACK_FAILED"
EVENT_VERIFIED = "VERIFIED"

VALID_EVENT_TYPES = (
    EVENT_CREATED,
    EVENT_APPROVAL_GRANTED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_PROVIDER_SUCCESS,
    EVENT_PROVIDER_FAILED,
    EVENT_ROLLBACK_STARTED,
    EVENT_ROLLBACK_SUCCESS,
    EVENT_ROLLBACK_FAILED,
    EVENT_VERIFIED,
)

# ---------------------------------------------------------------------------
# ExecutionState（P2.5 自有状态机，区别于 P2.4 的 CTX_*）
# ---------------------------------------------------------------------------
STATE_CREATED = "CREATED"
STATE_AUTHORIZED = "AUTHORIZED"
STATE_RUNNING = "RUNNING"
STATE_SUCCESS = "SUCCESS"
STATE_FAILED = "FAILED"
STATE_ROLLBACK = "ROLLBACK"
STATE_ROLLED_BACK = "ROLLED_BACK"
STATE_BLOCKED = "BLOCKED"
STATE_ESCALATED = "ESCALATED"

VALID_STATES = (
    STATE_CREATED,
    STATE_AUTHORIZED,
    STATE_RUNNING,
    STATE_SUCCESS,
    STATE_FAILED,
    STATE_ROLLBACK,
    STATE_ROLLED_BACK,
    STATE_BLOCKED,
    STATE_ESCALATED,
)

TERMINAL_STATES = (
    STATE_SUCCESS,
    STATE_FAILED,
    STATE_ROLLED_BACK,
    STATE_BLOCKED,
    STATE_ESCALATED,
)

# 合法迁移表（P2.5 状态机）
# 注：AUTHORIZED -> SUCCESS 允许（幂等命中：VALIDATING 直接 SUCCESS，不经 RUNNING）
_ALLOWED_STATE_TRANSITIONS: Dict[str, tuple] = {
    STATE_CREATED: (STATE_AUTHORIZED, STATE_BLOCKED),
    STATE_AUTHORIZED: (STATE_RUNNING, STATE_BLOCKED, STATE_SUCCESS),
    STATE_RUNNING: (STATE_SUCCESS, STATE_FAILED, STATE_ROLLBACK, STATE_BLOCKED),
    STATE_FAILED: (STATE_ROLLBACK, STATE_ROLLED_BACK, STATE_ESCALATED),
    STATE_ROLLBACK: (STATE_ROLLED_BACK, STATE_ESCALATED),
    STATE_SUCCESS: (),
    STATE_ROLLED_BACK: (),
    STATE_BLOCKED: (),
    STATE_ESCALATED: (),
}

# ---------------------------------------------------------------------------
# Execution Health 等级
# ---------------------------------------------------------------------------
HEALTH_GREEN = "GREEN"
HEALTH_YELLOW = "YELLOW"
HEALTH_RED = "RED"

VALID_HEALTH_LEVELS = (HEALTH_GREEN, HEALTH_YELLOW, HEALTH_RED)

# ---------------------------------------------------------------------------
# Anomaly Severity
# ---------------------------------------------------------------------------
SEVERITY_RED = "RED"
SEVERITY_WARNING = "WARNING"
SEVERITY_BLOCK = "BLOCK"
SEVERITY_ALERT = "ALERT"

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_str(value: Any) -> str:
    """归一化 str-Enum 成员为其 value（py3.11 str() 坑）。"""
    return str(getattr(value, "value", value))


class IllegalStateTransitionError(ValueError):
    """非法的 P2.5 ExecutionState 状态迁移。"""


# ---------------------------------------------------------------------------
# ExecutionEvent
# ---------------------------------------------------------------------------


@dataclass
class ExecutionEvent:
    """一次执行生命周期中的一个可观测事件（不可变记录）。

    Fields:
        event_id     : 事件唯一 ID（evt_ 前缀）
        execution_id : 对应 SafeExecutionContext.execution_id（exe_ 前缀）
        event_type   : EVENT_* 之一
        timestamp    : ISO-8601 UTC
        provider     : 落地 Provider（max / meta / play / ""）
        action       : 动作字符串（ExecutionAction.value）
        status       : 关联的执行状态（P2.5 STATE_* 或 P2.4 CTX_*）
        metadata     : 附加信息（latency / error / reason 等）
    """

    execution_id: str
    event_type: str
    timestamp: str = ""
    provider: str = ""
    action: str = ""
    status: str = ""
    event_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = _now_iso()
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"invalid event_type: {self.event_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "execution_id": self.execution_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "provider": self.provider,
            "action": self.action,
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionEvent":
        return cls(
            execution_id=str(d.get("execution_id", "")),
            event_type=str(d.get("event_type", "")),
            timestamp=str(d.get("timestamp", "")),
            provider=str(d.get("provider", "")),
            action=str(d.get("action", "")),
            status=str(d.get("status", "")),
            event_id=str(d.get("event_id", "")),
            metadata=d.get("metadata") or {},
        )


# ---------------------------------------------------------------------------
# ExecutionSummary（一次执行的可观测摘要，供 Metrics/Anomaly/Health 复用）
# ---------------------------------------------------------------------------


@dataclass
class ExecutionSummary:
    """Monitor 内部一次执行的归一化摘要。

    由 collector.summarize(request, outcome) 产出，供 Metrics / Anomaly / Health
    统一消费，避免各自重复解析 SafeExecutionOutcome。

    Fields:
        execution_id    : exe_ 前缀
        action          : 实际执行动作（context.action）
        intended_action : 决策请求动作（request.intent.action），用于 DRIFT 检测
        target          : 执行目标
        provider        : 落地 Provider
        verdict         : P2.4 VERDICT_*
        status          : P2.5 最终状态
        timestamp       : 执行开始时间
        is_real         : 是否真实触碰外部 API
        latency_seconds : 执行耗时（秒），无则 0.0
    """

    execution_id: str
    action: str
    target: str
    provider: str
    verdict: str
    status: str
    timestamp: str
    is_real: bool = False
    intended_action: str = ""
    latency_seconds: float = 0.0

    @property
    def drifted(self) -> bool:
        """Rule4：请求动作 ≠ 实际动作。"""
        if not self.intended_action:
            return False
        return self.intended_action != self.action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "action": self.action,
            "intended_action": self.intended_action,
            "target": self.target,
            "provider": self.provider,
            "verdict": self.verdict,
            "status": self.status,
            "timestamp": self.timestamp,
            "is_real": self.is_real,
            "latency_seconds": self.latency_seconds,
            "drifted": self.drifted,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionSummary":
        return cls(
            execution_id=str(d.get("execution_id", "")),
            action=str(d.get("action", "")),
            target=str(d.get("target", "")),
            provider=str(d.get("provider", "")),
            verdict=str(d.get("verdict", "")),
            status=str(d.get("status", "")),
            timestamp=str(d.get("timestamp", "")),
            is_real=bool(d.get("is_real", False)),
            intended_action=str(d.get("intended_action", "")),
            latency_seconds=float(d.get("latency_seconds", 0.0)),
        )


# ---------------------------------------------------------------------------
# ExecutionMetrics
# ---------------------------------------------------------------------------


@dataclass
class ExecutionMetrics:
    """一次聚合窗口内的执行指标。

    Fields:
        total_executions : 总执行次数
        success_rate     : 成功率（0..1）
        failure_rate     : 失败率（0..1）
        rollback_rate    : 回滚率（0..1）
        blocked_rate     : 拦截率（0..1）
    """

    total_executions: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    rollback_rate: float = 0.0
    blocked_rate: float = 0.0

    @staticmethod
    def _classify(verdict: str) -> str:
        """把 P2.4 verdict 归为 success/failed/rollback/blocked/other。"""
        v = str(verdict)
        if v in ("EXECUTED", "RETURN_EXISTING"):
            return "success"
        if v == "ROLLED_BACK":
            return "rollback"
        if v in ("FAILED", "ESCALATED"):
            return "failed"
        if v == "BLOCKED":
            return "blocked"
        return "other"

    @classmethod
    def from_summaries(cls, summaries: List[Dict[str, Any]]) -> "ExecutionMetrics":
        """从一组已归类的摘要（含 verdict 键）聚合指标。

        summaries 每个元素需含 ``verdict`` 键（P2.4 VERDICT_*）。
        """
        total = len(summaries)
        if total == 0:
            return cls()
        buckets = {
            "success": 0,
            "failed": 0,
            "rollback": 0,
            "blocked": 0,
            "other": 0,
        }
        for s in summaries:
            buckets[cls._classify(s.get("verdict", ""))] += 1
        return cls(
            total_executions=total,
            success_rate=round(buckets["success"] / total, 6),
            failure_rate=round(buckets["failed"] / total, 6),
            rollback_rate=round(buckets["rollback"] / total, 6),
            blocked_rate=round(buckets["blocked"] / total, 6),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_executions": self.total_executions,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "rollback_rate": self.rollback_rate,
            "blocked_rate": self.blocked_rate,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExecutionMetrics":
        return cls(
            total_executions=int(d.get("total_executions", 0)),
            success_rate=float(d.get("success_rate", 0.0)),
            failure_rate=float(d.get("failure_rate", 0.0)),
            rollback_rate=float(d.get("rollback_rate", 0.0)),
            blocked_rate=float(d.get("blocked_rate", 0.0)),
        )


__all__ = [
    # Event 常量
    "EVENT_CREATED",
    "EVENT_APPROVAL_GRANTED",
    "EVENT_EXECUTION_STARTED",
    "EVENT_PROVIDER_CALLED",
    "EVENT_PROVIDER_SUCCESS",
    "EVENT_PROVIDER_FAILED",
    "EVENT_ROLLBACK_STARTED",
    "EVENT_ROLLBACK_SUCCESS",
    "EVENT_ROLLBACK_FAILED",
    "EVENT_VERIFIED",
    "VALID_EVENT_TYPES",
    # State 常量
    "STATE_CREATED",
    "STATE_AUTHORIZED",
    "STATE_RUNNING",
    "STATE_SUCCESS",
    "STATE_FAILED",
    "STATE_ROLLBACK",
    "STATE_ROLLED_BACK",
    "STATE_BLOCKED",
    "STATE_ESCALATED",
    "VALID_STATES",
    "TERMINAL_STATES",
    "_ALLOWED_STATE_TRANSITIONS",
    # Health 常量
    "HEALTH_GREEN",
    "HEALTH_YELLOW",
    "HEALTH_RED",
    "VALID_HEALTH_LEVELS",
    # Severity 常量
    "SEVERITY_RED",
    "SEVERITY_WARNING",
    "SEVERITY_BLOCK",
    "SEVERITY_ALERT",
    # helpers
    "IllegalStateTransitionError",
    "_as_str",
    "_now_iso",
    # 模型
    "ExecutionEvent",
    "ExecutionSummary",
    "ExecutionMetrics",
]
