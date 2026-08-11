"""E14.5.3 Evolution Planner — 进化方向决策.

职责:
  1. 基于群体分析结果，制定下一代 Creative Population 的进化方向
  2. 生成基因级别的变异计划 (GeneMutationPlan)
  3. 设定进化目标 (EvolutionGoal) 和优先级
  4. 为 AdaptiveMutationSelector (E14.5.4) 提供可执行的进化计划

核心概念:
  - EvolutionGoal: 进化目标 (e.g. increase_visual_diversity)
  - GeneMutationPlan: 基因变异计划 (基因 + 方向 + 比例)
  - EvolutionPlan: 完整进化计划

数据流:
  GenomeIntelligenceReport (E14.5.1) + PopulationHealthReport (E14.5.2)
       ↓
  EvolutionPlanner.plan()
       ↓
  EvolutionPlan
       ↓
  AdaptiveMutationSelector (E14.5.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.genome_intelligence import (
    GenomeIntelligence,
    GenomeIntelligenceReport,
    GeneIntelligence,
    GenePerformance,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import (
    PopulationAnalyzer,
    PopulationHealthReport,
    DiversityMetrics,
    TrendSignal,
)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class EvolutionGoal:
    """进化目标.

    Attributes:
        goal_id: 目标 ID
        goal_type: 目标类型 (increase_diversity / amplify_rising / suppress_declining / explore_new)
        gene_category: 目标基因类别 (None = 全局)
        description: 描述
        priority: 优先级 (1-10, 10 最高)
        reason: 原因
    """
    goal_id: str = ""
    goal_type: str = ""
    gene_category: str | None = None
    description: str = ""
    priority: int = 5
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_type": self.goal_type,
            "gene_category": self.gene_category,
            "description": self.description,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass
class GeneMutationPlan:
    """基因级别的变异计划.

    Attributes:
        gene_category: 基因类别
        direction: 变异方向 (具体基因值)
        percentage: 该方向占新生成 DNA 的比例
        reason: 原因
        expected_impact: 预期影响 (e.g. "+15% ROAS")
        confidence: 置信度
    """
    gene_category: str = ""
    direction: str = ""
    percentage: float = 0.0
    reason: str = ""
    expected_impact: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "direction": self.direction,
            "percentage": round(self.percentage, 2),
            "reason": self.reason,
            "expected_impact": self.expected_impact,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class EvolutionPlan:
    """完整进化计划.

    Attributes:
        plan_id: 计划 ID
        goals: 进化目标列表
        mutation_plans: 基因变异计划列表
        target_population_size: 目标群体大小
        generation: 代际编号
        summary: 计划摘要
        created_at: 创建时间
    """
    plan_id: str = ""
    goals: list[EvolutionGoal] = field(default_factory=list)
    mutation_plans: list[GeneMutationPlan] = field(default_factory=list)
    target_population_size: int = 0
    generation: int = 0
    summary: str = ""
    created_at: str = ""

    @property
    def total_percentage(self) -> float:
        """所有变异计划的总百分比."""
        return sum(mp.percentage for mp in self.mutation_plans)

    @property
    def has_goals(self) -> bool:
        return len(self.goals) > 0

    def get_mutation_plans_by_gene(self, gene_category: str) -> list[GeneMutationPlan]:
        """获取指定基因类别的变异计划."""
        return [mp for mp in self.mutation_plans if mp.gene_category == gene_category]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goals": [g.to_dict() for g in self.goals],
            "mutation_plans": [mp.to_dict() for mp in self.mutation_plans],
            "target_population_size": self.target_population_size,
            "generation": self.generation,
            "summary": self.summary,
            "total_percentage": round(self.total_percentage, 2),
            "has_goals": self.has_goals,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# EvolutionPlanner — 核心引擎
# ═══════════════════════════════════════════════════════════

class EvolutionPlanner:
    """进化规划器 — 制定下一代 Creative Population 的进化方向.

    分析当前群体状态，制定基因级别的变异计划:
      - 多样性不足 → 探索新基因值
      - 上升趋势 → 放大优势基因
      - 下降趋势 → 抑制衰退基因
      - 群体疲劳 → 引入新方向

    用法:
        planner = EvolutionPlanner(genome_intelligence, population_analyzer)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            print(f"{mp.gene_category} → {mp.direction} ({mp.percentage:.0%})")
    """

    # 目标类型
    GOAL_INCREASE_DIVERSITY = "increase_diversity"
    GOAL_AMPLIFY_RISING = "amplify_rising"
    GOAL_SUPPRESS_DECLINING = "suppress_declining"
    GOAL_EXPLORE_NEW = "explore_new"

    # 默认分配比例
    DEFAULT_DIVERSITY_PCT = 0.40   # 多样性探索占 40%
    DEFAULT_AMPLIFY_PCT = 0.35     # 放大优势占 35%
    DEFAULT_EXPLORE_PCT = 0.25     # 探索新方向占 25%

    def __init__(
        self,
        genome_intelligence: GenomeIntelligence | None = None,
        population_analyzer: PopulationAnalyzer | None = None,
        min_mutation_pct: float = 0.05,
        max_mutation_pct: float = 0.50,
    ):
        self._genome_intelligence = genome_intelligence or GenomeIntelligence()
        self._population_analyzer = population_analyzer or PopulationAnalyzer(
            genome_intelligence=self._genome_intelligence,
        )
        self._min_mutation_pct = min_mutation_pct
        self._max_mutation_pct = max_mutation_pct
        self._generation = 0

    # ── 核心规划 ──────────────────────────────────────────

    def plan(
        self,
        genome_report: GenomeIntelligenceReport | None = None,
        health_report: PopulationHealthReport | None = None,
        historical_report: GenomeIntelligenceReport | None = None,
    ) -> EvolutionPlan:
        """制定进化计划.

        Args:
            genome_report: 当前基因组智能报告
            health_report: 群体健康报告
            historical_report: 历史基因组报告 (用于趋势分析)

        Returns:
            EvolutionPlan: 完整进化计划
        """
        # 1. 获取报告
        if genome_report is None:
            genome_report = self._genome_intelligence.analyze()
        if health_report is None:
            health_report = self._population_analyzer.analyze(
                genome_report=genome_report,
                historical_report=historical_report,
            )

        self._generation += 1

        # 2. 设定进化目标
        goals = self._set_evolution_goals(genome_report, health_report)

        # 3. 生成基因变异计划
        mutation_plans = self._generate_mutation_plans(
            genome_report, health_report, goals,
        )

        # 4. 计算目标群体大小
        target_size = self._calculate_target_size(genome_report)

        # 5. 生成摘要
        summary = self._generate_summary(goals, mutation_plans)

        return EvolutionPlan(
            plan_id=f"ep_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            goals=goals,
            mutation_plans=mutation_plans,
            target_population_size=target_size,
            generation=self._generation,
            summary=summary,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── 目标设定 ──────────────────────────────────────────

    def _set_evolution_goals(
        self,
        genome_report: GenomeIntelligenceReport,
        health_report: PopulationHealthReport,
    ) -> list[EvolutionGoal]:
        """设定进化目标.

        基于群体健康报告和基因组报告，确定当前最需要解决的问题.
        """
        goals: list[EvolutionGoal] = []
        goal_counter = 0

        # 1. 多样性问题 → 增加多样性
        for cat, dm in health_report.diversity.items():
            if dm.risk_level in ("critical", "high"):
                goal_counter += 1
                priority = 10 if dm.risk_level == "critical" else 8
                goals.append(EvolutionGoal(
                    goal_id=f"goal_{goal_counter}",
                    goal_type=self.GOAL_INCREASE_DIVERSITY,
                    gene_category=cat,
                    description=f"增加 {cat} 基因多样性 (当前 {dm.unique_values} 个值)",
                    priority=priority,
                    reason=f"{cat} 基因多样性不足, 主导值 '{dm.dominant_value}' 占比 {dm.dominance_ratio:.0%}",
                ))

        # 2. 上升趋势 → 放大优势
        for t in health_report.significant_trends:
            if t.direction == "rising":
                goal_counter += 1
                goals.append(EvolutionGoal(
                    goal_id=f"goal_{goal_counter}",
                    goal_type=self.GOAL_AMPLIFY_RISING,
                    gene_category=t.gene_category,
                    description=f"放大 {t.gene_category}={t.gene_value} (上升趋势 +{t.delta:.0%})",
                    priority=7,
                    reason=f"基因值 {t.gene_value} 胜率从 {t.historical_win_rate:.0%} 升至 {t.recent_win_rate:.0%}",
                ))

        # 3. 下降趋势 → 抑制衰退
        for t in health_report.significant_trends:
            if t.direction == "declining":
                goal_counter += 1
                goals.append(EvolutionGoal(
                    goal_id=f"goal_{goal_counter}",
                    goal_type=self.GOAL_SUPPRESS_DECLINING,
                    gene_category=t.gene_category,
                    description=f"抑制 {t.gene_category}={t.gene_value} (下降趋势 {t.delta:.0%})",
                    priority=6,
                    reason=f"基因值 {t.gene_value} 胜率从 {t.historical_win_rate:.0%} 降至 {t.recent_win_rate:.0%}",
                ))

        # 4. 整体探索需求
        if health_report.overall_risk_level in ("critical", "high"):
            goal_counter += 1
            goals.append(EvolutionGoal(
                goal_id=f"goal_{goal_counter}",
                goal_type=self.GOAL_EXPLORE_NEW,
                description="探索全新基因方向, 突破同质化",
                priority=9,
                reason=f"整体风险等级: {health_report.overall_risk_level}, 多样性: {health_report.overall_diversity_score:.2f}",
            ))

        # 按优先级排序
        goals.sort(key=lambda g: g.priority, reverse=True)
        return goals

    # ── 变异计划生成 ──────────────────────────────────────

    def _generate_mutation_plans(
        self,
        genome_report: GenomeIntelligenceReport,
        health_report: PopulationHealthReport,
        goals: list[EvolutionGoal],
    ) -> list[GeneMutationPlan]:
        """生成基因级别的变异计划."""
        plans: list[GeneMutationPlan] = []

        # 按目标类型分组处理
        diversity_goals = [g for g in goals if g.goal_type == self.GOAL_INCREASE_DIVERSITY]
        amplify_goals = [g for g in goals if g.goal_type == self.GOAL_AMPLIFY_RISING]
        suppress_goals = [g for g in goals if g.goal_type == self.GOAL_SUPPRESS_DECLINING]
        explore_goals = [g for g in goals if g.goal_type == self.GOAL_EXPLORE_NEW]

        # 1. 多样性探索计划
        if diversity_goals:
            diversity_pct = self.DEFAULT_DIVERSITY_PCT
            pct_per_gene = diversity_pct / max(len(diversity_goals), 1)
            pct_per_gene = max(pct_per_gene, self._min_mutation_pct)
            pct_per_gene = min(pct_per_gene, self._max_mutation_pct)

            for goal in diversity_goals:
                if goal.gene_category:
                    # 找到该基因类别中表现最好的非主导值
                    new_direction = self._find_alternative_direction(
                        genome_report, goal.gene_category,
                    )
                    plans.append(GeneMutationPlan(
                        gene_category=goal.gene_category,
                        direction=new_direction,
                        percentage=pct_per_gene,
                        reason=goal.reason,
                        expected_impact="预计提升多样性",
                        confidence=0.6,
                    ))

        # 2. 放大优势计划
        if amplify_goals:
            amplify_pct = self.DEFAULT_AMPLIFY_PCT
            pct_per_goal = amplify_pct / max(len(amplify_goals), 1)
            pct_per_goal = max(pct_per_goal, self._min_mutation_pct)
            pct_per_goal = min(pct_per_goal, self._max_mutation_pct)

            for goal in amplify_goals:
                if goal.gene_category:
                    # 提取基因值
                    gene_value = self._extract_gene_value(goal.description)
                    if gene_value:
                        # 获取置信度
                        gi = genome_report.get_gene(goal.gene_category)
                        confidence = 0.5
                        for v in (gi.values if gi else []):
                            if v.gene_value == gene_value:
                                confidence = v.confidence
                                break

                        plans.append(GeneMutationPlan(
                            gene_category=goal.gene_category,
                            direction=gene_value,
                            percentage=pct_per_goal,
                            reason=goal.reason,
                            expected_impact=f"预计 +{10 + len(amplify_goals) * 5}% ROAS",
                            confidence=confidence,
                        ))

        # 3. 抑制衰退计划
        for goal in suppress_goals:
            if goal.gene_category:
                gene_value = self._extract_gene_value(goal.description)
                if gene_value:
                    # 抑制意味着减少该基因值的比例，分配给其他方向
                    replacement = self._find_alternative_direction(
                        genome_report, goal.gene_category,
                    )
                    plans.append(GeneMutationPlan(
                        gene_category=goal.gene_category,
                        direction=replacement,
                        percentage=self._min_mutation_pct * 2,
                        reason=goal.reason,
                        expected_impact="预计止损",
                        confidence=0.5,
                    ))

        # 4. 探索新方向计划
        if explore_goals:
            explore_pct = self.DEFAULT_EXPLORE_PCT
            # 为每个基因类别分配探索比例
            explore_categories = set()
            for dm in health_report.diversity.values():
                if dm.risk_level in ("critical", "high"):
                    explore_categories.add(dm.gene_category)

            if explore_categories:
                pct_per_cat = explore_pct / max(len(explore_categories), 1)
                pct_per_cat = max(pct_per_cat, self._min_mutation_pct)
                pct_per_cat = min(pct_per_cat, self._max_mutation_pct)

                for cat in explore_categories:
                    new_direction = self._find_alternative_direction(genome_report, cat)
                    plans.append(GeneMutationPlan(
                        gene_category=cat,
                        direction=new_direction,
                        percentage=pct_per_cat,
                        reason="群体同质化风险, 需要探索新方向",
                        expected_impact="预计降低 fatigue 风险",
                        confidence=0.4,
                    ))

        return plans

    def _find_alternative_direction(
        self,
        report: GenomeIntelligenceReport,
        gene_category: str,
    ) -> str:
        """找到基因类别的替代方向 (非主导值)."""
        gi = report.get_gene(gene_category)
        if not gi or not gi.values:
            return "new_direction"

        # 跳过主导值，找下一个最佳值
        if len(gi.values) >= 2:
            return gi.values[1].gene_value
        elif len(gi.values) == 1:
            # 只有主导值，建议相反方向
            dominant = gi.values[0].gene_value
            return f"not_{dominant}"

        return "new_direction"

    def _extract_gene_value(self, text: str) -> str:
        """从描述文本中提取基因值.

        e.g. "放大 hook=transformation (上升趋势 +25%)" → "transformation"
        """
        import re
        match = re.search(r'=(\w+)', text)
        return match.group(1) if match else ""

    def _calculate_target_size(
        self,
        report: GenomeIntelligenceReport,
    ) -> int:
        """计算目标群体大小."""
        current = report.total_dnas_analyzed
        if current == 0:
            return 0
        # 如果当前群体小，扩大 50%；否则保持或略微扩大
        if current < 20:
            return max(current + 10, 20)
        elif current < 50:
            return int(current * 1.3)
        else:
            return int(current * 1.1)

    def _generate_summary(
        self,
        goals: list[EvolutionGoal],
        plans: list[GeneMutationPlan],
    ) -> str:
        """生成计划摘要."""
        parts = []

        goal_types = {}
        for g in goals:
            goal_types[g.goal_type] = goal_types.get(g.goal_type, 0) + 1

        if self.GOAL_INCREASE_DIVERSITY in goal_types:
            parts.append(f"多样性探索 x{goal_types[self.GOAL_INCREASE_DIVERSITY]}")
        if self.GOAL_AMPLIFY_RISING in goal_types:
            parts.append(f"放大优势 x{goal_types[self.GOAL_AMPLIFY_RISING]}")
        if self.GOAL_SUPPRESS_DECLINING in goal_types:
            parts.append(f"抑制衰退 x{goal_types[self.GOAL_SUPPRESS_DECLINING]}")
        if self.GOAL_EXPLORE_NEW in goal_types:
            parts.append(f"探索新方向 x{goal_types[self.GOAL_EXPLORE_NEW]}")

        # 添加具体变异计划
        plan_summary = [
            f"{mp.gene_category}→{mp.direction}({mp.percentage:.0%})"
            for mp in plans[:5]
        ]

        return "; ".join(parts) + " | " + ", ".join(plan_summary) if plan_summary else "; ".join(parts)

    # ── 快捷查询 ──────────────────────────────────────────

    def get_evolution_strategy(
        self,
        genome_report: GenomeIntelligenceReport | None = None,
        health_report: PopulationHealthReport | None = None,
    ) -> dict[str, Any]:
        """获取进化策略摘要.

        Returns:
            {primary_goal, strategy_type, gene_focus, mutation_count}
        """
        plan = self.plan(genome_report=genome_report, health_report=health_report)

        primary_goal = plan.goals[0].goal_type if plan.goals else "maintain"
        strategy_type = "diversify" if primary_goal in (
            self.GOAL_INCREASE_DIVERSITY, self.GOAL_EXPLORE_NEW
        ) else "amplify" if primary_goal == self.GOAL_AMPLIFY_RISING else "maintain"

        gene_focus = list(set(mp.gene_category for mp in plan.mutation_plans))

        return {
            "primary_goal": primary_goal,
            "strategy_type": strategy_type,
            "gene_focus": gene_focus,
            "mutation_count": len(plan.mutation_plans),
            "target_population": plan.target_population_size,
            "summary": plan.summary,
        }

    def preview_mutation_effects(
        self,
        plan: EvolutionPlan,
    ) -> dict[str, Any]:
        """预览变异计划的效果分布.

        Returns:
            {gene_category: {direction: percentage}}
        """
        effects: dict[str, dict[str, float]] = {}
        for mp in plan.mutation_plans:
            if mp.gene_category not in effects:
                effects[mp.gene_category] = {}
            effects[mp.gene_category][mp.direction] = mp.percentage

        return effects

    # ── 生命周期 ──────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "generation": self._generation,
            "min_mutation_pct": self._min_mutation_pct,
            "max_mutation_pct": self._max_mutation_pct,
            "default_allocations": {
                "diversity": self.DEFAULT_DIVERSITY_PCT,
                "amplify": self.DEFAULT_AMPLIFY_PCT,
                "explore": self.DEFAULT_EXPLORE_PCT,
            },
        }

    def reset(self) -> None:
        self._generation = 0
        self._genome_intelligence.reset()
        self._population_analyzer.reset()


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_evolution_planner(
    genome_intelligence: GenomeIntelligence | None = None,
    population_analyzer: PopulationAnalyzer | None = None,
    min_mutation_pct: float = 0.05,
    max_mutation_pct: float = 0.50,
) -> EvolutionPlanner:
    """创建 EvolutionPlanner 实例."""
    return EvolutionPlanner(
        genome_intelligence=genome_intelligence,
        population_analyzer=population_analyzer,
        min_mutation_pct=min_mutation_pct,
        max_mutation_pct=max_mutation_pct,
    )