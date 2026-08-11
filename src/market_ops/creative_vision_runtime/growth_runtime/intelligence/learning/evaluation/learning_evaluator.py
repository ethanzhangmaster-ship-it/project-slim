"""E13.7.6 Learning Evaluator — 学习有效性评估器.

Day 7.6.2:
  评估 Learning Layer 是否真的提升了决策质量，
  回答核心问题: "学习之后，决策质量是否提升？"

核心功能:
  - evaluate(): 基于 DecisionImpactTracker 数据评估学习有效性
  - compare_groups(): 对比基线组和增强组
  - calculate_learning_gain(): 计算学习增益
  - is_significant(): 判断统计显著性

设计原则:
  - 使用简单统计方法，不依赖 ML
  - 确定性可解释的评估逻辑
  - 最小样本量保护 (避免小样本误判)
"""

from __future__ import annotations

import math
from typing import Any

from .decision_impact_tracker import DecisionImpactTracker
from .models import (
    DecisionQualitySnapshot,
    LearningEffectiveness,
    LearningImpactMetric,
)


class LearningEvaluator:
    """学习有效性评估器 — 评估学习是否提升了决策质量.

    用法:
        evaluator = LearningEvaluator(min_samples=10)
        effectiveness = evaluator.evaluate(tracker)

        if effectiveness.is_effective:
            print(f"Learning gain: {effectiveness.learning_gain_percentage:.1f}%")
    """

    def __init__(
        self,
        min_samples: int = 10,
        significance_threshold: float = 0.05,
        min_effect_size: float = 0.02,
    ) -> None:
        """初始化评估器.

        Args:
            min_samples: 最小样本量 (不足时无法评估)
            significance_threshold: 显著性阈值 (参考 p-value)
            min_effect_size: 最小效应量 (低于此值视为无意义)
        """
        self._min_samples = min_samples
        self._significance_threshold = significance_threshold
        self._min_effect_size = min_effect_size
        self._evaluation_count: int = 0

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    # ── Public API ───────────────────────────────────────────────

    def evaluate(
        self,
        tracker: DecisionImpactTracker,
    ) -> LearningEffectiveness:
        """评估学习有效性.

        Args:
            tracker: 决策质量追踪器实例

        Returns:
            LearningEffectiveness: 学习有效性评估结果
        """
        self._evaluation_count += 1

        all_snapshots = tracker.get_history()
        enhanced = tracker.get_enhanced_snapshots()
        baseline_only = tracker.get_baseline_only_snapshots()
        completed = tracker.get_completed_snapshots()

        total = len(all_snapshots)
        enhanced_count = len(enhanced)

        if total == 0 or enhanced_count == 0:
            return LearningEffectiveness(
                total_decisions=total,
                learning_enhanced_count=enhanced_count,
                is_effective=False,
                effectiveness_score=0.0,
                recommendations=["insufficient_data: 需要更多决策数据"],
                metadata={"reason": "no_data"},
            )

        # 样本量检查
        completed_enhanced = [s for s in completed if s.learning_enhanced]
        completed_baseline = [s for s in completed if not s.learning_enhanced]

        if len(completed_enhanced) < self._min_samples:
            return LearningEffectiveness(
                total_decisions=total,
                learning_enhanced_count=enhanced_count,
                is_effective=False,
                effectiveness_score=0.0,
                recommendations=[
                    f"insufficient_samples: 学习增强样本不足 "
                    f"({len(completed_enhanced)}/{self._min_samples})"
                ],
                metadata={"reason": "insufficient_enhanced_samples"},
            )

        # 计算核心指标
        baseline_success_rate = self._calc_success_rate(completed_baseline)
        enhanced_success_rate = self._calc_success_rate(completed_enhanced)
        learning_gain = enhanced_success_rate - baseline_success_rate

        baseline_avg_conf = self._mean([s.baseline_confidence for s in all_snapshots])
        enhanced_avg_conf = self._mean([s.enhanced_confidence for s in enhanced])

        baseline_avg_score = self._mean([s.baseline_score for s in all_snapshots])
        enhanced_avg_score = self._mean([s.enhanced_score for s in enhanced])

        # 计算各维度影响力
        impact_metrics = self._calc_impact_metrics(
            all_snapshots, enhanced, completed_enhanced, completed_baseline
        )

        # 判断有效性
        is_effective = self._determine_effectiveness(
            learning_gain=learning_gain,
            enhanced_count=len(completed_enhanced),
            baseline_count=len(completed_baseline),
        )

        # 计算有效性评分
        effectiveness_score = self._calc_effectiveness_score(
            learning_gain=learning_gain,
            enhanced_count=len(completed_enhanced),
            total_completed=len(completed),
            impact_metrics=impact_metrics,
        )

        # 生成建议
        recommendations = self._generate_recommendations(
            learning_gain=learning_gain,
            is_effective=is_effective,
            impact_metrics=impact_metrics,
            enhanced_count=len(completed_enhanced),
        )

        return LearningEffectiveness(
            total_decisions=total,
            learning_enhanced_count=enhanced_count,
            baseline_success_rate=round(baseline_success_rate, 4),
            enhanced_success_rate=round(enhanced_success_rate, 4),
            learning_gain=round(learning_gain, 4),
            baseline_avg_confidence=round(baseline_avg_conf, 4),
            enhanced_avg_confidence=round(enhanced_avg_conf, 4),
            baseline_avg_score=round(baseline_avg_score, 4),
            enhanced_avg_score=round(enhanced_avg_score, 4),
            impact_metrics=impact_metrics,
            is_effective=is_effective,
            effectiveness_score=round(effectiveness_score, 4),
            recommendations=recommendations,
            metadata={
                "completed_enhanced": len(completed_enhanced),
                "completed_baseline": len(completed_baseline),
                "min_samples": self._min_samples,
            },
        )

    def compare_groups(
        self,
        baseline_group: list[DecisionQualitySnapshot],
        enhanced_group: list[DecisionQualitySnapshot],
    ) -> LearningEffectiveness:
        """直接对比两组快照.

        Args:
            baseline_group: 基线组 (无学习增强)
            enhanced_group: 增强组 (有学习增强)

        Returns:
            LearningEffectiveness: 对比结果
        """
        self._evaluation_count += 1

        total = len(baseline_group) + len(enhanced_group)
        enhanced_count = len(enhanced_group)

        if enhanced_count == 0:
            return LearningEffectiveness(
                total_decisions=total,
                learning_enhanced_count=0,
                is_effective=False,
                metadata={"reason": "no_enhanced_group"},
            )

        # 成功率
        baseline_success_rate = self._calc_success_rate(baseline_group)
        enhanced_success_rate = self._calc_success_rate(enhanced_group)
        learning_gain = enhanced_success_rate - baseline_success_rate

        # 置信度
        baseline_avg_conf = self._mean([s.baseline_confidence for s in baseline_group])
        enhanced_avg_conf = self._mean([s.enhanced_confidence for s in enhanced_group])

        # 评分
        baseline_avg_score = self._mean([s.baseline_score for s in baseline_group])
        enhanced_avg_score = self._mean([s.enhanced_score for s in enhanced_group])

        # 影响力
        impact_metrics = self._calc_impact_metrics(
            baseline_group + enhanced_group, enhanced_group,
            [s for s in enhanced_group if s.has_outcome],
            [s for s in baseline_group if s.has_outcome],
        )

        is_effective = self._determine_effectiveness(
            learning_gain=learning_gain,
            enhanced_count=len(enhanced_group),
            baseline_count=len(baseline_group),
        )

        effectiveness_score = self._calc_effectiveness_score(
            learning_gain=learning_gain,
            enhanced_count=len(enhanced_group),
            total_completed=sum(1 for s in baseline_group + enhanced_group if s.has_outcome),
            impact_metrics=impact_metrics,
        )

        recommendations = self._generate_recommendations(
            learning_gain=learning_gain,
            is_effective=is_effective,
            impact_metrics=impact_metrics,
            enhanced_count=len(enhanced_group),
        )

        return LearningEffectiveness(
            total_decisions=total,
            learning_enhanced_count=enhanced_count,
            baseline_success_rate=round(baseline_success_rate, 4),
            enhanced_success_rate=round(enhanced_success_rate, 4),
            learning_gain=round(learning_gain, 4),
            baseline_avg_confidence=round(baseline_avg_conf, 4),
            enhanced_avg_confidence=round(enhanced_avg_conf, 4),
            baseline_avg_score=round(baseline_avg_score, 4),
            enhanced_avg_score=round(enhanced_avg_score, 4),
            impact_metrics=impact_metrics,
            is_effective=is_effective,
            effectiveness_score=round(effectiveness_score, 4),
            recommendations=recommendations,
            metadata={
                "completed_enhanced": sum(1 for s in enhanced_group if s.has_outcome),
                "completed_baseline": sum(1 for s in baseline_group if s.has_outcome),
            },
        )

    def calculate_learning_gain(
        self,
        baseline_success_rate: float,
        enhanced_success_rate: float,
    ) -> float:
        """计算学习增益.

        Args:
            baseline_success_rate: 基线成功率
            enhanced_success_rate: 增强成功率

        Returns:
            学习增益 [-1, 1]
        """
        return enhanced_success_rate - baseline_success_rate

    def is_significant(
        self,
        learning_gain: float,
        sample_count: int,
    ) -> bool:
        """判断学习增益是否显著.

        Args:
            learning_gain: 学习增益
            sample_count: 样本量

        Returns:
            是否显著
        """
        if sample_count < self._min_samples:
            return False
        if abs(learning_gain) < self._min_effect_size:
            return False
        # 简单统计检验: 增益置信度 = 1 - 1/(1 + sample_count * |gain|)
        gain_confidence = 1.0 - 1.0 / (1.0 + sample_count * abs(learning_gain))
        return gain_confidence > (1.0 - self._significance_threshold)

    # ── Internal ─────────────────────────────────────────────────

    def _calc_impact_metrics(
        self,
        all_snapshots: list[DecisionQualitySnapshot],
        enhanced: list[DecisionQualitySnapshot],
        completed_enhanced: list[DecisionQualitySnapshot],
        completed_baseline: list[DecisionQualitySnapshot],
    ) -> list[LearningImpactMetric]:
        """计算各维度影响力指标."""
        metrics: list[LearningImpactMetric] = []

        # 1. 成功率影响
        baseline_sr = self._calc_success_rate(completed_baseline)
        enhanced_sr = self._calc_success_rate(completed_enhanced)
        sr_change = enhanced_sr - baseline_sr
        metrics.append(LearningImpactMetric(
            metric_name="success_rate",
            baseline_value=round(baseline_sr, 4),
            enhanced_value=round(enhanced_sr, 4),
            absolute_change=round(sr_change, 4),
            relative_change=round(
                sr_change / baseline_sr if baseline_sr > 0 else 0.0, 4
            ),
            is_improvement=sr_change > 0,
            confidence=round(self._metric_confidence(
                len(completed_enhanced), abs(sr_change)
            ), 4),
        ))

        # 2. 评分影响
        baseline_score = self._mean([s.baseline_score for s in all_snapshots])
        enhanced_score = self._mean([s.enhanced_score for s in enhanced])
        score_change = enhanced_score - baseline_score
        metrics.append(LearningImpactMetric(
            metric_name="decision_score",
            baseline_value=round(baseline_score, 4),
            enhanced_value=round(enhanced_score, 4),
            absolute_change=round(score_change, 4),
            relative_change=round(
                score_change / baseline_score if baseline_score > 0 else 0.0, 4
            ),
            is_improvement=score_change > 0,
            confidence=round(self._metric_confidence(len(enhanced), abs(score_change)), 4),
        ))

        # 3. 置信度影响
        baseline_conf = self._mean([s.baseline_confidence for s in all_snapshots])
        enhanced_conf = self._mean([s.enhanced_confidence for s in enhanced])
        conf_change = enhanced_conf - baseline_conf
        metrics.append(LearningImpactMetric(
            metric_name="decision_confidence",
            baseline_value=round(baseline_conf, 4),
            enhanced_value=round(enhanced_conf, 4),
            absolute_change=round(conf_change, 4),
            relative_change=round(
                conf_change / baseline_conf if baseline_conf > 0 else 0.0, 4
            ),
            is_improvement=conf_change > 0,
            confidence=round(self._metric_confidence(len(enhanced), abs(conf_change)), 4),
        ))

        # 4. 平均奖励影响
        baseline_reward = self._mean([s.actual_reward for s in completed_baseline])
        enhanced_reward = self._mean([s.actual_reward for s in completed_enhanced])
        reward_change = enhanced_reward - baseline_reward
        metrics.append(LearningImpactMetric(
            metric_name="avg_reward",
            baseline_value=round(baseline_reward, 4),
            enhanced_value=round(enhanced_reward, 4),
            absolute_change=round(reward_change, 4),
            relative_change=round(
                reward_change / baseline_reward if baseline_reward > 0 else 0.0, 4
            ),
            is_improvement=reward_change > 0,
            confidence=round(
                self._metric_confidence(len(completed_enhanced), abs(reward_change)), 4
            ),
        ))

        return metrics

    def _determine_effectiveness(
        self,
        learning_gain: float,
        enhanced_count: int,
        baseline_count: int,
    ) -> bool:
        """判断学习是否有效."""
        if enhanced_count < self._min_samples:
            return False
        if abs(learning_gain) < self._min_effect_size:
            return False
        return learning_gain > 0

    def _calc_effectiveness_score(
        self,
        learning_gain: float,
        enhanced_count: int,
        total_completed: int,
        impact_metrics: list[LearningImpactMetric],
    ) -> float:
        """计算有效性评分 [0, 1].

        综合: 学习增益 (40%) + 样本量信心 (30%) + 指标改善 (30%)
        """
        # 增益分量 (0-0.4)
        gain_component = min(abs(learning_gain) * 2.0, 1.0) * 0.4

        # 样本量分量 (0-0.3)
        sample_ratio = min(enhanced_count / max(self._min_samples, 1), 1.0)
        sample_component = sample_ratio * 0.3

        # 指标改善分量 (0-0.3)
        if impact_metrics:
            improved = sum(1 for m in impact_metrics if m.is_improvement)
            metric_component = (improved / len(impact_metrics)) * 0.3
        else:
            metric_component = 0.0

        return gain_component + sample_component + metric_component

    def _generate_recommendations(
        self,
        learning_gain: float,
        is_effective: bool,
        impact_metrics: list[LearningImpactMetric],
        enhanced_count: int,
    ) -> list[str]:
        """生成改进建议."""
        recommendations: list[str] = []

        if is_effective:
            recommendations.append(
                f"learning_effective: 学习增益 {learning_gain*100:.1f}%，"
                f"学习层有效提升决策质量"
            )
        else:
            if learning_gain <= 0:
                recommendations.append(
                    "learning_ineffective: 学习增益为负或零，"
                    "需检查知识提取和模式预测逻辑"
                )

        if enhanced_count < self._min_samples:
            recommendations.append(
                f"need_more_data: 当前样本 {enhanced_count}，"
                f"需要至少 {self._min_samples} 个学习增强决策"
            )

        # 检查各指标
        for metric in impact_metrics:
            if not metric.is_improvement and metric.metric_name == "success_rate":
                recommendations.append(
                    "success_rate_decline: 学习增强后成功率下降，"
                    "建议检查增强器推荐逻辑"
                )

        if not recommendations:
            recommendations.append("continue_monitoring: 继续收集数据观察趋势")

        return recommendations

    @staticmethod
    def _calc_success_rate(snapshots: list[DecisionQualitySnapshot]) -> float:
        """计算成功率."""
        if not snapshots:
            return 0.0
        completed = [s for s in snapshots if s.has_outcome]
        if not completed:
            return 0.0
        return sum(1 for s in completed if s.is_success) / len(completed)

    @staticmethod
    def _mean(values: list[float]) -> float:
        """计算平均值."""
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _metric_confidence(sample_count: int, effect_size: float) -> float:
        """计算指标置信度."""
        if sample_count == 0:
            return 0.0
        return 1.0 - 1.0 / (1.0 + sample_count * effect_size)