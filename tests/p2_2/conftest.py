"""P2.2 测试辅助：构造 ExecutionIntent / ExecutionRequest 的工厂。

避免每个测试重复样板，集中管理验收所需的默认参数。
"""
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)


def make_intent(
    action: ExecutionAction,
    target_id: str = "p04_merge_witch",
    domain: ExecutionDomain = ExecutionDomain.AD_MONETIZATION,
    *,
    risk_level: float = 0.2,
    confidence: float = 0.9,
    expected_impact: dict | None = None,
    reason: str = "test intent",
    decision_id: str = "dec_test",
    intent_id: str = "",
) -> ExecutionIntent:
    return ExecutionIntent(
        intent_id=intent_id,
        decision_id=decision_id,
        domain=domain,
        action=action,
        target_id=target_id,
        reason=reason,
        confidence=confidence,
        expected_impact=expected_impact or {},
        risk_level=risk_level,
    )


def make_request(
    action: ExecutionAction,
    *,
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
    target_id: str = "p04_merge_witch",
    domain: ExecutionDomain = ExecutionDomain.AD_MONETIZATION,
    risk_level: float = 0.2,
    expected_impact: dict | None = None,
    request_id: str = "",
) -> ExecutionRequest:
    intent = make_intent(
        action,
        target_id=target_id,
        domain=domain,
        risk_level=risk_level,
        expected_impact=expected_impact,
    )
    return ExecutionRequest(intent=intent, mode=mode, request_id=request_id)
