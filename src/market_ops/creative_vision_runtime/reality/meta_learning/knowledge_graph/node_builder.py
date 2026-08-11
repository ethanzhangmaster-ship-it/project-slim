"""E12.5.3 — Node Builder。

将 E12.5.2 的 MetaPattern 和 GeneImpactScore 转换为 KnowledgeNode。

流程:
  MetaPattern → KnowledgeNode (PATTERN)
  GeneImpactScore → KnowledgeNode (GENE)
  Pattern genes → KnowledgeNode (GENE)
  Market/Product/Platform → KnowledgeNode (MARKET/AUDIENCE/PLATFORM)
  Metrics → KnowledgeNode (METRIC)
"""

from __future__ import annotations

from ..pattern_miner.models import GeneImpactScore, MetaPattern, PatternType
from .models import KnowledgeNode, NodeType, RelationType


# ── Metric mapping ────────────────────────────────────────


METRIC_NODE_IDS = {
    "ctr": "METRIC_CTR",
    "roas": "METRIC_ROAS",
    "cvr": "METRIC_CVR",
    "cpi": "METRIC_CPI",
    "ipm": "METRIC_IPM",
    "d7_retention": "METRIC_D7",
    "payer_rate": "METRIC_PAYER",
}

METRIC_NAMES = {
    "ctr": "Click-Through Rate",
    "roas": "Return on Ad Spend",
    "cvr": "Conversion Rate",
    "cpi": "Cost Per Install",
    "ipm": "Installs Per Mille",
    "d7_retention": "Day 7 Retention",
    "payer_rate": "Payer Rate",
}


# ── NodeBuilder ────────────────────────────────────────────


class NodeBuilder:
    """节点构建器 —— 将 Pattern/Gene 转换为 KnowledgeNode。

    Usage:
        >>> builder = NodeBuilder()
        >>> node = builder.build_pattern_node(pattern)
        >>> gene_node = builder.build_gene_node("rescue", "emotion", 0.91)
        >>> metric_nodes = builder.build_metric_nodes()
    """

    def build_pattern_node(self, pattern: MetaPattern) -> KnowledgeNode:
        """从 MetaPattern 构建 PATTERN 节点。

        Args:
            pattern: MetaPattern 实例

        Returns:
            KnowledgeNode (PATTERN)
        """
        return KnowledgeNode(
            node_id=pattern.pattern_id,
            node_type=NodeType.PATTERN,
            name=pattern.name,
            attributes={
                "pattern_type": pattern.pattern_type.value,
                "genes": pattern.genes,
                "success_rate": round(pattern.success_rate, 4),
                "avg_roas_gain": round(pattern.avg_roas_gain, 4),
                "avg_ctr_gain": round(pattern.avg_ctr_gain, 4),
                "avg_cvr_gain": round(pattern.avg_cvr_gain, 4),
                "sample_count": pattern.sample_count,
                "rank_score": round(pattern.rank_score, 4),
                "insight": pattern.insight,
                "recommendation": pattern.recommendation,
            },
            confidence=pattern.confidence,
            source_ids=pattern.evidence,
            labels=[pattern.pattern_type.value, "pattern"],
        )

    def build_gene_node(
        self,
        gene_value: str,
        gene_feature: str,
        confidence: float = 0.7,
        gene_category: str = "",
        extra_attrs: dict | None = None,
    ) -> KnowledgeNode:
        """构建 GENE 节点。

        Args:
            gene_value:    基因值（如 rescue, bright_colorful）
            gene_feature:  基因特征名（如 emotion, style）
            confidence:    置信度
            gene_category: 基因类别
            extra_attrs:   额外属性

        Returns:
            KnowledgeNode (GENE)
        """
        node_id = f"GENE_{gene_feature.upper()}_{gene_value.upper()}"
        attributes = {
            "gene_feature": gene_feature,
            "gene_value": gene_value,
            "gene_category": gene_category,
        }
        if extra_attrs:
            attributes.update(extra_attrs)

        return KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.GENE,
            name=f"{gene_feature.replace('_', ' ').title()}: {gene_value.replace('_', ' ').title()}",
            attributes=attributes,
            confidence=confidence,
            labels=[gene_category, "gene"],
        )

    def build_gene_nodes_from_pattern(
        self,
        pattern: MetaPattern,
    ) -> list[KnowledgeNode]:
        """从 Pattern 的 genes 构建所有 GENE 节点。

        Args:
            pattern: MetaPattern 实例

        Returns:
            KnowledgeNode 列表
        """
        nodes: list[KnowledgeNode] = []
        for feat_name, feat_value in pattern.genes.items():
            node = self.build_gene_node(
                gene_value=feat_value,
                gene_feature=feat_name,
                confidence=pattern.confidence,
                gene_category=pattern.pattern_type.value,
            )
            nodes.append(node)
        return nodes

    def build_gene_node_from_impact(
        self,
        impact: GeneImpactScore,
    ) -> KnowledgeNode:
        """从 GeneImpactScore 构建 GENE 节点。

        Args:
            impact: GeneImpactScore 实例

        Returns:
            KnowledgeNode (GENE)
        """
        return KnowledgeNode(
            node_id=f"GENE_{impact.gene_feature.upper()}_{impact.gene_value.upper()}",
            node_type=NodeType.GENE,
            name=f"{impact.gene_feature.title()}: {impact.gene_value.title()}",
            attributes={
                "gene_feature": impact.gene_feature,
                "gene_value": impact.gene_value,
                "gene_category": impact.gene_category,
                "impact_score": round(impact.impact_score, 4),
                "lift_pct": round(impact.lift_pct, 4),
                "sample_count": impact.sample_count,
            },
            confidence=impact.confidence,
            labels=[impact.gene_category, "gene"],
        )

    def build_market_node(
        self,
        market: str,
        confidence: float = 0.8,
    ) -> KnowledgeNode:
        """构建 MARKET 节点。

        Args:
            market:     市场代码（如 US, EU, JP）
            confidence: 置信度

        Returns:
            KnowledgeNode (MARKET)
        """
        return KnowledgeNode(
            node_id=f"MARKET_{market.upper()}",
            node_type=NodeType.MARKET,
            name=f"Market: {market.upper()}",
            attributes={"market": market},
            confidence=confidence,
            labels=["market", market.lower()],
        )

    def build_product_node(
        self,
        product_id: str,
        product_name: str = "",
        confidence: float = 0.8,
    ) -> KnowledgeNode:
        """构建 PRODUCT 节点。"""
        return KnowledgeNode(
            node_id=f"PRODUCT_{product_id.upper()}",
            node_type=NodeType.PRODUCT,
            name=product_name or f"Product: {product_id}",
            attributes={"product_id": product_id, "product_name": product_name},
            confidence=confidence,
            labels=["product"],
        )

    def build_platform_node(
        self,
        platform: str,
        confidence: float = 0.9,
    ) -> KnowledgeNode:
        """构建 PLATFORM 节点。"""
        return KnowledgeNode(
            node_id=f"PLATFORM_{platform.upper()}",
            node_type=NodeType.PLATFORM,
            name=f"Platform: {platform.title()}",
            attributes={"platform": platform},
            confidence=confidence,
            labels=["platform", platform.lower()],
        )

    def build_audience_node(
        self,
        audience_name: str,
        attributes: dict | None = None,
        confidence: float = 0.7,
    ) -> KnowledgeNode:
        """构建 AUDIENCE 节点。"""
        node_id = f"AUDIENCE_{audience_name.upper().replace(' ', '_')}"
        return KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.AUDIENCE,
            name=f"Audience: {audience_name}",
            attributes=attributes or {"segment": audience_name},
            confidence=confidence,
            labels=["audience"],
        )

    def build_metric_nodes(self) -> list[KnowledgeNode]:
        """构建所有标准 METRIC 节点。"""
        nodes: list[KnowledgeNode] = []
        for metric_key, metric_id in METRIC_NODE_IDS.items():
            nodes.append(KnowledgeNode(
                node_id=metric_id,
                node_type=NodeType.METRIC,
                name=METRIC_NAMES.get(metric_key, metric_key.upper()),
                attributes={"metric": metric_key},
                confidence=1.0,
                labels=["metric"],
            ))
        return nodes

    def build_experiment_node(
        self,
        experiment_id: str,
        name: str = "",
        confidence: float = 0.8,
        extra_attrs: dict | None = None,
    ) -> KnowledgeNode:
        """构建 EXPERIMENT 节点。"""
        return KnowledgeNode(
            node_id=f"EXP_{experiment_id}",
            node_type=NodeType.EXPERIMENT,
            name=name or f"Experiment: {experiment_id}",
            attributes=extra_attrs or {},
            confidence=confidence,
            labels=["experiment"],
        )

    def build_creative_node(
        self,
        creative_id: str,
        name: str = "",
        confidence: float = 0.7,
        extra_attrs: dict | None = None,
    ) -> KnowledgeNode:
        """构建 CREATIVE 节点。"""
        return KnowledgeNode(
            node_id=f"CREATIVE_{creative_id}",
            node_type=NodeType.CREATIVE,
            name=name or f"Creative: {creative_id}",
            attributes=extra_attrs or {},
            confidence=confidence,
            labels=["creative"],
        )

    def build_full_graph_from_patterns(
        self,
        patterns: list[MetaPattern],
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """从 Pattern 列表构建完整子图。

        返回:
            (nodes, edges) — 包含 Pattern, Gene, Metric 节点及其关系
        """
        from .models import KnowledgeEdge

        nodes: list[KnowledgeNode] = []
        edges: list[KnowledgeEdge] = []

        # 添加标准 Metric 节点
        metric_nodes = self.build_metric_nodes()
        nodes.extend(metric_nodes)

        seen_gene_ids: set[str] = set()
        seen_pattern_ids: set[str] = set()

        for pattern in patterns:
            # Pattern 节点
            if pattern.pattern_id not in seen_pattern_ids:
                pattern_node = self.build_pattern_node(pattern)
                nodes.append(pattern_node)
                seen_pattern_ids.add(pattern.pattern_id)

            # Gene 节点
            gene_nodes = self.build_gene_nodes_from_pattern(pattern)
            for gene_node in gene_nodes:
                if gene_node.node_id not in seen_gene_ids:
                    nodes.append(gene_node)
                    seen_gene_ids.add(gene_node.node_id)

                # Gene → Pattern (BELONGS_TO)
                edges.append(KnowledgeEdge(
                    source_id=gene_node.node_id,
                    target_id=pattern.pattern_id,
                    relation_type=RelationType.BELONGS_TO,
                    weight=pattern.confidence,
                    evidence_count=pattern.sample_count,
                    confidence=pattern.confidence,
                ))

            # Pattern → Metric (IMPROVES)
            if pattern.avg_ctr_gain > 0:
                edges.append(KnowledgeEdge(
                    source_id=pattern.pattern_id,
                    target_id="METRIC_CTR",
                    relation_type=RelationType.IMPROVES,
                    weight=min(pattern.avg_ctr_gain, 1.0),
                    evidence_count=pattern.sample_count,
                    confidence=pattern.confidence,
                    attributes={"gain": round(pattern.avg_ctr_gain, 4)},
                ))

            if pattern.avg_roas_gain > 0:
                edges.append(KnowledgeEdge(
                    source_id=pattern.pattern_id,
                    target_id="METRIC_ROAS",
                    relation_type=RelationType.IMPROVES,
                    weight=min(pattern.avg_roas_gain, 1.0),
                    evidence_count=pattern.sample_count,
                    confidence=pattern.confidence,
                    attributes={"gain": round(pattern.avg_roas_gain, 4)},
                ))

            if pattern.avg_cvr_gain > 0:
                edges.append(KnowledgeEdge(
                    source_id=pattern.pattern_id,
                    target_id="METRIC_CVR",
                    relation_type=RelationType.IMPROVES,
                    weight=min(pattern.avg_cvr_gain, 1.0),
                    evidence_count=pattern.sample_count,
                    confidence=pattern.confidence,
                    attributes={"gain": round(pattern.avg_cvr_gain, 4)},
                ))

        return nodes, edges

    def __repr__(self) -> str:
        return "NodeBuilder()"