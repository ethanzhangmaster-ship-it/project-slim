"""E13.3.6 Confidence Calculator — 置信度与风险评估.

核心职责: 为决策系统提供统一的置信度评估和风险分级。

评估维度:
  - 数据置信度: 样本量、数据质量
  - 信号置信度: ROAS/CTR 多维度一致性
  - 时间置信度: 数据新鲜度、趋势稳定性
  - 执行置信度: 审批级别、预算变化幅度

输入: GrowthInsight, CreativeFitnessVector
输出: 置信度等级、风险评分、审批建议
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from ..pipeline.models import CreativeFitnessVector
from .models import (
    DecisionConfidence,
    GrowthInsight,
    OpportunitySeverity,
)


# ═══════════════════════════════════════════════════════════════
# Confidence Calculator
# ═══════════════════════════════════════════════════════════════


class ConfidenceCalculator:
    """E13.3.6 Confidence Calculator — 统一置信度评估.

    功能:
      1. 数据置信度: 基于样本量和数据质量
      2. 信号置信度: 基于多维度一致性
      3. 时间置信度: 基于数据新鲜度
      4. 综合置信度: 加权组合
    """

    # 默认权重
    DEFAULT_WEIGHTS = {
        "data_confidence": 0.40,   # 样本量 / 数据质量
        "signal_confidence": 0.35, # 多维度一致性
        "time_confidence": 0.25,   # 数据新鲜度
    }

    # 样本量阈值
    SAMPLE_THRESHOLDS = {
        "excellent": 10000,  # 大样本 → 高置信
        "good": 5000,        # 中等样本
        "adequate": 1000,    # 基本样本
        "minimal": 500,      # 最小样本
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        sample_thresholds: dict[str, int] | None = None,
    ):
        self._weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self._sample_thresholds = {**self.SAMPLE_THRESHOLDS, **(sample_thresholds or {})}

    # ── Properties ────────────────────────────────────────────

    @property
    def weights(self) -> dict[str, float]:
        return self._weights

    @property
    def sample_thresholds(self) -> dict[str, int]:
        return self._sample_thresholds

    # ── Core Calculation ──────────────────────────────────────

    def calculate(
        self, vector: CreativeFitnessVector,
    ) -> dict[str, Any]:
        """计算综合置信度.

        Args:
            vector: 创意适应度向量

        Returns:
            dict: {
                overall_confidence: float,
                level: DecisionConfidence,
                data_confidence: float,
                signal_confidence: float,
                time_confidence: float,
                components: dict,
                recommendation: str,
            }
        """
        data_conf = self._calc_data_confidence(vector)
        signal_conf = self._calc_signal_confidence(vector)
        time_conf = self._calc_time_confidence(vector)

        w = self._weights
        overall = (
            w["data_confidence"] * data_conf
            + w["signal_confidence"] * signal_conf
            + w["time_confidence"] * time_conf
        )

        level = self._to_level(overall)

        return {
            "overall_confidence": round(overall, 4),
            "level": level,
            "data_confidence": round(data_conf, 4),
            "signal_confidence": round(signal_conf, 4),
            "time_confidence": round(time_conf, 4),
            "components": {
                "sample_size": vector.sample_size,
                "is_confident": vector.is_confident,
                "has_metrics": vector.ctr > 0 or vector.d30_roas > 0,
            },
            "recommendation": self._get_recommendation(level, overall),
        }

    def calculate_for_insight(
        self, insight: GrowthInsight,
    ) -> dict[str, Any]:
        """计算洞察的置信度.

        Args:
            insight: 增长洞察

        Returns:
            dict: 置信度评估结果
        """
        # 基于 insight 自身置信度
        base_conf = insight.confidence

        # 如果有 source_vector，结合数据置信度
        source = insight.source_vector
        data_conf = 0.5
        if source and isinstance(source, CreativeFitnessVector):
            data_conf = self._calc_data_confidence(source)

        # 综合
        overall = base_conf * 0.6 + data_conf * 0.4
        level = self._to_level(overall)

        return {
            "overall_confidence": round(overall, 4),
            "level": level,
            "insight_confidence": round(base_conf, 4),
            "data_confidence": round(data_conf, 4),
            "recommendation": self._get_recommendation(level, overall),
        }

    # ── Component Calculators ─────────────────────────────────

    def _calc_data_confidence(
        self, vector: CreativeFitnessVector,
    ) -> float:
        """计算数据置信度 — 基于样本量."""
        sample_size = vector.sample_size

        if sample_size >= self._sample_thresholds["excellent"]:
            return 1.0
        elif sample_size >= self._sample_thresholds["good"]:
            # 5000-10000: 0.8-1.0
            ratio = (sample_size - self._sample_thresholds["good"]) / (
                self._sample_thresholds["excellent"] - self._sample_thresholds["good"]
            )
            return 0.8 + 0.2 * ratio
        elif sample_size >= self._sample_thresholds["adequate"]:
            # 1000-5000: 0.4-0.8
            ratio = (sample_size - self._sample_thresholds["adequate"]) / (
                self._sample_thresholds["good"] - self._sample_thresholds["adequate"]
            )
            return 0.4 + 0.4 * ratio
        elif sample_size >= self._sample_thresholds["minimal"]:
            # 500-1000: 0.2-0.4
            ratio = (sample_size - self._sample_thresholds["minimal"]) / (
                self._sample_thresholds["adequate"] - self._sample_thresholds["minimal"]
            )
            return 0.2 + 0.2 * ratio
        else:
            # < 500: 0-0.2
            return 0.2 * (sample_size / max(1, self._sample_thresholds["minimal"]))

    def _calc_signal_confidence(
        self, vector: CreativeFitnessVector,
    ) -> float:
        """计算信号置信度 — 基于多维度一致性.

        如果 ROAS 高但 LTV 低 → 信号不一致 → 低置信度
        如果 ROAS 高且 LTV 高 → 信号一致 → 高置信度
        """
        if vector.installs == 0:
            return 0.0

        signals = 0
        total_weight = 0.0

        # ROAS 信号
        if vector.d30_roas > 0:
            signals += 1
            total_weight += min(1.0, vector.d30_roas / 3.0)

        # LTV 信号
        if vector.d30_ltv > 0:
            signals += 1
            total_weight += min(1.0, vector.d30_ltv / 15.0)

        # CTR 信号
        if vector.ctr > 0:
            signals += 1
            total_weight += min(1.0, vector.ctr / 0.05)

        # Retention 信号
        if vector.d7_retention > 0:
            signals += 1
            total_weight += min(1.0, vector.d7_retention / 0.3)

        if signals == 0:
            return 0.0

        # 一致性 = 信号权重均值 / 最大可能权重
        avg_signal = total_weight / signals
        return min(1.0, avg_signal)

    def _calc_time_confidence(
        self, vector: CreativeFitnessVector,
    ) -> float:
        """计算时间置信度 — 基于数据新鲜度.

        数据越新 → 置信度越高
        数据超过 7 天 → 置信度下降
        """
        if not vector.date:
            return 0.5

        try:
            data_date = datetime.strptime(vector.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = (now - data_date).days

            if age_days <= 1:
                return 1.0
            elif age_days <= 3:
                return 0.9
            elif age_days <= 7:
                return 0.7
            elif age_days <= 14:
                return 0.5
            elif age_days <= 30:
                return 0.3
            else:
                return 0.1
        except (ValueError, TypeError):
            return 0.5

    # ── Helpers ───────────────────────────────────────────────

    def _to_level(self, confidence: float) -> DecisionConfidence:
        """将置信度数值转换为等级."""
        if confidence >= 0.85:
            return DecisionConfidence.HIGH
        elif confidence >= 0.70:
            return DecisionConfidence.MEDIUM
        elif confidence >= 0.50:
            return DecisionConfidence.LOW
        return DecisionConfidence.SPECULATIVE

    def _get_recommendation(
        self, level: DecisionConfidence, confidence: float,
    ) -> str:
        """获取置信度建议."""
        if level == DecisionConfidence.HIGH:
            return "可自主执行，无需人工干预"
        elif level == DecisionConfidence.MEDIUM:
            return "建议执行，可选择性确认"
        elif level == DecisionConfidence.LOW:
            return "建议人工确认后执行"
        else:
            return "数据不足，建议收集更多数据后决策"


# ═══════════════════════════════════════════════════════════════
# Risk Assessor
# ═══════════════════════════════════════════════════════════════


class RiskAssessor:
    """E13.3.6 Risk Assessor — 决策风险评估.

    评估维度:
      - 预算风险: 预算变化幅度过大
      - 置信度风险: 数据置信度不足
      - 执行风险: 自动执行可能出错
      - 业务风险: 对业务指标的影响
    """

    # 风险阈值
    RISK_THRESHOLDS = {
        "budget_change_high": 0.5,    # 预算变化 > 50% → 高风险
        "budget_change_medium": 0.2,  # 预算变化 > 20% → 中风险
        "confidence_low": 0.5,        # 置信度 < 0.5 → 高风险
        "confidence_medium": 0.7,     # 置信度 < 0.7 → 中风险
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**self.RISK_THRESHOLDS, **(thresholds or {})}

    def assess_budget_risk(
        self, current_budget: float, target_budget: float,
    ) -> dict[str, Any]:
        """评估预算变化风险.

        Args:
            current_budget: 当前预算
            target_budget: 目标预算

        Returns:
            dict: {risk_level, risk_score, reason}
        """
        if current_budget == 0:
            if target_budget == 0:
                return {"risk_level": "none", "risk_score": 0.0, "reason": "无预算变化"}
            return {"risk_level": "medium", "risk_score": 0.5, "reason": "从零启动预算"}

        change_pct = abs(target_budget - current_budget) / current_budget

        if change_pct > self._thresholds["budget_change_high"]:
            return {
                "risk_level": "high",
                "risk_score": min(1.0, change_pct),
                "reason": f"预算变化 {change_pct:.0%}，超过高风险阈值 {self._thresholds['budget_change_high']:.0%}",
            }
        elif change_pct > self._thresholds["budget_change_medium"]:
            return {
                "risk_level": "medium",
                "risk_score": change_pct,
                "reason": f"预算变化 {change_pct:.0%}，超过中风险阈值 {self._thresholds['budget_change_medium']:.0%}",
            }
        else:
            return {
                "risk_level": "low",
                "risk_score": change_pct,
                "reason": f"预算变化 {change_pct:.0%}，在安全范围内",
            }

    def assess_confidence_risk(
        self, confidence: float, required_confidence: float = 0.7,
    ) -> dict[str, Any]:
        """评估置信度风险.

        Args:
            confidence: 当前置信度
            required_confidence: 要求置信度

        Returns:
            dict: {risk_level, risk_score, reason}
        """
        if confidence < self._thresholds["confidence_low"]:
            return {
                "risk_level": "high",
                "risk_score": 1.0 - confidence,
                "reason": f"置信度 {confidence:.2f} 低于高风险阈值 {self._thresholds['confidence_low']}",
            }
        elif confidence < self._thresholds["confidence_medium"]:
            return {
                "risk_level": "medium",
                "risk_score": 1.0 - confidence,
                "reason": f"置信度 {confidence:.2f} 低于中风险阈值 {self._thresholds['confidence_medium']}",
            }
        elif confidence < required_confidence:
            return {
                "risk_level": "low",
                "risk_score": 1.0 - confidence,
                "reason": f"置信度 {confidence:.2f} 低于要求 {required_confidence}",
            }
        else:
            return {
                "risk_level": "none",
                "risk_score": 0.0,
                "reason": f"置信度 {confidence:.2f} 满足要求",
            }

    def assess_action_risk(
        self, action_type: str, confidence: float,
        budget_change_ratio: float = 0.0,
    ) -> dict[str, Any]:
        """综合评估动作风险.

        Args:
            action_type: 动作类型
            confidence: 决策置信度
            budget_change_ratio: 预算变化比例

        Returns:
            dict: {risk_level, risk_score, approval_level, reason}
        """
        risk_scores = []
        reasons = []

        # 动作类型风险
        high_risk_actions = {"stop", "pause"}
        medium_risk_actions = {"scale", "increase_budget", "decrease_budget", "redistribute_budget"}
        low_risk_actions = {"mutate", "launch_experiment", "duplicate_winner"}

        if action_type in high_risk_actions:
            risk_scores.append(0.8)
            reasons.append(f"高风险动作: {action_type}")
        elif action_type in medium_risk_actions:
            risk_scores.append(0.5)
            reasons.append(f"中风险动作: {action_type}")
        elif action_type in low_risk_actions:
            risk_scores.append(0.2)
            reasons.append(f"低风险动作: {action_type}")
        else:
            risk_scores.append(0.1)

        # 置信度风险
        if confidence < self._thresholds["confidence_low"]:
            risk_scores.append(0.9)
            reasons.append(f"置信度极低: {confidence:.2f}")
        elif confidence < self._thresholds["confidence_medium"]:
            risk_scores.append(0.5)
            reasons.append(f"置信度偏低: {confidence:.2f}")

        # 预算变化风险
        if budget_change_ratio > self._thresholds["budget_change_high"]:
            risk_scores.append(0.7)
            reasons.append(f"预算变化过大: {budget_change_ratio:.0%}")
        elif budget_change_ratio > self._thresholds["budget_change_medium"]:
            risk_scores.append(0.3)
            reasons.append(f"预算变化较大: {budget_change_ratio:.0%}")

        # 综合风险评分
        risk_score = sum(risk_scores) / max(1, len(risk_scores))

        if risk_score >= 0.7:
            risk_level = "high"
            approval_level = 2
        elif risk_score >= 0.4:
            risk_level = "medium"
            approval_level = 1
        else:
            risk_level = "low"
            approval_level = 0

        return {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 4),
            "approval_level": approval_level,
            "reason": "; ".join(reasons),
            "components": {
                "action_risk": risk_scores[0] if risk_scores else 0,
                "confidence_risk": 1.0 - confidence,
                "budget_risk": budget_change_ratio,
            },
        }

    def get_risk_summary(
        self, assessments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """汇总风险评估结果."""
        if not assessments:
            return {"total": 0, "high": 0, "medium": 0, "low": 0}

        high = sum(1 for a in assessments if a["risk_level"] == "high")
        medium = sum(1 for a in assessments if a["risk_level"] == "medium")
        low = sum(1 for a in assessments if a["risk_level"] == "low")

        avg_score = sum(a["risk_score"] for a in assessments) / len(assessments)

        return {
            "total": len(assessments),
            "high": high,
            "medium": medium,
            "low": low,
            "average_risk_score": round(avg_score, 4),
            "overall_risk_level": "high" if high > 0 or avg_score >= 0.5 else "medium" if avg_score >= 0.3 else "low",
        }