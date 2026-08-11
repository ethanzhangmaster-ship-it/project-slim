"""E13.4.1 ExperienceStore — 经验存储与检索.

核心职责:
  将 GrowthExperience 持久化存储，并提供多维查询和统计能力。

存储:
  - 内存存储 (用于开发和测试)
  - 未来可扩展为 DB 持久化 (PostgreSQL, SQLite)

查询:
  - 按动作类型、机会类型、类别、实体ID、产品ID 过滤
  - 按奖励分数、置信度、时间范围过滤
  - 按标签检索
  - 聚合统计

入口:
  ExecutionBatch → store_batch() → ExperienceStore
  GrowthDecisionExecutor → store() → ExperienceStore

出口:
  ExperienceStore → query() → MemoryRetriever
  ExperienceStore → get_stats() → Dashboard
"""

from __future__ import annotations

import time
from typing import Any

from .models import (
    ExperienceCategory,
    ExperienceOutcomeLevel,
    ExperienceQuery,
    ExperienceStats,
    GrowthExperience,
)


class ExperienceStore:
    """经验存储 — 记录和检索增长经验.

    用法:
        store = ExperienceStore()
        store.store(experience)
        results = store.query(ExperienceQuery(action_types=["mutate_hook"]))
        stats = store.get_stats()
    """

    def __init__(self, max_capacity: int = 10000):
        """初始化经验存储.

        Args:
            max_capacity: 最大存储容量 (超过后移除最旧记录)
        """
        self._experiences: list[GrowthExperience] = []
        self._max_capacity = max_capacity
        self._total_stored: int = 0

    # ═══════════════════════════════════════════════════════════
    # Store
    # ═══════════════════════════════════════════════════════════

    def store(self, experience: GrowthExperience) -> str:
        """存储一条经验.

        Args:
            experience: GrowthExperience 实例

        Returns:
            experience_id: 经验ID
        """
        self._experiences.append(experience)
        self._total_stored += 1

        # 容量控制: 移除最旧记录
        if len(self._experiences) > self._max_capacity:
            overflow = len(self._experiences) - self._max_capacity
            self._experiences = self._experiences[overflow:]

        return experience.experience_id

    def store_batch(self, experiences: list[GrowthExperience]) -> list[str]:
        """批量存储经验.

        Args:
            experiences: GrowthExperience 列表

        Returns:
            list[str]: 经验ID列表
        """
        return [self.store(exp) for exp in experiences]

    # ═══════════════════════════════════════════════════════════
    # Query
    # ═══════════════════════════════════════════════════════════

    def query(self, q: ExperienceQuery) -> list[GrowthExperience]:
        """按条件查询经验.

        Args:
            q: ExperienceQuery 查询条件

        Returns:
            list[GrowthExperience]: 匹配的经验列表
        """
        results = self._experiences

        # 动作类型过滤
        if q.action_types:
            results = [e for e in results if e.action_type in q.action_types]

        # 机会类型过滤
        if q.opportunity_types:
            results = [e for e in results if e.context.opportunity_type in q.opportunity_types]

        # 类别过滤
        if q.categories:
            results = [e for e in results if e.category.value in q.categories]

        # 实体ID过滤
        if q.entity_id:
            results = [e for e in results if e.context.entity_id == q.entity_id]

        # 产品ID过滤
        if q.product_id:
            results = [e for e in results if e.context.product_id == q.product_id]

        # 日期范围过滤
        if q.date_from:
            results = [e for e in results if e.context.date >= q.date_from]
        if q.date_to:
            results = [e for e in results if e.context.date <= q.date_to]

        # 奖励过滤
        if q.min_reward > 0:
            results = [e for e in results if e.reward >= q.min_reward]

        # 置信度过滤
        if q.min_confidence > 0:
            results = [e for e in results if e.confidence >= q.min_confidence]

        # 成功/失败过滤
        if q.success_only:
            results = [e for e in results if e.is_successful()]
        if q.failure_only:
            results = [e for e in results if e.is_failure()]

        # 标签过滤 (任意匹配)
        if q.tags:
            results = [e for e in results if any(t in e.tags for t in q.tags)]

        # 排序
        if q.sort_by == "reward":
            results = sorted(results, key=lambda e: -e.reward if q.sort_desc else e.reward)
        elif q.sort_by == "timestamp":
            results = sorted(results, key=lambda e: e.timestamp, reverse=q.sort_desc)
        elif q.sort_by == "confidence":
            results = sorted(results, key=lambda e: -e.confidence if q.sort_desc else e.confidence)

        # 数量限制
        if q.limit > 0 and len(results) > q.limit:
            results = results[:q.limit]

        return results

    # ═══════════════════════════════════════════════════════════
    # Convenience Query Methods
    # ═══════════════════════════════════════════════════════════

    def get_by_action_type(self, action_type: str, limit: int = 100) -> list[GrowthExperience]:
        """按动作类型获取经验."""
        return self.query(ExperienceQuery(action_types=[action_type], limit=limit))

    def get_by_opportunity_type(self, opportunity_type: str, limit: int = 100) -> list[GrowthExperience]:
        """按机会类型获取经验."""
        return self.query(ExperienceQuery(opportunity_types=[opportunity_type], limit=limit))

    def get_by_category(self, category: ExperienceCategory, limit: int = 100) -> list[GrowthExperience]:
        """按类别获取经验."""
        return self.query(ExperienceQuery(categories=[category.value], limit=limit))

    def get_by_entity(self, entity_id: str, limit: int = 100) -> list[GrowthExperience]:
        """按实体ID获取经验."""
        return self.query(ExperienceQuery(entity_id=entity_id, limit=limit))

    def get_by_product(self, product_id: str, limit: int = 100) -> list[GrowthExperience]:
        """按产品ID获取经验."""
        return self.query(ExperienceQuery(product_id=product_id, limit=limit))

    def get_successful(self, limit: int = 100) -> list[GrowthExperience]:
        """获取成功经验."""
        return self.query(ExperienceQuery(success_only=True, limit=limit))

    def get_failures(self, limit: int = 100) -> list[GrowthExperience]:
        """获取失败经验."""
        return self.query(ExperienceQuery(failure_only=True, limit=limit))

    def get_recent(self, n: int = 10) -> list[GrowthExperience]:
        """获取最近 N 条经验."""
        return self.query(ExperienceQuery(limit=n, sort_by="timestamp", sort_desc=True))

    def get_top_rewarded(self, n: int = 10) -> list[GrowthExperience]:
        """获取奖励最高的 N 条经验."""
        return self.query(ExperienceQuery(limit=n, sort_by="reward", sort_desc=True))

    def get_all(self) -> list[GrowthExperience]:
        """获取所有经验."""
        return list(self._experiences)

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> ExperienceStats:
        """获取经验库的聚合统计.

        Returns:
            ExperienceStats: 包含多维度统计信息
        """
        exps = self._experiences
        total = len(exps)

        if total == 0:
            return ExperienceStats()

        # 基础统计
        successes = [e for e in exps if e.is_successful()]
        failures = [e for e in exps if e.is_failure()]
        total_success = len(successes)
        total_failure = len(failures)
        success_rate = round(total_success / total, 4) if total > 0 else 0.0
        avg_reward = round(sum(e.reward for e in exps) / total, 4)
        avg_confidence = round(sum(e.confidence for e in exps) / total, 4)

        # 按动作类型统计
        by_action_type: dict[str, dict[str, float]] = {}
        action_groups: dict[str, list[GrowthExperience]] = {}
        for e in exps:
            at = e.action_type
            if at not in action_groups:
                action_groups[at] = []
            action_groups[at].append(e)
        for at, group in action_groups.items():
            s = sum(1 for e in group if e.is_successful())
            by_action_type[at] = {
                "count": len(group),
                "success_count": s,
                "success_rate": round(s / len(group), 4) if group else 0.0,
                "avg_reward": round(sum(e.reward for e in group) / len(group), 4),
            }

        # 按类别统计
        by_category: dict[str, dict[str, float]] = {}
        cat_groups: dict[str, list[GrowthExperience]] = {}
        for e in exps:
            cat = e.category.value
            if cat not in cat_groups:
                cat_groups[cat] = []
            cat_groups[cat].append(e)
        for cat, group in cat_groups.items():
            s = sum(1 for e in group if e.is_successful())
            by_category[cat] = {
                "count": len(group),
                "success_count": s,
                "success_rate": round(s / len(group), 4) if group else 0.0,
                "avg_reward": round(sum(e.reward for e in group) / len(group), 4),
            }

        # 按机会类型统计
        by_opportunity_type: dict[str, dict[str, float]] = {}
        opp_groups: dict[str, list[GrowthExperience]] = {}
        for e in exps:
            ot = e.context.opportunity_type
            if ot not in opp_groups:
                opp_groups[ot] = []
            opp_groups[ot].append(e)
        for ot, group in opp_groups.items():
            s = sum(1 for e in group if e.is_successful())
            by_opportunity_type[ot] = {
                "count": len(group),
                "success_count": s,
                "success_rate": round(s / len(group), 4) if group else 0.0,
                "avg_reward": round(sum(e.reward for e in group) / len(group), 4),
            }

        # Top / Worst actions (按成功率排序，至少 3 条经验)
        ranked_actions = sorted(
            [(at, s) for at, s in by_action_type.items() if s["count"] >= 3],
            key=lambda x: -x[1]["success_rate"],
        )
        top_actions = [
            {"action_type": at, **stats} for at, stats in ranked_actions[:5]
        ]
        worst_actions = [
            {"action_type": at, **stats} for at, stats in ranked_actions[-5:]
        ]

        # 最近趋势 (最近 10 条的成功率)
        recent = sorted(exps, key=lambda e: e.timestamp, reverse=True)[:10]
        recent_trend = [1.0 if e.is_successful() else 0.0 for e in recent]

        return ExperienceStats(
            total_experiences=total,
            total_success=total_success,
            total_failure=total_failure,
            success_rate=success_rate,
            avg_reward=avg_reward,
            avg_confidence=avg_confidence,
            by_action_type=by_action_type,
            by_category=by_category,
            by_opportunity_type=by_opportunity_type,
            top_actions=top_actions,
            worst_actions=worst_actions,
            recent_trend=recent_trend,
        )

    def get_success_rate(self, action_type: str = "") -> float:
        """获取成功率 (全局或按动作类型).

        Args:
            action_type: 动作类型 (为空则全局)

        Returns:
            float: 成功率 [0, 1]
        """
        if action_type:
            exps = self.get_by_action_type(action_type)
        else:
            exps = self._experiences

        if not exps:
            return 0.0

        successes = sum(1 for e in exps if e.is_successful())
        return round(successes / len(exps), 4)

    def get_avg_reward(self, action_type: str = "") -> float:
        """获取平均奖励 (全局或按动作类型).

        Args:
            action_type: 动作类型 (为空则全局)

        Returns:
            float: 平均奖励 [0, 1]
        """
        if action_type:
            exps = self.get_by_action_type(action_type)
        else:
            exps = self._experiences

        if not exps:
            return 0.0

        return round(sum(e.reward for e in exps) / len(exps), 4)

    # ═══════════════════════════════════════════════════════════
    # Management
    # ═══════════════════════════════════════════════════════════════

    @property
    def count(self) -> int:
        """当前存储的经验数量."""
        return len(self._experiences)

    @property
    def total_stored(self) -> int:
        """累计存储的经验数量 (含已移除)."""
        return self._total_stored

    @property
    def capacity(self) -> int:
        """最大容量."""
        return self._max_capacity

    def clear(self) -> None:
        """清空所有经验."""
        self._experiences.clear()

    def size(self) -> int:
        """当前经验数量 (同 count)."""
        return len(self._experiences)