"""E11.4.2 — Mutation Planner。

VisionDecision → VisionMutationPlan。

核心流程：
  1. 从 VisionDecision 提取 mutation_instructions
  2. 通过 GeneMapper 映射到 Genome 基因名
  3. 结合当前 Genome 值计算 new_value
  4. 通过 ConstraintEngine 约束变化量
  5. 生成 VisionMutationPlan
"""

from __future__ import annotations

import logging
from typing import Any

from ..decision.models import VisionDecision, MutationInstruction
from .models import MutationGeneChange, VisionMutationPlan
from .gene_mapper import GeneMapper
from .constraint import ConstraintEngine

logger = logging.getLogger(__name__)


class MutationPlanner:
    """突变计划生成器。

    VisionDecision + Genome → VisionMutationPlan。

    Attributes:
        mapper:      GeneMapper（Pattern → Genome Gene）
        constraints:  ConstraintEngine（突变约束）
        plan_count:   已生成计划数
    """

    def __init__(
        self,
        constraints: ConstraintEngine | None = None,
    ) -> None:
        self._mapper = GeneMapper()
        self._constraints = constraints or ConstraintEngine()
        self._plan_count: int = 0

    # ── Create Plan ──────────────────────────────────────

    def create_plan(
        self,
        decision: VisionDecision,
        genome: dict[str, float] | None = None,
    ) -> VisionMutationPlan:
        """从 VisionDecision 创建 VisionMutationPlan。

        Args:
            decision: 视觉决策
            genome:   当前 Genome 值 {gene_name: value}

        Returns:
            VisionMutationPlan
        """
        genome = genome or {}
        changes: list[MutationGeneChange] = []

        for instruction in decision.mutation_instructions:
            change = self._build_change(instruction, genome)
            if change is not None:
                changes.append(change)

        # 优先级
        priority = self._determine_priority(decision.confidence, changes)

        # 预期影响
        expected_impact = self._describe_impact(changes)

        # 总体置信度
        total_confidence = self._compute_total_confidence(changes, decision.confidence)

        # 总结
        summary = self._build_summary(changes, decision)

        self._plan_count += 1

        return VisionMutationPlan(
            asset_id=decision.creative_asset_id,
            source_decision_id=decision.decision_id,
            changes=changes,
            priority=priority,
            expected_impact=expected_impact,
            total_confidence=total_confidence,
            summary=summary,
        )

    def create_plan_batch(
        self,
        decisions: list[VisionDecision],
        genomes: dict[str, dict[str, float]] | None = None,
    ) -> list[VisionMutationPlan]:
        """批量创建突变计划。"""
        genomes = genomes or {}
        return [
            self.create_plan(d, genomes.get(d.creative_asset_id))
            for d in decisions
        ]

    # ── Stats ────────────────────────────────────────────

    @property
    def plan_count(self) -> int:
        return self._plan_count

    # ── Internal ────────────────────────────────────────

    def _build_change(
        self,
        instruction: MutationInstruction,
        genome: dict[str, float],
    ) -> MutationGeneChange | None:
        """从 MutationInstruction 构建 MutationGeneChange。"""
        # 1. 映射到 Genome 基因名
        genome_gene = self._mapper.intermediate_to_genome_gene(
            instruction.target_gene
        )
        if genome_gene is None:
            # 尝试直接使用 target_gene
            genome_gene = instruction.target_gene

        # 2. 获取当前值
        old_value = genome.get(genome_gene, 0.5)

        # 3. 计算目标值
        raw_target = self._compute_raw_target(
            old_value, instruction.operator, instruction.magnitude
        )

        # 4. 应用约束
        new_value = self._constraints.apply(
            gene_name=genome_gene,
            old_value=old_value,
            target_value=raw_target,
            operator=instruction.operator,
        )

        # 5. 如果变化太小，跳过
        if abs(new_value - old_value) < 0.01:
            return None

        return MutationGeneChange(
            gene_name=genome_gene,
            old_value=old_value,
            new_value=new_value,
            operator=instruction.operator,
            confidence=instruction.magnitude,
            reason=instruction.description,
            source_pattern=instruction.source_pattern,
        )

    @staticmethod
    def _compute_raw_target(
        current: float,
        operator: str,
        magnitude: float,
    ) -> float:
        """计算原始目标值（未约束）。"""
        if operator == "increase":
            return current + magnitude
        if operator == "decrease":
            return current - magnitude
        if operator == "set":
            return max(magnitude, current)
        return current

    @staticmethod
    def _determine_priority(
        confidence: float,
        changes: list[MutationGeneChange],
    ) -> str:
        if not changes:
            return "low"
        if confidence >= 0.7 and len(changes) >= 2:
            return "high"
        if confidence >= 0.5:
            return "medium"
        return "low"

    @staticmethod
    def _describe_impact(changes: list[MutationGeneChange]) -> str:
        if not changes:
            return "No changes planned"
        genes = [c.gene_name for c in changes[:3]]
        return (
            f"Expected to improve visual performance by "
            f"adjusting: {', '.join(genes)}"
        )

    @staticmethod
    def _compute_total_confidence(
        changes: list[MutationGeneChange],
        decision_confidence: float,
    ) -> float:
        if not changes:
            return 0.0
        avg_change_conf = sum(c.confidence for c in changes) / len(changes)
        return round((avg_change_conf * 0.6 + decision_confidence * 0.4), 3)

    @staticmethod
    def _build_summary(
        changes: list[MutationGeneChange],
        decision: VisionDecision,
    ) -> str:
        if not changes:
            return "No viable mutations found"

        parts = []
        for c in changes[:3]:
            parts.append(
                f"{c.gene_name}: {c.old_value:.2f}→{c.new_value:.2f} "
                f"({c.operator})"
            )

        return (
            f"Mutation plan for {decision.creative_asset_id}: "
            + "; ".join(parts)
        )

    def __repr__(self) -> str:
        return f"MutationPlanner(plans={self._plan_count})"