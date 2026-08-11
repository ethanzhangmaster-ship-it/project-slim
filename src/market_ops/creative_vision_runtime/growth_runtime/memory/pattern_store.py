"""E13.4.2 PatternStore — 模式存储与检索.

核心职责:
  存储 PatternMiner 挖掘出的 PatternMemory，提供多维查询、
  统计和决策增强能力。

功能:
  - store / store_batch: 存储模式
  - query: 多维查询
  - get_by_condition: 按条件匹配模式
  - get_best_pattern: 获取最佳匹配模式
  - get_avoid_patterns: 获取应避免模式
  - enhance_decision: 用模式记忆增强决策置信度
  - get_stats: 聚合统计

连接:
  PatternMiner → PatternStore → OpportunityEngine
"""

from __future__ import annotations

from typing import Any

from .models import (
    PatternCondition,
    PatternMemory,
    PatternMiningDimension,
    PatternQuery,
    PatternStats,
    PatternQuality,
)


class PatternStore:
    """模式存储 — 存储和检索增长模式.

    用法:
        store = PatternStore()
        store.store(pattern)
        best = store.get_best_pattern(condition)
    """

    def __init__(self, max_capacity: int = 1000):
        """初始化模式存储.

        Args:
            max_capacity: 最大存储容量
        """
        self._patterns: list[PatternMemory] = []
        self._max_capacity = max_capacity
        self._total_stored: int = 0

    # ═══════════════════════════════════════════════════════════
    # Store
    # ═══════════════════════════════════════════════════════════

    def store(self, pattern: PatternMemory) -> str:
        """存储一条模式.

        Args:
            pattern: PatternMemory 实例

        Returns:
            pattern_id: 模式ID
        """
        # 检查是否已存在相同 pattern (condition+action+dimension)
        existing = self._find_existing(pattern)
        if existing is not None:
            # 更新现有模式
            existing.performance = pattern.performance
            existing.score = pattern.score
            existing.confidence = pattern.confidence
            existing.source_experience_ids = pattern.source_experience_ids
            existing.tags = pattern.tags
            existing.updated_at = pattern.updated_at
            existing.compute_score()
            return existing.pattern_id

        self._patterns.append(pattern)
        self._total_stored += 1

        # 容量控制
        if len(self._patterns) > self._max_capacity:
            overflow = len(self._patterns) - self._max_capacity
            self._patterns = self._patterns[overflow:]

        return pattern.pattern_id

    def store_batch(self, patterns: list[PatternMemory]) -> list[str]:
        """批量存储模式."""
        return [self.store(p) for p in patterns]

    def _find_existing(self, pattern: PatternMemory) -> PatternMemory | None:
        """查找已存在的相同模式."""
        for p in self._patterns:
            if (
                p.dimension == pattern.dimension
                and p.condition.opportunity_type == pattern.condition.opportunity_type
                and p.condition.action_type == pattern.condition.action_type
                and p.action.action_type == pattern.action.action_type
            ):
                return p
        return None

    def remove(self, pattern: PatternMemory) -> bool:
        """从存储中移除指定模式.

        Args:
            pattern: 要移除的 PatternMemory

        Returns:
            bool: 是否成功移除
        """
        existing = self._find_existing(pattern)
        if existing is not None:
            self._patterns.remove(existing)
            return True
        return False

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def query(self, q: PatternQuery) -> list[PatternMemory]:
        """按条件查询模式.

        Args:
            q: PatternQuery 查询条件

        Returns:
            list[PatternMemory]: 匹配的模式列表
        """
        results = self._patterns

        # 机会类型过滤
        if q.opportunity_types:
            results = [p for p in results if p.condition.opportunity_type in q.opportunity_types]

        # 动作类型过滤
        if q.action_types:
            results = [p for p in results if p.action.action_type in q.action_types]

        # 类别过滤
        if q.categories:
            results = [p for p in results if p.condition.category in q.categories]

        # 维度过滤
        if q.dimensions:
            results = [p for p in results if p.dimension.value in q.dimensions]

        # 受众过滤
        if q.audience_segment:
            results = [p for p in results if p.condition.audience_segment == q.audience_segment]

        # DNA过滤 (子集匹配)
        if q.dna_genes:
            results = [p for p in results if self._match_dna(p.condition.dna_genes, q.dna_genes)]

        # 信号类型过滤 (任意匹配)
        if q.signal_types:
            results = [p for p in results if any(s in p.condition.signal_types for s in q.signal_types)]

        # 样本数过滤
        if q.min_samples > 0:
            results = [p for p in results if p.performance.samples >= q.min_samples]

        # 成功率过滤
        if q.min_success_rate > 0:
            results = [p for p in results if p.performance.success_rate >= q.min_success_rate]

        # 评分过滤
        if q.min_score > 0:
            results = [p for p in results if p.score >= q.min_score]

        # 可执行过滤
        if q.actionable_only:
            results = [p for p in results if p.is_actionable()]

        # 避免过滤
        if q.avoid_only:
            results = [p for p in results if p.is_avoid_pattern()]

        # 质量等级过滤
        if q.quality_levels:
            results = [p for p in results if p.performance.quality.value in q.quality_levels]

        # 标签过滤 (任意匹配)
        if q.tags:
            results = [p for p in results if any(t in p.tags for t in q.tags)]

        # 排序
        if q.sort_by == "score":
            results = sorted(results, key=lambda p: -p.score if q.sort_desc else p.score)
        elif q.sort_by == "samples":
            results = sorted(results, key=lambda p: -p.performance.samples if q.sort_desc else p.performance.samples)
        elif q.sort_by == "success_rate":
            results = sorted(results, key=lambda p: -p.performance.success_rate if q.sort_desc else p.performance.success_rate)
        elif q.sort_by == "avg_reward":
            results = sorted(results, key=lambda p: -p.performance.avg_reward if q.sort_desc else p.performance.avg_reward)

        # 数量限制
        if q.limit > 0 and len(results) > q.limit:
            results = results[:q.limit]

        return results

    @staticmethod
    def _match_dna(pattern_dna: dict[str, Any], query_dna: dict[str, Any]) -> bool:
        """检查 query_dna 是否是 pattern_dna 的子集."""
        for key, value in query_dna.items():
            if key not in pattern_dna or pattern_dna[key] != value:
                return False
        return True

    # ═══════════════════════════════════════════════════════════
    # Convenience Query Methods
    # ═══════════════════════════════════════════════════════════

    def get_by_condition(self, condition: PatternCondition, limit: int = 10) -> list[PatternMemory]:
        """按条件匹配模式 (最相关的排前面)."""
        q = PatternQuery(limit=limit, sort_by="score", sort_desc=True)

        if condition.opportunity_type:
            q.opportunity_types = [condition.opportunity_type]
        if condition.action_type:
            q.action_types = [condition.action_type]
        if condition.category:
            q.categories = [condition.category]
        if condition.audience_segment:
            q.audience_segment = condition.audience_segment
        if condition.signal_types:
            q.signal_types = condition.signal_types

        return self.query(q)

    def get_best_pattern(
        self,
        condition: PatternCondition | None = None,
        opportunity_type: str = "",
        action_type: str = "",
        actionable_only: bool = True,
    ) -> PatternMemory | None:
        """获取最佳匹配模式.

        Args:
            condition: 匹配条件
            opportunity_type: 机会类型 (快捷方式)
            action_type: 动作类型 (快捷方式)
            actionable_only: 仅返回可执行模式

        Returns:
            PatternMemory | None: 最佳模式
        """
        q = PatternQuery(
            limit=1,
            sort_by="score",
            sort_desc=True,
            actionable_only=actionable_only,
        )

        if condition is not None:
            if condition.opportunity_type:
                q.opportunity_types = [condition.opportunity_type]
            if condition.action_type:
                q.action_types = [condition.action_type]
            if condition.category:
                q.categories = [condition.category]
        if opportunity_type:
            q.opportunity_types = [opportunity_type]
        if action_type:
            q.action_types = [action_type]

        results = self.query(q)
        return results[0] if results else None

    def get_avoid_patterns(self, limit: int = 20) -> list[PatternMemory]:
        """获取应避免的模式."""
        return self.query(PatternQuery(avoid_only=True, limit=limit, sort_by="score", sort_desc=False))

    def get_by_opportunity_type(self, opportunity_type: str, limit: int = 20) -> list[PatternMemory]:
        """按机会类型获取模式."""
        return self.query(PatternQuery(
            opportunity_types=[opportunity_type],
            limit=limit,
            sort_by="score",
            sort_desc=True,
        ))

    def get_by_action_type(self, action_type: str, limit: int = 20) -> list[PatternMemory]:
        """按动作类型获取模式."""
        return self.query(PatternQuery(
            action_types=[action_type],
            limit=limit,
            sort_by="score",
            sort_desc=True,
        ))

    def get_by_dimension(self, dimension: PatternMiningDimension, limit: int = 20) -> list[PatternMemory]:
        """按挖掘维度获取模式."""
        return self.query(PatternQuery(
            dimensions=[dimension.value],
            limit=limit,
            sort_by="score",
            sort_desc=True,
        ))

    def get_top_patterns(self, n: int = 10) -> list[PatternMemory]:
        """获取最高评分模式."""
        return self.query(PatternQuery(limit=n, sort_by="score", sort_desc=True))

    def get_actionable_patterns(self, n: int = 20) -> list[PatternMemory]:
        """获取可执行模式."""
        return self.query(PatternQuery(actionable_only=True, limit=n, sort_by="score", sort_desc=True))

    def get_all(self) -> list[PatternMemory]:
        """获取所有模式."""
        return list(self._patterns)

    # ═══════════════════════════════════════════════════════════
    # Decision Enhancement
    # ═══════════════════════════════════════════════════════════

    def enhance_decision(
        self,
        opportunity_type: str = "",
        action_type: str = "",
        base_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """用模式记忆增强决策置信度.

        Args:
            opportunity_type: 机会类型
            action_type: 动作类型
            base_confidence: 基础置信度

        Returns:
            dict: {
                "enhanced_confidence": float,
                "pattern_confidence": float,
                "pattern_score": float,
                "matched_pattern": dict | None,
                "samples": int,
                "historical_success_rate": float,
                "recommendation": str,
            }
        """
        # 查询匹配模式
        pattern = self.get_best_pattern(
            opportunity_type=opportunity_type,
            action_type=action_type,
            actionable_only=True,
        )

        if pattern is None:
            return {
                "enhanced_confidence": base_confidence,
                "pattern_confidence": 0.0,
                "pattern_score": 0.0,
                "matched_pattern": None,
                "samples": 0,
                "historical_success_rate": 0.0,
                "recommendation": "no_matching_pattern",
            }

        # 使用模式置信度提升基础置信度
        pattern_confidence = pattern.confidence
        enhanced = round(
            base_confidence * 0.4 + pattern_confidence * 0.6,
            4,
        ) if base_confidence > 0 else pattern_confidence

        # 推荐级别
        if enhanced >= 0.8:
            recommendation = "strong_recommend"
        elif enhanced >= 0.6:
            recommendation = "recommend"
        elif enhanced >= 0.4:
            recommendation = "suggest"
        else:
            recommendation = "caution"

        return {
            "enhanced_confidence": enhanced,
            "pattern_confidence": pattern_confidence,
            "pattern_score": pattern.score,
            "matched_pattern": pattern.to_dict(),
            "samples": pattern.performance.samples,
            "historical_success_rate": pattern.performance.success_rate,
            "recommendation": recommendation,
        }

    def get_decision_warnings(
        self,
        opportunity_type: str = "",
        action_type: str = "",
    ) -> list[dict[str, Any]]:
        """获取决策警告 (基于模式记忆).

        Args:
            opportunity_type: 机会类型
            action_type: 动作类型

        Returns:
            list[dict]: 警告列表
        """
        warnings: list[dict[str, Any]] = []

        # 检查是否有应避免的模式
        avoid_patterns = self.get_avoid_patterns()
        for ap in avoid_patterns:
            if opportunity_type and ap.condition.opportunity_type != opportunity_type:
                continue
            if action_type and ap.action.action_type != action_type:
                continue
            warnings.append({
                "pattern_id": ap.pattern_id,
                "condition": ap.condition.to_dict(),
                "action": ap.action.to_dict(),
                "failure_rate": round(1.0 - ap.performance.success_rate, 4),
                "samples": ap.performance.samples,
                "warning": f"Avoid {ap.action.action_type} under {ap.condition.opportunity_type}: "
                           f"{ap.performance.samples} samples, "
                           f"{(1.0 - ap.performance.success_rate) * 100:.0f}% failure rate",
            })

        return warnings

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> PatternStats:
        """获取模式库统计."""
        patterns = self._patterns
        total = len(patterns)

        if total == 0:
            return PatternStats()

        # 基础统计
        actionable = [p for p in patterns if p.is_actionable()]
        avoid = [p for p in patterns if p.is_avoid_pattern()]
        avg_score = round(sum(p.score for p in patterns) / total, 4)
        avg_samples = round(sum(p.performance.samples for p in patterns) / total, 2)

        # 按维度统计
        by_dimension: dict[str, dict[str, float]] = {}
        dim_groups: dict[str, list[PatternMemory]] = {}
        for p in patterns:
            dim = p.dimension.value
            if dim not in dim_groups:
                dim_groups[dim] = []
            dim_groups[dim].append(p)
        for dim, group in dim_groups.items():
            by_dimension[dim] = {
                "count": len(group),
                "avg_score": round(sum(p.score for p in group) / len(group), 4) if group else 0,
                "avg_samples": round(sum(p.performance.samples for p in group) / len(group), 2) if group else 0,
            }

        # 按质量等级统计
        by_quality: dict[str, int] = {}
        for p in patterns:
            q = p.performance.quality.value
            by_quality[q] = by_quality.get(q, 0) + 1

        # 按类别统计
        by_category: dict[str, dict[str, float]] = {}
        cat_groups: dict[str, list[PatternMemory]] = {}
        for p in patterns:
            cat = p.condition.category or "unknown"
            if cat not in cat_groups:
                cat_groups[cat] = []
            cat_groups[cat].append(p)
        for cat, group in cat_groups.items():
            by_category[cat] = {
                "count": len(group),
                "avg_score": round(sum(p.score for p in group) / len(group), 4) if group else 0,
            }

        # Top patterns
        top = sorted(patterns, key=lambda p: -p.score)[:10]
        top_patterns = [
            {
                "pattern_id": p.pattern_id,
                "condition": p.condition.to_dict(),
                "action": p.action.action_type,
                "score": p.score,
                "samples": p.performance.samples,
                "success_rate": p.performance.success_rate,
            }
            for p in top
        ]

        # Avoid patterns
        avoid_sorted = sorted(avoid, key=lambda p: p.performance.success_rate)[:10]
        avoid_patterns = [
            {
                "pattern_id": p.pattern_id,
                "condition": p.condition.to_dict(),
                "action": p.action.action_type,
                "failure_rate": round(1.0 - p.performance.success_rate, 4),
                "samples": p.performance.samples,
            }
            for p in avoid_sorted
        ]

        return PatternStats(
            total_patterns=total,
            total_actionable=len(actionable),
            total_avoid=len(avoid),
            by_dimension=by_dimension,
            by_quality=by_quality,
            by_category=by_category,
            top_patterns=top_patterns,
            avoid_patterns=avoid_patterns,
            avg_score=avg_score,
            avg_samples=avg_samples,
        )

    # ═══════════════════════════════════════════════════════════
    # Management
    # ═══════════════════════════════════════════════════════════

    @property
    def count(self) -> int:
        return len(self._patterns)

    @property
    def total_stored(self) -> int:
        return self._total_stored

    def clear(self) -> None:
        self._patterns.clear()