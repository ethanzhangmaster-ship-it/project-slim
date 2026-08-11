"""E15.2.4 Explainability Layer — 人类可读解释.

将推理结果转换为人类可读的自然语言解释，连接:
  - Planner → 为什么选择这个计划
  - Risk → 风险是否可接受
  - Selection → 为什么选择这个动作
  - Reasoning → 推理链路
  - Decision → 最终决策

输出格式:
  Decision: [action]
  Why: [reasons]
  Risk: [level]
  Expected outcome: [prediction]
"""

from __future__ import annotations

from typing import Any

from .models import (
    DiagnosisStatus,
    Hypothesis,
    ReasoningContext,
    ReasoningDecision,
    ReasoningResult,
    ReasoningTrace,
)


# ═══════════════════════════════════════════════════════════════
# Execution Explainer
# ═══════════════════════════════════════════════════════════════


class ExecutionExplainer:
    """E15.2.4 执行解释器.

    将推理链转换为人类可读的解释文本。

    用法:
        explainer = ExecutionExplainer()
        text = explainer.explain(context, result)
    """

    def explain(self, context: ReasoningContext, result: ReasoningResult) -> str:
        """生成人类可读解释.

        Args:
            context: 推理上下文
            result:  推理结果

        Returns:
            str: 多段自然语言解释
        """
        lines: list[str] = []

        # 标题
        action_type = context.action.get("action_type", "unknown")
        lines.append(f"Decision: {action_type.replace('_', ' ').title()}")

        # 决策
        lines.append(f"Verdict: {result.decision.value.upper()}")
        lines.append(f"Confidence: {result.confidence:.0%}")

        # 为什么
        lines.append("")
        lines.append("Why:")
        for i, reason in enumerate(result.reasoning, 1):
            lines.append(f"  {i}. {reason}")

        # 假设
        if result.hypotheses:
            lines.append("")
            lines.append("Hypotheses:")
            for h in result.hypotheses:
                lines.append(f"  - {h.name}: {h.description}")
                lines.append(f"    Confidence: {h.confidence:.0%}")
                if h.evidence:
                    for e in h.evidence:
                        lines.append(f"    Evidence: {e}")

        # 风险
        risk = context.risk_assessment
        if risk:
            risk_level = risk.get("risk_level", "unknown")
            risk_score = risk.get("risk_score", 0)
            lines.append("")
            lines.append(f"Risk: {risk_level} (score: {risk_score:.2f})")

        # 诊断
        if result.diagnosis:
            lines.append("")
            lines.append(f"Diagnosis: {result.diagnosis.status.value}")
            if result.diagnosis.root_causes:
                lines.append(f"  Root cause: {', '.join(result.diagnosis.root_causes)}")
            if result.diagnosis.lessons:
                lines.append("  Lessons:")
                for lesson in result.diagnosis.lessons:
                    lines.append(f"    - {lesson}")

        # 下一步
        if result.next_action:
            lines.append("")
            lines.append(f"Next: {result.next_action}")

        # 追踪
        if result.trace:
            lines.append("")
            lines.append("Trace:")
            for step in result.trace.steps:
                lines.append(f"  [{step.step_type}] {step.description}")

        return "\n".join(lines)

    def explain_brief(self, context: ReasoningContext, result: ReasoningResult) -> str:
        """简短解释."""
        action_type = context.action.get("action_type", "unknown")
        decision = result.decision.value.upper()
        conf = f"{result.confidence:.0%}"
        next_action = result.next_action or "none"

        return (
            f"[{decision}] {action_type} "
            f"(confidence: {conf}) → {next_action}"
        )

    def explain_structured(self, context: ReasoningContext, result: ReasoningResult) -> dict[str, Any]:
        """结构化解释."""
        return {
            "decision": {
                "action": context.action.get("action_type", "unknown"),
                "verdict": result.decision.value,
                "confidence": result.confidence,
            },
            "why": result.reasoning,
            "hypotheses": [
                {
                    "name": h.name,
                    "description": h.description,
                    "confidence": h.confidence,
                    "evidence": h.evidence,
                }
                for h in result.hypotheses
            ],
            "risk": context.risk_assessment,
            "diagnosis": result.diagnosis.to_dict() if result.diagnosis else None,
            "next_action": result.next_action,
            "trace": {
                "steps": [
                    {"type": s.step_type, "description": s.description}
                    for s in (result.trace.steps if result.trace else [])
                ],
                "confidence": result.trace.confidence if result.trace else 0,
            },
        }


__all__ = ["ExecutionExplainer"]