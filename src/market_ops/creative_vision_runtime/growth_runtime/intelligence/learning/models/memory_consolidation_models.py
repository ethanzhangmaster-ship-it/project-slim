"""E13.7.10 Memory Consolidation Pipeline Models — 记忆整合编排协议.

Day 7.10:
  将 Day 7.9 的五个模块 (Extraction → Compression → Reinforcement
  → Decay → Knowledge Graph) 串成自动流水线。

核心模型:
  1. PipelineStage            — 流水线阶段枚举
  2. StageResult              — 单阶段执行结果
  3. ConsolidationReport      — 完整流水线报告

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 每个阶段 fail-safe (某阶段失败不阻断整体)
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. PipelineStage
# ═══════════════════════════════════════════════════════════════


class PipelineStage(str, Enum):
    """流水线阶段枚举."""
    EXTRACT = "extract"               # Step 1: Experience Extraction
    COMPRESS = "compress"             # Step 2: Knowledge Compression
    REINFORCE = "reinforce"           # Step 3: Pattern Reinforcement
    DECAY = "decay"                   # Step 4: Pattern Decay
    UPDATE_GRAPH = "update_graph"     # Step 5: Knowledge Graph Update


# ═══════════════════════════════════════════════════════════════
# 2. StageResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class StageResult:
    """单阶段执行结果 — 记录流水线中一个阶段的执行情况.

    Attributes:
        stage: 阶段名称
        success: 是否成功
        duration_ms: 耗时 (毫秒)
        items_processed: 处理条目数
        items_produced: 产出条目数
        error: 错误信息 (如果失败)
        result_ref: 阶段产出引用 (如 ConsolidatedExperience / CompressedKnowledge 等)
        metadata: 扩展元数据
    """
    stage: PipelineStage = PipelineStage.EXTRACT
    success: bool = True
    duration_ms: float = 0.0
    items_processed: int = 0
    items_produced: int = 0
    error: str | None = None
    result_ref: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_failed(self) -> bool:
        return not self.success

    @property
    def throughput(self) -> float:
        """吞吐量 (items/second)."""
        if self.duration_ms <= 0:
            return 0.0
        return round(self.items_produced / (self.duration_ms / 1000), 2)

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "items_processed": self.items_processed,
            "items_produced": self.items_produced,
            "error": self.error,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. ConsolidationReport
# ═══════════════════════════════════════════════════════════════


@dataclass
class ConsolidationReport:
    """记忆整合报告 — 一次完整流水线执行的输出.

    Attributes:
        report_id: 报告唯一标识
        cycle_number: 关联的学习周期编号
        pipeline_id: 流水线运行 ID
        stages: 各阶段执行结果
        total_duration_ms: 总耗时
        total_experiences: 提取的经验总数
        total_patterns: 存入的模式总数
        reinforced_patterns: 强化的模式数
        decayed_patterns: 衰减的模式数
        graph_nodes_updated: 图谱节点更新数
        graph_edges_updated: 图谱边更新数
        overall_success: 整体是否成功
        failed_stages: 失败的阶段列表
        summary: 人类可读摘要
        created_at: 创建时间
        metadata: 扩展元数据
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_number: int = 0
    pipeline_id: str = ""
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    total_experiences: int = 0
    total_patterns: int = 0
    reinforced_patterns: int = 0
    decayed_patterns: int = 0
    graph_nodes_updated: int = 0
    graph_edges_updated: int = 0
    overall_success: bool = True
    failed_stages: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_empty(self) -> bool:
        return len(self.stages) == 0

    @property
    def stage_count(self) -> int:
        return len(self.stages)

    @property
    def success_count(self) -> int:
        return sum(1 for s in self.stages if s.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for s in self.stages if not s.success)

    @property
    def has_failures(self) -> bool:
        return self.failure_count > 0

    @property
    def has_changes(self) -> bool:
        """是否有实质性变化 (产生了模式/更新了图谱)."""
        return (self.total_patterns > 0
                or self.reinforced_patterns > 0
                or self.decayed_patterns > 0
                or self.graph_nodes_updated > 0)

    # ── Factory Methods ─────────────────────────────────────────

    @classmethod
    def from_stages(
        cls,
        stages: list[StageResult],
        cycle_number: int = 0,
        pipeline_id: str = "",
    ) -> ConsolidationReport:
        """从阶段结果列表创建报告."""
        total_duration = round(sum(s.duration_ms for s in stages), 2)
        failed = [s.stage.value for s in stages if not s.success]

        # 从各阶段结果中提取统计
        extract_stage = _find_stage(stages, PipelineStage.EXTRACT)
        compress_stage = _find_stage(stages, PipelineStage.COMPRESS)
        reinforce_stage = _find_stage(stages, PipelineStage.REINFORCE)
        decay_stage = _find_stage(stages, PipelineStage.DECAY)
        graph_stage = _find_stage(stages, PipelineStage.UPDATE_GRAPH)

        total_experiences = extract_stage.items_produced if extract_stage else 0
        total_patterns = compress_stage.items_produced if compress_stage else 0
        reinforced_patterns = reinforce_stage.items_produced if reinforce_stage else 0
        decayed_patterns = decay_stage.items_produced if decay_stage else 0
        graph_nodes = graph_stage.items_produced if graph_stage else 0

        summary = cls._build_summary(
            total_experiences, total_patterns,
            reinforced_patterns, decayed_patterns, graph_nodes,
            total_duration, len(failed),
        )

        return cls(
            cycle_number=cycle_number,
            pipeline_id=pipeline_id,
            stages=stages,
            total_duration_ms=total_duration,
            total_experiences=total_experiences,
            total_patterns=total_patterns,
            reinforced_patterns=reinforced_patterns,
            decayed_patterns=decayed_patterns,
            graph_nodes_updated=graph_nodes,
            graph_edges_updated=0,
            overall_success=len(failed) == 0,
            failed_stages=failed,
            summary=summary,
        )

    @staticmethod
    def _build_summary(
        total_experiences: int,
        total_patterns: int,
        reinforced: int,
        decayed: int,
        graph_nodes: int,
        total_duration_ms: float,
        failed_count: int,
    ) -> str:
        """构建人类可读摘要."""
        status = "COMPLETED" if failed_count == 0 else f"COMPLETED ({failed_count} failures)"
        lines = [
            "=" * 55,
            f"  Memory Consolidation Pipeline — {status}",
            "=" * 55,
            f"  Experiences extracted:    {total_experiences:>4d}",
            f"  Patterns stored:         {total_patterns:>4d}",
            f"  Patterns reinforced:     {reinforced:>4d}",
            f"  Patterns decayed:        {decayed:>4d}",
            f"  Graph nodes updated:     {graph_nodes:>4d}",
            "-" * 55,
            f"  Total duration:          {total_duration_ms:>8.1f} ms",
            "=" * 55,
        ]
        return "\n".join(lines)

    # ── Serialization ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "cycle_number": self.cycle_number,
            "pipeline_id": self.pipeline_id,
            "stages": [s.to_dict() for s in self.stages],
            "total_duration_ms": self.total_duration_ms,
            "total_experiences": self.total_experiences,
            "total_patterns": self.total_patterns,
            "reinforced_patterns": self.reinforced_patterns,
            "decayed_patterns": self.decayed_patterns,
            "graph_nodes_updated": self.graph_nodes_updated,
            "graph_edges_updated": self.graph_edges_updated,
            "overall_success": self.overall_success,
            "failed_stages": self.failed_stages,
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _find_stage(stages: list[StageResult], stage: PipelineStage) -> StageResult | None:
    """查找指定阶段的结果."""
    for s in stages:
        if s.stage == stage:
            return s
    return None


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "PipelineStage",
    "StageResult",
    "ConsolidationReport",
]