"""P3.3.3 — 模型层测试（to_dict/from_dict 往返 + 枚举契约）。"""
from __future__ import annotations

import pytest

from src.ceo_intelligence.decision_engine.models import DecisionType
from src.execution.models import ExecutionAction
from src.operator.adaptive_strategy import (
    AdaptiveAction,
    AdaptiveStrategyRequest,
    AdaptiveStrategyResult,
    AdaptiveStrategyTemplate,
    FinalStatus,
    Stage,
)


# --- 枚举契约 -------------------------------------------------------------
def test_adaptive_action_values():
    assert AdaptiveAction.NETWORK_CLEANUP.value == "network_cleanup"
    assert AdaptiveAction.CAMPAIGN_PAUSE.value == "campaign_pause"
    assert AdaptiveAction.BUDGET_SCALE.value == "budget_scale"


def test_stage_state_machine_states_present():
    vals = {s.value for s in Stage}
    for v in ("created", "simulation_pending", "simulation_pass",
              "approval_pending", "authorized", "executing", "completed",
              "simulation_fail", "approval_rejected", "execution_failed",
              "recovery_required"):
        assert v in vals


def test_final_status_includes_blocked_unsupported():
    assert FinalStatus.BLOCKED_UNSUPPORTED.value == "blocked_unsupported"
    assert FinalStatus.SIMULATION_FAIL.value == "simulation_fail"
    assert FinalStatus.APPROVAL_REJECTED.value == "approval_rejected"
    assert FinalStatus.EXECUTION_FAILED.value == "execution_failed"
    assert FinalStatus.RECOVERY_REQUIRED.value == "recovery_required"
    assert FinalStatus.COMPLETED.value == "completed"


# --- Template 往返 --------------------------------------------------------
def _sample_template() -> AdaptiveStrategyTemplate:
    return AdaptiveStrategyTemplate(
        strategy_id="adaptive.network_cleanup",
        display_name="关停僵尸广告网络",
        adaptive_action=AdaptiveAction.NETWORK_CLEANUP,
        decision_action="MAX_OPTIMIZE",
        opportunity_type="monetization",
        decision_type=DecisionType.EXECUTE,
        expected_value=0.18,
        confidence=0.70,
        risk=0.50,
        reason="低 eCPM 网络拖累整体变现",
        execution_action=ExecutionAction.DISABLE_NETWORK,
        dimension="ad_monetization",
        provider_params={"network": "zombie_network"},
        supported=True,
    )


def test_template_to_dict_keys():
    d = _sample_template().to_dict()
    assert d["strategy_id"] == "adaptive.network_cleanup"
    assert d["adaptive_action"] == "network_cleanup"
    assert d["decision_action"] == "MAX_OPTIMIZE"
    assert d["execution_action"] == "disable_network"
    assert d["provider_params"] == {"network": "zombie_network"}
    assert d["supported"] is True


def test_template_round_trip():
    t = _sample_template()
    t2 = AdaptiveStrategyTemplate.from_dict(t.to_dict())
    assert t2.strategy_id == t.strategy_id
    assert t2.adaptive_action == t.adaptive_action
    assert t2.decision_type == t.decision_type
    assert t2.execution_action == t.execution_action
    assert t2.provider_params == t.provider_params
    assert t2.supported == t.supported


def test_template_default_supported_true():
    t = AdaptiveStrategyTemplate(
        strategy_id="x", display_name="x",
        adaptive_action=AdaptiveAction.CAMPAIGN_PAUSE,
        decision_action="UA_STOP", opportunity_type="ua_stop_loss",
        execution_action=ExecutionAction.PAUSE_CAMPAIGN,
    )
    assert t.supported is True
    assert t.from_dict({"strategy_id": "x"})  # 不抛


# --- Request 往返 ---------------------------------------------------------
def test_request_round_trip():
    r = AdaptiveStrategyRequest(
        proposal_id="p1", strategy_id="adaptive.network_cleanup",
        target="game_a", expected_change="kill",
        parameters={"network": "n1"}, mode="production",
        approver="op1", approver_role="OPERATOR",
    )
    r2 = AdaptiveStrategyRequest.from_dict(r.to_dict())
    assert r2.proposal_id == "p1"
    assert r2.strategy_id == "adaptive.network_cleanup"
    assert r2.target == "game_a"
    assert r2.parameters == {"network": "n1"}
    assert r2.mode == "production"
    assert r2.approver == "op1"
    assert r2.approver_role == "OPERATOR"
    assert r2.requires_simulation is True


def test_request_defaults():
    r = AdaptiveStrategyRequest(proposal_id="p", strategy_id="s", target="g")
    assert r.mode == "dry_run"
    assert r.parameters == {}
    assert r.requires_simulation is True
    assert r.source == "strategy_loop"
    assert r.approver == ""
    assert r.approver_role == ""


# --- Result 往返 ----------------------------------------------------------
def test_result_round_trip():
    res = AdaptiveStrategyResult(
        proposal_id="p1", strategy_id="adaptive.network_cleanup",
        target="game_a", action="disable_network",
        stage=Stage.COMPLETED.value, final_status=FinalStatus.COMPLETED.value,
        simulation_flag="pass", approval_status="auto",
        execution_verdict="executed", real_api_called=True,
        feedback={"outcome": "SUCCESS"},
        errors=["e1"], trace=["a", "b"],
    )
    r2 = AdaptiveStrategyResult.from_dict(res.to_dict())
    assert r2.proposal_id == "p1"
    assert r2.stage == "completed"
    assert r2.final_status == "completed"
    assert r2.real_api_called is True
    assert r2.feedback == {"outcome": "SUCCESS"}
    assert r2.errors == ["e1"]
    assert r2.trace == ["a", "b"]


def test_result_defaults_sane():
    res = AdaptiveStrategyResult()
    d = res.to_dict()
    assert d["stage"] == "created"
    assert d["final_status"] == "pending"
    assert d["real_api_called"] is False
    assert d["errors"] == []
    assert d["trace"] == []
