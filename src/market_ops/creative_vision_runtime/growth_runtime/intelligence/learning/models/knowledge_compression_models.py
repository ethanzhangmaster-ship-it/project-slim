"""E13.7.9 Knowledge Compression Models — 知识压缩协议.

Day 7.9 Step 2:
  将大量 ConsolidatedExperience 压缩为 PatternMemory，
  实现从「原始经验」到「可复用模式」的智能压缩。

核心模型:
  1. CompressionDimension  — 压缩维度 (如何分组)
  2. CompressedKnowledge   — 压缩后的知识单元
  3. CompressionResult     — 压缩操作结果

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 可序列化 (to_dict)，支持审计
  - 桥接 ConsolidatedExperience → PatternMemory
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. CompressionDimension
# ═══════════════════════════════════════════════════════════════


class CompressionDimension(str, Enum):
    """压缩维度 — 如何对经验进行分组压缩.

    | 维度                    | 分组键                          | 适用场景                |
    |------------------------|-------------------------------|----------------------|
    | ACTION_TYPE            | action_type                   | 按动作类型总结模式      |
    | CATEGORY               | category                      | 按类别 (创意/UA/收入)   |
    | FEEDBACK_CLASSIFICATION| feedback_classification       | 按反馈类型总结          |
    | ACTION_CATEGORY        | action_type + category        | 精确到动作×类别         |
    | ACTION_FEEDBACK        | action_type + feedback_class  | 动作×反馈效果           |
    | CATEGORY_FEEDBACK      | category + feedback_class     | 类别×反馈效果           |
    | FULL_CONTEXT           | action + category + feedback  | 全上下文精确压缩        |
    """

    ACTION_TYPE = "action_type"
    CATEGORY = "category"
    FEEDBACK_CLASSIFICATION = "feedback_classification"
    ACTION_CATEGORY = "action_category"
    ACTION_FEEDBACK = "action_feedback"
    CATEGORY_FEEDBACK = "category_feedback"
    FULL_CONTEXT = "full_context"


# ═══════════════════════════════════════════════════════════════
# 2. CompressedKnowledge
# ═══════════════════════════════════════════════════════════════


@dataclass
class CompressedKnowledge:
    """压缩后的知识单元 — 一组相似经验的压缩表示.

    这是 ConsolidatedExperience → PatternMemory 的中间表示。
    每个 CompressedKnowledge 可被转换为 PatternMemory 存入 PatternStore。

    Attributes:
        knowledge_id: 知识单元唯一标识
        dimension: 压缩维度
        dimension_key: 维度分组键
        source_experience_ids: 来源经验 ID 列表
        experience_count: 来源经验数
        action_type: 主导动作类型
        category: 主导类别
        avg_reward: 平均奖励
        avg_confidence: 平均置信度
        avg_learning_gain: 平均学习增益
        avg_significance: 平均显著性
        success_rate: 成功率
        dominant_feedback: 主导反馈分类
        key_insights: 关键洞察
        recommended_action: 推荐动作
        is_reliable: 是否可靠 (足够样本)
        reliability_score: 可靠性评分 [0, 1]
        created_at: 创建时间
        metadata: 扩展元数据
    """

    knowledge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dimension: str = CompressionDimension.ACTION_TYPE.value
    dimension_key: str = ""
    source_experience_ids: list[str] = field(default_factory=list)
    experience_count: int = 0

    # ── 聚合统计 ──
    action_type: str = ""
    category: str = "creative"
    avg_reward: float = 0.0
    avg_confidence: float = 0.0
    avg_learning_gain: float = 0.0
    avg_significance: float = 0.0
    success_rate: float = 0.0

    # ── 洞察 ──
    dominant_feedback: str = ""
    key_insights: list[str] = field(default_factory=list)
    recommended_action: str = ""

    # ── 可靠性 ──
    is_reliable: bool = False
    reliability_score: float = 0.0

    # ── 元数据 ──
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_positive(self) -> bool:
        """是否正向知识."""
        return self.avg_learning_gain > 0

    @property
    def has_high_confidence(self) -> bool:
        """是否高置信."""
        return self.avg_confidence >= 0.7

    @property
    def is_actionable(self) -> bool:
        """是否可执行."""
        return self.is_reliable and self.recommended_action != ""

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_experiences(
        cls,
        experiences: list[Any],  # ConsolidatedExperience
        dimension: CompressionDimension,
        dimension_key: str,
        min_reliable_samples: int = 5,
    ) -> CompressedKnowledge:
        """从一组经验创建压缩知识.

        Args:
            experiences: ConsolidatedExperience 列表
            dimension: 压缩维度
            dimension_key: 维度分组键
            min_reliable_samples: 最少可靠样本数

        Returns:
            CompressedKnowledge: 压缩知识
        """
        n = len(experiences)
        if n == 0:
            return cls(dimension=dimension.value, dimension_key=dimension_key)

        # 聚合统计
        avg_reward = round(sum(e.reward for e in experiences) / n, 4)
        avg_confidence = round(sum(e.confidence for e in experiences) / n, 4)
        avg_learning_gain = round(sum(e.learning_gain for e in experiences) / n, 4)
        avg_significance = round(sum(e.significance_score for e in experiences) / n, 4)
        success_count = sum(1 for e in experiences if e.success)
        success_rate = round(success_count / n, 4)

        # 主导动作类型
        action_counts: dict[str, int] = {}
        for e in experiences:
            if e.action_type:
                action_counts[e.action_type] = action_counts.get(e.action_type, 0) + 1
        dominant_action = max(action_counts, key=action_counts.get) if action_counts else ""

        # 主导类别
        cat_counts: dict[str, int] = {}
        for e in experiences:
            cat_counts[e.category] = cat_counts.get(e.category, 0) + 1
        dominant_category = max(cat_counts, key=cat_counts.get) if cat_counts else "creative"

        # 主导反馈
        fb_counts: dict[str, int] = {}
        for e in experiences:
            if e.feedback_classification:
                fb_counts[e.feedback_classification] = fb_counts.get(e.feedback_classification, 0) + 1
        dominant_feedback = max(fb_counts, key=fb_counts.get) if fb_counts else ""

        # 关键洞察
        insights = cls._generate_insights(experiences, avg_learning_gain, success_rate)

        # 推荐动作
        recommended = cls._infer_recommendation(dominant_action, avg_learning_gain, success_rate)

        # 可靠性
        reliability = cls._compute_reliability(n, avg_significance, success_rate)
        is_reliable = n >= min_reliable_samples and reliability >= 0.5

        return cls(
            dimension=dimension.value,
            dimension_key=dimension_key,
            source_experience_ids=[e.experience_id for e in experiences],
            experience_count=n,
            action_type=dominant_action,
            category=dominant_category,
            avg_reward=avg_reward,
            avg_confidence=avg_confidence,
            avg_learning_gain=avg_learning_gain,
            avg_significance=avg_significance,
            success_rate=success_rate,
            dominant_feedback=dominant_feedback,
            key_insights=insights,
            recommended_action=recommended,
            is_reliable=is_reliable,
            reliability_score=reliability,
        )

    @staticmethod
    def _generate_insights(
        experiences: list[Any],
        avg_learning_gain: float,
        success_rate: float,
    ) -> list[str]:
        """从经验中生成关键洞察."""
        insights: list[str] = []
        n = len(experiences)

        if avg_learning_gain > 0.1:
            insights.append(f"Strong positive learning: avg gain {avg_learning_gain:+.3f}")
        elif avg_learning_gain > 0:
            insights.append(f"Moderate positive learning: avg gain {avg_learning_gain:+.3f}")
        elif avg_learning_gain < -0.1:
            insights.append(f"Negative learning: avg gain {avg_learning_gain:+.3f}")
        else:
            insights.append(f"Stagnant learning: avg gain {avg_learning_gain:+.3f}")

        if success_rate >= 0.8:
            insights.append(f"High success rate: {success_rate:.0%} ({n} samples)")
        elif success_rate < 0.4:
            insights.append(f"Low success rate: {success_rate:.0%} ({n} samples)")

        # 调整洞察
        adjusted_count = sum(1 for e in experiences if hasattr(e, "has_adjustments") and e.has_adjustments)
        if adjusted_count > n * 0.5:
            insights.append(f"Frequently adjusted: {adjusted_count}/{n} experiences had policy adjustments")

        return insights

    @staticmethod
    def _infer_recommendation(
        action_type: str,
        avg_learning_gain: float,
        success_rate: float,
    ) -> str:
        """推断推荐动作."""
        if avg_learning_gain > 0.1 and success_rate >= 0.7:
            return f"amplify_{action_type}" if action_type else "amplify"
        elif avg_learning_gain > 0:
            return f"maintain_{action_type}" if action_type else "maintain"
        elif avg_learning_gain < -0.1:
            return f"suppress_{action_type}" if action_type else "suppress"
        else:
            return "investigate"

    @staticmethod
    def _compute_reliability(
        sample_count: int,
        avg_significance: float,
        success_rate: float,
    ) -> float:
        """计算可靠性评分.

        可靠性 = min(samples/10, 1.0) × 0.4 + significance × 0.3 + success_rate × 0.3
        """
        sample_factor = min(sample_count / 10.0, 1.0)
        return round(
            sample_factor * 0.4 + avg_significance * 0.3 + success_rate * 0.3,
            4,
        )

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "dimension": self.dimension,
            "dimension_key": self.dimension_key,
            "source_experience_ids": self.source_experience_ids,
            "experience_count": self.experience_count,
            "action_type": self.action_type,
            "category": self.category,
            "avg_reward": self.avg_reward,
            "avg_confidence": self.avg_confidence,
            "avg_learning_gain": self.avg_learning_gain,
            "avg_significance": self.avg_significance,
            "success_rate": self.success_rate,
            "dominant_feedback": self.dominant_feedback,
            "key_insights": self.key_insights,
            "recommended_action": self.recommended_action,
            "is_reliable": self.is_reliable,
            "reliability_score": self.reliability_score,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. CompressionResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class CompressionResult:
    """知识压缩结果 — 一次压缩操作的完整输出.

    Attributes:
        compression_id: 压缩操作唯一标识
        dimensions_used: 使用的压缩维度
        total_experiences: 输入经验总数
        knowledge_units: 压缩后的知识单元列表
        total_compressed: 压缩产生的知识单元数
        reliable_count: 可靠知识单元数
        actionable_count: 可执行知识单元数
        compression_ratio: 压缩比 (输入/输出)
        compression_summary: 压缩摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """

    compression_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dimensions_used: list[str] = field(default_factory=list)
    total_experiences: int = 0
    knowledge_units: list[CompressedKnowledge] = field(default_factory=list)
    total_compressed: int = 0
    reliable_count: int = 0
    actionable_count: int = 0
    compression_ratio: float = 0.0
    compression_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_knowledge_units(
        cls,
        knowledge_units: list[CompressedKnowledge],
        total_experiences: int = 0,
        dimensions_used: list[str] | None = None,
    ) -> CompressionResult:
        """从知识单元列表创建压缩结果."""
        n = len(knowledge_units)
        reliable = [k for k in knowledge_units if k.is_reliable]
        actionable = [k for k in knowledge_units if k.is_actionable]

        ratio = round(total_experiences / max(n, 1), 2)

        summary = cls._build_summary(
            total_experiences, n, len(reliable), len(actionable), ratio, knowledge_units,
        )

        return cls(
            dimensions_used=dimensions_used or [],
            total_experiences=total_experiences,
            knowledge_units=knowledge_units,
            total_compressed=n,
            reliable_count=len(reliable),
            actionable_count=len(actionable),
            compression_ratio=ratio,
            compression_summary=summary,
        )

    @staticmethod
    def _build_summary(
        total_experiences: int,
        total_compressed: int,
        reliable_count: int,
        actionable_count: int,
        ratio: float,
        knowledge_units: list[CompressedKnowledge],
    ) -> str:
        """构建压缩摘要."""
        lines = [
            "-" * 50,
            f"  Knowledge Compression Summary",
            "-" * 50,
            f"  Input experiences:    {total_experiences:>4d}",
            f"  Compressed units:     {total_compressed:>4d}",
            f"  Compression ratio:    {ratio:>7.2f}:1",
            f"  Reliable units:       {reliable_count:>4d}",
            f"  Actionable units:     {actionable_count:>4d}",
            "-" * 50,
        ]

        # 正向/负向分布
        positive = [k for k in knowledge_units if k.is_positive]
        negative = [k for k in knowledge_units if not k.is_positive]
        lines.append(f"  Positive knowledge:   {len(positive):>4d}")
        lines.append(f"  Negative knowledge:   {len(negative):>4d}")

        # Top insights
        if knowledge_units:
            lines.append(f"  Top Knowledge Units:")
            for k in sorted(knowledge_units, key=lambda x: -x.reliability_score)[:5]:
                lines.append(
                    f"    [{k.dimension_key}] {k.action_type}: "
                    f"gain={k.avg_learning_gain:+.3f}, "
                    f"reliability={k.reliability_score:.2f}"
                )

        lines.append("-" * 50)
        return "\n".join(lines)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        """是否为空压缩."""
        return self.total_compressed == 0

    @property
    def has_reliable(self) -> bool:
        """是否有可靠知识."""
        return self.reliable_count > 0

    @property
    def reliable_knowledge(self) -> list[CompressedKnowledge]:
        """获取可靠知识列表."""
        return [k for k in self.knowledge_units if k.is_reliable]

    @property
    def actionable_knowledge(self) -> list[CompressedKnowledge]:
        """获取可执行知识列表."""
        return [k for k in self.knowledge_units if k.is_actionable]

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "compression_id": self.compression_id,
            "dimensions_used": self.dimensions_used,
            "total_experiences": self.total_experiences,
            "total_compressed": self.total_compressed,
            "reliable_count": self.reliable_count,
            "actionable_count": self.actionable_count,
            "compression_ratio": self.compression_ratio,
            "compression_summary": self.compression_summary,
            "knowledge_units": [k.to_dict() for k in self.knowledge_units],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "CompressionDimension",
    "CompressedKnowledge",
    "CompressionResult",
]