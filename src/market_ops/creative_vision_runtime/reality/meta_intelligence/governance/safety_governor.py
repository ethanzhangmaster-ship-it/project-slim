"""E12.6.3 — Safety Governor。

核心安全控制器。

整合:
  - RiskDetector:     风险评估
  - SafetyPolicy:     安全策略规则
  - RollbackManager:  回滚管理

流程:
  SafetyContext → RiskDetector → PolicyEngine → SafetyDecision
                                              → ALLOW / MODIFY / BLOCK / ROLLBACK
"""

from __future__ import annotations

from typing import Any

from .models import (
    RiskLevel,
    RollbackRecord,
    SafetyAction,
    SafetyContext,
    SafetyDecision,
    RiskReport,
    get_safety_action_priority,
)
from .risk_detector import RiskDetector
from .safety_policy import (
    DEFAULT_SAFETY_POLICIES,
    SafetyPolicy,
)
from .rollback_manager import RollbackManager


class SafetyGovernor:
    """安全治理器 —— E12.6.3 核心。

    职责:
      1. 接收 SafetyContext
      2. 运行 RiskDetector 评估风险
      3. 运行 SafetyPolicy 引擎
      4. 输出 SafetyDecision（ALLOW/MODIFY/BLOCK/ROLLBACK）
      5. 必要时触发 RollbackManager
    """

    def __init__(
        self,
        policies: list[SafetyPolicy] | None = None,
        risk_detector: RiskDetector | None = None,
        rollback_manager: RollbackManager | None = None,
        default_action: SafetyAction = SafetyAction.ALLOW,
    ) -> None:
        """初始化 Safety Governor。

        Args:
            policies:         安全策略列表
            risk_detector:    风险评估器
            rollback_manager: 回滚管理器
            default_action:   默认安全动作（无策略触发时）
        """
        self.policies = policies if policies is not None else list(DEFAULT_SAFETY_POLICIES)
        self.risk_detector = risk_detector or RiskDetector()
        self.rollback_manager = rollback_manager or RollbackManager()
        self.default_action = default_action

    def evaluate(self, context: SafetyContext) -> SafetyDecision:
        """核心评估接口。

        流程:
          1. RiskDetector → RiskReport
          2. 评估所有 SafetyPolicy
          3. 选择最严格的决策
          4. 如果是 ROLLBACK，触发 RollbackManager

        Args:
            context: 安全评估上下文

        Returns:
            SafetyDecision
        """
        # 1. 风险评估
        risk_report = self.risk_detector.evaluate(context)

        # 2. 评估所有策略
        decisions = self._evaluate_policies(context, risk_report)

        # 3. 选择最严格的决策
        final_decision = self._select_strictest(decisions, context, risk_report)

        # 4. 如果是 ROLLBACK，触发回滚
        if final_decision.action == SafetyAction.ROLLBACK:
            self._trigger_rollback(context, final_decision)

        return final_decision

    def _evaluate_policies(
        self,
        context: SafetyContext,
        risk_report: RiskReport,
    ) -> list[SafetyDecision]:
        """评估所有安全策略。"""
        decisions: list[SafetyDecision] = []
        for policy in self.policies:
            result = policy.evaluate(context, risk_report)
            if result is not None:
                result.risk_report = risk_report
                result.context_snapshot = context.to_dict()
                decisions.append(result)
        return decisions

    def _select_strictest(
        self,
        decisions: list[SafetyDecision],
        context: SafetyContext,
        risk_report: RiskReport,
    ) -> SafetyDecision:
        """选择最严格的决策。

        优先级: ROLLBACK > BLOCK > REQUIRE_REVIEW > MODIFY > ALLOW
        """
        if not decisions:
            return SafetyDecision(
                product_id=context.product_id,
                action=self.default_action,
                risk_level=risk_report.risk_level,
                score=risk_report.total_score,
                reasons=["No safety policies triggered"],
                risk_report=risk_report,
                context_snapshot=context.to_dict(),
            )

        # 按优先级排序，取最严格的
        decisions.sort(
            key=lambda d: get_safety_action_priority(d.action),
            reverse=True,
        )
        return decisions[0]

    def _trigger_rollback(
        self,
        context: SafetyContext,
        decision: SafetyDecision,
    ) -> None:
        """触发回滚操作。"""
        constraints = decision.constraints

        rollback_type = constraints.get("rollback_type", "budget")

        if rollback_type == "population":
            # 种群回滚 → 回滚预算到安全水平
            self.rollback_manager.rollback_budget(
                product_id=context.product_id,
                reason=f"Population collapse: diversity {context.population_diversity:.2f}",
            )

    def is_safe(self, context: SafetyContext) -> bool:
        """快速判断操作是否安全。

        Returns:
            True 如果评估为 ALLOW
        """
        decision = self.evaluate(context)
        return decision.is_allowed

    def is_blocked(self, context: SafetyContext) -> bool:
        """快速判断操作是否被阻止。

        Returns:
            True 如果评估为 BLOCK 或 ROLLBACK
        """
        decision = self.evaluate(context)
        return decision.is_blocked

    def get_risk_report(self, context: SafetyContext) -> RiskReport:
        """获取风险评估报告（不执行策略）。

        Returns:
            RiskReport
        """
        return self.risk_detector.evaluate(context)

    def get_rollback_history(
        self,
        product_id: str | None = None,
        limit: int = 50,
    ) -> list[RollbackRecord]:
        """获取回滚历史记录。"""
        return self.rollback_manager.get_history(product_id=product_id, limit=limit)

    def get_summary(self, context: SafetyContext) -> dict[str, Any]:
        """生成评估摘要。"""
        decision = self.evaluate(context)
        risk_report = decision.risk_report

        return {
            "product_id": context.product_id,
            "action": context.action,
            "safety_action": decision.action.value,
            "safety_action_label": decision.action_label,
            "risk_level": decision.risk_level.value,
            "risk_score": decision.score,
            "is_allowed": decision.is_allowed,
            "is_blocked": decision.is_blocked,
            "needs_review": decision.needs_review,
            "reasons": decision.reasons,
            "constraints": decision.constraints if decision.is_modified else {},
            "risk_breakdown": (
                {
                    "mutation_risk": risk_report.mutation_risk,
                    "spend_risk": risk_report.spend_risk,
                    "prediction_risk": risk_report.prediction_risk,
                    "knowledge_risk": risk_report.knowledge_risk,
                }
                if risk_report
                else {}
            ),
        }

    def __repr__(self) -> str:
        return (
            f"SafetyGovernor(policies={len(self.policies)}, "
            f"detector={self.risk_detector!r})"
        )