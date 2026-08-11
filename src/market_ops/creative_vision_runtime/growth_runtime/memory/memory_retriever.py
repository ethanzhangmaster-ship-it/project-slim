"""E13.4.1 MemoryRetriever — 记忆检索增强器.

核心职责:
  为 E13.3.2 Opportunity Engine 提供记忆增强能力，
  在决策前查询历史经验，提供数据驱动的决策建议。

功能:
  - enhance_opportunity(): 为 GrowthOpportunity 附加记忆上下文
  - get_best_action(): 根据历史经验推荐最佳动作
  - get_action_success_rate(): 获取指定动作的历史成功率
  - get_similar_experiences(): 查找相似历史经验
  - get_failure_warnings(): 获取失败模式警告

连接:
  MemoryRetriever → ExperienceStore → GrowthExperience
  OpportunityEngine → MemoryRetriever → 增强决策
"""

from __future__ import annotations

from typing import Any

from .experience_store import ExperienceStore
from .models import (
    ExperienceCategory,
    ExperienceOutcomeLevel,
    ExperienceQuery,
    ExperienceStats,
    GrowthExperience,
)


class MemoryRetriever:
    """记忆检索器 — 在决策时查询历史经验.

    用法:
        store = ExperienceStore()
        retriever = MemoryRetriever(store)
        enhanced = retriever.enhance_opportunity(opportunity)
        best_action = retriever.get_best_action("creative_scale")
    """

    def __init__(self, store: ExperienceStore):
        """初始化检索器.

        Args:
            store: ExperienceStore 实例
        """
        self._store = store

    # ═══════════════════════════════════════════════════════════
    # Core Enhancement
    # ═══════════════════════════════════════════════════════════

    def enhance_opportunity(self, opportunity: Any) -> dict[str, Any]:
        """为 GrowthOpportunity 附加记忆增强信息.

        Args:
            opportunity: GrowthOpportunity 实例

        Returns:
            dict: 包含记忆增强信息的字典
                - recommended_action_type: 推荐动作类型
                - recommended_confidence: 推荐置信度 (基于历史)
                - historical_success_rate: 历史成功率
                - similar_experiences: 相似经验数
                - failure_warnings: 失败警告
        """
        opp_type = getattr(opportunity, "opportunity_type", None)
        opp_type_str = opp_type.value if hasattr(opp_type, "value") else str(opp_type)
        entity_id = getattr(opportunity, "entity_id", "")

        # 查询相似经验
        similar = self.get_similar_experiences(opportunity_type=opp_type_str, entity_id=entity_id)

        # 推荐最佳动作
        best_action = self.get_best_action(opp_type_str)

        # 历史成功率
        action_type = best_action.get("action_type", "") if best_action else ""
        hist_success_rate = self.get_action_success_rate(action_type) if action_type else 0.0

        # 失败警告
        warnings = self.get_failure_warnings(opp_type_str)

        return {
            "recommended_action_type": best_action.get("action_type", "") if best_action else "",
            "recommended_confidence": best_action.get("success_rate", 0.0) if best_action else 0.0,
            "historical_success_rate": hist_success_rate,
            "similar_experiences_count": len(similar),
            "similar_experiences": similar,
            "failure_warnings": warnings,
        }

    # ═══════════════════════════════════════════════════════════
    # Best Action Recommendation
    # ═══════════════════════════════════════════════════════════

    def get_best_action(
        self,
        opportunity_type: str = "",
        category: str = "",
        min_samples: int = 3,
    ) -> dict[str, Any]:
        """根据历史经验推荐最佳动作类型.

        基于历史成功率最高且样本量足够的动作。

        Args:
            opportunity_type: 机会类型 (如 creative_scale)
            category: 经验类别 (如 creative)
            min_samples: 最少样本数

        Returns:
            dict: {"action_type": str, "success_rate": float, "sample_count": int, "avg_reward": float}
        """
        # 查询相关经验
        q = ExperienceQuery()
        if opportunity_type:
            q.opportunity_types = [opportunity_type]
        if category:
            q.categories = [category]

        exps = self._store.query(q)

        if not exps:
            return {}

        # 按动作类型分组统计
        action_groups: dict[str, list[GrowthExperience]] = {}
        for e in exps:
            if e.action_type not in action_groups:
                action_groups[e.action_type] = []
            action_groups[e.action_type].append(e)

        # 计算每个动作的成功率
        candidates: list[dict[str, Any]] = []
        for at, group in action_groups.items():
            if len(group) < min_samples:
                continue
            successes = sum(1 for e in group if e.is_successful())
            success_rate = round(successes / len(group), 4)
            avg_reward = round(sum(e.reward for e in group) / len(group), 4)
            candidates.append({
                "action_type": at,
                "success_rate": success_rate,
                "sample_count": len(group),
                "avg_reward": avg_reward,
            })

        if not candidates:
            return {}

        # 按成功率降序，取最高
        candidates.sort(key=lambda c: (-c["success_rate"], -c["sample_count"]))
        return candidates[0]

    # ═══════════════════════════════════════════════════════════
    # Success Rate
    # ═══════════════════════════════════════════════════════════

    def get_action_success_rate(self, action_type: str) -> float:
        """获取指定动作类型的历史成功率.

        Args:
            action_type: 动作类型

        Returns:
            float: 成功率 [0, 1]
        """
        return self._store.get_success_rate(action_type)

    def get_opportunity_success_rate(self, opportunity_type: str) -> float:
        """获取指定机会类型的历史成功率.

        Args:
            opportunity_type: 机会类型

        Returns:
            float: 成功率 [0, 1]
        """
        exps = self._store.get_by_opportunity_type(opportunity_type)
        if not exps:
            return 0.0
        successes = sum(1 for e in exps if e.is_successful())
        return round(successes / len(exps), 4)

    def get_category_success_rate(self, category: ExperienceCategory) -> float:
        """获取指定类别的历史成功率.

        Args:
            category: 经验类别

        Returns:
            float: 成功率 [0, 1]
        """
        exps = self._store.get_by_category(category)
        if not exps:
            return 0.0
        successes = sum(1 for e in exps if e.is_successful())
        return round(successes / len(exps), 4)

    # ═══════════════════════════════════════════════════════════
    # Similar Experiences
    # ═══════════════════════════════════════════════════════════

    def get_similar_experiences(
        self,
        opportunity_type: str = "",
        action_type: str = "",
        entity_id: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """查找相似历史经验.

        Args:
            opportunity_type: 机会类型
            action_type: 动作类型
            entity_id: 实体ID
            limit: 返回数量

        Returns:
            list[dict]: 相似经验摘要列表
        """
        q = ExperienceQuery(limit=limit, sort_by="reward", sort_desc=True)

        if opportunity_type:
            q.opportunity_types = [opportunity_type]
        if action_type:
            q.action_types = [action_type]
        if entity_id:
            q.entity_id = entity_id

        exps = self._store.query(q)

        return [
            {
                "experience_id": e.experience_id,
                "action_type": e.action_type,
                "opportunity_type": e.context.opportunity_type,
                "success": e.outcome.success,
                "outcome_level": e.outcome.outcome_level.value,
                "reward": e.reward,
                "actual_impact": e.outcome.actual_impact,
                "timestamp": e.timestamp,
            }
            for e in exps
        ]

    # ═══════════════════════════════════════════════════════════
    # Failure Warnings
    # ═══════════════════════════════════════════════════════════

    def get_failure_warnings(self, opportunity_type: str = "") -> list[dict[str, Any]]:
        """获取失败模式警告.

        分析历史失败经验，识别高风险动作模式。

        Args:
            opportunity_type: 机会类型 (为空则全局)

        Returns:
            list[dict]: 失败警告列表
                - action_type: 高风险动作
                - failure_rate: 失败率
                - sample_count: 样本数
                - common_error: 常见错误
        """
        q = ExperienceQuery(failure_only=True)
        if opportunity_type:
            q.opportunity_types = [opportunity_type]

        failures = self._store.query(q)
        if not failures:
            return []

        # 按动作类型分组
        action_groups: dict[str, list[GrowthExperience]] = {}
        for e in failures:
            if e.action_type not in action_groups:
                action_groups[e.action_type] = []
            action_groups[e.action_type].append(e)

        # 获取该类别的总经验数以计算 failure_rate
        all_exps = self._store.query(ExperienceQuery(opportunity_types=[opportunity_type]) if opportunity_type else ExperienceQuery())

        # 计算每个动作类型的总经验数
        action_totals: dict[str, int] = {}
        for e in all_exps:
            action_totals[e.action_type] = action_totals.get(e.action_type, 0) + 1

        warnings: list[dict[str, Any]] = []
        for at, group in action_groups.items():
            failure_count = len(group)
            total_count = action_totals.get(at, failure_count)
            failure_rate = round(failure_count / total_count, 4) if total_count else 0.0

            # 常见错误
            errors = [e.outcome.error for e in group if e.outcome.error]
            common_error = max(set(errors), key=errors.count) if errors else ""

            # 仅警告失败率 > 50% 的动作
            if failure_rate > 0.5:
                warnings.append({
                    "action_type": at,
                    "failure_rate": failure_rate,
                    "failure_count": failure_count,
                    "total_count": total_count,
                    "common_error": common_error,
                })

        # 按失败率降序
        warnings.sort(key=lambda w: -w["failure_rate"])
        return warnings

    # ═══════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> ExperienceStats:
        """获取经验统计 (委托给 ExperienceStore)."""
        return self._store.get_stats()

    def get_summary(self) -> dict[str, Any]:
        """获取记忆库摘要.

        Returns:
            dict: 包含关键统计和洞察
        """
        stats = self._store.get_stats()

        return {
            "total_experiences": stats.total_experiences,
            "success_rate": stats.success_rate,
            "avg_reward": stats.avg_reward,
            "top_actions": stats.top_actions,
            "worst_actions": stats.worst_actions,
            "recent_trend": stats.recent_trend,
            "by_category": stats.by_category,
        }