"""E17.8 — 先验层：静态基线复用 E17.3 + 记忆图谱先验混合。"""
from src.ceo_intelligence.growth_memory_graph.models import GraphNode, NodeType, node_id
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.ceo_intelligence.simulation_engine.priors import get_prior, opportunity_type_of

TOL = 1e-6


def test_opportunity_type_of():
    assert opportunity_type_of("merge_witch:creative_refresh") == "creative_refresh"
    assert opportunity_type_of("plain_type") == "plain_type"


def test_static_prior_matches_e173_baseline():
    """无图谱时退化为 E17.3 静态基线（creative_refresh: .12/.10/.80/.30）。"""
    p = get_prior("creative_refresh")
    assert p.source == "static"
    assert abs(p.expected_revenue_change - 0.12) < TOL
    assert abs(p.expected_roas_change - 0.10) < TOL
    assert abs(p.confidence - 0.80) < TOL
    assert abs(p.risk - 0.30) < TOL
    assert p.samples == 0


def test_unknown_type_falls_back_to_default():
    p = get_prior("brand_new_type")
    assert abs(p.expected_revenue_change - 0.10) < TOL
    assert abs(p.risk - 0.40) < TOL


def _graph_with_results(
    tmp_path, strategy_type: str, successes: int, failures: int, revenue_delta=None
) -> GrowthMemoryGraph:
    g = GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))
    exec_payload = {"execution_id": "e1"}
    if revenue_delta is not None:
        exec_payload["revenue_delta"] = revenue_delta
    g.add_node(GraphNode(
        id=node_id(NodeType.EXECUTION, "e1"),
        type=NodeType.EXECUTION,
        label="exec e1",
        payload=exec_payload,
    ))
    idx = 0
    for success in [True] * successes + [False] * failures:
        g.add_node(GraphNode(
            id=node_id(NodeType.RESULT, f"r{idx}"),
            type=NodeType.RESULT,
            label=f"result {idx}",
            payload={
                "strategy_type": strategy_type,
                "domain": "creative",
                "action_type": "SAFE",
                "success": success,
                "execution_id": "e1",
            },
        ))
        idx += 1
    return g


def test_memory_prior_boosts_confidence_and_discounts_risk(tmp_path):
    """4 成功 0 失败 → boost=min(0.20, 1.0*0.15)=0.15；置信 +boost、风险 -boost/2。"""
    g = _graph_with_results(tmp_path, "creative_refresh", successes=4, failures=0)
    p = get_prior("creative_refresh", g)
    assert p.source == "static+memory"
    assert p.samples == 4
    assert abs(p.memory_boost - 0.15) < TOL
    assert abs(p.confidence - 0.95) < TOL          # 0.80 + 0.15
    assert abs(p.risk - 0.225) < TOL               # 0.30 - 0.075
    # 无 record_outcome 回填 → 收入均值不混合
    assert abs(p.expected_revenue_change - 0.12) < TOL
    assert abs(p.avg_revenue_delta - 0.0) < TOL


def test_memory_prior_mixes_realized_revenue(tmp_path):
    """record_outcome 回填 -0.60 → 收入各半混合：0.5*0.12 + 0.5*(-0.60) = -0.24。"""
    g = _graph_with_results(
        tmp_path, "creative_refresh", successes=0, failures=2, revenue_delta=-0.60
    )
    p = get_prior("creative_refresh", g)
    assert p.source == "static+memory"
    assert abs(p.avg_revenue_delta - (-0.60)) < TOL
    assert abs(p.expected_revenue_change - (-0.24)) < TOL
    # 成功率 0 → boost 0，置信/风险回到静态基线
    assert abs(p.memory_boost - 0.0) < TOL
    assert abs(p.confidence - 0.80) < TOL
    assert abs(p.risk - 0.30) < TOL


def test_insufficient_samples_stays_static(tmp_path):
    """仅 1 样本（< 2）→ 不启用记忆混合。"""
    g = _graph_with_results(tmp_path, "creative_refresh", successes=1, failures=0)
    p = get_prior("creative_refresh", g)
    assert p.source == "static"
    assert abs(p.confidence - 0.80) < TOL


def test_other_strategy_memory_does_not_leak(tmp_path):
    """图谱里只有 ua_scale 的记忆 → creative_refresh 仍是纯静态。"""
    g = _graph_with_results(tmp_path, "ua_scale", successes=3, failures=0)
    p = get_prior("creative_refresh", g)
    assert p.source == "static"
