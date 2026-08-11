"""P2.1 Execution Contract Layer — ExecutionIntent 构建器与辅助。

提供从原始字段构造 ExecutionIntent 的工厂函数、风险分级辅助、以及
from_dict / to_dict 之外的便捷序列化（便于审计落盘与跨进程传递）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    action_label,
    domain_label,
)


# 风险分级阈值（与 validator 共用语义）
LOW_RISK_THRESHOLD = 0.4   # risk_level < 0.4 → 低风险，可自动批准
MID_RISK_THRESHOLD = 0.7   # risk_level >= 0.7 → 高风险，强制人工


def risk_band(risk_level: float) -> str:
    """把 0-1 风险分数映射为人类可读档位。"""
    if risk_level < LOW_RISK_THRESHOLD:
        return "low"
    if risk_level < MID_RISK_THRESHOLD:
        return "mid"
    return "high"


def build_intent(
    decision_id: str,
    domain: ExecutionDomain,
    action: ExecutionAction,
    target_id: str,
    reason: str,
    confidence: float,
    *,
    expected_impact: Optional[Dict[str, Any]] = None,
    risk_level: float = 0.5,
    requires_approval: Optional[bool] = None,
    intent_id: str = "",
) -> ExecutionIntent:
    """构造一个 ExecutionIntent。

    requires_approval 缺省由风险档位推导：mid/high 风险默认需要审批。
    """
    if requires_approval is None:
        requires_approval = risk_band(risk_level) in ("mid", "high")
    return ExecutionIntent(
        intent_id=intent_id,
        decision_id=decision_id,
        domain=domain,
        action=action,
        target_id=target_id,
        reason=reason,
        confidence=confidence,
        expected_impact=expected_impact,
        risk_level=risk_level,
        requires_approval=requires_approval,
    )


def describe(intent: ExecutionIntent) -> str:
    """人类可读的单行描述，便于日志 / 审计 / CEO 报告。"""
    return (
        f"[{intent.intent_id}] {domain_label(intent.domain)} / "
        f"{action_label(intent.action)} → {intent.target_id} "
        f"(conf={intent.confidence:.0%}, risk={risk_band(intent.risk_level)}, "
        f"approval={'Y' if intent.requires_approval else 'N'})"
    )


def intent_summary_dict(intent: ExecutionIntent) -> Dict[str, Any]:
    """审计友好的摘要字典。"""
    return {
        "intent_id": intent.intent_id,
        "decision_id": intent.decision_id,
        "domain": intent.domain.value,
        "action": intent.action.value,
        "target_id": intent.target_id,
        "confidence": round(intent.confidence, 4),
        "risk_level": round(intent.risk_level, 4),
        "risk_band": risk_band(intent.risk_level),
        "requires_approval": intent.requires_approval,
    }


__all__ = [
    "LOW_RISK_THRESHOLD",
    "MID_RISK_THRESHOLD",
    "risk_band",
    "build_intent",
    "describe",
    "intent_summary_dict",
]
