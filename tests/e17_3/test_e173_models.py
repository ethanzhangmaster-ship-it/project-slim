"""E17.3 模型层测试：枚举映射 / to_dict 往返。"""
from src.ceo_intelligence.decision_engine.models import (
    ActionDomain,
    DecisionType,
    GrowthDecision,
    SimulationResult,
    action_domain,
    action_label,
)


def test_action_domain_mapping():
    assert action_domain("release_health") == ActionDomain.RELEASE
    assert action_domain("monetization") == ActionDomain.PAYMENT
    assert action_domain("ua_scale") == ActionDomain.UA
    assert action_domain("aso_optimization") == ActionDomain.ASO
    assert action_domain("creative_refresh") == ActionDomain.CREATIVE
    assert action_domain("retention") == ActionDomain.PRODUCT


def test_action_label():
    lbl = action_label("creative_refresh", "merge_witch")
    assert "merge_witch" in lbl


def test_decision_roundtrip():
    sim = SimulationResult(0.12, 0.05, 0.8, 0.3)
    d = GrowthDecision(
        game_id="g1",
        opportunity_id="g1:creative_refresh",
        action="刷新创意素材（g1）",
        decision_type=DecisionType.EXECUTE,
        expected_value=0.3,
        confidence=0.9,
        risk=0.3,
        urgency=0.8,
        reason="高置信低风险",
        simulation=sim,
    )
    d2 = GrowthDecision.from_dict(d.to_dict())
    assert d2.game_id == d.game_id
    assert d2.decision_type == d.decision_type
    assert d2.expected_value == d.expected_value
    assert d2.simulation.expected_revenue_change == 0.12
    assert d2.audit_id == d.audit_id  # 往返保持稳定


def test_decision_autofills_audit_id_and_ts():
    d = GrowthDecision(
        game_id="g",
        opportunity_id="g:r",
        action="a",
        decision_type=DecisionType.OBSERVE,
        expected_value=0.1,
        confidence=0.4,
        risk=0.2,
        reason="x",
    )
    assert d.audit_id.startswith("dec_")
    assert d.created_at
