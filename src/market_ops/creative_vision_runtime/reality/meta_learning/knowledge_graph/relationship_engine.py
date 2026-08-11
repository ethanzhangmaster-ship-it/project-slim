"""E12.5.3 — Relationship Engine。

自动发现 Pattern 之间的关联关系，构建知识图谱的边。

发现的关系类型:
  - IMPROVES:       Pattern/Gene 提升某个 Metric
  - COMBINES_WITH:  两个 Gene 组合效果好
  - FAILED_WITH:    两个 Gene 组合失败
  - SIMILAR_TO:     两个 Pattern 相似
  - WORKS_FOR:      Pattern 适用于某 Audience/Market/Platform
  - CAUSES:         因果链

核心算法:
  - 共现分析: 两个 Gene 同时出现时，成功率是否高于各自独立出现
  - 相似度计算: 基于基因特征重叠度
  - 市场/平台适配: 基于市场/平台特定成功率
"""

from __future__ import annotations

from collections import defaultdict

from ..models import ExperienceRecord
from ..pattern_miner.models import GeneImpactScore, MetaPattern, PatternType
from .models import KnowledgeEdge, KnowledgeNode, RelationType


class RelationshipEngine:
    """关系发现引擎 —— 自动发现 Pattern/Gene 之间的关联。

    Usage:
        >>> engine = RelationshipEngine()
        >>> edges = engine.discover_relationships(patterns, impacts)
        >>> combine_edges = engine.discover_gene_combinations(patterns)
    """

    # ── 主入口 ──────────────────────────────────────────────

    def discover_relationships(
        self,
        patterns: list[MetaPattern],
        impacts: list[GeneImpactScore] | None = None,
    ) -> list[KnowledgeEdge]:
        """从 Pattern 列表中发现所有关系。

        Args:
            patterns: MetaPattern 列表
            impacts:  GeneImpactScore 列表（可选）

        Returns:
            KnowledgeEdge 列表
        """
        edges: list[KnowledgeEdge] = []

        # 1. Pattern → Metric 关系
        edges.extend(self._discover_improves(patterns))

        # 2. Gene 组合关系
        edges.extend(self._discover_gene_combinations(patterns))

        # 3. Pattern 相似关系
        edges.extend(self._discover_similar_patterns(patterns))

        # 4. Gene → Pattern 归属关系
        edges.extend(self._discover_belongs_to(patterns))

        return edges

    def discover_from_experiences(
        self,
        experiences: list[ExperienceRecord],
    ) -> list[KnowledgeEdge]:
        """从 ExperienceRecord 列表中发现关系。

        Args:
            experiences: 经验记录列表

        Returns:
            KnowledgeEdge 列表
        """
        edges: list[KnowledgeEdge] = []

        # 分析实验中的基因共现
        edges.extend(self._discover_gene_cooccurrence(experiences))

        return edges

    # ── IMPROVES 关系 ──────────────────────────────────────

    def _discover_improves(self, patterns: list[MetaPattern]) -> list[KnowledgeEdge]:
        """发现 Pattern → Metric 的提升关系。

        为每个 Pattern 的每个正向指标创建一个 IMPROVES 边。
        """
        edges: list[KnowledgeEdge] = []

        metric_map = {
            "ctr": ("METRIC_CTR", "avg_ctr_gain"),
            "roas": ("METRIC_ROAS", "avg_roas_gain"),
            "cvr": ("METRIC_CVR", "avg_cvr_gain"),
        }

        for pattern in patterns:
            for metric_key, (metric_id, gain_attr) in metric_map.items():
                gain = getattr(pattern, gain_attr, 0.0)
                if gain > 0.01:
                    edges.append(KnowledgeEdge(
                        source_id=pattern.pattern_id,
                        target_id=metric_id,
                        relation_type=RelationType.IMPROVES,
                        weight=min(gain, 1.0),
                        evidence_count=pattern.sample_count,
                        confidence=pattern.confidence,
                        attributes={
                            "gain": round(gain, 4),
                            "metric": metric_key,
                        },
                    ))

        return edges

    # ── COMBINES_WITH / FAILED_WITH ────────────────────────

    def _discover_gene_combinations(
        self,
        patterns: list[MetaPattern],
    ) -> list[KnowledgeEdge]:
        """发现 Gene 之间的组合关系。

        如果两个 Pattern 共享相同的基因特征但不同值，
        检查它们是否经常一起出现并表现良好。
        """
        edges: list[KnowledgeEdge] = []

        # 按基因特征分组
        gene_groups: dict[str, list[MetaPattern]] = defaultdict(list)
        for pattern in patterns:
            for feat_name in pattern.genes:
                gene_groups[feat_name].append(pattern)

        # 对每个特征，查找不同值之间的组合
        for feat_name, group_patterns in gene_groups.items():
            if len(group_patterns) < 2:
                continue

            for i in range(len(group_patterns)):
                for j in range(i + 1, len(group_patterns)):
                    p1 = group_patterns[i]
                    p2 = group_patterns[j]

                    g1_val = p1.genes.get(feat_name, "")
                    g2_val = p2.genes.get(feat_name, "")
                    if not g1_val or not g2_val or g1_val == g2_val:
                        continue

                    g1_id = f"GENE_{feat_name.upper()}_{g1_val.upper()}"
                    g2_id = f"GENE_{feat_name.upper()}_{g2_val.upper()}"

                    # 综合成功率
                    combined_success = (p1.success_rate + p2.success_rate) / 2
                    combined_evidence = p1.sample_count + p2.sample_count

                    if combined_success >= 0.6:
                        edges.append(KnowledgeEdge(
                            source_id=g1_id,
                            target_id=g2_id,
                            relation_type=RelationType.COMBINES_WITH,
                            weight=combined_success,
                            evidence_count=combined_evidence,
                            confidence=max(p1.confidence, p2.confidence),
                            attributes={
                                "gene_feature": feat_name,
                                "gene_value_1": g1_val,
                                "gene_value_2": g2_val,
                                "combined_success_rate": round(combined_success, 4),
                            },
                        ))
                    elif combined_success < 0.3:
                        edges.append(KnowledgeEdge(
                            source_id=g1_id,
                            target_id=g2_id,
                            relation_type=RelationType.FAILED_WITH,
                            weight=1 - combined_success,
                            evidence_count=combined_evidence,
                            confidence=max(p1.confidence, p2.confidence),
                            attributes={
                                "gene_feature": feat_name,
                                "gene_value_1": g1_val,
                                "gene_value_2": g2_val,
                                "combined_success_rate": round(combined_success, 4),
                            },
                        ))

        return edges

    def _discover_gene_cooccurrence(
        self,
        experiences: list[ExperienceRecord],
    ) -> list[KnowledgeEdge]:
        """从经验中发现基因共现关系。

        分析两个基因同时出现时的表现，与分别出现时对比。
        """
        edges: list[KnowledgeEdge] = []

        if len(experiences) < 5:
            return edges

        # 统计基因对共现
        pair_stats: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"count": 0, "success": 0, "total_improvement": 0.0}
        )

        for exp in experiences:
            gene_values = list(exp.mutation.gene_after.values())
            for i in range(len(gene_values)):
                for j in range(i + 1, len(gene_values)):
                    pair = (gene_values[i], gene_values[j])
                    stats = pair_stats[pair]
                    stats["count"] += 1
                    if exp.is_success:
                        stats["success"] += 1
                    stats["total_improvement"] += exp.experiment.improvement

        for (g1, g2), stats in pair_stats.items():
            if stats["count"] < 3:
                continue

            success_rate = stats["success"] / stats["count"]
            evidence = stats["count"]

            g1_id = f"GENE_COOCCUR_{g1.upper().replace(' ', '_')}"
            g2_id = f"GENE_COOCCUR_{g2.upper().replace(' ', '_')}"

            if success_rate >= 0.6:
                edges.append(KnowledgeEdge(
                    source_id=g1_id,
                    target_id=g2_id,
                    relation_type=RelationType.COMBINES_WITH,
                    weight=success_rate,
                    evidence_count=evidence,
                    confidence=min(evidence / 10, 0.95),
                    attributes={
                        "cooccurrence_success_rate": round(success_rate, 4),
                        "avg_improvement": round(stats["total_improvement"] / evidence, 4),
                    },
                ))

        return edges

    # ── SIMILAR_TO ─────────────────────────────────────────

    def _discover_similar_patterns(
        self,
        patterns: list[MetaPattern],
    ) -> list[KnowledgeEdge]:
        """发现相似 Pattern。

        基于基因特征重叠度计算相似性。
        """
        edges: list[KnowledgeEdge] = []

        for i in range(len(patterns)):
            for j in range(i + 1, len(patterns)):
                p1 = patterns[i]
                p2 = patterns[j]

                # 只比较同类型 Pattern
                if p1.pattern_type != p2.pattern_type:
                    continue

                similarity = self._calculate_pattern_similarity(p1, p2)
                if similarity >= 0.5:
                    edges.append(KnowledgeEdge(
                        source_id=p1.pattern_id,
                        target_id=p2.pattern_id,
                        relation_type=RelationType.SIMILAR_TO,
                        weight=similarity,
                        evidence_count=min(p1.sample_count, p2.sample_count),
                        confidence=similarity,
                        attributes={
                            "similarity_score": round(similarity, 4),
                            "pattern_1": p1.name,
                            "pattern_2": p2.name,
                        },
                    ))

        return edges

    @staticmethod
    def _calculate_pattern_similarity(p1: MetaPattern, p2: MetaPattern) -> float:
        """计算两个 Pattern 的基因特征相似度。

        基于 Jaccard 相似度。
        """
        genes1 = set(p1.genes.items())
        genes2 = set(p2.genes.items())

        if not genes1 or not genes2:
            return 0.0

        intersection = genes1 & genes2
        union = genes1 | genes2

        if not union:
            return 0.0

        return len(intersection) / len(union)

    # ── BELONGS_TO ─────────────────────────────────────────

    def _discover_belongs_to(
        self,
        patterns: list[MetaPattern],
    ) -> list[KnowledgeEdge]:
        """发现 Gene → Pattern 的归属关系。"""
        edges: list[KnowledgeEdge] = []

        for pattern in patterns:
            for feat_name, feat_value in pattern.genes.items():
                gene_id = f"GENE_{feat_name.upper()}_{feat_value.upper()}"
                edges.append(KnowledgeEdge(
                    source_id=gene_id,
                    target_id=pattern.pattern_id,
                    relation_type=RelationType.BELONGS_TO,
                    weight=pattern.confidence,
                    evidence_count=pattern.sample_count,
                    confidence=pattern.confidence,
                ))

        return edges

    # ── WORKS_FOR ──────────────────────────────────────────

    def discover_works_for(
        self,
        pattern: MetaPattern,
        target_node: KnowledgeNode,
        node_type: str,
    ) -> KnowledgeEdge | None:
        """发现 Pattern 对特定目标的适用性。

        Args:
            pattern:      MetaPattern
            target_node:  目标节点
            node_type:    目标节点类型

        Returns:
            KnowledgeEdge 或 None
        """
        if pattern.success_rate < 0.5:
            return None

        return KnowledgeEdge(
            source_id=pattern.pattern_id,
            target_id=target_node.node_id,
            relation_type=RelationType.WORKS_FOR,
            weight=pattern.success_rate,
            evidence_count=pattern.sample_count,
            confidence=pattern.confidence,
            attributes={
                "target_type": node_type,
                "success_rate": round(pattern.success_rate, 4),
            },
        )

    # ── CAUSES ─────────────────────────────────────────────

    def discover_causal_chain(
        self,
        gene_id: str,
        pattern_id: str,
        metric_id: str,
        confidence: float = 0.7,
        evidence: int = 10,
    ) -> list[KnowledgeEdge]:
        """发现因果链: Gene → Pattern → Metric。

        Args:
            gene_id:     GENE 节点 ID
            pattern_id:  PATTERN 节点 ID
            metric_id:   METRIC 节点 ID
            confidence:  置信度
            evidence:    证据数

        Returns:
            [Gene→Pattern, Pattern→Metric] 边列表
        """
        return [
            KnowledgeEdge(
                source_id=gene_id,
                target_id=pattern_id,
                relation_type=RelationType.CAUSES,
                weight=confidence,
                evidence_count=evidence,
                confidence=confidence,
            ),
            KnowledgeEdge(
                source_id=pattern_id,
                target_id=metric_id,
                relation_type=RelationType.CAUSES,
                weight=confidence,
                evidence_count=evidence,
                confidence=confidence,
            ),
        ]

    def __repr__(self) -> str:
        return "RelationshipEngine()"