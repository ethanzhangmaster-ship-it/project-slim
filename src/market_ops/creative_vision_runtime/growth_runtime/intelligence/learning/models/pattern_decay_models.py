"""E13.7.9 Pattern Decay Models — 模式衰减协议.

Day 7.9 Step 4:
  对 PatternStore 中的模式进行衰减评估，
  识别过期、低效、未使用的模式并执行相应衰减策略。

核心模型:
  1. PatternDecayReason      — 衰减原因枚举
  2. DecayAction             — 衰减动作枚举
  3. DecayScore              — 衰减评分 (多维度组合)
  4. PatternDecayResult      — 单模式衰减结果
  5. DecayBatchResult        — 批量衰减结果

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 与 PatternLifecycleManager 互补 (评分层 vs 状态机层)
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. PatternDecayReason
# ═══════════════════════════════════════════════════════════════


class PatternDecayReason(str, Enum):
    """衰减原因枚举.

    | 原因                 | 含义                           | 典型触发条件                 |
    |---------------------|-------------------------------|---------------------------|
    | STALE               | 长期未使用                       | last_seen > 30 days        |
    | LOW_REWARD          | 奖励持续下降                     | avg_reward 下降 > 50%       |
    | LOW_USAGE           | 使用频率显著下降                  | usage_count 下降 > 80%      |
    | PERFORMANCE_DROP    | 成功率持续下降                    | success_rate 下降 > 30%     |
    | CONFIDENCE_DECAY    | 置信度自然衰减                    | confidence 降至阈值以下       |
    | LOW_SAMPLES         | 样本量不足                       | samples < min_samples       |
    | QUALITY_DEGRADATION | 模式质量从 STRONG 降级            | quality 连续下降             |
    """
    STALE = "stale"
    LOW_REWARD = "low_reward"
    LOW_USAGE = "low_usage"
    PERFORMANCE_DROP = "performance_drop"
    CONFIDENCE_DECAY = "confidence_decay"
    LOW_SAMPLES = "low_samples"
    QUALITY_DEGRADATION = "quality_degradation"


# ═══════════════════════════════════════════════════════════════
# 2. DecayAction
# ═══════════════════════════════════════════════════════════════


class DecayAction(str, Enum):
    """衰减动作枚举.

    | 动作                | 含义                          | 效果                         |
    |--------------------|------------------------------|-----------------------------|
    | MAINTAIN           | 保持现状                       | 不修改                        |
    | REDUCE_CONFIDENCE  | 降低置信度                     | confidence *= 0.85            |
    | MARK_AVOID         | 标记为应避免模式                | 添加 AVOID 标签，confidence 降低 |
    | ARCHIVE            | 归档 (不参与决策)               | 触发 LifecycleManager 迁移     |
    | DELETE             | 从 PatternStore 删除           | 永久移除                       |
    """
    MAINTAIN = "maintain"
    REDUCE_CONFIDENCE = "reduce_confidence"
    MARK_AVOID = "mark_avoid"
    ARCHIVE = "archive"
    DELETE = "delete"


# ═══════════════════════════════════════════════════════════════
# 3. DecayScore
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecayScore:
    """衰减评分 — 多维度衰减评估.

    综合公式:
      decay_score = stale_factor × 0.35 + reward_drop × 0.30
                  + usage_drop × 0.20 + confidence_loss × 0.15

    Attributes:
        total: 综合衰减评分 [0, 1]
        stale_factor: 过期因子 [0, 1]
        reward_drop: 奖励下降 [0, 1]
        usage_drop: 使用下降 [0, 1]
        confidence_loss: 置信度损失 [0, 1]
        factors: 各因子分解
        reason: 主导衰减原因
        created_at: 计算时间
        metadata: 扩展元数据
    """

    total: float = 0.0
    stale_factor: float = 0.0
    reward_drop: float = 0.0
    usage_drop: float = 0.0
    confidence_loss: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    reason: str = PatternDecayReason.STALE.value
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_significant(self) -> bool:
        """是否显著衰减."""
        return self.total >= 0.3

    @property
    def is_severe(self) -> bool:
        """是否严重衰减."""
        return self.total >= 0.6

    @property
    def is_critical(self) -> bool:
        """是否需要归档/删除."""
        return self.total >= 0.8

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "stale_factor": self.stale_factor,
            "reward_drop": self.reward_drop,
            "usage_drop": self.usage_drop,
            "confidence_loss": self.confidence_loss,
            "factors": self.factors,
            "reason": self.reason,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 4. PatternDecayResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternDecayResult:
    """单模式衰减结果 — 一次衰减操作对单个模式的影响.

    Attributes:
        result_id: 结果唯一标识
        pattern_id: 目标模式 ID
        reason: 衰减原因
        action: 执行的衰减动作
        decay_score: 衰减评分
        confidence_before: 衰减前置信度
        confidence_after: 衰减后置信度
        confidence_delta: 置信度变化
        score_before: 衰减前评分
        score_after: 衰减后评分
        score_delta: 评分变化
        lifecycle_from: 衰减前生命周期状态
        lifecycle_to: 衰减后生命周期状态
        changed: 是否发生变化
        created_at: 创建时间
        metadata: 扩展元数据
    """

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    reason: str = PatternDecayReason.STALE.value
    action: str = DecayAction.MAINTAIN.value
    decay_score: DecayScore = field(default_factory=DecayScore)
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    confidence_delta: float = 0.0
    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0
    lifecycle_from: str = ""
    lifecycle_to: str = ""
    changed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def was_maintained(self) -> bool:
        """是否保持."""
        return self.action == DecayAction.MAINTAIN.value

    @property
    def was_deleted(self) -> bool:
        """是否被删除."""
        return self.action == DecayAction.DELETE.value

    @property
    def was_archived(self) -> bool:
        """是否被归档."""
        return self.action == DecayAction.ARCHIVE.value

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "pattern_id": self.pattern_id,
            "reason": self.reason,
            "action": self.action,
            "decay_score": self.decay_score.to_dict(),
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "confidence_delta": self.confidence_delta,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "score_delta": self.score_delta,
            "lifecycle_from": self.lifecycle_from,
            "lifecycle_to": self.lifecycle_to,
            "changed": self.changed,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 5. DecayBatchResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecayBatchResult:
    """批量衰减结果 — 一次批量衰减操作的完整输出.

    Attributes:
        batch_id: 批次唯一标识
        total_patterns: 检查的模式总数
        decayed_patterns: 执行衰减的模式数
        archived_patterns: 归档的模式数
        deleted_patterns: 删除的模式数
        maintained_patterns: 保持的模式数
        total_confidence_loss: 总置信度损失
        avg_confidence_loss: 平均置信度损失
        results: 各模式衰减结果
        decay_summary: 衰减摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """

    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_patterns: int = 0
    decayed_patterns: int = 0
    archived_patterns: int = 0
    deleted_patterns: int = 0
    maintained_patterns: int = 0
    total_confidence_loss: float = 0.0
    avg_confidence_loss: float = 0.0
    results: list[PatternDecayResult] = field(default_factory=list)
    decay_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_results(
        cls,
        results: list[PatternDecayResult],
    ) -> DecayBatchResult:
        """从衰减结果列表创建批量结果."""
        n = len(results)
        decayed = [r for r in results if r.changed and r.action == DecayAction.REDUCE_CONFIDENCE.value]
        archived = [r for r in results if r.action == DecayAction.ARCHIVE.value]
        deleted = [r for r in results if r.action == DecayAction.DELETE.value]
        maintained = [r for r in results if not r.changed]

        total_loss = round(sum(r.confidence_delta for r in results), 4)
        avg_loss = round(total_loss / n, 4) if n > 0 else 0.0

        summary = cls._build_summary(n, len(decayed), len(archived), len(deleted), len(maintained), total_loss, avg_loss)

        return cls(
            total_patterns=n,
            decayed_patterns=len(decayed),
            archived_patterns=len(archived),
            deleted_patterns=len(deleted),
            maintained_patterns=len(maintained),
            total_confidence_loss=total_loss,
            avg_confidence_loss=avg_loss,
            results=results,
            decay_summary=summary,
        )

    @staticmethod
    def _build_summary(
        total: int,
        decayed: int,
        archived: int,
        deleted: int,
        maintained: int,
        total_loss: float,
        avg_loss: float,
    ) -> str:
        """构建衰减摘要."""
        lines = [
            "-" * 50,
            f"  Pattern Decay Summary",
            "-" * 50,
            f"  Total patterns:      {total:>4d}",
            f"  Decayed:             {decayed:>4d}",
            f"  Archived:            {archived:>4d}",
            f"  Deleted:             {deleted:>4d}",
            f"  Maintained:          {maintained:>4d}",
            "-" * 50,
            f"  Total confidence loss: {total_loss:+.4f}",
            f"  Avg confidence loss:   {avg_loss:+.4f}",
            "-" * 50,
        ]
        return "\n".join(lines)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        """是否为空."""
        return self.total_patterns == 0

    @property
    def has_changes(self) -> bool:
        """是否有变化."""
        return self.decayed_patterns > 0 or self.archived_patterns > 0 or self.deleted_patterns > 0

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_patterns": self.total_patterns,
            "decayed_patterns": self.decayed_patterns,
            "archived_patterns": self.archived_patterns,
            "deleted_patterns": self.deleted_patterns,
            "maintained_patterns": self.maintained_patterns,
            "total_confidence_loss": self.total_confidence_loss,
            "avg_confidence_loss": self.avg_confidence_loss,
            "results": [r.to_dict() for r in self.results],
            "decay_summary": self.decay_summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "PatternDecayReason",
    "DecayAction",
    "DecayScore",
    "PatternDecayResult",
    "DecayBatchResult",
]