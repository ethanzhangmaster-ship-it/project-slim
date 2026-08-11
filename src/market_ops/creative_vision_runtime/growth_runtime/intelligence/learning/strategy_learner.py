"""E15.3.5 Strategy Learner — 策略学习器.

从学习到的模式中生成策略推荐。

流程:
  Patterns → 策略归纳 → 策略推荐 → 反馈给 Planner/Selector

用法:
    learner = StrategyLearner()
    recommendations = learner.learn(patterns, experiences)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    InsightType,
    LearnedPattern,
    LearningExperience,
    LearningInsight,
    PatternStatus,
    StrategyRecommendation,
)


# ═══════════════════════════════════════════════════════════════
# Strategy Learner
# ═══════════════════════════════════════════════════════════════


class StrategyLearner:
    """E15.3.5 策略学习器 — 从模式中学习策略.

    用法:
        learner = StrategyLearner()
        recommendations = learner.learn(patterns, experiences)
    """

    def __init__(self, min_confidence: float = 0.60):
        self._min_confidence = min_confidence
        self._recommendations: list[StrategyRecommendation] = []
        self._learn_count: int = 0

    @property
    def learn_count(self) -> int:
        return self._learn_count

    # ── Learn ───────────────────────────────────────────────────

    def learn(
        self,
        patterns: list[LearnedPattern],
        experiences: list[LearningExperience] | None = None,
    ) -> list[StrategyRecommendation]:
        """从模式中学习策略.

        Args:
            patterns:     学习到的模式
            experiences:  原始经验 (可选)

        Returns:
            list[StrategyRecommendation]
        """
        self._learn_count += 1
        recommendations: list[StrategyRecommendation] = []

        # 1. 从活跃模式生成策略
        for pattern in patterns:
            if pattern.status == PatternStatus.ACTIVE:
                rec = self._pattern_to_strategy(pattern)
                if rec and rec.confidence >= self._min_confidence:
                    recommendations.append(rec)

        # 2. 从经验中直接学习 (如果无模式)
        if not patterns and experiences:
            recommendations.extend(self._learn_from_experiences(experiences))

        # 3. 生成通用策略
        recommendations.extend(self._generate_generic_strategies(patterns, experiences))

        self._recommendations.extend(recommendations)
        return recommendations

    def _pattern_to_strategy(
        self, pattern: LearnedPattern
    ) -> StrategyRecommendation | None:
        """将模式转换为策略."""
        if pattern.success_rate < 0.5:
            return None

        strategy_name = self._derive_strategy_name(pattern)
        action = pattern.recommendation.split("'")[1] if "'" in pattern.recommendation else pattern.name

        return StrategyRecommendation(
            strategy_name=strategy_name,
            description=f"Based on pattern '{pattern.name}': {pattern.recommendation}",
            confidence=pattern.confidence,
            expected_reward=pattern.success_rate * 0.5,
            source_patterns=[pattern.pattern_id],
            conditions=pattern.conditions,
            action=action,
            priority=1 if pattern.success_rate >= 0.80 else 2,
        )

    def _derive_strategy_name(self, pattern: LearnedPattern) -> str:
        """推导策略名称."""
        # 从模式名派生
        if "refresh" in pattern.name.lower():
            return "creative_refresh_strategy"
        elif "budget" in pattern.name.lower():
            return "budget_optimization_strategy"
        elif "scale" in pattern.name.lower():
            return "scale_winning_strategy"
        elif "pause" in pattern.name.lower():
            return "pause_underperforming_strategy"
        return f"derived_{pattern.name}"

    def _learn_from_experiences(
        self, experiences: list[LearningExperience]
    ) -> list[StrategyRecommendation]:
        """直接从经验中学习策略."""
        if len(experiences) < 10:
            return []

        recommendations = []

        # 按动作分组
        action_groups: dict[str, list[LearningExperience]] = {}
        for e in experiences:
            action_groups.setdefault(e.action, []).append(e)

        for action, group in action_groups.items():
            if len(group) < 5:
                continue
            success_rate = sum(1 for e in group if e.reward > 0) / len(group)
            if success_rate >= 0.6:
                recommendations.append(StrategyRecommendation(
                    strategy_name=f"strategy_{action}",
                    description=f"Action '{action}' shows {success_rate:.0%} success rate across {len(group)} executions",
                    confidence=success_rate,
                    expected_reward=success_rate * 0.4,
                    conditions={},
                    action=action,
                    priority=2,
                ))

        return recommendations

    def _generate_generic_strategies(
        self,
        patterns: list[LearnedPattern],
        experiences: list[LearningExperience] | None,
    ) -> list[StrategyRecommendation]:
        """生成通用策略."""
        strategies = []

        all_experiences = experiences or []
        if not patterns and not all_experiences:
            return strategies

        # 如果有足够多的经验且无模式，建议探索
        if len(all_experiences) >= 50 and not patterns:
            strategies.append(StrategyRecommendation(
                strategy_name="exploration_phase",
                description="Sufficient experience data collected but no patterns found. Consider exploring new strategies.",
                confidence=0.55,
                expected_reward=0.1,
                conditions={},
                action="explore",
                priority=3,
            ))

        return strategies

    # ── Generate Insights ───────────────────────────────────────

    def generate_insights(
        self, recommendations: list[StrategyRecommendation]
    ) -> list[LearningInsight]:
        """从策略推荐中生成洞察."""
        insights = []

        for rec in recommendations:
            if rec.confidence >= 0.80:
                insights.append(LearningInsight(
                    insight_type=InsightType.STRATEGY,
                    description=f"High-confidence strategy discovered: {rec.strategy_name}",
                    confidence=rec.confidence,
                    affected_components=["planner", "action_selection"],
                    evidence=[rec.description],
                    source_patterns=rec.source_patterns,
                    recommendations=[f"Adopt strategy: {rec.strategy_name}"],
                ))

        return insights

    # ── Query ───────────────────────────────────────────────────

    def get_recommendations(self) -> list[StrategyRecommendation]:
        return list(self._recommendations)

    def get_top_recommendations(self, n: int = 5) -> list[StrategyRecommendation]:
        sorted_recs = sorted(
            self._recommendations,
            key=lambda r: (r.confidence, r.expected_reward),
            reverse=True,
        )
        return sorted_recs[:n]

    def get_summary(self) -> dict[str, Any]:
        return {
            "learn_count": self._learn_count,
            "total_recommendations": len(self._recommendations),
            "high_confidence": len([r for r in self._recommendations if r.confidence >= 0.80]),
            "recommendations": [r.to_dict() for r in self._recommendations[-10:]],
        }

    def reset(self) -> None:
        self._recommendations.clear()
        self._learn_count = 0


__all__ = ["StrategyLearner"]