"""E14.5.4 Adaptive Mutation Selector — 连接E14.4.4 Learning与E11 Mutation Engine.

职责:
  1. 接收 EvolutionPlan (E14.5.3) 的进化方向
  2. 查询 MutationLearning (E14.4.4) 的历史变异有效性
  3. 结合 PopulationHealthReport (E14.5.2) 的群体弱点
  4. 生成具体的 AdaptiveMutation 指令
  5. 转换为 E11 MutationRule 格式，直接驱动基因组变异

核心概念:
  - AdaptiveMutation: 自适应变异指令 (基因 + 方向 + 置信度 + 预期收益)
  - 不是随机变异，而是基于学习结果的定向进化
  - 每个变异都有来源证据 (mutation_learning / population_weakness / combined)

数据流:
  EvolutionPlan + MutationLearning + PopulationHealthReport + CurrentGenome
       ↓
  AdaptiveMutationSelector.select()
       ↓
  list[AdaptiveMutation]
       ↓
  to_e11_mutation_rule() → E11 MutationRule
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.mutation_learning import (
    MutationLearning,
    MutationPriority,
    MutationEffectiveness,
    GeneCategory,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.strategy import (
    GeneMutationAction,
)
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
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.evolution_planner import (
    EvolutionPlan,
    EvolutionGoal,
    GeneMutationPlan,
)
from market_ops.e11.genome.schema import CreativeGenome, GENE_SLOTS
from market_ops.e11.mutation.mutation_schema import (
    MutationType,
    MutationRule,
    MutationTarget,
)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class AdaptiveMutation:
    """自适应变异指令 — 连接学习结果与 E11 变异引擎.

    基于以下来源合成:
      - MutationLearning 的历史变异成功率
      - PopulationHealth 的群体弱点
      - EvolutionPlan 的进化方向
      - 当前 Genome 的基因值

    Attributes:
        mutation_id: 变异指令 ID
        gene_category: 基因类别 (hook / visual / gameplay / emotion)
        current_value: 当前基因值
        target_value: 目标基因值
        confidence: 综合置信度 (0-1)
        expected_reward: 预期收益 (e.g. +0.18 = +18%)
        source: 变异来源 (mutation_learning / population_weakness / combined)
        mutation_type: E11 变异类型
        reason: 变异理由
        priority: 优先级 (0-1)
        created_at: 创建时间
    """
    mutation_id: str = field(default_factory=lambda: f"am_{uuid.uuid4().hex[:8]}")
    gene_category: str = ""
    current_value: str = ""
    target_value: str = ""
    confidence: float = 0.0
    expected_reward: float = 0.0
    source: str = "combined"
    mutation_type: str = "replace"
    reason: str = ""
    priority: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "gene_category": self.gene_category,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "confidence": round(self.confidence, 4),
            "expected_reward": round(self.expected_reward, 4),
            "source": self.source,
            "mutation_type": self.mutation_type,
            "reason": self.reason,
            "priority": round(self.priority, 4),
            "created_at": self.created_at,
        }

    def to_e11_mutation_target(self) -> MutationTarget:
        """转换为 E11 MutationTarget."""
        return MutationTarget(
            gene_name=self.gene_category,
            old_value=self.current_value,
            new_value=self.target_value,
            confidence=self.confidence,
        )

    def to_e11_mutation_rule(self) -> MutationRule:
        """转换为 E11 MutationRule."""
        mt = MutationType.REPLACE
        if self.mutation_type == "enhance":
            mt = MutationType.ENHANCE
        elif self.mutation_type == "combine":
            mt = MutationType.COMBINE
        elif self.mutation_type == "remove":
            mt = MutationType.REMOVE
        return MutationRule(
            target_gene=self.gene_category,
            mutation_type=mt,
            strategy=self.source,
            priority=self.priority,
        )


@dataclass
class AdaptiveMutationReport:
    """自适应变异报告.

    Attributes:
        report_id: 报告 ID
        total_mutations: 总变异指令数
        by_source: 按来源分类的变异数
        by_gene: 按基因类别分类的变异数
        mutations: 变异指令列表
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_mutations: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    by_gene: dict[str, int] = field(default_factory=dict)
    mutations: list[AdaptiveMutation] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_mutations": self.total_mutations,
            "by_source": self.by_source,
            "by_gene": self.by_gene,
            "mutations": [m.to_dict() for m in self.mutations],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# E11 基因槽位 → E14 基因类别映射
# ═══════════════════════════════════════════════════════════

# E11 GENE_SLOTS: hook, visual, reward, emotion, gameplay
# E14 GeneCategory: HOOK, VISUAL, GAMEPLAY, EMOTION, AUDIENCE, CONTEXT, MONETIZATION

_E11_TO_E14_GENE: dict[str, str] = {
    "hook": "hook",
    "visual": "visual",
    "reward": "monetization",  # E11 reward → E14 monetization
    "emotion": "emotion",
    "gameplay": "gameplay",
}

_E14_TO_E11_GENE: dict[str, str] = {
    "hook": "hook",
    "visual": "visual",
    "gameplay": "gameplay",
    "emotion": "emotion",
    "monetization": "reward",
    "audience": "hook",       # 受众影响 hook 选择
    "context": "hook",        # 情境影响 hook 选择
}


# ═══════════════════════════════════════════════════════════
# 基因值候选池 — 用于生成替代方案
# ═══════════════════════════════════════════════════════════

_GENE_VALUE_POOL: dict[str, list[str]] = {
    "hook": ["rescue", "transformation", "discovery", "challenge", "curiosity", "escape", "collection"],
    "visual": ["fantasy", "real_world", "cartoon", "3d", "minimalist", "dark", "colorful"],
    "gameplay": ["merge", "match3", "puzzle", "rpg", "strategy", "simulation", "action"],
    "emotion": ["surprise", "satisfaction", "relief", "excitement", "curiosity_emotion", "tension", "joy"],
    "monetization": ["iap", "rewarded_video", "subscription", "battle_pass", "gacha"],
}


# ═══════════════════════════════════════════════════════════
# AdaptiveMutationSelector
# ═══════════════════════════════════════════════════════════

class AdaptiveMutationSelector:
    """自适应变异选择器 — 智能选择最优变异方向.

    核心逻辑:
      1. 从 MutationLearning 获取历史变异优先级 (哪些变异有效)
      2. 从 PopulationHealth 识别群体弱点 (哪些基因需要变异)
      3. 从 EvolutionPlan 获取进化方向 (总体规划)
      4. 合成自适应变异指令

    三种变异来源:
      - mutation_learning: 基于历史成功率
      - population_weakness: 基于群体多样性不足
      - combined: 综合两者

    用法:
        selector = AdaptiveMutationSelector(
            mutation_learning=learner,
            genome_intelligence=gi,
            population_analyzer=pa,
        )
        mutations = selector.select(evolution_plan=plan)
        for m in mutations:
            rule = m.to_e11_mutation_rule()
            # 传递给 E11 MutationOperator
    """

    # 权重配置
    LEARNING_WEIGHT = 0.4       # 历史学习权重
    DIVERSITY_WEIGHT = 0.35     # 多样性权重
    TREND_WEIGHT = 0.25         # 趋势权重
    MIN_CONFIDENCE = 0.3        # 最小置信度
    MIN_PRIORITY = 0.1          # 最小优先级
    DEFAULT_MAX_MUTATIONS = 10  # 默认最大变异数

    def __init__(
        self,
        mutation_learning: MutationLearning | None = None,
        genome_intelligence: GenomeIntelligence | None = None,
        population_analyzer: PopulationAnalyzer | None = None,
        max_mutations: int = DEFAULT_MAX_MUTATIONS,
    ):
        self._mutation_learning = mutation_learning or MutationLearning()
        self._genome_intelligence = genome_intelligence
        self._population_analyzer = population_analyzer
        self._max_mutations = max_mutations
        self._generation_count: int = 0
        self._mutation_history: list[AdaptiveMutation] = []

    # ── 主入口 ──────────────────────────────────────────────

    def select(
        self,
        evolution_plan: EvolutionPlan | None = None,
        health_report: PopulationHealthReport | None = None,
        genome_report: GenomeIntelligenceReport | None = None,
        current_genomes: list[CreativeGenome] | None = None,
    ) -> list[AdaptiveMutation]:
        """选择自适应变异指令.

        Args:
            evolution_plan: E14.5.3 进化计划
            health_report: E14.5.2 群体健康报告
            genome_report: E14.5.1 基因组智能报告
            current_genomes: 当前群体中的基因组列表

        Returns:
            list[AdaptiveMutation]: 变异指令列表
        """
        self._generation_count += 1
        mutations: list[AdaptiveMutation] = []

        # 1. 基于历史学习生成变异
        learning_mutations = self._select_from_learning(evolution_plan)
        mutations.extend(learning_mutations)

        # 2. 基于群体弱点生成变异
        weakness_mutations = self._select_from_weakness(
            health_report, genome_report, current_genomes
        )
        mutations.extend(weakness_mutations)

        # 3. 基于进化计划生成变异
        plan_mutations = self._select_from_plan(evolution_plan, genome_report)
        mutations.extend(plan_mutations)

        # 4. 去重、排序、截断
        mutations = self._deduplicate(mutations)
        mutations = self._sort_by_priority(mutations)
        mutations = mutations[:self._max_mutations]

        self._mutation_history.extend(mutations)
        return mutations

    def select_for_genome(
        self,
        genome: CreativeGenome,
        evolution_plan: EvolutionPlan | None = None,
        health_report: PopulationHealthReport | None = None,
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> list[AdaptiveMutation]:
        """为特定基因组选择变异.

        Args:
            genome: 目标基因组
            evolution_plan: 进化计划
            health_report: 群体健康报告
            genome_report: 基因组智能报告

        Returns:
            list[AdaptiveMutation]: 适用于该基因组的变异指令
        """
        all_mutations = self.select(
            evolution_plan=evolution_plan,
            health_report=health_report,
            genome_report=genome_report,
        )

        # 过滤：只保留匹配该基因组基因槽位的变异
        applicable = []
        for am in all_mutations:
            e11_gene = _E14_TO_E11_GENE.get(am.gene_category, am.gene_category)
            if e11_gene in genome.genes:
                # 填充当前值
                gene_data = genome.genes[e11_gene]
                if isinstance(gene_data, dict):
                    current_val = gene_data.get("type", str(gene_data))
                else:
                    current_val = str(gene_data)
                am.current_value = current_val
                applicable.append(am)

        return applicable

    # ── 基于历史学习 ─────────────────────────────────────────

    def _select_from_learning(
        self,
        evolution_plan: EvolutionPlan | None = None,
    ) -> list[AdaptiveMutation]:
        """从 MutationLearning 生成变异指令."""
        mutations: list[AdaptiveMutation] = []

        priorities = self._mutation_learning.get_priorities(
            min_confidence=self.MIN_CONFIDENCE,
            top_n=5,
        )

        # 从进化计划中提取基因类别优先级
        plan_gene_weights = self._get_plan_gene_weights(evolution_plan)

        for p in priorities:
            if p.priority_score < self.MIN_PRIORITY:
                continue

            e11_gene = _E14_TO_E11_GENE.get(p.gene_category.value, p.gene_category.value)
            current_value = self._get_current_value(e11_gene)
            target_value = self._find_target_value(e11_gene, current_value, p)

            # 综合优先级：学习分数 × 计划权重
            plan_weight = plan_gene_weights.get(p.gene_category.value, 0.5)
            combined_priority = p.priority_score * self.LEARNING_WEIGHT + plan_weight * self.TREND_WEIGHT

            mutation = AdaptiveMutation(
                gene_category=p.gene_category.value,
                current_value=current_value,
                target_value=target_value,
                confidence=p.effectiveness.confidence if p.effectiveness else 0.5,
                expected_reward=p.effectiveness.avg_roas_impact if p.effectiveness else 0.0,
                source="mutation_learning",
                mutation_type="replace",
                reason=p.recommendation,
                priority=min(combined_priority, 1.0),
            )
            mutations.append(mutation)

        return mutations

    # ── 基于群体弱点 ─────────────────────────────────────────

    def _select_from_weakness(
        self,
        health_report: PopulationHealthReport | None,
        genome_report: GenomeIntelligenceReport | None,
        current_genomes: list[CreativeGenome] | None = None,
    ) -> list[AdaptiveMutation]:
        """从群体弱点生成变异指令."""
        mutations: list[AdaptiveMutation] = []

        if not health_report:
            return mutations

        # 识别高风险的基因类别
        risky_genes = self._identify_risky_genes(health_report)
        if not risky_genes:
            return mutations

        for gene, risk_level in risky_genes:
            e11_gene = _E14_TO_E11_GENE.get(gene, gene)

            # 找当前主导基因值
            current_value = self._get_dominant_value(gene, genome_report)
            if not current_value:
                # 从 genomes 中提取
                current_value = self._get_current_value_from_genomes(e11_gene, current_genomes)

            # 找替代基因值
            target_value = self._find_alternative_value(e11_gene, current_value, genome_report)

            mutation = AdaptiveMutation(
                gene_category=gene,
                current_value=current_value,
                target_value=target_value,
                confidence=0.6 if risk_level == "critical" else 0.5,
                expected_reward=0.0,
                source="population_weakness",
                mutation_type="replace",
                reason=f"群体多样性不足: {gene} 基因 {risk_level} 风险",
                priority=0.7 if risk_level == "critical" else 0.5,
            )
            mutations.append(mutation)

        return mutations

    def _identify_risky_genes(
        self,
        health_report: PopulationHealthReport,
    ) -> list[tuple[str, str]]:
        """识别高风险的基因类别."""
        risky = []

        # 遍历所有基因类别的多样性指标
        for gene_category, diversity in health_report.diversity.items():
            if diversity.dominance_ratio > 0.7:
                risky.append((
                    gene_category,
                    diversity.risk_level,
                ))

        # 如果整体风险高，检查 declining trends
        if health_report.overall_risk_level in ("critical", "high"):
            for trend in (health_report.trends or []):
                if trend.direction == "declining" and trend.strength > 0.3:
                    risky.append((
                        trend.gene_category,
                        "high",
                    ))

        return risky

    # ── 基于进化计划 ─────────────────────────────────────────

    def _select_from_plan(
        self,
        evolution_plan: EvolutionPlan | None,
        genome_report: GenomeIntelligenceReport | None,
    ) -> list[AdaptiveMutation]:
        """从进化计划生成变异指令."""
        mutations: list[AdaptiveMutation] = []

        if not evolution_plan or not evolution_plan.mutation_plans:
            return mutations

        for mp in evolution_plan.mutation_plans:
            if mp.percentage < 0.05:
                continue

            e11_gene = _E14_TO_E11_GENE.get(mp.gene_category, mp.gene_category)
            current_value = self._get_current_value(e11_gene)
            target_value = mp.direction if mp.direction else self._find_alternative_value(
                e11_gene, current_value, genome_report
            )

            mutation = AdaptiveMutation(
                gene_category=mp.gene_category,
                current_value=current_value,
                target_value=target_value,
                confidence=mp.confidence,
                expected_reward=0.0,
                source="combined",
                mutation_type="replace",
                reason=mp.reason,
                priority=mp.percentage,
            )
            mutations.append(mutation)

        return mutations

    # ── 辅助方法 ─────────────────────────────────────────────

    def _get_current_value(self, e11_gene: str) -> str:
        """从 GenomeIntelligence 获取当前基因值."""
        if self._genome_intelligence:
            report = self._genome_intelligence.analyze()
            gi = report.genes.get(e11_gene)
            if gi and gi.best_value:
                return gi.best_value
        return ""

    def _get_current_value_from_genomes(
        self,
        e11_gene: str,
        genomes: list[CreativeGenome] | None,
    ) -> str:
        """从基因组列表中提取当前基因值."""
        if not genomes:
            return ""

        values = []
        for g in genomes:
            gene_data = g.genes.get(e11_gene, {})
            if isinstance(gene_data, dict):
                val = gene_data.get("type", "")
            else:
                val = str(gene_data)
            if val:
                values.append(val)

        if not values:
            return ""

        # 返回最常见的值
        from collections import Counter
        return Counter(values).most_common(1)[0][0]

    def _get_dominant_value(
        self,
        gene: str,
        genome_report: GenomeIntelligenceReport | None,
    ) -> str:
        """获取主导基因值."""
        if not genome_report:
            return ""

        gi = genome_report.genes.get(gene)
        if gi and gi.best_value:
            return gi.best_value

        return ""

    def _find_target_value(
        self,
        e11_gene: str,
        current_value: str,
        priority: MutationPriority,
    ) -> str:
        """寻找目标基因值.

        策略:
          1. 从 MutationPriority 的推荐中推断
          2. 从基因值池中找不同于当前的替代值
          3. 优先选择最佳上下文中的值
        """
        pool = _GENE_VALUE_POOL.get(e11_gene, [])
        alternatives = [v for v in pool if v != current_value]

        if not alternatives:
            return ""

        # 尝试从 effectiveness 推断最佳值
        if priority.effectiveness and priority.effectiveness.avg_roas_impact > 0:
            return alternatives[0] if alternatives else ""

        # 默认选第一个替代值
        return alternatives[0] if alternatives else ""

    def _find_alternative_value(
        self,
        e11_gene: str,
        current_value: str,
        genome_report: GenomeIntelligenceReport | None,
    ) -> str:
        """寻找替代基因值 — 优先选择非主导的、有潜力的值."""
        pool = _GENE_VALUE_POOL.get(e11_gene, [])
        alternatives = [v for v in pool if v != current_value]

        if not alternatives:
            return ""

        # 如果有基因组报告，找性能第二好的值
        if genome_report:
            gi = genome_report.genes.get(e11_gene)
            if gi and gi.values:
                sorted_perfs = sorted(
                    gi.values,
                    key=lambda p: p.win_rate * p.confidence,
                    reverse=True,
                )
                for perf in sorted_perfs:
                    if perf.gene_value != current_value and perf.gene_value in alternatives:
                        return perf.gene_value

        return alternatives[0] if alternatives else ""

    def _get_plan_gene_weights(
        self,
        evolution_plan: EvolutionPlan | None,
    ) -> dict[str, float]:
        """从进化计划中提取基因类别权重."""
        weights: dict[str, float] = {}
        if not evolution_plan:
            return weights

        for mp in evolution_plan.mutation_plans:
            weights[mp.gene_category] = mp.percentage

        return weights

    def _deduplicate(
        self,
        mutations: list[AdaptiveMutation],
    ) -> list[AdaptiveMutation]:
        """去重: 同一基因类别 + 同一目标值 只保留优先级最高的."""
        seen: dict[str, AdaptiveMutation] = {}
        for m in mutations:
            key = f"{m.gene_category}:{m.target_value}"
            if key not in seen or m.priority > seen[key].priority:
                seen[key] = m
        return list(seen.values())

    def _sort_by_priority(
        self,
        mutations: list[AdaptiveMutation],
    ) -> list[AdaptiveMutation]:
        """按优先级降序排序."""
        return sorted(mutations, key=lambda m: m.priority, reverse=True)

    # ── 查询与报告 ──────────────────────────────────────────

    def get_mutations_by_source(
        self,
        source: str,
    ) -> list[AdaptiveMutation]:
        """按来源获取变异指令."""
        return [m for m in self._mutation_history if m.source == source]

    def get_mutations_by_gene(
        self,
        gene_category: str,
    ) -> list[AdaptiveMutation]:
        """按基因类别获取变异指令."""
        return [m for m in self._mutation_history if m.gene_category == gene_category]

    def get_recent(self, n: int = 20) -> list[AdaptiveMutation]:
        """获取最近的变异指令."""
        return self._mutation_history[-n:]

    def get_mutation_recommendation(self) -> dict[str, Any]:
        """获取变异推荐总结."""
        mutations = self._mutation_history[-self._max_mutations:]

        by_source: dict[str, int] = {}
        by_gene: dict[str, int] = {}

        for m in mutations:
            by_source[m.source] = by_source.get(m.source, 0) + 1
            by_gene[m.gene_category] = by_gene.get(m.gene_category, 0) + 1

        return {
            "total_mutations": len(self._mutation_history),
            "recent_mutations": len(mutations),
            "by_source": by_source,
            "by_gene": by_gene,
            "top_mutations": [m.to_dict() for m in mutations[:5]],
        }

    def generate_report(self) -> AdaptiveMutationReport:
        """生成自适应变异报告."""
        mutations = self._mutation_history[-self._max_mutations:]

        by_source: dict[str, int] = {}
        by_gene: dict[str, int] = {}

        for m in mutations:
            by_source[m.source] = by_source.get(m.source, 0) + 1
            by_gene[m.gene_category] = by_gene.get(m.gene_category, 0) + 1

        if mutations:
            top = mutations[0]
            summary = (
                f"共生成了 {len(self._mutation_history)} 条变异指令，"
                f"最近 {len(mutations)} 条。"
                f"最高优先级: {top.gene_category} → {top.target_value} "
                f"(置信度 {top.confidence:.0%})"
            )
        else:
            summary = "暂无变异指令"

        return AdaptiveMutationReport(
            total_mutations=len(mutations),
            by_source=by_source,
            by_gene=by_gene,
            mutations=mutations,
            summary=summary,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "total_mutations": len(self._mutation_history),
            "generation_count": self._generation_count,
            "max_mutations": self._max_mutations,
            "by_source": {
                src: len(self.get_mutations_by_source(src))
                for src in ("mutation_learning", "population_weakness", "combined")
            },
        }

    def reset(self) -> None:
        self._mutation_history.clear()
        self._generation_count = 0


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_adaptive_mutation_selector(
    mutation_learning: MutationLearning | None = None,
    genome_intelligence: GenomeIntelligence | None = None,
    population_analyzer: PopulationAnalyzer | None = None,
    max_mutations: int = 10,
) -> AdaptiveMutationSelector:
    """创建默认 AdaptiveMutationSelector."""
    return AdaptiveMutationSelector(
        mutation_learning=mutation_learning,
        genome_intelligence=genome_intelligence,
        population_analyzer=population_analyzer,
        max_mutations=max_mutations,
    )