"""E15.2.4 Decision Trace — 决策追踪.

与 E15.0.11 Observability 对接，记录完整推理链路。

记录:
  - Planner → 选择什么计划
  - Risk → 风险评估
  - Selection → 选择理由
  - Reasoning → 推理步骤
  - Decision → 最终决策
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    Hypothesis,
    ReasoningContext,
    ReasoningStep,
    ReasoningTrace,
)


# ═══════════════════════════════════════════════════════════════
# Decision Trace Builder
# ═══════════════════════════════════════════════════════════════


class DecisionTraceBuilder:
    """E15.2.4 决策追踪构建器.

    构建完整的推理追踪链路，记录每一步推理过程。

    用法:
        builder = DecisionTraceBuilder()
        trace = builder.build(context, steps, decision, hypotheses)
    """

    def __init__(self):
        self._steps: list[ReasoningStep] = []

    def build(
        self,
        context: ReasoningContext,
        steps: list[ReasoningStep],
        decision: str,
        confidence: float,
        hypotheses: list[Hypothesis] | None = None,
    ) -> ReasoningTrace:
        """构建完整推理追踪.

        Args:
            context:    推理上下文
            steps:      推理步骤
            decision:   最终决策
            confidence: 置信度
            hypotheses: 假设列表

        Returns:
            ReasoningTrace
        """
        trace = ReasoningTrace(
            steps=steps,
            final_decision=decision,
            confidence=confidence,
            hypotheses=hypotheses or [],
        )
        return trace

    def create_observation_step(
        self, context: ReasoningContext
    ) -> ReasoningStep:
        """创建观测步骤."""
        obs_count = len(context.observations)
        metric_names = [o.metric for o in context.observations[:5]]

        return ReasoningStep(
            step_type="observation",
            description=f"Extracted {obs_count} observations: {', '.join(metric_names)}",
            confidence=1.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"observation_count": obs_count},
        )

    def create_hypothesis_step(
        self, hypotheses: list[Hypothesis]
    ) -> ReasoningStep:
        """创建假设步骤."""
        if not hypotheses:
            return ReasoningStep(
                step_type="hypothesis",
                description="No hypotheses generated",
                confidence=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        top = hypotheses[0]
        desc = (
            f"Generated {len(hypotheses)} hypotheses. "
            f"Top: '{top.name}' (confidence: {top.confidence:.2f})"
        )

        return ReasoningStep(
            step_type="hypothesis",
            description=desc,
            confidence=top.confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "hypothesis_count": len(hypotheses),
                "top_hypothesis": top.name,
            },
        )

    def create_evaluation_step(
        self,
        improved_metrics: list[str],
        degraded_metrics: list[str],
    ) -> ReasoningStep:
        """创建评估步骤."""
        confidence = 0.8
        if degraded_metrics and not improved_metrics:
            confidence = 0.2
        elif improved_metrics and degraded_metrics:
            confidence = 0.5

        parts: list[str] = []
        if improved_metrics:
            parts.append(f"Improved: {', '.join(improved_metrics)}")
        if degraded_metrics:
            parts.append(f"Degraded: {', '.join(degraded_metrics)}")

        desc = "Evidence evaluation: " + ("; ".join(parts) if parts else "no changes")

        return ReasoningStep(
            step_type="evaluation",
            description=desc,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "improved_count": len(improved_metrics),
                "degraded_count": len(degraded_metrics),
            },
        )

    def create_decision_step(
        self, decision: str, confidence: float, reasoning: list[str]
    ) -> ReasoningStep:
        """创建决策步骤."""
        return ReasoningStep(
            step_type="decision",
            description=f"Final decision: {decision} (confidence: {confidence:.2f})",
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "decision": decision,
                "reasoning_points": len(reasoning),
            },
        )

    def create_context_step(self, context: ReasoningContext) -> ReasoningStep:
        """创建上下文步骤 (Planner + Risk + Selection)."""
        parts: list[str] = []
        action_type = context.action.get("action_type", "unknown")
        parts.append(f"Action: {action_type}")

        risk_level = context.risk_assessment.get("risk_level", "unknown")
        parts.append(f"Risk: {risk_level}")

        selected_score = context.selected_action.get("score", 0)
        parts.append(f"Selection score: {selected_score}")

        return ReasoningStep(
            step_type="observation",
            description="Context loaded: " + ", ".join(parts),
            confidence=1.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={
                "action_type": action_type,
                "risk_level": risk_level,
            },
        )


__all__ = ["DecisionTraceBuilder"]