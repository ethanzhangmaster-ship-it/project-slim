"""E11.4.3 — Mutation Executor。

将 GenomeMutationTask 应用到 Genome dict 上。

核心职责：
  1. 将基因突变应用到 genome dict
  2. 验证突变合法性（通过 ConstraintEngine）
  3. 支持回滚（保存原始值）
  4. 批量应用
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from ..mutation.constraint import ConstraintEngine
from ..mutation.models import VisionMutationPlan
from .models import GeneMutation, GenomeMutationTask

logger = logging.getLogger(__name__)


class MutationExecutor:
    """Genome 突变执行器。

    将 GenomeMutationTask 中的基因突变应用到 genome dict。

    Attributes:
        constraints:       ConstraintEngine（突变约束）
        applied_count:     已应用任务数
        failed_count:      失败任务数
        rolled_back_count: 回滚任务数
    """

    def __init__(
        self,
        constraints: ConstraintEngine | None = None,
    ) -> None:
        self._constraints = constraints or ConstraintEngine()
        self._applied_count: int = 0
        self._failed_count: int = 0
        self._rolled_back_count: int = 0

    # ── 核心操作 ──────────────────────────────────────

    def apply(
        self,
        task: GenomeMutationTask,
        genome: dict[str, Any],
    ) -> dict[str, Any]:
        """将突变任务应用到 genome dict。

        Args:
            task:   突变任务
            genome: 当前 genome dict（含 genes 字段）

        Returns:
            突变后的 genome dict（浅拷贝 + 基因修改）
        """
        # 保存原始值用于回滚
        original = copy.deepcopy(genome)

        try:
            genes = genome.get("genes", {})
            if not isinstance(genes, dict):
                task.mark_failed("genome.genes is not a dict")
                return genome

            for mutation in task.gene_mutations:
                self._apply_single_mutation(genes, mutation)

            genome["genes"] = genes

            # 记录 lineage
            if "parent_ids" not in genome:
                genome["parent_ids"] = []
            if genome.get("genome_id") and genome["genome_id"] not in genome["parent_ids"]:
                genome["parent_ids"].append(genome["genome_id"])

            # 记录 mutation_count
            genome["mutation_count"] = genome.get("mutation_count", 0) + len(task.gene_mutations)

            # 记录 metadаta
            if "metadata" not in genome:
                genome["metadata"] = {}
            genome["metadata"]["_last_mutation_task_id"] = task.task_id
            genome["metadata"]["_last_mutation_source"] = task.source_plan_id
            genome["metadata"]["_rollback_snapshot"] = original

            task.mark_applied()
            self._applied_count += 1

            return genome

        except Exception as e:
            task.mark_failed(str(e))
            self._failed_count += 1
            logger.error(f"Failed to apply mutation task {task.task_id}: {e}")
            return original

    def apply_batch(
        self,
        tasks: list[GenomeMutationTask],
        genomes: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """批量应用突变任务到多个 genome。

        Args:
            tasks:   突变任务列表
            genomes: genome_id → genome dict 映射

        Returns:
            更新后的 genome_id → genome dict 映射
        """
        result = dict(genomes)
        for task in tasks:
            gid = task.genome_id
            if gid not in result:
                task.mark_failed(f"genome {gid} not found")
                self._failed_count += 1
                continue
            result[gid] = self.apply(task, result[gid])
        return result

    def validate(
        self,
        task: GenomeMutationTask,
        genome: dict[str, Any],
    ) -> bool:
        """验证突变任务是否合法（干运行，不修改 genome）。

        Args:
            task:   突变任务
            genome: 当前 genome dict

        Returns:
            是否全部合法
        """
        genes = genome.get("genes", {})
        if not isinstance(genes, dict):
            return False

        for mutation in task.gene_mutations:
            old_value = genes.get(mutation.gene_name, mutation.old_value)
            if not self._constraints.validate(
                mutation.gene_name,
                old_value,
                mutation.new_value,
            ):
                return False
        return True

    def rollback(
        self,
        task: GenomeMutationTask,
        genome: dict[str, Any],
    ) -> dict[str, Any]:
        """回滚突变任务，恢复到原始 genome。

        Args:
            task:   已应用的突变任务
            genome: 当前 genome dict

        Returns:
            回滚后的 genome dict
        """
        if not task.is_applied:
            return genome

        snapshot = genome.get("metadata", {}).get("_rollback_snapshot")
        if snapshot is None:
            logger.warning(f"No rollback snapshot for task {task.task_id}")
            return genome

        self._rolled_back_count += 1
        task.status = "pending"
        task.error_message = "rolled back"

        return snapshot

    # ── 内部 ──────────────────────────────────────────

    def _apply_single_mutation(
        self,
        genes: dict[str, Any],
        mutation: GeneMutation,
    ) -> None:
        """应用单基因突变到 genes dict。

        使用 ConstraintEngine 验证并约束变化量。
        """
        old_value = genes.get(mutation.gene_name, 0.5)

        # 通过约束引擎计算安全值
        safe_value = self._constraints.apply(
            gene_name=mutation.gene_name,
            old_value=old_value,
            target_value=mutation.new_value,
            operator=mutation.operator,
        )

        genes[mutation.gene_name] = safe_value

    # ── Stats ──────────────────────────────────────────

    @property
    def applied_count(self) -> int:
        return self._applied_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    @property
    def rolled_back_count(self) -> int:
        return self._rolled_back_count

    def get_stats(self) -> dict[str, int]:
        return {
            "applied": self._applied_count,
            "failed": self._failed_count,
            "rolled_back": self._rolled_back_count,
        }

    def __repr__(self) -> str:
        return (
            f"MutationExecutor(applied={self._applied_count}, "
            f"failed={self._failed_count}, "
            f"rolled_back={self._rolled_back_count})"
        )