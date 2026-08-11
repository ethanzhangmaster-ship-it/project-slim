"""P2.6.1 Execution Recovery Layer — 核心域模型。

P2.6 的定位：从「敢执行 + 会观察」升级到「能自愈」。
本模块定义执行恢复层的核心模型：

- RecoveryIncident         : 一次执行故障事件的全生命周期（7 状态机）
- FailureClassification    : 故障分类结果（failure_type + treatment + severity）
- RecoveryPlan             : 恢复计划（策略 + 重试参数 + 目标）
- RecoveryAttempt          : 单次恢复尝试记录
- RecoveryResult           : 恢复最终交付物
- VerificationResult       : 恢复后状态验证结果
- EscalationTicket         : 升级人工的工单
- RecoveryExperienceRecord : 回流 E16/E17.7 的恢复经验

设计纪律（与 P2.1~P2.5 一致）：
- 纯 dataclass + str 常量，无 I/O、无网络、无 LLM
- 所有时间戳 ISO-8601 UTC 字符串
- 序列化统一 _as_str 归一化（py3.11 str(Enum) 坑）
- 恢复动作绝不绕过 P2.3：本层模型只描述「计划」，执行必须走
  Recovery -> Authorization Check -> Safe Executor
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_str(value: Any) -> str:
    """归一化 str-Enum 成员为其 value（py3.11 str() 坑）。"""
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# RecoveryIncident 状态常量（7 状态机）
# ---------------------------------------------------------------------------

INCIDENT_DETECTED = "DETECTED"       # 故障已捕获，尚未分类
INCIDENT_CLASSIFIED = "CLASSIFIED"   # 已完成故障分类
INCIDENT_PLANNED = "PLANNED"         # 已产出恢复计划
INCIDENT_RECOVERING = "RECOVERING"   # 恢复动作执行中（经 P2.3/P2.4）
INCIDENT_VERIFIED = "VERIFIED"       # 恢复后验证通过
INCIDENT_ESCALATED = "ESCALATED"     # 已升级人工（终态前）
INCIDENT_CLOSED = "CLOSED"           # 事件关闭（终态）

VALID_INCIDENT_STATUSES = (
    INCIDENT_DETECTED,
    INCIDENT_CLASSIFIED,
    INCIDENT_PLANNED,
    INCIDENT_RECOVERING,
    INCIDENT_VERIFIED,
    INCIDENT_ESCALATED,
    INCIDENT_CLOSED,
)

TERMINAL_INCIDENT_STATUSES = (INCIDENT_CLOSED,)

# 合法状态迁移表
# DETECTED -> CLASSIFIED
# CLASSIFIED -> PLANNED | ESCALATED（分类结果直接要求升级，如 AUTH_FAILURE）
# PLANNED -> RECOVERING | ESCALATED（计划即升级，如 HIGH/CRITICAL）
# RECOVERING -> VERIFIED | ESCALATED（恢复失败/超次升级）
# VERIFIED -> CLOSED
# ESCALATED -> CLOSED（人工处理完毕后关闭）
_ALLOWED_INCIDENT_TRANSITIONS = {
    INCIDENT_DETECTED: (INCIDENT_CLASSIFIED,),
    INCIDENT_CLASSIFIED: (INCIDENT_PLANNED, INCIDENT_ESCALATED),
    INCIDENT_PLANNED: (INCIDENT_RECOVERING, INCIDENT_ESCALATED),
    INCIDENT_RECOVERING: (INCIDENT_VERIFIED, INCIDENT_ESCALATED),
    INCIDENT_VERIFIED: (INCIDENT_CLOSED,),
    INCIDENT_ESCALATED: (INCIDENT_CLOSED,),
    INCIDENT_CLOSED: (),
}


class IllegalIncidentTransitionError(ValueError):
    """非法的 RecoveryIncident 状态迁移。"""


# ---------------------------------------------------------------------------
# 故障类型 / 处置方式 / 严重级别常量
# ---------------------------------------------------------------------------

# FailureType（4 + 1 类）
FAILURE_TIMEOUT = "PROVIDER_TIMEOUT"          # Provider 超时 / 5xx / rate limit
FAILURE_AUTH = "AUTH_FAILURE"                 # 认证失败（401/403 token 失效）
FAILURE_STATE_DRIFT = "STATE_DRIFT"           # 请求态与平台实际态不一致
FAILURE_ROLLBACK_FAILED = "ROLLBACK_FAILED"   # 回滚失败（最高级）
FAILURE_UNKNOWN = "UNKNOWN"                   # 无法识别的故障

VALID_FAILURE_TYPES = (
    FAILURE_TIMEOUT,
    FAILURE_AUTH,
    FAILURE_STATE_DRIFT,
    FAILURE_ROLLBACK_FAILED,
    FAILURE_UNKNOWN,
)

# TreatmentType（分类器建议的处置方式）
TREATMENT_RETRY = "RETRY"
TREATMENT_RECONCILE = "RECONCILE"
TREATMENT_ROLLBACK_RETRY = "ROLLBACK_RETRY"
TREATMENT_ESCALATE = "ESCALATE"
TREATMENT_EMERGENCY_ESCALATE = "EMERGENCY_ESCALATE"

VALID_TREATMENTS = (
    TREATMENT_RETRY,
    TREATMENT_RECONCILE,
    TREATMENT_ROLLBACK_RETRY,
    TREATMENT_ESCALATE,
    TREATMENT_EMERGENCY_ESCALATE,
)

# Severity（与 Escalation 四级一致）
SEVERITY_LOW = "LOW"            # 自动 retry 即可
SEVERITY_MEDIUM = "MEDIUM"      # 自动恢复（reconcile 等）
SEVERITY_HIGH = "HIGH"          # 需要人工介入
SEVERITY_CRITICAL = "CRITICAL"  # 停止所有自动执行

VALID_SEVERITIES = (
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    SEVERITY_CRITICAL,
)

_SEVERITY_RANK = {
    SEVERITY_LOW: 0,
    SEVERITY_MEDIUM: 1,
    SEVERITY_HIGH: 2,
    SEVERITY_CRITICAL: 3,
}


def severity_rank(severity: Any) -> int:
    """严重级别 -> 数值序（未知级别按 HIGH 保守处理）。"""
    return _SEVERITY_RANK.get(_as_str(severity), _SEVERITY_RANK[SEVERITY_HIGH])


# RecoveryStrategy 常量（Planner 产出的策略名）
STRATEGY_RETRY = "RETRY"
STRATEGY_RECONCILE = "RECONCILE"
STRATEGY_ROLLBACK_RETRY = "ROLLBACK_RETRY"
STRATEGY_ESCALATION = "ESCALATION"

VALID_STRATEGIES = (
    STRATEGY_RETRY,
    STRATEGY_RECONCILE,
    STRATEGY_ROLLBACK_RETRY,
    STRATEGY_ESCALATION,
)

# RecoveryResult 状态常量
RECOVERY_RECOVERED = "RECOVERED"          # 恢复成功且验证通过
RECOVERY_NOT_RECOVERED = "NOT_RECOVERED"  # 尝试后仍未恢复
RECOVERY_ESCALATED = "ESCALATED"          # 已升级人工
RECOVERY_SKIPPED = "SKIPPED"              # 无需/无法恢复（如非生产模拟）

VALID_RECOVERY_STATUSES = (
    RECOVERY_RECOVERED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_ESCALATED,
    RECOVERY_SKIPPED,
)

# VerificationResult 状态常量
VERIFY_RECOVERED = "RECOVERED"
VERIFY_NOT_RECOVERED = "NOT_RECOVERED"
VERIFY_UNVERIFIABLE = "UNVERIFIABLE"

VALID_VERIFY_STATUSES = (
    VERIFY_RECOVERED,
    VERIFY_NOT_RECOVERED,
    VERIFY_UNVERIFIABLE,
)


# ---------------------------------------------------------------------------
# RecoveryIncident
# ---------------------------------------------------------------------------


@dataclass
class RecoveryIncident:
    """一次执行故障事件的全生命周期记录（用户契约字段）。

    Fields:
        incident_id  : 事件唯一 ID（inc_ 前缀）
        execution_id : 关联的 SafeExecutionContext.execution_id
        action       : 原始动作（ExecutionAction.value）
        provider     : 落地 Provider（max / meta / play）
        failure_type : FAILURE_* 之一（分类后填充）
        severity     : SEVERITY_* 之一
        detected_at  : 捕获时间
        status       : 7 状态之一
    """

    execution_id: str
    action: str = ""
    provider: str = ""
    failure_type: str = FAILURE_UNKNOWN
    severity: str = SEVERITY_MEDIUM
    incident_id: str = ""
    detected_at: str = ""
    status: str = INCIDENT_DETECTED
    target: str = ""
    request_id: str = ""
    mode: str = "dry_run"
    error: str = ""
    # 状态迁移轨迹 [(status, at_iso), ...]
    history: List[Any] = field(default_factory=list)
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.incident_id:
            self.incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        if not self.detected_at:
            self.detected_at = _now_iso()
        self.action = _as_str(self.action)
        self.mode = _as_str(self.mode)
        self.failure_type = _as_str(self.failure_type)
        self.severity = _as_str(self.severity)
        if self.status not in VALID_INCIDENT_STATUSES:
            raise ValueError(f"invalid incident status: {self.status}")
        if self.failure_type not in VALID_FAILURE_TYPES:
            raise ValueError(f"invalid failure type: {self.failure_type}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")
        if not self.history:
            self.history = [(self.status, self.detected_at)]

    # -- 状态机 -------------------------------------------------------------

    def transition(self, new_status: str, reason: str = "") -> None:
        """执行一次状态迁移；非法迁移抛 IllegalIncidentTransitionError。"""
        if new_status not in VALID_INCIDENT_STATUSES:
            raise IllegalIncidentTransitionError(f"unknown status: {new_status}")
        allowed = _ALLOWED_INCIDENT_TRANSITIONS.get(self.status, ())
        if new_status not in allowed:
            raise IllegalIncidentTransitionError(
                f"illegal incident transition {self.status} -> {new_status}"
            )
        self.status = new_status
        self.history.append((new_status, _now_iso()))
        if reason:
            self.reason = reason

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_INCIDENT_STATUSES

    # -- 序列化 --------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "action": _as_str(self.action),
            "provider": self.provider,
            "target": self.target,
            "mode": _as_str(self.mode),
            "failure_type": _as_str(self.failure_type),
            "severity": _as_str(self.severity),
            "detected_at": self.detected_at,
            "status": self.status,
            "error": self.error,
            "history": [list(item) for item in self.history],
            "reason": self.reason,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryIncident":
        incident = cls(
            execution_id=str(data.get("execution_id", "")),
            action=str(data.get("action", "")),
            provider=str(data.get("provider", "")),
            failure_type=str(data.get("failure_type", FAILURE_UNKNOWN)),
            severity=str(data.get("severity", SEVERITY_MEDIUM)),
            incident_id=str(data.get("incident_id", "")),
            detected_at=str(data.get("detected_at", "")),
            status=str(data.get("status", INCIDENT_DETECTED)),
            target=str(data.get("target", "")),
            request_id=str(data.get("request_id", "")),
            mode=str(data.get("mode", "dry_run")),
            error=str(data.get("error", "") or ""),
            reason=str(data.get("reason", "")),
            metadata=data.get("metadata") or {},
        )
        history = data.get("history") or []
        if history:
            incident.history = [tuple(item) for item in history]
        return incident

    @classmethod
    def from_outcome(cls, outcome: Any, request: Any = None) -> "RecoveryIncident":
        """从 P2.4 SafeExecutionOutcome（+ 可选 ExecutionRequest）构造事件。

        仅提取字段，不做分类——分类是 FailureClassifier 的职责。
        """
        context = getattr(outcome, "context", None)
        result = getattr(outcome, "result", None)
        intent = getattr(request, "intent", None) if request is not None else None
        error = ""
        if result is not None:
            error = str(getattr(result, "error", "") or "")
        if not error and context is not None:
            error = str(getattr(context, "reason", "") or "")
        return cls(
            execution_id=str(getattr(context, "execution_id", "") or ""),
            action=_as_str(
                getattr(context, "action", "")
                or getattr(intent, "action", "")
            ),
            provider=str(getattr(result, "provider", "") or ""),
            target=str(
                getattr(context, "target", "")
                or getattr(intent, "target_id", "")
            ),
            request_id=str(
                getattr(context, "request_id", "")
                or getattr(request, "request_id", "")
            ),
            mode=_as_str(getattr(context, "mode", "dry_run") or "dry_run"),
            error=error,
            metadata={"verdict": _as_str(getattr(outcome, "verdict", ""))},
        )


# ---------------------------------------------------------------------------
# FailureClassification
# ---------------------------------------------------------------------------


@dataclass
class FailureClassification:
    """故障分类结果（FailureClassifier 的交付物）。

    Fields:
        incident_id  : 关联事件 ID
        failure_type : FAILURE_* 之一
        treatment    : TREATMENT_* 之一（建议处置方式）
        severity     : SEVERITY_* 之一
        provider     : 故障 Provider
        action       : 原始动作
        message      : 人类可读的分类说明
        confidence   : 分类置信度 0..1（规则命中=1.0，UNKNOWN 兜底较低）
    """

    incident_id: str
    failure_type: str
    treatment: str
    severity: str
    provider: str = ""
    action: str = ""
    message: str = ""
    confidence: float = 1.0
    classified_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.classified_at:
            self.classified_at = _now_iso()
        self.failure_type = _as_str(self.failure_type)
        self.treatment = _as_str(self.treatment)
        self.severity = _as_str(self.severity)
        self.action = _as_str(self.action)
        if self.failure_type not in VALID_FAILURE_TYPES:
            raise ValueError(f"invalid failure type: {self.failure_type}")
        if self.treatment not in VALID_TREATMENTS:
            raise ValueError(f"invalid treatment: {self.treatment}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")

    @property
    def requires_escalation(self) -> bool:
        return self.treatment in (
            TREATMENT_ESCALATE,
            TREATMENT_EMERGENCY_ESCALATE,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "failure_type": _as_str(self.failure_type),
            "treatment": _as_str(self.treatment),
            "severity": _as_str(self.severity),
            "provider": self.provider,
            "action": _as_str(self.action),
            "message": self.message,
            "confidence": self.confidence,
            "classified_at": self.classified_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureClassification":
        return cls(
            incident_id=str(data.get("incident_id", "")),
            failure_type=str(data.get("failure_type", FAILURE_UNKNOWN)),
            treatment=str(data.get("treatment", TREATMENT_ESCALATE)),
            severity=str(data.get("severity", SEVERITY_HIGH)),
            provider=str(data.get("provider", "")),
            action=str(data.get("action", "")),
            message=str(data.get("message", "")),
            confidence=float(data.get("confidence", 1.0)),
            classified_at=str(data.get("classified_at", "")),
            metadata=data.get("metadata") or {},
        )


# ---------------------------------------------------------------------------
# RecoveryPlan
# ---------------------------------------------------------------------------


@dataclass
class RecoveryPlan:
    """恢复计划（RecoveryPlanner 的交付物）。

    Fields:
        plan_id       : 计划唯一 ID（rcp_ 前缀）
        incident_id   : 关联事件 ID
        strategy      : STRATEGY_* 之一
        action        : 恢复要重放的动作（ExecutionAction.value）
        target        : 执行目标
        provider      : 落地 Provider
        max_attempts  : 最大尝试次数（RETRY=3 / ROLLBACK_RETRY=1 / 其余 1）
        backoff       : 各次重试前等待秒数（如 [1, 5, 30]）
        risk_level    : 原始风险分 0..1
        expected_state: 恢复成功后的期望状态（供 Verifier 比对）
        escalate_only : True 表示本计划不执行任何动作、直接升级
    """

    incident_id: str
    strategy: str
    action: str = ""
    target: str = ""
    provider: str = ""
    max_attempts: int = 1
    backoff: List[float] = field(default_factory=list)
    risk_level: float = 0.5
    expected_state: Dict[str, Any] = field(default_factory=dict)
    escalate_only: bool = False
    rollback_action: str = ""
    plan_id: str = ""
    created_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"rcp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        self.strategy = _as_str(self.strategy)
        self.action = _as_str(self.action)
        self.rollback_action = _as_str(self.rollback_action)
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(f"invalid strategy: {self.strategy}")
        if self.strategy == STRATEGY_ESCALATION:
            self.escalate_only = True
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "incident_id": self.incident_id,
            "strategy": _as_str(self.strategy),
            "action": _as_str(self.action),
            "target": self.target,
            "provider": self.provider,
            "max_attempts": self.max_attempts,
            "backoff": list(self.backoff),
            "risk_level": self.risk_level,
            "expected_state": self.expected_state,
            "escalate_only": self.escalate_only,
            "rollback_action": _as_str(self.rollback_action),
            "created_at": self.created_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryPlan":
        return cls(
            incident_id=str(data.get("incident_id", "")),
            strategy=str(data.get("strategy", STRATEGY_ESCALATION)),
            action=str(data.get("action", "")),
            target=str(data.get("target", "")),
            provider=str(data.get("provider", "")),
            max_attempts=int(data.get("max_attempts", 1)),
            backoff=list(data.get("backoff") or []),
            risk_level=float(data.get("risk_level", 0.5)),
            expected_state=data.get("expected_state") or {},
            escalate_only=bool(data.get("escalate_only", False)),
            rollback_action=str(data.get("rollback_action", "")),
            plan_id=str(data.get("plan_id", "")),
            created_at=str(data.get("created_at", "")),
            notes=str(data.get("notes", "")),
        )


# ---------------------------------------------------------------------------
# RecoveryAttempt / VerificationResult / RecoveryResult
# ---------------------------------------------------------------------------


@dataclass
class RecoveryAttempt:
    """单次恢复尝试记录。"""

    attempt: int
    waited_seconds: float = 0.0
    verdict: str = ""            # P2.4 VERDICT_* 或空（未执行）
    ok: bool = False
    error: str = ""
    started_at: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = _now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt,
            "waited_seconds": self.waited_seconds,
            "verdict": _as_str(self.verdict),
            "ok": self.ok,
            "error": self.error,
            "started_at": self.started_at,
        }


@dataclass
class VerificationResult:
    """恢复后验证结果（RecoveryVerifier 的交付物）。"""

    incident_id: str
    status: str                              # VERIFY_* 之一
    expected_state: Dict[str, Any] = field(default_factory=dict)
    observed_state: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    verified_at: str = ""

    def __post_init__(self) -> None:
        if not self.verified_at:
            self.verified_at = _now_iso()
        self.status = _as_str(self.status)
        if self.status not in VALID_VERIFY_STATUSES:
            raise ValueError(f"invalid verify status: {self.status}")

    @property
    def recovered(self) -> bool:
        return self.status == VERIFY_RECOVERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "status": self.status,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "message": self.message,
            "verified_at": self.verified_at,
        }


@dataclass
class RecoveryResult:
    """恢复的最终交付物（RecoveryEngine / RecoveryExecutor 的产出）。

    Fields:
        incident_id  : 关联事件 ID
        plan_id      : 关联计划 ID
        status       : RECOVERY_* 之一
        attempts     : 实际尝试次数
        attempt_log  : 各次尝试记录
        verification : 恢复后验证结果（未验证为 None）
        escalation   : 升级工单（未升级为 None，dict 形式）
        outcome      : 最后一次 SafeExecutionOutcome 的 to_dict（未执行为 None）
    """

    incident_id: str
    plan_id: str = ""
    status: str = RECOVERY_NOT_RECOVERED
    attempts: int = 0
    attempt_log: List[RecoveryAttempt] = field(default_factory=list)
    verification: Optional[VerificationResult] = None
    escalation: Optional[Dict[str, Any]] = None
    outcome: Optional[Dict[str, Any]] = None
    finished_at: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if not self.finished_at:
            self.finished_at = _now_iso()
        self.status = _as_str(self.status)
        if self.status not in VALID_RECOVERY_STATUSES:
            raise ValueError(f"invalid recovery status: {self.status}")

    @property
    def recovered(self) -> bool:
        return self.status == RECOVERY_RECOVERED

    @property
    def escalated(self) -> bool:
        return self.status == RECOVERY_ESCALATED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "attempts": self.attempts,
            "attempt_log": [a.to_dict() for a in self.attempt_log],
            "verification": (
                self.verification.to_dict() if self.verification else None
            ),
            "escalation": self.escalation,
            "outcome": self.outcome,
            "finished_at": self.finished_at,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# EscalationTicket
# ---------------------------------------------------------------------------


@dataclass
class EscalationTicket:
    """升级人工的工单（用户契约字段）。

    Fields:
        ticket_id          : 工单唯一 ID（esc_ 前缀）
        incident_id        : 关联事件 ID
        severity           : SEVERITY_* 之一
        reason             : 升级原因
        recommended_action : 建议的人工动作
        created_at         : 创建时间
        halt_automation    : CRITICAL 时为 True——停止所有自动执行
    """

    incident_id: str
    severity: str
    reason: str
    recommended_action: str = ""
    ticket_id: str = ""
    created_at: str = ""
    halt_automation: bool = False
    approval_id: str = ""        # 接 P2.3 manual approval 时回填
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ticket_id:
            self.ticket_id = f"esc_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        self.severity = _as_str(self.severity)
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")
        if self.severity == SEVERITY_CRITICAL:
            self.halt_automation = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "incident_id": self.incident_id,
            "severity": _as_str(self.severity),
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at,
            "halt_automation": self.halt_automation,
            "approval_id": self.approval_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EscalationTicket":
        ticket = cls(
            incident_id=str(data.get("incident_id", "")),
            severity=str(data.get("severity", SEVERITY_HIGH)),
            reason=str(data.get("reason", "")),
            recommended_action=str(data.get("recommended_action", "")),
            ticket_id=str(data.get("ticket_id", "")),
            created_at=str(data.get("created_at", "")),
            halt_automation=bool(data.get("halt_automation", False)),
            approval_id=str(data.get("approval_id", "")),
            metadata=data.get("metadata") or {},
        )
        return ticket


# ---------------------------------------------------------------------------
# RecoveryExperienceRecord（回流 E16 + E17.7）
# ---------------------------------------------------------------------------


@dataclass
class RecoveryExperienceRecord:
    """恢复经验记录——让 AI 学到「Meta timeout 通常 retry 有效」。

    结构遵循用户契约：{failure, action, recovery, result, reward}。
    reward 约定：
        RECOVERED       -> 0.8（自动恢复成功，高奖励）
        NOT_RECOVERED   -> 0.0
        ESCALATED       -> 0.2（正确升级也是有价值的保守行为）
        SKIPPED         -> 0.0
    """

    failure: str                  # FAILURE_* 之一
    action: str                   # 原始动作
    recovery: str                 # STRATEGY_* 之一
    result: str                   # RECOVERY_* 之一
    reward: float = 0.0
    provider: str = ""
    incident_id: str = ""
    attempts: int = 0
    success: bool = False
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now_iso()
        self.failure = _as_str(self.failure)
        self.action = _as_str(self.action)
        self.recovery = _as_str(self.recovery)
        self.result = _as_str(self.result)
        self.success = self.result == RECOVERY_RECOVERED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure": self.failure,
            "action": self.action,
            "recovery": self.recovery,
            "result": self.result,
            "reward": self.reward,
            "provider": self.provider,
            "incident_id": self.incident_id,
            "attempts": self.attempts,
            "success": self.success,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryExperienceRecord":
        return cls(
            failure=str(data.get("failure", FAILURE_UNKNOWN)),
            action=str(data.get("action", "")),
            recovery=str(data.get("recovery", STRATEGY_ESCALATION)),
            result=str(data.get("result", RECOVERY_NOT_RECOVERED)),
            reward=float(data.get("reward", 0.0)),
            provider=str(data.get("provider", "")),
            incident_id=str(data.get("incident_id", "")),
            attempts=int(data.get("attempts", 0)),
            created_at=str(data.get("created_at", "")),
            metadata=data.get("metadata") or {},
        )


# reward 约定表（供 Memory Bridge / 测试引用）
RECOVERY_REWARDS = {
    RECOVERY_RECOVERED: 0.8,
    RECOVERY_NOT_RECOVERED: 0.0,
    RECOVERY_ESCALATED: 0.2,
    RECOVERY_SKIPPED: 0.0,
}


def reward_for(status: Any) -> float:
    """RECOVERY_* 状态 -> reward。未知状态按 0.0。"""
    return RECOVERY_REWARDS.get(_as_str(status), 0.0)


__all__ = [
    # incident 状态
    "INCIDENT_DETECTED",
    "INCIDENT_CLASSIFIED",
    "INCIDENT_PLANNED",
    "INCIDENT_RECOVERING",
    "INCIDENT_VERIFIED",
    "INCIDENT_ESCALATED",
    "INCIDENT_CLOSED",
    "VALID_INCIDENT_STATUSES",
    "TERMINAL_INCIDENT_STATUSES",
    "IllegalIncidentTransitionError",
    # failure / treatment / severity
    "FAILURE_TIMEOUT",
    "FAILURE_AUTH",
    "FAILURE_STATE_DRIFT",
    "FAILURE_ROLLBACK_FAILED",
    "FAILURE_UNKNOWN",
    "VALID_FAILURE_TYPES",
    "TREATMENT_RETRY",
    "TREATMENT_RECONCILE",
    "TREATMENT_ROLLBACK_RETRY",
    "TREATMENT_ESCALATE",
    "TREATMENT_EMERGENCY_ESCALATE",
    "VALID_TREATMENTS",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "SEVERITY_HIGH",
    "SEVERITY_CRITICAL",
    "VALID_SEVERITIES",
    "severity_rank",
    # strategy / recovery / verify 状态
    "STRATEGY_RETRY",
    "STRATEGY_RECONCILE",
    "STRATEGY_ROLLBACK_RETRY",
    "STRATEGY_ESCALATION",
    "VALID_STRATEGIES",
    "RECOVERY_RECOVERED",
    "RECOVERY_NOT_RECOVERED",
    "RECOVERY_ESCALATED",
    "RECOVERY_SKIPPED",
    "VALID_RECOVERY_STATUSES",
    "VERIFY_RECOVERED",
    "VERIFY_NOT_RECOVERED",
    "VERIFY_UNVERIFIABLE",
    "VALID_VERIFY_STATUSES",
    # 模型
    "RecoveryIncident",
    "FailureClassification",
    "RecoveryPlan",
    "RecoveryAttempt",
    "VerificationResult",
    "RecoveryResult",
    "EscalationTicket",
    "RecoveryExperienceRecord",
    "RECOVERY_REWARDS",
    "reward_for",
    # 工具
    "_as_str",
    "_now_iso",
]
