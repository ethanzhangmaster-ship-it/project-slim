"""E13.2 Pipeline Models — Reality Data Pipeline 统一数据模型.

模块:
  - RawEvent: 原始事件 (从 Connector 进入 Pipeline)
  - NormalizedEvent: 标准化事件 (清洗后)
  - CreativeFitnessVector: 创意适应度向量
  - AttributionEdge: 归因边 (Creative → User → Revenue)
  - KnowledgeNode: 知识图谱节点
  - KnowledgeEdge: 知识图谱边
  - PipelineConfig: Pipeline 配置
  - PipelineStats: Pipeline 统计
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class PipelineStage(str, Enum):
    """Pipeline 阶段."""
    INGESTION = "ingestion"
    NORMALIZATION = "normalization"
    ATTRIBUTION = "attribution"
    FEATURE = "feature"
    GRAPH = "graph"


class EventStatus(str, Enum):
    """事件处理状态."""
    RAW = "raw"
    NORMALIZED = "normalized"
    ATTRIBUTED = "attributed"
    FEATURIZED = "featurized"
    INDEXED = "indexed"
    ERROR = "error"
    DROPPED = "dropped"


class NodeType(str, Enum):
    """知识图谱节点类型."""
    CREATIVE = "creative"
    CAMPAIGN = "campaign"
    AD_SET = "ad_set"
    USER_SEGMENT = "user_segment"
    PRODUCT = "product"
    NETWORK = "network"
    COUNTRY = "country"
    AD_FORMAT = "ad_format"
    REVENUE_OUTCOME = "revenue_outcome"
    CREATIVE_DNA = "creative_dna"


class EdgeType(str, Enum):
    """知识图谱边类型."""
    ACQUIRED_BY = "acquired_by"
    ATTRIBUTED_TO = "attributed_to"
    GENERATED = "generated"
    BELONGS_TO = "belongs_to"
    TARGETS = "targets"
    CONTAINS = "contains"
    EVOLVED_FROM = "evolved_from"
    MONETIZES_VIA = "monetizes_via"


class AttributionType(str, Enum):
    """归因类型."""
    LAST_CLICK = "last_click"
    MULTI_TOUCH = "multi_touch"
    PROBABILISTIC = "probabilistic"
    DETERMINISTIC = "deterministic"


# ═══════════════════════════════════════════════════════════════
# Raw Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class RawEvent:
    """原始事件 — 从 Connector 进入 Pipeline 的原始数据."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""  # meta_ads, adjust, max
    event_type: str = ""  # spend, install, revenue, impression
    product_id: str = ""
    date: str = ""

    # Raw payload
    payload: dict[str, Any] = field(default_factory=dict)

    # Trace
    trace_id: str = ""
    batch_id: str = ""

    # Status
    status: EventStatus = EventStatus.RAW

    # Timestamps
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "event_type": self.event_type,
            "product_id": self.product_id,
            "date": self.date,
            "status": self.status.value,
            "ingested_at": self.ingested_at,
            "source_timestamp": self.source_timestamp,
            "trace_id": self.trace_id,
            "batch_id": self.batch_id,
        }

    @property
    def is_spend_event(self) -> bool:
        return self.event_type in ("spend", "cost", "impression")

    @property
    def is_revenue_event(self) -> bool:
        return self.event_type in ("revenue", "purchase", "ad_revenue")

    @property
    def is_attribution_event(self) -> bool:
        return self.event_type in ("install", "reattribution", "attribution")


# ═══════════════════════════════════════════════════════════════
# Normalized Event
# ═══════════════════════════════════════════════════════════════


@dataclass
class NormalizedEvent:
    """标准化事件 — 清洗整形后的统一事件."""
    event_id: str = ""
    source_event_id: str = ""
    source: str = ""
    event_type: str = ""
    product_id: str = ""
    date: str = ""

    # Standardized metrics
    metrics: dict[str, float] = field(default_factory=dict)

    # Dimensions
    campaign_id: str = ""
    adset_id: str = ""
    creative_id: str = ""
    user_id: str = ""
    network: str = ""
    country: str = ""
    platform: str = ""

    # Status
    status: EventStatus = EventStatus.NORMALIZED

    # Validation
    validation_errors: list[str] = field(default_factory=list)
    confidence: float = 1.0

    # Trace
    trace_id: str = ""
    batch_id: str = ""

    normalized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source_event_id": self.source_event_id,
            "source": self.source,
            "event_type": self.event_type,
            "product_id": self.product_id,
            "date": self.date,
            "metrics": self.metrics,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "creative_id": self.creative_id,
            "network": self.network,
            "country": self.country,
            "status": self.status.value,
            "confidence": self.confidence,
            "trace_id": self.trace_id,
        }

    @property
    def is_valid(self) -> bool:
        return len(self.validation_errors) == 0

    @property
    def has_creative_id(self) -> bool:
        return bool(self.creative_id)

    @property
    def has_campaign_id(self) -> bool:
        return bool(self.campaign_id)

    def get_metric(self, key: str, default: float = 0.0) -> float:
        return self.metrics.get(key, default)


# ═══════════════════════════════════════════════════════════════
# Attribution Edge
# ═══════════════════════════════════════════════════════════════


@dataclass
class AttributionEdge:
    """归因边 — 连接 Creative → User → Revenue 的完整链路."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Source (Creative)
    creative_id: str = ""
    creative_name: str = ""
    genome_id: str = ""  # Creative DNA genome_id

    # Campaign
    campaign_id: str = ""
    campaign_name: str = ""
    network: str = ""

    # User
    user_id: str = ""
    user_segment: str = ""

    # Spend
    spend: float = 0.0
    cpi: float = 0.0
    ctr: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0

    # Revenue
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    total_revenue: float = 0.0

    # LTV
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    predicted_ltv: float = 0.0

    # ROAS
    d7_roas: float = 0.0
    d30_roas: float = 0.0

    # Retention
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # Payer
    is_payer: bool = False
    payer_rate: float = 0.0

    # Attribution
    attribution_type: AttributionType = AttributionType.LAST_CLICK
    attribution_confidence: float = 1.0

    # Time
    date: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "genome_id": self.genome_id,
            "campaign_id": self.campaign_id,
            "network": self.network,
            "user_id": self.user_id,
            "spend": round(self.spend, 4),
            "cpi": round(self.cpi, 4),
            "ctr": round(self.ctr, 6),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "iap_revenue": round(self.iap_revenue, 4),
            "ad_revenue": round(self.ad_revenue, 4),
            "total_revenue": round(self.total_revenue, 4),
            "d7_ltv": round(self.d7_ltv, 4),
            "d30_ltv": round(self.d30_ltv, 4),
            "d7_roas": round(self.d7_roas, 4),
            "d30_roas": round(self.d30_roas, 4),
            "d1_retention": round(self.d1_retention, 4),
            "d7_retention": round(self.d7_retention, 4),
            "d30_retention": round(self.d30_retention, 4),
            "is_payer": self.is_payer,
            "payer_rate": round(self.payer_rate, 4),
            "attribution_type": self.attribution_type.value,
            "attribution_confidence": round(self.attribution_confidence, 2),
            "date": self.date,
        }

    @property
    def is_profitable(self) -> bool:
        return self.total_revenue > self.spend

    @property
    def roas_ratio(self) -> float:
        if self.spend == 0:
            return 0.0
        return self.total_revenue / self.spend

    @property
    def total_value_per_user(self) -> float:
        """每个用户的总价值 (包括 IAP + IAA)."""
        return self.total_revenue

    @property
    def is_hybrid_monetization(self) -> bool:
        """是否混合变现 (IAP > 0 且 IAA > 0)."""
        return self.iap_revenue > 0 and self.ad_revenue > 0


# ═══════════════════════════════════════════════════════════════
# Creative Fitness Vector
# ═══════════════════════════════════════════════════════════════


@dataclass
class CreativeFitnessVector:
    """创意适应度向量 — 综合评估创意表现的多维向量."""
    creative_id: str = ""
    creative_name: str = ""
    genome_id: str = ""
    product_id: str = ""
    date: str = ""

    # Acquisition metrics
    ctr: float = 0.0
    cpi: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    spend: float = 0.0

    # Revenue metrics
    iap_revenue: float = 0.0
    ad_revenue: float = 0.0
    total_revenue: float = 0.0

    # ROAS
    d1_roas: float = 0.0
    d7_roas: float = 0.0
    d30_roas: float = 0.0

    # LTV
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    predicted_ltv: float = 0.0

    # Retention
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    d30_retention: float = 0.0

    # Conversion
    iap_conversion: float = 0.0
    payer_rate: float = 0.0

    # IAA metrics
    ad_arpdau: float = 0.0
    ecpm: float = 0.0
    fill_rate: float = 0.0

    # Composite scores
    fitness_score: float = 0.0
    revenue_score: float = 0.0
    growth_score: float = 0.0
    efficiency_score: float = 0.0

    # Confidence
    sample_size: int = 0
    confidence: float = 0.0

    # Status
    is_winner: bool = False
    is_fatigued: bool = False
    fatigue_score: float = 0.0

    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "creative_name": self.creative_name,
            "genome_id": self.genome_id,
            "product_id": self.product_id,
            "date": self.date,
            "ctr": round(self.ctr, 6),
            "cpi": round(self.cpi, 4),
            "cpm": round(self.cpm, 4),
            "cpc": round(self.cpc, 4),
            "impressions": self.impressions,
            "clicks": self.clicks,
            "installs": self.installs,
            "spend": round(self.spend, 4),
            "iap_revenue": round(self.iap_revenue, 4),
            "ad_revenue": round(self.ad_revenue, 4),
            "total_revenue": round(self.total_revenue, 4),
            "d1_roas": round(self.d1_roas, 4),
            "d7_roas": round(self.d7_roas, 4),
            "d30_roas": round(self.d30_roas, 4),
            "d7_ltv": round(self.d7_ltv, 4),
            "d30_ltv": round(self.d30_ltv, 4),
            "predicted_ltv": round(self.predicted_ltv, 4),
            "d1_retention": round(self.d1_retention, 4),
            "d7_retention": round(self.d7_retention, 4),
            "d30_retention": round(self.d30_retention, 4),
            "iap_conversion": round(self.iap_conversion, 4),
            "payer_rate": round(self.payer_rate, 4),
            "ad_arpdau": round(self.ad_arpdau, 6),
            "ecpm": round(self.ecpm, 4),
            "fill_rate": round(self.fill_rate, 4),
            "fitness_score": round(self.fitness_score, 4),
            "revenue_score": round(self.revenue_score, 4),
            "growth_score": round(self.growth_score, 4),
            "efficiency_score": round(self.efficiency_score, 4),
            "sample_size": self.sample_size,
            "confidence": round(self.confidence, 2),
            "is_winner": self.is_winner,
            "is_fatigued": self.is_fatigued,
            "fatigue_score": round(self.fatigue_score, 4),
        }

    @property
    def is_hybrid(self) -> bool:
        return self.iap_revenue > 0 and self.ad_revenue > 0

    @property
    def revenue_per_install(self) -> float:
        if self.installs == 0:
            return 0.0
        return self.total_revenue / self.installs

    @property
    def is_confident(self) -> bool:
        """样本量 > 1000 且置信度 > 0.8."""
        return self.sample_size >= 1000 and self.confidence >= 0.8

    def to_vector(self) -> list[float]:
        """转换为特征向量 (用于 ML 模型)."""
        return [
            self.ctr, self.cpi, self.cpm, self.cpc,
            self.d1_roas, self.d7_roas, self.d30_roas,
            self.d7_ltv, self.d30_ltv, self.predicted_ltv,
            self.d1_retention, self.d7_retention, self.d30_retention,
            self.iap_conversion, self.payer_rate,
            self.ad_arpdau, self.ecpm, self.fill_rate,
            self.fitness_score, self.revenue_score, self.growth_score,
            self.efficiency_score, self.fatigue_score,
        ]


# ═══════════════════════════════════════════════════════════════
# Knowledge Graph
# ═══════════════════════════════════════════════════════════════


@dataclass
class KnowledgeNode:
    """知识图谱节点."""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_type: NodeType = NodeType.CREATIVE
    label: str = ""
    product_id: str = ""

    # Properties
    properties: dict[str, Any] = field(default_factory=dict)

    # Metrics (computed)
    metrics: dict[str, float] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "product_id": self.product_id,
            "properties": self.properties,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "updated_at": self.updated_at or self.created_at,
        }

    @classmethod
    def create_creative_node(
        cls, creative_id: str, creative_name: str = "", genome_id: str = "",
        product_id: str = "", **kwargs: Any,
    ) -> KnowledgeNode:
        return cls(
            node_id=creative_id,
            node_type=NodeType.CREATIVE,
            label=creative_name or creative_id,
            product_id=product_id,
            properties={"genome_id": genome_id, **kwargs},
        )

    @classmethod
    def create_user_segment_node(
        cls, segment_id: str, segment_name: str = "", product_id: str = "",
        **kwargs: Any,
    ) -> KnowledgeNode:
        return cls(
            node_id=segment_id,
            node_type=NodeType.USER_SEGMENT,
            label=segment_name or segment_id,
            product_id=product_id,
            properties=kwargs,
        )

    @classmethod
    def create_revenue_outcome_node(
        cls, outcome_id: str, product_id: str = "", **kwargs: Any,
    ) -> KnowledgeNode:
        return cls(
            node_id=outcome_id,
            node_type=NodeType.REVENUE_OUTCOME,
            label=f"Revenue: {outcome_id}",
            product_id=product_id,
            properties=kwargs,
        )


@dataclass
class KnowledgeEdge:
    """知识图谱边."""
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    edge_type: EdgeType = EdgeType.ATTRIBUTED_TO

    # Weight / Confidence
    weight: float = 1.0
    confidence: float = 1.0

    # Properties
    properties: dict[str, Any] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "weight": round(self.weight, 4),
            "confidence": round(self.confidence, 2),
            "properties": self.properties,
        }


@dataclass
class KnowledgeGraph:
    """知识图谱."""
    graph_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    product_id: str = ""

    nodes: dict[str, KnowledgeNode] = field(default_factory=dict)
    edges: list[KnowledgeEdge] = field(default_factory=list)

    # Indexes
    _node_type_index: dict[NodeType, list[str]] = field(default_factory=dict)
    _edge_type_index: dict[EdgeType, list[str]] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = ""

    def add_node(self, node: KnowledgeNode) -> None:
        self.nodes[node.node_id] = node
        self._node_type_index.setdefault(node.node_type, []).append(node.node_id)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_edge(self, edge: KnowledgeEdge) -> None:
        self.edges.append(edge)
        self._edge_type_index.setdefault(edge.edge_type, []).append(edge.edge_id)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> list[KnowledgeNode]:
        ids = self._node_type_index.get(node_type, [])
        return [self.nodes[nid] for nid in ids if nid in self.nodes]

    def get_edges_by_type(self, edge_type: EdgeType) -> list[KnowledgeEdge]:
        ids = self._edge_type_index.get(edge_type, [])
        edge_map = {e.edge_id: e for e in self.edges}
        return [edge_map[eid] for eid in ids if eid in edge_map]

    def get_neighbors(self, node_id: str) -> list[KnowledgeNode]:
        neighbors: list[KnowledgeNode] = []
        for edge in self.edges:
            if edge.source_id == node_id and edge.target_id in self.nodes:
                neighbors.append(self.nodes[edge.target_id])
            elif edge.target_id == node_id and edge.source_id in self.nodes:
                neighbors.append(self.nodes[edge.source_id])
        return neighbors

    def get_creative_to_revenue_chain(self, creative_id: str) -> list[KnowledgeEdge]:
        """获取 Creative → Revenue 的完整链路."""
        chain: list[KnowledgeEdge] = []
        visited: set[str] = set()
        current = creative_id

        while current not in visited:
            visited.add(current)
            found = False
            for edge in self.edges:
                if edge.source_id == current:
                    chain.append(edge)
                    current = edge.target_id
                    found = True
                    if edge.edge_type == EdgeType.GENERATED:
                        break  # reached revenue outcome
                    break
            if not found:
                break

        return chain

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "name": self.name,
            "product_id": self.product_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "node_types": {k.value: len(v) for k, v in self._node_type_index.items()},
            "edge_types": {k.value: len(v) for k, v in self._edge_type_index.items()},
        }


# ═══════════════════════════════════════════════════════════════
# Pipeline Config & Stats
# ═══════════════════════════════════════════════════════════════


@dataclass
class PipelineConfig:
    """Pipeline 配置."""
    pipeline_name: str = "reality_data_pipeline"

    # Batch settings
    batch_size: int = 1000
    max_batch_age_seconds: int = 300

    # Normalization
    normalize_metrics: bool = True
    validate_events: bool = True
    drop_duplicates: bool = True

    # Attribution
    attribution_window_days: int = 30
    attribution_type: AttributionType = AttributionType.LAST_CLICK
    min_confidence: float = 0.5

    # Feature store
    feature_compute_interval_hours: int = 24
    min_sample_size: int = 100
    winner_threshold: float = 0.8

    # Knowledge graph
    graph_update_interval_hours: int = 24
    max_nodes: int = 100000
    max_edges: int = 500000

    # Retention
    retention_days: int = 90

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "batch_size": self.batch_size,
            "attribution_window_days": self.attribution_window_days,
            "attribution_type": self.attribution_type.value,
            "min_confidence": self.min_confidence,
            "feature_compute_interval_hours": self.feature_compute_interval_hours,
            "min_sample_size": self.min_sample_size,
            "winner_threshold": self.winner_threshold,
            "graph_update_interval_hours": self.graph_update_interval_hours,
        }


@dataclass
class PipelineStats:
    """Pipeline 运行统计."""
    pipeline_name: str = ""

    # Counts
    total_raw_events: int = 0
    total_normalized: int = 0
    total_attributed: int = 0
    total_featurized: int = 0
    total_errors: int = 0
    total_dropped: int = 0

    # Attribution
    attribution_edges: int = 0
    attribution_confidence_avg: float = 0.0

    # Feature store
    feature_vectors: int = 0
    winners_count: int = 0
    fatigued_count: int = 0

    # Knowledge graph
    graph_nodes: int = 0
    graph_edges: int = 0

    # Timing
    last_run_at: str = ""
    last_duration_seconds: float = 0.0
    total_runs: int = 0

    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "total_raw_events": self.total_raw_events,
            "total_normalized": self.total_normalized,
            "total_attributed": self.total_attributed,
            "total_featurized": self.total_featurized,
            "total_errors": self.total_errors,
            "total_dropped": self.total_dropped,
            "attribution_edges": self.attribution_edges,
            "attribution_confidence_avg": round(self.attribution_confidence_avg, 2),
            "feature_vectors": self.feature_vectors,
            "winners_count": self.winners_count,
            "fatigued_count": self.fatigued_count,
            "graph_nodes": self.graph_nodes,
            "graph_edges": self.graph_edges,
            "last_run_at": self.last_run_at,
            "last_duration_seconds": round(self.last_duration_seconds, 2),
            "total_runs": self.total_runs,
        }

    @property
    def success_rate(self) -> float:
        total = self.total_raw_events
        if total == 0:
            return 1.0
        return (total - self.total_errors - self.total_dropped) / total

    @property
    def pipeline_health(self) -> str:
        rate = self.success_rate
        if rate >= 0.99:
            return "healthy"
        elif rate >= 0.95:
            return "degraded"
        return "unhealthy"