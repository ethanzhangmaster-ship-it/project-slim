"""E14.4.2.3 Creative Planner — 创意执行计划.

将 Creative Strategy 转化为可执行的 CreativePlan:

  输入: CreativeStrategy (策略类型 + 基因变异指令)
  输出: CreativePlan (population_size, mutation_config, generation_count, 优先级)

核心能力:
  - 策略→计划: 将策略转化为具体的执行计划
  - 种群规模: 根据策略类型和置信度确定生成数量
  - 变异配置: 生成每个基因的变异比例配置
  - 代际规划: 确定迭代代数和验证参数
  - 优先级排序: 确保高优先级策略优先执行

设计原则:
  - 确定性计划生成
  - 与 E11 Evolution Engine 兼容
  - 可追踪、可回滚
  - 支持批量计划和优先级排序
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .strategy import (
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
)
from .opportunity import OpportunityPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class PlanStatus(str, Enum):
    """计划状态."""
    DRAFT = "draft"            # 草稿
    READY = "ready"            # 就绪
    EXECUTING = "executing"    # 执行中
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消


class ExperimentType(str, Enum):
    """实验类型."""
    A_B_TEST = "ab_test"               # A/B 测试
    MULTI_VARIANT = "multi_variant"     # 多变体测试
    EXPLORATION = "exploration"         # 探索性实验
    SCALE_UP = "scale_up"              # 扩量
    CONCEPT_TEST = "concept_test"       # 概念测试


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class MutationConfig:
    """单个基因的变异配置.

    Attributes:
        gene_category: 基因类别
        mutation_action: 变异动作
        mutation_rate: 变异比例 (0-1)
        target_values: 目标值列表
        preserve_original: 是否保留原始值
    """
    gene_category: str = ""
    mutation_action: GeneMutationAction = GeneMutationAction.KEEP
    mutation_rate: float = 0.0
    target_values: list[str] = field(default_factory=list)
    preserve_original: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "mutation_action": self.mutation_action.value,
            "mutation_rate": self.mutation_rate,
            "target_values": self.target_values,
            "preserve_original": self.preserve_original,
        }


@dataclass
class ExperimentConfig:
    """实验配置.

    Attributes:
        experiment_type: 实验类型
        control_group_size: 对照组大小
        variant_group_size: 变体组大小
        success_criteria: 成功标准
        min_duration_days: 最少运行天数
        max_budget: 最大预算
        significance_level: 显著性水平
    """
    experiment_type: ExperimentType = ExperimentType.A_B_TEST
    control_group_size: int = 1
    variant_group_size: int = 5
    success_criteria: dict[str, float] = field(default_factory=dict)
    min_duration_days: int = 3
    max_budget: float = 0.0
    significance_level: float = 0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_type": self.experiment_type.value,
            "control_group_size": self.control_group_size,
            "variant_group_size": self.variant_group_size,
            "success_criteria": self.success_criteria,
            "min_duration_days": self.min_duration_days,
            "max_budget": self.max_budget,
            "significance_level": self.significance_level,
        }


@dataclass
class CreativePlan:
    """创意执行计划 — 策略→执行.

    Attributes:
        plan_id: 计划 ID
        strategy_id: 关联策略 ID
        creative_id: 目标创意 ID
        strategy_type: 策略类型
        status: 计划状态
        priority: 优先级
        population_size: 种群大小 (生成变体数量)
        mutation_configs: 基因变异配置列表
        experiment_config: 实验配置
        generation_count: 迭代代数
        keep_original: 是否保留原始素材
        expected_impact: 预期影响
        confidence: 置信度
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    creative_id: str = ""
    strategy_type: CreativeStrategyType = CreativeStrategyType.UNKNOWN
    status: PlanStatus = PlanStatus.DRAFT
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    population_size: int = 5
    mutation_configs: list[MutationConfig] = field(default_factory=list)
    experiment_config: ExperimentConfig | None = None
    generation_count: int = 1
    keep_original: bool = True
    expected_impact: str = ""
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "creative_id": self.creative_id,
            "strategy_type": self.strategy_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "population_size": self.population_size,
            "mutation_configs": [m.to_dict() for m in self.mutation_configs],
            "experiment_config": self.experiment_config.to_dict() if self.experiment_config else None,
            "generation_count": self.generation_count,
            "keep_original": self.keep_original,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def total_variants(self) -> int:
        """总变体数 (含原始)."""
        return self.population_size + (1 if self.keep_original else 0)

    @property
    def is_ready(self) -> bool:
        return self.status == PlanStatus.READY

    @property
    def is_completed(self) -> bool:
        return self.status == PlanStatus.COMPLETED

    @property
    def summary(self) -> str:
        parts = [
            f"[{self.priority.value.upper()}] {self.strategy_type.value}",
            f"pop={self.population_size}",
            f"gen={self.generation_count}",
        ]
        if self.keep_original:
            parts.append("keep_original")
        return " ".join(parts)


@dataclass
class BatchPlan:
    """批量计划 — 多个 CreativePlan 的组合.

    Attributes:
        batch_id: 批次 ID
        plans: 计划列表
        total_variants: 总变体数
        total_budget: 总预算
        sorted_plans: 排序后的计划 (按优先级)
        summary: 批次摘要
        created_at: 创建时间
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plans: list[CreativePlan] = field(default_factory=list)
    total_variants: int = 0
    total_budget: float = 0.0
    sorted_plans: list[CreativePlan] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "plans": [p.to_dict() for p in self.plans],
            "total_variants": self.total_variants,
            "total_budget": self.total_budget,
            "sorted_plans": [p.to_dict() for p in self.sorted_plans],
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def plan_count(self) -> int:
        return len(self.plans)


# ═══════════════════════════════════════════════════════════════
# Default Configs
# ═══════════════════════════════════════════════════════════════

# 策略类型 → 默认种群大小
DEFAULT_POPULATION_SIZE: dict[CreativeStrategyType, int] = {
    CreativeStrategyType.REFRESH_HOOK: 5,
    CreativeStrategyType.CHANGE_VISUAL_STYLE: 5,
    CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: 5,
    CreativeStrategyType.CHANGE_EMOTION: 5,
    CreativeStrategyType.COPY_WINNER_DNA: 10,
    CreativeStrategyType.EXPLORE_NEW_DNA: 10,
    CreativeStrategyType.OPTIMIZE_OPENING: 5,
    CreativeStrategyType.SCALE_WINNER: 3,
    CreativeStrategyType.EXPLORE_NEW_AUDIENCE: 5,
    CreativeStrategyType.TEST_NEW_CONCEPT: 5,
    CreativeStrategyType.REFRESH_CREATIVE: 10,
}

# 策略类型 → 默认代际数
DEFAULT_GENERATION_COUNT: dict[CreativeStrategyType, int] = {
    CreativeStrategyType.COPY_WINNER_DNA: 3,
    CreativeStrategyType.EXPLORE_NEW_DNA: 2,
    CreativeStrategyType.REFRESH_CREATIVE: 2,
}

# 策略类型 → 实验类型
STRATEGY_TO_EXPERIMENT: dict[CreativeStrategyType, ExperimentType] = {
    CreativeStrategyType.REFRESH_HOOK: ExperimentType.A_B_TEST,
    CreativeStrategyType.CHANGE_VISUAL_STYLE: ExperimentType.A_B_TEST,
    CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: ExperimentType.MULTI_VARIANT,
    CreativeStrategyType.CHANGE_EMOTION: ExperimentType.A_B_TEST,
    CreativeStrategyType.COPY_WINNER_DNA: ExperimentType.MULTI_VARIANT,
    CreativeStrategyType.EXPLORE_NEW_DNA: ExperimentType.EXPLORATION,
    CreativeStrategyType.OPTIMIZE_OPENING: ExperimentType.A_B_TEST,
    CreativeStrategyType.SCALE_WINNER: ExperimentType.SCALE_UP,
    CreativeStrategyType.EXPLORE_NEW_AUDIENCE: ExperimentType.EXPLORATION,
    CreativeStrategyType.TEST_NEW_CONCEPT: ExperimentType.CONCEPT_TEST,
    CreativeStrategyType.REFRESH_CREATIVE: ExperimentType.MULTI_VARIANT,
}


# ═══════════════════════════════════════════════════════════════
# Creative Planner
# ═══════════════════════════════════════════════════════════════


class CreativePlanner:
    """创意规划器 — 将策略转化为执行计划.

    职责:
      1. 策略→计划: 将策略转化为具体的执行计划
      2. 种群规模: 根据策略类型和置信度确定生成数量
      3. 变异配置: 生成每个基因的变异比例
      4. 实验设计: 确定实验类型和验证参数
      5. 优先级排序: 确保高优先级策略优先执行

    用法:
        planner = CreativePlanner()
        plan = planner.plan(strategy)
        batch = planner.plan_batch(strategies)
    """

    def __init__(self):
        self._plans: dict[str, CreativePlan] = {}
        self._history: list[CreativePlan] = []

    # ── 核心规划 ──────────────────────────────────────────────

    def plan(self, strategy: CreativeStrategy) -> CreativePlan:
        """根据策略生成执行计划.

        Args:
            strategy: 创意策略

        Returns:
            CreativePlan: 执行计划
        """
        # 1. 确定种群大小
        population_size = self._determine_population_size(strategy)

        # 2. 生成变异配置
        mutation_configs = self._build_mutation_configs(strategy)

        # 3. 确定实验配置
        experiment_config = self._build_experiment_config(strategy)

        # 4. 确定代际数
        generation_count = self._determine_generation_count(strategy)

        # 5. 是否保留原始
        keep_original = strategy.strategy_type != CreativeStrategyType.COPY_WINNER_DNA

        plan = CreativePlan(
            strategy_id=strategy.strategy_id,
            creative_id=strategy.target_creative_id,
            strategy_type=strategy.strategy_type,
            status=PlanStatus.READY,
            priority=strategy.priority,
            population_size=population_size,
            mutation_configs=mutation_configs,
            experiment_config=experiment_config,
            generation_count=generation_count,
            keep_original=keep_original,
            expected_impact=strategy.expected_impact,
            confidence=strategy.confidence,
        )

        self._plans[plan.plan_id] = plan
        self._history.append(plan)
        return plan

    def plan_batch(
        self,
        strategies: list[CreativeStrategy],
        max_total_variants: int = 50,
    ) -> BatchPlan:
        """批量规划.

        Args:
            strategies: 策略列表
            max_total_variants: 最大总变体数

        Returns:
            BatchPlan: 批量计划
        """
        plans = [self.plan(s) for s in strategies]

        # 按优先级排序
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3,
        }
        sorted_plans = sorted(plans, key=lambda p: priority_order.get(p.priority, 99))

        # 如果总数超过限制，裁剪低优先级计划
        total_variants = sum(p.total_variants for p in sorted_plans)
        if total_variants > max_total_variants:
            # 保留高优先级
            kept = []
            current = 0
            for p in sorted_plans:
                if current + p.total_variants <= max_total_variants:
                    kept.append(p)
                    current += p.total_variants
                else:
                    p.status = PlanStatus.CANCELLED
            sorted_plans = kept
            total_variants = current

        summary_parts = []
        critical_count = sum(1 for p in plans if p.priority == OpportunityPriority.CRITICAL)
        high_count = sum(1 for p in plans if p.priority == OpportunityPriority.HIGH)
        if critical_count:
            summary_parts.append(f"{critical_count} 个紧急计划")
        if high_count:
            summary_parts.append(f"{high_count} 个高优计划")
        summary_parts.append(f"总变体: {total_variants}")

        return BatchPlan(
            plans=plans,
            total_variants=total_variants,
            sorted_plans=sorted_plans,
            summary=" | ".join(summary_parts),
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _determine_population_size(self, strategy: CreativeStrategy) -> int:
        """确定种群大小."""
        base = DEFAULT_POPULATION_SIZE.get(
            strategy.strategy_type,
            5,
        )
        # 置信度调整
        if strategy.confidence >= 0.8:
            base = int(base * 1.2)
        elif strategy.confidence < 0.5:
            base = max(3, int(base * 0.7))
        return min(base, 20)

    def _build_mutation_configs(
        self,
        strategy: CreativeStrategy,
    ) -> list[MutationConfig]:
        """构建变异配置."""
        configs = []
        for mutation in strategy.mutation_plan:
            mutation_rate = self._calculate_mutation_rate(mutation)
            configs.append(MutationConfig(
                gene_category=mutation.gene_category,
                mutation_action=mutation.action,
                mutation_rate=mutation_rate,
                target_values=mutation.target_values,
                preserve_original=mutation.action != GeneMutationAction.CHANGE or mutation.gene_category != "hook",
            ))
        return configs

    def _calculate_mutation_rate(self, mutation: GeneMutation) -> float:
        """计算变异比例."""
        if mutation.action == GeneMutationAction.KEEP:
            return 0.0
        elif mutation.action == GeneMutationAction.CHANGE:
            return 0.30
        elif mutation.action == GeneMutationAction.EXPLORE:
            return 0.40
        elif mutation.action == GeneMutationAction.BOOST:
            return 0.20
        elif mutation.action == GeneMutationAction.REDUCE:
            return 0.10
        return 0.0

    def _build_experiment_config(
        self,
        strategy: CreativeStrategy,
    ) -> ExperimentConfig:
        """构建实验配置."""
        experiment_type = STRATEGY_TO_EXPERIMENT.get(
            strategy.strategy_type,
            ExperimentType.A_B_TEST,
        )

        success_criteria = {
            "min_roas": 1.0,
            "min_ctr_improvement": 0.10,
            "max_fatigue": 0.5,
        }

        if strategy.strategy_type == CreativeStrategyType.SCALE_WINNER:
            success_criteria = {"min_roas": 1.5, "max_fatigue": 0.3}
        elif strategy.strategy_type == CreativeStrategyType.EXPLORE_NEW_DNA:
            success_criteria = {"min_roas": 0.8, "min_ctr": 0.015}

        max_budget = 0.0
        if strategy.priority == OpportunityPriority.CRITICAL:
            max_budget = 2000.0
        elif strategy.priority == OpportunityPriority.HIGH:
            max_budget = 1000.0
        else:
            max_budget = 500.0

        return ExperimentConfig(
            experiment_type=experiment_type,
            success_criteria=success_criteria,
            max_budget=max_budget,
        )

    def _determine_generation_count(self, strategy: CreativeStrategy) -> int:
        """确定代际数."""
        default = DEFAULT_GENERATION_COUNT.get(strategy.strategy_type, 1)
        if strategy.priority == OpportunityPriority.CRITICAL:
            default = max(default, 2)
        return min(default, 5)

    # ── 计划管理 ──────────────────────────────────────────────

    def get_plan(self, plan_id: str) -> CreativePlan | None:
        return self._plans.get(plan_id)

    def update_status(self, plan_id: str, status: PlanStatus) -> bool:
        plan = self._plans.get(plan_id)
        if plan is None:
            return False
        plan.status = status
        if status == PlanStatus.EXECUTING:
            plan.started_at = datetime.now(timezone.utc).isoformat()
        elif status in (PlanStatus.COMPLETED, PlanStatus.FAILED):
            plan.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    def get_ready_plans(self) -> list[CreativePlan]:
        return [p for p in self._plans.values() if p.is_ready]

    def get_executing_plans(self) -> list[CreativePlan]:
        return [p for p in self._plans.values() if p.status == PlanStatus.EXECUTING]

    def get_completed_plans(self) -> list[CreativePlan]:
        return [p for p in self._plans.values() if p.is_completed]

    def get_plans_by_creative(self, creative_id: str) -> list[CreativePlan]:
        return [p for p in self._plans.values() if p.creative_id == creative_id]

    # ── 查询 ──────────────────────────────────────────────────

    def get_history(self, n: int = 20) -> list[CreativePlan]:
        return self._history[-n:]

    def stats(self) -> dict[str, Any]:
        total = len(self._plans)
        if total == 0:
            return {"total": 0}
        status_counts: dict[str, int] = {}
        for p in self._plans.values():
            s = p.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total": total,
            "by_status": status_counts,
            "ready": len(self.get_ready_plans()),
            "executing": len(self.get_executing_plans()),
            "completed": len(self.get_completed_plans()),
            "total_variants": sum(p.total_variants for p in self._plans.values()),
        }

    def reset(self) -> None:
        self._plans.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_planner() -> CreativePlanner:
    """创建默认规划器."""
    return CreativePlanner()