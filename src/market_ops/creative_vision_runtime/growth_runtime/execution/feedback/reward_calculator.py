"""E13.6.5 Reward Calculator — Reward 计算器.

从 ExecutionFeedback 中计算四维 Reward 信号:
  - execution_reward: 执行质量 (成功率、完成度)
  - efficiency_reward: 效率 (速度、资源利用)
  - safety_reward: 安全性 (无拦截、无警告)
  - outcome_reward: 业务结果 (ROAS 变化等)

核心公式:
  total_reward = execution_weight × execution_reward
               + efficiency_weight × efficiency_reward
               + safety_weight × safety_reward
               + outcome_weight × outcome_reward

  所有分项 reward 在 [-1, 1] 区间.

连接:
  ResultAnalyzer → RewardCalculator → FeedbackProcessor → FeedbackLoop
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .models import (
    ExecutionFeedback,
    FeedbackConfig,
    RewardSignal,
    create_default_config,
)


# ═══════════════════════════════════════════════════════════════
# Reward Calculator
# ═══════════════════════════════════════════════════════════════


class RewardCalculator:
    """Reward 计算器 — 从反馈中计算量化 Reward.

    用法:
        calc = RewardCalculator()
        reward = calc.calculate(feedback)
        print(f"Total Reward: {reward.total_reward}")
    """

    def __init__(self, config: FeedbackConfig | None = None):
        self.config = config or create_default_config()
        self._calculation_count: int = 0

    # ── 主入口 ────────────────────────────────────────────────

    def calculate(
        self,
        feedback: ExecutionFeedback,
        business_metrics: dict[str, Any] | None = None,
    ) -> RewardSignal:
        """计算 Reward 信号.

        Args:
            feedback: 执行反馈
            business_metrics: 业务指标 (ROAS, 收入变化等)

        Returns:
            RewardSignal: 量化 Reward
        """
        self._calculation_count += 1

        # 计算四维 reward
        exec_r = self._calc_execution_reward(feedback)
        eff_r = self._calc_efficiency_reward(feedback)
        safe_r = self._calc_safety_reward(feedback)
        outcome_r = self._calc_outcome_reward(feedback, business_metrics)

        # 加权计算总 reward
        total = (
            self.config.execution_weight * exec_r
            + self.config.efficiency_weight * eff_r
            + self.config.safety_weight * safe_r
            + self.config.outcome_weight * outcome_r
        )

        # 钳制到 [-1, 1]
        total = max(-1.0, min(1.0, total))

        # 确定 reward 等级
        if total > self.config.positive_threshold:
            level = "positive"
        elif total < self.config.negative_threshold:
            level = "negative"
        else:
            level = "neutral"

        # 置信度
        confidence = self._calc_confidence(feedback)

        reward = RewardSignal(
            decision_id=feedback.decision_id,
            total_reward=total,
            execution_reward=exec_r,
            efficiency_reward=eff_r,
            safety_reward=safe_r,
            outcome_reward=outcome_r,
            confidence=confidence,
            components={
                "execution_raw": exec_r,
                "efficiency_raw": eff_r,
                "safety_raw": safe_r,
                "outcome_raw": outcome_r,
                "success_rate": feedback.success_rate,
                "failure_nodes": feedback.failure_nodes,
                "rollback_nodes": feedback.rollback_nodes,
                "duration_ms": feedback.execution_duration_ms,
            },
            reward_level=level,
        )

        return reward

    # ── 批量计算 ──────────────────────────────────────────────

    def calculate_batch(
        self,
        feedbacks: list[ExecutionFeedback],
        business_metrics: dict[str, Any] | None = None,
    ) -> list[RewardSignal]:
        """批量计算 Reward.

        Args:
            feedbacks: 反馈列表
            business_metrics: 业务指标

        Returns:
            list[RewardSignal]: Reward 列表
        """
        return [self.calculate(f, business_metrics) for f in feedbacks]

    # ── 执行 Reward ───────────────────────────────────────────

    def _calc_execution_reward(self, feedback: ExecutionFeedback) -> float:
        """计算执行质量 reward.

        基于:
          - 成功率 (主因子)
          - 失败惩罚
          - 回滚惩罚

        Returns:
            float: execution_reward ∈ [-1, 1]
        """
        if feedback.total_nodes == 0:
            return 0.0

        # 基础分: 成功率映射到 [-1, 1]
        # success_rate=1.0 → 1.0, success_rate=0.5 → 0.0, success_rate=0.0 → -1.0
        base = 2.0 * feedback.success_rate - 1.0

        # 失败惩罚: 每次失败 -0.2
        failure_penalty = feedback.failure_nodes * 0.2

        # 回滚惩罚: 每次回滚 -0.15
        rollback_penalty = feedback.rollback_nodes * 0.15

        reward = base - failure_penalty - rollback_penalty
        return max(-1.0, min(1.0, reward))

    # ── 效率 Reward ───────────────────────────────────────────

    def _calc_efficiency_reward(self, feedback: ExecutionFeedback) -> float:
        """计算效率 reward.

        基于:
          - 执行速度 (越接近 0ms 越好，但需要合理下限)
          - 跳过率 (过高表示浪费)

        Returns:
            float: efficiency_reward ∈ [-1, 1]
        """
        if feedback.total_nodes == 0:
            return 0.0

        # 速度分: 使用 sigmoid 将耗时映射到 [0, 1]
        # 基准: 5000ms 为中性，100ms 接近满分，60000ms 接近 0
        duration = feedback.execution_duration_ms
        if duration <= 0:
            speed_score = 0.5
        else:
            # sigmoid: 1 / (1 + exp((x - 5000) / 10000))
            speed_score = 1.0 / (1.0 + math.exp((duration - 5000) / 10000))

        # 映射到 [-1, 1]: speed_score=1.0 → 1.0, speed_score=0.5 → 0.0, speed_score=0.0 → -1.0
        speed_reward = 2.0 * speed_score - 1.0

        # 跳过率惩罚
        skip_rate = feedback.skipped_nodes / feedback.total_nodes
        skip_penalty = skip_rate * 0.5

        reward = speed_reward - skip_penalty
        return max(-1.0, min(1.0, reward))

    # ── 安全 Reward ───────────────────────────────────────────

    def _calc_safety_reward(self, feedback: ExecutionFeedback) -> float:
        """计算安全 reward.

        基于:
          - 是否被拦截 (BLOCK → -1.0)
          - 是否需要审批 (REQUIRE_APPROVAL → -0.5)
          - 是否有警告 (WARN → -0.2)
          - 风险评分 (risk_score 越高，reward 越低)

        Returns:
            float: safety_reward ∈ [-1, 1]
        """
        # 基础分: 1.0 (完全安全)
        reward = 1.0

        if feedback.was_blocked:
            # 被拦截: 严重扣分
            reward -= 1.0
        elif feedback.needed_approval:
            # 需要审批: 中等扣分
            reward -= 0.5

        # 安全评估中的风险评分
        if feedback.safety_evaluation:
            risk_score = feedback.safety_evaluation.get("risk_score", 0.0)
            # 风险越高，扣分越多
            reward -= risk_score * 0.5

            # 警告数量
            warnings = feedback.safety_evaluation.get("warnings", [])
            reward -= len(warnings) * 0.1

            # 触发规则数
            triggered = feedback.safety_evaluation.get("triggered_rules", [])
            reward -= len(triggered) * 0.05

        return max(-1.0, min(1.0, reward))

    # ── 业务结果 Reward ───────────────────────────────────────

    def _calc_outcome_reward(self, feedback: ExecutionFeedback, business_metrics: dict[str, Any] | None = None) -> float:
        """计算业务结果 reward.

        基于业务指标:
          - ROAS 变化 (正 → 正 reward)
          - 收入变化
          - 转化率变化

        无业务指标时，基于执行成功推断.

        Returns:
            float: outcome_reward ∈ [-1, 1]
        """
        if business_metrics:
            return self._calc_outcome_from_metrics(business_metrics)

        # 无业务指标时，从执行结果推断
        return self._calc_outcome_from_execution(feedback)

    def _calc_outcome_from_metrics(self, metrics: dict[str, Any]) -> float:
        """从业务指标计算 outcome reward."""
        reward = 0.0
        count = 0

        # ROAS 变化
        roas_change = metrics.get("roas_change", 0.0)
        if roas_change != 0.0:
            # sigmoid: ROAS +20% → 0.88, ROAS -20% → -0.88
            reward += math.tanh(roas_change * 5.0)
            count += 1

        # 收入变化
        revenue_change = metrics.get("revenue_change", 0.0)
        if revenue_change != 0.0:
            reward += math.tanh(revenue_change * 3.0)
            count += 1

        # 转化率变化
        cvr_change = metrics.get("cvr_change", 0.0)
        if cvr_change != 0.0:
            reward += math.tanh(cvr_change * 5.0)
            count += 1

        # CPA 变化 (反向: CPA 降低 = 正向)
        cpa_change = metrics.get("cpa_change", 0.0)
        if cpa_change != 0.0:
            reward += math.tanh(-cpa_change * 5.0)
            count += 1

        if count == 0:
            return 0.0

        return max(-1.0, min(1.0, reward / count))

    def _calc_outcome_from_execution(self, feedback: ExecutionFeedback) -> float:
        """从执行结果推断业务结果 (无实际指标时的 fallback).

        推断逻辑:
          - 全部成功 → 中性偏正 (0.3)
          - 有失败 → 负向 (-0.3)
          - 被拦截 → 负向 (-0.5)
        """
        if feedback.was_blocked:
            return -0.5

        if feedback.has_failures:
            return -0.3

        if feedback.success_rate >= 1.0:
            return 0.3

        if feedback.success_rate >= 0.8:
            return 0.1

        return 0.0

    # ── 置信度 ────────────────────────────────────────────────

    def _calc_confidence(self, feedback: ExecutionFeedback) -> float:
        """计算 Reward 置信度.

        基于:
          - 执行节点数 (越多越可靠)
          - 是否有业务指标 (有 → 更可靠)
          - 审计条目完整性

        Returns:
            float: confidence ∈ [0, 1]
        """
        confidence = 0.5  # 基础置信度

        # 节点数越多，置信度越高
        if feedback.total_nodes > 0:
            node_bonus = min(feedback.total_nodes / 10.0, 0.3)
            confidence += node_bonus

        # 有审计记录 → 更可靠
        if feedback.audit_entries:
            confidence += 0.1

        # 有安全评估 → 更可靠
        if feedback.safety_evaluation:
            confidence += 0.1

        return max(0.0, min(1.0, confidence))

    # ── 统计 ──────────────────────────────────────────────────

    def get_reward_distribution(
        self,
        rewards: list[RewardSignal],
    ) -> dict[str, Any]:
        """获取 Reward 分布统计.

        Args:
            rewards: Reward 列表

        Returns:
            dict: 分布统计
        """
        if not rewards:
            return {"count": 0, "distribution": {}}

        positive = sum(1 for r in rewards if r.is_positive)
        neutral = sum(1 for r in rewards if r.is_neutral)
        negative = sum(1 for r in rewards if r.is_negative)

        totals = [r.total_reward for r in rewards]
        execs = [r.execution_reward for r in rewards]
        effs = [r.efficiency_reward for r in rewards]
        safes = [r.safety_reward for r in rewards]
        outcomes = [r.outcome_reward for r in rewards]

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 4)

        return {
            "count": len(rewards),
            "distribution": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
            },
            "avg_total": _avg(totals),
            "avg_execution": _avg(execs),
            "avg_efficiency": _avg(effs),
            "avg_safety": _avg(safes),
            "avg_outcome": _avg(outcomes),
            "min_total": round(min(totals), 4),
            "max_total": round(max(totals), 4),
        }

    @property
    def calculation_count(self) -> int:
        return self._calculation_count

    def reset(self) -> None:
        """重置计数器."""
        self._calculation_count = 0