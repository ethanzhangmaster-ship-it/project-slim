"""E13.4.2 PatternMiner — 增长模式挖掘器.

核心职责:
  从 ExperienceStore 中的经验数据中提取可复用的增长模式，
  支持多维度聚合挖掘和评分排序。

挖掘维度:
  - OPPORTUNITY_ACTION: 机会类型 × 动作类型
  - OPPORTUNITY_CATEGORY: 机会类型 × 类别
  - ACTION_AUDIENCE: 动作类型 × 受众
  - ACTION_DNA: 动作类型 × DNA基因
  - SIGNAL_ACTION: 信号类型 × 动作类型
  - FULL_CONTEXT: 全上下文组合

流程:
  ExperienceStore
      ↓
  _group_by_dimension()
      ↓
  _compute_pattern_performance()
      ↓
  _build_pattern()
      ↓
  _assign_quality()
      ↓
  _rank_patterns()
      ↓
  PatternMemory[]

连接:
  ExperienceStore → PatternMiner → PatternMemory → PatternStore
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .experience_store import ExperienceStore
from .models import (
    ExperienceCategory,
    GrowthExperience,
    PatternAction,
    PatternCondition,
    PatternMemory,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
)


class PatternMiner:
    """增长模式挖掘器 — 从经验中提取可复用模式.

    用法:
        store = ExperienceStore()
        miner = PatternMiner(store)
        patterns = miner.mine(dimensions=[PatternMiningDimension.OPPORTUNITY_ACTION])
    """

    # 质量等级阈值
    QUALITY_THRESHOLDS = {
        PatternQuality.STRONG: {"min_samples": 30, "min_success_rate": 0.7},
        PatternQuality.RELIABLE: {"min_samples": 10, "min_success_rate": 0.6},
        PatternQuality.EMERGING: {"min_samples": 3, "min_success_rate": 0.5},
        PatternQuality.AVOID: {"min_samples": 3, "min_failure_rate": 0.7},
    }

    def __init__(self, store: ExperienceStore):
        """初始化挖掘器.

        Args:
            store: ExperienceStore 实例
        """
        self._store = store

    # ═══════════════════════════════════════════════════════════
    # Main Mining API
    # ═══════════════════════════════════════════════════════════

    def mine(
        self,
        dimensions: list[PatternMiningDimension] | None = None,
        min_samples: int = 3,
        experiences: list[GrowthExperience] | None = None,
    ) -> list[PatternMemory]:
        """从经验中挖掘增长模式.

        Args:
            dimensions: 挖掘维度列表 (默认全部)
            min_samples: 每个模式最少样本数
            experiences: 经验列表 (默认从 store 获取全部)

        Returns:
            list[PatternMemory]: 按 score 降序排列的模式列表
        """
        if dimensions is None:
            dimensions = list(PatternMiningDimension)

        if experiences is None:
            experiences = self._store.get_all()

        if len(experiences) < min_samples:
            return []

        all_patterns: list[PatternMemory] = []

        for dimension in dimensions:
            patterns = self._mine_by_dimension(experiences, dimension, min_samples)
            all_patterns.extend(patterns)

        # 去重 (按 condition + action 唯一)
        all_patterns = self._deduplicate(all_patterns)

        # 排序
        self._rank_patterns(all_patterns)

        return all_patterns

    def mine_and_rank(
        self,
        dimensions: list[PatternMiningDimension] | None = None,
        min_samples: int = 3,
        top_n: int = 20,
    ) -> list[PatternMemory]:
        """挖掘并返回 Top-N 模式."""
        patterns = self.mine(dimensions=dimensions, min_samples=min_samples)
        return patterns[:top_n]

    def mine_actionable(
        self,
        dimensions: list[PatternMiningDimension] | None = None,
        min_samples: int = 5,
        min_success_rate: float = 0.5,
    ) -> list[PatternMemory]:
        """仅挖掘可执行模式."""
        patterns = self.mine(dimensions=dimensions, min_samples=min_samples)
        return [p for p in patterns if p.is_actionable(min_samples, min_success_rate)]

    def mine_avoid_patterns(
        self,
        min_samples: int = 3,
        failure_threshold: float = 0.7,
    ) -> list[PatternMemory]:
        """挖掘应避免的模式 (高失败率)."""
        patterns = self.mine(min_samples=min_samples)
        return [p for p in patterns if p.is_avoid_pattern(failure_threshold)]

    # ═══════════════════════════════════════════════════════════
    # Dimension Mining
    # ═══════════════════════════════════════════════════════════

    def _mine_by_dimension(
        self,
        experiences: list[GrowthExperience],
        dimension: PatternMiningDimension,
        min_samples: int,
    ) -> list[PatternMemory]:
        """按指定维度挖掘模式."""
        # Step 1: 分组
        groups = self._group_by_dimension(experiences, dimension)

        # Step 2: 为每个组构建模式
        patterns: list[PatternMemory] = []
        for key, group in groups.items():
            if len(group) < min_samples:
                continue

            pattern = self._build_pattern(group, dimension, key)
            if pattern is not None:
                patterns.append(pattern)

        return patterns

    def _group_by_dimension(
        self,
        experiences: list[GrowthExperience],
        dimension: PatternMiningDimension,
    ) -> dict[str, list[GrowthExperience]]:
        """按维度对经验分组."""
        groups: dict[str, list[GrowthExperience]] = defaultdict(list)

        for exp in experiences:
            condition = PatternCondition(
                opportunity_type=exp.context.opportunity_type,
                action_type=exp.action_type,
                category=exp.category.value,
                audience_segment=exp.context.audience_segment,
                dna_genes=exp.context.dna_genes,
                signal_types=exp.context.trigger_signals,
                product_category=exp.context.product_id,
                entity_type=exp.context.entity_type,
            )
            key = condition.dimension_key(dimension)
            if key:
                groups[key].append(exp)

        return dict(groups)

    # ═══════════════════════════════════════════════════════════
    # Pattern Building
    # ═══════════════════════════════════════════════════════════

    def _build_pattern(
        self,
        group: list[GrowthExperience],
        dimension: PatternMiningDimension,
        key: str,
    ) -> PatternMemory | None:
        """从一组经验构建一个模式."""
        if not group:
            return None

        # 代表性经验 (取第一条)
        representative = group[0]

        # 构建条件
        condition = PatternCondition(
            opportunity_type=representative.context.opportunity_type,
            action_type=representative.action_type,
            category=representative.category.value,
            audience_segment=representative.context.audience_segment,
            dna_genes=representative.context.dna_genes,
            signal_types=representative.context.trigger_signals,
            product_category=representative.context.product_id,
            entity_type=representative.context.entity_type,
        )

        # 构建动作
        action = PatternAction(
            action_type=representative.action_type,
            params_template=representative.action_params,
            expected_impact=self._summarize_impact(group),
            approval_level="auto",
        )

        # 计算表现
        performance = self._compute_performance(group)

        # 来源经验ID
        source_ids = [e.experience_id for e in group]

        # 标签
        tags = self._extract_tags(group)

        pattern = PatternMemory(
            dimension=dimension,
            condition=condition,
            action=action,
            performance=performance,
            source_experience_ids=source_ids,
            tags=tags,
        )

        # 计算评分
        pattern.compute_score()

        return pattern

    def _compute_performance(self, group: list[GrowthExperience]) -> PatternPerformance:
        """计算一组经验的表现统计."""
        n = len(group)
        successes = [e for e in group if e.is_successful()]
        success_count = len(successes)
        success_rate = round(success_count / n, 4) if n > 0 else 0.0
        avg_reward = round(sum(e.reward for e in group) / n, 4)
        avg_confidence = round(sum(e.confidence for e in group) / n, 4)

        # 平均指标变化
        avg_metrics: dict[str, float] = {}
        all_metrics = defaultdict(list)
        for e in group:
            for metric, delta in e.outcome.metrics_delta.items():
                all_metrics[metric].append(delta)
        for metric, deltas in all_metrics.items():
            if deltas:
                avg_metrics[metric] = round(sum(deltas) / len(deltas), 4)

        # 奖励标准差
        if n > 1:
            mean = avg_reward
            variance = sum((e.reward - mean) ** 2 for e in group) / (n - 1)
            std_reward = round(math.sqrt(variance), 4)
        else:
            std_reward = 0.0

        # 时间范围
        timestamps = sorted([e.timestamp for e in group])
        first_seen = timestamps[0] if timestamps else ""
        last_seen = timestamps[-1] if timestamps else ""

        # 趋势 (最近 10 条)
        recent = sorted(group, key=lambda e: e.timestamp, reverse=True)[:10]
        trend = [1.0 if e.is_successful() else 0.0 for e in recent]

        # 质量等级
        quality = self._assign_quality(n, success_rate)

        return PatternPerformance(
            samples=n,
            success_count=success_count,
            success_rate=success_rate,
            avg_reward=avg_reward,
            avg_confidence=avg_confidence,
            avg_metrics_delta=avg_metrics,
            std_reward=std_reward,
            quality=quality,
            first_seen=first_seen,
            last_seen=last_seen,
            trend=trend,
        )

    def _assign_quality(self, samples: int, success_rate: float) -> PatternQuality:
        """根据样本数和成功率分配质量等级."""
        # 先检查 AVOID
        if samples >= 3 and (1.0 - success_rate) >= 0.7:
            return PatternQuality.AVOID

        for quality, thresholds in self.QUALITY_THRESHOLDS.items():
            if quality == PatternQuality.AVOID:
                continue
            if samples >= thresholds["min_samples"] and success_rate >= thresholds["min_success_rate"]:
                return quality

        return PatternQuality.WEAK

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    def _summarize_impact(self, group: list[GrowthExperience]) -> str:
        """总结一组经验的预期影响."""
        successes = [e for e in group if e.is_successful()]
        if not successes:
            return "No significant impact observed"

        # 收集所有成功经验的 impact
        impacts = [e.outcome.actual_impact for e in successes if e.outcome.actual_impact]
        if impacts:
            # 返回最常见的 impact
            from collections import Counter
            return Counter(impacts).most_common(1)[0][0]

        # 无 impact 描述，使用指标变化
        avg_metrics = {}
        all_metrics = defaultdict(list)
        for e in successes:
            for metric, delta in e.outcome.metrics_delta.items():
                all_metrics[metric].append(delta)
        for metric, deltas in all_metrics.items():
            avg_metrics[metric] = round(sum(deltas) / len(deltas), 2)

        if avg_metrics:
            parts = [f"{k}: {v:+.2f}" for k, v in sorted(avg_metrics.items())[:3]]
            return ", ".join(parts)

        return f"Success rate: {len(successes)}/{len(group)}"

    def _extract_tags(self, group: list[GrowthExperience]) -> list[str]:
        """从一组经验中提取标签."""
        tags: set[str] = set()
        for e in group:
            for tag in e.tags:
                tags.add(tag)
        return sorted(tags)

    def _deduplicate(self, patterns: list[PatternMemory]) -> list[PatternMemory]:
        """去重: 相同 opportunity_type + action_type + audience_segment 只保留样本数最大的."""
        seen: dict[str, PatternMemory] = {}
        for p in patterns:
            audience = p.condition.audience_segment or ""
            key = f"{p.condition.opportunity_type}|{p.action.action_type}|{audience}"
            if key not in seen or p.performance.samples > seen[key].performance.samples:
                seen[key] = p
        return list(seen.values())

    def _rank_patterns(self, patterns: list[PatternMemory]) -> None:
        """按 score 降序排序."""
        patterns.sort(key=lambda p: -p.score)