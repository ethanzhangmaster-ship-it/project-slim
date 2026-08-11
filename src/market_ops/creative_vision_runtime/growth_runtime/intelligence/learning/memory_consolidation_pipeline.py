"""E13.7.10 Memory Consolidation Pipeline — 记忆整合自动流水线.

Day 7.10:
  将 Day 7.9 五个模块串成自动流水线:
    Extract → Compress → Reinforce → Decay → Update Graph

核心职责:
  1. 编排 Day 7.9 五个模块的顺序执行
  2. 每个阶段 fail-safe (某阶段失败不阻断整体)
  3. 生成 ConsolidationReport 供审计
  4. 与 LearningCycleOrchestrator 集成

流程:
  OrchestrationCycleResult
      │
      ▼
  [1] ExperienceExtractor.extract()
      │
      ▼
  [2] KnowledgeCompressor.compress_from_extraction()
      │
      ▼
  [3] PatternReinforcementBridge.reinforce_from_extraction()
      │
      ▼
  [4] PatternDecayEngine.decay_store()
      │
      ▼
  [5] KnowledgeGraphUpdater.update_graph()
      │
      ▼
  ConsolidationReport

连接:
  LearningCycleOrchestrator → MemoryConsolidationPipeline → evolution_models.KnowledgeGraph

设计原则:
  - 编排层，不实现具体算法
  - 每个阶段 fail-safe
  - 完整的生命周期管理
  - 可审计的阶段记录
  - 不修改已有模块
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .knowledge_compressor import KnowledgeCompressor
from .knowledge_graph_updater import KnowledgeGraphUpdater
from .learning_experience_extractor import ExperienceExtractor
from .models.memory_consolidation_models import (
    ConsolidationReport,
    PipelineStage,
    StageResult,
)
from .pattern_decay_engine import PatternDecayEngine
from .pattern_reinforcement_bridge import PatternReinforcementBridge


class MemoryConsolidationPipeline:
    """记忆整合流水线 — 自动编排 Day 7.9 五个模块.

    用法:
        pipeline = MemoryConsolidationPipeline(
            extractor=ExperienceExtractor(),
            compressor=KnowledgeCompressor(),
            reinforcement_bridge=PatternReinforcementBridge(),
            decay_engine=PatternDecayEngine(),
            graph_updater=KnowledgeGraphUpdater(),
            pattern_store=PatternStore(),
        )
        report = pipeline.consolidate(cycle_result)
        print(report.summary)
    """

    def __init__(
        self,
        extractor: ExperienceExtractor | None = None,
        compressor: KnowledgeCompressor | None = None,
        reinforcement_bridge: PatternReinforcementBridge | None = None,
        decay_engine: PatternDecayEngine | None = None,
        graph_updater: KnowledgeGraphUpdater | None = None,
        pattern_store: Any = None,  # PatternStore
    ):
        self._extractor = extractor or ExperienceExtractor()
        self._compressor = compressor or KnowledgeCompressor()
        self._reinforcement_bridge = reinforcement_bridge or PatternReinforcementBridge()
        self._decay_engine = decay_engine or PatternDecayEngine()
        self._graph_updater = graph_updater or KnowledgeGraphUpdater()
        self._pattern_store = pattern_store

        self._run_count: int = 0
        self._reports: list[ConsolidationReport] = []

    # ── Properties ───────────────────────────────────────────────

    @property
    def run_count(self) -> int:
        return self._run_count

    @property
    def last_report(self) -> ConsolidationReport | None:
        return self._reports[-1] if self._reports else None

    # ── Public API ───────────────────────────────────────────────

    def consolidate(
        self,
        cycle_result: Any,  # OrchestrationCycleResult
    ) -> ConsolidationReport:
        """执行完整记忆整合流水线 — 主入口.

        Args:
            cycle_result: OrchestrationCycleResult 实例

        Returns:
            ConsolidationReport: 流水线报告
        """
        self._run_count += 1
        pipeline_id = str(uuid.uuid4())[:8]
        cycle_number = getattr(cycle_result, "cycle_number", self._run_count)
        stages: list[StageResult] = []

        # ── Stage 1: Experience Extraction ──
        stage1 = self._run_extract(cycle_result)
        stages.append(stage1)

        extraction_result = stage1.result_ref if stage1.success else None

        # ── Stage 2: Knowledge Compression ──
        stage2 = self._run_compress(extraction_result)
        stages.append(stage2)

        compression_result = stage2.result_ref if stage2.success else None

        # ── Stage 3: Pattern Reinforcement ──
        stage3 = self._run_reinforce(compression_result)
        stages.append(stage3)

        reinforcement_result = stage3.result_ref if stage3.success else None

        # ── Stage 4: Pattern Decay ──
        stage4 = self._run_decay()
        stages.append(stage4)

        decay_result = stage4.result_ref if stage4.success else None

        # ── Stage 5: Knowledge Graph Update ──
        stage5 = self._run_update_graph(reinforcement_result, decay_result)
        stages.append(stage5)

        # ── Build Report ──
        report = ConsolidationReport.from_stages(
            stages=stages,
            cycle_number=cycle_number,
            pipeline_id=pipeline_id,
        )
        self._reports.append(report)
        return report

    def consolidate_batch(
        self,
        cycle_results: list[Any],
    ) -> list[ConsolidationReport]:
        """批量执行流水线.

        Args:
            cycle_results: OrchestrationCycleResult 列表

        Returns:
            list[ConsolidationReport]: 每个周期的报告
        """
        reports: list[ConsolidationReport] = []
        for cr in cycle_results:
            report = self.consolidate(cr)
            reports.append(report)
        return reports

    # ── Stage Runners ────────────────────────────────────────────

    def _run_extract(self, cycle_result: Any) -> StageResult:
        """Stage 1: Experience Extraction."""
        start = time.perf_counter()
        try:
            extraction_result = self._extractor.extract(cycle_result)
            count = (
                len(extraction_result.experiences)
                if hasattr(extraction_result, "experiences") else 0
            )
            return StageResult(
                stage=PipelineStage.EXTRACT,
                success=True,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                items_processed=1,
                items_produced=count,
                result_ref=extraction_result,
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.EXTRACT,
                success=False,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=str(e),
            )

    def _run_compress(
        self,
        extraction_result: Any,
    ) -> StageResult:
        """Stage 2: Knowledge Compression."""
        if extraction_result is None:
            return StageResult(
                stage=PipelineStage.COMPRESS,
                success=False,
                error="No extraction result from previous stage",
            )
        start = time.perf_counter()
        try:
            compression_result = self._compressor.compress_from_extraction(
                extraction_result,
            )
            count = (
                len(compression_result.knowledge_units)
                if hasattr(compression_result, "knowledge_units") else 0
            )
            return StageResult(
                stage=PipelineStage.COMPRESS,
                success=True,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                items_processed=(
                    len(extraction_result.experiences)
                    if hasattr(extraction_result, "experiences") else 0
                ),
                items_produced=count,
                result_ref=compression_result,
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.COMPRESS,
                success=False,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=str(e),
            )

    def _run_reinforce(
        self,
        compression_result: Any,
    ) -> StageResult:
        """Stage 3: Pattern Reinforcement."""
        if compression_result is None or self._pattern_store is None:
            return StageResult(
                stage=PipelineStage.REINFORCE,
                success=False,
                error="No compression result or no pattern store available",
            )
        start = time.perf_counter()
        try:
            reinforcement_result = self._reinforcement_bridge.reinforce_from_extraction(
                compression_result=compression_result,
                pattern_store=self._pattern_store,
            )
            count = (
                len(reinforcement_result.results)
                if hasattr(reinforcement_result, "results") else 0
            )
            return StageResult(
                stage=PipelineStage.REINFORCE,
                success=True,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                items_processed=(
                    len(compression_result.knowledge_units)
                    if hasattr(compression_result, "knowledge_units") else 0
                ),
                items_produced=count,
                result_ref=reinforcement_result,
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.REINFORCE,
                success=False,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=str(e),
            )

    def _run_decay(self) -> StageResult:
        """Stage 4: Pattern Decay."""
        if self._pattern_store is None:
            return StageResult(
                stage=PipelineStage.DECAY,
                success=False,
                error="No pattern store available",
            )
        start = time.perf_counter()
        try:
            decay_result = self._decay_engine.decay_store(self._pattern_store)
            count = (
                len(decay_result.results)
                if hasattr(decay_result, "results") else 0
            )
            return StageResult(
                stage=PipelineStage.DECAY,
                success=True,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                items_processed=decay_result.total_patterns if hasattr(decay_result, "total_patterns") else 0,
                items_produced=count,
                result_ref=decay_result,
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.DECAY,
                success=False,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=str(e),
            )

    def _run_update_graph(
        self,
        reinforcement_result: Any,
        decay_result: Any,
    ) -> StageResult:
        """Stage 5: Knowledge Graph Update."""
        if self._pattern_store is None:
            return StageResult(
                stage=PipelineStage.UPDATE_GRAPH,
                success=False,
                error="No pattern store available",
            )
        start = time.perf_counter()
        try:
            patterns = self._pattern_store.get_all()

            # 提取 reinforcement/decay results 列表
            rr_list = (
                reinforcement_result.results
                if reinforcement_result and hasattr(reinforcement_result, "results")
                else []
            )
            dr_list = (
                decay_result.results
                if decay_result and hasattr(decay_result, "results")
                else []
            )

            graph_result = self._graph_updater.update_graph(
                patterns=patterns,
                reinforcement_results=rr_list if rr_list else None,
                decay_results=dr_list if dr_list else None,
            )
            return StageResult(
                stage=PipelineStage.UPDATE_GRAPH,
                success=True,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                items_processed=len(patterns),
                items_produced=graph_result.total_nodes if hasattr(graph_result, "total_nodes") else 0,
                result_ref=graph_result,
            )
        except Exception as e:
            return StageResult(
                stage=PipelineStage.UPDATE_GRAPH,
                success=False,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
                error=str(e),
            )

    # ── Reports ──────────────────────────────────────────────────

    def get_reports(self, limit: int = 10) -> list[ConsolidationReport]:
        """获取最近报告."""
        return self._reports[-limit:] if limit > 0 else self._reports

    def get_latest_report(self) -> ConsolidationReport | None:
        """获取最新报告."""
        return self._reports[-1] if self._reports else None

    # ── Statistics ───────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取流水线统计."""
        reports = self._reports
        total_runs = len(reports)
        success_runs = sum(1 for r in reports if r.overall_success)
        total_experiences = sum(r.total_experiences for r in reports)
        total_patterns = sum(r.total_patterns for r in reports)
        total_reinforced = sum(r.reinforced_patterns for r in reports)
        total_decayed = sum(r.decayed_patterns for r in reports)

        return {
            "run_count": self._run_count,
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failure_runs": total_runs - success_runs,
            "total_experiences": total_experiences,
            "total_patterns": total_patterns,
            "total_reinforced": total_reinforced,
            "total_decayed": total_decayed,
            "pipeline_health": round(success_runs / total_runs, 4) if total_runs > 0 else 1.0,
        }

    def reset(self) -> None:
        """重置流水线状态."""
        self._run_count = 0
        self._reports.clear()


__all__ = [
    "MemoryConsolidationPipeline",
]