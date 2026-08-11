"""P2.4.4 Rollback Engine — 失败回滚与升级。

Execution Policy：
    Rule 4：Provider 执行失败 -> 尝试回滚（有 RollbackCapability 才回滚）
    Rule 5：回滚也失败 -> ESCALATE（升级人工，绝不静默）

平台回滚能力声明（用户契约）：
    MAX  : disable_network -> enable_network
    Meta : pause_campaign  -> active_campaign
    Play : create_release  -> delete_draft

Provider 侧契约：``rollback(plan: RollbackPlan) -> Dict``，返回至少含
``{"success": bool}``；未实现 rollback 视为无回滚能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.execution.safe_executor.models import (
    RollbackCapability,
    RollbackPlan,
)

# 回滚结果状态
RB_SUCCESS = "ROLLBACK_SUCCESS"
RB_FAILED = "ROLLBACK_FAILED"
RB_ESCALATED = "ESCALATED"          # Rule 5：回滚失败升级人工
RB_NOT_SUPPORTED = "NOT_SUPPORTED"  # 无回滚能力（不算失败，但需记录）


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_str(value: Any) -> str:
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# 默认回滚能力注册表（三平台声明）
# ---------------------------------------------------------------------------

DEFAULT_CAPABILITIES: List[RollbackCapability] = [
    RollbackCapability(
        provider="max",
        original_action="disable_network",
        rollback_action="enable_network",
        description="MAX 关停网络的逆操作：重新启用该广告网络",
    ),
    RollbackCapability(
        provider="meta",
        original_action="pause_campaign",
        rollback_action="active_campaign",
        description="Meta 暂停广告系列的逆操作：恢复投放",
    ),
    RollbackCapability(
        provider="play",
        original_action="create_release",
        rollback_action="delete_draft",
        description="Play 创建发布的逆操作：删除草稿 release",
    ),
]


class RollbackRegistry:
    """RollbackCapability 注册表：provider+action -> 回滚能力。"""

    def __init__(self, capabilities: Optional[List[RollbackCapability]] = None):
        self._caps: List[RollbackCapability] = list(
            DEFAULT_CAPABILITIES if capabilities is None else capabilities
        )

    def register(self, capability: RollbackCapability) -> None:
        self._caps.append(capability)

    def lookup(self, provider: str, action: Any) -> Optional[RollbackCapability]:
        action_str = _as_str(action)
        for cap in self._caps:
            if cap.matches(provider, action_str):
                return cap
        return None

    def supports(self, provider: str, action: Any) -> bool:
        return self.lookup(provider, action) is not None

    @property
    def capabilities(self) -> List[RollbackCapability]:
        return list(self._caps)


# ---------------------------------------------------------------------------
# RollbackResult
# ---------------------------------------------------------------------------


@dataclass
class RollbackResult:
    """一次回滚尝试的结果。"""

    plan_id: str
    execution_id: str
    provider: str
    rollback_action: str
    status: str  # RB_* 之一
    detail: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now_iso()

    @property
    def ok(self) -> bool:
        return self.status == RB_SUCCESS

    @property
    def escalated(self) -> bool:
        return self.status == RB_ESCALATED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "execution_id": self.execution_id,
            "provider": self.provider,
            "rollback_action": self.rollback_action,
            "status": self.status,
            "detail": self.detail,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# RollbackEngine
# ---------------------------------------------------------------------------


class RollbackEngine:
    """构建 RollbackPlan 并调 Provider 执行回滚。

    - build_plan：查注册表；无能力返回 None（调用方记 NOT_SUPPORTED）
    - execute：调 provider.rollback(plan)；失败 / 异常 / 未实现 -> ESCALATED
    """

    def __init__(self, registry: Optional[RollbackRegistry] = None):
        self.registry = registry or RollbackRegistry()

    def build_plan(
        self,
        provider_id: str,
        action: Any,
        snapshot: Dict[str, Any],
        execution_id: str = "",
        target: str = "",
    ) -> Optional[RollbackPlan]:
        cap = self.registry.lookup(provider_id, action)
        if cap is None:
            return None
        return RollbackPlan(
            original_action=_as_str(action),
            rollback_action=cap.rollback_action,
            snapshot=dict(snapshot or {}),
            provider=provider_id,
            execution_id=execution_id,
            target=target,
        )

    def execute(self, plan: RollbackPlan, provider: Any) -> RollbackResult:
        """执行回滚；任何失败都转 ESCALATED（Rule 5），绝不抛出。"""
        fn = getattr(provider, "rollback", None)
        if not callable(fn):
            return RollbackResult(
                plan_id=plan.plan_id,
                execution_id=plan.execution_id,
                provider=plan.provider,
                rollback_action=plan.rollback_action,
                status=RB_ESCALATED,
                error=(
                    f"provider {plan.provider} 未实现 rollback(plan)，"
                    "无法自动回滚，需人工介入"
                ),
            )
        try:
            detail = fn(plan)
        except Exception as exc:  # noqa: BLE001 — 回滚异常必须升级而非炸链路
            return RollbackResult(
                plan_id=plan.plan_id,
                execution_id=plan.execution_id,
                provider=plan.provider,
                rollback_action=plan.rollback_action,
                status=RB_ESCALATED,
                error=f"rollback raised {type(exc).__name__}: {exc}",
            )

        detail = detail if isinstance(detail, dict) else {"raw": detail}
        if detail.get("success"):
            return RollbackResult(
                plan_id=plan.plan_id,
                execution_id=plan.execution_id,
                provider=plan.provider,
                rollback_action=plan.rollback_action,
                status=RB_SUCCESS,
                detail=detail,
            )
        return RollbackResult(
            plan_id=plan.plan_id,
            execution_id=plan.execution_id,
            provider=plan.provider,
            rollback_action=plan.rollback_action,
            status=RB_ESCALATED,
            detail=detail,
            error=str(detail.get("error", "rollback reported failure")),
        )


__all__ = [
    "RB_SUCCESS",
    "RB_FAILED",
    "RB_ESCALATED",
    "RB_NOT_SUPPORTED",
    "DEFAULT_CAPABILITIES",
    "RollbackRegistry",
    "RollbackResult",
    "RollbackEngine",
]
