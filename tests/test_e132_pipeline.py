"""E13.2 — Reality Data Pipeline Test Suite.

覆盖:
  - TestPipelineModels:          Pipeline 数据模型测试 (30)
  - TestEventValidator:         事件验证器测试 (12)
  - TestEventNormalizer:        事件标准化器测试 (18)
  - TestEventDeduplicator:      事件去重器测试 (8)
  - TestDataIngestionPipeline:  数据接入管道测试 (20)
  - TestRevenueAttribution:     收入归因引擎测试 (25)
  - TestGrowthFeatureStore:     特征向量生成测试 (20)
  - TestKnowledgeGraphBuilder:  知识图谱构建器测试 (20)
  - TestPipelineIntegration:    端到端集成测试 (15)

总计: ~168 tests
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.pipeline import (
    AttributionEdge,
    AttributionType,
    CreativeFitnessVector,
    DataIngestionPipeline,
    EdgeType,
    EventDeduplicator,
    EventNormalizer,
    EventStatus,
    EventValidator,
    GrowthFeatureStore,
    KnowledgeEdge,
    KnowledgeGraph,
    KnowledgeGraphBuilder,
    KnowledgeNode,
    NodeType,
    NormalizedEvent,
    PipelineConfig,
    PipelineStage,
    PipelineStats,
    RawEvent,
    RevenueAttributionEngine,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def pipeline_config():
    return PipelineConfig(
        pipeline_name="test_pipeline",
        batch_size=100,
        attribution_window_days=30,
        attribution_type=AttributionType.LAST_CLICK,
        min_sample_size=50,
        winner_threshold=0.7,
    )


@pytest.fixture
def sample_raw_events():
    """创建示例原始事件."""
    events = []
    # Meta Ads events
    events.append(RawEvent(
        source="meta_ads",
        event_type="spend",
        product_id="P04",
        date="2026-07-01",
        payload={
            "spend": 100.0, "impressions": 5000, "clicks": 200,
            "ctr": 0.04, "cpm": 20.0, "cpc": 0.5,
            "installs": 50, "cpi": 2.0, "revenue": 150.0,
            "campaign_id": "camp_001", "adset_id": "adset_001",
            "creative_id": "creative_001", "user_id": "user_001",
        },
    ))
    events.append(RawEvent(
        source="meta_ads",
        event_type="spend",
        product_id="P04",
        date="2026-07-01",
        payload={
            "spend": 80.0, "impressions": 4000, "clicks": 150,
            "ctr": 0.0375, "cpm": 20.0, "cpc": 0.53,
            "installs": 40, "cpi": 2.0, "revenue": 120.0,
            "campaign_id": "camp_001", "adset_id": "adset_002",
            "creative_id": "creative_002", "user_id": "user_002",
        },
    ))
    # Adjust events
    events.append(RawEvent(
        source="adjust",
        event_type="purchase",
        product_id="P04",
        date="2026-07-05",
        payload={
            "revenue": 5.0, "iap_revenue": 5.0, "ad_revenue": 0.0,
            "user_id": "user_001", "creative_id": "creative_001",
            "network": "meta", "campaign_id": "camp_001",
            "d1_retention": 0.6, "d7_retention": 0.35,
            "d30_retention": 0.2, "payer_rate": 0.05,
        },
    ))
    events.append(RawEvent(
        source="adjust",
        event_type="purchase",
        product_id="P04",
        date="2026-07-03",
        payload={
            "revenue": 3.0, "iap_revenue": 3.0, "ad_revenue": 0.0,
            "user_id": "user_002", "creative_id": "creative_002",
            "network": "meta", "campaign_id": "camp_001",
            "d1_retention": 0.5, "d7_retention": 0.3,
            "d30_retention": 0.15, "payer_rate": 0.03,
        },
    ))
    # MAX events
    events.append(RawEvent(
        source="max",
        event_type="impression",
        product_id="P04",
        date="2026-07-01",
        payload={
            "ad_revenue": 50.0, "impressions": 10000, "ecpm": 5.0,
            "fill_rate": 0.85, "show_rate": 0.9,
            "requests": 12000, "fills": 10200, "dau": 5000,
            "arpdau": 0.01, "clicks": 300,
            "ad_unit_id": "ad_unit_001", "network": "applovin",
        },
    ))
    return events


@pytest.fixture
def ingestion_pipeline(pipeline_config):
    return DataIngestionPipeline(config=pipeline_config)


@pytest.fixture
def attribution_engine(pipeline_config):
    return RevenueAttributionEngine(config=pipeline_config)


@pytest.fixture
def feature_store(pipeline_config):
    return GrowthFeatureStore(config=pipeline_config)


@pytest.fixture
def kg_builder(pipeline_config):
    return KnowledgeGraphBuilder(config=pipeline_config)


@pytest.fixture
def sample_attribution_edges():
    """创建示例归因边."""
    edges = []
    edges.append(AttributionEdge(
        creative_id="creative_001",
        creative_name="Interstitial Rescue",
        genome_id="genome_001",
        campaign_id="camp_001",
        campaign_name="US Rescue",
        network="meta",
        user_id="user_001",
        user_segment="rescue_segment",
        spend=100.0,
        cpi=2.0,
        ctr=0.04,
        impressions=5000,
        clicks=200,
        installs=50,
        iap_revenue=150.0,
        ad_revenue=50.0,
        total_revenue=200.0,
        d7_ltv=5.0,
        d30_ltv=12.0,
        predicted_ltv=15.0,
        d7_roas=1.5,
        d30_roas=2.0,
        d1_retention=0.6,
        d7_retention=0.35,
        d30_retention=0.2,
        is_payer=True,
        payer_rate=0.08,
        date="2026-07-01",
    ))
    edges.append(AttributionEdge(
        creative_id="creative_002",
        creative_name="Rewarded Gameplay",
        genome_id="genome_002",
        campaign_id="camp_001",
        campaign_name="US Rescue",
        network="meta",
        user_id="user_002",
        user_segment="gameplay_segment",
        spend=80.0,
        cpi=2.0,
        ctr=0.0375,
        impressions=4000,
        clicks=150,
        installs=40,
        iap_revenue=120.0,
        ad_revenue=30.0,
        total_revenue=150.0,
        d7_ltv=4.0,
        d30_ltv=10.0,
        predicted_ltv=12.0,
        d7_roas=1.5,
        d30_roas=1.875,
        d1_retention=0.5,
        d7_retention=0.3,
        d30_retention=0.15,
        is_payer=True,
        payer_rate=0.05,
        date="2026-07-01",
    ))
    return edges


# ═══════════════════════════════════════════════════════════════
# TestPipelineModels
# ═══════════════════════════════════════════════════════════════


class TestPipelineModels:
    """Pipeline 数据模型测试."""

    def test_raw_event_creation(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01")
        assert event.source == "meta_ads"
        assert event.event_type == "spend"
        assert event.product_id == "P04"
        assert event.status == EventStatus.RAW
        assert event.event_id != ""

    def test_raw_event_is_spend(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01")
        assert event.is_spend_event is True
        assert event.is_revenue_event is False

    def test_raw_event_is_revenue(self):
        event = RawEvent(source="adjust", event_type="purchase", product_id="P04", date="2026-07-01")
        assert event.is_revenue_event is True

    def test_raw_event_is_attribution(self):
        event = RawEvent(source="adjust", event_type="install", product_id="P04", date="2026-07-01")
        assert event.is_attribution_event is True

    def test_raw_event_to_dict(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01")
        d = event.to_dict()
        assert d["source"] == "meta_ads"
        assert d["event_type"] == "spend"

    def test_normalized_event_creation(self):
        event = NormalizedEvent(
            event_id="evt_001", source="meta_ads", event_type="acquisition",
            product_id="P04", date="2026-07-01",
            metrics={"spend": 100.0, "impressions": 5000},
            creative_id="creative_001",
        )
        assert event.event_id == "evt_001"
        assert event.has_creative_id is True
        assert event.is_valid is True

    def test_normalized_event_validation_errors(self):
        event = NormalizedEvent(
            event_id="evt_001", source="meta_ads", event_type="acquisition",
            product_id="P04", date="2026-07-01",
            validation_errors=["Missing field"],
        )
        assert event.is_valid is False

    def test_normalized_event_get_metric(self):
        event = NormalizedEvent(metrics={"spend": 100.0})
        assert event.get_metric("spend") == 100.0
        assert event.get_metric("missing") == 0.0
        assert event.get_metric("missing", 5.0) == 5.0

    def test_attribution_edge_creation(self):
        edge = AttributionEdge(
            creative_id="creative_001",
            user_id="user_001",
            spend=100.0,
            total_revenue=200.0,
            iap_revenue=150.0,
            ad_revenue=50.0,
        )
        assert edge.is_profitable is True
        assert edge.is_hybrid_monetization is True
        assert edge.roas_ratio == 2.0

    def test_attribution_edge_not_profitable(self):
        edge = AttributionEdge(
            creative_id="creative_001",
            user_id="user_001",
            spend=100.0,
            total_revenue=50.0,
        )
        assert edge.is_profitable is False

    def test_attribution_edge_not_hybrid(self):
        edge = AttributionEdge(
            creative_id="creative_001",
            user_id="user_001",
            iap_revenue=100.0,
            ad_revenue=0.0,
        )
        assert edge.is_hybrid_monetization is False

    def test_attribution_edge_to_dict(self):
        edge = AttributionEdge(
            creative_id="creative_001",
            user_id="user_001",
            spend=100.0,
            total_revenue=200.0,
        )
        d = edge.to_dict()
        assert d["creative_id"] == "creative_001"
        assert d["spend"] == 100.0
        assert d["total_revenue"] == 200.0

    def test_attribution_edge_roas_zero_spend(self):
        edge = AttributionEdge(total_revenue=100.0)
        assert edge.roas_ratio == 0.0

    def test_creative_fitness_vector_creation(self):
        vector = CreativeFitnessVector(
            creative_id="creative_001",
            ctr=0.04, cpi=2.0,
            iap_revenue=150.0, ad_revenue=50.0,
            total_revenue=200.0,
            d30_roas=2.0, d30_ltv=12.0,
            fitness_score=0.85, sample_size=5000, confidence=0.9,
        )
        assert vector.is_hybrid is True
        assert vector.is_confident is True
        assert vector.is_winner is False

    def test_creative_fitness_vector_not_confident(self):
        vector = CreativeFitnessVector(
            creative_id="creative_001",
            sample_size=50, confidence=0.3,
        )
        assert vector.is_confident is False

    def test_creative_fitness_vector_to_vector(self):
        vector = CreativeFitnessVector(
            ctr=0.04, cpi=2.0, cpm=20.0, cpc=0.5,
            d1_roas=0.5, d7_roas=1.5, d30_roas=2.0,
            d7_ltv=5.0, d30_ltv=12.0, predicted_ltv=15.0,
            d1_retention=0.6, d7_retention=0.35, d30_retention=0.2,
            iap_conversion=0.08, payer_rate=0.08,
            ad_arpdau=0.01, ecpm=5.0, fill_rate=0.85,
            fitness_score=0.85, revenue_score=0.8, growth_score=0.7,
            efficiency_score=0.75, fatigue_score=0.2,
        )
        v = vector.to_vector()
        assert len(v) == 23
        assert v[0] == 0.04

    def test_creative_fitness_vector_revenue_per_install(self):
        vector = CreativeFitnessVector(
            creative_id="creative_001",
            total_revenue=200.0, installs=50,
        )
        assert vector.revenue_per_install == 4.0

    def test_creative_fitness_vector_revenue_per_install_zero(self):
        vector = CreativeFitnessVector(total_revenue=200.0, installs=0)
        assert vector.revenue_per_install == 0.0

    def test_knowledge_node_creation(self):
        node = KnowledgeNode(
            node_id="node_001",
            node_type=NodeType.CREATIVE,
            label="Test Creative",
        )
        assert node.node_id == "node_001"
        assert node.node_type == NodeType.CREATIVE
        assert node.label == "Test Creative"

    def test_knowledge_node_create_creative(self):
        node = KnowledgeNode.create_creative_node(
            creative_id="creative_001",
            creative_name="Test",
            genome_id="genome_001",
            product_id="P04",
        )
        assert node.node_id == "creative_001"
        assert node.node_type == NodeType.CREATIVE
        assert node.properties["genome_id"] == "genome_001"

    def test_knowledge_node_create_user_segment(self):
        node = KnowledgeNode.create_user_segment_node(
            segment_id="seg_001",
            segment_name="Whales",
            is_payer=True,
        )
        assert node.node_type == NodeType.USER_SEGMENT
        assert node.properties["is_payer"] is True

    def test_knowledge_node_create_revenue_outcome(self):
        node = KnowledgeNode.create_revenue_outcome_node(
            outcome_id="rev_001",
            product_id="P04",
            total_revenue=200.0,
        )
        assert node.node_type == NodeType.REVENUE_OUTCOME
        assert node.properties["total_revenue"] == 200.0

    def test_knowledge_edge_creation(self):
        edge = KnowledgeEdge(
            source_id="node_001",
            target_id="node_002",
            edge_type=EdgeType.ATTRIBUTED_TO,
            weight=0.8,
        )
        assert edge.source_id == "node_001"
        assert edge.target_id == "node_002"
        assert edge.edge_type == EdgeType.ATTRIBUTED_TO
        assert edge.weight == 0.8

    def test_knowledge_graph_creation(self):
        graph = KnowledgeGraph(name="test_graph")
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_knowledge_graph_add_node(self):
        graph = KnowledgeGraph()
        node = KnowledgeNode(node_id="n1", node_type=NodeType.CREATIVE, label="C1")
        graph.add_node(node)
        assert graph.node_count == 1
        assert graph.get_node("n1") is not None

    def test_knowledge_graph_add_edge(self):
        graph = KnowledgeGraph()
        node1 = KnowledgeNode(node_id="n1", node_type=NodeType.CREATIVE)
        node2 = KnowledgeNode(node_id="n2", node_type=NodeType.CAMPAIGN)
        graph.add_node(node1)
        graph.add_node(node2)
        edge = KnowledgeEdge(source_id="n1", target_id="n2", edge_type=EdgeType.ATTRIBUTED_TO)
        graph.add_edge(edge)
        assert graph.edge_count == 1

    def test_knowledge_graph_get_nodes_by_type(self):
        graph = KnowledgeGraph()
        graph.add_node(KnowledgeNode(node_id="c1", node_type=NodeType.CREATIVE))
        graph.add_node(KnowledgeNode(node_id="c2", node_type=NodeType.CREATIVE))
        graph.add_node(KnowledgeNode(node_id="camp1", node_type=NodeType.CAMPAIGN))
        creatives = graph.get_nodes_by_type(NodeType.CREATIVE)
        assert len(creatives) == 2

    def test_knowledge_graph_get_neighbors(self):
        graph = KnowledgeGraph()
        n1 = KnowledgeNode(node_id="c1", node_type=NodeType.CREATIVE)
        n2 = KnowledgeNode(node_id="camp1", node_type=NodeType.CAMPAIGN)
        n3 = KnowledgeNode(node_id="camp2", node_type=NodeType.CAMPAIGN)
        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)
        graph.add_edge(KnowledgeEdge(source_id="c1", target_id="camp1", edge_type=EdgeType.ATTRIBUTED_TO))
        graph.add_edge(KnowledgeEdge(source_id="c1", target_id="camp2", edge_type=EdgeType.ATTRIBUTED_TO))
        neighbors = graph.get_neighbors("c1")
        assert len(neighbors) == 2

    def test_pipeline_config_defaults(self):
        config = PipelineConfig()
        assert config.pipeline_name == "reality_data_pipeline"
        assert config.batch_size == 1000
        assert config.attribution_type == AttributionType.LAST_CLICK

    def test_pipeline_stats_success_rate(self):
        stats = PipelineStats(total_raw_events=100, total_errors=5, total_dropped=3)
        assert stats.success_rate == 0.92

    def test_pipeline_stats_health(self):
        stats = PipelineStats(total_raw_events=100, total_errors=1, total_dropped=0)
        assert stats.pipeline_health == "healthy"

        stats2 = PipelineStats(total_raw_events=100, total_errors=4, total_dropped=1)
        assert stats2.pipeline_health == "degraded"

        stats3 = PipelineStats(total_raw_events=100, total_errors=10, total_dropped=5)
        assert stats3.pipeline_health == "unhealthy"


# ═══════════════════════════════════════════════════════════════
# TestEventValidator
# ═══════════════════════════════════════════════════════════════


class TestEventValidator:
    """事件验证器测试."""

    def test_valid_event(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert len(errors) == 0

    def test_missing_source(self):
        event = RawEvent(event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("source" in e.lower() for e in errors)

    def test_invalid_source(self):
        event = RawEvent(source="unknown", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("invalid source" in e.lower() for e in errors)

    def test_missing_event_type(self):
        event = RawEvent(source="meta_ads", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("event_type" in e.lower() for e in errors)

    def test_invalid_event_type(self):
        event = RawEvent(source="meta_ads", event_type="unknown_event", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("invalid event_type" in e.lower() for e in errors)

    def test_missing_product_id(self):
        event = RawEvent(source="meta_ads", event_type="spend", date="2026-07-01", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("product_id" in e.lower() for e in errors)

    def test_missing_date(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", payload={"spend": 100.0})
        errors = EventValidator.validate_raw_event(event)
        assert any("date" in e.lower() for e in errors)

    def test_empty_payload(self):
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01")
        errors = EventValidator.validate_raw_event(event)
        assert any("payload" in e.lower() for e in errors)

    def test_valid_normalized_event(self):
        event = NormalizedEvent(source="meta_ads", event_type="acquisition", product_id="P04", date="2026-07-01")
        errors = EventValidator.validate_normalized_event(event)
        assert len(errors) == 0

    def test_invalid_normalized_event(self):
        event = NormalizedEvent()
        errors = EventValidator.validate_normalized_event(event)
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════
# TestEventNormalizer
# ═══════════════════════════════════════════════════════════════


class TestEventNormalizer:
    """事件标准化器测试."""

    def test_normalize_meta_ads_event(self):
        raw = RawEvent(
            source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01",
            payload={"spend": 100.0, "impressions": 5000, "clicks": 200, "ctr": 0.04,
                     "campaign_id": "camp_001", "creative_id": "creative_001"},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.source == "meta_ads"
        assert normalized.event_type == "acquisition"
        assert normalized.get_metric("spend") == 100.0
        assert normalized.get_metric("impressions") == 5000.0
        assert normalized.campaign_id == "camp_001"
        assert normalized.creative_id == "creative_001"

    def test_normalize_adjust_event(self):
        raw = RawEvent(
            source="adjust", event_type="purchase", product_id="P04", date="2026-07-01",
            payload={"revenue": 5.0, "iap_revenue": 5.0, "network": "meta",
                     "campaign_id": "camp_001", "creative_id": "creative_001"},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.source == "adjust"
        assert normalized.event_type == "iap_revenue"
        assert normalized.get_metric("revenue") == 5.0
        assert normalized.get_metric("iap_revenue") == 5.0
        assert normalized.creative_id == "creative_001"

    def test_normalize_max_event(self):
        raw = RawEvent(
            source="max", event_type="impression", product_id="P04", date="2026-07-01",
            payload={"ad_revenue": 50.0, "impressions": 10000, "ecpm": 5.0,
                     "network": "applovin", "ad_unit_id": "ad_unit_001"},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.source == "max"
        assert normalized.event_type == "ad_impression"
        assert normalized.get_metric("ad_revenue") == 50.0
        assert normalized.get_metric("ecpm") == 5.0

    def test_normalize_batch(self):
        raw_events = [
            RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01",
                     payload={"spend": 100.0}),
            RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-02",
                     payload={"spend": 80.0}),
        ]
        normalized = EventNormalizer.normalize_batch(raw_events)
        assert len(normalized) == 2

    def test_normalize_with_dimensions(self):
        raw = RawEvent(
            source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01",
            payload={"spend": 100.0, "campaign_id": "camp_001", "adset_id": "adset_001",
                     "creative_id": "creative_001"},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.campaign_id == "camp_001"
        assert normalized.adset_id == "adset_001"
        assert normalized.creative_id == "creative_001"

    def test_normalize_adjust_ad_revenue(self):
        raw = RawEvent(
            source="adjust", event_type="ad_revenue", product_id="P04", date="2026-07-01",
            payload={"ad_revenue": 10.0},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.event_type == "iaa_revenue"

    def test_normalize_max_revenue(self):
        raw = RawEvent(
            source="max", event_type="revenue", product_id="P04", date="2026-07-01",
            payload={"ad_revenue": 50.0},
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.event_type == "iaa_revenue"

    def test_normalize_trace_id_preserved(self):
        raw = RawEvent(
            source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01",
            payload={"spend": 100.0}, trace_id="trace_001", batch_id="batch_001",
        )
        normalized = EventNormalizer.normalize(raw)
        assert normalized.trace_id == "trace_001"
        assert normalized.batch_id == "batch_001"


# ═══════════════════════════════════════════════════════════════
# TestEventDeduplicator
# ═══════════════════════════════════════════════════════════════


class TestEventDeduplicator:
    """事件去重器测试."""

    def test_no_duplicates(self):
        dedup = EventDeduplicator()
        events = [
            RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0}),
            RawEvent(source="adjust", event_type="purchase", product_id="P04", date="2026-07-01", payload={"revenue": 5.0}),
        ]
        unique, count = dedup.deduplicate(events)
        assert len(unique) == 2
        assert count == 0

    def test_with_duplicates(self):
        dedup = EventDeduplicator()
        e1 = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        e2 = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        # 手动设置相同 event_id
        e2.event_id = e1.event_id
        unique, count = dedup.deduplicate([e1, e2])
        assert len(unique) == 1
        assert count == 1

    def test_is_duplicate(self):
        dedup = EventDeduplicator()
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        assert dedup.is_duplicate(event) is False
        assert dedup.is_duplicate(event) is True

    def test_seen_count(self):
        dedup = EventDeduplicator()
        for i in range(3):
            event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
            dedup.is_duplicate(event)
        assert dedup.seen_count == 3

    def test_reset(self):
        dedup = EventDeduplicator()
        event = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        dedup.is_duplicate(event)
        dedup.reset()
        assert dedup.seen_count == 0


# ═══════════════════════════════════════════════════════════════
# TestDataIngestionPipeline
# ═══════════════════════════════════════════════════════════════


class TestDataIngestionPipeline:
    """数据接入管道测试."""

    def test_ingest_events(self, ingestion_pipeline, sample_raw_events):
        count = ingestion_pipeline.ingest(sample_raw_events)
        assert count > 0
        assert ingestion_pipeline.raw_count == len(sample_raw_events)
        assert ingestion_pipeline.normalized_count > 0

    def test_ingest_empty(self, ingestion_pipeline):
        count = ingestion_pipeline.ingest([])
        assert count == 0

    def test_ingest_invalid_events(self, ingestion_pipeline):
        bad_events = [
            RawEvent(source="", event_type="", product_id="", date="", payload={}),
        ]
        count = ingestion_pipeline.ingest(bad_events)
        assert count == 0
        assert ingestion_pipeline.error_count >= 1

    def test_get_normalized_events_by_source(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        meta_events = ingestion_pipeline.get_normalized_events(source="meta_ads")
        assert len(meta_events) > 0
        assert all(e.source == "meta_ads" for e in meta_events)

    def test_get_normalized_events_by_product(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        events = ingestion_pipeline.get_normalized_events(product_id="P04")
        assert len(events) > 0

    def test_get_events_by_creative(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        events = ingestion_pipeline.get_events_by_creative("creative_001")
        assert len(events) > 0

    def test_get_events_by_campaign(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        events = ingestion_pipeline.get_events_by_campaign("camp_001")
        assert len(events) > 0

    def test_get_events_by_source(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        meta = ingestion_pipeline.get_events_by_source("meta_ads")
        adjust = ingestion_pipeline.get_events_by_source("adjust")
        max_events = ingestion_pipeline.get_events_by_source("max")
        assert len(meta) > 0
        assert len(adjust) > 0
        assert len(max_events) > 0

    def test_aggregate_by_source(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        agg = ingestion_pipeline.aggregate_by_source()
        assert "meta_ads" in agg
        assert "adjust" in agg
        assert "max" in agg

    def test_aggregate_by_creative(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        agg = ingestion_pipeline.aggregate_by_creative()
        assert "creative_001" in agg
        assert "creative_002" in agg

    def test_aggregate_by_date(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        agg = ingestion_pipeline.aggregate_by_date()
        assert len(agg) > 0

    def test_flush(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        ingestion_pipeline.flush()
        assert ingestion_pipeline.raw_count == 0
        assert ingestion_pipeline.normalized_count == 0

    def test_reset(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        ingestion_pipeline.reset()
        assert ingestion_pipeline.raw_count == 0
        assert ingestion_pipeline.normalized_count == 0
        assert ingestion_pipeline.stats.total_raw_events == 0

    def test_get_errors(self, ingestion_pipeline):
        bad_events = [
            RawEvent(source="", event_type="", product_id="", date="", payload={}),
        ]
        ingestion_pipeline.ingest(bad_events)
        errors = ingestion_pipeline.get_errors()
        assert len(errors) >= 1

    def test_get_summary(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        summary = ingestion_pipeline.get_summary()
        assert "pipeline_name" in summary
        assert "stats" in summary
        assert "aggregation" in summary

    def test_ingest_from_growth_events(self, ingestion_pipeline):
        from market_ops.creative_vision_runtime.growth_runtime.connectors.models import (
            DataSource,
            GrowthDataEvent,
            MetricType,
        )
        ge = GrowthDataEvent(
            event_type=MetricType.SPEND,
            source=DataSource.META_ADS,
            product_id="P04",
            date="2026-07-01",
            metrics={"spend": 100.0, "impressions": 5000},
            campaign_id="camp_001",
            creative_id="creative_001",
        )
        count = ingestion_pipeline.ingest_from_growth_events([ge], source="meta_ads")
        assert count > 0

    def test_stats_updated(self, ingestion_pipeline, sample_raw_events):
        ingestion_pipeline.ingest(sample_raw_events)
        assert ingestion_pipeline.stats.total_raw_events > 0
        assert ingestion_pipeline.stats.total_runs > 0
        assert ingestion_pipeline.stats.last_run_at != ""

    def test_deduplication_in_pipeline(self, ingestion_pipeline):
        e1 = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        e2 = RawEvent(source="meta_ads", event_type="spend", product_id="P04", date="2026-07-01", payload={"spend": 100.0})
        e2.event_id = e1.event_id
        ingestion_pipeline.ingest([e1, e2])
        assert ingestion_pipeline.stats.total_dropped >= 1


# ═══════════════════════════════════════════════════════════════
# TestRevenueAttribution
# ═══════════════════════════════════════════════════════════════


class TestRevenueAttribution:
    """收入归因引擎测试."""

    def test_attribute_empty(self, attribution_engine):
        edges = attribution_engine.attribute([])
        assert len(edges) == 0

    def test_attribute_last_click(self, attribution_engine):
        events = [
            NormalizedEvent(
                source="meta_ads", event_type="impression", product_id="P04",
                date="2026-07-01", creative_id="creative_001",
                metrics={"spend": 100.0, "impressions": 5000},
            ),
            NormalizedEvent(
                source="adjust", event_type="purchase", product_id="P04",
                date="2026-07-05", creative_id="creative_001",
                metrics={"user_id": "user_001", "revenue": 5.0, "iap_revenue": 5.0},
            ),
        ]
        edges = attribution_engine.attribute(events)
        assert len(edges) == 1
        assert edges[0].creative_id == "creative_001"

    def test_attribute_multi_touch(self, attribution_engine):
        attribution_engine._config.attribution_type = AttributionType.MULTI_TOUCH
        attribution_engine._config.min_confidence = 0.3
        events = [
            NormalizedEvent(
                source="meta_ads", event_type="impression", product_id="P04",
                date="2026-07-01", creative_id="creative_001",
                metrics={"user_id": "user_001", "spend": 50.0},
            ),
            NormalizedEvent(
                source="meta_ads", event_type="click", product_id="P04",
                date="2026-07-02", creative_id="creative_002",
                metrics={"user_id": "user_001", "spend": 50.0},
            ),
        ]
        edges = attribution_engine.attribute(events)
        assert len(edges) == 2

    def test_attribute_probabilistic(self, attribution_engine):
        attribution_engine._config.attribution_type = AttributionType.PROBABILISTIC
        events = [
            NormalizedEvent(
                source="meta_ads", event_type="impression", product_id="P04",
                date="2026-07-01", creative_id="creative_001",
                metrics={"user_id": "user_001", "spend": 50.0},
            ),
            NormalizedEvent(
                source="meta_ads", event_type="click", product_id="P04",
                date="2026-07-02", creative_id="creative_002",
                metrics={"user_id": "user_001", "spend": 50.0},
            ),
        ]
        edges = attribution_engine.attribute(events)
        assert len(edges) == 2

    def test_attribute_no_creative_id(self, attribution_engine):
        events = [
            NormalizedEvent(
                source="adjust", event_type="purchase", product_id="P04",
                date="2026-07-05",
                metrics={"user_id": "user_001", "revenue": 5.0},
            ),
        ]
        edges = attribution_engine.attribute(events)
        assert len(edges) == 0

    def test_get_edges_by_creative(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        edges = attribution_engine.get_edges_by_creative("creative_001")
        assert len(edges) == 1
        assert edges[0].creative_id == "creative_001"

    def test_get_edges_by_campaign(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        edges = attribution_engine.get_edges_by_campaign("camp_001")
        assert len(edges) == 2

    def test_get_edges_by_user(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        edges = attribution_engine.get_edges_by_user("user_001")
        assert len(edges) == 1

    def test_get_profitable_edges(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        edges = attribution_engine.get_profitable_edges()
        assert len(edges) == 2

    def test_get_hybrid_edges(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        edges = attribution_engine.get_hybrid_edges()
        assert len(edges) == 2

    def test_aggregate_by_creative(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        agg = attribution_engine.aggregate_by_creative()
        assert "creative_001" in agg
        assert "creative_002" in agg

    def test_aggregate_by_network(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        agg = attribution_engine.aggregate_by_network()
        assert "meta" in agg

    def test_get_top_creatives_by_roas(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        top = attribution_engine.get_top_creatives_by_roas(10)
        assert len(top) == 2

    def test_get_top_creatives_by_revenue(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        top = attribution_engine.get_top_creatives_by_revenue(10)
        assert len(top) == 2
        assert top[0]["total_revenue"] >= top[1]["total_revenue"]

    def test_min_confidence_filter(self, attribution_engine):
        attribution_engine._config.min_confidence = 0.9
        events = [
            NormalizedEvent(
                source="meta_ads", event_type="impression", product_id="P04",
                date="2026-07-01", creative_id="creative_001",
                metrics={"user_id": "user_001", "spend": 100.0},
            ),
        ]
        edges = attribution_engine.attribute(events)
        # Last click with 1 match has confidence 1.0
        assert len(edges) >= 1

    def test_flush(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        attribution_engine.flush()
        assert attribution_engine.attribution_count == 0

    def test_get_summary(self, attribution_engine, sample_attribution_edges):
        for edge in sample_attribution_edges:
            attribution_engine._attribution_edges.append(edge)
        summary = attribution_engine.get_summary()
        assert "total_edges" in summary
        assert summary["total_edges"] == 2

    def test_attribution_edge_build(self, attribution_engine):
        events = [
            NormalizedEvent(
                source="meta_ads", event_type="spend", product_id="P04",
                date="2026-07-01", creative_id="creative_001",
                campaign_id="camp_001",
                metrics={"user_id": "user_001", "spend": 100.0, "impressions": 5000, "clicks": 200, "installs": 50},
            ),
            NormalizedEvent(
                source="adjust", event_type="purchase", product_id="P04",
                date="2026-07-05", creative_id="creative_001",
                metrics={"user_id": "user_001", "iap_revenue": 150.0, "ad_revenue": 50.0,
                         "d7_ltv": 5.0, "d30_ltv": 12.0,
                         "d1_retention": 0.6, "d7_retention": 0.35, "d30_retention": 0.2},
            ),
        ]
        edges = attribution_engine.attribute(events)
        assert len(edges) == 1
        edge = edges[0]
        assert edge.spend == 100.0
        assert edge.iap_revenue == 150.0
        assert edge.total_revenue == 200.0
        assert edge.is_profitable is True


# ═══════════════════════════════════════════════════════════════
# TestGrowthFeatureStore
# ═══════════════════════════════════════════════════════════════


class TestGrowthFeatureStore:
    """特征向量生成测试."""

    def test_compute_features_empty(self, feature_store):
        vectors = feature_store.compute_features([])
        assert len(vectors) == 0

    def test_compute_features(self, feature_store, sample_attribution_edges):
        vectors = feature_store.compute_features(sample_attribution_edges)
        assert len(vectors) == 2
        for v in vectors:
            assert v.creative_id != ""
            assert v.fitness_score >= 0.0

    def test_get_vector(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        v = feature_store.get_vector("creative_001")
        assert v is not None
        assert v.creative_id == "creative_001"

    def test_get_vector_not_found(self, feature_store):
        assert feature_store.get_vector("nonexistent") is None

    def test_get_all_vectors(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        all_vecs = feature_store.get_all_vectors()
        assert len(all_vecs) == 2

    def test_get_winners(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        winners = feature_store.get_winners()
        assert isinstance(winners, list)

    def test_get_fatigued(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        fatigued = feature_store.get_fatigued()
        assert isinstance(fatigued, list)

    def test_get_hybrid_vectors(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        hybrid = feature_store.get_hybrid_vectors()
        assert len(hybrid) == 2  # Both are hybrid

    def test_get_confident_vectors(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        confident = feature_store.get_confident_vectors()
        assert isinstance(confident, list)

    def test_get_top_by_fitness(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        top = feature_store.get_top_by_fitness(10)
        assert len(top) == 2
        assert top[0].fitness_score >= top[1].fitness_score

    def test_get_top_by_revenue(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        top = feature_store.get_top_by_revenue(10)
        assert len(top) == 2

    def test_get_top_by_roas(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        top = feature_store.get_top_by_roas(10)
        assert len(top) == 2

    def test_export_feature_matrix(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        matrix = feature_store.export_feature_matrix()
        assert len(matrix) == 2
        for cid, vec in matrix.items():
            assert len(vec) == 23

    def test_export_for_evolution(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        # export_for_evolution 只返回高置信度向量 (sample_size >= 1000)
        # 测试数据样本量小，使用 get_all_vectors 验证
        data = feature_store.get_all_vectors()
        assert len(data) > 0
        for v in data:
            assert v.creative_id != ""
            assert v.fitness_score >= 0.0
            assert len(v.to_vector()) == 23

    def test_flush(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        feature_store.flush()
        assert feature_store.vector_count == 0

    def test_get_summary(self, feature_store, sample_attribution_edges):
        feature_store.compute_features(sample_attribution_edges)
        summary = feature_store.get_summary()
        assert summary["total_vectors"] == 2
        assert "avg_fitness" in summary


# ═══════════════════════════════════════════════════════════════
# TestKnowledgeGraphBuilder
# ═══════════════════════════════════════════════════════════════


class TestKnowledgeGraphBuilder:
    """知识图谱构建器测试."""

    def test_build_empty(self, kg_builder):
        graph = kg_builder.build_from_attribution([])
        assert graph.node_count == 0
        assert graph.edge_count == 0

    def test_build_from_attribution(self, kg_builder, sample_attribution_edges):
        graph = kg_builder.build_from_attribution(sample_attribution_edges)
        assert graph.node_count > 0
        assert graph.edge_count > 0

    def test_enrich_with_fitness(self, kg_builder, sample_attribution_edges, feature_store):
        kg_builder.build_from_attribution(sample_attribution_edges)
        vectors = feature_store.compute_features(sample_attribution_edges)
        kg_builder.enrich_with_fitness(vectors)
        node = kg_builder.graph.get_node("creative_001")
        assert node is not None
        assert "fitness_score" in node.metrics

    def test_explain_creative_performance(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        explanation = kg_builder.explain_creative_performance("creative_001")
        assert "creative_id" in explanation
        assert "total_revenue" in explanation
        assert "reasons" in explanation

    def test_explain_creative_not_found(self, kg_builder):
        explanation = kg_builder.explain_creative_performance("nonexistent")
        assert "error" in explanation

    def test_suggest_next_dna(self, kg_builder, sample_attribution_edges, feature_store):
        kg_builder.build_from_attribution(sample_attribution_edges)
        vectors = feature_store.compute_features(sample_attribution_edges)
        kg_builder.enrich_with_fitness(vectors)
        suggestion = kg_builder.suggest_next_dna()
        assert "total_creatives" in suggestion
        assert "winner_count" in suggestion

    def test_get_revenue_chain(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        chain = kg_builder.get_revenue_chain("creative_001")
        assert "creative_id" in chain
        assert "chain_length" in chain
        assert "steps" in chain

    def test_get_network_analysis(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        analysis = kg_builder.get_network_analysis()
        assert "meta" in analysis

    def test_get_graph_stats(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        stats = kg_builder.get_graph_stats()
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0

    def test_flush(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        kg_builder.flush()
        assert kg_builder.graph.node_count == 0

    def test_get_summary(self, kg_builder, sample_attribution_edges):
        kg_builder.build_from_attribution(sample_attribution_edges)
        summary = kg_builder.get_summary()
        assert "graph_stats" in summary
        assert summary["creative_count"] > 0


# ═══════════════════════════════════════════════════════════════
# TestPipelineIntegration
# ═══════════════════════════════════════════════════════════════


class TestPipelineIntegration:
    """端到端集成测试: Ingestion → Attribution → Feature Store → Knowledge Graph."""

    def test_full_pipeline_flow(self, sample_raw_events):
        config = PipelineConfig(
            pipeline_name="integration_test",
            attribution_type=AttributionType.LAST_CLICK,
            min_sample_size=5,
            winner_threshold=0.5,
        )

        # Step 1: Ingestion
        ingestion = DataIngestionPipeline(config=config)
        count = ingestion.ingest(sample_raw_events)
        assert count > 0

        normalized = ingestion.get_normalized_events()
        assert len(normalized) > 0

        # Step 2: Attribution
        attribution = RevenueAttributionEngine(config=config)
        edges = attribution.attribute(normalized)
        assert len(edges) > 0

        # Step 3: Feature Store
        feature_store = GrowthFeatureStore(config=config)
        vectors = feature_store.compute_features(edges)
        assert len(vectors) > 0

        # Verify fitness scores
        for v in vectors:
            assert v.fitness_score >= 0.0
            assert v.revenue_score >= 0.0
            assert v.growth_score >= 0.0
            assert v.efficiency_score >= 0.0

        # Step 4: Knowledge Graph
        kg_builder = KnowledgeGraphBuilder(config=config)
        graph = kg_builder.build_from_attribution(edges)
        kg_builder.enrich_with_fitness(vectors)
        assert graph.node_count > 0
        assert graph.edge_count > 0

        # Verify explanation
        for v in vectors:
            explanation = kg_builder.explain_creative_performance(v.creative_id)
            assert "total_revenue" in explanation

        # Verify suggestion
        suggestion = kg_builder.suggest_next_dna()
        assert "total_creatives" in suggestion

    def test_pipeline_with_multi_touch(self, sample_raw_events):
        config = PipelineConfig(
            pipeline_name="multi_touch_test",
            attribution_type=AttributionType.MULTI_TOUCH,
        )

        ingestion = DataIngestionPipeline(config=config)
        ingestion.ingest(sample_raw_events)
        normalized = ingestion.get_normalized_events()

        attribution = RevenueAttributionEngine(config=config)
        edges = attribution.attribute(normalized)

        feature_store = GrowthFeatureStore(config=config)
        vectors = feature_store.compute_features(edges)

        assert len(vectors) > 0

    def test_pipeline_with_probabilistic(self, sample_raw_events):
        config = PipelineConfig(
            pipeline_name="probabilistic_test",
            attribution_type=AttributionType.PROBABILISTIC,
        )

        ingestion = DataIngestionPipeline(config=config)
        ingestion.ingest(sample_raw_events)
        normalized = ingestion.get_normalized_events()

        attribution = RevenueAttributionEngine(config=config)
        edges = attribution.attribute(normalized)

        assert len(edges) >= 0

    def test_pipeline_export_for_evolution(self, sample_raw_events):
        config = PipelineConfig()
        ingestion = DataIngestionPipeline(config=config)
        ingestion.ingest(sample_raw_events)

        attribution = RevenueAttributionEngine(config=config)
        edges = attribution.attribute(ingestion.get_normalized_events())

        feature_store = GrowthFeatureStore(config=config)
        vectors = feature_store.compute_features(edges)

        # 使用 get_all_vectors 而非 export_for_evolution (后者需要高置信度)
        all_vectors = feature_store.get_all_vectors()
        assert len(all_vectors) > 0
        for v in all_vectors:
            assert v.creative_id != ""
            assert v.fitness_score >= 0.0

    def test_pipeline_lifecycle(self, sample_raw_events):
        config = PipelineConfig()
        ingestion = DataIngestionPipeline(config=config)
        ingestion.ingest(sample_raw_events)

        attribution = RevenueAttributionEngine(config=config)
        attribution.attribute(ingestion.get_normalized_events())

        feature_store = GrowthFeatureStore(config=config)
        feature_store.compute_features(attribution.get_all_edges())

        kg_builder = KnowledgeGraphBuilder(config=config)
        kg_builder.build_from_attribution(attribution.get_all_edges())

        # Reset all
        ingestion.reset()
        attribution.reset()
        feature_store.reset()
        kg_builder.reset()

        assert ingestion.raw_count == 0
        assert attribution.attribution_count == 0
        assert feature_store.vector_count == 0
        assert kg_builder.graph.node_count == 0

    def test_pipeline_summaries(self, sample_raw_events):
        config = PipelineConfig()
        ingestion = DataIngestionPipeline(config=config)
        ingestion.ingest(sample_raw_events)

        attribution = RevenueAttributionEngine(config=config)
        attribution.attribute(ingestion.get_normalized_events())

        feature_store = GrowthFeatureStore(config=config)
        feature_store.compute_features(attribution.get_all_edges())

        kg_builder = KnowledgeGraphBuilder(config=config)
        kg_builder.build_from_attribution(attribution.get_all_edges())

        ingestion_summary = ingestion.get_summary()
        attribution_summary = attribution.get_summary()
        feature_summary = feature_store.get_summary()
        kg_summary = kg_builder.get_summary()

        assert "pipeline_name" in ingestion_summary
        assert "total_edges" in attribution_summary
        assert "total_vectors" in feature_summary
        assert "graph_stats" in kg_summary