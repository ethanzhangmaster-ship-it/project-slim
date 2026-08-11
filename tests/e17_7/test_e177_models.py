"""E17.7 — 模型层：roundtrip 与报告渲染。"""
from src.ceo_intelligence.growth_memory_graph.models import (
    EdgeType,
    ExecutionChain,
    GraphEdge,
    GraphNode,
    GraphPattern,
    MemoryEvent,
    MemoryGraphReport,
    NodeType,
    node_id,
)


def test_node_id_convention():
    assert node_id(NodeType.GAME, "merge_witch") == "game:merge_witch"
    assert node_id(NodeType.EXECUTION, "exec_abc") == "execution:exec_abc"


def test_node_edge_roundtrip():
    n = GraphNode(id="game:g1", type=NodeType.GAME, label="g1",
                  payload={"game_id": "g1"})
    n2 = GraphNode.from_dict(n.to_dict())
    assert n2.id == n.id and n2.type is NodeType.GAME
    assert n2.payload == {"game_id": "g1"}

    e = GraphEdge(src="game:g1", tgt="opportunity:g1:ua_scale",
                  type=EdgeType.HAS_OPPORTUNITY)
    e2 = GraphEdge.from_dict(e.to_dict())
    assert e2.key == e.key == ("game:g1", "opportunity:g1:ua_scale", "has_opportunity")


def test_memory_event_roundtrip_and_defaults():
    ev = MemoryEvent(kind="decision", nodes=[
        GraphNode(id="game:g1", type=NodeType.GAME),
    ])
    assert ev.event_id.startswith("evt_")
    ev2 = MemoryEvent.from_dict(ev.to_dict())
    assert ev2.kind == "decision" and len(ev2.nodes) == 1
    assert ev2.event_id == ev.event_id


def test_pattern_roundtrip():
    p = GraphPattern(strategy_type="creative_refresh", domain="creative",
                     action_type="generate_creatives", samples=4, successes=3,
                     success_rate=0.75, confidence_boost=0.1125)
    p2 = GraphPattern.from_dict(p.to_dict())
    assert abs(p2.success_rate - 0.75) < 1e-6
    assert abs(p2.confidence_boost - 0.1125) < 1e-6


def test_report_markdown():
    rpt = MemoryGraphReport(
        total_nodes=12, total_edges=11, games=["merge_witch"],
        chains=[ExecutionChain(execution_id="exec_1", game_id="merge_witch",
                               strategy_type="creative_refresh",
                               success_actions=3, total_actions=5)],
        patterns=[GraphPattern(strategy_type="creative_refresh", domain="creative",
                               action_type="generate_creatives", samples=2,
                               successes=2, success_rate=1.0,
                               confidence_boost=0.15)],
        summary={"chains": 1, "action_success_rate": 0.6, "real_api_called": False},
    )
    md = rpt.to_markdown()
    assert "增长记忆图谱" in md
    assert "creative_refresh" in md
    assert "否（SIM）" in md
