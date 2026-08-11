"""E13.7.9 Knowledge Compressor — 知识压缩引擎.

Day 7.9 Step 2:
  将大量 ConsolidatedExperience 压缩为 CompressedKnowledge，
  再转换为 PatternMemory 存入 PatternStore。

核心职责:
  1. 按维度分组经验
  2. 压缩每组经验为 CompressedKnowledge
  3. 转换为 PatternMemory 存入 PatternStore

流程:
  ConsolidatedExperience[]
      │
      ▼
  _group_by_dimension() → {dimension_key: [ConsolidatedExperience]}
      │
      ▼
  _compress_group() → CompressedKnowledge
      │
      ▼
  _to_pattern_memory() → PatternMemory
      │
      ▼
  PatternStore.store()

连接:
  ExperienceExtractor → KnowledgeCompressor → PatternStore → PatternMiner

设计原则:
  - 纯桥接层，不修改已有模块
  - 支持多维度同时压缩
  - 可配置最少可靠样本数
  - 自动去重 (相同维度键只保留最优)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models.knowledge_compression_models import (
    CompressedKnowledge,
    CompressionDimension,
    CompressionResult,
)
from .models.learning_memory_models import (
    ConsolidatedExperience,
)


class KnowledgeCompressor:
    """知识压缩引擎 — 将经验压缩为可复用模式.

    桥接 Learning System 和 Pattern Store:
      - ConsolidatedExperience (学习经验) → CompressedKnowledge (压缩知识)
      - CompressedKnowledge → PatternMemory (可复用模式)

    用法:
        compressor = KnowledgeCompressor(min_reliable_samples=5)
        result = compressor.compress(experiences)
        # 将可靠知识存入 PatternStore
        for knowledge in result.reliable_knowledge:
            pattern = compressor.to_pattern_memory(knowledge)
            pattern_store.store(pattern)
    """

    def __init__(self, min_reliable_samples: int = 5):
        """初始化压缩器.

        Args:
            min_reliable_samples: 最少可靠样本数
        """
        self._min_reliable_samples = max(1, min_reliable_samples)
        self._compress_count: int = 0
        self._total_experiences_processed: int = 0
        self._total_knowledge_generated: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def min_reliable_samples(self) -> int:
        return self._min_reliable_samples

    @property
    def compress_count(self) -> int:
        """压缩操作次数."""
        return self._compress_count

    @property
    def total_experiences_processed(self) -> int:
        """累计处理经验数."""
        return self._total_experiences_processed

    @property
    def total_knowledge_generated(self) -> int:
        """累计生成知识数."""
        return self._total_knowledge_generated

    # ── Public API ───────────────────────────────────────────────

    def compress(
        self,
        experiences: list[Any],  # ConsolidatedExperience
        dimensions: list[CompressionDimension] | None = None,
    ) -> CompressionResult:
        """压缩经验为知识 — 主入口.

        Args:
            experiences: ConsolidatedExperience 列表
            dimensions: 压缩维度列表 (默认使用 ACTION_FEEDBACK 和 CATEGORY_FEEDBACK)

        Returns:
            CompressionResult: 压缩结果
        """
        self._compress_count += 1

        if not experiences:
            self._total_experiences_processed += 0
            return CompressionResult()

        if dimensions is None:
            dimensions = [
                CompressionDimension.ACTION_FEEDBACK,
                CompressionDimension.CATEGORY_FEEDBACK,
            ]

        self._total_experiences_processed += len(experiences)

        all_knowledge: list[CompressedKnowledge] = []
        for dim in dimensions:
            # 分组
            groups = self._group_by_dimension(experiences, dim)
            # 压缩每组
            for key, group in groups.items():
                if len(group) >= 1:  # 至少1条经验即可压缩
                    knowledge = CompressedKnowledge.from_experiences(
                        experiences=group,
                        dimension=dim,
                        dimension_key=key,
                        min_reliable_samples=self._min_reliable_samples,
                    )
                    all_knowledge.append(knowledge)

        # 去重 (相同 dimension_key 保留可靠性最高的)
        all_knowledge = self._deduplicate(all_knowledge)

        self._total_knowledge_generated += len(all_knowledge)

        return CompressionResult.from_knowledge_units(
            knowledge_units=all_knowledge,
            total_experiences=len(experiences),
            dimensions_used=[d.value for d in dimensions],
        )

    def compress_single_dimension(
        self,
        experiences: list[Any],
        dimension: CompressionDimension,
    ) -> CompressionResult:
        """单维度压缩."""
        return self.compress(experiences, dimensions=[dimension])

    def compress_and_store(
        self,
        experiences: list[Any],
        pattern_store: Any,  # PatternStore
        dimensions: list[CompressionDimension] | None = None,
    ) -> CompressionResult:
        """压缩并存入 PatternStore.

        Args:
            experiences: ConsolidatedExperience 列表
            pattern_store: PatternStore 实例
            dimensions: 压缩维度

        Returns:
            CompressionResult: 压缩结果
        """
        result = self.compress(experiences, dimensions)

        for knowledge in result.reliable_knowledge:
            pattern = self.to_pattern_memory(knowledge)
            pattern_store.store(pattern)

        return result

    def compress_from_extraction(
        self,
        extraction_result: Any,  # ExtractionResult
        dimensions: list[CompressionDimension] | None = None,
    ) -> CompressionResult:
        """从 ExtractionResult 直接压缩."""
        experiences = extraction_result.experiences if hasattr(extraction_result, "experiences") else []
        return self.compress(experiences, dimensions)

    # ── Memory System Bridge ────────────────────────────────────

    def to_pattern_memory(
        self,
        knowledge: CompressedKnowledge,
    ) -> Any:
        """将 CompressedKnowledge 转换为 PatternMemory.

        Args:
            knowledge: CompressedKnowledge 实例

        Returns:
            PatternMemory: 可直接存入 PatternStore 的模式
        """
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternAction,
            PatternCondition,
            PatternMemory,
            PatternMiningDimension,
            PatternPerformance,
            PatternQuality,
        )

        # 构建 PatternCondition
        condition = PatternCondition(
            opportunity_type=knowledge.dimension_key,
            action_type=knowledge.action_type,
            category=knowledge.category,
            signal_types=[knowledge.dominant_feedback] if knowledge.dominant_feedback else [],
        )

        # 构建 PatternAction
        action = PatternAction(
            action_type=knowledge.action_type,
            expected_impact=knowledge.recommended_action,
            approval_level="auto" if knowledge.is_reliable else "manual",
        )

        # 构建 PatternPerformance
        quality = self._map_quality(knowledge)
        performance = PatternPerformance(
            samples=knowledge.experience_count,
            success_count=int(knowledge.success_rate * knowledge.experience_count),
            success_rate=knowledge.success_rate,
            avg_reward=knowledge.avg_reward,
            avg_confidence=knowledge.avg_confidence,
            quality=quality,
            trend=[knowledge.avg_learning_gain],
        )

        # 构建 PatternMemory
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=condition,
            action=action,
            performance=performance,
            source_experience_ids=knowledge.source_experience_ids,
            tags=self._generate_pattern_tags(knowledge),
            confidence=knowledge.reliability_score,
            metadata={
                "compression_dimension": knowledge.dimension,
                "compression_dimension_key": knowledge.dimension_key,
                "avg_learning_gain": knowledge.avg_learning_gain,
                "avg_significance": knowledge.avg_significance,
                "key_insights": knowledge.key_insights,
                "compressed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        pattern.compute_score()
        # restore confidence after compute_score overwrites it
        pattern.confidence = knowledge.reliability_score
        return pattern

    def to_pattern_memories(
        self,
        knowledge_units: list[CompressedKnowledge],
    ) -> list[Any]:
        """批量转换."""
        return [self.to_pattern_memory(k) for k in knowledge_units]

    # ── Grouping ────────────────────────────────────────────────

    def _group_by_dimension(
        self,
        experiences: list[Any],
        dimension: CompressionDimension,
    ) -> dict[str, list[Any]]:
        """按维度对经验分组."""
        groups: dict[str, list[Any]] = defaultdict(list)

        for exp in experiences:
            key = self._dimension_key(exp, dimension)
            if key:
                groups[key].append(exp)

        return dict(groups)

    @staticmethod
    def _dimension_key(exp: Any, dimension: CompressionDimension) -> str:
        """计算维度分组键."""
        if dimension == CompressionDimension.ACTION_TYPE:
            return getattr(exp, "action_type", "") or "unknown"
        elif dimension == CompressionDimension.CATEGORY:
            return getattr(exp, "category", "") or "creative"
        elif dimension == CompressionDimension.FEEDBACK_CLASSIFICATION:
            return getattr(exp, "feedback_classification", "") or "unknown"
        elif dimension == CompressionDimension.ACTION_CATEGORY:
            action = getattr(exp, "action_type", "") or "unknown"
            category = getattr(exp, "category", "") or "creative"
            return f"{action}|{category}"
        elif dimension == CompressionDimension.ACTION_FEEDBACK:
            action = getattr(exp, "action_type", "") or "unknown"
            feedback = getattr(exp, "feedback_classification", "") or "unknown"
            return f"{action}|{feedback}"
        elif dimension == CompressionDimension.CATEGORY_FEEDBACK:
            category = getattr(exp, "category", "") or "creative"
            feedback = getattr(exp, "feedback_classification", "") or "unknown"
            return f"{category}|{feedback}"
        elif dimension == CompressionDimension.FULL_CONTEXT:
            action = getattr(exp, "action_type", "") or "unknown"
            category = getattr(exp, "category", "") or "creative"
            feedback = getattr(exp, "feedback_classification", "") or "unknown"
            return f"{action}|{category}|{feedback}"
        return "unknown"

    # ── Helpers ─────────────────────────────────────────────────

    def _deduplicate(
        self,
        knowledge_units: list[CompressedKnowledge],
    ) -> list[CompressedKnowledge]:
        """去重: 相同 dimension_key 保留可靠性最高的."""
        seen: dict[str, CompressedKnowledge] = {}
        for k in knowledge_units:
            if k.dimension_key not in seen or k.reliability_score > seen[k.dimension_key].reliability_score:
                seen[k.dimension_key] = k
        return list(seen.values())

    @staticmethod
    def _map_quality(knowledge: CompressedKnowledge) -> Any:
        """将 CompressedKnowledge 映射到 PatternQuality."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import PatternQuality

        if knowledge.experience_count >= 30 and knowledge.success_rate >= 0.7:
            return PatternQuality.STRONG
        elif knowledge.experience_count >= 10 and knowledge.success_rate >= 0.6:
            return PatternQuality.RELIABLE
        elif knowledge.experience_count >= 3 and knowledge.success_rate >= 0.5:
            return PatternQuality.EMERGING
        elif knowledge.experience_count >= 3 and (1.0 - knowledge.success_rate) >= 0.7:
            return PatternQuality.AVOID
        return PatternQuality.WEAK

    @staticmethod
    def _generate_pattern_tags(knowledge: CompressedKnowledge) -> list[str]:
        """生成模式标签."""
        tags: list[str] = []
        if knowledge.is_positive:
            tags.append("positive")
        else:
            tags.append("negative")
        if knowledge.is_reliable:
            tags.append("reliable")
        if knowledge.is_actionable:
            tags.append("actionable")
        if knowledge.dominant_feedback:
            tags.append(knowledge.dominant_feedback.lower())
        if knowledge.category:
            tags.append(knowledge.category)
        return tags

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取压缩器统计."""
        return {
            "compress_count": self._compress_count,
            "total_experiences_processed": self._total_experiences_processed,
            "total_knowledge_generated": self._total_knowledge_generated,
            "min_reliable_samples": self._min_reliable_samples,
            "avg_compression_ratio": round(
                self._total_experiences_processed / max(self._total_knowledge_generated, 1), 2,
            ),
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self._compress_count = 0
        self._total_experiences_processed = 0
        self._total_knowledge_generated = 0


__all__ = [
    "KnowledgeCompressor",
]