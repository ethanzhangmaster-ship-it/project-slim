"""P2.6.4 Recovery Planner — 恢复计划生成器。

输入：FailureClassification + 原始动作/风险/回滚能力，
输出：RecoveryPlan（策略 + 重试参数 + 期望状态）。

    Failure + Risk + Capability -> RecoveryPlan

示例（用户契约）：
    action=PAUSE_CAMPAIGN, failure=TIMEOUT, risk=0.4
    -> strategy=RETRY, max_attempts=3, backoff=[1,5,30]

安全规则：
- HIGH / CRITICAL severity 一律强制 ESCALATION（不做任何自动恢复）
- treatment=ESCALATE / EMERGENCY_ESCALATE 一律 ESCALATION
- 高风险动作（risk >= RISK_ESCALATE_THRESHOLD=0.7）即使可重试也升级——
  钱类高危动作不值得自动重放
- 本层只产计划，不执行。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.execution.recovery.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
    STRATEGY_ROLLBACK_RETRY,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    TREATMENT_ROLLBACK_RETRY,
    FailureClassification,
    RecoveryIncident,
    RecoveryPlan,
    _as_str,
    severity_rank,
)
from src.execution.recovery.strategy import (
    EscalationPolicy,
    policy_for_treatment,
)

# 风险阈值：>= 0.7 的动作不自动恢复，直接升级
RISK_ESCALATE_THRESHOLD = 0.7

_TREATMENT_STRATEGY = {
    TREATMENT_RETRY: STRATEGY_RETRY,
    TREATMENT_RECONCILE: STRATEGY_RECONCILE,
    TREATMENT_ROLLBACK_RETRY: STRATEGY_ROLLBACK_RETRY,
}


class RecoveryPlanner:
    """确定性恢复计划生成器（无 I/O、无网络、无 LLM）。"""

    def __init__(self, risk_escalate_threshold: float = RISK_ESCALATE_THRESHOLD):
        self.risk_escalate_threshold = risk_escalate_threshold

    def plan(
        self,
        classification: FailureClassification,
        action: str = "",
        target: str = "",
        provider: str = "",
        risk: float = 0.5,
        rollback_action: str = "",
        expected_state: Optional[Dict[str, Any]] = None,
        incident: Optional[RecoveryIncident] = None,
    ) -> RecoveryPlan:
        """生成恢复计划。

        Args:
            classification : FailureClassifier 的分类结果
            action         : 恢复要重放的动作（缺省取 classification.action）
            target         : 执行目标
            provider       : 落地 Provider（缺省取 classification.provider）
            risk           : 原始 intent.risk_level（0..1）
            rollback_action: ROLLBACK_RETRY 时要重放的回滚动作
            expected_state : 恢复成功后的期望状态（供 Verifier 比对）
            incident       : 可选事件；传入则推进状态机 CLASSIFIED->PLANNED
                            （ESCALATION 计划则 CLASSIFIED->ESCALATED 由
                             Escalation 阶段统一处理，这里仍走 PLANNED）

        Returns:
            RecoveryPlan
        """
        action = _as_str(action or classification.action)
        provider = provider or classification.provider
        treatment = _as_str(classification.treatment)
        severity = _as_str(classification.severity)
        risk = float(risk)

        escalation_reason = self._escalation_reason(treatment, severity, risk)

        if escalation_reason:
            policy = EscalationPolicy()
            plan = RecoveryPlan(
                incident_id=classification.incident_id,
                strategy=STRATEGY_ESCALATION,
                action=action,
                target=target,
                provider=provider,
                max_attempts=policy.max_attempts,
                backoff=list(policy.backoff),
                risk_level=risk,
                expected_state=dict(expected_state or {}),
                escalate_only=True,
                rollback_action=_as_str(rollback_action),
                notes=escalation_reason,
            )
        else:
            policy = policy_for_treatment(treatment)
            strategy = _TREATMENT_STRATEGY.get(treatment, STRATEGY_ESCALATION)
            plan = RecoveryPlan(
                incident_id=classification.incident_id,
                strategy=strategy,
                action=action,
                target=target,
                provider=provider,
                max_attempts=policy.max_attempts,
                backoff=list(policy.backoff),
                risk_level=risk,
                expected_state=dict(expected_state or {}),
                escalate_only=False,
                rollback_action=_as_str(rollback_action),
                notes=(
                    f"treatment={treatment} severity={severity} risk={risk:.2f}"
                ),
            )

        if incident is not None and incident.status == "CLASSIFIED":
            incident.transition("PLANNED", reason=plan.notes)
        return plan

    # ------------------------------------------------------------------

    def _escalation_reason(
        self, treatment: str, severity: str, risk: float
    ) -> str:
        """返回强制升级原因；空字符串表示可自动恢复。"""
        # Rule 1 — 分类器直接要求升级
        if treatment not in _TREATMENT_STRATEGY:
            return f"treatment {treatment} requires manual intervention"
        # Rule 2 — HIGH / CRITICAL severity 强制升级
        if severity_rank(severity) >= severity_rank(SEVERITY_HIGH):
            return f"severity {severity} forces escalation"
        # Rule 3 — 高风险动作不自动重放
        if risk >= self.risk_escalate_threshold:
            return (
                f"risk {risk:.2f} >= {self.risk_escalate_threshold:.2f}, "
                "auto-recovery not allowed for high-risk action"
            )
        return ""


__all__ = ["RecoveryPlanner", "RISK_ESCALATE_THRESHOLD"]
