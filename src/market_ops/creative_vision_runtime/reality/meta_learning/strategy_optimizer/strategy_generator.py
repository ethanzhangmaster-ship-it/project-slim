"""E12.5.4 — Strategy Generator。

将 E12.5.2 Pattern 和 E12.5.3 Knowledge Graph 关系
转换为可执行的 MetaStrategy。

核心逻辑:
  - Pattern → Strategy:     高成功率 Pattern 生成 Amplify 策略
  - Knowledge → Strategy:   Graph 关系生成 DNA 组合策略
  - Exploration → Strategy: 生成探索性新组合
"""

from __future__ import annotations

from ..pattern_miner.models import MetaPattern, PatternType
from ..knowledge_graph.models import (
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationType,
)
from .models import (
    MetaStrategy,
    OptimizationGoal,
    StrategySource,
    StrategyStatus,
)


class StrategyGenerator:
    """策略生成器 —— Pattern → Strategy。

    Usage:
        >>> gen = StrategyGenerator()
        >>> strategies = gen.generate_from_patterns(patterns)
        >>> kg_strategies = gen.generate_from_knowledge(nodes, edges)
    """

    # 成功率阈值
    HIGH_SUCCESS_THRESHOLD: float = 0.70
    STRONG_SUCCESS_THRESHOLD: float = 0.80

    # 最小样本量
    MIN_SAMPLE_COUNT: int = 5

    def __init__(
        self,
        high_threshold: float = 0.70,
        strong_threshold: float = 0.80,
        min_samples: int = 5,
    ) -> None:
        self.HIGH_SUCCESS_THRESHOLD = high_threshold
        self.STRONG_SUCCESS_THRESHOLD = strong_threshold
        self.MIN_SAMPLE_COUNT = min_samples

    # ── Pattern → Strategy ─────────────────────────────────

    def generate_from_patterns(
        self,
        patterns: list[MetaPattern],
        target_product: str = "",
    ) -> list[MetaStrategy]:
        """从 Pattern 列表生成策略。

        Args:
            patterns:        MetaPattern 列表
            target_product:  目标产品

        Returns:
            MetaStrategy 列表
        """
        strategies: list[MetaStrategy] = []

        for pattern in patterns:
            strategy = self._pattern_to_strategy(pattern, target_product)
            if strategy is not None:
                strategies.append(strategy)

        return strategies

    def _pattern_to_strategy(
        self,
        pattern: MetaPattern,
        target_product: str,
    ) -> MetaStrategy | None:
        """单个 Pattern 转换为策略。

        规则:
          - success_rate < HIGH_THRESHOLD → 跳过（不稳定）
          - sample_count < MIN_SAMPLE → 跳过（样本不足）
          - success_rate >= STRONG_THRESHOLD → 高置信度 Amplify
          - 否则 → 中等置信度 Explore
        """
        if pattern.sample_count < self.MIN_SAMPLE_COUNT:
            return None

        if pattern.success_rate < self.HIGH_SUCCESS_THRESHOLD:
            return None

        is_strong = pattern.success_rate >= self.STRONG_SUCCESS_THRESHOLD
        confidence = pattern.confidence if pattern.confidence > 0 else 0.70

        # 确定优化目标
        goal = self._infer_goal(pattern)

        # 构建 DNA 修改
        dna_mutations = dict(pattern.genes)

        # 强 Pattern → Amplify
        if is_strong:
            strategy = MetaStrategy(
                name=f"Amplify {pattern.name}",
                target_product=target_product or ", ".join(pattern.products),
                optimization_goal=goal,
                dna_mutations=dna_mutations,
                dna_amplify=list(pattern.genes.keys()),
                dna_suppress=[],
                dna_explore=[],
                source_patterns=[pattern.pattern_id],
                expected_ctr_delta=pattern.avg_ctr_gain,
                expected_roas_delta=pattern.avg_roas_gain,
                expected_cvr_delta=pattern.avg_cvr_gain,
                confidence=confidence,
                risk_score=0.15 if is_strong else 0.30,
                exploration=False,
                strategy_source=StrategySource.PATTERN,
                evidence_count=pattern.sample_count,
                markets=list(pattern.markets),
                platforms=list(pattern.platforms),
                insight=pattern.insight,
                recommendation=f"Amplify {pattern.name}基因权重，"
                f"基于 {pattern.sample_count} 次实验，"
                f"成功率 {pattern.success_rate:.0%}",
            )
        else:
            # 中等 Pattern → Explore（小规模测试）
            strategy = MetaStrategy(
                name=f"Explore {pattern.name}",
                target_product=target_product or ", ".join(pattern.products),
                optimization_goal=goal,
                dna_mutations=dna_mutations,
                dna_amplify=[],
                dna_suppress=[],
                dna_explore=list(pattern.genes.keys()),
                source_patterns=[pattern.pattern_id],
                expected_ctr_delta=pattern.avg_ctr_gain * 0.5,
                expected_roas_delta=pattern.avg_roas_gain * 0.5,
                expected_cvr_delta=pattern.avg_cvr_gain * 0.5,
                confidence=confidence * 0.8,
                risk_score=0.35,
                exploration=True,
                strategy_source=StrategySource.PATTERN,
                evidence_count=pattern.sample_count,
                markets=list(pattern.markets),
                platforms=list(pattern.platforms),
                insight=pattern.insight,
                recommendation=f"小规模测试 {pattern.name} 基因组合，"
                f"基于 {pattern.sample_count} 次实验",
            )

        return strategy

    def _infer_goal(self, pattern: MetaPattern) -> OptimizationGoal:
        """根据 Pattern 指标推断优化目标。"""
        gains = {
            "ctr": pattern.avg_ctr_gain,
            "roas": pattern.avg_roas_gain,
            "cvr": pattern.avg_cvr_gain,
        }
        max_key = max(gains, key=gains.get)
        max_value = gains[max_key]

        if max_value <= 0:
            return OptimizationGoal.BALANCED

        goal_map = {
            "ctr": OptimizationGoal.CTR,
            "roas": OptimizationGoal.ROAS,
            "cvr": OptimizationGoal.CVR,
        }
        return goal_map.get(max_key, OptimizationGoal.BALANCED)

    # ── Knowledge Graph → Strategy ─────────────────────────

    def generate_from_knowledge(
        self,
        nodes: list[KnowledgeNode],
        edges: list[KnowledgeEdge],
        target_product: str = "",
    ) -> list[MetaStrategy]:
        """从 Knowledge Graph 生成策略。

        分析 IMPROVES 和 COMBINES_WITH 关系，
        生成基因组合策略。

        Args:
            nodes:   KnowledgeNode 列表
            edges:   KnowledgeEdge 列表
            target_product: 目标产品

        Returns:
            MetaStrategy 列表
        """
        strategies: list[MetaStrategy] = []

        # 找到 IMPROVES 关系
        improves_edges = [e for e in edges if e.relation_type == RelationType.IMPROVES]
        # 找到 COMBINES_WITH 关系
        combines_edges = [e for e in edges if e.relation_type == RelationType.COMBINES_WITH]

        node_map = {n.node_id: n for n in nodes}

        # 从 IMPROVES 关系生成策略
        for edge in improves_edges:
            if edge.confidence < 0.60 or edge.evidence_count < self.MIN_SAMPLE_COUNT:
                continue

            source_node = node_map.get(edge.source_id)
            target_node = node_map.get(edge.target_id)

            if source_node is None:
                continue

            gene_name = source_node.name
            metric_name = target_node.name if target_node else "performance"

            goal = self._metric_to_goal(metric_name)

            is_strong = edge.confidence >= 0.80

            strategy = MetaStrategy(
                name=f"{gene_name} → {metric_name}",
                target_product=target_product,
                optimization_goal=goal,
                dna_mutations={source_node.node_type.value: gene_name},
                dna_amplify=[gene_name] if is_strong else [],
                dna_suppress=[],
                dna_explore=[gene_name] if not is_strong else [],
                source_knowledge=[edge.source_id, edge.target_id],
                expected_ctr_delta=edge.weight if goal == OptimizationGoal.CTR else 0.0,
                expected_roas_delta=edge.weight if goal == OptimizationGoal.ROAS else 0.0,
                expected_cvr_delta=edge.weight if goal == OptimizationGoal.CVR else 0.0,
                confidence=edge.confidence,
                risk_score=0.15 if is_strong else 0.30,
                exploration=not is_strong,
                strategy_source=StrategySource.KNOWLEDGE,
                evidence_count=edge.evidence_count,
                insight=f"Graph edge: {source_node.name} improves {metric_name}",
                recommendation=f"{'Amplify' if is_strong else 'Explore'} "
                f"{source_node.name} for {metric_name} improvement",
            )
            strategies.append(strategy)

        # 从 COMBINES_WITH 关系生成组合策略
        for edge in combines_edges:
            if edge.confidence < 0.60 or edge.evidence_count < self.MIN_SAMPLE_COUNT:
                continue

            source_node = node_map.get(edge.source_id)
            target_node = node_map.get(edge.target_id)

            if source_node is None or target_node is None:
                continue

            gene_combo = {
                source_node.node_type.value: source_node.name,
                target_node.node_type.value: target_node.name,
            }

            strategy = MetaStrategy(
                name=f"Combo: {source_node.name} + {target_node.name}",
                target_product=target_product,
                optimization_goal=OptimizationGoal.BALANCED,
                dna_mutations=gene_combo,
                dna_amplify=list(gene_combo.keys()),
                dna_suppress=[],
                dna_explore=[],
                source_knowledge=[edge.source_id, edge.target_id],
                expected_ctr_delta=edge.weight * 0.6,
                expected_roas_delta=edge.weight * 0.6,
                confidence=edge.confidence,
                risk_score=0.20,
                exploration=False,
                strategy_source=StrategySource.KNOWLEDGE,
                evidence_count=edge.evidence_count,
                insight=f"Synergy: {source_node.name} + {target_node.name}",
                recommendation=f"Combine {source_node.name} and {target_node.name} "
                f"for better performance",
            )
            strategies.append(strategy)

        return strategies

    def _metric_to_goal(self, metric_name: str) -> OptimizationGoal:
        """指标名 → 优化目标。"""
        metric_lower = metric_name.lower()
        if "ctr" in metric_lower:
            return OptimizationGoal.CTR
        if "roas" in metric_lower:
            return OptimizationGoal.ROAS
        if "cvr" in metric_lower:
            return OptimizationGoal.CVR
        if "cpi" in metric_lower:
            return OptimizationGoal.CPI
        return OptimizationGoal.BALANCED

    # ── Exploration Generator ───────────────────────────────

    def generate_exploration(
        self,
        patterns: list[MetaPattern],
        target_product: str = "",
        count: int = 3,
    ) -> list[MetaStrategy]:
        """生成探索性新组合策略。

        从已验证 Pattern 中提取基因，随机组合成新策略。

        Args:
            patterns:       已验证 Pattern 列表
            target_product: 目标产品
            count:          生成数量

        Returns:
            探索策略列表
        """
        if not patterns:
            return []

        # 收集所有基因
        all_genes: dict[str, list[str]] = {}
        for p in patterns:
            for gene_key, gene_value in p.genes.items():
                if gene_key not in all_genes:
                    all_genes[gene_key] = []
                if gene_value not in all_genes[gene_key]:
                    all_genes[gene_key].append(gene_value)

        strategies: list[MetaStrategy] = []
        gene_keys = list(all_genes.keys())

        for i in range(min(count, len(gene_keys))):
            # 每次选择不同的基因组合
            start_idx = i % len(gene_keys)
            selected_genes: dict[str, str] = {}

            for j in range(min(3, len(gene_keys))):
                key = gene_keys[(start_idx + j) % len(gene_keys)]
                if all_genes[key]:
                    selected_genes[key] = all_genes[key][i % len(all_genes[key])]

            if not selected_genes:
                continue

            strategy = MetaStrategy(
                name=f"Exploration Combo {i + 1}",
                target_product=target_product,
                optimization_goal=OptimizationGoal.BALANCED,
                dna_mutations=selected_genes,
                dna_amplify=[],
                dna_suppress=[],
                dna_explore=list(selected_genes.keys()),
                source_patterns=[p.pattern_id for p in patterns[:3]],
                expected_ctr_delta=0.05,
                expected_roas_delta=0.05,
                confidence=0.40,
                risk_score=0.50,
                exploration=True,
                strategy_source=StrategySource.EXPLORATION,
                evidence_count=0,
                insight=f"Exploring new gene combination: {selected_genes}",
                recommendation="Small-scale test of new gene combinations",
            )
            strategies.append(strategy)

        return strategies

    def __repr__(self) -> str:
        return (
            f"StrategyGenerator(high={self.HIGH_SUCCESS_THRESHOLD}, "
            f"strong={self.STRONG_SUCCESS_THRESHOLD})"
        )