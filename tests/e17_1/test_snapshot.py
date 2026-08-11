"""E17.1 公司级快照聚合 + 中文视图测试。"""
from src.growth_reality.models import (
    AcquisitionFact,
    GrowthRealitySnapshot,
    ProductFact,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot


def _full(gid, rev, dau, spend):
    return GrowthRealitySnapshot(
        game_id=gid,
        timestamp="2026-07-29",
        revenue=RevenueFact(daily_revenue=rev, payer_count=1, arpdau=rev / dau, ltv=1),
        acquisition=AcquisitionFact(spend=spend, installs=10, cpi=1, roas=1),
        product=ProductFact(dau=dau, retention=0.2, conversion=0.01),
        confidence=1.0,
    )


def test_company_rollup_totals():
    snaps = [_full("g1", 1000, 2000, 300), _full("g2", 500, 1000, 200)]
    cs = build_company_snapshot(snaps, "2026-07-29")
    assert cs.game_count == 2
    assert cs.total_revenue == 1500.0
    assert cs.total_dau == 3000
    assert cs.total_spend == 500.0
    assert cs.avg_confidence == 1.0
    assert cs.at_risk == []  # 两者都健康


def test_at_risk_flags_low_confidence():
    good = _full("g1", 100, 1000, 10)
    bad = GrowthRealitySnapshot(
        game_id="g2", timestamp="t", product=ProductFact(dau=0), confidence=0.2
    )
    cs = build_company_snapshot([good, bad], "t")
    assert cs.at_risk == ["g2"]


def test_markdown_contains_aggregates():
    snaps = [_full("g1", 1000, 2000, 300)]
    cs = build_company_snapshot(snaps, "2026-07-29")
    md = cs.to_markdown()
    assert "公司增长现实快照" in md
    assert "g1" in md
    assert "$1,000.00" in md
    assert "逐游戏概览" in md
