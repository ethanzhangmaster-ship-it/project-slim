"""E15.3.5 Knowledge Extractor — 知识提取器.

从经验中提取知识和模式。

流程:
  Experiences → 聚类分析 → 统计归纳 → 知识输出

提取类型:
  - Pattern Discovery: 发现成功模式
  - Action Effectiveness: 动作效果统计
  - Context-Outcome Correlation: 上下文-结果关联
  - Insight Generation: 洞察生成

用法:
    extractor = KnowledgeExtractor()
    patterns = extractor.extract_patterns(experiences)
    insights = extractor.generate_insights(experiences)
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .models import (
    InsightType,
    LearnedPattern,
    LearningExperience,
    LearningInsight,
    PatternStatus,
)


# ═══════════════════════════════════════════════════════════════
# Knowledge Extractor
# ═══════════════════════════════════════════════════════════════


class KnowledgeExtractor:
    """E15.3.5 知识提取器 — 从经验中提取知识.

    用法:
        extractor = KnowledgeExtractor()
        patterns = extractor.extract_patterns(experiences)
        insights = extractor.generate_insights(experiences)
    """

    def __init__(self, min_evidence: int = 10, min_confidence: float = 0.50):
        self._min_evidence = min_evidence
        self._min_confidence = min_confidence
        self._extraction_count: int = 0
        self._patterns: list[LearnedPattern] = []
        self._insights: list[LearningInsight] = []

    @property
    def extraction_count(self) -> int:
        return self._extraction_count

    # ── Pattern Extraction ──────────────────────────────────────

    def extract_patterns(
        self, experiences: list[LearningExperience]
    ) -> list[LearnedPattern]:
        """从经验中提取模式.

        Args:
            experiences: 经验列表

        Returns:
            list[LearnedPattern]
        """
        self._extraction_count += 1

        if len(experiences) < self._min_evidence:
            return []

        patterns: list[LearnedPattern] = []

        # 1. 按动作分组
        grouped = self._group_by_action(experiences)

        # 2. 对每个动作组提取模式
        for action, group in grouped.items():
            if len(group) < self._min_evidence:
                continue

            pattern = self._extract_action_pattern(action, group)
            if pattern and pattern.confidence >= self._min_confidence:
                patterns.append(pattern)
                self._patterns.append(pattern)

        return patterns

    def _group_by_action(
        self, experiences: list[LearningExperience]
    ) -> dict[str, list[LearningExperience]]:
        """按动作分组."""
        groups: dict[str, list[LearningExperience]] = {}
        for e in experiences:
            groups.setdefault(e.action, []).append(e)
        return groups

    def _extract_action_pattern(
        self, action: str, experiences: list[LearningExperience]
    ) -> LearnedPattern | None:
        """从动作组中提取模式."""
        total = len(experiences)
        successes = sum(1 for e in experiences if e.reward > 0)
        success_rate = successes / total if total > 0 else 0.0

        if success_rate < 0.5:
            return None

        # 提取常见上下文条件
        conditions = self._extract_conditions(experiences)

        # 提取推荐动作
        recommendation = self._generate_recommendation(action, success_rate, conditions)

        # 计算置信度
        confidence = 0.5 + (success_rate - 0.5) * 0.6 + (total / 100) * 0.2
        confidence = min(0.95, confidence)

        return LearnedPattern(
            name=f"pattern_{action}",
            conditions=conditions,
            recommendation=recommendation,
            confidence=round(confidence, 4),
            success_rate=round(success_rate, 4),
            usage_count=total,
            evidence_count=total,
            status=PatternStatus.DISCOVERED,
            discovered_at=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_conditions(
        self, experiences: list[LearningExperience]
    ) -> dict[str, Any]:
        """提取常见条件."""
        conditions: dict[str, Any] = {}

        # 统计上下文字段值的频率
        field_values: dict[str, Counter] = {}
        for e in experiences:
            for key, value in e.context.items():
                if isinstance(value, (str, int, float, bool)):
                    field_values.setdefault(key, Counter())
                    field_values[key][str(value)] += 1

        # 取最常见的值
        for field, counter in field_values.items():
            if counter:
                most_common = counter.most_common(1)[0]
                if most_common[1] >= len(experiences) * 0.5:
                    conditions[field] = most_common[0]

        return conditions

    def _generate_recommendation(
        self, action: str, success_rate: float, conditions: dict[str, Any]
    ) -> str:
        """生成推荐描述."""
        if success_rate >= 0.80:
            return f"Strongly recommend '{action}' (success rate: {success_rate:.0%})"
        elif success_rate >= 0.65:
            return f"Consider '{action}' with caution (success rate: {success_rate:.0%})"
        return f"'{action}' shows moderate success (success rate: {success_rate:.0%})"

    # ── Insight Generation ──────────────────────────────────────

    def generate_insights(
        self, experiences: list[LearningExperience]
    ) -> list[LearningInsight]:
        """从经验中生成洞察.

        Args:
            experiences: 经验列表

        Returns:
            list[LearningInsight]
        """
        insights: list[LearningInsight] = []

        if len(experiences) < self._min_evidence:
            return insights

        # 1. 动作效果排名
        insights.extend(self._generate_action_rankings(experiences))

        # 2. 趋势洞察
        insights.extend(self._generate_trend_insights(experiences))

        # 3. 相关性洞察
        insights.extend(self._generate_correlation_insights(experiences))

        self._insights.extend(insights)
        return insights

    def _generate_action_rankings(
        self, experiences: list[LearningExperience]
    ) -> list[LearningInsight]:
        """生成动作效果排名."""
        grouped = self._group_by_action(experiences)
        action_stats = []

        for action, group in grouped.items():
            if len(group) < 5:
                continue
            avg_reward = sum(e.reward for e in group) / len(group)
            success_rate = sum(1 for e in group if e.reward > 0) / len(group)
            action_stats.append((action, avg_reward, success_rate, len(group)))

        if not action_stats:
            return []

        # 排序
        action_stats.sort(key=lambda x: x[1], reverse=True)

        insights = []

        # 最佳动作
        best = action_stats[0]
        insights.append(LearningInsight(
            insight_type=InsightType.PATTERN,
            description=f"Top performing action: '{best[0]}' (avg reward: {best[1]:.2f}, success: {best[2]:.0%})",
            confidence=min(0.9, 0.6 + best[2] * 0.3),
            affected_components=["action_selection", "planner"],
            evidence=[f"Based on {best[3]} executions"],
            source_patterns=[],
            recommendations=[f"Prioritize '{best[0]}' in decision making"],
        ))

        # 最差动作
        if len(action_stats) >= 2:
            worst = action_stats[-1]
            if worst[1] < 0:
                insights.append(LearningInsight(
                    insight_type=InsightType.WARNING,
                    description=f"Underperforming action: '{worst[0]}' (avg reward: {worst[1]:.2f})",
                    confidence=min(0.85, 0.6 + abs(worst[1]) * 0.2),
                    affected_components=["action_selection"],
                    evidence=[f"Based on {worst[3]} executions"],
                    source_patterns=[],
                    recommendations=[f"Re-evaluate or deprioritize '{worst[0]}'"],
                ))

        return insights

    def _generate_trend_insights(
        self, experiences: list[LearningExperience]
    ) -> list[LearningInsight]:
        """生成趋势洞察."""
        if len(experiences) < 20:
            return []

        insights = []

        # 比较近期 vs 整体
        recent = experiences[-20:]
        overall = experiences

        recent_avg = sum(e.reward for e in recent) / len(recent)
        overall_avg = sum(e.reward for e in overall) / len(overall)

        diff = recent_avg - overall_avg
        if abs(diff) >= 0.15:
            if diff > 0:
                insights.append(LearningInsight(
                    insight_type=InsightType.OPPORTUNITY,
                    description=f"Performance improving: recent avg reward {recent_avg:.2f} vs overall {overall_avg:.2f}",
                    confidence=0.75,
                    affected_components=["planner", "action_selection"],
                    evidence=[f"Recent 20 executions: {recent_avg:.2f}", f"Overall: {overall_avg:.2f}"],
                    recommendations=["Continue current strategy, consider scaling"],
                ))
            else:
                insights.append(LearningInsight(
                    insight_type=InsightType.WARNING,
                    description=f"Performance declining: recent avg reward {recent_avg:.2f} vs overall {overall_avg:.2f}",
                    confidence=0.75,
                    affected_components=["planner", "action_selection", "risk_engine"],
                    evidence=[f"Recent 20 executions: {recent_avg:.2f}", f"Overall: {overall_avg:.2f}"],
                    recommendations=["Investigate root cause, consider strategy adjustment"],
                ))

        return insights

    def _generate_correlation_insights(
        self, experiences: list[LearningExperience]
    ) -> list[LearningInsight]:
        """生成相关性洞察."""
        insights = []

        # 分析上下文因素与成功率的关系
        context_fields = set()
        for e in experiences:
            context_fields.update(e.context.keys())

        for field in context_fields:
            high_group = [e for e in experiences if e.context.get(field) is not None]
            if len(high_group) < 10:
                continue

            high_avg = sum(e.reward for e in high_group) / len(high_group)
            rest = [e for e in experiences if e.context.get(field) is None]
            if not rest:
                continue
            rest_avg = sum(e.reward for e in rest) / len(rest)

            if abs(high_avg - rest_avg) >= 0.2:
                insights.append(LearningInsight(
                    insight_type=InsightType.CORRELATION,
                    description=f"Context '{field}' correlates with {'higher' if high_avg > rest_avg else 'lower'} reward",
                    confidence=0.65,
                    affected_components=["planner", "action_selection"],
                    evidence=[f"With '{field}': avg={high_avg:.2f}", f"Without: avg={rest_avg:.2f}"],
                    recommendations=[f"Consider '{field}' as a significant decision factor"],
                ))

        return insights

    # ── Query ───────────────────────────────────────────────────

    def get_patterns(self) -> list[LearnedPattern]:
        return list(self._patterns)

    def get_insights(self) -> list[LearningInsight]:
        return list(self._insights)

    def get_summary(self) -> dict[str, Any]:
        return {
            "extraction_count": self._extraction_count,
            "patterns_count": len(self._patterns),
            "insights_count": len(self._insights),
            "patterns": [p.to_dict() for p in self._patterns[-5:]],
            "insights": [i.to_dict() for i in self._insights[-5:]],
        }

    def reset(self) -> None:
        self._extraction_count = 0
        self._patterns.clear()
        self._insights.clear()


__all__ = ["KnowledgeExtractor"]