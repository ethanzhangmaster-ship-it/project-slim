"""E17.11.3 ExperienceConsolidationAdapter — 经验整合适配器.

Day 7.11 Step 3.2:
  将 GrowthExperience[] 转换为 ConsolidationContext，
  适配 MemoryConsolidationPipeline 的输入协议。

核心职责:
  1. 聚合 GrowthExperience[] 为 ConsolidationContext
  2. 提取聚合后的 policy_decision / execution_result / effectiveness
  3. 保持 duck-type 兼容，使 MemoryConsolidationPipeline 无修改消费

设计原则:
  - 输入适配层，不实现业务逻辑
  - 兼容 ConsolidationContext 的 duck-type 协议
  - 聚合统计而非简单包装
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from typing import Any

from .models.consolidation_models import (
    ConsolidationContext,
    _MockEffectiveness,
    _MockExecutionResult,
    _MockPolicyDecision,
)


class ExperienceConsolidationAdapter:
    """GrowthExperience → ConsolidationContext 适配器.

    将 GrowthExperience 列表聚合为 MemoryConsolidationPipeline 可消费的
    ConsolidationContext，复用 Day 7.10 的核心整合引擎。

    聚合逻辑:
      - policy_decision: 取最常见 action_type，置信度取平均
      - execution_result: 取多数成功/失败
      - effectiveness: 聚合所有 metrics_delta 和 reward

    用法:
        adapter = ExperienceConsolidationAdapter()
        context = adapter.build_context(experiences)
        report = memory_pipeline.consolidate(context)
    """

    # ── 默认配置 ─────────────────────────────────────────────────

    DEFAULT_CYCLE_NUMBER = 0

    def __init__(self) -> None:
        self._build_count: int = 0
        self._total_experiences_adapted: int = 0
        self._cycle_number: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def build_count(self) -> int:
        return self._build_count

    @property
    def total_experiences_adapted(self) -> int:
        return self._total_experiences_adapted

    # ── Public API ──────────────────────────────────────────────

    def build_context(
        self,
        experiences: list[Any],
        history_avg_reward: float | None = None,
    ) -> ConsolidationContext:
        """将 GrowthExperience[] 转换为 ConsolidationContext.

        Args:
            experiences: GrowthExperience 列表
            history_avg_reward: 历史平均奖励 (用于 learning_gain 计算)

        Returns:
            ConsolidationContext: 整合上下文
        """
        self._build_count += 1
        self._cycle_number += 1
        total = len(experiences)
        self._total_experiences_adapted += total

        if not experiences:
            return ConsolidationContext(
                cycle_number=self._cycle_number,
                source_experiences=[],
                experience_count=0,
                metadata={"build_count": self._build_count},
            )

        # ── 聚合 policy_decision ──
        policy = self._aggregate_policy(experiences)

        # ── 聚合 execution_result ──
        execution = self._aggregate_execution(experiences)

        # ── 聚合 effectiveness ──
        effectiveness = self._aggregate_effectiveness(experiences, history_avg_reward)

        return ConsolidationContext(
            cycle_number=self._cycle_number,
            source_experiences=experiences,
            experience_count=total,
            policy_decision=policy,
            execution_result=execution,
            effectiveness=effectiveness,
            metadata={
                "build_count": self._build_count,
                "adapter": "ExperienceConsolidationAdapter",
                "history_avg_reward": history_avg_reward,
            },
        )

    # ── Aggregate Methods ───────────────────────────────────────

    def _aggregate_policy(
        self,
        experiences: list[Any],
    ) -> _MockPolicyDecision:
        """聚合策略决策: 取最常见的 action_type，置信度取平均."""
        if not experiences:
            return _MockPolicyDecision()

        # 统计 action_type 频率
        action_counts: dict[str, int] = {}
        confidences: list[float] = []
        for e in experiences:
            action = getattr(e, "action_type", "")
            if action:
                action_counts[action] = action_counts.get(action, 0) + 1
            conf = getattr(e, "confidence", 0.0)
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))

        # 最常见的 action
        top_action = (
            max(action_counts, key=action_counts.get) if action_counts else ""
        )
        avg_confidence = (
            round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        )

        # 决策类型: 基于成功率
        success_count = sum(1 for e in experiences if self._is_successful(e))
        success_rate = success_count / len(experiences) if experiences else 0.0
        decision_type = "allow_learning" if success_rate >= 0.5 else "adjust_mode"

        # 提取 action_params
        action_params: dict[str, Any] = {
            "experience_count": len(experiences),
            "success_count": success_count,
            "success_rate": round(success_rate, 4),
            "unique_actions": list(action_counts.keys()),
        }

        return _MockPolicyDecision(
            action=top_action,
            decision_type=decision_type,
            confidence=avg_confidence,
            action_params=action_params,
        )

    def _aggregate_execution(
        self,
        experiences: list[Any],
    ) -> _MockExecutionResult:
        """聚合执行结果: 取多数成功/失败."""
        if not experiences:
            return _MockExecutionResult(success=False, action="")

        success_count = sum(1 for e in experiences if self._is_successful(e))
        total = len(experiences)
        majority_success = success_count >= total / 2

        # 取最常见的 action
        action_counts: dict[str, int] = {}
        for e in experiences:
            action = getattr(e, "action_type", "")
            if action:
                action_counts[action] = action_counts.get(action, 0) + 1
        top_action = max(action_counts, key=action_counts.get) if action_counts else ""

        return _MockExecutionResult(
            success=majority_success,
            action=top_action,
        )

    def _aggregate_effectiveness(
        self,
        experiences: list[Any],
        history_avg_reward: float | None = None,
    ) -> _MockEffectiveness:
        """聚合学习有效性: 合并所有 metrics_delta 和 reward."""
        if not experiences:
            return _MockEffectiveness()

        # 合并 metrics_delta
        metrics_delta: dict[str, float] = {}
        for e in experiences:
            outcome = getattr(e, "outcome", None)
            if outcome is not None:
                delta = getattr(outcome, "metrics_delta", {})
                if isinstance(delta, dict):
                    for k, v in delta.items():
                        if isinstance(v, (int, float)):
                            metrics_delta[k] = metrics_delta.get(k, 0.0) + float(v)

        # 平均化 metrics_delta
        total = len(experiences)
        for k in metrics_delta:
            metrics_delta[k] = round(metrics_delta[k] / total, 4)

        # 平均 reward
        avg_reward = round(
            sum(getattr(e, "reward", 0.0) for e in experiences) / total, 4
        )

        # learning_gain: 相对于历史平均的提升
        hist = history_avg_reward if history_avg_reward is not None else 0.50
        learning_gain = round(max(0.0, avg_reward - hist), 4)

        # effectiveness_score: 基于成功率和平均 reward
        success_count = sum(1 for e in experiences if self._is_successful(e))
        success_rate = success_count / total if total > 0 else 0.0
        effectiveness_score = round((avg_reward * 0.6 + success_rate * 0.4), 4)

        return _MockEffectiveness(
            learning_gain=learning_gain,
            effectiveness_score=effectiveness_score,
            metrics_delta=metrics_delta,
        )

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _is_successful(experience: Any) -> bool:
        """判断经验是否成功."""
        if hasattr(experience, "is_successful"):
            return bool(experience.is_successful())
        outcome = getattr(experience, "outcome", None)
        if outcome is not None:
            return bool(getattr(outcome, "success", False))
        return getattr(experience, "reward", 0.0) >= 0.50

    # ── Management ──────────────────────────────────────────────

    def reset(self) -> None:
        """重置适配器状态."""
        self._build_count = 0
        self._total_experiences_adapted = 0
        self._cycle_number = 0


__all__ = [
    "ExperienceConsolidationAdapter",
]