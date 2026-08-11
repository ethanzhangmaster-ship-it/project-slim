"""P2.1 Execution Contract Layer — Decision → Intent 映射器。

把 E17.3 的 GrowthDecision（「决策语言」）翻译成本层的 ExecutionIntent
（「手部动作语言」）。映射表是 P2 执行语义的单一事实来源。

映射规则（用户验收 Mapping Table）：

    E17.3 决策动作           →  P2 执行动作 / 域
    REVENUE_RECOVERY        →  CREATE_INVESTIGATION  (REVENUE)
    CREATIVE_REFRESH        →  CREATE_ASO_UPDATE     (ASO)
    UA_SCALE                →  SCALE_BUDGET          (UA)
    UA_STOP                 →  PAUSE_CAMPAIGN        (UA)
    MAX_OPTIMIZE            →  DISABLE_NETWORK       (AD_MONETIZATION)

补充同义动作（来自 E17.2 opportunity 命名）：
    UA_STOP_LOSS            →  PAUSE_CAMPAIGN        (UA)
    ASO_OPTIMIZATION        →  CREATE_ASO_UPDATE     (ASO)
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.ceo_intelligence.decision_engine.models import (
    DecisionType,
    GrowthDecision,
)

from .intent import build_intent, risk_band
from .models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)
from .registry import CapabilityRegistry


class UnmappedDecisionAction(ValueError):
    """决策动作无法映射到任何 P2 执行动作。"""


# 决策动作 → (执行动作, 执行域)。键统一用大写规整。
_DECISION_ACTION_MAP: Dict[str, Tuple[ExecutionAction, ExecutionDomain]] = {
    "REVENUE_RECOVERY": (ExecutionAction.CREATE_INVESTIGATION, ExecutionDomain.REVENUE),
    "CREATIVE_REFRESH": (ExecutionAction.CREATE_ASO_UPDATE, ExecutionDomain.ASO),
    "UA_SCALE": (ExecutionAction.SCALE_BUDGET, ExecutionDomain.UA),
    "UA_STOP": (ExecutionAction.PAUSE_CAMPAIGN, ExecutionDomain.UA),
    "MAX_OPTIMIZE": (ExecutionAction.DISABLE_NETWORK, ExecutionDomain.AD_MONETIZATION),
    # 同义（E17.2 opportunity 命名）
    "UA_STOP_LOSS": (ExecutionAction.PAUSE_CAMPAIGN, ExecutionDomain.UA),
    "ASO_OPTIMIZATION": (ExecutionAction.CREATE_ASO_UPDATE, ExecutionDomain.ASO),
}


def normalize_action(action: str) -> str:
    """把决策动作归一化为查表键（去空格、转大写）。"""
    return action.strip().upper()


class DecisionToIntentMapper:
    """GrowthDecision → ExecutionIntent。"""

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        # registry 仅用于下游校验时的能力查询；映射本身不依赖它
        self.registry = registry

    # ------------------------------------------------------------------
    # 查表
    # ------------------------------------------------------------------
    @staticmethod
    def lookup(action: str) -> Optional[Tuple[ExecutionAction, ExecutionDomain]]:
        return _DECISION_ACTION_MAP.get(normalize_action(action))

    @staticmethod
    def known_decision_action(action: str) -> bool:
        return normalize_action(action) in _DECISION_ACTION_MAP

    # ------------------------------------------------------------------
    # 映射
    # ------------------------------------------------------------------
    def map(self, decision: GrowthDecision) -> ExecutionIntent:
        """把一个决策翻译成执行意图。

        未映射的决策动作 → 抛 UnmappedDecisionAction（由上层转成 BLOCKED 合同）。
        REJECT 决策 → 同样抛 UnmappedDecisionAction（拒绝即不执行）。
        """
        if decision.decision_type == DecisionType.REJECT:
            raise UnmappedDecisionAction(
                f"决策被拒绝（REJECT）：{decision.action} 不生成执行意图"
            )

        mapped = self.lookup(decision.action)
        if mapped is None:
            raise UnmappedDecisionAction(
                f"决策动作 {decision.action!r} 无法映射到任何 P2 执行动作"
            )
        action, domain = mapped

        # 预期影响：从决策的 expected_value + 模拟结果结构化
        expected_impact: Dict[str, object] = {
            "expected_value": decision.expected_value,
        }
        if decision.simulation is not None:
            expected_impact["expected_revenue_change"] = (
                decision.simulation.expected_revenue_change
            )
            expected_impact["expected_roas_change"] = (
                decision.simulation.expected_roas_change
            )

        # requires_approval 初判：决策出口已要求审批，或风险达 mid/high 档
        decision_forces_approval = decision.decision_type in (
            DecisionType.APPROVE,
            DecisionType.OBSERVE,
        )
        risk_forces_approval = risk_band(decision.risk) in ("mid", "high")
        requires_approval = decision_forces_approval or risk_forces_approval

        return build_intent(
            decision_id=decision.audit_id or decision.opportunity_id,
            domain=domain,
            action=action,
            target_id=decision.game_id,
            reason=decision.reason,
            confidence=decision.confidence,
            expected_impact=expected_impact,
            risk_level=decision.risk,
            requires_approval=requires_approval,
        )

    # ------------------------------------------------------------------
    # 便捷封装：直接出 Request
    # ------------------------------------------------------------------
    def build_request(
        self,
        decision: GrowthDecision,
        mode: ExecutionMode = ExecutionMode.DRY_RUN,
    ) -> ExecutionRequest:
        intent = self.map(decision)
        return ExecutionRequest(intent=intent, mode=mode)


__all__ = [
    "UnmappedDecisionAction",
    "normalize_action",
    "DecisionToIntentMapper",
]
