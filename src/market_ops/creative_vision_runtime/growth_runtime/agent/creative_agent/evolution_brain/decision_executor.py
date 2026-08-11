"""E14.6.1 Evolution Decision Executor — 进化决策执行器.

职责:
  1. 将 EvolutionPlan (E14.5.3) 转换为可执行的 EvolutionAction
  2. 连接 E14.5.4 AdaptiveMutation 和 E11 PopulationManager
  3. 执行进化动作，生成新的 CreativeGenome 并加入种群
  4. 验证、调度、追踪每个执行动作

核心概念:
  - EvolutionAction: 单个可执行进化动作 (e.g. CREATE_VARIANTS, MUTATE_GENE)
  - ExecutionResult: 动作执行结果 (生成的 Genome ID、种群 ID)
  - DecisionExecutor: 核心执行引擎

数据流:
  EvolutionPlan (E14.5.3)
       ↓
  DecisionExecutor.execute()
       ↓
  list[EvolutionAction]
       ↓
  E11 PopulationManager.add_genome()
       ↓
  ExecutionResult
       ↓
  E14.6.3 Experiment Controller (下一步)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
    EvolutionPlan,
    EvolutionGoal,
    GeneMutationPlan,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.adaptive_mutation import (
    AdaptiveMutationSelector,
    AdaptiveMutation,
)
from market_ops.e11.genome.schema import CreativeGenome, GenomeLineage
from market_ops.e11.evolution.population_manager import PopulationManager


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class ActionType(str, Enum):
    """进化动作类型."""
    CREATE_VARIANTS = "create_variants"     # 基于赢家模板生成变体
    MUTATE_GENE = "mutate_gene"            # 定向变异特定基因
    EXPLORE_NEW = "explore_new"            # 探索全新方向
    AMPLIFY_WINNER = "amplify_winner"      # 放大赢家基因
    SUPPRESS_LOSER = "suppress_loser"      # 抑制失败基因
    DIVERSIFY = "diversify"                # 增加多样性
    POPULATE = "populate"                  # 填充种群到目标大小


class ActionStatus(str, Enum):
    """动作执行状态."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionAction:
    """单个可执行进化动作.

    将抽象进化目标转化为具体可执行的动作指令.

    Attributes:
        action_id: 动作 ID
        action_type: 动作类型
        goal_id: 来源目标 ID
        gene_category: 目标基因类别
        mutation_direction: 变异方向 (目标基因值)
        count: 生成数量
        mutation_type: 变异类型 (replace / add / remove)
        mutation_source: 变异来源 (winner_pattern / exploration / diversity)
        expected_impact: 预期影响
        confidence: 置信度
        priority: 优先级
        plan_id: 来源计划 ID
        status: 执行状态
        created_at: 创建时间
    """
    action_id: str = field(default_factory=lambda: f"action_{uuid.uuid4().hex[:8]}")
    action_type: ActionType = ActionType.CREATE_VARIANTS
    goal_id: str = ""
    gene_category: str = ""
    mutation_direction: str = ""
    count: int = 1
    mutation_type: str = "replace"
    mutation_source: str = ""
    expected_impact: str = ""
    confidence: float = 0.0
    priority: int = 5
    plan_id: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "goal_id": self.goal_id,
            "gene_category": self.gene_category,
            "mutation_direction": self.mutation_direction,
            "count": self.count,
            "mutation_type": self.mutation_type,
            "mutation_source": self.mutation_source,
            "expected_impact": self.expected_impact,
            "confidence": round(self.confidence, 3),
            "priority": self.priority,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionAction:
        return cls(
            action_id=data.get("action_id", ""),
            action_type=ActionType(data.get("action_type", "create_variants")),
            goal_id=data.get("goal_id", ""),
            gene_category=data.get("gene_category", ""),
            mutation_direction=data.get("mutation_direction", ""),
            count=data.get("count", 1),
            mutation_type=data.get("mutation_type", "replace"),
            mutation_source=data.get("mutation_source", ""),
            expected_impact=data.get("expected_impact", ""),
            confidence=data.get("confidence", 0.0),
            priority=data.get("priority", 5),
            plan_id=data.get("plan_id", ""),
            status=ActionStatus(data.get("status", "pending")),
            created_at=data.get("created_at", ""),
        )


@dataclass
class ExecutionResult:
    """动作执行结果.

    Attributes:
        result_id: 结果 ID
        action_id: 对应动作 ID
        status: 执行状态
        genome_ids: 生成的基因组 ID 列表
        population_id: 所属种群 ID
        stats: 统计信息 (生成数、跳过数、失败数)
        error_message: 错误信息
        created_at: 创建时间
    """
    result_id: str = field(default_factory=lambda: f"result_{uuid.uuid4().hex[:8]}")
    action_id: str = ""
    status: ActionStatus = ActionStatus.PENDING
    genome_ids: list[str] = field(default_factory=list)
    population_id: str = ""
    stats: dict[str, int] = field(default_factory=dict)
    error_message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def generated_count(self) -> int:
        return len(self.genome_ids)

    @property
    def is_success(self) -> bool:
        return self.status == ActionStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "genome_ids": self.genome_ids,
            "population_id": self.population_id,
            "generated_count": self.generated_count,
            "stats": self.stats,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionResult:
        return cls(
            result_id=data.get("result_id", ""),
            action_id=data.get("action_id", ""),
            status=ActionStatus(data.get("status", "pending")),
            genome_ids=data.get("genome_ids", []),
            population_id=data.get("population_id", ""),
            stats=data.get("stats", {}),
            error_message=data.get("error_message", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class ExecutionReport:
    """执行报告 — 汇总多次执行结果.

    Attributes:
        report_id: 报告 ID
        plan_id: 来源计划 ID
        total_actions: 总动作数
        success_actions: 成功动作数
        failed_actions: 失败动作数
        total_genomes: 生成基因组总数
        population_id: 种群 ID
        results: 各动作结果列表
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    total_actions: int = 0
    success_actions: int = 0
    failed_actions: int = 0
    total_genomes: int = 0
    population_id: str = ""
    results: list[ExecutionResult] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "plan_id": self.plan_id,
            "total_actions": self.total_actions,
            "success_actions": self.success_actions,
            "failed_actions": self.failed_actions,
            "total_genomes": self.total_genomes,
            "population_id": self.population_id,
            "results": [r.to_dict() for r in self.results],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# DecisionExecutor — 核心引擎
# ═══════════════════════════════════════════════════════════

class DecisionExecutor:
    """进化决策执行器 — 将 EvolutionPlan 转换为可执行动作并执行.

    核心职责:
      1. 将 EvolutionPlan 的每个目标 + 变异计划组合为 EvolutionAction
      2. 按优先级排序动作，确保关键动作优先执行
      3. 调用 E11 PopulationManager 将生成的 Genome 加入种群
      4. 追踪每个动作的执行结果

    用法:
        executor = DecisionExecutor(population_manager)
        actions = executor.convert_plan(evolution_plan)
        result = executor.execute(actions, population_id="pop_001")
        print(f"生成 {result.generated_count} 个基因组")
    """

    # 目标类型到动作类型的映射
    GOAL_ACTION_MAP: dict[str, ActionType] = {
        "increase_diversity": ActionType.DIVERSIFY,
        "amplify_rising": ActionType.AMPLIFY_WINNER,
        "suppress_declining": ActionType.SUPPRESS_LOSER,
        "explore_new": ActionType.EXPLORE_NEW,
    }

    # 默认每个基因变异计划生成的基因组数量
    DEFAULT_COUNT_PER_PLAN = 5

    # 基因类别到槽位键的映射
    GENE_SLOT_KEYS = {
        "hook": "hook",
        "visual": "visual",
        "emotion": "emotion",
        "gameplay": "gameplay",
        "reward": "reward",
    }

    def __init__(
        self,
        population_manager: PopulationManager | None = None,
        adaptive_selector: AdaptiveMutationSelector | None = None,
        default_count: int = 5,
        min_confidence: float = 0.3,
    ):
        self._population_manager = population_manager or PopulationManager()
        self._adaptive_selector = adaptive_selector or AdaptiveMutationSelector()
        self._default_count = default_count
        self._min_confidence = min_confidence
        self._actions: dict[str, EvolutionAction] = {}
        self._results: dict[str, ExecutionResult] = {}

    # ── 核心: 计划 → 动作 ─────────────────────────────────

    def convert_plan(self, plan: EvolutionPlan) -> list[EvolutionAction]:
        """将 EvolutionPlan 转换为 EvolutionAction 列表.

        Args:
            plan: 进化计划

        Returns:
            list[EvolutionAction]: 可执行动作列表, 按优先级降序排列
        """
        actions: list[EvolutionAction] = []

        # 1. 为每个目标 + 变异计划组合生成动作
        for goal in plan.goals:
            # 找到该目标对应的变异计划
            related_plans = self._get_related_mutation_plans(goal, plan.mutation_plans)

            if related_plans:
                for mp in related_plans:
                    action = self._build_action_from_goal_and_plan(goal, mp, plan)
                    actions.append(action)
            else:
                # 没有变异计划但有目标 → 生成默认动作
                action = self._build_action_from_goal_only(goal, plan)
                actions.append(action)

        # 2. 为没有对应目标的变异计划生成动作
        covered_genes = {a.gene_category for a in actions}
        for mp in plan.mutation_plans:
            if mp.gene_category and mp.gene_category not in covered_genes:
                action = self._build_action_from_plan_only(mp, plan)
                actions.append(action)

        # 3. 如果种群大小不足，添加 POPULATE 动作
        if plan.target_population_size > 0:
            total_count = sum(a.count for a in actions)
            if total_count < plan.target_population_size:
                gap = plan.target_population_size - total_count
                actions.append(EvolutionAction(
                    action_type=ActionType.POPULATE,
                    goal_id="",
                    gene_category="",
                    mutation_direction="fill_population",
                    count=gap,
                    mutation_type="replace",
                    mutation_source="population_gap",
                    expected_impact=f"填充种群到 {plan.target_population_size}",
                    confidence=0.5,
                    priority=1,
                    plan_id=plan.plan_id,
                ))

        # 4. 按优先级降序排列
        actions.sort(key=lambda a: (-a.priority, -a.confidence))

        # 存储
        for a in actions:
            self._actions[a.action_id] = a

        return actions

    # ── 核心: 执行动作 ────────────────────────────────────

    def execute(
        self,
        actions: list[EvolutionAction],
        population_id: str = "",
        generation: int = 1,
        base_genomes: list[CreativeGenome] | None = None,
    ) -> ExecutionReport:
        """执行所有动作, 生成基因组并加入种群.

        Args:
            actions: 动作列表
            population_id: 种群 ID (空则自动创建)
            generation: 代际编号
            base_genomes: 基础基因组 (用于变体生成)

        Returns:
            ExecutionReport: 执行报告
        """
        if not population_id:
            population_id = f"pop_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        results: list[ExecutionResult] = []
        total_genomes = 0
        success_count = 0
        failed_count = 0

        plan_id = actions[0].plan_id if actions else ""

        for action in actions:
            result = self._execute_single(action, population_id, generation, base_genomes)
            results.append(result)
            self._results[result.result_id] = result

            total_genomes += result.generated_count
            if result.is_success:
                success_count += 1
            elif result.status == ActionStatus.FAILED:
                failed_count += 1

        summary = (
            f"执行 {len(actions)} 个动作，成功 {success_count}，"
            f"失败 {failed_count}，生成 {total_genomes} 个基因组"
        )

        return ExecutionReport(
            plan_id=plan_id,
            total_actions=len(actions),
            success_actions=success_count,
            failed_actions=failed_count,
            total_genomes=total_genomes,
            population_id=population_id,
            results=results,
            summary=summary,
        )

    def execute_single_action(
        self,
        action: EvolutionAction,
        population_id: str = "",
        generation: int = 1,
        base_genomes: list[CreativeGenome] | None = None,
    ) -> ExecutionResult:
        """执行单个动作.

        Args:
            action: 动作
            population_id: 种群 ID
            generation: 代际编号
            base_genomes: 基础基因组

        Returns:
            ExecutionResult: 执行结果
        """
        result = self._execute_single(action, population_id, generation, base_genomes)
        self._results[result.result_id] = result
        return result

    # ── 动作构建 ──────────────────────────────────────────

    def _build_action_from_goal_and_plan(
        self,
        goal: EvolutionGoal,
        mp: GeneMutationPlan,
        plan: EvolutionPlan,
    ) -> EvolutionAction:
        """从目标 + 变异计划构建动作."""
        action_type = self.GOAL_ACTION_MAP.get(goal.goal_type, ActionType.CREATE_VARIANTS)
        count = max(1, int(plan.target_population_size * mp.percentage / 100)) if plan.target_population_size > 0 else self._default_count

        return EvolutionAction(
            action_type=action_type,
            goal_id=goal.goal_id,
            gene_category=mp.gene_category,
            mutation_direction=mp.direction,
            count=count,
            mutation_type="replace",
            mutation_source=goal.goal_type,
            expected_impact=mp.expected_impact,
            confidence=mp.confidence,
            priority=goal.priority,
            plan_id=plan.plan_id,
        )

    def _build_action_from_goal_only(
        self,
        goal: EvolutionGoal,
        plan: EvolutionPlan,
    ) -> EvolutionAction:
        """从仅有目标构建动作 (无变异计划时)."""
        action_type = self.GOAL_ACTION_MAP.get(goal.goal_type, ActionType.CREATE_VARIANTS)

        return EvolutionAction(
            action_type=action_type,
            goal_id=goal.goal_id,
            gene_category=goal.gene_category or "",
            mutation_direction=goal.description,
            count=self._default_count,
            mutation_type="replace",
            mutation_source=goal.goal_type,
            expected_impact="",
            confidence=0.5,
            priority=goal.priority,
            plan_id=plan.plan_id,
        )

    def _build_action_from_plan_only(
        self,
        mp: GeneMutationPlan,
        plan: EvolutionPlan,
    ) -> EvolutionAction:
        """从仅有变异计划构建动作."""
        count = max(1, int(plan.target_population_size * mp.percentage / 100)) if plan.target_population_size > 0 else self._default_count

        return EvolutionAction(
            action_type=ActionType.MUTATE_GENE,
            goal_id="",
            gene_category=mp.gene_category,
            mutation_direction=mp.direction,
            count=count,
            mutation_type="replace",
            mutation_source="mutation_plan",
            expected_impact=mp.expected_impact,
            confidence=mp.confidence,
            priority=3,
            plan_id=plan.plan_id,
        )

    # ── 内部执行 ──────────────────────────────────────────

    def _execute_single(
        self,
        action: EvolutionAction,
        population_id: str,
        generation: int,
        base_genomes: list[CreativeGenome] | None = None,
    ) -> ExecutionResult:
        """执行单个动作的核心逻辑."""
        action.status = ActionStatus.EXECUTING

        try:
            # 根据动作类型生成基因组
            genomes = self._generate_genomes(action, generation, base_genomes)

            genome_ids = [g.genome_id for g in genomes]

            result = ExecutionResult(
                action_id=action.action_id,
                status=ActionStatus.SUCCESS if genome_ids else ActionStatus.PARTIAL,
                genome_ids=genome_ids,
                population_id=population_id,
                stats={
                    "requested": action.count,
                    "generated": len(genome_ids),
                    "skipped": action.count - len(genome_ids),
                },
            )

            action.status = ActionStatus.SUCCESS if genome_ids else ActionStatus.PARTIAL

        except Exception as e:
            result = ExecutionResult(
                action_id=action.action_id,
                status=ActionStatus.FAILED,
                genome_ids=[],
                population_id=population_id,
                stats={"requested": action.count, "generated": 0, "skipped": action.count},
                error_message=str(e),
            )
            action.status = ActionStatus.FAILED

        return result

    def _generate_genomes(
        self,
        action: EvolutionAction,
        generation: int,
        base_genomes: list[CreativeGenome] | None = None,
    ) -> list[CreativeGenome]:
        """根据动作类型生成基因组.

        Args:
            action: 进化动作
            generation: 代际编号
            base_genomes: 基础基因组 (用于变体)

        Returns:
            list[CreativeGenome]: 生成的基因组列表
        """
        genomes: list[CreativeGenome] = []

        if action.action_type == ActionType.POPULATE:
            # 填充种群: 生成随机基因组
            for i in range(action.count):
                genome = self._create_genome(
                    action=action,
                    generation=generation,
                    index=i,
                )
                genomes.append(genome)

        elif action.action_type == ActionType.CREATE_VARIANTS:
            # 基于赢家模板生成变体
            if base_genomes:
                for i in range(min(action.count, len(base_genomes))):
                    base = base_genomes[i % len(base_genomes)]
                    genome = self._create_variant_genome(base, action, generation, i)
                    genomes.append(genome)
            else:
                for i in range(action.count):
                    genome = self._create_genome(action, generation, i)
                    genomes.append(genome)

        elif action.action_type == ActionType.MUTATE_GENE:
            # 定向变异
            if base_genomes:
                for i in range(min(action.count, len(base_genomes))):
                    base = base_genomes[i % len(base_genomes)]
                    genome = self._create_mutated_genome(base, action, generation, i)
                    genomes.append(genome)
            else:
                for i in range(action.count):
                    genome = self._create_genome(action, generation, i)
                    genomes.append(genome)

        elif action.action_type == ActionType.AMPLIFY_WINNER:
            # 放大赢家: 复制赢家基因组并轻微变异
            if base_genomes:
                for i in range(action.count):
                    base = base_genomes[i % len(base_genomes)]
                    genome = self._create_amplified_genome(base, action, generation, i)
                    genomes.append(genome)
            else:
                for i in range(action.count):
                    genome = self._create_genome(action, generation, i)
                    genomes.append(genome)

        elif action.action_type in (ActionType.SUPPRESS_LOSER, ActionType.DIVERSIFY, ActionType.EXPLORE_NEW):
            # 探索新方向: 生成全新基因组
            for i in range(action.count):
                genome = self._create_genome(action, generation, i)
                genomes.append(genome)

        return genomes

    # ── 基因组创建 ────────────────────────────────────

    def _create_genome(
        self,
        action: EvolutionAction,
        generation: int,
        index: int = 0,
    ) -> CreativeGenome:
        """创建基础基因组."""
        genome_id = f"genome_{generation}_{action.action_type.value}_{index}_{uuid.uuid4().hex[:6]}"

        genes: dict[str, dict[str, Any]] = self._build_genes_from_action(action, index)

        return CreativeGenome(
            genome_id=genome_id,
            generation=generation,
            genes=genes,
            lineage=GenomeLineage(
                source=action.mutation_source,
                created_by="decision_executor",
            ),
        )

    def _create_variant_genome(
        self,
        base: CreativeGenome,
        action: EvolutionAction,
        generation: int,
        index: int = 0,
    ) -> CreativeGenome:
        """基于基础基因组创建变体."""
        genome_id = f"{base.genome_id}_v{generation}_{index}"

        # 复制基础基因
        genes = {k: dict(v) for k, v in base.genes.items()}

        # 修改目标基因
        if action.gene_category and action.mutation_direction:
            slot_key = self.GENE_SLOT_KEYS.get(action.gene_category, action.gene_category)
            if slot_key in genes:
                genes[slot_key]["type"] = action.mutation_direction
            else:
                genes[slot_key] = {"type": action.mutation_direction}

        return CreativeGenome(
            genome_id=genome_id,
            parent_id=base.genome_id,
            generation=generation,
            genes=genes,
            lineage=GenomeLineage(
                source=base.genome_id,
                created_by="decision_executor",
            ),
        )

    def _create_mutated_genome(
        self,
        base: CreativeGenome,
        action: EvolutionAction,
        generation: int,
        index: int = 0,
    ) -> CreativeGenome:
        """创建定向变异基因组."""
        genome_id = f"{base.genome_id}_mut_{generation}_{index}"

        genes = {k: dict(v) for k, v in base.genes.items()}

        if action.gene_category and action.mutation_direction:
            slot_key = self.GENE_SLOT_KEYS.get(action.gene_category, action.gene_category)
            if action.mutation_type == "replace":
                if slot_key in genes:
                    genes[slot_key]["type"] = action.mutation_direction
                else:
                    genes[slot_key] = {"type": action.mutation_direction}
            elif action.mutation_type == "add":
                if slot_key not in genes:
                    genes[slot_key] = {"type": action.mutation_direction}

        return CreativeGenome(
            genome_id=genome_id,
            parent_id=base.genome_id,
            generation=generation,
            genes=genes,
            lineage=GenomeLineage(
                source=base.genome_id,
                created_by="decision_executor_mutation",
            ),
        )

    def _create_amplified_genome(
        self,
        base: CreativeGenome,
        action: EvolutionAction,
        generation: int,
        index: int = 0,
    ) -> CreativeGenome:
        """创建放大赢家基因组 (复制赢家并轻微调整)."""
        genome_id = f"{base.genome_id}_amp_{generation}_{index}"

        genes = {k: dict(v) for k, v in base.genes.items()}

        # 放大: 保持赢家基因, 轻微调整其他维度
        if action.gene_category and action.mutation_direction:
            slot_key = self.GENE_SLOT_KEYS.get(action.gene_category, action.gene_category)
            genes[slot_key] = {"type": action.mutation_direction}

        return CreativeGenome(
            genome_id=genome_id,
            parent_id=base.genome_id,
            generation=generation,
            genes=genes,
            lineage=GenomeLineage(
                source=base.genome_id,
                created_by="decision_executor_amplify",
            ),
        )

    def _build_genes_from_action(
        self,
        action: EvolutionAction,
        index: int = 0,
    ) -> dict[str, dict[str, Any]]:
        """从动作构建基因字典."""
        genes: dict[str, dict[str, Any]] = {
            "hook": {"type": "unknown"},
            "visual": {"type": "unknown"},
            "emotion": {"type": "unknown"},
            "gameplay": {"type": "unknown"},
            "reward": {"type": "unknown"},
        }

        if action.gene_category and action.mutation_direction:
            slot_key = self.GENE_SLOT_KEYS.get(action.gene_category, action.gene_category)
            genes[slot_key] = {"type": action.mutation_direction}

        return genes

    # ── 验证 ──────────────────────────────────────────────

    def validate(self, action: EvolutionAction) -> bool:
        """验证动作是否有效.

        Args:
            action: 待验证动作

        Returns:
            True 有效, False 无效
        """
        if action.count <= 0:
            return False
        if action.confidence < self._min_confidence and action.action_type != ActionType.POPULATE:
            return False
        if action.action_type != ActionType.POPULATE and not action.gene_category:
            return False
        return True

    def validate_actions(self, actions: list[EvolutionAction]) -> dict[str, bool]:
        """批量验证动作.

        Returns:
            dict[action_id, is_valid]
        """
        return {a.action_id: self.validate(a) for a in actions}

    # ── 查询 ──────────────────────────────────────────────

    def get_action(self, action_id: str) -> EvolutionAction | None:
        """获取动作."""
        return self._actions.get(action_id)

    def get_result(self, result_id: str) -> ExecutionResult | None:
        """获取结果."""
        return self._results.get(result_id)

    def get_actions_by_status(self, status: ActionStatus) -> list[EvolutionAction]:
        """按状态获取动作."""
        return [a for a in self._actions.values() if a.status == status]

    def get_results_by_status(self, status: ActionStatus) -> list[ExecutionResult]:
        """按状态获取结果."""
        return [r for r in self._results.values() if r.status == status]

    # ── 统计 ──────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "total_actions": len(self._actions),
            "total_results": len(self._results),
            "actions_by_status": {
                s.value: len(self.get_actions_by_status(s))
                for s in ActionStatus
            },
            "results_by_status": {
                s.value: len(self.get_results_by_status(s))
                for s in ActionStatus
            },
        }

    def reset(self) -> None:
        self._actions.clear()
        self._results.clear()

    # ── 辅助 ──────────────────────────────────────────────

    def _get_related_mutation_plans(
        self,
        goal: EvolutionGoal,
        mutation_plans: list[GeneMutationPlan],
    ) -> list[GeneMutationPlan]:
        """获取与目标相关的变异计划."""
        related = []
        for mp in mutation_plans:
            if goal.gene_category and mp.gene_category == goal.gene_category:
                related.append(mp)
            elif mp.gene_category == "" or mp.direction == "":
                continue
            elif goal.goal_type == "increase_diversity" and mp.reason and "diversity" in mp.reason.lower():
                related.append(mp)
        return related


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_decision_executor(
    population_manager: PopulationManager | None = None,
    adaptive_selector: AdaptiveMutationSelector | None = None,
    default_count: int = 5,
) -> DecisionExecutor:
    """创建默认 DecisionExecutor."""
    return DecisionExecutor(
        population_manager=population_manager,
        adaptive_selector=adaptive_selector,
        default_count=default_count,
    )