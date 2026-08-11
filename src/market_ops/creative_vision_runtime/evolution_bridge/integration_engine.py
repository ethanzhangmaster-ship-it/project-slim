"""E11.4.3 — Evolution Integration Engine。

统一入口：VisionMutationPlan → Genome Mutation → V5 Engine。

完整链路：
  VisionMutationPlan
    → GenomeAdapter.to_mutation_task()
    → GenomeMutationTask
    → MutationExecutor.apply()
    → mutated genome dict
    → V5 GenomeManager.create() / update()

连接 V5 Mutation Engine 的方式：
  - 通过 GenomeMutationTask 作为中间契约
  - V5 GenomeManager 接收 mutated genome dict 并创建/更新 Genome
  - 不直接依赖 V5 模块（通过 genome dict 解耦）
"""

from __future__ import annotations

import logging
from typing import Any

from ..mutation.models import VisionMutationPlan
from ..mutation.constraint import ConstraintEngine
from ..mutation.mutation_planner import MutationPlanner
from .models import GeneMutation, GenomeMutationTask
from .genome_adapter import GenomeAdapter
from .mutation_executor import MutationExecutor

logger = logging.getLogger(__name__)


class EvolutionIntegrationEngine:
    """E11.4 Vision Runtime → V5 Evolution Engine 集成引擎。

    统一入口，串联 VisionMutationPlan → Genome Mutation → V5 Engine。

    Attributes:
        adapter:         GenomeAdapter（Plan → Task）
        executor:        MutationExecutor（Task → Genome）
        planner:         MutationPlanner（Decision → Plan）
        constraints:     ConstraintEngine（突变约束）
        evolve_count:    已执行进化次数
    """

    def __init__(
        self,
        constraints: ConstraintEngine | None = None,
        planner: MutationPlanner | None = None,
    ) -> None:
        self._adapter = GenomeAdapter()
        self._constraints = constraints or ConstraintEngine()
        self._executor = MutationExecutor(constraints=self._constraints)
        self._planner = planner or MutationPlanner(constraints=self._constraints)
        self._evolve_count: int = 0

    # ── 主入口：evolve_from_vision ─────────────────────

    def evolve_from_vision(
        self,
        plan: VisionMutationPlan,
        genome: dict[str, Any],
    ) -> dict[str, Any]:
        """从 VisionMutationPlan 进化一个 genome。

        完整链路：
          VisionMutationPlan → GenomeMutationTask → apply → mutated genome

        Args:
            plan:   视觉突变计划（来自 E11.4.2 MutationPlanner）
            genome: 当前 genome dict

        Returns:
            进化后的 genome dict
        """
        # 1. 转换 Plan → Task
        genome_context = genome.get("genes", {})
        task = self._adapter.to_mutation_task(
            plan,
            genome_id=genome.get("genome_id", ""),
            genome_context=genome_context,
        )

        # 2. 验证
        if not self._executor.validate(task, genome):
            task.mark_failed("validation failed")
            logger.warning(f"Mutation task {task.task_id} failed validation")
            return genome

        # 3. 应用突变
        mutated = self._executor.apply(task, genome)

        self._evolve_count += 1
        return mutated

    def evolve_from_vision_batch(
        self,
        plans: list[VisionMutationPlan],
        genomes: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """批量进化多个 genome。

        Args:
            plans:   视觉突变计划列表
            genomes: genome_id → genome dict 映射

        Returns:
            更新后的 genome_id → genome dict 映射
        """
        # 1. 批量转换 Plan → Task
        tasks = self._adapter.to_mutation_tasks(
            plans,
            genome_contexts={
                gid: g.get("genes", {})
                for gid, g in genomes.items()
            },
        )

        # 2. 批量应用
        result = self._executor.apply_batch(tasks, genomes)

        self._evolve_count += len(tasks)
        return result

    # ── 连接 V5 GenomeManager ──────────────────────────

    def create_genome_from_plan(
        self,
        plan: VisionMutationPlan,
        name: str,
        generation: int = 0,
        base_genome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """从 VisionMutationPlan 创建新 genome（用于 V5 GenomeManager.create()）。

        在没有现有 genome 的情况下，从 plan 创建初始 genome。

        Args:
            plan:        视觉突变计划
            name:        Genome 名称
            generation:  代数
            base_genome: 基础 genome dict（可选，不提供则使用默认值）

        Returns:
            新 genome dict（可直接传给 V5 GenomeManager.create()）
        """
        import uuid
        from datetime import datetime, timezone

        # 基础基因值（默认 0.5）
        genes = {
            "hook_contrast": 0.5,
            "color_brightness": 0.5,
            "color_saturation": 0.5,
            "object_density": 0.5,
            "transition_speed": 0.5,
            "reward_reveal_curve": 0.5,
        }

        # 如果提供了基础 genome，使用其基因值
        if base_genome and base_genome.get("genes"):
            for k, v in base_genome["genes"].items():
                if k in genes:
                    genes[k] = float(v)

        genome = {
            "genome_id": str(uuid.uuid4())[:12],
            "name": name,
            "generation": generation,
            "genes": genes,
            "parent_ids": [],
            "mutation_count": 0,
            "metadata": {
                "source_plan_id": plan.plan_id,
                "source_asset_id": plan.asset_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # 应用 plan 的突变
        context = genome.get("genes", {})
        task = self._adapter.to_mutation_task(
            plan,
            genome_id=genome["genome_id"],
            genome_context=context,
        )

        if self._executor.validate(task, genome):
            genome = self._executor.apply(task, genome)

        self._evolve_count += 1
        return genome

    # ── 回滚 ──────────────────────────────────────────

    def rollback(
        self,
        genome: dict[str, Any],
    ) -> dict[str, Any]:
        """回滚 genome 到上次突变前的状态。

        Args:
            genome: 当前 genome dict

        Returns:
            回滚后的 genome dict
        """
        task_id = genome.get("metadata", {}).get("_last_mutation_task_id")
        if not task_id:
            logger.warning("No last mutation task found for rollback")
            return genome

        # 重建 task
        task = GenomeMutationTask(task_id=task_id)
        task.mark_applied()

        return self._executor.rollback(task, genome)

    # ── V5 集成 ───────────────────────────────────────

    def connect_to_v5(
        self,
        genome_manager: Any,
    ) -> None:
        """连接 V5 GenomeManager。

        注册事件处理器，使 E11.4.3 可以响应 V5 事件。

        Args:
            genome_manager: V5 GenomeManager 实例
        """
        try:
            genome_manager.on_event(self._on_v5_event)
            logger.info("Connected to V5 GenomeManager")
        except Exception as e:
            logger.error(f"Failed to connect to V5 GenomeManager: {e}")

    def _on_v5_event(self, event: Any) -> None:
        """处理 V5 EvolutionEvent。"""
        logger.debug(f"V5 event: {event.event_type} on {event.entity_id}")

    # ── Stats ──────────────────────────────────────────

    @property
    def evolve_count(self) -> int:
        return self._evolve_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "evolve_count": self._evolve_count,
            "adapter": {"task_count": self._adapter.task_count},
            "executor": self._executor.get_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionIntegrationEngine(evolve_count={self._evolve_count}, "
            f"tasks={self._adapter.task_count})"
        )