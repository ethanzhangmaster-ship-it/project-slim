"""P3.3.3 — Planner 测试（StrategyProposal → GrowthDecision + Provider 参数）。"""
from __future__ import annotations

import pytest

from src.ceo_intelligence.decision_engine.models import DecisionType
from src.execution.models import ExecutionAction
from src.operator.adaptive_strategy import (
    AdaptiveAction,
    AdaptiveStrategyPlanner,
    AdaptiveStrategyRequest,
    AdaptiveStrategyTemplate,
    UnknownStrategyError,
)
from src.operator.adaptive_strategy.planner import DEFAULT_TEMPLATES


def test_default_templates_have_two_safe_actions():
    assert set(DEFAULT_TEMPLATES.keys()) == {
        "adaptive.network_cleanup",
        "adaptive.campaign_pause",
    }


def test_plan_network_cleanup_maps_to_max_optimize():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.network_cleanup",
        target="g1", parameters={"network": "n1"}))
    d = plan.decision
    assert d.action == "MAX_OPTIMIZE"
    assert d.opportunity_id == "g1:monetization"
    assert d.decision_type == DecisionType.EXECUTE
    assert plan.template.execution_action == ExecutionAction.DISABLE_NETWORK
    assert plan.opportunity_id == "g1:monetization"


def test_plan_campaign_pause_maps_to_ua_stop():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.campaign_pause",
        target="g2", parameters={"campaign_id": "c1"}))
    d = plan.decision
    assert d.action == "UA_STOP"
    assert d.opportunity_id == "g2:ua_stop_loss"
    assert plan.template.execution_action == ExecutionAction.PAUSE_CAMPAIGN


def test_plan_uses_request_expected_change_as_reason_fallback():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.network_cleanup",
        target="g", expected_change="custom reason",
        parameters={"network": "n"}))
    # 模板有 reason，故用模板 reason
    assert plan.decision.reason == "低 eCPM 网络拖累整体变现，关停以回收填充"
    # 不带参数的版本同样能构造
    plan2 = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.campaign_pause", target="g2"))
    assert plan2.decision.reason


def test_provider_params_remap_network():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.network_cleanup",
        target="g", parameters={"network": "NET123", "ad_unit_id": "au_9"}))
    assert plan.provider_params["network"] == "NET123"
    assert plan.provider_params["ad_unit_id"] == "au_9"


def test_provider_params_remap_campaign():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.campaign_pause",
        target="g", parameters={"campaign_id": "CAMP_X"}))
    assert plan.provider_params["campaign_id"] == "CAMP_X"


def test_expected_value_override_from_params():
    p = AdaptiveStrategyPlanner()
    plan = p.plan(AdaptiveStrategyRequest(
        proposal_id="p", strategy_id="adaptive.network_cleanup",
        target="g", parameters={"network": "n", "expected_value": 0.42}))
    assert plan.expected_value == 0.42
    assert plan.decision.expected_value == 0.42


def test_unknown_strategy_raises():
    p = AdaptiveStrategyPlanner()
    with pytest.raises(UnknownStrategyError):
        p.plan(AdaptiveStrategyRequest(
            proposal_id="p", strategy_id="adaptive.does_not_exist",
            target="g"))


def test_budget_scale_absent_and_blocked():
    p = AdaptiveStrategyPlanner()
    with pytest.raises(UnknownStrategyError):
        p.get_template("adaptive.budget_scale")
    with pytest.raises(UnknownStrategyError):
        p.plan(AdaptiveStrategyRequest(
            proposal_id="p", strategy_id="adaptive.budget_scale", target="g"))


def test_known_strategies_excludes_unsupported():
    tpl = AdaptiveStrategyTemplate(
        strategy_id="adaptive.budget_scale", display_name="扩量",
        adaptive_action=AdaptiveAction.BUDGET_SCALE,
        decision_action="UA_SCALE", opportunity_type="ua_scale",
        execution_action=ExecutionAction.SCALE_BUDGET, supported=False,
    )
    p = AdaptiveStrategyPlanner(templates={"adaptive.budget_scale": tpl})
    assert "adaptive.budget_scale" not in p.known_strategies()
    # get_template 对 unsupported 也抛
    with pytest.raises(UnknownStrategyError):
        p.get_template("adaptive.budget_scale")


def test_get_template_returns_supported():
    p = AdaptiveStrategyPlanner()
    tpl = p.get_template("adaptive.network_cleanup")
    assert tpl.supported is True
    assert tpl.strategy_id == "adaptive.network_cleanup"
