"""E17.3 三道门策略测试（Test2 / Test3 及边界）。"""
from src.ceo_intelligence.decision_engine.models import DecisionType
from src.ceo_intelligence.decision_engine.policy import CompanyDecisionPolicy


def test_gate1_low_confidence_observes():
    """Test2：低置信度 → OBSERVE。"""
    p = CompanyDecisionPolicy()
    dt, reason = p.decide(
        game_id="g", opportunity_type="creative_refresh",
        expected_value=0.3, confidence=0.4, risk=0.2,
    )
    assert dt == DecisionType.OBSERVE
    assert "置信" in reason


def test_gate3_payment_requires_human():
    """Test3：修改核心经济（PAYMENT 域） → APPROVE（人工）。"""
    p = CompanyDecisionPolicy()
    dt, reason = p.decide(
        game_id="g", opportunity_type="monetization",
        expected_value=0.3, confidence=0.95, risk=0.2,
    )
    assert dt == DecisionType.APPROVE
    assert "付费" in reason or "人工" in reason


def test_gate2_high_risk_approve():
    """高风险（>=0.6）无论置信度多高 → APPROVE。"""
    p = CompanyDecisionPolicy()
    dt, _ = p.decide(
        game_id="g", opportunity_type="retention",
        expected_value=0.3, confidence=0.98, risk=0.7,
    )
    assert dt == DecisionType.APPROVE


def test_gate_release_auto_when_safe():
    """RELEASE 域 + 高置信 + 低风险 → EXECUTE。"""
    p = CompanyDecisionPolicy()
    dt, _ = p.decide(
        game_id="g", opportunity_type="release_health",
        expected_value=0.1, confidence=0.95, risk=0.1,
    )
    assert dt == DecisionType.EXECUTE


def test_reject_no_upside():
    """无正向收益预期 → REJECT。"""
    p = CompanyDecisionPolicy()
    dt, _ = p.decide(
        game_id="g", opportunity_type="creative_refresh",
        expected_value=0.0, confidence=0.95, risk=0.2,
    )
    assert dt == DecisionType.REJECT


def test_high_conf_low_risk_ua_executes():
    """UA 域高置信低风险 → EXECUTE。"""
    p = CompanyDecisionPolicy()
    dt, _ = p.decide(
        game_id="g", opportunity_type="ua_scale",
        expected_value=0.2, confidence=0.95, risk=0.3,
    )
    assert dt == DecisionType.EXECUTE
