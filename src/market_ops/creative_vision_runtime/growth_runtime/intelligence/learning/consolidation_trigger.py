"""E17.11.3 ConsolidationTrigger — 整合触发判定引擎.

Day 7.11 Step 3.1:
  独立触发逻辑，决定是否将经验批次送入 MemoryConsolidationPipeline。

核心职责:
  1. 检查经验数量阈值
  2. 检查高重要性经验比例
  3. 检查奖励提升趋势
  4. 管理冷却周期

设计原则:
  - 独立于 Pipeline，不嵌入编排逻辑
  - 多个检查条件 OR 关系 (任一满足即触发)
  - 返回 TriggerDecision 而非 boolean，包含置信度和原因
  - 可配置阈值，支持测试模式
"""

from __future__ import annotations

from typing import Any

from .models.consolidation_models import (
    TriggerDecision,
    TriggerReason,
)


class ConsolidationTrigger:
    """整合触发判定引擎.

    检查经验批次是否满足整合条件，决定是否触发 MemoryConsolidationPipeline。

    触发条件 (OR 关系):
      1. 经验数量 >= min_experience_count
      2. 高重要性经验比例 >= min_importance_ratio
      3. 最近 N 条经验的平均奖励 > 历史平均

    用法:
        trigger = ConsolidationTrigger(
            min_experience_count=5,
            min_importance_ratio=0.3,
        )
        decision = trigger.check(experiences)

        if decision.should_run:
            pipeline.run(experiences)
    """

    # ── 默认阈值 ─────────────────────────────────────────────────

    DEFAULT_MIN_EXPERIENCE_COUNT = 5
    DEFAULT_MIN_IMPORTANCE_RATIO = 0.30
    DEFAULT_REWARD_WINDOW = 5          # 奖励趋势窗口大小
    DEFAULT_REWARD_IMPROVEMENT_MIN = 0.05  # 最小奖励提升
    DEFAULT_HISTORY_AVG_REWARD = 0.50  # 默认历史平均奖励 (无历史时)
    DEFAULT_REWARD_WINDOW_MIN = 2      # 趋势窗口最小样本数
    DEFAULT_COOLDOWN_COUNT = 3         # 冷却周期 (连续跳过次数)

    def __init__(
        self,
        min_experience_count: int = DEFAULT_MIN_EXPERIENCE_COUNT,
        min_importance_ratio: float = DEFAULT_MIN_IMPORTANCE_RATIO,
        reward_window: int = DEFAULT_REWARD_WINDOW,
        reward_improvement_min: float = DEFAULT_REWARD_IMPROVEMENT_MIN,
        history_avg_reward: float = DEFAULT_HISTORY_AVG_REWARD,
        cooldown_count: int = DEFAULT_COOLDOWN_COUNT,
        enabled: bool = True,
    ):
        """初始化触发判定引擎.

        Args:
            min_experience_count: 触发整合的最小经验数
            min_importance_ratio: 触发整合的最小高重要性经验比例
            reward_window: 奖励趋势检查的窗口大小
            reward_improvement_min: 最小奖励提升幅度
            history_avg_reward: 历史平均奖励 (外部传入)
            cooldown_count: 冷却周期 (连续跳过 N 次后强制触发)
            enabled: 是否启用
        """
        self.min_experience_count = min_experience_count
        self.min_importance_ratio = min_importance_ratio
        self.reward_window = reward_window
        self.reward_improvement_min = reward_improvement_min
        self.history_avg_reward = history_avg_reward
        self.cooldown_count = cooldown_count
        self.enabled = enabled

        self._check_count: int = 0
        self._trigger_count: int = 0
        self._skip_streak: int = 0  # 连续跳过次数

    # ── Properties ──────────────────────────────────────────────

    @property
    def check_count(self) -> int:
        return self._check_count

    @property
    def trigger_count(self) -> int:
        return self._trigger_count

    @property
    def skip_streak(self) -> int:
        return self._skip_streak

    # ── Public API ──────────────────────────────────────────────

    def check(self, experiences: list[Any]) -> TriggerDecision:
        """检查是否应该触发整合.

        Args:
            experiences: GrowthExperience 列表

        Returns:
            TriggerDecision: 触发决策
        """
        self._check_count += 1

        if not self.enabled:
            return TriggerDecision.skip("trigger disabled")

        if not experiences:
            self._skip_streak += 1
            return TriggerDecision.skip("no experiences")

        total = len(experiences)

        # ── Check 1: Count Threshold ──
        if total >= self.min_experience_count:
            decision = TriggerDecision.approve(
                reason=TriggerReason.COUNT_THRESHOLD,
                confidence=min(1.0, total / (self.min_experience_count * 2)),
                urgency=min(1.0, total / (self.min_experience_count * 3)),
                experience_count=total,
                threshold=self.min_experience_count,
            )
            self._trigger_count += 1
            self._skip_streak = 0
            return decision

        # ── Check 2: Importance Threshold ──
        high_importance = self._count_high_importance(experiences)
        importance_ratio = high_importance / total if total > 0 else 0.0
        if importance_ratio >= self.min_importance_ratio:
            decision = TriggerDecision.approve(
                reason=TriggerReason.IMPORTANCE_THRESHOLD,
                confidence=min(1.0, importance_ratio / (self.min_importance_ratio * 2)),
                urgency=importance_ratio,
                high_importance_count=high_importance,
                total_count=total,
                ratio=round(importance_ratio, 4),
            )
            self._trigger_count += 1
            self._skip_streak = 0
            return decision

        # ── Check 3: Reward Improvement Trend ──
        if total >= self.reward_window:
            recent_avg = self._calc_recent_avg_reward(experiences)
            if recent_avg >= self.history_avg_reward + self.reward_improvement_min:
                improvement = recent_avg - self.history_avg_reward
                decision = TriggerDecision.approve(
                    reason=TriggerReason.REWARD_IMPROVEMENT,
                    confidence=min(1.0, improvement / 0.20),
                    urgency=min(1.0, improvement / 0.15),
                    recent_avg_reward=round(recent_avg, 4),
                    history_avg_reward=round(self.history_avg_reward, 4),
                    improvement=round(improvement, 4),
                )
                self._trigger_count += 1
                self._skip_streak = 0
                return decision

        # ── Check 4: Cooldown Expired ──
        self._skip_streak += 1
        if self._skip_streak >= self.cooldown_count:
            decision = TriggerDecision.approve(
                reason=TriggerReason.COOLDOWN_EXPIRED,
                confidence=0.50,
                urgency=0.60,
                skip_streak=self._skip_streak,
                cooldown_count=self.cooldown_count,
            )
            self._trigger_count += 1
            self._skip_streak = 0
            return decision

        return TriggerDecision.skip(
            f"count={total}<{self.min_experience_count}, "
            f"importance_ratio={importance_ratio:.2f}<{self.min_importance_ratio}, "
            f"skip_streak={self._skip_streak}/{self.cooldown_count}"
        )

    def check_batch(
        self,
        experiences: list[Any],
        min_reward: float = 0.0,
    ) -> TriggerDecision:
        """批量检查 — 同时检查所有条件.

        Args:
            experiences: GrowthExperience 列表
            min_reward: 最低奖励过滤 (只考虑 reward >= min_reward 的经验)

        Returns:
            TriggerDecision
        """
        if min_reward > 0:
            filtered = [e for e in experiences if getattr(e, "reward", 0.0) >= min_reward]
            return self.check(filtered)
        return self.check(experiences)

    # ── Internal ────────────────────────────────────────────────

    def _count_high_importance(self, experiences: list[Any]) -> int:
        """统计高重要性经验数量.

        高重要性 = reward >= 0.75 或 confidence >= 0.80
        """
        count = 0
        for e in experiences:
            reward = getattr(e, "reward", 0.0)
            confidence = getattr(e, "confidence", 0.0)
            if reward >= 0.75 or confidence >= 0.80:
                count += 1
        return count

    def _calc_recent_avg_reward(self, experiences: list[Any]) -> float:
        """计算最近 N 条经验的平均奖励."""
        window = min(self.reward_window, len(experiences))
        if window == 0:
            return 0.0
        recent = experiences[-window:]
        total = sum(getattr(e, "reward", 0.0) for e in recent)
        return round(total / window, 4)

    # ── Configuration ───────────────────────────────────────────

    def set_history_avg_reward(self, avg_reward: float) -> None:
        """设置历史平均奖励 (由外部统计)."""
        self.history_avg_reward = max(0.0, min(1.0, avg_reward))

    def reset(self) -> None:
        """重置触发状态."""
        self._check_count = 0
        self._trigger_count = 0
        self._skip_streak = 0

    @classmethod
    def test_mode(cls) -> ConsolidationTrigger:
        """测试模式: 低阈值，快速触发."""
        return cls(
            min_experience_count=2,
            min_importance_ratio=0.10,
            reward_window=2,
            reward_improvement_min=0.01,
            cooldown_count=1,
            enabled=True,
        )

    @classmethod
    def strict_mode(cls) -> ConsolidationTrigger:
        """严格模式: 高阈值，谨慎触发."""
        return cls(
            min_experience_count=20,
            min_importance_ratio=0.50,
            reward_window=10,
            reward_improvement_min=0.10,
            cooldown_count=10,
            enabled=True,
        )


__all__ = [
    "ConsolidationTrigger",
]