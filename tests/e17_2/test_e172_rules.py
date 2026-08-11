"""E17.2 规则引擎测试（Test1-Test4 + 负向）。

直接构造 GameSignals 喂规则，验证「信号 → 机会类型」映射。
"""
from src.ceo_intelligence.opportunity_engine.models import GameSignals
from src.ceo_intelligence.opportunity_engine.rules import evaluate
from src.ceo_intelligence.opportunity_engine.models import OpportunityType


def _types(sig):
    return [o.type for o in evaluate(sig, game_id="g")]


# Test1 — 收入下降 → REVENUE_RECOVERY
def test_revenue_decline():
    sig = GameSignals(revenue_growth=-0.30, revenue=1000.0, coverage=1)
    assert _types(sig) == [OpportunityType.REVENUE_RECOVERY]


# Test2 — Creative 疲劳（CTR↓ + frequency↑ + fatigue 高）→ CREATIVE_REFRESH
def test_creative_fatigue():
    sig = GameSignals(ctr_growth=-0.25, frequency_growth=0.5, fatigue_score=0.85)
    assert _types(sig) == [OpportunityType.CREATIVE_REFRESH]


# Test3 — UA 扩量（ROAS 高 + 预算小）→ UA_SCALE
def test_ua_scale():
    sig = GameSignals(roas=1.8, budget_level=0.2)
    assert _types(sig) == [OpportunityType.UA_SCALE]


# Test4 — ASO 优化（CVR↓ + 评分高）→ ASO_OPTIMIZATION
def test_aso_optimization():
    sig = GameSignals(store_cvr_growth=-0.20, rating=4.5)
    assert _types(sig) == [OpportunityType.ASO_OPTIMIZATION]


# Test5（规则负向）— 健康信号不应误报
def test_no_false_positive_on_healthy():
    sig = GameSignals(revenue_growth=0.05, roas=1.6, budget_level=0.8,
                      ctr_growth=0.02, store_cvr_growth=0.01, rating=3.0)
    assert _types(sig) == []


# Test6（规则叠加）— 收入下降 + ASO 下降 同时触发两类
def test_multiple_rules_fire():
    sig = GameSignals(revenue_growth=-0.25, revenue=500,
                      store_cvr_growth=-0.20, rating=4.6, coverage=2)
    types = set(_types(sig))
    assert OpportunityType.REVENUE_RECOVERY in types
    assert OpportunityType.ASO_OPTIMIZATION in types
