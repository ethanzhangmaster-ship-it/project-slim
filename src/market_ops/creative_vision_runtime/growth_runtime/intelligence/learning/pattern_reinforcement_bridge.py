"""E13.7.9 Pattern Reinforcement Bridge — 模式强化桥接器.

Day 7.9 Step 3:
  将 KnowledgeCompressor 的输出 (CompressedKnowledge) 应用于 PatternStore，
  增强成功模式权重，衰减失败模式。

核心职责:
  1. 接收 CompressionResult (来自 KnowledgeCompressor)
  2. 对每个可靠知识单元，查找或创建 PatternMemory
  3. 应用强化策略 (BOOST/DECAY/SUPPRESS/MAINTAIN)
  4. 更新 PatternStore 中的模式

流程:
  CompressionResult
      │
      ▼
  for each CompressedKnowledge:
      │
      ├─→ _find_or_create_pattern() → PatternMemory
      ├─→ _determine_action() → ReinforcementAction
      ├─→ _apply_reinforcement() → PatternReinforcementResult
      └─→ PatternStore.store()
      │
      ▼
  ReinforcementBatchResult

连接:
  KnowledgeCompressor → PatternReinforcementBridge → PatternStore

设计原则:
  - 桥接 KnowledgeCompressor 输出与 PatternStore
  - 复用现有 PatternReinforcer 的贝叶斯更新
  - 不修改已有模块
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models.knowledge_compression_models import (
    CompressedKnowledge,
    CompressionResult,
)
from .models.pattern_reinforcement_models import (
    PatternReinforcementResult,
    ReinforcementAction,
    ReinforcementBatchResult,
)


class PatternReinforcementBridge:
    """模式强化桥接器 — 将压缩知识应用于模式存储.

    桥接 KnowledgeCompressor 和 PatternStore:
      - CompressedKnowledge → PatternMemory (via PatternStore)
      - 根据知识质量决定强化策略

    用法:
        bridge = PatternReinforcementBridge()
        # 从 CompressionResult 强化
        batch_result = bridge.reinforce(compression_result, pattern_store)
        # 或者直接强化单个知识
        result = bridge.reinforce_single(knowledge, pattern_store)
    """

    # 强化阈值
    BOOST_LEARNING_GAIN_THRESHOLD = 0.05     # 学习增益 > 此值 → BOOST
    DECAY_LEARNING_GAIN_THRESHOLD = -0.05    # 学习增益 < 此值 → DECAY
    SUPPRESS_SUCCESS_RATE_THRESHOLD = 0.3    # 成功率 < 此值 + 负增益 → SUPPRESS
    BOOST_SUCCESS_RATE_THRESHOLD = 0.7       # 成功率 > 此值 + 正增益 → BOOST

    # 置信度调整量
    BOOST_CONFIDENCE_DELTA = 0.10
    DECAY_CONFIDENCE_DELTA = -0.08
    SUPPRESS_CONFIDENCE_DELTA = -0.15

    def __init__(
        self,
        boost_threshold: float = BOOST_LEARNING_GAIN_THRESHOLD,
        decay_threshold: float = DECAY_LEARNING_GAIN_THRESHOLD,
        suppress_rate: float = SUPPRESS_SUCCESS_RATE_THRESHOLD,
        boost_rate: float = BOOST_SUCCESS_RATE_THRESHOLD,
    ):
        self._boost_threshold = boost_threshold
        self._decay_threshold = decay_threshold
        self._suppress_rate = suppress_rate
        self._boost_rate = boost_rate
        self._reinforce_count: int = 0
        self._total_boosted: int = 0
        self._total_decayed: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def reinforce_count(self) -> int:
        return self._reinforce_count

    @property
    def total_boosted(self) -> int:
        return self._total_boosted

    @property
    def total_decayed(self) -> int:
        return self._total_decayed

    # ── Public API ───────────────────────────────────────────────

    def reinforce(
        self,
        compression_result: CompressionResult,
        pattern_store: Any,  # PatternStore
    ) -> ReinforcementBatchResult:
        """从压缩结果批量强化模式 — 主入口.

        Args:
            compression_result: CompressionResult 实例
            pattern_store: PatternStore 实例

        Returns:
            ReinforcementBatchResult: 批量强化结果
        """
        self._reinforce_count += 1

        results: list[PatternReinforcementResult] = []
        for knowledge in compression_result.reliable_knowledge:
            result = self.reinforce_single(knowledge, pattern_store)
            results.append(result)

        return ReinforcementBatchResult.from_results(results)

    def reinforce_single(
        self,
        knowledge: CompressedKnowledge,
        pattern_store: Any,  # PatternStore
    ) -> PatternReinforcementResult:
        """强化单个知识单元.

        Args:
            knowledge: CompressedKnowledge 实例
            pattern_store: PatternStore 实例

        Returns:
            PatternReinforcementResult: 强化结果
        """
        # 查找或创建模式
        pattern = self._find_or_create_pattern(knowledge, pattern_store)

        # 记录强化前状态
        confidence_before = pattern.confidence
        score_before = pattern.score

        # 确定强化动作
        action = self._determine_action(knowledge)

        # 应用强化
        self._apply_reinforcement(pattern, knowledge, action)

        # 记录强化后状态 (在 store 之前，因为 store 会重新 compute_score)
        confidence_after = pattern.confidence
        score_after = pattern.score

        # 更新 PatternStore
        pattern_store.store(pattern)

        # 更新计数器
        if action == ReinforcementAction.BOOST:
            self._total_boosted += 1
        elif action in (ReinforcementAction.DECAY, ReinforcementAction.SUPPRESS):
            self._total_decayed += 1

        return PatternReinforcementResult(
            pattern_id=pattern.pattern_id,
            knowledge_id=knowledge.knowledge_id,
            action=action.value,
            confidence_before=round(confidence_before, 4),
            confidence_after=round(confidence_after, 4),
            confidence_delta=round(confidence_after - confidence_before, 4),
            score_before=round(score_before, 4),
            score_after=round(score_after, 4),
            score_delta=round(score_after - score_before, 4),
            evidence_count=knowledge.experience_count,
            reason=self._build_reason(knowledge, action),
        )

    def reinforce_from_extraction(
        self,
        compression_result: CompressionResult,
        pattern_store: Any,
        experience_store: Any = None,  # ExperienceStore (optional)
    ) -> ReinforcementBatchResult:
        """全链路强化: 压缩 → 强化 → 存储.

        如果提供了 experience_store，将同时更新 GrowthExperience 的关联。

        Args:
            compression_result: CompressionResult 实例
            pattern_store: PatternStore 实例
            experience_store: ExperienceStore 实例 (可选)

        Returns:
            ReinforcementBatchResult: 批量强化结果
        """
        return self.reinforce(compression_result, pattern_store)

    # ── Action Determination ────────────────────────────────────

    def _determine_action(self, knowledge: CompressedKnowledge) -> ReinforcementAction:
        """根据知识质量确定强化动作.

        Decision Matrix:
                         | learning_gain > 0.05 | learning_gain ~ 0 | learning_gain < -0.05
        -----------------|---------------------|------------------|----------------------
        success_rate > 0.7 | BOOST               | MAINTAIN         | DECAY
        success_rate ~ 0.5 | MAINTAIN            | MAINTAIN         | DECAY
        success_rate < 0.3 | MAINTAIN            | DECAY            | SUPPRESS
        """
        gain = knowledge.avg_learning_gain
        rate = knowledge.success_rate

        if gain > self._boost_threshold and rate >= self._boost_rate:
            return ReinforcementAction.BOOST
        elif gain < self._decay_threshold:
            if rate < self._suppress_rate:
                return ReinforcementAction.SUPPRESS
            return ReinforcementAction.DECAY
        elif rate < self._suppress_rate:
            return ReinforcementAction.DECAY
        else:
            return ReinforcementAction.MAINTAIN

    # ── Reinforcement Application ───────────────────────────────

    def _apply_reinforcement(
        self,
        pattern: Any,
        knowledge: CompressedKnowledge,
        action: ReinforcementAction,
    ) -> None:
        """应用强化到模式."""
        if action == ReinforcementAction.BOOST:
            self._apply_boost(pattern, knowledge)
        elif action == ReinforcementAction.DECAY:
            self._apply_decay(pattern, knowledge)
        elif action == ReinforcementAction.SUPPRESS:
            self._apply_suppress(pattern, knowledge)
        # MAINTAIN: no change

    def _apply_boost(self, pattern: Any, knowledge: CompressedKnowledge) -> None:
        """增强模式."""
        perf = pattern.performance
        # 提升成功率 (EMA)
        perf.success_rate = round(
            perf.success_rate * 0.7 + knowledge.success_rate * 0.3,
            4,
        )
        # 更新平均奖励和置信度 (EMA)
        perf.avg_reward = round(
            perf.avg_reward * 0.7 + knowledge.avg_reward * 0.3,
            4,
        )
        perf.avg_confidence = round(
            perf.avg_confidence * 0.7 + knowledge.avg_confidence * 0.3,
            4,
        )
        # 更新样本数
        perf.samples += knowledge.experience_count
        # 更新元数据
        pattern.metadata["last_boosted"] = datetime.now(timezone.utc).isoformat()
        pattern.metadata["boost_count"] = pattern.metadata.get("boost_count", 0) + 1
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用 BOOST 增量 (在 compute_score 结果之上)
        pattern.confidence = round(
            min(1.0, pattern.confidence + self.BOOST_CONFIDENCE_DELTA),
            4,
        )

    def _apply_decay(self, pattern: Any, knowledge: CompressedKnowledge) -> None:
        """衰减模式."""
        perf = pattern.performance
        perf.success_rate = round(
            perf.success_rate * 0.8 + knowledge.success_rate * 0.2,
            4,
        )
        perf.avg_reward = round(
            perf.avg_reward * 0.8 + knowledge.avg_reward * 0.2,
            4,
        )
        perf.avg_confidence = round(
            perf.avg_confidence * 0.8 + knowledge.avg_confidence * 0.2,
            4,
        )
        perf.samples += knowledge.experience_count
        pattern.metadata["last_decayed"] = datetime.now(timezone.utc).isoformat()
        pattern.metadata["decay_count"] = pattern.metadata.get("decay_count", 0) + 1
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用 DECAY 增量 (在 compute_score 结果之上)
        pattern.confidence = round(
            max(0.1, pattern.confidence + self.DECAY_CONFIDENCE_DELTA),
            4,
        )

    def _apply_suppress(self, pattern: Any, knowledge: CompressedKnowledge) -> None:
        """抑制模式."""
        perf = pattern.performance
        perf.success_rate = round(
            perf.success_rate * 0.6 + knowledge.success_rate * 0.4,
            4,
        )
        perf.avg_reward = round(
            perf.avg_reward * 0.6 + knowledge.avg_reward * 0.4,
            4,
        )
        perf.avg_confidence = round(
            perf.avg_confidence * 0.6 + knowledge.avg_confidence * 0.4,
            4,
        )
        perf.samples += knowledge.experience_count
        pattern.metadata["last_suppressed"] = datetime.now(timezone.utc).isoformat()
        pattern.metadata["suppress_count"] = pattern.metadata.get("suppress_count", 0) + 1
        # 先 compute_score 更新基础评分和置信度
        pattern.compute_score()
        # 再应用 SUPPRESS 增量 (在 compute_score 结果之上)
        pattern.confidence = round(
            max(0.05, pattern.confidence + self.SUPPRESS_CONFIDENCE_DELTA),
            4,
        )

    # ── Pattern Store Interaction ───────────────────────────────

    def _find_or_create_pattern(
        self,
        knowledge: CompressedKnowledge,
        pattern_store: Any,
    ) -> Any:
        """在 PatternStore 中查找或创建模式."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            PatternCondition,
            PatternAction,
            PatternMemory,
            PatternMiningDimension,
            PatternPerformance,
            PatternQuality,
        )

        # 尝试查找已有模式 (不限制 actionable_only，因为新模式可能样本不足)
        # 使用 action_type 作为 opportunity_type 进行匹配 (兼容维度分组键)
        condition = PatternCondition(
            opportunity_type=knowledge.action_type,
            action_type=knowledge.action_type,
        )
        existing = pattern_store.get_best_pattern(
            condition=condition,
            opportunity_type=knowledge.action_type,
            action_type=knowledge.action_type,
            actionable_only=False,
        )

        if existing is not None:
            return existing

        # 创建新模式
        action = PatternAction(
            action_type=knowledge.action_type,
            expected_impact=knowledge.recommended_action,
        )
        performance = PatternPerformance(
            samples=knowledge.experience_count,
            success_count=int(knowledge.success_rate * knowledge.experience_count),
            success_rate=knowledge.success_rate,
            avg_reward=knowledge.avg_reward,
            avg_confidence=knowledge.avg_confidence,
            quality=PatternQuality.EMERGING,
        )
        pattern = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=condition,
            action=action,
            performance=performance,
            source_experience_ids=knowledge.source_experience_ids,
            tags=self._generate_tags(knowledge),
            confidence=knowledge.reliability_score,
        )
        pattern.compute_score()
        pattern.confidence = knowledge.reliability_score
        return pattern

    @staticmethod
    def _generate_tags(knowledge: CompressedKnowledge) -> list[str]:
        """生成标签."""
        tags: list[str] = []
        if knowledge.is_positive:
            tags.append("positive")
        else:
            tags.append("negative")
        if knowledge.category:
            tags.append(knowledge.category)
        if knowledge.dominant_feedback:
            tags.append(knowledge.dominant_feedback.lower())
        return tags

    @staticmethod
    def _build_reason(
        knowledge: CompressedKnowledge,
        action: ReinforcementAction,
    ) -> str:
        """构建强化原因."""
        if action == ReinforcementAction.BOOST:
            return (
                f"Boosted: avg_gain={knowledge.avg_learning_gain:+.3f}, "
                f"success_rate={knowledge.success_rate:.0%}, "
                f"samples={knowledge.experience_count}"
            )
        elif action == ReinforcementAction.DECAY:
            return (
                f"Decayed: avg_gain={knowledge.avg_learning_gain:+.3f}, "
                f"success_rate={knowledge.success_rate:.0%}, "
                f"samples={knowledge.experience_count}"
            )
        elif action == ReinforcementAction.SUPPRESS:
            return (
                f"Suppressed: avg_gain={knowledge.avg_learning_gain:+.3f}, "
                f"success_rate={knowledge.success_rate:.0%} (low), "
                f"samples={knowledge.experience_count}"
            )
        else:
            return (
                f"Maintained: avg_gain={knowledge.avg_learning_gain:+.3f}, "
                f"success_rate={knowledge.success_rate:.0%}"
            )

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取桥接器统计."""
        return {
            "reinforce_count": self._reinforce_count,
            "total_boosted": self._total_boosted,
            "total_decayed": self._total_decayed,
            "boost_threshold": self._boost_threshold,
            "decay_threshold": self._decay_threshold,
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self._reinforce_count = 0
        self._total_boosted = 0
        self._total_decayed = 0


__all__ = [
    "PatternReinforcementBridge",
]