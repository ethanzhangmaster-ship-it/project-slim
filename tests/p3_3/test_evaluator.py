"""P3.3 — OutcomeEvaluator 测试（零重算，只归并）。"""
from __future__ import annotations

from types import SimpleNamespace

from src.operator.strategy.evaluator import OutcomeEvaluator, evaluate
from src.operator.strategy.models import BusinessOutcome


class _Action:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_business_positive_success():
    a = _Action(action="DISABLE_NETWORK", game_id="g1")
    bo = BusinessOutcome("ecpm", 2.1, 4.8)
    fb = evaluate(a, business_outcome=bo)
    assert fb.outcome == "SUCCESS"
    assert fb.reward > 0
    assert fb.strategy_id == "unknown_strategy"  # 未给 strategy_id


def test_business_negative_failure():
    a = _Action(action="X", game_id="g2")
    bo = BusinessOutcome("ecpm", 4.8, 2.1)
    fb = evaluate(a, business_outcome=bo)
    assert fb.outcome == "FAILURE"
    assert fb.reward < 0


def test_execution_ok_success():
    a = _Action(action="X", game_id="g")
    ex = SimpleNamespace(ok=True, verdict="executed")
    fb = evaluate(a, execution_result=ex)
    assert fb.outcome == "SUCCESS" and fb.reward == 1.0


def test_no_execution_neutral():
    a = _Action(action="X", game_id="g")
    fb = evaluate(a)
    assert fb.outcome == "NEUTRAL" and fb.reward == 0.0


def test_blocked_execution_treated_protected():
    a = _Action(action="X", game_id="g")
    # ok 缺省 + verdict 含 "block" → 视为保护生效，非策略失败
    ex = SimpleNamespace(verdict="blocked")
    fb = evaluate(a, execution_result=ex)
    assert fb.outcome == "SUCCESS"


def test_strategy_id_resolution_priority():
    a = _Action(action="X", game_id="g", opportunity_type="monetization",
                strategy_id="legacy_id")
    fb = evaluate(a, strategy_id="explicit")
    assert fb.strategy_id == "explicit"
    fb2 = evaluate(a)
    assert fb2.strategy_id == "legacy_id"
    fb3 = evaluate(_Action(action="X", game_id="g", opportunity_type="monetization"))
    assert fb3.strategy_id == "monetization"


def test_action_id_resolution():
    a = _Action(action="DISABLE_NETWORK", game_id="g1", action_id="aid-1")
    fb = evaluate(a)
    assert fb.action_id == "aid-1"
    fb2 = evaluate(_Action(action="ACT", game_id="g9"))
    assert fb2.action_id == "g9:ACT"


def test_evidence_business_format():
    a = _Action(action="X", game_id="g")
    bo = BusinessOutcome("ecpm", 2.1, 4.8)
    fb = evaluate(a, business_outcome=bo)
    assert "2.1" in fb.evidence and "4.8" in fb.evidence


def test_evidence_execution_format():
    a = _Action(action="X", game_id="g")
    ex = SimpleNamespace(ok=True, verdict="executed")
    fb = evaluate(a, execution_result=ex)
    assert "execution ok" in fb.evidence
    ex2 = SimpleNamespace(ok=False, verdict="failed")
    fb2 = evaluate(a, execution_result=ex2)
    assert "failed" in fb2.evidence


def test_reward_clamped():
    a = _Action(action="X", game_id="g")
    bo = BusinessOutcome("ecpm", 1.0, 100.0)  # ratio 99
    fb = evaluate(a, business_outcome=bo)
    assert fb.reward <= 1.0


def test_evaluator_class_wrapper():
    a = _Action(action="X", game_id="g")
    bo = BusinessOutcome("ecpm", 2.0, 3.0)
    fb1 = OutcomeEvaluator().evaluate(a, business_outcome=bo)
    fb2 = evaluate(a, business_outcome=bo)
    assert fb1.outcome == fb2.outcome and fb1.reward == fb2.reward
