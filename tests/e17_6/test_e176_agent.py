"""E17.6 — GrowthExecutionRouterAgent：execute_plan + Test7 端到端。"""
import json

from audit.trail import AuditTrail
from src.ceo_intelligence.execution_router.agent import (
    GrowthExecutionRouterAgent,
    run_pipeline,
)
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.registry import build_default_registry
from src.ceo_intelligence.execution_router.router import ApprovalOutbox, ExecutionRouter
from src.ceo_intelligence.strategy_planner.models import GrowthStrategyPlan
from src.ceo_intelligence.strategy_planner.templates import build_tasks, get_template
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot


def _agent(tmp_path) -> GrowthExecutionRouterAgent:
    router = ExecutionRouter(
        registry=build_default_registry(
            release_state_path=str(tmp_path / "release_state.json")
        ),
        audit=AuditTrail(audit_dir=str(tmp_path / "audit")),
        memory=ExecutionMemory(str(tmp_path / "exec_mem.jsonl")),
        outbox=ApprovalOutbox(str(tmp_path / "outbox.jsonl")),
    )
    return GrowthExecutionRouterAgent(router=router)


def _plan(strategy_type: str) -> GrowthStrategyPlan:
    tpl = get_template(strategy_type)
    return GrowthStrategyPlan(
        game_id="merge_witch",
        decision_id="dec_plan",
        objective=tpl.objective,
        strategy_type=strategy_type,
        tasks=build_tasks(tpl),
    )


def test_execute_creative_refresh_plan(tmp_path):
    """creative_refresh：前 3 步 SAFE 自动成功，Meta 实验待审批，下游跳过。"""
    agent = _agent(tmp_path)
    report = agent.execute_plan(_plan("creative_refresh"))

    assert report.game_id == "merge_witch"
    assert report.execution_id.startswith("exec_")
    assert report.status == "waiting_approval"
    s = report.summary
    assert s["total"] == 5
    assert s["success"] == 3            # analyze_dna / generate / clip
    assert s["waiting_approval"] == 1   # Run Meta experiment（CONTROLLED）
    assert s["skipped"] == 1            # Evaluate ROAS 依赖实验
    assert s["real_api_called"] is False

    results = report.results()
    assert results[3].system == "meta_ads"
    assert "dependency task 4" in results[4].detail

    # 待审批信箱有且仅有 Meta 实验
    pending = agent.pending_approvals()
    assert len(pending) == 1
    assert pending[0]["action"]["action_type"] == "run_experiment"

    # markdown 可渲染
    md = report.to_markdown()
    assert "执行报告" in md and "meta_ads" in md


def test_execute_plan_all_safe_success(tmp_path):
    """release_health：triage + 2 个人类任务登记，全部 SAFE → success。"""
    agent = _agent(tmp_path)
    report = agent.execute_plan(_plan("release_health"))
    assert report.status == "success"
    assert report.summary["success"] == 3
    assert report.summary["waiting_approval"] == 0
    systems = [r.system for r in report.results()]
    assert systems[0] == "play_runtime_release"
    assert set(systems[1:]) == {"analytics"}


def test_execute_plan_audit_covers_every_action(tmp_path):
    """Test5（计划级）：5 个动作 → 5 条 EP0 ExecutionRecord。"""
    agent = _agent(tmp_path)
    report = agent.execute_plan(_plan("creative_refresh"))
    lines = (tmp_path / "audit" / "executions.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == report.summary["total"] == 5
    # 记忆同样每动作一条
    assert len(agent.router.memory.for_execution(report.execution_id)) == 5


def test_approve_then_rerun_unblocks_downstream(tmp_path):
    """审批闭环：approve 待审批动作后执行成功并出信箱。"""
    agent = _agent(tmp_path)
    agent.execute_plan(_plan("creative_refresh"))
    pending = agent.pending_approvals()
    res = agent.approve(pending[0]["action_id"], approver="ethan", reason="go")
    assert res.status.value == "success"
    assert agent.pending_approvals() == []
    approvals = (tmp_path / "audit" / "approvals.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert json.loads(approvals[0])["approved"] is True


# --------------------------------------------------------------------------- #
# Test7：端到端 Reality → Opportunity → Decision → Strategy → Execution
# --------------------------------------------------------------------------- #
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


def test7_e2e_reality_to_execution(tmp_path):
    """Test7：全链路 E17.1→2→3→4→6，SIM 纪律全程锁死。"""
    store, company = _build_company(tmp_path)
    router = ExecutionRouter(
        registry=build_default_registry(
            release_state_path=str(tmp_path / "release_state.json")
        ),
        audit=AuditTrail(audit_dir=str(tmp_path / "audit")),
        memory=ExecutionMemory(str(tmp_path / "exec_mem.jsonl")),
        outbox=ApprovalOutbox(str(tmp_path / "outbox.jsonl")),
    )

    dec_report, portfolio, reports = run_pipeline(
        company, store=store,
        execution_router=router,
        approval_queue_path=str(tmp_path / "q.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        created_at="2026-07-29",
    )

    # 上游产出正常
    assert dec_report.total_decisions >= 2
    assert portfolio.summary["planned"] >= 2
    # 每条作战计划都有执行报告
    assert len(reports) == portfolio.summary["planned"]

    for report in reports:
        assert report.summary["total"] == len(report.actions) > 0
        # SIM 纪律：全程无真实 API
        assert report.summary["real_api_called"] is False
        for r in report.results():
            assert r.real_api_called is False

    # creative_refresh 链路：走到 Meta 实验即停下等审批
    cr = next(r for r in reports if r.strategy_type == "creative_refresh")
    assert cr.status == "waiting_approval"
    assert cr.summary["success"] >= 3

    # 审计三流落盘：决策（上游）+ 执行（本层）
    exec_lines = (tmp_path / "audit" / "executions.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(exec_lines) >= sum(r.summary["total"] for r in reports)

    # 执行记忆闭环：每动作一条经验，可按域统计成功率
    mem_rows = router.memory.all()
    assert len(mem_rows) == sum(r.summary["total"] for r in reports)
    assert router.memory.success_rate("creative") > 0.0
