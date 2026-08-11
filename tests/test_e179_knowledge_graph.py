"""E17.9 Knowledge Graph Update — 测试用例.

Day 7.9 Step 5:
  覆盖 Knowledge Graph Update 层的:
    - NodeType / EdgeType 枚举
    - KnowledgeGraphNode 模型 (properties, serialization)
    - KnowledgeGraphEdge 模型 (properties, serialization)
    - GraphUpdateResult 模型 (properties, serialization)
    - GraphBatchUpdateResult 模型 (from_results, aggregation, properties, serialization)
    - KnowledgeGraphUpdater 引擎 (sync, strengthen, weaken, connect, update_graph)
    - Edge cases (empty store, no matches, duplicate patterns)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.models.knowledge_graph_models import (
    EdgeType,
    GraphBatchUpdateResult,
    GraphUpdateResult,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    NodeType,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.knowledge_graph_updater import (
    KnowledgeGraphUpdater,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternMemory,
    PatternCondition,
    PatternAction,
    PatternPerformance,
    PatternMiningDimension,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def updater() -> KnowledgeGraphUpdater:
    return KnowledgeGraphUpdater()


@pytest.fixture
def pattern_a() -> PatternMemory:
    """模式 A: 高成功率."""
    condition = PatternCondition(
        opportunity_type="increase_budget",
        action_type="increase_budget",
    )
    action = PatternAction(
        action_type="increase_budget",
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=20,
        success_count=17,
        success_rate=0.85,
        avg_reward=0.80,
        avg_confidence=0.90,
        last_seen=datetime(2026, 7, 29, tzinfo=timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["positive", "ua"],
        metadata={"peak_reward": 0.85},
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def pattern_b() -> PatternMemory:
    """模式 B: 中等成功率."""
    condition = PatternCondition(
        opportunity_type="adjust_bid",
        action_type="adjust_bid",
    )
    action = PatternAction(
        action_type="adjust_bid",
        expected_impact="maintain",
    )
    perf = PatternPerformance(
        samples=10,
        success_count=6,
        success_rate=0.60,
        avg_reward=0.55,
        avg_confidence=0.65,
        last_seen=datetime(2026, 7, 25, tzinfo=timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["neutral"],
        metadata={"peak_reward": 0.60},
    )
    pattern.compute_score()
    return pattern


@pytest.fixture
def pattern_c() -> PatternMemory:
    """模式 C: 与 A 相似 (相同动作类型)."""
    condition = PatternCondition(
        opportunity_type="increase_budget",
        action_type="increase_budget",
        category="ua",
        audience_segment="high_value",
    )
    action = PatternAction(
        action_type="increase_budget",
        expected_impact="amplify",
    )
    perf = PatternPerformance(
        samples=15,
        success_count=12,
        success_rate=0.80,
        avg_reward=0.75,
        avg_confidence=0.85,
        last_seen=datetime(2026, 7, 28, tzinfo=timezone.utc).isoformat(),
    )
    pattern = PatternMemory(
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=condition,
        action=action,
        performance=perf,
        tags=["positive", "ua"],
        metadata={"peak_reward": 0.80},
    )
    pattern.compute_score()
    return pattern


# ═══════════════════════════════════════════════════════════════
# Test: NodeType / EdgeType
# ═══════════════════════════════════════════════════════════════


class TestNodeType:
    """NodeType 枚举测试."""

    def test_all_types_exist(self):
        assert NodeType.PATTERN.value == "pattern"
        assert NodeType.CONTEXT.value == "context"
        assert NodeType.OUTCOME.value == "outcome"
        assert NodeType.STRATEGY.value == "strategy"

    def test_type_count(self):
        assert len(list(NodeType)) == 4


class TestEdgeType:
    """EdgeType 枚举测试."""

    def test_all_types_exist(self):
        assert EdgeType.REINFORCES.value == "reinforces"
        assert EdgeType.CONTRADICTS.value == "contradicts"
        assert EdgeType.DERIVES_FROM.value == "derives_from"
        assert EdgeType.EVIDENCE_FOR.value == "evidence_for"
        assert EdgeType.SIMILAR_TO.value == "similar_to"
        assert EdgeType.DECAYS_TO.value == "decays_to"

    def test_type_count(self):
        assert len(list(EdgeType)) == 6


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphNode Model
# ═══════════════════════════════════════════════════════════════


class TestKnowledgeGraphNode:
    """KnowledgeGraphNode 数据模型测试."""

    def test_default_construction(self):
        node = KnowledgeGraphNode()
        assert node.node_id != ""
        assert node.node_type == NodeType.PATTERN
        assert node.confidence == 0.5
        assert node.weight == 1.0
        assert node.is_isolated is True
        assert node.is_high_confidence is False
        assert node.is_low_confidence is False

    def test_high_confidence(self):
        node = KnowledgeGraphNode(confidence=0.85)
        assert node.is_high_confidence is True
        assert node.is_low_confidence is False

    def test_low_confidence(self):
        node = KnowledgeGraphNode(confidence=0.15)
        assert node.is_high_confidence is False
        assert node.is_low_confidence is True

    def test_boundary_high(self):
        node = KnowledgeGraphNode(confidence=0.70)
        assert node.is_high_confidence is True

    def test_isolated_with_edges(self):
        node = KnowledgeGraphNode(edge_count=3)
        assert node.is_isolated is False

    def test_pattern_ref(self):
        node = KnowledgeGraphNode(pattern_ref="p-001")
        assert node.pattern_ref == "p-001"

    def test_label(self):
        node = KnowledgeGraphNode(label="increase_budget @ ua (85%)")
        assert "increase_budget" in node.label

    def test_to_dict(self):
        node = KnowledgeGraphNode(
            node_type=NodeType.PATTERN,
            label="test",
            confidence=0.75,
            pattern_ref="p-001",
            tags=["ua", "positive"],
        )
        d = node.to_dict()
        assert d["node_type"] == "pattern"
        assert d["label"] == "test"
        assert d["confidence"] == 0.75
        assert d["pattern_ref"] == "p-001"
        assert d["tags"] == ["ua", "positive"]
        assert "node_id" in d
        assert "created_at" in d


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphEdge Model
# ═══════════════════════════════════════════════════════════════


class TestKnowledgeGraphEdge:
    """KnowledgeGraphEdge 数据模型测试."""

    def test_default_construction(self):
        edge = KnowledgeGraphEdge()
        assert edge.edge_id != ""
        assert edge.weight == 0.5
        assert edge.confidence == 0.5
        assert edge.evidence_count == 0
        assert edge.is_strong is False
        assert edge.is_weak is False

    def test_strong_edge(self):
        edge = KnowledgeGraphEdge(weight=0.85)
        assert edge.is_strong is True
        assert edge.is_weak is False

    def test_weak_edge(self):
        edge = KnowledgeGraphEdge(weight=0.15)
        assert edge.is_strong is False
        assert edge.is_weak is True

    def test_boundary_strong(self):
        edge = KnowledgeGraphEdge(weight=0.70)
        assert edge.is_strong is True

    def test_evidence_count(self):
        edge = KnowledgeGraphEdge(evidence_count=5)
        assert edge.evidence_count == 5

    def test_to_dict(self):
        edge = KnowledgeGraphEdge(
            source_id="n1",
            target_id="n2",
            edge_type=EdgeType.REINFORCES,
            weight=0.80,
            evidence_count=3,
        )
        d = edge.to_dict()
        assert d["source_id"] == "n1"
        assert d["target_id"] == "n2"
        assert d["edge_type"] == "reinforces"
        assert d["weight"] == 0.80
        assert d["evidence_count"] == 3


# ═══════════════════════════════════════════════════════════════
# Test: GraphUpdateResult Model
# ═══════════════════════════════════════════════════════════════


class TestGraphUpdateResultModel:
    """GraphUpdateResult 数据模型测试."""

    def test_default_construction(self):
        r = GraphUpdateResult()
        assert r.result_id != ""
        assert r.action == "unchanged"
        assert r.changed is False
        assert r.was_created is False
        assert r.was_updated is False

    def test_created_action(self):
        r = GraphUpdateResult(action="created", changed=True)
        assert r.was_created is True
        assert r.was_strengthened is False
        assert r.was_weakened is False

    def test_strengthened_action(self):
        r = GraphUpdateResult(action="strengthened", changed=True)
        assert r.was_strengthened is True
        assert r.was_created is False

    def test_weakened_action(self):
        r = GraphUpdateResult(action="weakened", changed=True)
        assert r.was_weakened is True

    def test_confidence_delta(self):
        r = GraphUpdateResult(
            node_confidence_before=0.50,
            node_confidence_after=0.55,
        )
        assert r.confidence_delta == 0.05

    def test_weight_delta(self):
        r = GraphUpdateResult(
            node_weight_before=1.0,
            node_weight_after=0.85,
        )
        assert r.weight_delta == -0.15

    def test_to_dict(self):
        r = GraphUpdateResult(
            pattern_id="p-001",
            node_id="n-001",
            action="strengthened",
            node_confidence_before=0.50,
            node_confidence_after=0.55,
            changed=True,
            reason="Reinforcement boost",
        )
        d = r.to_dict()
        assert d["pattern_id"] == "p-001"
        assert d["action"] == "strengthened"
        assert d["changed"] is True
        assert d["reason"] == "Reinforcement boost"


# ═══════════════════════════════════════════════════════════════
# Test: GraphBatchUpdateResult Model
# ═══════════════════════════════════════════════════════════════


class TestGraphBatchUpdateResultModel:
    """GraphBatchUpdateResult 数据模型测试."""

    def test_default_construction(self):
        b = GraphBatchUpdateResult()
        assert b.batch_id != ""
        assert b.total_nodes == 0
        assert b.is_empty is True
        assert b.has_changes is False

    def test_from_results_empty(self):
        b = GraphBatchUpdateResult.from_results([])
        assert b.total_nodes == 0
        assert b.is_empty is True

    def test_from_results_created(self):
        r = GraphUpdateResult(action="created", changed=True)
        b = GraphBatchUpdateResult.from_results([r])
        assert b.total_nodes == 1
        assert b.nodes_created == 1
        assert b.nodes_unchanged == 0
        assert b.has_changes is True

    def test_from_results_unchanged(self):
        r = GraphUpdateResult(action="unchanged", changed=False)
        b = GraphBatchUpdateResult.from_results([r])
        assert b.nodes_unchanged == 1
        assert b.has_changes is False

    def test_from_results_mixed(self):
        results = [
            GraphUpdateResult(action="created", changed=True),
            GraphUpdateResult(action="strengthened", changed=True),
            GraphUpdateResult(action="weakened", changed=True),
            GraphUpdateResult(action="updated", changed=True),
            GraphUpdateResult(action="unchanged", changed=False),
        ]
        b = GraphBatchUpdateResult.from_results(results)
        assert b.total_nodes == 5
        assert b.nodes_created == 1
        assert b.nodes_strengthened == 1
        assert b.nodes_weakened == 1
        assert b.nodes_updated == 1
        assert b.nodes_unchanged == 1

    def test_from_results_with_edges(self):
        r = GraphUpdateResult(
            action="created", changed=True,
            edges_added=2, edges_updated=1,
        )
        b = GraphBatchUpdateResult.from_results([r], total_edges=3)
        assert b.total_edges == 3
        assert b.edges_added == 2
        assert b.edges_updated == 1

    def test_summary_content(self):
        r = GraphUpdateResult(action="created", changed=True)
        b = GraphBatchUpdateResult.from_results([r])
        assert "Knowledge Graph Update Summary" in b.update_summary
        assert "Total nodes" in b.update_summary
        assert "Created" in b.update_summary

    def test_to_dict(self):
        r = GraphUpdateResult(action="created", changed=True)
        b = GraphBatchUpdateResult.from_results([r])
        d = b.to_dict()
        assert d["total_nodes"] == 1
        assert isinstance(d["results"], list)
        assert len(d["results"]) == 1


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Construction
# ═══════════════════════════════════════════════════════════════


class TestUpdaterConstruction:
    """KnowledgeGraphUpdater 构造测试."""

    def test_default_construction(self, updater):
        assert updater.node_count == 0
        assert updater.edge_count == 0
        assert updater.update_count == 0

    def test_get_stats_empty(self, updater):
        stats = updater.get_stats()
        assert stats["node_count"] == 0
        assert stats["edge_count"] == 0
        assert stats["update_count"] == 0
        assert stats["total_created"] == 0
        assert stats["total_strengthened"] == 0
        assert stats["total_weakened"] == 0
        assert stats["isolated_nodes"] == 0

    def test_reset_stats(self, updater):
        updater._update_count = 5
        updater._total_created = 3
        updater._total_strengthened = 2
        updater._total_weakened = 1
        updater.reset_stats()
        assert updater.update_count == 0
        assert updater.node_count == 0
        assert updater.edge_count == 0


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Sync Patterns
# ═══════════════════════════════════════════════════════════════


class TestSyncPatterns:
    """Pattern 同步测试."""

    def test_sync_single_pattern_creates_node(self, updater, pattern_a):
        results = updater.sync_patterns([pattern_a])
        assert len(results) == 1
        assert results[0].action == "created"
        assert results[0].changed is True
        assert updater.node_count == 1

    def test_sync_creates_node_with_correct_confidence(self, updater, pattern_a):
        results = updater.sync_patterns([pattern_a])
        node = updater.get_node(results[0].node_id)
        assert node is not None
        assert node.confidence == pattern_a.confidence
        assert node.pattern_ref == pattern_a.pattern_id

    def test_sync_multiple_patterns(self, updater, pattern_a, pattern_b, pattern_c):
        results = updater.sync_patterns([pattern_a, pattern_b, pattern_c])
        assert len(results) == 3
        assert all(r.action == "created" for r in results)
        assert updater.node_count == 3

    def test_sync_existing_pattern_updates(self, updater, pattern_a):
        # First sync
        updater.sync_patterns([pattern_a])
        # Modify pattern confidence
        pattern_a.confidence = 0.60
        # Second sync
        results = updater.sync_patterns([pattern_a])
        assert results[0].action == "updated"
        assert results[0].changed is True

    def test_sync_existing_unchanged(self, updater, pattern_a):
        # First sync
        updater.sync_patterns([pattern_a])
        # Second sync with same values
        results = updater.sync_patterns([pattern_a])
        assert results[0].action == "updated"
        assert results[0].changed is False  # no actual change

    def test_sync_node_label_contains_action_type(self, updater, pattern_a):
        results = updater.sync_patterns([pattern_a])
        node = updater.get_node(results[0].node_id)
        assert "increase_budget" in node.label

    def test_sync_node_metadata(self, updater, pattern_a):
        results = updater.sync_patterns([pattern_a])
        node = updater.get_node(results[0].node_id)
        assert node.metadata["action_type"] == "increase_budget"
        assert node.metadata["success_rate"] == 0.85

    def test_sync_node_tags(self, updater, pattern_a):
        results = updater.sync_patterns([pattern_a])
        node = updater.get_node(results[0].node_id)
        assert "positive" in node.tags
        assert "ua" in node.tags

    def test_sync_empty_patterns(self, updater):
        results = updater.sync_patterns([])
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Strengthen
# ═══════════════════════════════════════════════════════════════


class TestStrengthen:
    """强化测试."""

    @pytest.fixture
    def reinforcement_results(self, pattern_a, pattern_b):
        """模拟强化结果."""
        class MockReinforcementResult:
            def __init__(self, pattern_id):
                self.pattern_id = pattern_id
        return [
            MockReinforcementResult(pattern_a.pattern_id),
            MockReinforcementResult(pattern_b.pattern_id),
        ]

    def test_strengthen_increases_confidence(self, updater, pattern_a, reinforcement_results):
        updater.sync_patterns([pattern_a])
        results = updater.strengthen_from_reinforcement(reinforcement_results[:1])
        assert len(results) == 1
        assert results[0].action == "strengthened"
        assert results[0].node_confidence_after > results[0].node_confidence_before

    def test_strengthen_creates_reinforces_edge(self, updater, pattern_a, reinforcement_results):
        updater.sync_patterns([pattern_a])
        updater.strengthen_from_reinforcement(reinforcement_results[:1])
        assert updater.edge_count >= 1

    def test_strengthen_updates_metadata(self, updater, pattern_a, reinforcement_results):
        updater.sync_patterns([pattern_a])
        updater.strengthen_from_reinforcement(reinforcement_results[:1])
        node = updater.get_all_nodes()[0]
        assert "last_strengthened" in node.metadata
        assert node.metadata["strengthen_count"] == 1

    def test_strengthen_unknown_pattern(self, updater, reinforcement_results):
        """强化不存在的模式."""
        results = updater.strengthen_from_reinforcement(reinforcement_results[:1])
        assert len(results) == 0

    def test_strengthen_capped_at_1(self, updater, pattern_a):
        """置信度不超过 1.0."""
        updater.sync_patterns([pattern_a])
        node = updater.get_all_nodes()[0]
        node.confidence = 0.98

        class MockRR:
            def __init__(self, pid):
                self.pattern_id = pid
        results = updater.strengthen_from_reinforcement([MockRR(pattern_a.pattern_id)])
        node = updater.get_all_nodes()[0]
        assert node.confidence <= 1.0

    def test_strengthen_multiple_times(self, updater, pattern_a):
        """多次强化累积."""
        updater.sync_patterns([pattern_a])
        class MockRR:
            def __init__(self, pid):
                self.pattern_id = pid
        rr = [MockRR(pattern_a.pattern_id)]

        updater.strengthen_from_reinforcement(rr)
        c1 = updater.get_all_nodes()[0].confidence
        updater.strengthen_from_reinforcement(rr)
        c2 = updater.get_all_nodes()[0].confidence
        assert c2 > c1


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Weaken
# ═══════════════════════════════════════════════════════════════


class TestWeaken:
    """衰减测试."""

    @pytest.fixture
    def decay_results(self, pattern_a, pattern_b):
        """模拟衰减结果."""
        class MockDecayResult:
            def __init__(self, pattern_id):
                self.pattern_id = pattern_id
        return [
            MockDecayResult(pattern_a.pattern_id),
            MockDecayResult(pattern_b.pattern_id),
        ]

    def test_weaken_decreases_confidence(self, updater, pattern_a, decay_results):
        updater.sync_patterns([pattern_a])
        results = updater.weaken_from_decay(decay_results[:1])
        assert len(results) == 1
        assert results[0].action == "weakened"
        assert results[0].node_confidence_after < results[0].node_confidence_before

    def test_weaken_creates_decays_to_edge(self, updater, pattern_a, decay_results):
        updater.sync_patterns([pattern_a])
        updater.weaken_from_decay(decay_results[:1])
        assert updater.edge_count >= 1

    def test_weaken_updates_metadata(self, updater, pattern_a, decay_results):
        updater.sync_patterns([pattern_a])
        updater.weaken_from_decay(decay_results[:1])
        node = updater.get_all_nodes()[0]
        assert "last_weakened" in node.metadata
        assert node.metadata["weaken_count"] == 1

    def test_weaken_has_minimum_confidence(self, updater, pattern_a, decay_results):
        """置信度不低于最低值."""
        updater.sync_patterns([pattern_a])
        node = updater.get_all_nodes()[0]
        node.confidence = 0.06
        updater.weaken_from_decay(decay_results[:1])
        node = updater.get_all_nodes()[0]
        assert node.confidence >= 0.05

    def test_weaken_unknown_pattern(self, updater, decay_results):
        results = updater.weaken_from_decay(decay_results[:1])
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Connect Related Patterns
# ═══════════════════════════════════════════════════════════════


class TestConnectRelated:
    """模式连接测试."""

    def test_similar_patterns_create_edge(self, updater, pattern_a, pattern_c):
        """pattern_a 和 pattern_c 有相同 action_type 和 opportunity_type，应创建边."""
        updater.sync_patterns([pattern_a, pattern_c])
        results = updater.connect_related_patterns([pattern_a, pattern_c])
        # 应该至少有一条 SIMILAR_TO 边
        assert updater.edge_count >= 1

    def test_dissimilar_patterns_no_edge(self, updater, pattern_a, pattern_b):
        """不同动作类型不创建 SIMILAR_TO 边."""
        updater.sync_patterns([pattern_a, pattern_b])
        updater.connect_related_patterns([pattern_a, pattern_b])
        # 不同动作类型，相似度 < 0.5，不应创建 SIMILAR_TO 边
        # 但可能创建 EVIDENCE_FOR 边 (如果有相同动作类型)
        # pattern_a: increase_budget, pattern_b: adjust_bid → 不同
        # 所以应该没有边
        assert updater.edge_count == 0

    def test_same_action_type_creates_evidence_edge(self, updater, pattern_a, pattern_c):
        """相同动作类型创建 EVIDENCE_FOR 边."""
        updater.sync_patterns([pattern_a, pattern_c])
        updater.connect_related_patterns([pattern_a, pattern_c])
        edges = updater.get_all_edges()
        evidence_edges = [e for e in edges if e.edge_type == EdgeType.EVIDENCE_FOR]
        assert len(evidence_edges) >= 1

    def test_connect_increments_edge_count(self, updater, pattern_a, pattern_c):
        updater.sync_patterns([pattern_a, pattern_c])
        updater.connect_related_patterns([pattern_a, pattern_c])
        node = updater.get_all_nodes()[0]
        assert node.edge_count > 0

    def test_connect_returns_results(self, updater, pattern_a, pattern_c):
        updater.sync_patterns([pattern_a, pattern_c])
        results = updater.connect_related_patterns([pattern_a, pattern_c])
        assert len(results) >= 1

    def test_connect_single_pattern(self, updater, pattern_a):
        """单个模式不应创建边."""
        updater.sync_patterns([pattern_a])
        results = updater.connect_related_patterns([pattern_a])
        assert updater.edge_count == 0


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Update Graph (Full Cycle)
# ═══════════════════════════════════════════════════════════════


class TestUpdateGraph:
    """完整图谱更新周期测试."""

    def test_update_graph_empty(self, updater):
        batch = updater.update_graph([])
        assert batch.total_nodes == 0
        assert batch.is_empty is True

    def test_update_graph_sync_only(self, updater, pattern_a, pattern_b):
        batch = updater.update_graph([pattern_a, pattern_b])
        assert batch.total_nodes == 2
        assert batch.nodes_created == 2
        assert updater.update_count == 1

    def test_update_graph_with_reinforcement(self, updater, pattern_a):
        class MockRR:
            def __init__(self, pid):
                self.pattern_id = pid
        batch = updater.update_graph(
            [pattern_a],
            reinforcement_results=[MockRR(pattern_a.pattern_id)],
        )
        # sync(1) + strengthen(1) = 2 results
        assert batch.total_nodes == 2
        assert batch.nodes_strengthened == 1

    def test_update_graph_with_decay(self, updater, pattern_a):
        class MockDR:
            def __init__(self, pid):
                self.pattern_id = pid
        batch = updater.update_graph(
            [pattern_a],
            decay_results=[MockDR(pattern_a.pattern_id)],
        )
        # sync(1) + weaken(1) = 2 results
        assert batch.total_nodes == 2
        assert batch.nodes_weakened == 1

    def test_update_graph_full_cycle(self, updater, pattern_a, pattern_c):
        """完整周期: sync + strengthen + weaken + connect."""
        class MockRR:
            def __init__(self, pid):
                self.pattern_id = pid
        class MockDR:
            def __init__(self, pid):
                self.pattern_id = pid

        batch = updater.update_graph(
            [pattern_a, pattern_c],
            reinforcement_results=[MockRR(pattern_a.pattern_id)],
            decay_results=[MockDR(pattern_c.pattern_id)],
        )
        # sync(2) + strengthen(1) + weaken(1) + connect(1) = 5 results
        assert batch.total_nodes == 5
        assert batch.nodes_strengthened >= 1
        assert batch.nodes_weakened >= 1
        assert batch.has_changes is True

    def test_update_graph_increments_count(self, updater, pattern_a):
        updater.update_graph([pattern_a])
        updater.update_graph([pattern_a])
        assert updater.update_count == 2

    def test_update_graph_second_run_updates(self, updater, pattern_a):
        """第二次运行应该更新已有节点."""
        updater.update_graph([pattern_a])
        pattern_a.confidence = 0.60
        batch = updater.update_graph([pattern_a])
        assert batch.nodes_created == 0
        # 应该有一个 updated 结果
        assert any(r.action == "updated" for r in batch.results)


# ═══════════════════════════════════════════════════════════════
# Test: KnowledgeGraphUpdater — Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_pattern_with_minimal_metadata(self, updater):
        """最小元数据模式."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(action_type="test"),
            action=PatternAction(action_type="test"),
            performance=PatternPerformance(
                samples=1,
                success_rate=0.50,
                avg_reward=0.50,
            ),
        )
        p.compute_score()
        results = updater.sync_patterns([p])
        assert results[0].action == "created"
        assert updater.node_count == 1

    def test_pattern_with_no_tags(self, updater):
        """无标签模式."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(action_type="test"),
            action=PatternAction(action_type="test"),
            performance=PatternPerformance(samples=1, success_rate=0.50),
        )
        p.compute_score()
        results = updater.sync_patterns([p])
        node = updater.get_node(results[0].node_id)
        assert node.tags == []

    def test_pattern_with_low_score(self, updater):
        """低评分模式."""
        p = PatternMemory(
            dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
            condition=PatternCondition(action_type="failing"),
            action=PatternAction(action_type="failing"),
            performance=PatternPerformance(
                samples=3,
                success_count=0,
                success_rate=0.0,
                avg_reward=0.0,
            ),
        )
        p.compute_score()
        results = updater.sync_patterns([p])
        node = updater.get_node(results[0].node_id)
        assert node.weight >= 0.1  # min weight

    def test_get_node_by_id(self, updater, pattern_a):
        updater.sync_patterns([pattern_a])
        node = updater.get_all_nodes()[0]
        found = updater.get_node(node.node_id)
        assert found is not None
        assert found.node_id == node.node_id

    def test_get_node_not_found(self, updater):
        assert updater.get_node("nonexistent") is None

    def test_get_all_edges_empty(self, updater):
        edges = updater.get_all_edges()
        assert edges == []

    def test_build_label_with_action_and_opportunity(self, updater, pattern_a):
        label = updater._build_label(pattern_a)
        assert "increase_budget" in label

    def test_pattern_similarity_same_action(self, updater, pattern_a, pattern_c):
        sim = updater._compute_pattern_similarity(pattern_a, pattern_c)
        assert sim > 0.5  # same action_type + same opportunity_type

    def test_pattern_similarity_different(self, updater, pattern_a, pattern_b):
        sim = updater._compute_pattern_similarity(pattern_a, pattern_b)
        assert sim < 0.5  # different action_type and opportunity_type

    def test_strengthen_then_weaken(self, updater, pattern_a):
        """先强化后衰减."""
        updater.sync_patterns([pattern_a])

        class MockRR:
            def __init__(self, pid):
                self.pattern_id = pid
        class MockDR:
            def __init__(self, pid):
                self.pattern_id = pid

        updater.strengthen_from_reinforcement([MockRR(pattern_a.pattern_id)])
        c_strengthened = updater.get_all_nodes()[0].confidence

        updater.weaken_from_decay([MockDR(pattern_a.pattern_id)])
        c_weakened = updater.get_all_nodes()[0].confidence

        assert c_weakened < c_strengthened

    def test_stats_after_operations(self, updater, pattern_a, pattern_c):
        """操作后统计."""
        updater.sync_patterns([pattern_a, pattern_c])
        updater.connect_related_patterns([pattern_a, pattern_c])

        stats = updater.get_stats()
        assert stats["node_count"] == 2
        assert stats["edge_count"] >= 1
        assert stats["total_created"] == 2
        assert stats["isolated_nodes"] == 0  # connected

    def test_ensure_edge_creates_new(self, updater):
        edges_before = updater.edge_count
        added = updater._ensure_edge("n1", "n2", EdgeType.SIMILAR_TO, 0.6)
        assert added == 1
        assert updater.edge_count == edges_before + 1

    def test_ensure_edge_updates_existing(self, updater):
        updater._ensure_edge("n1", "n2", EdgeType.SIMILAR_TO, 0.6)
        added = updater._ensure_edge("n1", "n2", EdgeType.SIMILAR_TO, 0.6)
        assert added == 0  # updated, not created
        edge = updater._find_edge("n1", "n2", EdgeType.SIMILAR_TO)
        assert edge is not None
        assert edge.evidence_count == 2

    def test_find_edge_not_found(self, updater):
        assert updater._find_edge("n1", "n2", EdgeType.SIMILAR_TO) is None

    def test_count_edges_for_node(self, updater):
        updater._ensure_edge("n1", "n2", EdgeType.SIMILAR_TO, 0.6)
        updater._ensure_edge("n1", "n3", EdgeType.EVIDENCE_FOR, 0.5)
        count = updater._count_edges_for_node("n1")
        assert count == 2

    def test_count_edges_isolated_node(self, updater):
        count = updater._count_edges_for_node("n_isolated")
        assert count == 0