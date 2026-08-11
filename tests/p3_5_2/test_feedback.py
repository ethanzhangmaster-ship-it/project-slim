"""
P3.5.2 — KnowledgeFeedbackRecorder + Operator Layer 反馈适配器测试。

覆盖：record 写 Graph / 幂等 / fail-open / real_api_called=False /
attach_outcome 回流 / 只写 CEO_DECISION 不污染其他节点 / operator 反馈适配器映射。
"""
from __future__ import annotations

from types import SimpleNamespace

from src.ceo_intelligence.growth_memory_graph.feedback import (
    DecisionKnowledgeRecord,
    KnowledgeFeedbackRecorder,
)
from src.ceo_intelligence.growth_memory_graph.models import NodeType, node_id
from src.operator.portfolio.ranking_models import PortfolioVerdict

from .helpers import (
    _add_game,
    _add_ceo,
    build_kg_shared,
    _tmp_path,
)
from src.ceo_intelligence.growth_memory_graph.knowledge import GrowthKnowledgeGraph


def _kg() -> GrowthKnowledgeGraph:
    kg = GrowthKnowledgeGraph(graph_path=_tmp_path())
    _add_game(kg, "game_x")
    return kg


# ---------------------------------------------------------------------- #
# Recorder 基础
# ---------------------------------------------------------------------- #
def test_record_writes_ceo_decision_node_and_edges():
    kg = _kg()
    rec = KnowledgeFeedbackRecorder(kg)
    counts = rec.record(
        DecisionKnowledgeRecord(
            record_id="rec_1",
            game_id="game_x",
            decision_type="portfolio",
            source="PORTFOLIO",
            decision_payload={"action": "scale"},
            knowledge_signal={
                "confidence": 0.8,
                "historical_success_rate": 0.9,
                "similar_case_count": 12,
                "risk_flags": ["low_historical_success"],
            },
            outcome={"success": True, "success_rate": 1.0, "simulated": False},
        )
    )
    assert counts["nodes_added"] == 1
    assert counts["edges_added"] == 3

    node = kg.graph.get_node(node_id(NodeType.CEO_DECISION, "rec_1"))
    assert node is not None
    assert node.type == NodeType.CEO_DECISION
    assert node.payload["game_id"] == "game_x"
    assert node.payload["source"] == "PORTFOLIO"
    assert node.payload["decision_payload"]["action"] == "scale"
    assert node.payload["knowledge_signal"]["risk_flags"] == ["low_historical_success"]
    assert node.payload["outcome"]["success_rate"] == 1.0

    edge_types = {e.type for e in kg.graph.edges.values() if e.src == node.id or e.tgt == node.id}
    assert any(e.value == "has_ceo_decision" for e in edge_types)
    assert any(e.value == "used_knowledge_signal" for e in edge_types)
    assert any(e.value == "produced_outcome" for e in edge_types)


def test_record_idempotent_same_record_id():
    kg = _kg()
    rec = KnowledgeFeedbackRecorder(kg)
    r = DecisionKnowledgeRecord(record_id="rec_x", game_id="game_x")
    assert rec.record(r)["nodes_added"] == 1
    second = rec.record(DecisionKnowledgeRecord(record_id="rec_x", game_id="game_x"))
    assert second["nodes_added"] == 0
    assert second["edges_added"] == 0


def test_record_fail_open_no_graph():
    counts = KnowledgeFeedbackRecorder(None).record(
        DecisionKnowledgeRecord(record_id="r1", game_id="game_x")
    )
    assert counts == {"nodes_added": 0, "edges_added": 0}


def test_record_fail_open_graph_error():
    class Broken:
        @property
        def graph(self):
            raise RuntimeError("store down")

    counts = KnowledgeFeedbackRecorder(Broken()).record(
        DecisionKnowledgeRecord(record_id="r1", game_id="game_x")
    )
    assert counts == {"nodes_added": 0, "edges_added": 0}


def test_recorder_real_api_called_false():
    assert KnowledgeFeedbackRecorder(_kg()).real_api_called is False


def test_attach_outcome_updates_node():
    kg = _kg()
    rec = KnowledgeFeedbackRecorder(kg)
    rec.record(DecisionKnowledgeRecord(record_id="rec_2", game_id="game_x"))
    changed = rec.attach_outcome(
        "rec_2", {"success": True, "success_rate": 0.87, "reward": 12.5}
    )
    assert changed is True
    node = kg.graph.get_node(node_id(NodeType.CEO_DECISION, "rec_2"))
    assert node.payload["outcome"]["success_rate"] == 0.87
    assert node.payload["outcome"]["reward"] == 12.5
    # 幂等：重复 attach 相同值 → 无变化
    assert (
        rec.attach_outcome("rec_2", {"success": True, "success_rate": 0.87}) is False
    )
    # 不存在的 record_id → False（fail-open）
    assert rec.attach_outcome("nope", {"success": True}) is False


def test_record_only_adds_ceo_decision_nodes():
    kg = _kg()
    before = {k: v for k, v in kg.graph.stats().items() if k.startswith("nodes_")}
    KnowledgeFeedbackRecorder(kg).record(
        DecisionKnowledgeRecord(record_id="rec_3", game_id="game_x")
    )
    after = {k: v for k, v in kg.graph.stats().items() if k.startswith("nodes_")}
    new_types = [k for k in after if after[k] > before.get(k, 0)]
    assert new_types == ["nodes_ceo_decision"], new_types


# ---------------------------------------------------------------------- #
# Operator Layer 反馈适配器（P3.5.2 冻结点 6/7：消费 Result，业务层不写存储）
# ---------------------------------------------------------------------- #
def _fake_candidate(gid, action):
    return SimpleNamespace(
        game_id=gid,
        recommended_action=action,
        priority=80.0,
        rank=1,
        confidence=0.9,
        action_state="auto",
        knowledge_signal={
            "confidence": 0.6,
            "historical_success_rate": 0.4,
            "similar_case_count": 5,
            "risk_flags": ["low_historical_success"],
        },
    )


def test_operator_portfolio_feedback_maps_candidates():
    from src.operator.feedback import record_portfolio_feedback

    kg = _kg()
    recorder = KnowledgeFeedbackRecorder(kg)
    result = SimpleNamespace(
        ranked_games=[
            _fake_candidate("game_x", PortfolioVerdict.SCALE),
            _fake_candidate("game_a", PortfolioVerdict.REDUCE),
        ]
    )
    n = record_portfolio_feedback(recorder, result)
    assert n == 2
    ceo_nodes = kg.graph.query(NodeType.CEO_DECISION)
    assert len(ceo_nodes) == 2
    by_game = {nd.payload["game_id"]: nd for nd in ceo_nodes}
    assert set(by_game) == {"game_x", "game_a"}
    assert by_game["game_x"].payload["source"] == "PORTFOLIO"
    assert by_game["game_x"].payload["decision_payload"]["action"] == "scale"
    assert by_game["game_x"].payload["knowledge_signal"]["risk_flags"] == [
        "low_historical_success"
    ]
    assert by_game["game_x"].payload["outcome"] == {}


def test_operator_strategy_feedback_maps_proposals():
    from src.operator.feedback import record_strategy_feedback

    kg = _kg()
    recorder = KnowledgeFeedbackRecorder(kg)
    p = SimpleNamespace(
        proposed_change="increase budget 30%",
        current_strategy="aggressive_scale",
        expected_impact="retention uplift",
        confidence=0.82,
        knowledge_confidence=0.46,
        knowledge_signal={"confidence": 0.6, "risk_flags": ["historical_failure_pattern"]},
        requires_simulation=True,
    )
    result = SimpleNamespace(proposals=[p])
    n = record_strategy_feedback(recorder, result, game_id="game_x")
    assert n == 1
    nodes = kg.graph.query(NodeType.CEO_DECISION)
    assert len(nodes) == 1
    nd = nodes[0]
    assert nd.payload["game_id"] == "game_x"
    assert nd.payload["source"] == "STRATEGY"
    assert nd.payload["decision_payload"]["action"] == "increase budget 30%"
    assert nd.payload["outcome"]["success_rate"] == 0.46
    assert nd.payload["outcome"]["simulated"] is True


def test_operator_feedback_fail_open_none():
    from src.operator.feedback import record_portfolio_feedback, record_strategy_feedback

    assert record_portfolio_feedback(None, object()) == 0
    assert record_portfolio_feedback(KnowledgeFeedbackRecorder(_kg()), None) == 0
    assert record_strategy_feedback(None, object()) == 0
    assert record_strategy_feedback(KnowledgeFeedbackRecorder(_kg()), None) == 0
