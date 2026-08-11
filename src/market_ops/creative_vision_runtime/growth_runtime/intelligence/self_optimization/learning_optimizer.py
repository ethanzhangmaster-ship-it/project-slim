"""E15.3.4 Learning Optimizer — 学习优化器.

优化记忆系统和学习循环的参数，提升经验质量和复用率。

连接:
  - E15.1.5 Memory Feedback Bridge: 经验质量评估
  - E15.3.2 Decision Loop:         学习速度优化

优化目标:
  - Pattern mining threshold
  - Experience importance weighting
  - Retrieval similarity threshold
  - Learning rate adjustment

用法:
    optimizer = LearningOptimizer()
    opportunities = optimizer.analyze(memory_stats)
    actions = optimizer.generate_actions(opportunities)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    OptimizationAction,
    OptimizationArea,
    OptimizationOpportunity,
    OptimizationStatus,
    OptimizationPolicy,
)


# ═══════════════════════════════════════════════════════════════
# Learning Optimizer
# ═══════════════════════════════════════════════════════════════


class LearningOptimizer:
    """E15.3.4 学习优化器 — 优化记忆和学习系统.

    分析经验质量和检索效率，生成优化建议。

    用法:
        optimizer = LearningOptimizer()
        opportunities = optimizer.analyze(memory_stats)
        actions = optimizer.generate_actions(opportunities)
    """

    def __init__(self, policy: OptimizationPolicy | None = None):
        self._policy = policy or OptimizationPolicy()
        self._actions: list[OptimizationAction] = []

    # ── Analyze ─────────────────────────────────────────────────

    def analyze(self, memory_stats: dict[str, Any]) -> list[OptimizationOpportunity]:
        """分析记忆系统状态，发现优化机会.

        Args:
            memory_stats: 记忆系统统计数据
                {
                    "total_experiences": int,
                    "successful_patterns": int,
                    "retrieval_hit_rate": float,
                    "avg_experience_quality": float,
                    "pattern_utilization_rate": float,
                    "similarity_threshold": float,
                    "retrieval_top_k": int,
                }

        Returns:
            list[OptimizationOpportunity]
        """
        opportunities: list[OptimizationOpportunity] = []

        # 1. 检查记忆命中率
        retrieval_rate = memory_stats.get("retrieval_hit_rate", 0.0)
        if retrieval_rate < 0.50:
            opportunities.append(OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Memory retrieval hit rate too low",
                evidence=[
                    f"Hit rate: {retrieval_rate:.2f}",
                    f"Target: 0.70",
                ],
                expected_gain=0.15,
                confidence=0.80,
                suggested_change="Decrease similarity_threshold from 0.85 to 0.78",
                priority=1,
            ))

        # 2. 检查模式利用率
        utilization = memory_stats.get("pattern_utilization_rate", 0.0)
        if utilization < 0.30:
            opportunities.append(OptimizationOpportunity(
                area=OptimizationArea.MEMORY,
                problem="Pattern utilization rate too low",
                evidence=[
                    f"Utilization: {utilization:.2f}",
                    f"Target: 0.50",
                ],
                expected_gain=0.10,
                confidence=0.75,
                suggested_change="Increase retrieval_top_k or decrease similarity_threshold",
                priority=2,
            ))

        # 3. 检查经验质量
        quality = memory_stats.get("avg_experience_quality", 0.0)
        if quality < 0.50:
            opportunities.append(OptimizationOpportunity(
                area=OptimizationArea.LEARNING,
                problem="Average experience quality too low",
                evidence=[
                    f"Quality: {quality:.2f}",
                    f"Target: 0.60",
                ],
                expected_gain=0.12,
                confidence=0.70,
                suggested_change="Increase experience_weight to prioritize high-quality experiences",
                priority=2,
            ))

        # 4. 检查模式挖掘效率
        total_patterns = memory_stats.get("successful_patterns", 0)
        total_experiences = memory_stats.get("total_experiences", 1)
        pattern_ratio = total_patterns / max(1, total_experiences)
        if pattern_ratio < 0.10 and total_experiences > 50:
            opportunities.append(OptimizationOpportunity(
                area=OptimizationArea.LEARNING,
                problem="Pattern mining efficiency too low",
                evidence=[
                    f"Patterns: {total_patterns}/{total_experiences} ({pattern_ratio:.2%})",
                ],
                expected_gain=0.08,
                confidence=0.65,
                suggested_change="Lower pattern mining threshold to capture more patterns",
                priority=3,
            ))

        return opportunities

    # ── Generate Actions ────────────────────────────────────────

    def generate_actions(
        self, opportunities: list[OptimizationOpportunity]
    ) -> list[OptimizationAction]:
        """根据优化机会生成学习参数调整动作.

        Args:
            opportunities: 优化机会列表

        Returns:
            list[OptimizationAction]
        """
        actions: list[OptimizationAction] = []
        for opp in opportunities:
            if not opp.is_actionable():
                continue
            action = self._map_to_action(opp)
            if action:
                actions.append(action)
                self._actions.append(action)
        return actions

    def _map_to_action(self, opp: OptimizationOpportunity) -> OptimizationAction | None:
        """将优化机会映射为参数调整动作."""
        # 根据问题描述推断参数
        param_map = {
            "retrieval_hit_rate": ("similarity_threshold", 0.85, 0.78),
            "pattern_utilization": ("retrieval_top_k", 10, 13),
            "experience_quality": ("experience_weight", 1.00, 1.20),
            "pattern_mining": ("similarity_threshold", 0.85, 0.80),
        }

        matched = None
        for keyword, (param, old, new) in param_map.items():
            if keyword in opp.problem.lower().replace(" ", "_"):
                matched = (param, old, new)
                break

        if matched is None:
            return None

        param, old_val, new_val = matched
        return OptimizationAction(
            opportunity_id=opp.opportunity_id,
            area=opp.area,
            parameter=param,
            old_value=old_val,
            new_value=new_val,
            reason=opp.problem,
            risk_level="low",
            status=OptimizationStatus.PROPOSED,
        )

    # ── Evaluate Learning Quality ───────────────────────────────

    def evaluate_experience_quality(
        self, experiences: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """评估经验质量.

        Args:
            experiences: 经验列表，每条包含 reward, outcome, confidence 等

        Returns:
            dict: 质量评估结果
        """
        if not experiences:
            return {"quality": 0.0, "count": 0, "issues": ["no_experiences"]}

        # 计算质量指标
        rewards = [e.get("reward", 0.0) for e in experiences]
        avg_reward = sum(rewards) / len(rewards)
        positive_ratio = sum(1 for r in rewards if r > 0) / len(rewards)

        quality = (avg_reward * 0.5 + positive_ratio * 0.5)

        issues = []
        if avg_reward < 0.3:
            issues.append("low_avg_reward")
        if positive_ratio < 0.4:
            issues.append("low_positive_ratio")

        return {
            "quality": round(quality, 4),
            "count": len(experiences),
            "avg_reward": round(avg_reward, 4),
            "positive_ratio": round(positive_ratio, 4),
            "issues": issues,
        }

    def evaluate_retrieval_efficiency(
        self, retrieval_stats: dict[str, Any]
    ) -> dict[str, Any]:
        """评估检索效率.

        Args:
            retrieval_stats: {
                "total_queries": int,
                "hits": int,
                "avg_similarity": float,
                "threshold": float,
            }

        Returns:
            dict: 效率评估
        """
        total = retrieval_stats.get("total_queries", 0)
        hits = retrieval_stats.get("hits", 0)
        avg_sim = retrieval_stats.get("avg_similarity", 0.0)
        threshold = retrieval_stats.get("threshold", 0.85)

        hit_rate = hits / max(1, total)
        efficiency = hit_rate * (avg_sim / max(0.01, threshold))

        return {
            "hit_rate": round(hit_rate, 4),
            "efficiency": round(efficiency, 4),
            "avg_similarity": round(avg_sim, 4),
            "recommendation": "decrease_threshold" if hit_rate < 0.5 else "maintain",
        }

    # ── Query ───────────────────────────────────────────────────

    def get_actions(self) -> list[OptimizationAction]:
        return list(self._actions)

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_actions": len(self._actions),
            "proposed": len([a for a in self._actions if a.status == OptimizationStatus.PROPOSED]),
            "applied": len([a for a in self._actions if a.status == OptimizationStatus.APPLIED]),
        }

    def reset(self) -> None:
        self._actions.clear()


__all__ = ["LearningOptimizer"]