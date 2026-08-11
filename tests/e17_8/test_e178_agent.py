"""E17.8 — GrowthSimulationAgent + store 落盘 + Test8 端到端（闸门插入 E17.6 之前）。"""
import json

from audit.trail import AuditTrail
from src.ceo_intelligence.decision_engine.models import (
    DecisionReport,
    DecisionType,
    GrowthDecision,
)
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.registry import build_default_registry
from src.ceo_intelligence.execution_router.router import ApprovalOutbox, ExecutionRouter
from src.ceo_intelligence.growth_memory_graph.models import GraphNode, NodeType, node_id
from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph
from src.ceo_intelligence.simulation_engine.agent import (
    GrowthSimulationAgent,
    run_pipeline,
)
from src.ceo_intelligence.simulation_engine.models import PreFlightStatus
from src.ceo_intelligence.simulation_engine.store import JsonlSimulationStore
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot

TOL = 1e-6


def _decision(game_id, opp_type, dtype) -> GrowthDecision:
    return GrowthDecision(
        game_id=game_id,
        opportunity_id=f"{game_id}:{opp_type}",
        action=f"act({game_id})",
        decision_type=dtype,
        expected_value=0.12,
        confidence=0.8,
        risk=0.3,
        reason="test",
        audit_id=f"dec_{game_id}_{opp_type}",
    )


def _dec_report() -> DecisionReport:
    decisions = [
        _decision("merge_witch", "creative_refresh", DecisionType.EXECUTE),
        _decision("puzzle_island", "revenue_recovery", DecisionType.APPROVE),
        _decision("idle_farm", "aso_optimization", DecisionType.OBSERVE),
        _decision("word_maze", "monetization", DecisionType.REJECT),
    ]
    return DecisionReport(total_decisions=len(decisions), decisions=decisions)


def test_build_simulates_only_actionable_decisions():
    """EXECUTE/APPROVE 模拟，OBSERVE/REJECT 跳过。"""
    report = GrowthSimulationAgent().build(_dec_report(), created_at="2026-07-29")
    assert report.total_decisions == 2
    assert report.summary["skipped"] == 2
    assert {s.game_id for s in report.simulations} == {"merge_witch", "puzzle_island"}
    assert report.summary["real_api_called"] is False
    assert report.summary["memory_prior_used"] is False
    # 每个决策 × 每个非基线情景一条反事实对比
    assert len(report.comparisons) == 2 * 2
    assert report.created_at == "2026-07-29"


def test_build_reproducible():
    a = GrowthSimulationAgent().build(_dec_report(), created_at="2026-07-29")
    b = GrowthSimulationAgent().build(_dec_report(), created_at="2026-07-29")
    assert a.to_dict() == b.to_dict()


def test_store_records_report(tmp_path):
    store = JsonlSimulationStore(path=str(tmp_path / "sim_runs.jsonl"))
    agent = GrowthSimulationAgent(store=store)
    agent.build(_dec_report(), created_at="2026-07-29")
    agent.build(_dec_report(), created_at="2026-07-30")
    rows = store.all()
    assert len(rows) == 2
    assert store.latest().created_at == "2026-07-30"
    # 坏行容错
    with open(tmp_path / "sim_runs.jsonl", "a", encoding="utf-8") as fh:
        fh.write("{not json}\n")
    assert len(store.all()) == 2


def _poisoned_graph(tmp_path, strategy_type: str) -> GrowthMemoryGraph:
    """2 条失败记忆 + 实得收入 -0.60 → 该策略先验被拉负 → BLOCK。"""
    g = GrowthMemoryGraph(path=str(tmp_path / "graph.jsonl"))
    g.add_node(GraphNode(
        id=node_id(NodeType.EXECUTION, "e1"),
        type=NodeType.EXECUTION,
        label="exec e1",
        payload={"execution_id": "e1", "revenue_delta": -0.60},
    ))
    for i in range(2):
        g.add_node(GraphNode(
            id=node_id(NodeType.RESULT, f"r{i}"),
            type=NodeType.RESULT,
            label=f"result {i}",
            payload={
                "strategy_type": strategy_type,
                "domain": "creative",
                "action_type": "SAFE",
                "success": False,
                "execution_id": "e1",
            },
        ))
    return g


def test_build_with_memory_graph_blocks_bad_history(tmp_path):
    """记忆图谱里真金白银亏过的策略 → 先验拉负 → 闸门 BLOCK。"""
    graph = _poisoned_graph(tmp_path, "creative_refresh")
    report = GrowthSimulationAgent().build(_dec_report(), memory_graph=graph)
    assert report.summary["memory_prior_used"] is True
    assert report.summary["block"] == 1
    blocked = next(
        s for s in report.simulations if s.flag.status == PreFlightStatus.BLOCK
    )
    assert blocked.game_id == "merge_witch"
    assert blocked.prior.source == "static+memory"
    assert abs(blocked.prior.expected_revenue_change - (-0.24)) < TOL
    # 组合分布剔除 BLOCK → 仍为正
    assert report.portfolio["baseline"].p50 > 0.0


# --------------------------------------------------------------------------- #
# Test8：端到端 Reality → … → Strategy → [Simulation 闸门] → Execution
# --------------------------------------------------------------------------- #
def _build_company(tmp_path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
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


def test8_e2e_gate_open(tmp_path):
    """无坏记忆 → 闸门放行/复核但不 BLOCK，全部计划进入执行，SIM 锁死。"""
    store, company = _build_company(tmp_path)
    sim_store = JsonlSimulationStore(path=str(tmp_path / "sim_runs.jsonl"))

    dec_report, portfolio, sim_report, exec_reports = run_pipeline(
        company, store=store,
        simulation_store=sim_store,
        execution_router=_router(tmp_path),
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    assert dec_report.total_decisions >= 2
    assert sim_report.total_decisions >= 1
    assert sim_report.summary["block"] == 0
    assert sim_report.summary["real_api_called"] is False
    # 无 BLOCK → 执行报告数 = 作战计划数
    assert len(exec_reports) == len(portfolio.plans)
    for report in exec_reports:
        assert report.summary["real_api_called"] is False
    # 模拟报告已落盘
    assert len(sim_store.all()) == 1
    line = (tmp_path / "sim_runs.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(line)["summary"]["real_api_called"] is False


def test8_e2e_gate_blocks_poisoned_strategy(tmp_path):
    """creative_refresh 有亏损记忆 → 该计划被闸门挡在 E17.6 之外。"""
    store, company = _build_company(tmp_path)
    graph = _poisoned_graph(tmp_path, "creative_refresh")

    dec_report, portfolio, sim_report, exec_reports = run_pipeline(
        company, store=store,
        memory_graph=graph,
        execution_router=_router(tmp_path),
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    assert sim_report.summary["block"] >= 1
    blocked_ids = set(sim_report.blocked_decision_ids())
    assert blocked_ids
    # 被 BLOCK 的计划不执行
    assert len(exec_reports) == len(
        [p for p in portfolio.plans if p.decision_id not in blocked_ids]
    )
    executed_decisions = {r.decision_id for r in exec_reports}
    assert blocked_ids.isdisjoint(executed_decisions)


def test8_execute_false_skips_execution(tmp_path):
    """execute=False → 只出模拟报告，不触发 E17.6。"""
    store, company = _build_company(tmp_path)
    _, _, sim_report, exec_reports = run_pipeline(
        company, store=store,
        execute=False,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )
    assert sim_report.total_decisions >= 1
    assert exec_reports == []
