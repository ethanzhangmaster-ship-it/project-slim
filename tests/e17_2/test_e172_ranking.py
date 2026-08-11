"""E17.2 排序测试（Test5）：最高收益（Priority）排第一。"""
from src.ceo_intelligence.opportunity_engine.models import GrowthOpportunity, OpportunityType
from src.ceo_intelligence.opportunity_engine.ranking import rank


def _opp(gid, impact, conf, urg, risk):
    return GrowthOpportunity(
        game_id=gid,
        type=OpportunityType.REVENUE_RECOVERY,
        title=gid,
        problem=gid,
        expected_impact=impact,
        confidence=conf,
        urgency=urg,
        risk=risk,
    )


def test_ranking_by_priority_desc():
    # Priority = Impact*Conf*Urg/Risk
    a = _opp("A", 0.5, 0.8, 0.9, 0.3)   # 0.5*0.8*0.9/0.3 = 1.20
    b = _opp("B", 0.5, 0.3, 0.9, 0.3)   # 0.5*0.3*0.9/0.3 = 0.45
    c = _opp("C", 0.3, 0.9, 0.8, 0.2)   # 0.3*0.9*0.8/0.2 = 1.08
    ranked = rank([b, c, a])  # 乱序输入
    assert [o.game_id for o in ranked] == ["A", "C", "B"]
    assert ranked[0].priority > ranked[1].priority > ranked[2].priority


def test_risk_in_denominator_lowers_priority():
    # 同 impact/conf/urg，风险高者排后
    low_risk = _opp("low", 0.4, 0.8, 0.8, 0.2)
    high_risk = _opp("high", 0.4, 0.8, 0.8, 0.8)
    ranked = rank([high_risk, low_risk])
    assert ranked[0].game_id == "low"
