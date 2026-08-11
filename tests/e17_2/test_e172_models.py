"""E17.2 模型层测试：枚举 / 机会对象 / 报告序列化 + 中文视图。"""
from src.ceo_intelligence.opportunity_engine.models import (
    GrowthOpportunity,
    OpportunityReport,
    OpportunityType,
    PortfolioOpportunity,
)


def test_opportunity_type_values():
    assert OpportunityType.REVENUE_RECOVERY.value == "revenue_recovery"
    assert OpportunityType.UA_SCALE.value == "ua_scale"
    assert OpportunityType.UA_STOP_LOSS.value == "ua_stop_loss"
    assert OpportunityType.CREATIVE_REFRESH.value == "creative_refresh"
    assert OpportunityType.ASO_OPTIMIZATION.value == "aso_optimization"
    assert OpportunityType.MONETIZATION.value == "monetization"
    assert OpportunityType.RETENTION.value == "retention"
    assert OpportunityType.RELEASE_HEALTH.value == "release_health"


def test_growth_opportunity_roundtrip():
    o = GrowthOpportunity(
        game_id="g1",
        type=OpportunityType.CREATIVE_REFRESH,
        title="素材刷新",
        problem="CTR 下降",
        evidence=["ctr -25%"],
        expected_impact=0.2,
        confidence=0.85,
        urgency=0.6,
        risk=0.3,
        suggested_actions=["生成素材"],
        priority=0.42,
        segment="US",
    )
    d = o.to_dict()
    assert d["type"] == "creative_refresh"
    back = GrowthOpportunity.from_dict(d)
    assert back == o
    assert back.type == OpportunityType.CREATIVE_REFRESH


def test_report_roundtrip_and_markdown():
    o = GrowthOpportunity(
        game_id="g1",
        type=OpportunityType.REVENUE_RECOVERY,
        title="收入下滑修复",
        problem="日收入环比 -30%",
        expected_impact=0.3,
        confidence=0.9,
        urgency=0.9,
        risk=0.4,
        priority=0.6,
    )
    p = PortfolioOpportunity(game_id="g1", top_problem="收入下滑", priority=0.6, type="revenue_recovery")
    rep = OpportunityReport(
        total_opportunities=1,
        top_priority=[o],
        portfolio_ranking=[p],
        risk_summary={"high": 0, "medium": 1, "low": 0, "total_expected_impact": 0.3},
    )
    d = rep.to_dict()
    back = OpportunityReport.from_dict(d)
    assert back.total_opportunities == 1
    assert back.top_priority[0].game_id == "g1"
    md = rep.to_markdown()
    assert "增长机会报告" in md
    assert "g1" in md
