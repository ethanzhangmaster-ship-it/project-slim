"""E17.1 模型层测试：Fact / Snapshot 序列化 + 置信度分级。"""
from src.growth_reality.models import (
    AcquisitionFact,
    AsoFact,
    ConfidenceLevel,
    CreativeFact,
    GrowthRealitySnapshot,
    ProductFact,
    RevenueFact,
)


def test_revenue_fact_roundtrip():
    f = RevenueFact(daily_revenue=123.45, payer_count=10, arpdau=1.2, ltv=5.0)
    d = f.to_dict()
    assert d == {
        "daily_revenue": 123.45, "payer_count": 10, "arpdau": 1.2, "ltv": 5.0,
        # P1.2 扩展的 MAX / IAA 原生变现指标（缺省为 0 / 空）
        "impressions": 0, "requests": 0, "ecpm": 0.0,
        "rewarded_video_revenue": 0.0, "network_distribution": {},
    }
    assert RevenueFact.from_dict(d) == f


def test_snapshot_roundtrip_full():
    snap = GrowthRealitySnapshot(
        game_id="g1",
        timestamp="2026-07-29",
        revenue=RevenueFact(daily_revenue=100, payer_count=5, arpdau=0, ltv=2),
        acquisition=AcquisitionFact(spend=50, installs=20, cpi=2.5, roas=0),
        aso=AsoFact(ranking=3, store_cvr=0.02, rating=4.1, review_velocity=5),
        creative=CreativeFact(ctr=0.01, fatigue_score=0.3, creative_score=80),
        product=ProductFact(dau=1000, retention=0.2, conversion=0.01),
        confidence=1.0,
        sources=["demo_sim"],
    )
    d = snap.to_dict()
    back = GrowthRealitySnapshot.from_dict(d)
    assert back == snap
    assert back.revenue.daily_revenue == 100
    assert back.product.dau == 1000


def test_snapshot_partial_domains():
    snap = GrowthRealitySnapshot(game_id="g2", timestamp="t", product=ProductFact(dau=42))
    assert snap.domain_coverage() == 1
    assert snap.covered_domains() == ["product"]
    assert snap.confidence == 0.0  # 未归一化时 confidence 缺省 0


def test_confidence_level_brackets():
    assert ConfidenceLevel.from_score(0.9) == ConfidenceLevel.HIGH
    assert ConfidenceLevel.from_score(0.5) == ConfidenceLevel.MEDIUM
    assert ConfidenceLevel.from_score(0.1) == ConfidenceLevel.LOW
    snap = GrowthRealitySnapshot(game_id="g", timestamp="t")
    snap.confidence = 0.8
    assert snap.confidence_level == ConfidenceLevel.HIGH
