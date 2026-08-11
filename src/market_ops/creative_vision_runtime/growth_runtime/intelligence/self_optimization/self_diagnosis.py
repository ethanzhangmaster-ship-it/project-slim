"""E15.3.4 Self Diagnosis Engine — 自我诊断引擎.

类似 E15.2.4 Execution Reasoning，但针对系统自身运行状况。

流程:
  System Observation → Hypothesis → Diagnosis → Optimization Proposal

诊断规则:
  - Risk policy too conservative
  - Action selection weights misaligned
  - Memory retrieval threshold too high
  - Planning template mismatch

用法:
    diagnosis = SelfDiagnosisEngine()
    result = diagnosis.diagnose(metrics, strategy_perf)
    opportunities = diagnosis.generate_opportunities(result)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    MetricSeverity,
    OptimizationArea,
    OptimizationMetric,
    OptimizationOpportunity,
    StrategyPerformance,
    SystemDiagnosis,
    TrendDirection,
)


# ═══════════════════════════════════════════════════════════════
# Diagnosis Rules
# ═══════════════════════════════════════════════════════════════

# 内置诊断规则: (condition_fn, hypothesis, root_cause, recommendation)
DIAGNOSIS_RULES: list[dict[str, Any]] = [
    {
        "name": "risk_too_conservative",
        "description": "Risk engine blocks too many actions",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "risk_approval_rate") is not None
            and _get_metric(metrics, "risk_approval_rate").current_value < 0.50
            and _get_metric(metrics, "execution_success_rate") is not None
            and _get_metric(metrics, "execution_success_rate").current_value > 0.80
        ),
        "hypothesis": "Risk policy is too conservative, blocking valid actions",
        "root_cause": "risk_threshold_too_low",
        "recommendation": "Increase risk approval threshold from 0.50 to 0.55",
    },
    {
        "name": "decision_accuracy_decline",
        "description": "Decision accuracy declining over time",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "decision_accuracy") is not None
            and _get_metric(metrics, "decision_accuracy").trend == TrendDirection.DECLINING
            and _get_metric(metrics, "decision_accuracy").current_value < 0.70
        ),
        "hypothesis": "Action selection weights have drifted from optimal configuration",
        "root_cause": "action_selection_weight_drift",
        "recommendation": "Re-calibrate action selection weights: increase confidence_weight, decrease reward_weight",
    },
    {
        "name": "execution_failure_increase",
        "description": "Execution failure rate increasing",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "execution_success_rate") is not None
            and _get_metric(metrics, "execution_success_rate").trend == TrendDirection.DECLINING
            and _get_metric(metrics, "execution_success_rate").current_value < 0.75
        ),
        "hypothesis": "Execution pipeline has systemic issues or external API degradation",
        "root_cause": "execution_pipeline_degradation",
        "recommendation": "Audit execution pipeline, check external API health, adjust retry policies",
    },
    {
        "name": "memory_underutilization",
        "description": "Memory patterns not being used in decisions",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "memory_hit_rate") is not None
            and _get_metric(metrics, "memory_hit_rate").current_value < 0.40
        ),
        "hypothesis": "Memory retrieval threshold is too high, preventing pattern matching",
        "root_cause": "similarity_threshold_too_high",
        "recommendation": "Decrease similarity_threshold from 0.85 to 0.78",
    },
    {
        "name": "strategy_degradation_detected",
        "description": "One or more strategies show significant degradation",
        "condition": lambda metrics, strategies: (
            any(s.degraded for s in strategies)
        ),
        "hypothesis": "External market conditions have changed, strategies need adaptation",
        "root_cause": "strategy_degradation",
        "recommendation": "Re-evaluate degraded strategy weights and consider replacement",
    },
    {
        "name": "reward_prediction_inaccurate",
        "description": "Reward predictions consistently inaccurate",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "reward_prediction_error") is not None
            and _get_metric(metrics, "reward_prediction_error").current_value > 0.20
        ),
        "hypothesis": "Reward prediction model is miscalibrated",
        "root_cause": "reward_prediction_miscalibration",
        "recommendation": "Adjust reward_weight in action selection, increase confidence_weight",
    },
    {
        "name": "planning_inefficiency",
        "description": "Planning template match rate is low",
        "condition": lambda metrics, strategies: (
            _get_metric(metrics, "planning_match_rate") is not None
            and _get_metric(metrics, "planning_match_rate").current_value < 0.60
        ),
        "hypothesis": "Planning templates are outdated or too specific",
        "root_cause": "planning_template_mismatch",
        "recommendation": "Lower template_match_threshold or add new templates",
    },
    {
        "name": "overall_system_health_warning",
        "description": "Multiple metrics showing degradation",
        "condition": lambda metrics, strategies: (
            len([m for m in metrics if m.is_degraded()]) >= 3
        ),
        "hypothesis": "System-wide performance degradation, possible root cause in upstream data",
        "root_cause": "system_wide_degradation",
        "recommendation": "Perform comprehensive system audit, check data pipeline integrity",
    },
]


def _get_metric(metrics: list[OptimizationMetric], name: str) -> OptimizationMetric | None:
    """从指标列表中获取指定指标."""
    for m in metrics:
        if m.metric_name == name:
            return m
    return None


# ═══════════════════════════════════════════════════════════════
# Self Diagnosis Engine
# ═══════════════════════════════════════════════════════════════


class SelfDiagnosisEngine:
    """E15.3.4 自我诊断引擎 — 诊断系统自身问题.

    流程:
      1. 收集系统指标
      2. 应用诊断规则
      3. 生成假设和根因
      4. 输出优化建议

    用法:
        engine = SelfDiagnosisEngine()
        diagnosis = engine.diagnose(metrics, strategies)
        opportunities = engine.generate_opportunities(diagnosis)
    """

    def __init__(self, rules: list[dict[str, Any]] | None = None):
        self._rules = rules or DIAGNOSIS_RULES
        self._diagnoses: list[SystemDiagnosis] = []
        self._diagnosis_count: int = 0

    @property
    def diagnosis_count(self) -> int:
        return self._diagnosis_count

    # ── Diagnose ────────────────────────────────────────────────

    def diagnose(
        self,
        metrics: list[OptimizationMetric],
        strategies: list[StrategyPerformance],
    ) -> SystemDiagnosis:
        """运行系统诊断.

        Args:
            metrics:    性能指标列表
            strategies: 策略性能列表

        Returns:
            SystemDiagnosis: 诊断结果
        """
        self._diagnosis_count += 1

        observations: list[str] = []
        hypotheses: list[dict[str, Any]] = []
        root_causes: list[str] = []
        recommendations: list[str] = []

        # 1. 收集观察
        for metric in metrics:
            if metric.is_degraded():
                observations.append(
                    f"{metric.metric_name}: {metric.current_value:.2f} (target: {metric.target_value:.2f}, "
                    f"trend: {metric.trend.value})"
                )

        for strategy in strategies:
            if strategy.degraded:
                observations.append(
                    f"Strategy '{strategy.strategy_name}' degraded: "
                    f"success_rate={strategy.success_rate:.2f}, degradation={strategy.degradation_rate:.2f}"
                )

        # 2. 应用诊断规则
        for rule in self._rules:
            try:
                if rule["condition"](metrics, strategies):
                    hypotheses.append({
                        "name": rule["name"],
                        "hypothesis": rule["hypothesis"],
                        "confidence": self._calculate_confidence(rule, metrics, strategies),
                    })
                    root_causes.append(rule["root_cause"])
                    recommendations.append(rule["recommendation"])
            except Exception:
                continue

        # 3. 计算整体严重程度
        degraded_count = len([m for m in metrics if m.is_degraded()])
        if degraded_count >= 3:
            severity = MetricSeverity.CRITICAL
        elif degraded_count >= 1:
            severity = MetricSeverity.WARNING
        else:
            severity = MetricSeverity.NORMAL

        # 4. 计算置信度
        overall_confidence = sum(h["confidence"] for h in hypotheses) / len(hypotheses) if hypotheses else 0.0

        diagnosis = SystemDiagnosis(
            observations=observations,
            hypotheses=hypotheses,
            root_causes=root_causes,
            confidence=round(overall_confidence, 4),
            recommendations=recommendations,
            severity=severity,
        )
        self._diagnoses.append(diagnosis)
        return diagnosis

    def _calculate_confidence(
        self,
        rule: dict[str, Any],
        metrics: list[OptimizationMetric],
        strategies: list[StrategyPerformance],
    ) -> float:
        """计算规则置信度."""
        base = 0.70

        # 根据相关指标严重程度调整
        if rule["name"] == "risk_too_conservative":
            m = _get_metric(metrics, "risk_approval_rate")
            if m:
                base += (1 - m.current_value) * 0.2
        elif rule["name"] == "decision_accuracy_decline":
            m = _get_metric(metrics, "decision_accuracy")
            if m:
                base += (1 - m.current_value) * 0.2
        elif rule["name"] == "memory_underutilization":
            m = _get_metric(metrics, "memory_hit_rate")
            if m:
                base += (1 - m.current_value) * 0.15
        elif rule["name"] == "strategy_degradation_detected":
            degraded = [s for s in strategies if s.degraded]
            base += min(0.25, len(degraded) * 0.08)

        return round(min(0.95, base), 4)

    # ── Generate Opportunities ──────────────────────────────────

    def generate_opportunities(
        self, diagnosis: SystemDiagnosis
    ) -> list[OptimizationOpportunity]:
        """根据诊断结果生成优化机会.

        Args:
            diagnosis: 诊断结果

        Returns:
            list[OptimizationOpportunity]
        """
        opportunities: list[OptimizationOpportunity] = []

        for i, hypothesis in enumerate(diagnosis.hypotheses):
            root_cause = diagnosis.root_causes[i] if i < len(diagnosis.root_causes) else ""
            recommendation = diagnosis.recommendations[i] if i < len(diagnosis.recommendations) else ""

            area = self._map_area(root_cause)
            opp = OptimizationOpportunity(
                area=area,
                problem=hypothesis["hypothesis"],
                evidence=diagnosis.observations[:3],
                expected_gain=self._estimate_gain(root_cause),
                confidence=hypothesis["confidence"],
                suggested_change=recommendation,
                priority=1 if diagnosis.severity == MetricSeverity.CRITICAL else 2,
            )
            opportunities.append(opp)

        return opportunities

    def _map_area(self, root_cause: str) -> OptimizationArea:
        """根因映射到优化领域."""
        area_map = {
            "risk_threshold_too_low": OptimizationArea.RISK_ENGINE,
            "action_selection_weight_drift": OptimizationArea.ACTION_SELECTION,
            "execution_pipeline_degradation": OptimizationArea.EXECUTION_SUCCESS,
            "similarity_threshold_too_high": OptimizationArea.MEMORY,
            "strategy_degradation": OptimizationArea.ACTION_SELECTION,
            "reward_prediction_miscalibration": OptimizationArea.ACTION_SELECTION,
            "planning_template_mismatch": OptimizationArea.PLANNING,
            "system_wide_degradation": OptimizationArea.DECISION_ACCURACY,
        }
        return area_map.get(root_cause, OptimizationArea.DECISION_ACCURACY)

    def _estimate_gain(self, root_cause: str) -> float:
        """估算优化收益."""
        gain_map = {
            "risk_threshold_too_low": 0.15,
            "action_selection_weight_drift": 0.12,
            "execution_pipeline_degradation": 0.20,
            "similarity_threshold_too_high": 0.10,
            "strategy_degradation": 0.08,
            "reward_prediction_miscalibration": 0.10,
            "planning_template_mismatch": 0.08,
            "system_wide_degradation": 0.25,
        }
        return gain_map.get(root_cause, 0.05)

    # ── Query ───────────────────────────────────────────────────

    def get_diagnoses(self) -> list[SystemDiagnosis]:
        return list(self._diagnoses)

    def get_latest_diagnosis(self) -> SystemDiagnosis | None:
        return self._diagnoses[-1] if self._diagnoses else None

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_diagnoses": len(self._diagnoses),
            "latest": self.get_latest_diagnosis().to_dict() if self._diagnoses else None,
        }

    def reset(self) -> None:
        self._diagnoses.clear()
        self._diagnosis_count = 0


__all__ = ["DIAGNOSIS_RULES", "SelfDiagnosisEngine"]