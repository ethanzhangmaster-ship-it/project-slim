"""E13.7.9 Experience Extractor — 学习经验提取器.

Day 7.9 Step 1:
  从 Learning Cycle 的结果中提取结构化经验数据，
  桥接 Learning System 与 Memory System。

核心职责:
  1. 从 OrchestrationCycleResult 提取 ConsolidatedExperience
  2. 将 ConsolidatedExperience 转换为 GrowthExperience (Memory System 格式)
  3. 提取并存储到 ExperienceStore

流程:
  OrchestrationCycleResult
      │
      ▼
  extract() → ConsolidatedExperience
      │
      ▼
  to_growth_experience() → GrowthExperience
      │
      ▼
  ExperienceStore.store()

连接:
  LearningCycleOrchestrator → ExperienceExtractor → ExperienceStore → PatternMiner

设计原则:
  - 纯桥接层，不修改已有模块
  - 所有提取逻辑集中在此模块
  - 可配置显著性阈值
  - 支持批量提取
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models.learning_memory_models import (
    ConsolidatedExperience,
    ExtractionResult,
)


class ExperienceExtractor:
    """经验提取器 — 从学习循环中提取结构化经验.

    桥接 Learning System 和 Memory System:
      - Learning System: OrchestrationCycleResult (编排周期输出)
      - Memory System:  GrowthExperience (经验存储单元)

    用法:
        extractor = ExperienceExtractor(significance_threshold=0.3)
        result = extractor.extract(cycle_result)
        # 将显著经验存入 ExperienceStore
        for exp in result.significant_experiences:
            growth_exp = extractor.to_growth_experience(exp)
            experience_store.store(growth_exp)
    """

    def __init__(self, significance_threshold: float = 0.3):
        """初始化提取器.

        Args:
            significance_threshold: 显著性阈值 [0, 1]
                低于此值的经验不会被标记为 significant
        """
        self._significance_threshold = max(0.0, min(1.0, significance_threshold))
        self._extract_count: int = 0
        self._total_extracted: int = 0
        self._total_significant: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def significance_threshold(self) -> float:
        return self._significance_threshold

    @property
    def extract_count(self) -> int:
        """提取操作次数."""
        return self._extract_count

    @property
    def total_extracted(self) -> int:
        """累计提取经验数."""
        return self._total_extracted

    @property
    def total_significant(self) -> int:
        """累计显著经验数."""
        return self._total_significant

    # ── Public API ───────────────────────────────────────────────

    def extract(self, cycle_result: Any) -> ExtractionResult:
        """从编排周期结果中提取经验 — 主入口.

        Args:
            cycle_result: OrchestrationCycleResult 实例

        Returns:
            ExtractionResult: 提取结果，包含 ConsolidatedExperience 列表
        """
        self._extract_count += 1

        # 提取单一经验 (每个周期产生一条经验)
        experience = ConsolidatedExperience.from_cycle_result(
            cycle_result=cycle_result,
            significance_threshold=self._significance_threshold,
        )

        self._total_extracted += 1
        if experience.is_significant:
            self._total_significant += 1

        return ExtractionResult.from_experiences(
            experiences=[experience],
            source_cycle_id=experience.source_cycle_id,
            cycle_number=experience.cycle_number,
        )

    def extract_batch(
        self,
        cycle_results: list[Any],
    ) -> list[ExtractionResult]:
        """批量提取经验.

        Args:
            cycle_results: OrchestrationCycleResult 列表

        Returns:
            list[ExtractionResult]: 每个周期的提取结果
        """
        return [self.extract(cr) for cr in cycle_results]

    def extract_all_experiences(
        self,
        cycle_results: list[Any],
    ) -> list[ConsolidatedExperience]:
        """批量提取所有经验 (扁平化).

        Args:
            cycle_results: OrchestrationCycleResult 列表

        Returns:
            list[ConsolidatedExperience]: 所有周期的经验列表
        """
        results = self.extract_batch(cycle_results)
        all_exp: list[ConsolidatedExperience] = []
        for r in results:
            all_exp.extend(r.experiences)
        return all_exp

    def extract_significant_only(
        self,
        cycle_results: list[Any],
    ) -> list[ConsolidatedExperience]:
        """仅提取显著经验.

        Args:
            cycle_results: OrchestrationCycleResult 列表

        Returns:
            list[ConsolidatedExperience]: 显著经验列表
        """
        all_exp = self.extract_all_experiences(cycle_results)
        return [e for e in all_exp if e.is_significant]

    # ── Memory System Bridge ────────────────────────────────────

    def to_growth_experience(
        self,
        consolidated: ConsolidatedExperience,
    ) -> Any:
        """将 ConsolidatedExperience 转换为 GrowthExperience.

        这是 Learning System → Memory System 的核心转换点。

        Args:
            consolidated: ConsolidatedExperience 实例

        Returns:
            GrowthExperience: 可直接存入 ExperienceStore 的经验
        """
        # 动态导入避免循环依赖
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
            ExperienceContext,
            ExperienceOutcome,
            ExperienceOutcomeLevel,
            GrowthExperience,
        )

        # 构建 ExperienceContext
        context = ExperienceContext(
            opportunity_type=consolidated.decision_type or "learning_cycle",
            action_type=consolidated.action_type,
            trigger_signals=consolidated.tags,
            market_conditions=consolidated.metrics_delta,
        )

        # 构建 ExperienceOutcome
        outcome_level = self._map_outcome_level(consolidated)
        outcome = ExperienceOutcome(
            success=consolidated.success,
            outcome_level=outcome_level,
            metrics_delta=consolidated.metrics_delta,
            actual_reward=consolidated.reward,
        )

        # 构建 GrowthExperience
        experience = GrowthExperience(
            context=context,
            action_type=consolidated.action_type,
            action_params=consolidated.action_params,
            outcome=outcome,
            reward=consolidated.reward,
            confidence=consolidated.confidence,
            tags=consolidated.tags,
            metadata={
                "source_cycle_id": consolidated.source_cycle_id,
                "cycle_number": consolidated.cycle_number,
                "feedback_classification": consolidated.feedback_classification,
                "learning_gain": consolidated.learning_gain,
                "effectiveness_score": consolidated.effectiveness_score,
                "gate_decision": consolidated.gate_decision,
                "significance_score": consolidated.significance_score,
                "is_significant": consolidated.is_significant,
                "policy_adjustments": consolidated.policy_adjustments,
                "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return experience

    def extract_and_store(
        self,
        cycle_result: Any,
        experience_store: Any,  # ExperienceStore
    ) -> ExtractionResult:
        """提取经验并直接存入 ExperienceStore.

        Args:
            cycle_result: OrchestrationCycleResult 实例
            experience_store: ExperienceStore 实例

        Returns:
            ExtractionResult: 提取结果
        """
        result = self.extract(cycle_result)

        for exp in result.experiences:
            if exp.is_significant:
                growth_exp = self.to_growth_experience(exp)
                experience_store.store(growth_exp)

        return result

    def extract_batch_and_store(
        self,
        cycle_results: list[Any],
        experience_store: Any,
    ) -> list[ExtractionResult]:
        """批量提取并存储.

        Args:
            cycle_results: OrchestrationCycleResult 列表
            experience_store: ExperienceStore 实例

        Returns:
            list[ExtractionResult]: 提取结果列表
        """
        return [self.extract_and_store(cr, experience_store) for cr in cycle_results]

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _map_outcome_level(
        consolidated: ConsolidatedExperience,
    ) -> Any:
        """将 ConsolidatedExperience 映射到 ExperienceOutcomeLevel."""
        from market_ops.creative_vision_runtime.growth_runtime.memory.models import ExperienceOutcomeLevel

        if not consolidated.success:
            return ExperienceOutcomeLevel.FAILURE

        if consolidated.learning_gain >= 0.1:
            return ExperienceOutcomeLevel.STRONG_SUCCESS
        elif consolidated.learning_gain > 0:
            return ExperienceOutcomeLevel.SUCCESS
        elif consolidated.learning_gain >= -0.05:
            return ExperienceOutcomeLevel.NEUTRAL
        else:
            return ExperienceOutcomeLevel.FAILURE

    # ── Statistics ──────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取提取器统计."""
        return {
            "extract_count": self._extract_count,
            "total_extracted": self._total_extracted,
            "total_significant": self._total_significant,
            "significance_threshold": self._significance_threshold,
            "significant_ratio": round(
                self._total_significant / max(self._total_extracted, 1), 4,
            ),
        }

    def reset_stats(self) -> None:
        """重置统计."""
        self._extract_count = 0
        self._total_extracted = 0
        self._total_significant = 0


__all__ = [
    "ExperienceExtractor",
]