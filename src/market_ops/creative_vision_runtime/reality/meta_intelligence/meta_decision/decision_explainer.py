"""E12.6.1 — Decision Explainer。

让 AI 决策可解释 —— 生成人类可读的决策解释。

输出格式:
  Decision: <action_label>
  Reasons: <bullet list>
  Expected Impact: <description>
  Risk Assessment: <description>
  Suggested Action: <description>
"""

from __future__ import annotations

from .models import DecisionContext, MetaDecision, MetaDecisionType


class DecisionExplainer:
    """决策解释器 —— 生成可读的决策解释。

    Usage:
        >>> explainer = DecisionExplainer()
        >>> decision = engine.decide(context)
        >>> explanation = explainer.explain(decision, context)
        >>> print(explanation)
    """

    # ── Explain ────────────────────────────────────────────

    def explain(
        self,
        decision: MetaDecision,
        context: DecisionContext | None = None,
    ) -> str:
        """生成决策解释。

        Args:
            decision: MetaDecision
            context:  DecisionContext（可选）

        Returns:
            人类可读的解释文本
        """
        parts: list[str] = []

        # 标题
        parts.append(f"Decision: {decision.action_label}")
        parts.append(f"Confidence: {decision.confidence:.0%}")
        parts.append(f"Priority: {decision.priority}")
        parts.append("")

        # 理由
        parts.append("Reasons:")
        for i, reason in enumerate(decision.reasons, 1):
            parts.append(f"  {i}. {reason}")
        parts.append("")

        # 预期影响
        parts.append(self._explain_expected_impact(decision))
        parts.append("")

        # 风险评估
        parts.append(self._explain_risk(decision))
        parts.append("")

        # 建议行动
        if context:
            parts.append(self._explain_context(decision, context))
            parts.append("")

        # 建议行动
        parts.append(self._suggested_action(decision))
        parts.append("")

        return "\n".join(parts)

    def explain_short(self, decision: MetaDecision) -> str:
        """生成简短解释。

        Args:
            decision: MetaDecision

        Returns:
            简短解释
        """
        return f"[{decision.action_label}] {decision.reasons[0] if decision.reasons else 'No reason provided'} (confidence: {decision.confidence:.0%})"

    # ── Impact ─────────────────────────────────────────────

    def _explain_expected_impact(self, decision: MetaDecision) -> str:
        """解释预期影响。"""
        if decision.expected_impact <= 0 and decision.action != MetaDecisionType.WAIT:
            return "Expected Impact: Stop losses / prevent further decline"

        if decision.action == MetaDecisionType.START_EXPERIMENT:
            return f"Expected Impact: +{decision.expected_impact:.0%} performance improvement through new creative mutations"
        elif decision.action == MetaDecisionType.SCALE_WINNER:
            return f"Expected Impact: +{decision.expected_impact:.0%} ROAS improvement by scaling winning creatives"
        elif decision.action == MetaDecisionType.START_LEARNING:
            return f"Expected Impact: Restore population diversity (+{decision.expected_impact:.0%}) through new pattern learning"
        elif decision.action == MetaDecisionType.CONTINUE_EVOLUTION:
            return f"Expected Impact: Maintain healthy evolution trajectory"
        elif decision.action == MetaDecisionType.ROLLBACK:
            return f"Expected Impact: Recover {decision.expected_impact:.0%} of lost performance by reverting to stable state"
        elif decision.action == MetaDecisionType.WAIT:
            return "Expected Impact: Avoid premature decisions — wait for more data"
        else:
            return f"Expected Impact: {decision.expected_impact:.0%}"

    # ── Risk ───────────────────────────────────────────────

    def _explain_risk(self, decision: MetaDecision) -> str:
        """解释风险。"""
        if decision.is_risky:
            return (
                "Risk Assessment: HIGH — This is a disruptive action. "
                "Ensure rollback capability is available before proceeding."
            )
        elif decision.confidence < 0.60:
            return (
                "Risk Assessment: MEDIUM — Confidence is moderate. "
                "Consider collecting more data before acting."
            )
        elif decision.confidence >= 0.80:
            return (
                "Risk Assessment: LOW — High confidence decision. "
                "Safe to proceed with automated execution."
            )
        else:
            return (
                "Risk Assessment: MODERATE — Standard risk level. "
                "Proceed with normal monitoring."
            )

    # ── Context ────────────────────────────────────────────

    def _explain_context(
        self,
        decision: MetaDecision,
        context: DecisionContext,
    ) -> str:
        """解释上下文。"""
        parts = ["Context:"]
        parts.append(f"  Product: {context.product_id}")
        parts.append(f"  Recent ROAS: {context.recent_roas:.2f}")
        parts.append(f"  ROAS Trend: {context.roas_trend:+.2f}")
        parts.append(f"  Fatigue: {context.fatigue_score:.0%}")
        parts.append(f"  Population Diversity: {context.population_diversity:.0%}")
        parts.append(f"  Active Experiments: {context.active_experiments}")
        parts.append(f"  Spend (7d): ${context.spend_last_7d:,.0f}")
        return "\n".join(parts)

    # ── Suggested Action ───────────────────────────────────

    def _suggested_action(self, decision: MetaDecision) -> str:
        """生成建议行动。"""
        actions = {
            MetaDecisionType.START_EXPERIMENT: (
                "Suggested Action: Create 3-5 new creative variants with "
                "mutated DNA. Target: reduce fatigue below 0.60 within 14 days."
            ),
            MetaDecisionType.SCALE_WINNER: (
                "Suggested Action: Increase budget allocation to top-performing "
                "creatives by 30-50%. Monitor ROAS weekly."
            ),
            MetaDecisionType.STOP_EXPERIMENT: (
                "Suggested Action: Immediately pause all underperforming experiments. "
                "Review failure patterns and update knowledge base."
            ),
            MetaDecisionType.START_LEARNING: (
                "Suggested Action: Trigger Meta Learning Cycle. Mine new patterns "
                "from recent experiments. Target: restore diversity above 0.30."
            ),
            MetaDecisionType.CONTINUE_EVOLUTION: (
                "Suggested Action: Maintain current evolution trajectory. "
                "Continue regular mutation cycles with standard parameters."
            ),
            MetaDecisionType.ROLLBACK: (
                "Suggested Action: Revert to last known stable creative set. "
                "Pause all new mutations. Investigate root cause of decline."
            ),
            MetaDecisionType.WAIT: (
                "Suggested Action: Collect more data. Minimum: 50 new experiments "
                "or $5,000 additional spend before re-evaluating."
            ),
        }
        return actions.get(decision.action, "Suggested Action: Review and decide manually.")

    def __repr__(self) -> str:
        return "DecisionExplainer()"