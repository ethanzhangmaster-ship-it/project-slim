"""E13.5.5 Decision Explainer — 决策解释生成.

自动生成人类可读的决策解释，包括:
  1. 机会描述 (发生了什么)
  2. 策略选择理由 (为什么选这个策略)
  3. 历史经验参考 (类似场景成功率)
  4. 风险评估 (当前风险等级)
  5. 预期改善 (预期收益)

连接:
  DecisionEngine → DecisionExplainer → Growth Memory / Experience Store
"""

from __future__ import annotations

from typing import Any

from ..intelligence_models import GrowthOpportunity, OpportunityType
from ..risk_models import RiskAssessment, RiskDecision, RiskLevel
from .models import DecisionOutput, DecisionScore, DecisionType


class DecisionExplainer:
    """决策解释器 — 将决策结果翻译为人类可读的解释.

    用法:
        explainer = DecisionExplainer()
        output = explainer.explain(decision, opportunity, risk, top_score, history)
        print(output.explanation)
    """

    # ── 配置 ──────────────────────────────────────────────────

    # 机会类型中文描述映射
    _OPPORTUNITY_DESC: dict[str, str] = {
        "creative_scale": "素材放量机会",
        "creative_refresh": "素材刷新需求",
        "creative_mutate": "素材变异机会",
        "budget_optimization": "预算优化空间",
        "budget_redistribution": "预算再分配需求",
        "audience_expansion": "受众扩展机会",
        "audience_refine": "受众精细化需求",
        "monetization_optimization": "变现优化空间",
        "campaign_restructure": "广告系列重构需求",
        "bid_optimization": "出价优化空间",
        "experiment_launch": "实验启动机会",
        "risk_mitigation": "风险缓解需求",
    }

    # 决策类型中文描述
    _DECISION_DESC: dict[str, str] = {
        "execute": "直接执行",
        "test": "小预算测试",
        "hold": "保持观察",
        "block": "禁止执行",
        "escalate": "需要人工确认",
    }

    # 风险等级中文描述
    _RISK_DESC: dict[str, str] = {
        "safe": "安全",
        "low": "低",
        "medium": "中等",
        "high": "高",
        "critical": "致命",
    }

    def explain(
        self,
        decision: DecisionOutput,
        opportunity: GrowthOpportunity | None = None,
        risk: RiskAssessment | None = None,
        top_score: DecisionScore | None = None,
        history: dict[str, Any] | None = None,
    ) -> DecisionOutput:
        """生成决策解释并填充到 DecisionOutput 中.

        Args:
            decision: 决策结果 (会被原地修改)
            opportunity: 触发机会
            risk: 风险评估
            top_score: 最优策略评分
            history: 历史经验数据 (similar_cases, success_rate)

        Returns:
            DecisionOutput: 填充了 explanation/reasons/warnings 的决策
        """
        if history is None:
            history = {}

        reasons: list[str] = []
        warnings: list[str] = []

        # 1. 机会分析
        self._add_opportunity_reasons(reasons, opportunity)

        # 2. 策略选择理由
        self._add_strategy_reasons(reasons, decision, top_score)

        # 3. 历史经验
        self._add_history_reasons(reasons, history)

        # 4. 风险评估
        self._add_risk_reasons(reasons, warnings, risk)
        self._add_decision_reasons(reasons, decision)

        # 5. 预期改善
        self._add_expected_impact(reasons, decision)

        # 组装完整解释
        decision.reasons = reasons
        decision.warnings = warnings
        decision.explanation = self._build_explanation(
            decision, opportunity, risk, top_score, history, reasons, warnings
        )

        return decision

    # ═══════════════════════════════════════════════════════════
    # 解释生成
    # ═══════════════════════════════════════════════════════════

    def _build_explanation(
        self,
        decision: DecisionOutput,
        opportunity: GrowthOpportunity | None,
        risk: RiskAssessment | None,
        top_score: DecisionScore | None,
        history: dict[str, Any],
        reasons: list[str],
        warnings: list[str],
    ) -> str:
        """构建完整解释文本."""
        lines: list[str] = []

        # 决策标题
        decision_label = self._DECISION_DESC.get(
            decision.decision_type.value, decision.decision_type.value
        )
        lines.append(f"Decision: {decision_label}")

        if decision.strategy_name:
            lines.append(f"Strategy: {decision.strategy_name}")

        # 置信度 & 风险
        lines.append(f"Confidence: {decision.confidence:.0%}")
        lines.append(f"Risk: {self._RISK_DESC.get(decision.risk_level, decision.risk_level)} ({decision.risk_score:.2f})")

        # 理由
        if reasons:
            lines.append("")
            lines.append("Reasons:")
            for i, reason in enumerate(reasons, 1):
                lines.append(f"  {i}. {reason}")

        # 备选方案
        if decision.alternatives:
            lines.append("")
            lines.append("Alternatives:")
            for alt in decision.alternatives:
                if alt.strategy_name:
                    lines.append(f"  - {alt.strategy_name} (score: {alt.final_score:.2f})")

        # 警告
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in warnings:
                lines.append(f"  ! {w}")

        # 预期影响
        if decision.expected_reward > 0:
            lines.append("")
            lines.append(f"Expected Reward: {decision.expected_reward:.2%}")

        # 审批提示
        if decision.requires_approval:
            lines.append("")
            lines.append("[ Requires Human Approval ]")

        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # 各维度解释
    # ═══════════════════════════════════════════════════════════

    def _add_opportunity_reasons(
        self,
        reasons: list[str],
        opportunity: GrowthOpportunity | None,
    ) -> None:
        """添加机会相关理由."""
        if opportunity is None:
            return

        # 机会类型描述
        opp_type = opportunity.opportunity_type
        if isinstance(opp_type, OpportunityType):
            opp_type_str = opp_type.value
        else:
            opp_type_str = str(opp_type)

        desc = self._OPPORTUNITY_DESC.get(opp_type_str, opp_type_str)
        reasons.append(f"检测到{desc}")

        # 机会原因
        if opportunity.reason:
            reasons.append(f"原因: {opportunity.reason}")

        # 置信度
        if opportunity.confidence > 0:
            reasons.append(f"机会置信度: {opportunity.confidence:.0%}")

    def _add_strategy_reasons(
        self,
        reasons: list[str],
        decision: DecisionOutput,
        top_score: DecisionScore | None,
    ) -> None:
        """添加策略选择理由."""
        if top_score is None:
            return

        if decision.strategy_name:
            reasons.append(
                f"选择策略「{decision.strategy_name}」: "
                f"综合评分 {top_score.final_score:.2f}"
            )

        if top_score.strategy_reward > 0:
            reasons.append(f"历史成功率: {top_score.strategy_reward:.0%}")

        if top_score.confidence > 0:
            reasons.append(f"策略置信度: {top_score.confidence:.0%}")

        # 备选方案
        if decision.alternatives:
            alt_names = [a.strategy_name for a in decision.alternatives[:3] if a.strategy_name]
            if alt_names:
                reasons.append(f"备选方案: {', '.join(alt_names)}")

    def _add_history_reasons(
        self,
        reasons: list[str],
        history: dict[str, Any],
    ) -> None:
        """添加历史经验理由."""
        if not history:
            return

        similar_cases = history.get("similar_cases", 0)
        success_rate = history.get("success_rate", 0.0)
        total_experiences = history.get("total_experiences", 0)

        if similar_cases > 0:
            reasons.append(f"历史相似案例: {similar_cases} 个")

        if success_rate > 0:
            reasons.append(f"历史成功率: {success_rate:.0%}")

        if total_experiences > 0:
            reasons.append(f"相关经验总数: {total_experiences}")

    def _add_risk_reasons(
        self,
        reasons: list[str],
        warnings: list[str],
        risk: RiskAssessment | None,
    ) -> None:
        """添加风险评估理由."""
        if risk is None:
            return

        risk_level_label = self._RISK_DESC.get(
            risk.risk_level.value, risk.risk_level.value
        )
        reasons.append(f"风险等级: {risk_level_label} ({risk.risk_score:.2f})")

        # 风险子维度
        if risk.failure_risk > 0:
            reasons.append(f"历史失败风险: {risk.failure_risk:.2f}")
        if risk.aggression_risk > 0:
            reasons.append(f"策略激进风险: {risk.aggression_risk:.2f}")
        if risk.uncertainty_risk > 0:
            reasons.append(f"不确定性风险: {risk.uncertainty_risk:.2f}")
        if risk.impact_risk > 0:
            reasons.append(f"影响程度风险: {risk.impact_risk:.2f}")

        # 风险原因
        for r in risk.reasons:
            reasons.append(f"风险因素: {r}")

        # 风险决策
        if risk.decision == RiskDecision.WARNING:
            warnings.append("风险控制: 警告级别 — 建议监控执行")
        elif risk.decision == RiskDecision.BLOCK:
            warnings.append("风险控制: 已阻止 — 风险过高，禁止执行")

        # 建议
        for rec in risk.recommendations:
            warnings.append(f"建议: {rec}")

        # 失败警告
        for fw in risk.failure_warnings:
            if isinstance(fw, dict):
                msg = fw.get("message", str(fw))
            else:
                msg = str(fw)
            warnings.append(f"失败历史: {msg}")

    def _add_decision_reasons(
        self,
        reasons: list[str],
        decision: DecisionOutput,
    ) -> None:
        """添加决策类型理由."""
        dt = decision.decision_type

        if dt == DecisionType.EXECUTE:
            reasons.append("决策: 高置信度 + 低风险 → 自动执行")
        elif dt == DecisionType.TEST:
            reasons.append("决策: 中等置信度 → 小预算测试验证")
        elif dt == DecisionType.HOLD:
            reasons.append("决策: 置信度不足 → 保持观察")
        elif dt == DecisionType.BLOCK:
            reasons.append("决策: 风险过高 → 禁止执行")
        elif dt == DecisionType.ESCALATE:
            reasons.append("决策: 需要人工确认")

    def _add_expected_impact(
        self,
        reasons: list[str],
        decision: DecisionOutput,
    ) -> None:
        """添加预期影响."""
        if decision.action_plan and decision.action_plan.expected_roas_impact != 0:
            impact = decision.action_plan.expected_roas_impact
            direction = "+" if impact > 0 else ""
            reasons.append(f"预期 ROAS 影响: {direction}{impact:.0%}")

        if decision.expected_reward > 0:
            reasons.append(f"预期收益: {decision.expected_reward:.2%}")

    # ═══════════════════════════════════════════════════════════
    # 快捷方法
    # ═══════════════════════════════════════════════════════════

    def explain_decision_type(self, decision_type: DecisionType) -> str:
        """解释决策类型."""
        return self._DECISION_DESC.get(decision_type.value, str(decision_type))

    def explain_opportunity_type(self, opp_type: str) -> str:
        """解释机会类型."""
        return self._OPPORTUNITY_DESC.get(opp_type, opp_type)

    def explain_risk_level(self, risk_level: str) -> str:
        """解释风险等级."""
        return self._RISK_DESC.get(risk_level, risk_level)