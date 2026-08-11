"""P2.4.1 Safe Executor — 核心域模型。

P2.4 的定位：从「能执行」升级到「敢执行」。
本模块定义执行安全沙箱的四个核心模型：

- SafeExecutionContext : 一次安全执行的全生命周期上下文（9 状态机）
- RollbackCapability   : Provider 声明「这个动作可以怎么撤销」
- RollbackPlan         : 一次具体回滚的执行计划
- SafeExecutionOutcome : SafeExecutor 的最终交付物（context + result + rollback）

设计纪律（与 P2.1/P2.3 一致）：
- 纯 dataclass + 常量，无 I/O、无网络、无 LLM
- 所有时间戳 ISO-8601 UTC 字符串
- 枚举一律用 str 常量（py3.11 str(Enum) 序列化坑，见 approval/models._as_str）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# SafeExecutionContext 状态常量（9 个）
# ---------------------------------------------------------------------------

CTX_CREATED = "CREATED"            # 上下文已创建，尚未校验
CTX_VALIDATING = "VALIDATING"      # 正在验证授权 / 风险 / 幂等
CTX_SNAPSHOTTING = "SNAPSHOTTING"  # 正在保存执行前快照
CTX_EXECUTING = "EXECUTING"        # 正在调用 Provider
CTX_VERIFYING = "VERIFYING"        # 正在验证执行后状态
CTX_SUCCESS = "SUCCESS"            # 执行成功（终态）
CTX_FAILED = "FAILED"              # 执行失败且未回滚 / 回滚失败（终态）
CTX_ROLLED_BACK = "ROLLED_BACK"    # 执行失败并已回滚（终态）
CTX_BLOCKED = "BLOCKED"            # 被安全闸门拦截，未触碰外部系统（终态）

VALID_CONTEXT_STATUSES = (
    CTX_CREATED,
    CTX_VALIDATING,
    CTX_SNAPSHOTTING,
    CTX_EXECUTING,
    CTX_VERIFYING,
    CTX_SUCCESS,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_BLOCKED,
)

TERMINAL_CONTEXT_STATUSES = (
    CTX_SUCCESS,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_BLOCKED,
)

# 合法状态迁移表（Execution Policy 的状态机基础）
_ALLOWED_TRANSITIONS = {
    CTX_CREATED: (CTX_VALIDATING, CTX_BLOCKED),
    CTX_VALIDATING: (CTX_SNAPSHOTTING, CTX_SUCCESS, CTX_BLOCKED),
    CTX_SNAPSHOTTING: (CTX_EXECUTING, CTX_BLOCKED),
    CTX_EXECUTING: (CTX_VERIFYING, CTX_FAILED),
    # VERIFYING -> BLOCKED：Router 内部闸门拦截（real_api_called=False，从未动手）
    CTX_VERIFYING: (CTX_SUCCESS, CTX_FAILED, CTX_ROLLED_BACK, CTX_BLOCKED),
    # 终态不再迁移
    CTX_SUCCESS: (),
    CTX_FAILED: (),
    CTX_ROLLED_BACK: (),
    CTX_BLOCKED: (),
}

# SafeExecutionOutcome 判定（verdict）常量
VERDICT_EXECUTED = "EXECUTED"                # 正常执行成功
VERDICT_RETURN_EXISTING = "RETURN_EXISTING"  # 幂等命中，返回历史结果
VERDICT_BLOCKED = "BLOCKED"                  # 被闸门拦截
VERDICT_ROLLED_BACK = "ROLLED_BACK"          # 执行失败已回滚
VERDICT_ESCALATED = "ESCALATED"              # 回滚也失败，升级人工（Rule 5）
VERDICT_FAILED = "FAILED"                    # 失败且无回滚能力

VALID_VERDICTS = (
    VERDICT_EXECUTED,
    VERDICT_RETURN_EXISTING,
    VERDICT_BLOCKED,
    VERDICT_ROLLED_BACK,
    VERDICT_ESCALATED,
    VERDICT_FAILED,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_str(value: Any) -> str:
    """归一化 str-Enum 成员为其 value（py3.11 str() 坑）。"""
    return str(getattr(value, "value", value))


class InvalidTransitionError(ValueError):
    """非法的 SafeExecutionContext 状态迁移。"""


# ---------------------------------------------------------------------------
# SafeExecutionContext
# ---------------------------------------------------------------------------


@dataclass
class SafeExecutionContext:
    """一次安全执行的全生命周期记录（用户契约字段）。

    Fields:
        execution_id     : 本次安全执行的唯一 ID（exe_ 前缀）
        request_id       : 对应 ExecutionRequest.request_id
        action           : 动作字符串（ExecutionAction.value）
        target           : 执行目标（game_id / campaign_id / network ...）
        mode             : simulation / dry_run / production
        risk_score       : 风险分（0..1，来自 intent.risk_level）
        authorization_id : P2.3 ExecutionAuthorization.approval_id（无授权为空）
        before_state     : 执行前快照
        after_state      : 执行后状态
        started_at       : 开始时间
        finished_at      : 结束时间（未结束为空）
        status           : 9 状态之一
    """

    request_id: str
    action: str
    target: str
    mode: str = "dry_run"
    risk_score: float = 0.5
    authorization_id: str = ""
    before_state: Dict[str, Any] = field(default_factory=dict)
    after_state: Dict[str, Any] = field(default_factory=dict)
    execution_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    status: str = CTX_CREATED
    # 附加轨迹：状态迁移历史 [(status, at_iso), ...]，审计友好
    history: list = field(default_factory=list)
    # 拦截 / 失败原因
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.execution_id:
            self.execution_id = f"exe_{uuid.uuid4().hex[:12]}"
        if not self.started_at:
            self.started_at = _now_iso()
        self.action = _as_str(self.action)
        self.mode = _as_str(self.mode)
        if self.status not in VALID_CONTEXT_STATUSES:
            raise ValueError(f"invalid context status: {self.status}")
        if not self.history:
            self.history = [(self.status, self.started_at)]

    # -- 状态机 -------------------------------------------------------------

    def transition(self, new_status: str, reason: str = "") -> None:
        """执行一次状态迁移；非法迁移抛 InvalidTransitionError。"""
        if new_status not in VALID_CONTEXT_STATUSES:
            raise InvalidTransitionError(f"unknown status: {new_status}")
        allowed = _ALLOWED_TRANSITIONS.get(self.status, ())
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"illegal transition {self.status} -> {new_status}"
            )
        self.status = new_status
        now = _now_iso()
        self.history.append((new_status, now))
        if reason:
            self.reason = reason
        if new_status in TERMINAL_CONTEXT_STATUSES:
            self.finished_at = now

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_CONTEXT_STATUSES

    @property
    def is_production(self) -> bool:
        return self.mode == "production"

    # -- 序列化 --------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "request_id": self.request_id,
            "action": _as_str(self.action),
            "target": self.target,
            "mode": _as_str(self.mode),
            "risk_score": self.risk_score,
            "authorization_id": self.authorization_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "history": [list(item) for item in self.history],
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SafeExecutionContext":
        ctx = cls(
            request_id=str(data.get("request_id", "")),
            action=str(data.get("action", "")),
            target=str(data.get("target", "")),
            mode=str(data.get("mode", "dry_run")),
            risk_score=float(data.get("risk_score", 0.5)),
            authorization_id=str(data.get("authorization_id", "")),
            before_state=data.get("before_state") or {},
            after_state=data.get("after_state") or {},
            execution_id=str(data.get("execution_id", "")),
            started_at=str(data.get("started_at", "")),
            finished_at=str(data.get("finished_at", "")),
            status=str(data.get("status", CTX_CREATED)),
            reason=str(data.get("reason", "")),
        )
        history = data.get("history") or []
        if history:
            ctx.history = [tuple(item) for item in history]
        return ctx

    @classmethod
    def from_request(cls, request: Any) -> "SafeExecutionContext":
        """从 P2.1 ExecutionRequest 构造上下文（不修改原请求）。"""
        intent = getattr(request, "intent", None)
        authorization = getattr(request, "authorization", None)
        return cls(
            request_id=getattr(request, "request_id", ""),
            action=_as_str(getattr(intent, "action", "")),
            target=str(getattr(intent, "target_id", "")),
            mode=_as_str(getattr(request, "mode", "dry_run")),
            risk_score=float(getattr(intent, "risk_level", 0.5) or 0.0),
            authorization_id=str(getattr(authorization, "approval_id", "") or ""),
        )


# ---------------------------------------------------------------------------
# RollbackCapability / RollbackPlan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RollbackCapability:
    """Provider 声明：original_action 可用 rollback_action 撤销。

    平台声明（用户契约）：
        MAX  : disable_network -> enable_network
        Meta : pause_campaign  -> active_campaign
        Play : create_release  -> delete_draft
    """

    provider: str
    original_action: str
    rollback_action: str
    description: str = ""

    def matches(self, provider: str, action: Any) -> bool:
        return self.provider == provider and self.original_action == _as_str(action)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "original_action": _as_str(self.original_action),
            "rollback_action": _as_str(self.rollback_action),
            "description": self.description,
        }


@dataclass
class RollbackPlan:
    """一次具体回滚的执行计划（用户契约字段）。"""

    original_action: str
    rollback_action: str
    snapshot: Dict[str, Any]
    provider: str
    execution_id: str = ""
    target: str = ""
    plan_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = f"rbp_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now_iso()
        self.original_action = _as_str(self.original_action)
        self.rollback_action = _as_str(self.rollback_action)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "execution_id": self.execution_id,
            "original_action": self.original_action,
            "rollback_action": self.rollback_action,
            "snapshot": self.snapshot,
            "provider": self.provider,
            "target": self.target,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RollbackPlan":
        return cls(
            original_action=str(data.get("original_action", "")),
            rollback_action=str(data.get("rollback_action", "")),
            snapshot=data.get("snapshot") or {},
            provider=str(data.get("provider", "")),
            execution_id=str(data.get("execution_id", "")),
            target=str(data.get("target", "")),
            plan_id=str(data.get("plan_id", "")),
            created_at=str(data.get("created_at", "")),
        )


# ---------------------------------------------------------------------------
# SafeExecutionOutcome
# ---------------------------------------------------------------------------


@dataclass
class SafeExecutionOutcome:
    """SafeExecutor 的最终交付物。

    Fields:
        context   : SafeExecutionContext（全生命周期）
        result    : P2.2 ExecutionResult（BLOCKED 前置拦截时可为 None）
        verdict   : VERDICT_* 之一
        rollback  : 回滚执行详情（未回滚为 None）
        escalated : Rule 5——回滚失败需要人工介入
    """

    context: SafeExecutionContext
    result: Optional[Any] = None
    verdict: str = VERDICT_BLOCKED
    rollback: Optional[Dict[str, Any]] = None
    escalated: bool = False

    def __post_init__(self) -> None:
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"invalid verdict: {self.verdict}")

    @property
    def ok(self) -> bool:
        return self.verdict in (VERDICT_EXECUTED, VERDICT_RETURN_EXISTING)

    def to_dict(self) -> Dict[str, Any]:
        result = self.result
        if result is not None and hasattr(result, "to_dict"):
            result = result.to_dict()
        return {
            "context": self.context.to_dict(),
            "result": result,
            "verdict": self.verdict,
            "rollback": self.rollback,
            "escalated": self.escalated,
        }


__all__ = [
    # 状态常量
    "CTX_CREATED",
    "CTX_VALIDATING",
    "CTX_SNAPSHOTTING",
    "CTX_EXECUTING",
    "CTX_VERIFYING",
    "CTX_SUCCESS",
    "CTX_FAILED",
    "CTX_ROLLED_BACK",
    "CTX_BLOCKED",
    "VALID_CONTEXT_STATUSES",
    "TERMINAL_CONTEXT_STATUSES",
    # verdict 常量
    "VERDICT_EXECUTED",
    "VERDICT_RETURN_EXISTING",
    "VERDICT_BLOCKED",
    "VERDICT_ROLLED_BACK",
    "VERDICT_ESCALATED",
    "VERDICT_FAILED",
    "VALID_VERDICTS",
    # 模型
    "InvalidTransitionError",
    "SafeExecutionContext",
    "RollbackCapability",
    "RollbackPlan",
    "SafeExecutionOutcome",
]
