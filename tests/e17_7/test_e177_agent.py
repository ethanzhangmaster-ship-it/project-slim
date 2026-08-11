"""E17.7 — GrowthMemoryGraphAgent + Test E2E：E17.1 → E17.7 全链路。"""
from audit.trail import AuditTrail
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.registry import build_default_registry
from src.ceo_intelligence.execution_router.router import ApprovalOutbox, ExecutionRouter
from src.ceo_intelligence.growth_memory_graph.agent import (
    GrowthMemoryGraphAgent,
    run_pipeline,
)
from src.ceo_intelligence.growth_memory_graph.models import NodeType
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot


def _build_company(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    # merge_witch：收入 -30% + 创意疲劳 → CREATIVE_REFRESH
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d0",
        revenue=RevenueFact(5000, 50), creative=CreativeFact(0.03, 0.2, 80),
        confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "merge_witch", "d1",
        revenue=RevenueFact(3500, 35), creative=CreativeFact(0.022, 0.85, 55),
        confidence=1.0,
    ))
    # puzzle_island：商店 CVR -20%，评分高 → ASO_OPTIMIZATION
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d0", aso=AsoFact(12, 0.05, 4.6, 4), confidence=1.0,
    ))
    store.append(GrowthRealitySnapshot(
        "puzzle_island", "d1", aso=AsoFact(12, 0.04, 4.6, 4), confidence=1.0,
    ))
    company = build_company_snapshot(
        [store.latest("merge_witch"), store.latest("puzzle_island")], "2026-07-29"
    )
    return store, company


def _router(tmp_path) -> ExecutionRouter:
    return ExecutionRouter(
        registry=build_default_registry(
            release_state_path=str(tmp_path / "release_state.json")
        ),
        audit=AuditTrail(audit_dir=str(tmp_path / "audit")),
        memory=ExecutionMemory(str(tmp_path / "exec_mem.jsonl")),
        outbox=ApprovalOutbox(str(tmp_path / "outbox.jsonl")),
    )


def test_build_from_memory_offline(tmp_path):
    """离线重建：先跑 E17.6，然后只用 ExecutionMemory 建图。"""
    from src.ceo_intelligence.execution_router.agent import (
        run_pipeline as exec_pipeline,
    )
    store, company = _build_company(tmp_path)
    router = _router(tmp_path)
    _, _, reports = exec_pipeline(
        company, store=store, execution_router=router,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"), created_at="2026-07-29",
    )

    agent = GrowthMemoryGraphAgent(
        graph=GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))
    )
    added = agent.build_from_memory(router.memory)
    assert added["nodes_added"] > 0 and added["edges_added"] > 0

    total_actions = sum(r.summary["total"] for r in reports)
    assert len(agent.graph.query(NodeType.ACTION)) == total_actions
    assert len(agent.graph.query(NodeType.RESULT)) == total_actions
    # 每条 execution 均可回溯
    for r in reports:
        chain = agent.trace(r.execution_id)
        assert chain is not None and chain.total_actions == r.summary["total"]


def test_e2e_reality_to_memory_graph(tmp_path):
    """Test7 扩展：E17.1→2→3→4→6→7 全链路，SIM 纪律锁死，图谱可学习。"""
    store, company = _build_company(tmp_path)
    graph = GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))

    dec_report, portfolio, reports, graph_report = run_pipeline(
        company, graph=graph, store=store,
        execution_router=_router(tmp_path),
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    # 上游正常 + 图谱规模
    assert dec_report.total_decisions >= 2
    assert len(reports) == portfolio.summary["planned"]
    assert graph_report.total_nodes > 0
    assert set(graph_report.games) == {"merge_witch", "puzzle_island"}
    assert graph_report.summary["chains"] == len(reports)

    # SIM 纪律：图谱级锁死
    assert graph_report.summary["real_api_called"] is False

    # 在线摄入含机会层：game → opportunity → decision → strategy → execution 全通
    cr = next(r for r in reports if r.strategy_type == "creative_refresh")
    chain = graph.trace_execution(cr.execution_id)
    assert chain.node_ids[0] == "game:merge_witch"
    assert chain.node_ids[1].startswith("opportunity:merge_witch:")
    assert chain.node_ids[2].startswith("decision:")
    assert chain.node_ids[3].startswith("strategy:")
    assert chain.node_ids[4] == f"execution:{cr.execution_id}"
    assert chain.total_actions == cr.summary["total"]
    assert chain.success_actions == cr.summary["success"]

    # 子图：从 game 出发可达全链
    sub = graph.game_subgraph("merge_witch")
    types = {n["type"] for n in sub["nodes"]}
    assert {"game", "opportunity", "decision", "strategy",
            "execution", "action", "result"} <= types

    # 成功率查询与 E17.6 记忆口径一致
    assert graph.success_rate_by(domain="creative") > 0.0

    # markdown 渲染
    md = graph_report.to_markdown()
    assert "增长记忆图谱" in md and "否（SIM）" in md


def test_idempotent_reingest_and_outcome_feedback(tmp_path):
    """重复摄入不膨胀；record_outcome 后 boost 可反馈给 E17.2 口径。"""
    store, company = _build_company(tmp_path)
    graph = GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))
    dec_report, portfolio, reports, _ = run_pipeline(
        company, graph=graph, store=store,
        execution_router=_router(tmp_path),
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"), created_at="2026-07-29",
    )
    stats_before = graph.stats()

    # 幂等：同一批产出重复摄入 → 图不变
    agent = GrowthMemoryGraphAgent(graph=graph)
    added = agent.ingest_pipeline(dec_report, portfolio, reports)
    assert added == {"nodes_added": 0, "edges_added": 0}
    assert graph.stats() == stats_before

    # 学习闭环：挂真实收入结果 → 模式带上 avg_revenue_delta
    cr = next(r for r in reports if r.strategy_type == "creative_refresh")
    assert agent.record_outcome(cr.execution_id, 0.18, "创意刷新 7 日 +18%")
    rpt = agent.report()
    cr_patterns = [p for p in rpt.patterns if p.strategy_type == "creative_refresh"]
    assert cr_patterns and any(p.avg_revenue_delta > 0 for p in cr_patterns)

    # 置信度加成公式与 E17.2 对齐（≥2 样本才生效，封顶 0.20）
    boost = agent.confidence_boost_for("creative_refresh")
    assert 0.0 <= boost <= 0.20
