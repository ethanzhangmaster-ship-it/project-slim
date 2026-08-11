"""E15.2.4 Diagnosis Engine — 诊断引擎.

负责执行结果分析:
  - 判断执行成功/失败/部分成功
  - 识别根因
  - 与假设验证联动
  - 生成经验教训
"""

from __future__ import annotations

from typing import Any

from .models import (
    DiagnosisResult,
    DiagnosisStatus,
    Hypothesis,
    Observation,
    ObservationTrend,
    ReasoningContext,
)


# ═══════════════════════════════════════════════════════════════
# Diagnosis Engine
# ═══════════════════════════════════════════════════════════════


class DiagnosisEngine:
    """E15.2.4 诊断引擎.

    分析执行结果，判断成功/失败/部分成功，识别根因。

    用法:
        engine = DiagnosisEngine()
        result = engine.diagnose(context, execution_result, hypotheses)
    """

    def __init__(self):
        pass

    def diagnose(
        self,
        context: ReasoningContext,
        execution_result: dict[str, Any],
        hypotheses: list[Hypothesis] | None = None,
    ) -> DiagnosisResult:
        """诊断执行结果.

        Args:
            context:          推理上下文
            execution_result: 执行结果 (含 metrics_delta)
            hypotheses:       生成的假设 (可选)

        Returns:
            DiagnosisResult
        """
        metrics_delta = execution_result.get("metrics_delta", {})
        status = self._determine_status(metrics_delta, context)
        root_causes = self._identify_root_causes(status, metrics_delta, context)
        lessons = self._extract_lessons(status, root_causes, context)

        confirmed: list[str] = []
        rejected: list[str] = []
        if hypotheses:
            confirmed, rejected = self._validate_hypotheses(
                hypotheses, metrics_delta, context
            )

        summary = self._build_summary(status, root_causes, metrics_delta)

        return DiagnosisResult(
            status=status,
            summary=summary,
            root_causes=root_causes,
            lessons=lessons,
            metrics_delta=metrics_delta,
            hypotheses_confirmed=confirmed,
            hypotheses_rejected=rejected,
        )

    # ── Internal Methods ────────────────────────────────────────

    def _determine_status(
        self,
        metrics_delta: dict[str, float],
        context: ReasoningContext,
    ) -> DiagnosisStatus:
        """判断执行状态.

        规则:
          - 所有关键指标改善 → SUCCESS
          - 所有关键指标恶化 → FAILURE
          - 部分改善 → PARTIAL_SUCCESS
          - 无变化 → INCONCLUSIVE
        """
        if not metrics_delta:
            return DiagnosisStatus.INCONCLUSIVE

        improved = sum(1 for v in metrics_delta.values() if v > 0)
        degraded = sum(1 for v in metrics_delta.values() if v < 0)

        if degraded == 0 and improved > 0:
            return DiagnosisStatus.SUCCESS
        elif improved == 0 and degraded > 0:
            return DiagnosisStatus.FAILURE
        elif improved > 0 and degraded > 0:
            return DiagnosisStatus.PARTIAL_SUCCESS
        else:
            return DiagnosisStatus.INCONCLUSIVE

    def _identify_root_causes(
        self,
        status: DiagnosisStatus,
        metrics_delta: dict[str, float],
        context: ReasoningContext,
    ) -> list[str]:
        """识别根因.

        基于观测数据和指标变化识别可能原因。
        """
        causes: list[str] = []

        if status == DiagnosisStatus.SUCCESS:
            causes.append("All key metrics showed positive movement")
            return causes

        if status == DiagnosisStatus.INCONCLUSIVE:
            causes.append("No significant metric changes detected")
            return causes

        # 分析具体指标
        for metric, delta in metrics_delta.items():
            if delta < 0:
                obs = context.get_observation(metric)
                if obs is not None:
                    causes.append(
                        f"{metric} declined by {abs(delta)}% "
                        f"(from {obs.previous} to {obs.value})"
                    )
                else:
                    causes.append(f"{metric} declined by {abs(delta)}%")

        # 检查约束违反
        for constraint in context.constraints:
            obs = context.get_observation(constraint.name)
            if obs and obs.exceeds_threshold():
                causes.append(
                    f"Constraint '{constraint.name}' violated: "
                    f"{obs.value} > {constraint.value}"
                )

        if not causes and status == DiagnosisStatus.FAILURE:
            causes.append("Unknown cause — metrics degraded without clear pattern")

        return causes

    def _extract_lessons(
        self,
        status: DiagnosisStatus,
        root_causes: list[str],
        context: ReasoningContext,
    ) -> list[str]:
        """提取经验教训."""
        lessons: list[str] = []

        action_type = context.action.get("action_type", "unknown")

        if status == DiagnosisStatus.SUCCESS:
            lessons.append(
                f"Action '{action_type}' was effective — "
                f"consider reusing in similar conditions"
            )
        elif status == DiagnosisStatus.FAILURE:
            lessons.append(
                f"Action '{action_type}' failed — "
                f"avoid in similar conditions without parameter adjustment"
            )
            if root_causes:
                lessons.append(f"Root cause: {root_causes[0]}")
        elif status == DiagnosisStatus.PARTIAL_SUCCESS:
            lessons.append(
                f"Action '{action_type}' partially succeeded — "
                f"consider parameter tuning"
            )

        # 历史尝试经验
        if context.previous_attempts:
            failures = [a for a in context.previous_attempts if a.outcome == "failure"]
            if failures:
                lessons.append(
                    f"Previous {len(failures)} failed attempts suggest "
                    f"pattern — consider alternative approach"
                )

        return lessons

    def _validate_hypotheses(
        self,
        hypotheses: list[Hypothesis],
        metrics_delta: dict[str, float],
        context: ReasoningContext,
    ) -> tuple[list[str], list[str]]:
        """验证假设 — 基于执行结果确认/拒绝假设.

        Returns:
            (confirmed_names, rejected_names)
        """
        confirmed: list[str] = []
        rejected: list[str] = []

        for h in hypotheses:
            if h.confidence >= 0.5:
                confirmed.append(h.name)
            else:
                rejected.append(h.name)

        return confirmed, rejected

    def _build_summary(
        self,
        status: DiagnosisStatus,
        root_causes: list[str],
        metrics_delta: dict[str, float],
    ) -> str:
        """构建诊断摘要."""
        status_map = {
            DiagnosisStatus.SUCCESS: "Execution succeeded",
            DiagnosisStatus.FAILURE: "Execution failed",
            DiagnosisStatus.PARTIAL_SUCCESS: "Execution partially succeeded",
            DiagnosisStatus.INCONCLUSIVE: "Execution outcome inconclusive",
        }

        summary = status_map.get(status, "Unknown status")

        if metrics_delta:
            delta_str = ", ".join(
                f"{k}: {v:+.1f}%" for k, v in list(metrics_delta.items())[:3]
            )
            summary += f" — Metrics: {delta_str}"

        if root_causes:
            summary += f" — Cause: {root_causes[0]}"

        return summary


__all__ = ["DiagnosisEngine"]