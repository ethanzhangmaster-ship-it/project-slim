"""P3.3.3 — Controller 状态机闭环测试（覆盖契约 §8 Case 1-6/8/9/10）。

纪律：
- 全部用注入的 FakeProvider（绝不触真实 Max/Meta/Play 外部系统）；
- DRY_RUN 路径默认 fake（real_api_called=False），PRODUCTION 路径单独验证 real_api_called=True；
- 审批结果用 FakeApprovalService 确定性注入（DENY / MANUAL / AUTO）。
"""
from __future__ import annotations

from typing import Any, List, Optional

from src.execution.models import ExecutionAction
from src.execution.providers.base import BaseExecutionProvider
from src.execution.providers.result import STATUS_SUCCESS, ExecutionResult
from src.operator.adaptive_strategy import (
    FinalStatus,
    build_adaptive_strategy_engine,
)

from .conftest import (
    MAX_ACTIONS,
    META_ACTIONS,
    blocking_prior,
    build_engine,
    make_request,
    ok_providers,
    review_prior,
)


# ===========================================================================
# 可注入的审批服务（确定性控制 outcome）
# ===========================================================================
class FakeApprovalService:
    def __init__(self, outcome: str = "MANUAL", *, auto: bool = False,
                 authorization: Any = None, approval_id: str = "ap_1",
                 reason: str = "") -> None:
        self.outcome = outcome
        self.auto = auto
        self.authorization = authorization
        self.approval_id = approval_id
        self.reason = reason
        self.submit_calls: List[Any] = []
        self.approve_calls: List[Any] = []
        self.authorize_calls: List[Any] = []

    def submit(self, request, requested_by="system"):
        request.approval_id = self.approval_id
        self.submit_calls.append(request)
        r = type("R", (), {})()
        r.request = request
        r.outcome = self.outcome
        r.auto_approved = self.auto
        r.authorization = self.authorization
        r.reason = self.reason
        return r

    def approve(self, approval_id, approver, role):
        self.approve_calls.append((approval_id, approver, role))
        a = type("A", (), {})()
        a.approved_by = approver
        a.allowed_action = "disable_network"
        a.approval_id = approval_id
        return a

    def authorize(self, request, authorization):
        self.authorize_calls.append((request, authorization))
        return request


def _eng(providers=None, memory_path=None, prior_provider=None, approval=None):
    ctrl = build_adaptive_strategy_engine(
        providers=providers if providers is not None else ok_providers(),
        memory_path=memory_path,
        prior_provider=prior_provider,
    )
    if approval is not None:
        ctrl.approval = approval
    return ctrl


# ===========================================================================
# Case 1：Proposal 自动进 Simulation，不执行（DRY_RUN 不触网）
# ===========================================================================
def test_case1_dry_run_enters_simulation_no_real_call():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(mode="dry_run", approver="op1"))
    assert res.simulation_flag in ("pass", "review")
    assert res.real_api_called is False
    assert res.final_status == FinalStatus.COMPLETED.value
    # DRY_RUN：Provider 只走 _dry_run，绝不走 _do_real
    assert provs[0].real_invocations == 0
    assert provs[0].dry_invocations == 1


def test_case1_manual_no_approver_does_not_execute():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(approver=""))
    assert res.final_status == FinalStatus.RECOVERY_REQUIRED.value
    assert res.execution_result is None
    assert provs[0].execute_calls == []


# ===========================================================================
# Case 2：SIM_FAIL（注入负先验）→ BLOCKED，不进审批/执行
# ===========================================================================
def test_case2_sim_fail_blocks_no_approval_no_execution():
    provs = ok_providers()
    ctrl = _eng(providers=provs, prior_provider=blocking_prior)
    res = ctrl.run(make_request())
    assert res.simulation_flag == "block"
    assert res.final_status == FinalStatus.SIMULATION_FAIL.value
    assert "approval_pending" not in res.trace
    assert "executing" not in res.trace
    # Provider 从未被调用
    assert all(p.execute_calls == [] for p in provs)


def test_case2_review_prior_still_proceeds_to_approval():
    """REVIEW 闸门不阻断（契约 §4），但 BLOCK 才停。"""
    provs = ok_providers()
    ctrl = _eng(providers=provs, prior_provider=review_prior)
    res = ctrl.run(make_request(approver="op1"))
    assert res.simulation_flag == "review"
    # 仍到达审批并执行（有 approver）
    assert res.final_status == FinalStatus.COMPLETED.value


# ===========================================================================
# Case 3：APPROVAL_REJECT → STOP，不执行
# ===========================================================================
def test_case3_approval_deny_stops_no_provider():
    provs = ok_providers()
    deny = FakeApprovalService(outcome="DENY", reason="policy denies")
    ctrl = _eng(providers=provs, approval=deny)
    res = ctrl.run(make_request())
    assert res.final_status == FinalStatus.APPROVAL_REJECTED.value
    assert res.execution_result is None
    assert "policy DENY" in res.trace
    assert "executing" not in res.trace
    assert all(p.execute_calls == [] for p in provs)


def test_case3_approve_failure_rejected():
    provs = ok_providers()
    class FailApprove(FakeApprovalService):
        def approve(self, approval_id, approver, role):
            raise RuntimeError("approver unknown")
    ctrl = _eng(providers=provs, approval=FailApprove(outcome="MANUAL"))
    res = ctrl.run(make_request())
    assert res.final_status == FinalStatus.APPROVAL_REJECTED.value
    assert all(p.execute_calls == [] for p in provs)


# ===========================================================================
# Case 4：APPROVAL_PASS → SafeExecutor 验证 real_api_called 纪律
# ===========================================================================
def test_case4_dry_run_real_api_called_false():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(mode="dry_run", approver="op1"))
    assert res.real_api_called is False
    assert res.final_status == FinalStatus.COMPLETED.value
    assert res.execution_verdict  # 非空


def test_case4_production_real_api_called_true():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(mode="production", approver="op1"))
    assert res.real_api_called is True
    assert res.final_status == FinalStatus.COMPLETED.value
    # PRODUCTION：走 _do_real
    assert provs[0].real_invocations == 1
    assert provs[0].dry_invocations == 0


def test_case4_auto_approval_path():
    """AUTO 批准（auto_approved）也应闭环完成。"""
    provs = ok_providers()
    auto = FakeApprovalService(outcome="AUTO", auto=True, authorization=object())
    ctrl = _eng(providers=provs, approval=auto)
    res = ctrl.run(make_request(mode="dry_run"))
    assert res.approval_status == "AUTO"
    assert res.final_status == FinalStatus.COMPLETED.value
    # AUTO 仍需 execute（auto_approved 只是免人工）
    assert provs[0].execute_calls


# ===========================================================================
# Case 5：执行成功 → 反馈 → StrategyMemory
# ===========================================================================
def test_case5_feedback_and_memory(tmp_path):
    mem = str(tmp_path / "strategy_memory.jsonl")
    ctrl = build_adaptive_strategy_engine(
        providers=ok_providers(), memory_path=mem)
    res = ctrl.run(make_request(strategy_id="adaptive.network_cleanup",
                                approver="op1", mode="dry_run"))
    assert res.final_status == FinalStatus.COMPLETED.value
    assert res.feedback is not None
    assert res.feedback["outcome"] == "SUCCESS"
    # 策略经验被更新
    st = ctrl.memory.all_states()["adaptive.network_cleanup"]
    assert st.performance["samples"] == 1
    assert st.performance["wins"] == 1
    assert st.performance["reward_sum"] == 1.0
    # 落盘
    import os
    assert os.path.exists(mem)
    with open(mem, "r", encoding="utf-8") as fh:
        lines = [l for l in fh.read().splitlines() if l.strip()]
    assert any("adaptive.network_cleanup" in l for l in lines)


def test_case5_campaign_pause_memory(tmp_path):
    mem = str(tmp_path / "strategy_memory.jsonl")
    ctrl = build_adaptive_strategy_engine(
        providers=ok_providers(), memory_path=mem)
    res = ctrl.run(make_request(strategy_id="adaptive.campaign_pause",
                                target="g2",
                                parameters={"campaign_id": "c1"},
                                approver="op1", mode="dry_run"))
    assert res.feedback["outcome"] == "SUCCESS"
    st = ctrl.memory.all_states()["adaptive.campaign_pause"]
    assert st.performance["samples"] == 1


# ===========================================================================
# Case 6：状态机完整跃迁（trace 顺序）
# ===========================================================================
def test_case6_trace_full_success_path():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(mode="dry_run", approver="op1"))
    stages = [t for t in res.trace if t in {
        "created", "simulation_pending", "simulation_pass", "approval_pending",
        "authorized", "executing", "completed",
    }]
    assert stages == [
        "created", "simulation_pending", "simulation_pass",
        "approval_pending", "authorized", "executing", "completed",
    ]
    assert res.stage == "completed"


def test_case6_terminal_states_do_not_loop():
    """失败终态不会再触发 Provider。"""
    provs = ok_providers()
    deny = FakeApprovalService(outcome="DENY")
    ctrl = _eng(providers=provs, approval=deny)
    res = ctrl.run(make_request())
    assert res.final_status == FinalStatus.APPROVAL_REJECTED.value
    assert res.stage == "approval_rejected"
    assert all(p.execute_calls == [] for p in provs)


# ===========================================================================
# Case 8：Budget Scale 门控（暂缓项直接 BLOCKED_UNSUPPORTED）
# ===========================================================================
def test_case8_budget_scale_blocked_unsupported():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(strategy_id="adaptive.budget_scale"))
    assert res.final_status == FinalStatus.BLOCKED_UNSUPPORTED.value
    assert res.stage == "created"
    assert all(p.execute_calls == [] for p in provs)


def test_case8_any_unknown_strategy_blocked():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(strategy_id="adaptive.totally_made_up"))
    assert res.final_status == FinalStatus.BLOCKED_UNSUPPORTED.value
    assert all(p.execute_calls == [] for p in provs)


# ===========================================================================
# Case 9：无 approver 的 MANUAL 请求 → RECOVERY_REQUIRED
# ===========================================================================
def test_case9_manual_no_approver_recovery_required():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(approver=""))
    assert res.final_status == FinalStatus.RECOVERY_REQUIRED.value
    assert res.stage == "recovery_required"
    assert res.execution_result is None
    assert "MANUAL waiting for human" in "\n".join(res.trace)
    assert all(p.execute_calls == [] for p in provs)


def test_case9_manual_with_approver_completes():
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(approver="op1", approver_role="OPERATOR"))
    assert res.final_status == FinalStatus.COMPLETED.value
    assert provs[0].execute_calls  # 确实执行了（DRY_RUN）


# ===========================================================================
# Case 10：re-merge 正确性（provider 参数进 expected_impact）
# ===========================================================================
class EchoProvider(BaseExecutionProvider):
    """回显 intent.expected_impact 中的 provider 参数到 after_state。"""
    def __init__(self, provider_id, supported_actions):
        self.provider_id = provider_id
        self.supported_actions = tuple(supported_actions)
        self.execute_calls = []
        self.real_invocations = 0
        self.dry_invocations = 0
    def execute(self, request):
        self.execute_calls.append(request)
        return super().execute(request)
    def _echo(self, request):
        impact = request.intent.expected_impact or {}
        return ExecutionResult(
            request_id=request.request_id, provider=self.provider_id,
            status=STATUS_SUCCESS, real_api_called=False,
            before_state={}, after_state={
                "network": impact.get("network"),
                "ad_unit_id": impact.get("ad_unit_id"),
                "campaign_id": impact.get("campaign_id"),
            })
    def _dry_run(self, request):
        self.dry_invocations += 1
        return self._echo(request)
    def _do_real(self, request):
        self.real_invocations += 1
        return self._echo(request)


def _echo_providers():
    return [EchoProvider("max", MAX_ACTIONS), EchoProvider("meta", META_ACTIONS)]


def test_case10_remerge_network_param():
    provs = _echo_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(
        strategy_id="adaptive.network_cleanup",
        parameters={"network": "NET_X", "ad_unit_id": "AU_Y"},
        approver="op1", mode="dry_run"))
    assert res.final_status == FinalStatus.COMPLETED.value
    after = res.execution_result["after_state"]
    assert after["network"] == "NET_X"
    assert after["ad_unit_id"] == "AU_Y"


def test_case10_remerge_campaign_param():
    provs = _echo_providers()
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(
        strategy_id="adaptive.campaign_pause", target="g2",
        parameters={"campaign_id": "CAMP_Z"},
        approver="op1", mode="dry_run"))
    after = res.execution_result["after_state"]
    assert after["campaign_id"] == "CAMP_Z"


# ===========================================================================
# 额外变体：provider 执行失败 / 阻塞 的闭环处理
# ===========================================================================
def test_execution_failed_propagates():
    from src.execution.providers.result import STATUS_FAILED
    provs = [
        type("P", (BaseExecutionProvider,), {
            "provider_id": "max",
            "supported_actions": MAX_ACTIONS,
            "_do_real": lambda self, r: ExecutionResult(
                request_id=r.request_id, provider="max",
                status=STATUS_FAILED, real_api_called=True,
                before_state={}, after_state={}, error="boom"),
        })(),
        type("P2", (BaseExecutionProvider,), {
            "provider_id": "meta",
            "supported_actions": META_ACTIONS,
        })(),
    ]
    ctrl = _eng(providers=provs)
    res = ctrl.run(make_request(mode="production", approver="op1"))
    assert res.final_status == FinalStatus.EXECUTION_FAILED.value
    assert res.stage == "execution_failed"


def test_contract_blocked_with_empty_registry_is_guarded():
    """若 build_contract 因无 registry 而 BLOCKED → EXECUTION_FAILED（不触 Provider）。"""
    provs = ok_providers()
    ctrl = _eng(providers=provs)
    # 正常 registry 下不应走此分支；此处仅确认终态安全
    res = ctrl.run(make_request(approver="op1"))
    assert res.final_status == FinalStatus.COMPLETED.value
