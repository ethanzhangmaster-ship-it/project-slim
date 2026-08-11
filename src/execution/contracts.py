"""P2.1 Execution Contract Layer — 执行合同（Execution Contract）聚合。

把一个 GrowthDecision 端到端打包成一份「执行合同」：
    Decision → Intent → (Validator) → Request → AuditTrail

这是 P2 执行语义的单一交付物：下游 P2.2 Provider 只认 ExecutionContract，
不再关心 E17.3 的决策细节。

本层不调用任何真实 API（SIM 纪律）：
- mode 默认 DRY_RUN
- 仅在 intent 通过安全门（非 BLOCKED）时才生成 Request
- 生成 Intent 时通过 EP0 AuditTrail 记录 execution_intent_created 事件
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from audit.trail import AuditTrail, DecisionRecord

from src.ceo_intelligence.decision_engine.models import (
    DecisionType,
    GrowthDecision,
)

from .intent import describe, intent_summary_dict
from .mapper import DecisionToIntentMapper, UnmappedDecisionAction
from .models import ExecutionIntent, ExecutionMode, ExecutionRequest
from .registry import CapabilityRegistry
from .validator import (
    ExecutionContractValidator,
    ValidationResult,
    ValidationStatus,
)


@dataclass
class ExecutionContract:
    """一份完整的执行合同（不可变交付物）。"""

    decision_id: str
    status: ValidationStatus
    reason: str
    intent: Optional[ExecutionIntent] = None
    validation: Optional[ValidationResult] = None
    request: Optional[ExecutionRequest] = None

    @property
    def blocked(self) -> bool:
        return self.status == ValidationStatus.BLOCKED

    @property
    def needs_approval(self) -> bool:
        return self.status == ValidationStatus.NEEDS_APPROVAL

    @property
    def approved_auto(self) -> bool:
        return self.status == ValidationStatus.APPROVED

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "status": self.status.value,
            "reason": self.reason,
            "intent": self.intent.to_dict() if self.intent else None,
            "validation": self.validation.to_dict() if self.validation else None,
            "request": self.request.to_dict() if self.request else None,
        }


def _record_audit(
    audit_trail: Optional[AuditTrail],
    intent: ExecutionIntent,
    mode: ExecutionMode,
) -> None:
    if audit_trail is None:
        return
    audit_trail.record_decision(
        DecisionRecord(
            agent="execution_contract",
            action="execution_intent_created",
            game_id=intent.target_id,
            reason=(
                f"决策 {intent.decision_id} → 意图 {intent.intent_id} "
                f"({intent.action.value}, mode={mode.value})"
            ),
            confidence=intent.confidence,
            decision_id=intent.decision_id,
            inputs={
                "intent_id": intent.intent_id,
                "domain": intent.domain.value,
                "action": intent.action.value,
                "mode": mode.value,
                "requires_approval": intent.requires_approval,
                "summary": intent_summary_dict(intent),
                "describe": describe(intent),
            },
        )
    )


def build_contract(
    decision: GrowthDecision,
    registry: Optional[CapabilityRegistry] = None,
    validator: Optional[ExecutionContractValidator] = None,
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
    audit_trail: Optional[AuditTrail] = None,
) -> ExecutionContract:
    """端到端把决策打包成执行合同。

    返回 ExecutionContract（含 status / intent / validation / request）。
    对 REJECT 或未映射动作，返回 BLOCKED 合同且不生成 Request。
    """
    reg = registry if registry is not None else CapabilityRegistry()
    val = validator if validator is not None else ExecutionContractValidator(reg)
    mapper = DecisionToIntentMapper(registry=reg)

    # 1) REJECT：直接 BLOCKED
    if decision.decision_type == DecisionType.REJECT:
        return ExecutionContract(
            decision_id=decision.audit_id or decision.opportunity_id,
            status=ValidationStatus.BLOCKED,
            reason=f"决策被拒绝（REJECT）：{decision.action} 不生成执行合同",
        )

    # 2) 映射：未知决策动作 → BLOCKED
    try:
        intent = mapper.map(decision)
    except UnmappedDecisionAction as exc:
        return ExecutionContract(
            decision_id=decision.audit_id or decision.opportunity_id,
            status=ValidationStatus.BLOCKED,
            reason=f"未映射决策动作：{exc}",
        )

    # 3) 安全校验
    result = val.validate(intent)

    # 4) 仅非 BLOCKED 才生成 Request 并记录审计
    request: Optional[ExecutionRequest] = None
    if result.status != ValidationStatus.BLOCKED:
        request = ExecutionRequest(intent=intent, mode=mode)
        _record_audit(audit_trail, intent, mode)

    return ExecutionContract(
        decision_id=decision.audit_id or decision.opportunity_id,
        status=result.status,
        reason=result.reason,
        intent=intent,
        validation=result,
        request=request,
    )


__all__ = [
    "ExecutionContract",
    "build_contract",
]
