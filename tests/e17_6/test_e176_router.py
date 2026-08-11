"""E17.6 — ExecutionRouter：路由 / 权限门 / 状态机 / 审计 / 记忆测试。

覆盖 spec Test1（CREATIVE 路由）、Test2（UA 路由）、Test3（权限审批）、
Test4（RELEASE→E15）、Test5（审计）、Test6（失败回滚）。
"""
import json

from audit.trail import AuditTrail
from src.ceo_intelligence.execution_router.memory import ExecutionMemory
from src.ceo_intelligence.execution_router.models import (
    ExecutionAction,
    ExecutionStatus,
)
from src.ceo_intelligence.execution_router.registry import build_default_registry
from src.ceo_intelligence.execution_router.router import ApprovalOutbox, ExecutionRouter


def _router(tmp_path) -> ExecutionRouter:
    return ExecutionRouter(
        registry=build_default_registry(
            release_state_path=str(tmp_path / "release_state.json")
        ),
        audit=AuditTrail(audit_dir=str(tmp_path / "audit")),
        memory=ExecutionMemory(str(tmp_path / "exec_mem.jsonl")),
        outbox=ApprovalOutbox(str(tmp_path / "outbox.jsonl")),
    )


def _action(domain: str, action_type: str, **kw) -> ExecutionAction:
    return ExecutionAction(
        action_id="", game_id="merge_witch",
        domain=domain, action_type=action_type,
        decision_id="dec_r", plan_strategy_type="creative_refresh", **kw,
    )


def test1_creative_action_routes_to_creative_adapter(tmp_path):
    """Test1：CREATIVE 动作 → CreativeAdapter，SAFE 自动执行成功。"""
    r = _router(tmp_path)
    res = r.route(_action("creative", "generate_creatives", payload={"count": 30}))
    assert res.system == "creative_agent"
    assert res.status == ExecutionStatus.SUCCESS
    assert res.real_api_called is False
    assert "30 creatives" in res.detail
    # 状态机完整轨迹：created→validating→executing→success→learning
    assert res.state_history == [
        "created", "validating", "executing", "success", "learning",
    ]


def test2_increase_budget_routes_to_meta_and_executes_after_approval(tmp_path):
    """Test2：INCREASE_BUDGET → MetaAdapter；批准后真正执行。"""
    r = _router(tmp_path)
    action = _action("ua", "increase_budget", payload={"percent": 20}, risk_level=0.5)
    res = r.route(action)
    assert res.system == "meta_ads"                     # 路由到 MetaAdapter
    assert res.status == ExecutionStatus.WAITING_APPROVAL

    approved = r.approve(action.action_id, approver="ethan", reason="scale winner")
    assert approved.status == ExecutionStatus.SUCCESS
    assert approved.system == "meta_ads"
    assert "increase budget 20%" in approved.detail
    assert approved.real_api_called is False
    # 审批后 outbox 清空
    assert r.pending_approvals() == []


def test3_permission_gate_budget_waits_for_approval(tmp_path):
    """Test3：预算增加（CONTROLLED）→ WAITING_APPROVAL 并进审批信箱。"""
    r = _router(tmp_path)
    action = _action("ua", "increase_budget", payload={"percent": 20})
    res = r.route(action)
    assert res.status == ExecutionStatus.WAITING_APPROVAL
    assert res.permission_tier == "controlled"
    pending = r.pending_approvals()
    assert len(pending) == 1
    assert pending[0]["action_id"] == action.action_id
    # 拒绝后不再待办，且不执行
    r.reject(action.action_id, approver="ethan", reason="not now")
    assert r.pending_approvals() == []


def test3b_critical_pricing_never_auto_executes(tmp_path):
    """CRITICAL：apply_pricing 即使批准也不自动执行（只能人工后台）。"""
    r = _router(tmp_path)
    action = _action("economy", "apply_pricing")
    res = r.route(action)
    assert res.status == ExecutionStatus.WAITING_APPROVAL
    assert res.permission_tier == "critical"
    assert r.pending_approvals()[0]["manual_only"] is True

    approved = r.approve(action.action_id, approver="ethan")
    assert approved.status == ExecutionStatus.SKIPPED
    assert "manually" in approved.detail
    assert approved.real_api_called is False


def test4_halt_release_routes_to_e15_release_agent(tmp_path):
    """Test4：HALT_RELEASE → PlayReleaseAdapter（E15 ReleaseAgent），SAFE 止血。"""
    r = _router(tmp_path)
    res = r.route(_action(
        "release", "halt_release", target="com.gamefactory.mergewitch",
    ))
    assert res.system == "play_runtime_release"
    assert res.status == ExecutionStatus.SUCCESS
    assert res.real_api_called is False                 # SIM 门控生效
    assert res.data.get("op") == "halt_rollout"


def test5_every_action_writes_audit_record(tmp_path):
    """Test5：每个动作（含待审批/跳过）都有 EP0 ExecutionRecord。"""
    r = _router(tmp_path)
    r.route(_action("creative", "analyze_dna"))                 # SUCCESS
    r.route(_action("ua", "increase_budget"))                   # WAITING_APPROVAL
    r.record_skip(_action("analytics", "evaluate_roas"), "skipped: dep failed")

    lines = (tmp_path / "audit" / "executions.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    records = [json.loads(x) for x in lines]
    assert records[0]["action"] == "creative:analyze_dna:success"
    assert records[1]["action"] == "ua:increase_budget:waiting_approval"
    assert records[2]["action"] == "analytics:evaluate_roas:skipped"
    assert all(rec["agent"] == "execution_router" for rec in records)


def test6_failure_triggers_rollback(tmp_path):
    """Test6：API 失败 → FAILED → ROLLBACK，rolled_back=True。"""
    r = _router(tmp_path)
    res = r.route(_action(
        "creative", "generate_creatives", payload={"simulate_failure": True},
    ))
    assert res.status == ExecutionStatus.ROLLBACK
    assert res.rolled_back is True
    assert res.error == "creative pipeline error (simulated)"
    assert "failed" in res.state_history
    assert "rollback" in res.state_history
    # 审计记录失败
    lines = (tmp_path / "audit" / "executions.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[0])
    assert rec["success"] is False
    assert rec["error"]


def test_execution_memory_records_full_loop(tmp_path):
    """Execution Memory：每个动作沉淀 Decision→Execution→Result 闭环。"""
    r = _router(tmp_path)
    r.route(_action("creative", "analyze_dna"), execution_id="exec_t")
    r.route(_action("creative", "generate_creatives",
                    payload={"simulate_failure": True}), execution_id="exec_t")

    rows = r.memory.for_execution("exec_t")
    assert len(rows) == 2
    ok, bad = rows[0], rows[1]
    assert ok.success is True and ok.status == "success"
    assert bad.success is False and bad.rolled_back is True
    assert ok.decision_id == "dec_r"
    assert ok.strategy_type == "creative_refresh"
    assert abs(r.memory.success_rate("creative") - 0.5) < 1e-6


def test_unknown_domain_fails_without_rollback(tmp_path):
    """无 adapter 的域 → FAILED（配置错误，不回滚）。"""
    r = _router(tmp_path)
    res = r.route(_action("nonexistent", "anything"))
    assert res.status == ExecutionStatus.FAILED
    assert "no adapter" in res.error
    assert res.rolled_back is False
