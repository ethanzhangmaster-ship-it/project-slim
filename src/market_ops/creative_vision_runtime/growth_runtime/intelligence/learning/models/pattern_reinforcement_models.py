"""E13.7.9 Pattern Reinforcement Models — 模式强化协议.

Day 7.9 Step 3:
  将压缩后的知识 (CompressedKnowledge) 应用于已有模式，
  增强成功模式权重，抑制失败模式。

核心模型:
  1. ReinforcementAction      — 强化动作类型
  2. PatternReinforcementResult — 单模式强化结果
  3. ReinforcementBatchResult   — 批量强化结果

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 桥接 KnowledgeCompressor → PatternStore
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. ReinforcementAction
# ═══════════════════════════════════════════════════════════════


class ReinforcementAction(str, Enum):
    """强化动作类型.

    | 动作      | 含义                          | 触发条件                  |
    |----------|------------------------------|--------------------------|
    | BOOST    | 增强模式权重                    | 正向学习 + 高可靠性         |
    | DECAY    | 衰减模式权重                    | 负向学习 + 表现下降          |
    | MAINTAIN | 保持现状                       | 稳定或边界情况              |
    | SUPPRESS | 抑制模式 (标记为 AVOID)         | 持续失败 + 高置信度          |
    """

    BOOST = "boost"
    DECAY = "decay"
    MAINTAIN = "maintain"
    SUPPRESS = "suppress"


# ═══════════════════════════════════════════════════════════════
# 2. PatternReinforcementResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class PatternReinforcementResult:
    """单模式强化结果 — 一次强化操作对单个模式的影响.

    Attributes:
        result_id: 结果唯一标识
        pattern_id: 目标模式 ID
        knowledge_id: 来源知识 ID
        action: 执行的强化动作
        confidence_before: 强化前置信度
        confidence_after: 强化后置信度
        confidence_delta: 置信度变化
        score_before: 强化前评分
        score_after: 强化后评分
        score_delta: 评分变化
        evidence_count: 新证据数量
        reason: 强化原因
        created_at: 创建时间
        metadata: 扩展元数据
    """

    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: str = ""
    knowledge_id: str = ""
    action: str = ReinforcementAction.MAINTAIN.value
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    confidence_delta: float = 0.0
    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0
    evidence_count: int = 0
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def was_changed(self) -> bool:
        """是否发生了变化."""
        return self.action != ReinforcementAction.MAINTAIN.value

    @property
    def was_boosted(self) -> bool:
        """是否被增强."""
        return self.action == ReinforcementAction.BOOST.value

    @property
    def was_decayed(self) -> bool:
        """是否被衰减."""
        return self.action in (ReinforcementAction.DECAY.value, ReinforcementAction.SUPPRESS.value)

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "pattern_id": self.pattern_id,
            "knowledge_id": self.knowledge_id,
            "action": self.action,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "confidence_delta": self.confidence_delta,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "score_delta": self.score_delta,
            "evidence_count": self.evidence_count,
            "reason": self.reason,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. ReinforcementBatchResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class ReinforcementBatchResult:
    """批量强化结果 — 一次批量强化操作的完整输出.

    Attributes:
        batch_id: 批次唯一标识
        total_processed: 处理总数
        boosted_count: 增强数
        decayed_count: 衰减数
        maintained_count: 保持不变数
        suppressed_count: 抑制数
        total_confidence_gain: 总置信度增益
        avg_confidence_gain: 平均置信度增益
        results: 各模式强化结果
        reinforcement_summary: 强化摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """

    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_processed: int = 0
    boosted_count: int = 0
    decayed_count: int = 0
    maintained_count: int = 0
    suppressed_count: int = 0
    total_confidence_gain: float = 0.0
    avg_confidence_gain: float = 0.0
    results: list[PatternReinforcementResult] = field(default_factory=list)
    reinforcement_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_results(
        cls,
        results: list[PatternReinforcementResult],
    ) -> ReinforcementBatchResult:
        """从强化结果列表创建批量结果."""
        n = len(results)
        boosted = [r for r in results if r.was_boosted]
        decayed = [r for r in results if r.was_decayed]
        maintained = [r for r in results if not r.was_changed]
        suppressed = [r for r in results if r.action == ReinforcementAction.SUPPRESS.value]

        total_gain = round(sum(r.confidence_delta for r in results), 4)
        avg_gain = round(total_gain / n, 4) if n > 0 else 0.0

        summary = cls._build_summary(n, len(boosted), len(decayed), len(maintained), len(suppressed), total_gain, avg_gain)

        return cls(
            total_processed=n,
            boosted_count=len(boosted),
            decayed_count=len(decayed),
            maintained_count=len(maintained),
            suppressed_count=len(suppressed),
            total_confidence_gain=total_gain,
            avg_confidence_gain=avg_gain,
            results=results,
            reinforcement_summary=summary,
        )

    @staticmethod
    def _build_summary(
        total: int,
        boosted: int,
        decayed: int,
        maintained: int,
        suppressed: int,
        total_gain: float,
        avg_gain: float,
    ) -> str:
        """构建强化摘要."""
        lines = [
            "-" * 50,
            f"  Pattern Reinforcement Summary",
            "-" * 50,
            f"  Total processed:      {total:>4d}",
            f"  Boosted:              {boosted:>4d}",
            f"  Decayed:              {decayed:>4d}",
            f"  Suppressed:           {suppressed:>4d}",
            f"  Maintained:           {maintained:>4d}",
            "-" * 50,
            f"  Total confidence gain: {total_gain:+.4f}",
            f"  Avg confidence gain:   {avg_gain:+.4f}",
            "-" * 50,
        ]
        return "\n".join(lines)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        """是否为空."""
        return self.total_processed == 0

    @property
    def has_changes(self) -> bool:
        """是否有变化."""
        return self.boosted_count > 0 or self.decayed_count > 0

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_processed": self.total_processed,
            "boosted_count": self.boosted_count,
            "decayed_count": self.decayed_count,
            "maintained_count": self.maintained_count,
            "suppressed_count": self.suppressed_count,
            "total_confidence_gain": self.total_confidence_gain,
            "avg_confidence_gain": self.avg_confidence_gain,
            "results": [r.to_dict() for r in self.results],
            "reinforcement_summary": self.reinforcement_summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "ReinforcementAction",
    "PatternReinforcementResult",
    "ReinforcementBatchResult",
]