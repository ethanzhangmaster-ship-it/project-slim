"""E17.7 — GrowthMemoryGraph：幂等、持久化、遍历、成功率。"""
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.models import ExecutionExperience
from src.ceo_intelligence.growth_memory_graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
)
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph


def _graph(tmp_path) -> GrowthMemoryGraph:
    return GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))


def _exp(execution_id="exec_1", action_id="act_1", success=True,
         domain="creative", action_type="generate_creatives") -> ExecutionExperience:
    return ExecutionExperience(
        execution_id=execution_id, action_id=action_id, decision_id="dec_1",
        game_id="merge_witch", strategy_type="creative_refresh",
        domain=domain, action_type=action_type,
        status="success" if success else "failed", success=success,
    )


def test_add_node_edge_idempotent(tmp_path):
    g = _graph(tmp_path)
    n = GraphNode(id="game:g1", type=NodeType.GAME, payload={"game_id": "g1"})
    assert g.add_node(n) is True
    assert g.add_node(GraphNode(id="game:g1", type=NodeType.GAME,
                                payload={"game_id": "g1"})) is False  # 无变化
    e = GraphEdge(src="game:g1", tgt="opportunity:g1:ua_scale",
                  type=EdgeType.HAS_OPPORTUNITY)
    assert g.add_edge(e) is True
    assert g.add_edge(GraphEdge(src="game:g1", tgt="opportunity:g1:ua_scale",
                                type=EdgeType.HAS_OPPORTUNITY)) is False
    assert g.stats()["nodes"] == 1 and g.stats()["edges"] == 1


def test_node_payload_merge_last_write_wins(tmp_path):
    g = _graph(tmp_path)
    g.add_node(GraphNode(id="execution:e1", type=NodeType.EXECUTION,
                         payload={"status": "waiting_approval"}))
    changed = g.add_node(GraphNode(id="execution:e1", type=NodeType.EXECUTION,
                                   payload={"status": "success",
                                            "revenue_delta": 0.12}))
    assert changed is True
    node = g.get_node("execution:e1")
    assert node.payload["status"] == "success"
    assert abs(node.payload["revenue_delta"] - 0.12) < 1e-6


def test_persistence_reload(tmp_path):
    path = str(tmp_path / "graph.jsonl")
    g1 = GrowthMemoryGraph(path=path)
    mem = ExecutionMemory(str(tmp_path / "mem.jsonl"))
    mem.record(_exp())
    mem.record(_exp(action_id="act_2", success=False, action_type="run_experiment"))
    g1.build_from_execution_memory(mem)
    stats1 = g1.stats()

    g2 = GrowthMemoryGraph(path=path)  # 重放 JSONL
    assert g2.stats() == stats1
    assert g2.get_node("game:merge_witch") is not None
    # 重建后再次摄入同数据 → 不新增
    r = g2.build_from_execution_memory(mem)
    assert r == {"nodes_added": 0, "edges_added": 0}


def test_trace_execution_chain_order(tmp_path):
    g = _graph(tmp_path)
    mem = ExecutionMemory(str(tmp_path / "mem.jsonl"))
    mem.record(_exp(action_id="act_1"))
    mem.record(_exp(action_id="act_2", success=False))
    g.build_from_execution_memory(mem)

    chain = g.trace_execution("exec_1")
    assert chain is not None
    assert chain.game_id == "merge_witch"
    assert chain.decision_id == "dec_1"
    assert chain.strategy_type == "creative_refresh"
    assert chain.total_actions == 2 and chain.success_actions == 1
    # 链路顺序：decision → strategy → execution 在前（经验重建无 opportunity 层）
    assert chain.node_ids[0] == "decision:dec_1"
    assert chain.node_ids[1] == "strategy:dec_1"
    assert chain.node_ids[2] == "execution:exec_1"
    assert g.trace_execution("exec_missing") is None


def test_game_subgraph_reachability(tmp_path):
    g = _graph(tmp_path)
    mem = ExecutionMemory(str(tmp_path / "mem.jsonl"))
    mem.record(_exp())
    g.build_from_execution_memory(mem)
    # 经验重建时 game 节点无出边（链从 decision 起），子图仅含 game 自身
    sub = g.game_subgraph("merge_witch")
    assert sub["nodes"][0]["id"] == "game:merge_witch"
    assert g.game_subgraph("nonexistent") == {"nodes": [], "edges": []}
    # 但按 payload.game_id 查询可命中全链
    assert len(g.query(game_id="merge_witch")) >= 5


def test_success_rate_by(tmp_path):
    g = _graph(tmp_path)
    mem = ExecutionMemory(str(tmp_path / "mem.jsonl"))
    mem.record(_exp(action_id="a1", success=True))
    mem.record(_exp(action_id="a2", success=True, action_type="clip_score"))
    mem.record(_exp(action_id="a3", success=False, domain="ua",
                    action_type="run_experiment"))
    g.build_from_execution_memory(mem)

    assert abs(g.success_rate_by(domain="creative") - 1.0) < 1e-6
    assert abs(g.success_rate_by(domain="ua") - 0.0) < 1e-6
    assert abs(g.success_rate_by(strategy_type="creative_refresh") - 2 / 3) < 1e-6
    assert abs(g.success_rate_by(domain="nonexistent") - 0.0) < 1e-6
