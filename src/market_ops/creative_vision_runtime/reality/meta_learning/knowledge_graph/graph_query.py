"""E12.5.3 — Graph Query Engine。

图查询引擎，为 E11 Mutation Engine 提供知识图谱查询能力。

查询场景:
  1. find_best_genes:        查询提升某个指标的最佳基因
  2. find_best_patterns:     查询最佳模式
  3. recommend_mutation:     为 E11 推荐突变策略
  4. find_similar_patterns:  查找相似模式
  5. find_transfer_candidates: 跨产品迁移候选
  6. find_gene_combinations: 查找最佳基因组合
  7. get_causal_chain:       获取因果链
"""

from __future__ import annotations

from collections import defaultdict

from .graph_store import GraphStore
from .models import (
    GraphQuery,
    GraphQueryResult,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
    RelationType,
)


class GraphQueryEngine:
    """图查询引擎 —— 为 E11 提供知识图谱查询。

    Usage:
        >>> engine = GraphQueryEngine(store)
        >>> result = engine.find_best_genes_for_metric("CTR")
        >>> mutation = engine.recommend_mutation(
        ...     product_id="p04",
        ...     target_metric="CTR",
        ... )
    """

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    # ── 场景 1: 查询提升某个指标的最佳基因 ──────────────────

    def find_best_genes_for_metric(
        self,
        metric: str,
        max_results: int = 10,
        min_confidence: float = 0.60,
    ) -> GraphQueryResult:
        """查询提升某个指标的最佳基因。

        Args:
            metric:        指标名称（ctr, roas, cvr 等）
            max_results:   最大返回数
            min_confidence: 最低置信度

        Returns:
            GraphQueryResult
        """
        metric_id = f"METRIC_{metric.upper()}"
        query = GraphQuery(
            query_type="find_best_genes",
            target_metric=metric,
            max_results=max_results,
            min_confidence=min_confidence,
        )

        # 查找指向 Metric 的 IMPROVES 边
        incoming_edges = self._store.query_edges_to(metric_id, RelationType.IMPROVES)
        incoming_edges = [e for e in incoming_edges if e.confidence >= min_confidence]
        incoming_edges.sort(key=lambda e: e.weight, reverse=True)

        recommendations: list[dict] = []
        for edge in incoming_edges[:max_results]:
            source_node = self._store.get_node(edge.source_id)
            if source_node is None:
                continue

            # 如果是 Pattern 节点，继续找其所属的 Gene 节点
            genes = self._find_genes_for_pattern(edge.source_id)

            recommendations.append({
                "pattern_id": edge.source_id,
                "pattern_name": source_node.name,
                "node_type": source_node.node_type.value,
                "genes": genes,
                "weight": round(edge.weight, 4),
                "confidence": round(edge.confidence, 4),
                "evidence_count": edge.evidence_count,
                "gain": edge.attributes.get("gain", 0),
            })

        # 收集相关节点
        nodes = [self._store.get_node(e.source_id) for e in incoming_edges[:max_results]]
        nodes = [n for n in nodes if n is not None]

        result = GraphQueryResult(
            query=query,
            nodes=nodes,
            edges=incoming_edges[:max_results],
            recommendations=recommendations,
            summary=f"Found {len(recommendations)} genes/patterns that improve {metric.upper()}",
        )
        return result

    # ── 场景 2: 查询最佳模式 ────────────────────────────────

    def find_best_patterns(
        self,
        max_results: int = 10,
        min_confidence: float = 0.60,
    ) -> GraphQueryResult:
        """查询全局最佳模式。

        Args:
            max_results:    最大返回数
            min_confidence: 最低置信度

        Returns:
            GraphQueryResult
        """
        query = GraphQuery(
            query_type="find_best_patterns",
            max_results=max_results,
            min_confidence=min_confidence,
        )

        pattern_nodes = self._store.get_nodes_by_type(NodeType.PATTERN)
        pattern_nodes = [n for n in pattern_nodes if n.confidence >= min_confidence]

        # 按 rank_score 降序
        pattern_nodes.sort(
            key=lambda n: n.attributes.get("rank_score", 0),
            reverse=True,
        )

        recommendations: list[dict] = []
        for node in pattern_nodes[:max_results]:
            rec = {
                "pattern_id": node.node_id,
                "pattern_name": node.name,
                "success_rate": node.attributes.get("success_rate", 0),
                "avg_roas_gain": node.attributes.get("avg_roas_gain", 0),
                "avg_ctr_gain": node.attributes.get("avg_ctr_gain", 0),
                "sample_count": node.attributes.get("sample_count", 0),
                "confidence": round(node.confidence, 4),
                "rank_score": node.attributes.get("rank_score", 0),
                "genes": node.attributes.get("genes", {}),
                "recommendation": node.attributes.get("recommendation", ""),
            }
            recommendations.append(rec)

        result = GraphQueryResult(
            query=query,
            nodes=pattern_nodes[:max_results],
            recommendations=recommendations,
            summary=f"Found {len(recommendations)} best patterns",
        )
        return result

    # ── 场景 3: 为 E11 推荐突变策略 ──────────────────────────

    def recommend_mutation(
        self,
        product_id: str = "",
        target_metric: str = "CTR",
        max_results: int = 5,
        min_confidence: float = 0.60,
    ) -> GraphQueryResult:
        """为 E11 Mutation Engine 推荐突变策略。

        Args:
            product_id:     产品 ID
            target_metric:  目标指标
            max_results:    最大返回数
            min_confidence: 最低置信度

        Returns:
            GraphQueryResult（recommendations 包含 mutation_priorities）
        """
        query = GraphQuery(
            query_type="recommend_mutation",
            product_id=product_id,
            target_metric=target_metric,
            max_results=max_results,
            min_confidence=min_confidence,
        )

        # 查找提升指标的最佳基因
        gene_result = self.find_best_genes_for_metric(
            metric=target_metric,
            max_results=max_results * 2,
            min_confidence=min_confidence,
        )

        recommendations: list[dict] = []
        for rec in gene_result.recommendations[:max_results]:
            mutation_prior = {
                "pattern_id": rec["pattern_id"],
                "pattern_name": rec["pattern_name"],
                "priority": rec["weight"],
                "confidence": rec["confidence"],
                "evidence_count": rec["evidence_count"],
                "gain": rec["gain"],
                "genes": rec["genes"],
                "strategy": "Amplify" if rec["weight"] >= 0.6 else "Explore",
                "explanation": (
                    f"'{rec['pattern_name']}' improves {target_metric.upper()} "
                    f"by {rec['gain']:.1%} with {rec['confidence']:.0%} confidence "
                    f"({rec['evidence_count']} experiments)"
                ),
            }
            recommendations.append(mutation_prior)

        # 收集相关节点
        nodes = gene_result.nodes

        result = GraphQueryResult(
            query=query,
            nodes=nodes,
            edges=gene_result.edges,
            recommendations=recommendations,
            summary=(
                f"Recommended {len(recommendations)} mutation strategies "
                f"for {target_metric.upper()} improvement"
            ),
        )
        return result

    # ── 场景 4: 相似模式 ────────────────────────────────────

    def find_similar_patterns(
        self,
        pattern_id: str,
        max_results: int = 5,
    ) -> GraphQueryResult:
        """查找与指定模式相似的其他模式。

        Args:
            pattern_id:   模式节点 ID
            max_results:  最大返回数

        Returns:
            GraphQueryResult
        """
        query = GraphQuery(
            query_type="find_similar_patterns",
            max_results=max_results,
        )

        neighbors = self._store.query_neighbors(
            pattern_id,
            relation_type=RelationType.SIMILAR_TO,
            max_results=max_results,
        )

        recommendations: list[dict] = []
        for neighbor_node, edge in neighbors:
            recommendations.append({
                "pattern_id": neighbor_node.node_id,
                "pattern_name": neighbor_node.name,
                "similarity": round(edge.weight, 4),
                "confidence": round(edge.confidence, 4),
            })

        nodes = [n for n, _ in neighbors]

        result = GraphQueryResult(
            query=query,
            nodes=nodes,
            edges=[e for _, e in neighbors],
            recommendations=recommendations,
            summary=f"Found {len(recommendations)} similar patterns",
        )
        return result

    # ── 场景 5: 跨产品迁移 ──────────────────────────────────

    def find_transfer_candidates(
        self,
        source_product_id: str,
        target_product_id: str = "",
        max_results: int = 5,
    ) -> GraphQueryResult:
        """查找跨产品迁移候选。

        Args:
            source_product_id: 源产品 ID
            target_product_id: 目标产品 ID
            max_results:       最大返回数

        Returns:
            GraphQueryResult
        """
        query = GraphQuery(
            query_type="find_transfer_candidates",
            product_id=source_product_id,
            max_results=max_results,
        )

        # 查找源产品的所有 Pattern
        source_product_node = self._store.get_node(
            f"PRODUCT_{source_product_id.upper()}"
        )

        # 获取全局最佳模式（它们可能适用于其他产品）
        best = self.find_best_patterns(max_results=max_results)

        recommendations: list[dict] = []
        for rec in best.recommendations[:max_results]:
            transfer_rec = dict(rec)
            transfer_rec["transferability"] = rec["confidence"]
            if target_product_id:
                transfer_rec["target_product"] = target_product_id
            recommendations.append(transfer_rec)

        result = GraphQueryResult(
            query=query,
            nodes=best.nodes,
            recommendations=recommendations,
            summary=(
                f"Found {len(recommendations)} transfer candidates "
                f"from {source_product_id}"
                + (f" to {target_product_id}" if target_product_id else "")
            ),
        )
        return result

    # ── 场景 6: 基因组合 ────────────────────────────────────

    def find_gene_combinations(
        self,
        max_results: int = 10,
        min_confidence: float = 0.60,
    ) -> GraphQueryResult:
        """查找最佳基因组合。

        Args:
            max_results:    最大返回数
            min_confidence: 最低置信度

        Returns:
            GraphQueryResult
        """
        query = GraphQuery(
            query_type="find_gene_combinations",
            max_results=max_results,
            min_confidence=min_confidence,
        )

        combine_edges = self._store.get_edges_by_type(RelationType.COMBINES_WITH)
        combine_edges = [e for e in combine_edges if e.confidence >= min_confidence]
        combine_edges.sort(key=lambda e: e.weight, reverse=True)

        recommendations: list[dict] = []
        for edge in combine_edges[:max_results]:
            source_node = self._store.get_node(edge.source_id)
            target_node = self._store.get_node(edge.target_id)

            recommendations.append({
                "gene_1": source_node.name if source_node else edge.source_id,
                "gene_2": target_node.name if target_node else edge.target_id,
                "combined_weight": round(edge.weight, 4),
                "confidence": round(edge.confidence, 4),
                "evidence_count": edge.evidence_count,
                "gene_1_id": edge.source_id,
                "gene_2_id": edge.target_id,
            })

        nodes: list[KnowledgeNode] = []
        seen_ids: set[str] = set()
        for edge in combine_edges[:max_results]:
            for nid in [edge.source_id, edge.target_id]:
                if nid not in seen_ids:
                    node = self._store.get_node(nid)
                    if node:
                        nodes.append(node)
                        seen_ids.add(nid)

        result = GraphQueryResult(
            query=query,
            nodes=nodes,
            edges=combine_edges[:max_results],
            recommendations=recommendations,
            summary=f"Found {len(recommendations)} gene combinations",
        )
        return result

    # ── 场景 7: 因果链 ──────────────────────────────────────

    def get_causal_chain(
        self,
        gene_id: str,
        metric_id: str = "METRIC_CTR",
        max_depth: int = 5,
    ) -> GraphQueryResult:
        """获取基因到指标的因果链。

        Args:
            gene_id:    GENE 节点 ID
            metric_id:  METRIC 节点 ID
            max_depth:  最大深度

        Returns:
            GraphQueryResult
        """
        query = GraphQuery(
            query_type="get_causal_chain",
            target_metric=metric_id,
        )

        path = self._store.find_path(gene_id, metric_id, max_depth)

        if path:
            gene_node = self._store.get_node(gene_id)
            metric_node = self._store.get_node(metric_id)

            nodes: list[KnowledgeNode] = []
            if gene_node:
                nodes.append(gene_node)
            if metric_node:
                nodes.append(metric_node)

            # 中间节点
            for edge in path:
                for nid in [edge.source_id, edge.target_id]:
                    if nid not in {n.node_id for n in nodes}:
                        node = self._store.get_node(nid)
                        if node:
                            nodes.append(node)

            summary = (
                f"Causal chain found: {gene_id} → {metric_id} "
                f"({len(path)} steps)"
            )
        else:
            nodes = []
            path = []
            summary = f"No causal chain found from {gene_id} to {metric_id}"

        result = GraphQueryResult(
            query=query,
            nodes=nodes,
            edges=path,
            paths=[path] if path else [],
            summary=summary,
        )
        return result

    # ── 辅助 ────────────────────────────────────────────────

    def _find_genes_for_pattern(self, pattern_id: str) -> dict[str, str]:
        """查找 Pattern 的基因列表。"""
        neighbors = self._store.query_neighbors(
            pattern_id,
            relation_type=RelationType.BELONGS_TO,
        )
        # 从 BELONGS_TO 边中提取基因信息
        genes: dict[str, str] = {}
        for node, edge in neighbors:
            if node.node_type == NodeType.GENE:
                feat = node.attributes.get("gene_feature", "")
                val = node.attributes.get("gene_value", "")
                if feat and val:
                    genes[feat] = val

        # 如果图中没有 BELONGS_TO 边，尝试从 Pattern 节点属性中获取
        if not genes:
            pattern_node = self._store.get_node(pattern_id)
            if pattern_node and "genes" in pattern_node.attributes:
                genes = pattern_node.attributes["genes"]

        return genes

    def generate_query_report(
        self,
        product_id: str = "",
        target_metric: str = "CTR",
    ) -> dict:
        """生成综合查询报告。

        Args:
            product_id:    产品 ID
            target_metric: 目标指标

        Returns:
            报告字典
        """
        best_genes = self.find_best_genes_for_metric(target_metric)
        best_patterns = self.find_best_patterns()
        combinations = self.find_gene_combinations()

        report = {
            "target_metric": target_metric,
            "product_id": product_id or "global",
            "top_genes": best_genes.recommendations[:5],
            "top_patterns": best_patterns.recommendations[:5],
            "top_combinations": combinations.recommendations[:5],
            "mutation_strategy": self.recommend_mutation(
                product_id=product_id,
                target_metric=target_metric,
            ).recommendations[:5],
        }

        if product_id:
            transfer = self.find_transfer_candidates(product_id)
            report["transfer_candidates"] = transfer.recommendations[:3]

        return report

    def __repr__(self) -> str:
        return f"GraphQueryEngine(store={self._store})"