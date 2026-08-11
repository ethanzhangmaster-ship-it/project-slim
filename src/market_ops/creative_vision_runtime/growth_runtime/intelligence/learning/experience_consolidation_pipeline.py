"""E17.11.3 ExperienceConsolidationPipeline — 经验整合编排管线.

Day 7.11 Step 3.3:
  编排 ConsolidationTrigger → ExperienceConsolidationAdapter → MemoryConsolidationPipeline，
  将 ExperienceStore 中的经验批次送入核心记忆整合引擎。

核心流程:
  GrowthExperience[]
      │
      ▼
  ConsolidationTrigger.check()
      │
      ├── NO → ConsolidationResult.skipped()
      │
      ▼ YES
  ExperienceConsolidationAdapter.build_context()
      │
      ▼
  MemoryConsolidationPipeline.consolidate(context)
      │
      ▼
  ConsolidationResult

设计原则:
  - 编排层，不实现具体算法
  - Trigger 决定安全阀，Adapter 负责适配，Pipeline 负责执行
  - fail-safe: 整合失败不阻断经验写入
  - 可审计的完整链路
  - 不修改已有模块
"""

from __future__ import annotations

import time
from typing import Any

from .consolidation_trigger import ConsolidationTrigger
from .experience_consolidation_adapter import ExperienceConsolidationAdapter
from .memory_consolidation_pipeline import MemoryConsolidationPipeline
from .models.consolidation_models import (
    ConsolidationResult,
    ConsolidationStatus,
    TriggerDecision,
)


class ExperienceConsolidationPipeline:
    """经验整合编排管线.

    编排 Trigger → Adapter → MemoryPipeline 的完整链路，
    将经验批次转化为长期记忆。

    用法:
        pipeline = ExperienceConsolidationPipeline(
            memory_pipeline=MemoryConsolidationPipeline(...),
            trigger=ConsolidationTrigger(),
            adapter=ExperienceConsolidationAdapter(),
        )
        result = pipeline.run(experiences)

        if result.is_executed:
            print(f"Patterns: {result.consolidation_report.total_patterns}")
    """

    def __init__(
        self,
        memory_pipeline: MemoryConsolidationPipeline | None = None,
        trigger: ConsolidationTrigger | None = None,
        adapter: ExperienceConsolidationAdapter | None = None,
    ):
        """初始化编排管线.

        Args:
            memory_pipeline: MemoryConsolidationPipeline (核心整合引擎)
            trigger: ConsolidationTrigger (触发判定)
            adapter: ExperienceConsolidationAdapter (输入适配)
        """
        self._memory_pipeline = memory_pipeline
        self._trigger = trigger or ConsolidationTrigger()
        self._adapter = adapter or ExperienceConsolidationAdapter()

        self._run_count: int = 0
        self._executed_count: int = 0
        self._skipped_count: int = 0
        self._failed_count: int = 0
        self._results: list[ConsolidationResult] = []

    # ── Properties ──────────────────────────────────────────────

    @property
    def run_count(self) -> int:
        return self._run_count

    @property
    def executed_count(self) -> int:
        return self._executed_count

    @property
    def skipped_count(self) -> int:
        return self._skipped_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    @property
    def trigger(self) -> ConsolidationTrigger:
        return self._trigger

    @property
    def adapter(self) -> ExperienceConsolidationAdapter:
        return self._adapter

    @property
    def memory_pipeline(self) -> MemoryConsolidationPipeline | None:
        return self._memory_pipeline

    # ── Public API ──────────────────────────────────────────────

    def run(
        self,
        experiences: list[Any],
        history_avg_reward: float | None = None,
    ) -> ConsolidationResult:
        """执行经验整合 — 主入口.

        Args:
            experiences: GrowthExperience 列表
            history_avg_reward: 历史平均奖励 (用于 learning_gain)

        Returns:
            ConsolidationResult
        """
        self._run_count += 1
        start = time.perf_counter()

        # ── Step 1: Trigger Check ──
        trigger_decision = self._trigger.check(experiences)

        if not trigger_decision.should_run:
            result = ConsolidationResult.skipped(trigger_decision)
            result.experience_count = len(experiences)
            result.duration_ms = round((time.perf_counter() - start) * 1000, 2)
            self._skipped_count += 1
            self._results.append(result)
            return result

        # ── Step 2: Build Context ──
        try:
            context = self._adapter.build_context(
                experiences, history_avg_reward,
            )
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            result = ConsolidationResult.failed(
                trigger_decision,
                error=f"Adapter build_context failed: {e}",
                duration_ms=duration_ms,
            )
            result.experience_count = len(experiences)
            self._failed_count += 1
            self._results.append(result)
            return result

        # ── Step 3: Consolidate via MemoryPipeline ──
        if self._memory_pipeline is None:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            result = ConsolidationResult.failed(
                trigger_decision,
                error="No memory_pipeline configured",
                duration_ms=duration_ms,
            )
            result.experience_count = len(experiences)
            self._failed_count += 1
            self._results.append(result)
            return result

        try:
            # 将 GrowthExperiences 转换为 ConsolidatedExperiences
            # 绕过 extract 阶段，直接送入 compress → reinforce
            report = self._consolidate_from_experiences(experiences, context)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            result = ConsolidationResult.executed(
                trigger=trigger_decision,
                report=report,
                experience_count=len(experiences),
                context_id=context.cycle_id,
                duration_ms=duration_ms,
            )
            self._executed_count += 1
            self._results.append(result)
            return result
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            result = ConsolidationResult.failed(
                trigger_decision,
                error=f"MemoryPipeline consolidate failed: {e}",
                duration_ms=duration_ms,
            )
            result.experience_count = len(experiences)
            self._failed_count += 1
            self._results.append(result)
            return result

    def _consolidate_from_experiences(
        self,
        experiences: list[Any],
        context: Any,
    ) -> Any:
        """将 GrowthExperience 列表直接送入 MemoryPipeline 的压缩→强化阶段.

        绕过 extract 阶段，因为 GrowthExperience 已经是结构化经验，
        直接转换为 ConsolidatedExperience 后送入压缩器。

        Args:
            experiences: GrowthExperience 列表
            context: ConsolidationContext

        Returns:
            ConsolidationReport
        """
        from .models.learning_memory_models import (
            ConsolidatedExperience,
            ExtractionResult,
        )
        from .models.memory_consolidation_models import (
            ConsolidationReport,
            PipelineStage,
            StageResult,
        )

        pipeline_id = context.cycle_id[:8] if context.cycle_id else "unknown"
        stages: list[StageResult] = []

        # ── Step 3a: 将 GrowthExperience → ConsolidatedExperience ──
        consolidated: list[ConsolidatedExperience] = []
        for exp in experiences:
            try:
                ce = ConsolidatedExperience.from_growth_experience(exp)
                consolidated.append(ce)
            except Exception:
                continue

        # 构建 ExtractionResult
        extraction_result = ExtractionResult.from_experiences(
            experiences=consolidated,
            source_cycle_id=context.cycle_id,
            cycle_number=context.cycle_number,
        )

        # 记录 extract 阶段 (标记为 synthetic)
        stages.append(StageResult(
            stage=PipelineStage.EXTRACT,
            success=True,
            duration_ms=0.0,
            items_processed=len(experiences),
            items_produced=len(consolidated),
            result_ref=extraction_result,
        ))

        # ── Step 3b: Compress ──
        stage2 = self._memory_pipeline._run_compress(extraction_result)
        stages.append(stage2)
        compression_result = stage2.result_ref if stage2.success else None

        # ── Step 3c: Reinforce ──
        stage3 = self._memory_pipeline._run_reinforce(compression_result)
        stages.append(stage3)
        reinforcement_result = stage3.result_ref if stage3.success else None

        # ── Step 3d: Decay ──
        stage4 = self._memory_pipeline._run_decay()
        stages.append(stage4)
        decay_result = stage4.result_ref if stage4.success else None

        # ── Step 3e: Update Graph ──
        stage5 = self._memory_pipeline._run_update_graph(
            reinforcement_result, decay_result,
        )
        stages.append(stage5)

        # ── Build Report ──
        return ConsolidationReport.from_stages(
            stages=stages,
            cycle_number=context.cycle_number,
            pipeline_id=pipeline_id,
        )

    def run_batch(
        self,
        experience_batches: list[list[Any]],
        history_avg_reward: float | None = None,
    ) -> list[ConsolidationResult]:
        """批量执行整合.

        Args:
            experience_batches: 多批 GrowthExperience 列表
            history_avg_reward: 历史平均奖励

        Returns:
            list[ConsolidationResult]
        """
        results: list[ConsolidationResult] = []
        for batch in experience_batches:
            result = self.run(batch, history_avg_reward)
            results.append(result)
        return results

    # ── Reports ─────────────────────────────────────────────────

    def get_results(self, limit: int = 10) -> list[ConsolidationResult]:
        """获取最近结果."""
        return self._results[-limit:] if limit > 0 else self._results

    def get_latest_result(self) -> ConsolidationResult | None:
        """获取最新结果."""
        return self._results[-1] if self._results else None

    # ── Statistics ───────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取管线统计."""
        total = self._run_count
        return {
            "run_count": total,
            "executed_count": self._executed_count,
            "skipped_count": self._skipped_count,
            "failed_count": self._failed_count,
            "execution_rate": round(self._executed_count / total, 4) if total > 0 else 0.0,
            "skip_rate": round(self._skipped_count / total, 4) if total > 0 else 0.0,
            "failure_rate": round(self._failed_count / total, 4) if total > 0 else 0.0,
            "trigger_checks": self._trigger.check_count,
            "trigger_approvals": self._trigger.trigger_count,
            "adapter_builds": self._adapter.build_count,
            "adapter_experiences": self._adapter.total_experiences_adapted,
        }

    # ── Management ──────────────────────────────────────────────

    def reset(self) -> None:
        """重置管线状态."""
        self._run_count = 0
        self._executed_count = 0
        self._skipped_count = 0
        self._failed_count = 0
        self._results.clear()
        self._trigger.reset()
        self._adapter.reset()

    def set_memory_pipeline(self, pipeline: MemoryConsolidationPipeline) -> None:
        """设置核心整合引擎."""
        self._memory_pipeline = pipeline

    def set_trigger(self, trigger: ConsolidationTrigger) -> None:
        """设置触发判定引擎."""
        self._trigger = trigger


__all__ = [
    "ExperienceConsolidationPipeline",
]