"""E15.2.4 Execution Reasoning Engine — 核心推理引擎.

AI Operator 的 reasoning loop 核心，整合:
  - Observation Extractor:  从执行结果提取观测
  - Hypothesis Generator:   生成假设
  - Evidence Evaluator:     评估证据
  - Decision Reasoner:      生成决策推理
  - Trace Builder:          构建推理追踪

流程:
  Execution Result → Observations → Hypotheses → Evaluation → Decision → Trace
"""

from __future__ import annotations

from typing import Any

from .decision_trace import DecisionTraceBuilder
from .diagnosis import DiagnosisEngine
from .hypothesis import HypothesisEngine
from .models import (
    Hypothesis,
    Observation,
    ObservationTrend,
    ReasoningContext,
    ReasoningDecision,
    ReasoningResult,
    ReasoningStep,
    ReasoningTrace,
)


# ═══════════════════════════════════════════════════════════════
# Execution Reasoning Engine
# ═══════════════════════════════════════════════════════════════


class ExecutionReasoningEngine:
    """E15.2.4 执行推理引擎.

    整合假设生成、诊断、决策推理和追踪，形成完整的推理链路。

    用法:
        engine = ExecutionReasoningEngine()
        result = engine.reason(context, execution_result)
    """

    def __init__(
        self,
        hypothesis_engine: HypothesisEngine | None = None,
        diagnosis_engine: DiagnosisEngine | None = None,
        trace_builder: DecisionTraceBuilder | None = None,
    ):
        """初始化.

        Args:
            hypothesis_engine: 假设引擎
            diagnosis_engine:  诊断引擎
            trace_builder:     追踪构建器
        """
        self._hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self._diagnosis_engine = diagnosis_engine or DiagnosisEngine()
        self._trace_builder = trace_builder or DecisionTraceBuilder()

    def reason(
        self,
        context: ReasoningContext,
        execution_result: dict[str, Any],
    ) -> ReasoningResult:
        """执行推理.

        Args:
            context:          推理上下文
            execution_result: 执行结果

        Returns:
            ReasoningResult: 推理结论
        """
        steps: list[ReasoningStep] = []

        # 1. Context step
        steps.append(self._trace_builder.create_context_step(context))

        # 2. 提取观测 (从 execution_result 补充到 context)
        enriched_context = self._enrich_observations(context, execution_result)

        # 3. Observation step
        steps.append(self._trace_builder.create_observation_step(enriched_context))

        # 4. 生成假设
        hypotheses = self._hypothesis_engine.generate_from_context(enriched_context)
        steps.append(self._trace_builder.create_hypothesis_step(hypotheses))

        # 5. 诊断
        diagnosis = self._diagnosis_engine.diagnose(
            enriched_context, execution_result, hypotheses
        )

        # 6. 证据评估
        metrics_delta = execution_result.get("metrics_delta", {})
        improved = [k for k, v in metrics_delta.items() if v > 0]
        degraded = [k for k, v in metrics_delta.items() if v < 0]
        steps.append(
            self._trace_builder.create_evaluation_step(improved, degraded)
        )

        # 7. 决策推理
        decision, confidence, reasoning = self._make_decision(
            enriched_context, execution_result, hypotheses, diagnosis
        )
        steps.append(
            self._trace_builder.create_decision_step(
                decision.value, confidence, reasoning
            )
        )

        # 8. 构建追踪
        trace = self._trace_builder.build(
            enriched_context, steps, decision.value, confidence, hypotheses
        )

        # 9. 确定下一步动作
        next_action = self._determine_next_action(
            decision, hypotheses, enriched_context
        )

        return ReasoningResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            next_action=next_action,
            hypotheses=hypotheses,
            diagnosis=diagnosis,
            trace=trace,
        )

    # ── Observation Extraction ──────────────────────────────────

    def _enrich_observations(
        self,
        context: ReasoningContext,
        execution_result: dict[str, Any],
    ) -> ReasoningContext:
        """从执行结果补充观测数据."""
        metrics_delta = execution_result.get("metrics_delta", {})
        metrics_before = execution_result.get("metrics_before", {})
        metrics_after = execution_result.get("metrics_after", {})

        existing_metrics = {o.metric for o in context.observations}

        for metric, delta in metrics_delta.items():
            if metric in existing_metrics:
                continue

            before = metrics_before.get(metric, 0)
            after = metrics_after.get(metric, 0)

            trend = ObservationTrend.STABLE
            if delta > 0.01:
                trend = ObservationTrend.UP
            elif delta < -0.01:
                trend = ObservationTrend.DOWN

            context.observations.append(
                Observation(
                    metric=metric,
                    value=after,
                    previous=before,
                    trend=trend,
                )
            )

        return context

    # ── Decision Making ─────────────────────────────────────────

    def _make_decision(
        self,
        context: ReasoningContext,
        execution_result: dict[str, Any],
        hypotheses: list[Hypothesis],
        diagnosis: Any,
    ) -> tuple[ReasoningDecision, float, list[str]]:
        """生成决策推理.

        Returns:
            (decision, confidence, reasoning_points)
        """
        reasoning: list[str] = []
        metrics_delta = execution_result.get("metrics_delta", {})

        # 检查约束违反
        for constraint in context.constraints:
            obs = context.get_observation(constraint.name)
            if obs and obs.exceeds_threshold():
                reasoning.append(
                    f"Constraint '{constraint.name}' violated: "
                    f"{obs.value} > {constraint.value}"
                )
                return ReasoningDecision.STOP, 0.8, reasoning

        # 评估指标趋势
        roas_obs = context.get_observation("roas")
        ctr_obs = context.get_observation("ctr")
        fatigue_obs = context.get_observation("fatigue")

        improved = [k for k, v in metrics_delta.items() if v > 0]
        degraded = [k for k, v in metrics_delta.items() if v < 0]

        # 全部改善 → CONTINUE
        if improved and not degraded:
            reasoning.append("All key metrics improved")
            if roas_obs and roas_obs.trend == ObservationTrend.UP:
                reasoning.append("ROAS trend positive — scaling opportunity")
            conf = min(0.95, 0.7 + len(improved) * 0.05)
            return ReasoningDecision.CONTINUE, round(conf, 2), reasoning

        # 全部恶化 → STOP
        if degraded and not improved:
            reasoning.append("All key metrics degraded")
            if roas_obs and roas_obs.trend == ObservationTrend.DOWN:
                reasoning.append("ROAS declining — stop recommended")
            return ReasoningDecision.STOP, 0.75, reasoning

        # 部分改善 → 检查假设
        if improved and degraded:
            reasoning.append("Mixed results — some metrics improved, some degraded")

            top_hypothesis = hypotheses[0] if hypotheses else None
            if top_hypothesis and top_hypothesis.confidence > 0.5:
                reasoning.append(
                    f"Hypothesis '{top_hypothesis.name}' suggests "
                    f"{top_hypothesis.suggested_action or 'monitor'}"
                )
                if top_hypothesis.suggested_action == "replace_creative":
                    return ReasoningDecision.MODIFY, 0.70, reasoning
                if top_hypothesis.suggested_action == "monitor":
                    return ReasoningDecision.MONITOR, 0.65, reasoning

            return ReasoningDecision.MONITOR, 0.60, reasoning

        # 无变化
        reasoning.append("No significant metric changes detected")
        return ReasoningDecision.MONITOR, 0.50, reasoning

    def _determine_next_action(
        self,
        decision: ReasoningDecision,
        hypotheses: list[Hypothesis],
        context: ReasoningContext,
    ) -> str | None:
        """确定下一步动作."""
        if decision == ReasoningDecision.CONTINUE:
            # 从假设中提取建议
            if hypotheses and hypotheses[0].suggested_action:
                return hypotheses[0].suggested_action
            return "continue_execution"

        if decision == ReasoningDecision.STOP:
            return "pause_and_review"

        if decision == ReasoningDecision.MODIFY:
            if hypotheses and hypotheses[0].suggested_action:
                return hypotheses[0].suggested_action
            return "modify_parameters"

        if decision == ReasoningDecision.ESCALATE:
            return "escalate_to_human"

        # MONITOR
        return "monitor_metrics"

    # ── Accessors ───────────────────────────────────────────────

    @property
    def hypothesis_engine(self) -> HypothesisEngine:
        return self._hypothesis_engine

    @property
    def diagnosis_engine(self) -> DiagnosisEngine:
        return self._diagnosis_engine


__all__ = ["ExecutionReasoningEngine"]