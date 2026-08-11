"""P2.1 Execution Contract Layer — 安全校验（Safety Validation）。

执行合同的第一道安全门（在真实 API 之前）。

放行规则（与 intent.risk_band 一致）：
- UNKNOWN 动作（注册表里没有）→ BLOCKED（禁止执行未知动作）
- 注册权限为 blocked → BLOCKED
- 注册权限为 approval（动作本身强制人工）→ NEEDS_APPROVAL
- 风险 >= LOW_RISK_THRESHOLD（mid/high 风险）→ NEEDS_APPROVAL
- 低风险 + 已注册 + 非强制审批 → APPROVED（可自动执行）
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .intent import LOW_RISK_THRESHOLD, risk_band
from .models import ExecutionIntent
from .registry import CapabilityRegistry, Permission


class ValidationStatus(str, Enum):
    APPROVED = "approved"            # 通过安全门，可自动执行（仍需 mode=PRODUCTION）
    NEEDS_APPROVAL = "needs_approval"  # 需人工审批后才可执行
    BLOCKED = "blocked"              # 禁止执行


@dataclass
class ValidationResult:
    intent_id: str
    status: ValidationStatus
    requires_approval: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "intent_id": self.intent_id,
            "status": self.status.value,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
        }


class ExecutionContractValidator:
    """对 ExecutionIntent 做安全校验。

    纯函数式、无副作用。可注入 CapabilityRegistry；缺省使用空表
    （空表下所有动作都视为 UNKNOWN → BLOCKED，强制显式登记能力）。
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry if registry is not None else CapabilityRegistry()

    def validate(self, intent: ExecutionIntent) -> ValidationResult:
        action = intent.action

        # 1) 未知动作：注册表里没有 → 禁止
        if not self.registry.is_known(action):
            return ValidationResult(
                intent_id=intent.intent_id,
                status=ValidationStatus.BLOCKED,
                requires_approval=True,
                reason=f"未知动作 {action.value!r}：未在 CapabilityRegistry 登记，禁止执行",
            )

        # 2) 注册权限黑名单
        if self.registry.is_blocked(action):
            return ValidationResult(
                intent_id=intent.intent_id,
                status=ValidationStatus.BLOCKED,
                requires_approval=True,
                reason=f"动作 {action.value!r} 已被注册表禁止（permission=blocked）",
            )

        # 3) 注册权限强制人工审批
        if self.registry.requires_approval(action):
            return ValidationResult(
                intent_id=intent.intent_id,
                status=ValidationStatus.NEEDS_APPROVAL,
                requires_approval=True,
                reason=f"动作 {action.value!r} 注册为强制人工审批（permission=approval）",
            )

        # 4) 风险门槛：mid/high 风险必须人工
        if intent.risk_level >= LOW_RISK_THRESHOLD:
            return ValidationResult(
                intent_id=intent.intent_id,
                status=ValidationStatus.NEEDS_APPROVAL,
                requires_approval=True,
                reason=(
                    f"风险 {intent.risk_level:.2f} 属于 {risk_band(intent.risk_level)} 档"
                    f"（>= {LOW_RISK_THRESHOLD}），需人工审批"
                ),
            )

        # 5) 通过：低风险 + 已登记 + 非强制审批
        return ValidationResult(
            intent_id=intent.intent_id,
            status=ValidationStatus.APPROVED,
            requires_approval=False,
            reason=f"低风险（{intent.risk_level:.2f}）且已登记，可自动执行",
        )

    def is_blocked(self, intent: ExecutionIntent) -> bool:
        return self.validate(intent).status == ValidationStatus.BLOCKED

    def is_approved_auto(self, intent: ExecutionIntent) -> bool:
        return self.validate(intent).status == ValidationStatus.APPROVED


__all__ = [
    "ValidationStatus",
    "ValidationResult",
    "ExecutionContractValidator",
    "Permission",
]
