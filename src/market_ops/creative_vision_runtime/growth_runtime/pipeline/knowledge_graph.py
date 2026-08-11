"""E13.2.4 Reality Knowledge Graph — 知识图谱构建.

核心职责: 构建 Creative → Acquisition → User Segment → Revenue Outcome
的完整知识图谱，使 AI Agent 能够回答:
  - "为什么 P04 Witch 的第 17 个素材赚钱？"
  - "下一批应该生成什么 DNA？"

图谱结构:
  Creative ──[ACQUIRED_BY]──> Campaign
  Campaign ──[TARGETS]──> User Segment
  User Segment ──[GENERATED]──> Revenue Outcome
  Creative ──[ATTRIBUTED_TO]──> Revenue Outcome
  Creative ──[BELONGS_TO]──> Product
  Creative ──[CONTAINS]──> Creative DNA
  Creative ──[EVOLVED_FROM]──> Creative (parent)

数据流:
  AttributionEdge[] + CreativeFitnessVector[] → KnowledgeGraph → AI Agent Query
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    AttributionEdge,
    CreativeFitnessVector,
    EdgeType,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeNode,
    NodeType,
    PipelineConfig,
    PipelineStats,
)


# ═══════════════════════════════════════════════════════════════
# Knowledge Graph Builder
# ═══════════════════════════════════════════════════════════════


class KnowledgeGraphBuilder:
    """E13.2.4 知识图谱构建器.

    功能:
      1. 从 AttributionEdge 构建节点和边
      2. 从 CreativeFitnessVector 丰富节点属性
      3. 建立 Creative → Revenue 的完整链路
      4. 支持图谱查询和推理
    """

    def __init__(self, config: PipelineConfig | None = None):
        self._config = config or PipelineConfig()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

        self._graph = KnowledgeGraph(name="reality_knowledge_graph")
        self._node_counter: dict[NodeType, int] = defaultdict(int)

    # ── Properties ────────────────────────────────────────────

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    @property
    def graph(self) -> KnowledgeGraph:
        return self._graph

    # ── Graph Building ────────────────────────────────────────

    def build_from_attribution(
        self, attribution_edges: list[AttributionEdge],
    ) -> KnowledgeGraph:
        """从 AttributionEdge 构建知识图谱.

        Args:
            attribution_edges: 归因边列表

        Returns:
            KnowledgeGraph: 构建好的知识图谱
        """
        if not attribution_edges:
            return self._graph

        for edge in attribution_edges:
            self._add_creative_node(edge)
            self._add_campaign_node(edge)
            self._add_user_segment_node(edge)
            self._add_revenue_outcome_node(edge)
            self._add_network_node(edge)

            self._add_attribution_edges(edge)

        # 更新统计
        self._stats.graph_nodes = self._graph.node_count
        self._stats.graph_edges = self._graph.edge_count

        return self._graph

    def enrich_with_fitness(
        self, fitness_vectors: list[CreativeFitnessVector],
    ) -> None:
        """用 CreativeFitnessVector 丰富节点属性."""
        for vector in fitness_vectors:
            node = self._graph.get_node(vector.creative_id)
            if node:
                node.metrics = {
                    "fitness_score": vector.fitness_score,
                    "revenue_score": vector.revenue_score,
                    "growth_score": vector.growth_score,
                    "efficiency_score": vector.efficiency_score,
                    "d30_roas": vector.d30_roas,
                    "d30_ltv": vector.d30_ltv,
                    "ctr": vector.ctr,
                    "cpi": vector.cpi,
                    "total_revenue": vector.total_revenue,
                    "is_winner": 1.0 if vector.is_winner else 0.0,
                    "is_fatigued": 1.0 if vector.is_fatigued else 0.0,
                }
                node.properties["genome_id"] = vector.genome_id
                node.properties["is_winner"] = vector.is_winner
                node.properties["is_fatigued"] = vector.is_fatigued
                node.updated_at = datetime.now(timezone.utc).isoformat()

    # ── Node Creation ─────────────────────────────────────────

    def _add_creative_node(self, edge: AttributionEdge) -> None:
        """添加 Creative 节点."""
        if edge.creative_id and edge.creative_id not in self._graph.nodes:
            node = KnowledgeNode.create_creative_node(
                creative_id=edge.creative_id,
                creative_name=edge.creative_name,
                genome_id=edge.genome_id,
                product_id=edge.user_id,  # placeholder
            )
            node.metrics = {
                "spend": edge.spend,
                "revenue": edge.total_revenue,
                "roas": edge.roas_ratio,
                "installs": edge.installs,
            }
            self._graph.add_node(node)
            self._node_counter[NodeType.CREATIVE] += 1

    def _add_campaign_node(self, edge: AttributionEdge) -> None:
        """添加 Campaign 节点."""
        if edge.campaign_id and edge.campaign_id not in self._graph.nodes:
            node = KnowledgeNode(
                node_id=edge.campaign_id,
                node_type=NodeType.CAMPAIGN,
                label=edge.campaign_name or edge.campaign_id,
                properties={"network": edge.network},
            )
            self._graph.add_node(node)
            self._node_counter[NodeType.CAMPAIGN] += 1

    def _add_user_segment_node(self, edge: AttributionEdge) -> None:
        """添加 User Segment 节点."""
        segment_id = edge.user_segment or f"segment_{edge.user_id[:8]}"
        if segment_id and segment_id not in self._graph.nodes:
            node = KnowledgeNode.create_user_segment_node(
                segment_id=segment_id,
                segment_name=f"User {edge.user_id[:8]}",
                is_payer=edge.is_payer,
                payer_rate=edge.payer_rate,
                d7_retention=edge.d7_retention,
                d30_retention=edge.d30_retention,
            )
            node.metrics = {
                "ltv": edge.predicted_ltv,
                "iap_revenue": edge.iap_revenue,
                "ad_revenue": edge.ad_revenue,
                "total_revenue": edge.total_revenue,
            }
            self._graph.add_node(node)
            self._node_counter[NodeType.USER_SEGMENT] += 1

    def _add_revenue_outcome_node(self, edge: AttributionEdge) -> None:
        """添加 Revenue Outcome 节点."""
        outcome_id = f"revenue_{edge.creative_id}_{edge.date}"
        if outcome_id and outcome_id not in self._graph.nodes:
            node = KnowledgeNode.create_revenue_outcome_node(
                outcome_id=outcome_id,
                product_id=edge.user_id,
                iap_revenue=edge.iap_revenue,
                ad_revenue=edge.ad_revenue,
                total_revenue=edge.total_revenue,
                d7_roas=edge.d7_roas,
                d30_roas=edge.d30_roas,
                is_hybrid=edge.is_hybrid_monetization,
            )
            node.metrics = {
                "total_revenue": edge.total_revenue,
                "iap_revenue": edge.iap_revenue,
                "ad_revenue": edge.ad_revenue,
                "d7_roas": edge.d7_roas,
                "d30_roas": edge.d30_roas,
                "roas_ratio": edge.roas_ratio,
                "is_profitable": 1.0 if edge.is_profitable else 0.0,
            }
            self._graph.add_node(node)
            self._node_counter[NodeType.REVENUE_OUTCOME] += 1

    def _add_network_node(self, edge: AttributionEdge) -> None:
        """添加 Network 节点."""
        if edge.network and edge.network not in self._graph.nodes:
            node = KnowledgeNode(
                node_id=edge.network,
                node_type=NodeType.NETWORK,
                label=edge.network,
            )
            self._graph.add_node(node)
            self._node_counter[NodeType.NETWORK] += 1

    # ── Edge Creation ─────────────────────────────────────────

    def _add_attribution_edges(self, edge: AttributionEdge) -> None:
        """添加 Attribution 相关的边."""
        # Creative → Campaign: ACQUIRED_BY
        if edge.creative_id and edge.campaign_id:
            self._graph.add_edge(KnowledgeEdge(
                source_id=edge.creative_id,
                target_id=edge.campaign_id,
                edge_type=EdgeType.ATTRIBUTED_TO,
                weight=edge.attribution_confidence,
                confidence=edge.attribution_confidence,
                properties={"spend": edge.spend, "ctr": edge.ctr},
            ))

        # Campaign → User Segment: TARGETS
        segment_id = edge.user_segment or f"segment_{edge.user_id[:8]}"
        if edge.campaign_id and segment_id:
            self._graph.add_edge(KnowledgeEdge(
                source_id=edge.campaign_id,
                target_id=segment_id,
                edge_type=EdgeType.TARGETS,
                weight=edge.attribution_confidence,
                confidence=edge.attribution_confidence,
            ))

        # User Segment → Revenue Outcome: GENERATED
        outcome_id = f"revenue_{edge.creative_id}_{edge.date}"
        if segment_id and outcome_id:
            self._graph.add_edge(KnowledgeEdge(
                source_id=segment_id,
                target_id=outcome_id,
                edge_type=EdgeType.GENERATED,
                weight=edge.total_revenue,
                confidence=edge.attribution_confidence,
                properties={
                    "total_revenue": edge.total_revenue,
                    "iap_revenue": edge.iap_revenue,
                    "ad_revenue": edge.ad_revenue,
                },
            ))

        # Creative → Revenue Outcome: GENERATED (直接连接)
        if edge.creative_id and outcome_id:
            self._graph.add_edge(KnowledgeEdge(
                source_id=edge.creative_id,
                target_id=outcome_id,
                edge_type=EdgeType.GENERATED,
                weight=edge.total_revenue,
                confidence=edge.attribution_confidence,
                properties={
                    "total_revenue": edge.total_revenue,
                    "roas": edge.roas_ratio,
                    "d30_roas": edge.d30_roas,
                },
            ))

        # Campaign → Network: BELONGS_TO
        if edge.campaign_id and edge.network:
            self._graph.add_edge(KnowledgeEdge(
                source_id=edge.campaign_id,
                target_id=edge.network,
                edge_type=EdgeType.BELONGS_TO,
                weight=1.0,
                confidence=1.0,
            ))

    # ── Query & Reasoning ─────────────────────────────────────

    def explain_creative_performance(self, creative_id: str) -> dict[str, Any]:
        """解释某个 Creative 的表现: "为什么赚钱？" """
        node = self._graph.get_node(creative_id)
        if not node:
            return {"error": f"Creative {creative_id} not found"}

        # 获取邻居
        neighbors = self._graph.get_neighbors(creative_id)
        campaigns = [n for n in neighbors if n.node_type == NodeType.CAMPAIGN]
        revenue_outcomes = [n for n in neighbors if n.node_type == NodeType.REVENUE_OUTCOME]

        # 聚合 revenue
        total_revenue = sum(
            n.metrics.get("total_revenue", 0) for n in revenue_outcomes
        )
        total_iap = sum(
            n.metrics.get("iap_revenue", 0) for n in revenue_outcomes
        )
        total_ad = sum(
            n.metrics.get("ad_revenue", 0) for n in revenue_outcomes
        )

        # ROAS
        spend = node.metrics.get("spend", 0)
        roas = total_revenue / spend if spend > 0 else 0.0

        # 判断赚钱原因
        reasons: list[str] = []
        if roas > 1.5:
            reasons.append("High ROAS (>1.5x)")
        if node.metrics.get("is_winner", 0) > 0:
            reasons.append("Identified as Winner")
        if total_iap > 0 and total_ad > 0:
            reasons.append("Hybrid monetization (IAP + IAA)")
        elif total_iap > total_ad:
            reasons.append("IAP-dominant monetization")
        else:
            reasons.append("IAA-dominant monetization")

        return {
            "creative_id": creative_id,
            "creative_name": node.label,
            "genome_id": node.properties.get("genome_id", ""),
            "total_revenue": round(total_revenue, 4),
            "iap_revenue": round(total_iap, 4),
            "ad_revenue": round(total_ad, 4),
            "spend": round(spend, 4),
            "roas": round(roas, 4),
            "is_winner": node.properties.get("is_winner", False),
            "is_fatigued": node.properties.get("is_fatigued", False),
            "fitness_score": node.metrics.get("fitness_score", 0),
            "reasons": reasons,
            "campaigns": [n.label for n in campaigns],
            "revenue_outcomes": len(revenue_outcomes),
            "neighbors": len(neighbors),
        }

    def suggest_next_dna(self, product_id: str = "") -> dict[str, Any]:
        """建议下一批应该生成什么 DNA."""
        creative_nodes = self._graph.get_nodes_by_type(NodeType.CREATIVE)

        if not creative_nodes:
            return {"suggestion": "Not enough data to suggest DNA"}

        # 分析 Winner 的特征
        winners = [n for n in creative_nodes if n.properties.get("is_winner", False)]
        non_winners = [n for n in creative_nodes if not n.properties.get("is_winner", False)]

        # 提取 Winner 的高频特征
        winner_genomes = [
            n.properties.get("genome_id", "")
            for n in winners
            if n.properties.get("genome_id")
        ]

        # 提取 Winner 的高分指标
        high_fitness_metrics: dict[str, float] = {}
        for n in winners:
            for key, value in n.metrics.items():
                if isinstance(value, (int, float)):
                    high_fitness_metrics[key] = max(
                        high_fitness_metrics.get(key, 0.0),
                        value,
                    )

        return {
            "total_creatives": len(creative_nodes),
            "winner_count": len(winners),
            "non_winner_count": len(non_winners),
            "winner_genomes": winner_genomes[:5],
            "top_metrics": dict(
                sorted(high_fitness_metrics.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "suggestion": (
                "Amplify high-ROAS genomes, explore hybrid monetization creatives"
                if winners else "Not enough winners to suggest DNA direction"
            ),
        }

    def get_revenue_chain(self, creative_id: str) -> dict[str, Any]:
        """获取 Creative → Revenue 的完整链路."""
        chain = self._graph.get_creative_to_revenue_chain(creative_id)

        chain_steps: list[dict[str, Any]] = []
        total_revenue = 0.0
        for edge in chain:
            target_node = self._graph.get_node(edge.target_id)
            chain_steps.append({
                "from": edge.source_id,
                "to": edge.target_id,
                "edge_type": edge.edge_type.value,
                "weight": edge.weight,
                "target_type": target_node.node_type.value if target_node else "",
                "target_label": target_node.label if target_node else "",
            })
            total_revenue += edge.weight

        return {
            "creative_id": creative_id,
            "chain_length": len(chain),
            "total_revenue": round(total_revenue, 4),
            "steps": chain_steps,
        }

    def get_network_analysis(self) -> dict[str, Any]:
        """Network 分析: 哪个网络带来最高价值."""
        network_nodes = self._graph.get_nodes_by_type(NodeType.NETWORK)
        result: dict[str, Any] = {}

        for node in network_nodes:
            neighbors = self._graph.get_neighbors(node.node_id)
            campaigns = [n for n in neighbors if n.node_type == NodeType.CAMPAIGN]
            result[node.node_id] = {
                "campaign_count": len(campaigns),
                "label": node.label,
            }

        return result

    # ── Graph Statistics ──────────────────────────────────────

    def get_graph_stats(self) -> dict[str, Any]:
        """获取图谱统计."""
        node_types = defaultdict(int)
        for node in self._graph.nodes.values():
            node_types[node.node_type.value] += 1

        edge_types = defaultdict(int)
        for edge in self._graph.edges:
            edge_types[edge.edge_type.value] += 1

        return {
            "total_nodes": self._graph.node_count,
            "total_edges": self._graph.edge_count,
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
            "densest_nodes": self._get_densest_nodes(5),
        }

    def _get_densest_nodes(self, limit: int = 5) -> list[dict[str, Any]]:
        """获取连接最多的节点."""
        degree: dict[str, int] = defaultdict(int)
        for edge in self._graph.edges:
            degree[edge.source_id] += 1
            degree[edge.target_id] += 1

        sorted_degrees = sorted(degree.items(), key=lambda x: x[1], reverse=True)

        result: list[dict[str, Any]] = []
        for node_id, deg in sorted_degrees[:limit]:
            node = self._graph.get_node(node_id)
            result.append({
                "node_id": node_id,
                "degree": deg,
                "node_type": node.node_type.value if node else "",
                "label": node.label if node else "",
            })

        return result

    # ── Lifecycle ─────────────────────────────────────────────

    def flush(self) -> None:
        """清空图谱."""
        self._graph = KnowledgeGraph(name="reality_knowledge_graph")
        self._node_counter.clear()

    def reset(self) -> None:
        """重置图谱构建器."""
        self.flush()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

    def get_summary(self) -> dict[str, Any]:
        """获取图谱构建器摘要."""
        return {
            "graph_name": self._graph.name,
            "graph_stats": self.get_graph_stats(),
            "creative_count": self._node_counter.get(NodeType.CREATIVE, 0),
            "campaign_count": self._node_counter.get(NodeType.CAMPAIGN, 0),
            "user_segment_count": self._node_counter.get(NodeType.USER_SEGMENT, 0),
            "revenue_outcome_count": self._node_counter.get(NodeType.REVENUE_OUTCOME, 0),
            "network_count": self._node_counter.get(NodeType.NETWORK, 0),
        }