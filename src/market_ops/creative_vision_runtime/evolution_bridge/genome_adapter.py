"""E11.4.3 — Genome Adapter。

VisionMutationPlan → GenomeMutationTask 转换器。

核心职责：
  1. 将 VisionMutationPlan.changes (MutationGeneChange) 映射为 GeneMutation
  2. 保留 lineage（parent plan ID）
  3. 生成统一优先级和置信度
  4. 支持批量转换
"""

from __future__ import annotations

import logging
from typing import Any

from ..mutation.models import VisionMutationPlan, MutationGeneChange
from .models import GeneMutation, GenomeMutationTask

logger = logging.getLogger(__name__)


class GenomeAdapter:
    """VisionMutationPlan → GenomeMutationTask 适配器。

    将视觉驱动的突变计划转换为 Genome 级别的突变任务。

    Attributes:
        task_count: 已创建任务数
    """

    def __init__(self) -> None:
        self._task_count: int = 0

    # ── 核心转换 ──────────────────────────────────────

    def to_mutation_task(
        self,
        plan: VisionMutationPlan,
        genome_id: str = "",
        genome_context: dict[str, Any] | None = None,
    ) -> GenomeMutationTask:
        """将 VisionMutationPlan 转换为 GenomeMutationTask。

        Args:
            plan:           视觉突变计划
            genome_id:      目标 Genome ID（为空则使用 plan.asset_id）
            genome_context: 可选的 Genome 上下文（用于补充 old_value）

        Returns:
            GenomeMutationTask
        """
        genome_context = genome_context or {}
        gene_mutations = self._convert_changes(plan.changes, genome_context)

        task = GenomeMutationTask(
            genome_id=genome_id or plan.asset_id,
            asset_id=plan.asset_id,
            source_plan_id=plan.plan_id,
            gene_mutations=gene_mutations,
            priority=plan.priority,
            total_confidence=plan.total_confidence,
            summary=plan.summary,
        )

        self._task_count += 1
        return task

    def to_mutation_tasks(
        self,
        plans: list[VisionMutationPlan],
        genome_map: dict[str, str] | None = None,
        genome_contexts: dict[str, dict[str, Any]] | None = None,
    ) -> list[GenomeMutationTask]:
        """批量转换 VisionMutationPlan → GenomeMutationTask。

        Args:
            plans:           视觉突变计划列表
            genome_map:      asset_id → genome_id 映射
            genome_contexts: genome_id → genome_context 映射

        Returns:
            GenomeMutationTask 列表
        """
        genome_map = genome_map or {}
        genome_contexts = genome_contexts or {}

        tasks: list[GenomeMutationTask] = []
        for plan in plans:
            gid = genome_map.get(plan.asset_id, plan.asset_id)
            ctx = genome_contexts.get(gid, {})
            task = self.to_mutation_task(plan, genome_id=gid, genome_context=ctx)
            tasks.append(task)

        return tasks

    # ── 内部 ──────────────────────────────────────────

    @staticmethod
    def _convert_changes(
        changes: list[MutationGeneChange],
        genome_context: dict[str, Any],
    ) -> list[GeneMutation]:
        """将 MutationGeneChange 列表转换为 GeneMutation 列表。

        如果 genome_context 提供了当前基因值，则使用它作为 old_value。
        """
        gene_mutations: list[GeneMutation] = []
        for change in changes:
            old_value = genome_context.get(change.gene_name, change.old_value)
            gene_mutations.append(GeneMutation(
                gene_name=change.gene_name,
                old_value=old_value,
                new_value=change.new_value,
                operator=change.operator,
                confidence=change.confidence,
                reason=change.reason,
                source_pattern=change.source_pattern,
            ))
        return gene_mutations

    # ── Stats ──────────────────────────────────────────

    @property
    def task_count(self) -> int:
        return self._task_count

    def __repr__(self) -> str:
        return f"GenomeAdapter(tasks={self._task_count})"