"""E13.7.9 Pattern Decay Engine — 模式衰减引擎.

Day 7.9 Step 4:
  对 PatternStore 中的模式进行衰减评估，
  识别过期、低效、未使用的模式并执行相应衰减策略。

核心职责:
  1. 计算 decay_score (多维度衰减评分)
  2. 根据 decay_score 决定 DecayAction
  3. 应用衰减策略 (REDUCE_CONFIDENCE / MARK_AVOID / ARCHIVE / DELETE)
  4. 与 PatternLifecycleManager 集成 (状态迁移)

流程:
  PatternStore.get_all()
      │
      ▼
  for each pattern:
      │
      ├─→ calculate_decay_score() → DecayScore
      ├─→ determine_decay_action() → DecayAction
      ├─→ apply_decay() → PatternDecayResult
      └─→ lifecycle_manager.transition()
      │
      ▼
  DecayBatchResult

连接:
  PatternStore → PatternDecayEngine → PatternLifecycleManager

设计原则:
  - 与 PatternLifecycleManager 互补 (评分层 vs 状态机层)
  - 不修改已有模块 (PatternLifecycleManager, PatternEvaluator)
  - 确定性衰减评分，可解释
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .models.pattern_decay_models import (
    DecayAction,
    DecayBatchResult,
    DecayScore,
    PatternDecayReason,
    PatternDecayResult,
)


class PatternDecayEngine:
    """模式衰减引擎 — 评估并执行模式衰减.

    核心衰减公式:
      decay_score = stale_factor × 0.35 + reward_drop × 0.30
                  + usage_drop × 0.20 + confidence_loss × 0.15

    衰减阈值:
      | Decay Score | Action            |
      |------------|-------------------|
      | < 0.3      | MAINTAIN          |
      | 0.3 ~ 0.6  | REDUCE_CONFIDENCE |
      | 0.6 ~ 0.8  | MARK_AVOID        |
      | >= 0.8     | ARCHIVE           |

    用法:
        engine = PatternDecayEngine()
        batch = engine.decay_store(pattern_store, lifecycle_manager)
        # 或者评估单个模式
        result = engine.evaluate_pattern(pattern)
    """

    # 衰减阈值
    MAINTAIN_THRESHOLD = 0.3
    REDUCE_CONFIDENCE_THRESHOLD = 0.6
    MARK_AVOID_THRESHOLD = 0.8

    # 置信度调整系数
    REDUCE_CONFIDENCE_FACTOR = 0.85
    MARK_AVOID_CONFIDENCE_FACTOR = 0.70

    # 过期阈值
    STALE_DAYS_THRESHOLD = 30         # 超过此天数即认为过期
    MAX_STALE_DAYS = 90               # 最大过期天数 (stale_factor = 1.0)

    # 最低样本数
    MIN_SAMPLES_THRESHOLD = 3

    # 权重
    WEIGHT_STALE = 0.35
    WEIGHT_REWARD = 0.30
    WEIGHT_USAGE = 0.20
    WEIGHT_CONFIDENCE = 0.15

    def __init__(
        self,
        now: datetime | None = None,
        stale_days: float = STALE_DAYS_THRESHOLD,
        max_stale_days: float = MAX_STALE_DAYS,
    ):
        self._now = now or datetime.now(timezone.utc)
        self._stale_days = max(1.0, stale_days)
        self._max_stale_days = max(self._stale_days, max_stale_days)
        self._decay_count: int = 0
        self._total_decayed: int = 0
        self._total_archived: int = 0
        self._total_deleted: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def decay_count(self) -> int:
        return self._decay_count

    @property
    def total_decayed(self) -> int:
        return self._total_decayed

    @property
    def total_archived(self) -> int:
        return self._total_archived

    @property
    def total_deleted(self) -> int:
        return self._total_deleted

    # ── Public API ───────────────────────────────────────────────

    def decay_store(
        self,
        pattern_store: Any,  # PatternStore
        lifecycle_manager: Any = None,  # PatternLifecycleManager
    ) -> DecayBatchResult:
        """对 PatternStore 中所有模式执行衰减评估 — 主入口.

        Args:
            pattern_store: PatternStore 实例
            lifecycle_manager: PatternLifecycleManager 实例 (可选)

        Returns:
            DecayBatchResult: 批量衰减结果
        """
        self._decay_count += 1
        patterns = pattern_store.get_all()
        results: list[PatternDecayResult] = []

        for pattern in patterns:
            result = self.evaluate_pattern(pattern, lifecycle_manager)
            results.append(result)

            # 应用衰减
            if result.action == DecayAction.DELETE.value:
                pattern_store.remove(pattern)
            elif result.action == DecayAction.ARCHIVE.value:
                if lifecycle_manager is not None:
                    lifecycle_manager.check_pattern(pattern)
                pattern_store.store(pattern)
            elif result.changed:
                pattern_store.store(pattern)

        return DecayBatchResult.from_results(results)

    def evaluate_pattern(
        self,
        pattern: Any,  # PatternMemory
        lifecycle_manager: Any = None,  # PatternLifecycleManager
    ) -> PatternDecayResult:
        """评估单个模式的衰减状态.

        Args:
            pattern: PatternMemory 实例
            lifecycle_manager: PatternLifecycleManager 实例 (可选)

        Returns:
            PatternDecayResult: 衰减结果
        """
        # 记录衰减前状态
        confidence_before = pattern.confidence
        score_before = pattern.score
        lifecycle_before = pattern.metadata.get("lifecycle_state", "active")

        # 计算衰减评分
        decay_score = self.calculate_decay_score(pattern)

        # 确定衰减动作
        action = self._determine_decay_action(decay_score)

        # 应用衰减
        self._apply_decay(pattern, decay_score, action)

        # 生命周期管理
        lifecycle_after = lifecycle_before
        if lifecycle_manager is not None and action in (DecayAction.ARCHIVE, DecayAction.MARK_AVOID):
            transition = lifecycle_manager.check_pattern(pattern)
            if transition is not None:
                lifecycle_after = transition.to_state.value

        # 更新计数器
        changed = action != DecayAction.MAINTAIN
        if changed:
            self._total_decayed += 1
        if action == DecayAction.ARCHIVE:
            self._total_archived += 1
        elif action == DecayAction.DELETE:
            self._total_deleted += 1

        return PatternDecayResult(
            pattern_id=pattern.pattern_id,
            reason=decay_score.reason,
            action=action.value,
            decay_score=decay_score,
            confidence_before=round(confidence_before, 4),
            confidence_after=round(pattern.confidence, 4),
            confidence_delta=round(pattern.confidence - confidence_before, 4),
            score_before=round(score_before, 4),
            score_after=round(pattern.score, 4),
            score_delta=round(pattern.score - score_before, 4),
            lifecycle_from=lifecycle_before,
            lifecycle_to=lifecycle_after,
            changed=changed,
        )

    def calculate_decay_score(self, pattern: Any) -> DecayScore:
        """计算多维度衰减评分.

        公式:
          decay_score = stale_factor × 0.35 + reward_drop × 0.30
                      + usage_drop × 0.20 + confidence_loss × 0.15

        Args:
            pattern: PatternMemory 实例

        Returns:
            DecayScore: 衰减评分
        """
        perf = pattern.performance

        # 1. Stale Factor: 基于 last_seen 计算
        stale_factor = self._calc_stale_factor(perf.last_seen)

        # 2. Reward Drop: 奖励下降
        reward_drop = self._calc_reward_drop(perf.avg_reward, pattern.metadata)

        # 3. Usage Drop: 使用频率下降
        usage_drop = self._calc_usage_drop(pattern.metadata)

        # 4. Confidence Loss: 置信度损失
        confidence_loss = self._calc_confidence_loss(pattern)

        # 综合评分
        total = round(
            stale_factor * self.WEIGHT_STALE
            + reward_drop * self.WEIGHT_REWARD
            + usage_drop * self.WEIGHT_USAGE
            + confidence_loss * self.WEIGHT_CONFIDENCE,
            4,
        )

        # 主导原因
        reason = self._determine_dominant_reason(
            stale_factor, reward_drop, usage_drop, confidence_loss,
        )

        return DecayScore(
            total=total,
            stale_factor=round(stale_factor, 4),
            reward_drop=round(reward_drop, 4),
            usage_drop=round(usage_drop, 4),
            confidence_loss=round(confidence_loss, 4),
            factors={
                "stale_factor": round(stale_factor, 4),
                "reward_drop": round(reward_drop, 4),
                "usage_drop": round(usage_drop, 4),
                "confidence_loss": round(confidence_loss, 4),
            },
            reason=reason,
        )

    # ── Factor Calculation ──────────────────────────────────────

    def _calc_stale_factor(self, last_seen: str) -> float:
        """计算过期因子.

        stale_factor = min(days_since_last_seen / max_stale_days, 1.0)
        """
        if not last_seen:
            return 0.0
        days = self._days_since(last_seen)
        if days is None:
            return 0.0
        return round(min(days / self._max_stale_days, 1.0), 4)

    def _calc_reward_drop(
        self,
        avg_reward: float,
        metadata: dict[str, Any],
    ) -> float:
        """计算奖励下降.

        reward_drop = 1.0 - (current_avg_reward / max(peak_reward, 0.01))
        clamped to [0, 1]
        """
        peak_reward = metadata.get("peak_reward", avg_reward)
        if peak_reward <= 0 or avg_reward <= 0:
            return 0.0
        ratio = avg_reward / max(peak_reward, 0.01)
        drop = 1.0 - ratio
        return round(max(0.0, min(1.0, drop)), 4)

    def _calc_usage_drop(self, metadata: dict[str, Any]) -> float:
        """计算使用频率下降.

        usage_drop = 1.0 - (recent_usage / max(peak_usage, 1))

        如果 metadata 中没有 usage_count_recent 或 usage_count_peak,
        说明该模式尚未被使用过，返回 0.0。
        """
        if "usage_count_recent" not in metadata and "usage_count_peak" not in metadata:
            return 0.0
        recent_usage = metadata.get("usage_count_recent", 0)
        peak_usage = metadata.get("usage_count_peak", 1)
        if peak_usage <= 0:
            return 0.0
        ratio = recent_usage / max(peak_usage, 1)
        drop = 1.0 - ratio
        return round(max(0.0, min(1.0, drop)), 4)

    def _calc_confidence_loss(self, pattern: Any) -> float:
        """计算置信度损失.

        confidence_loss = 1.0 - confidence
        """
        return round(max(0.0, min(1.0, 1.0 - pattern.confidence)), 4)

    # ── Action Determination ────────────────────────────────────

    def _determine_decay_action(self, decay_score: DecayScore) -> DecayAction:
        """根据衰减评分确定衰减动作.

        | Decay Score | Action            |
        |------------|-------------------|
        | < 0.3      | MAINTAIN          |
        | 0.3 ~ 0.6  | REDUCE_CONFIDENCE |
        | 0.6 ~ 0.8  | MARK_AVOID        |
        | >= 0.8     | ARCHIVE           |
        """
        if decay_score.total < self.MAINTAIN_THRESHOLD:
            return DecayAction.MAINTAIN
        elif decay_score.total < self.REDUCE_CONFIDENCE_THRESHOLD:
            return DecayAction.REDUCE_CONFIDENCE
        elif decay_score.total < self.MARK_AVOID_THRESHOLD:
            return DecayAction.MARK_AVOID
        else:
            return DecayAction.ARCHIVE

    def _determine_dominant_reason(
        self,
        stale_factor: float,
        reward_drop: float,
        usage_drop: float,
        confidence_loss: float,
    ) -> str:
        """确定主导衰减原因."""
        weighted = {
            PatternDecayReason.STALE.value: stale_factor * self.WEIGHT_STALE,
            PatternDecayReason.LOW_REWARD.value: reward_drop * self.WEIGHT_REWARD,
            PatternDecayReason.LOW_USAGE.value: usage_drop * self.WEIGHT_USAGE,
            PatternDecayReason.CONFIDENCE_DECAY.value: confidence_loss * self.WEIGHT_CONFIDENCE,
        }
        return max(weighted, key=weighted.get)

    # ── Decay Application ───────────────────────────────────────

    def _apply_decay(
        self,
        pattern: Any,
        decay_score: DecayScore,
        action: DecayAction,
    ) -> None:
        """应用衰减策略."""
        if action == DecayAction.MAINTAIN:
            return

        if action == DecayAction.REDUCE_CONFIDENCE:
            self._apply_reduce_confidence(pattern, decay_score)
        elif action == DecayAction.MARK_AVOID:
            self._apply_mark_avoid(pattern, decay_score)
        elif action == DecayAction.ARCHIVE:
            self._apply_archive(pattern, decay_score)
        elif action == DecayAction.DELETE:
            self._apply_delete_mark(pattern)

    def _apply_reduce_confidence(self, pattern: Any, decay_score: DecayScore) -> None:
        """降低置信度."""
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用衰减因子
        pattern.confidence = round(
            max(0.05, pattern.confidence * self.REDUCE_CONFIDENCE_FACTOR),
            4,
        )
        pattern.metadata["last_decayed"] = self._now.isoformat()
        pattern.metadata["decay_reason"] = decay_score.reason
        pattern.metadata["decay_score"] = decay_score.total

    def _apply_mark_avoid(self, pattern: Any, decay_score: DecayScore) -> None:
        """标记为应避免模式."""
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用衰减因子
        pattern.confidence = round(
            max(0.05, pattern.confidence * self.MARK_AVOID_CONFIDENCE_FACTOR),
            4,
        )
        # 添加 AVOID 标签
        if "avoid" not in pattern.tags:
            pattern.tags.append("avoid")
        pattern.metadata["last_decayed"] = self._now.isoformat()
        pattern.metadata["decay_reason"] = decay_score.reason
        pattern.metadata["decay_score"] = decay_score.total
        pattern.metadata["marked_avoid"] = True

    def _apply_archive(self, pattern: Any, decay_score: DecayScore) -> None:
        """归档模式."""
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用衰减因子
        pattern.confidence = round(
            max(0.0, pattern.confidence * 0.5),
            4,
        )
        pattern.metadata["lifecycle_state"] = "archived"
        pattern.metadata["last_decayed"] = self._now.isoformat()
        pattern.metadata["decay_reason"] = decay_score.reason
        pattern.metadata["decay_score"] = decay_score.total

    def _apply_delete_mark(self, pattern: Any) -> None:
        """标记为删除 (实际删除由 decay_store 执行)."""
        pattern.metadata["marked_for_delete"] = True
        pattern.metadata["deleted_at"] = self._now.isoformat()

    # ── Utility ─────────────────────────────────────────────────

    def _days_since(self, iso_str: str) -> float | None:
        """计算从 iso_str 到现在的天数."""
        try:
            ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            # 确保 ts 是 offset-aware
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return (self._now - ts).total_seconds() / 86400.0
        except (ValueError, AttributeError, TypeError):
            return None

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取引擎统计."""
        return {
            "decay_count": self._decay_count,
            "total_decayed": self._total_decayed,
            "total_archived": self._total_archived,
            "total_deleted": self._total_deleted,
            "stale_days_threshold": self._stale_days,
            "max_stale_days": self._max_stale_days,
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self._decay_count = 0
        self._total_decayed = 0
        self._total_archived = 0
        self._total_deleted = 0


__all__ = [
    "PatternDecayEngine",
]