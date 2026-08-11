"""P3.2 — Action Formatter 测试：三态收敛 + WHY 解释（核心）。

Case1 AUTO（低险高置信 -> AUTO EXECUTE）
Case2 APPROVAL（risk=0.6 -> APPROVAL REQUIRED）
Case3 BLOCK（confidence=0.3 + 负期望 -> BLOCKED）
"""
from __future__ import annotations

from src.ceo_intelligence.daily_operator.models import ActionKind, DailyActionItem
from src.ceo_intelligence.decision_engine.models import (
    DecisionType,
    GrowthDecision,
)
from src.ceo_intelligence.simulation_engine.models import (
    DecisionSimulation,
    PreFlightFlag,
    PreFlightStatus,
    SimulationPrior,
)

from src.operator.report.action_formatter import ActionFormatter, format_actions
from src.operator.report.models import ActionState, CEOActionStatus


def _dec(audit_id, action, risk, conf, ev, dtype=DecisionType.EXECUTE):
    return GrowthDecision(
        game_id="g1", opportunity_id="o1", action=action,
        decision_type=dtype, expected_value=ev, confidence=conf, risk=risk,
        reason="测试决策", audit_id=audit_id,
    )


def _sim(audit_id, status=PreFlightStatus.PASS, reason=""):
    return DecisionSimulation(
        game_id="g1", opportunity_id="o1", action="x",
        decision_type="execute", prior=SimulationPrior(opportunity_type="ua_scale"),
        flag=PreFlightFlag(status, reason), decision_audit_id=audit_id,
    )


def _action(kind, audit_id, action="ua_scale", detail="", opp="ua_scale"):
    return DailyActionItem(
        kind=kind, game_id="g1", action=action, detail=detail,
        decision_audit_id=audit_id, opportunity_type=opp,
    )


class TestCase1Auto:
    def test_auto_maps_to_executed(self):
        a = _action(ActionKind.AUTO, "dec1")
        dec = _dec("dec1", "ua_scale", risk=0.1, conf=0.95, ev=0.12)
        sim = _sim("dec1", PreFlightStatus.PASS)
        out = format_actions([a], {"dec1": dec}, {"dec1": sim}, {})
        assert len(out) == 1
        ceo = out[0]
        assert ceo.execution_mode == ActionState.AUTO
        assert ceo.status == CEOActionStatus.EXECUTED
        assert "已自动执行" in ceo.explanation
        assert "12.0%" in ceo.explanation
        assert ceo.action_id == "cea-000"

    def test_auto_source_traceability(self):
        a = _action(ActionKind.AUTO, "dec1")
        dec = _dec("dec1", "ua_scale", 0.1, 0.9, 0.1)
        out = format_actions([a], {"dec1": dec}, {}, {})
        assert out[0].source == "e17.3_decision+e17.8_sim+p2.4_execution"


class TestCase2Approval:
    def test_approval_maps_to_awaiting(self):
        a = _action(ActionKind.APPROVAL, "dec2", action="monetization", opp="monetization")
        dec = _dec("dec2", "monetization", risk=0.6, conf=0.8, ev=0.10,
                   dtype=DecisionType.APPROVE)
        sim = _sim("dec2", PreFlightStatus.REVIEW)
        out = format_actions([a], {"dec2": dec}, {"dec2": sim}, {})
        ceo = out[0]
        assert ceo.execution_mode == ActionState.APPROVAL
        assert ceo.status == CEOActionStatus.AWAITING_APPROVAL
        assert "审批" in ceo.explanation
        assert "60%" in ceo.explanation

    def test_approval_includes_detail(self):
        a = _action(ActionKind.APPROVAL, "dec2", action="monetization",
                    detail="高价值付费改动，需人工复核", opp="monetization")
        dec = _dec("dec2", "monetization", 0.6, 0.8, 0.1, DecisionType.APPROVE)
        out = format_actions([a], {"dec2": dec}, {}, {})
        assert "需人工复核" in out[0].explanation
        assert out[0].source == "e17.3_decision+p2.3_approval"


class TestCase3Block:
    def test_block_maps_to_prevented(self):
        a = _action(ActionKind.BLOCK, "dec3")
        dec = _dec("dec3", "ua_scale", risk=0.9, conf=0.3, ev=-0.2)
        sim = _sim("dec3", PreFlightStatus.BLOCK, reason="负期望，模拟闸门阻断")
        out = format_actions([a], {"dec3": dec}, {"dec3": sim}, {})
        ceo = out[0]
        assert ceo.execution_mode == ActionState.BLOCKED
        assert ceo.status == CEOActionStatus.PREVENTED
        assert "阻断" in ceo.explanation
        assert "负期望" in ceo.explanation
        assert ceo.source == "e17.8_simulation_gate"

    def test_block_falls_back_to_detail_when_no_sim_reason(self):
        a = _action(ActionKind.BLOCK, "dec3", detail="置信不足，闸门拦下")
        dec = _dec("dec3", "ua_scale", 0.9, 0.3, -0.2)
        out = format_actions([a], {"dec3": dec}, {}, {})
        assert "置信不足" in out[0].explanation


class TestOrderingAndEdge:
    def test_empty_actions(self):
        assert format_actions([], {}, {}, {}) == []

    def test_ids_assigned_by_priority_desc(self):
        # 三个行动，优先级由 |EV|*conf 决定：0.2*0.9=0.18, 0.1*0.5=0.05, 0.05*0.3=0.015
        a_hi = _action(ActionKind.AUTO, "d_hi", action="hi")
        a_mid = _action(ActionKind.APPROVAL, "d_mid", action="mid")
        a_lo = _action(ActionKind.BLOCK, "d_lo", action="lo")
        decs = {
            "d_hi": _dec("d_hi", "hi", 0.1, 0.9, 0.2),
            "d_mid": _dec("d_mid", "mid", 0.6, 0.5, 0.1, DecisionType.APPROVE),
            "d_lo": _dec("d_lo", "lo", 0.9, 0.3, 0.05),
        }
        out = format_actions([a_lo, a_mid, a_hi], decs, {}, {})
        # 按优先级降序分配 id
        assert out[0].action_id == "cea-000"
        assert out[0].action_type == "hi"
        assert out[1].action_type == "mid"
        assert out[2].action_type == "lo"

    def test_priority_from_game_priority_when_available(self):
        a = _action(ActionKind.AUTO, "d1")
        dec = _dec("d1", "ua_scale", 0.1, 0.9, 0.1)
        pri = type("P", (), {"priority_score_value": 0.9876})()
        fmt = ActionFormatter(priorities_by_game={"g1": pri})
        out = fmt.format([a])
        assert abs(out[0].priority - 0.9876) < 1e-6

    def test_formatter_class_and_module_equivalent(self):
        a = _action(ActionKind.AUTO, "d1")
        dec = _dec("d1", "ua_scale", 0.1, 0.9, 0.1)
        m = format_actions([a], {"d1": dec}, {}, {})
        c = ActionFormatter({"d1": dec}).format([a])
        assert m[0].to_dict() == c[0].to_dict()
