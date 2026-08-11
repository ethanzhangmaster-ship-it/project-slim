"""E17.1 归一化层测试：五域解析 + 派生 arpdau / roas。"""
from src.growth_reality.normalizer import RealityNormalizer


def test_normalize_full_domains_sets_confidence_one():
    raw = {
        "game_id": "g",
        "as_of": "2026-07-29",
        "sources": ["demo_sim"],
        "domains": {
            "revenue": {"daily_revenue": 1000.0, "payer_count": 50, "ltv": 8.0},
            "acquisition": {"spend": 300.0, "installs": 100, "cpi": 3.0},
            "aso": {"ranking": 5, "store_cvr": 0.03, "rating": 4.2, "review_velocity": 7},
            "creative": {"ctr": 0.02, "fatigue_score": 0.4, "creative_score": 75},
            "product": {"dau": 2000, "retention": 0.25, "conversion": 0.02},
        },
    }
    snap = RealityNormalizer().normalize_game("g", "2026-07-29", raw)
    assert snap.domain_coverage() == 5
    assert snap.confidence == 1.0
    assert snap.revenue.daily_revenue == 1000.0
    assert snap.product.dau == 2000


def test_derived_arpdau_from_dau():
    raw = {
        "domains": {
            "revenue": {"daily_revenue": 1000.0, "payer_count": 10},
            "product": {"dau": 2000, "retention": 0.2, "conversion": 0.01},
        }
    }
    snap = RealityNormalizer().normalize_game("g", "t", raw)
    assert snap.revenue.arpdau == 1000.0 / 2000.0  # 0.5


def test_derived_roas_from_spend():
    # P1.4：ROAS 仅在收入与花费均来自真实源（real_domains 含二者）时计算
    raw = {
        "real_domains": ["revenue", "acquisition"],
        "domains": {
            "revenue": {"daily_revenue": 100.0, "payer_count": 1},
            "acquisition": {"spend": 100.0, "installs": 10, "cpi": 10.0},
        },
    }
    snap = RealityNormalizer().normalize_game("g", "t", raw)
    # roas = daily_revenue*30 / spend
    assert abs(snap.acquisition.roas - (100.0 * 30 / 100.0)) < 1e-9
    assert snap.attribution is not None and snap.attribution.is_real is True


def test_roas_gated_when_spend_not_real():
    # P1.4：收入真实但花费非真实（SIM）→ 不臆造 ROAS
    raw = {
        "real_domains": ["revenue"],
        "domains": {
            "revenue": {"daily_revenue": 100.0, "payer_count": 1},
            "acquisition": {"spend": 100.0, "installs": 10, "cpi": 10.0},
        },
    }
    snap = RealityNormalizer().normalize_game("g", "t", raw)
    assert snap.acquisition.roas == 0.0
    assert snap.attribution is None


def test_partial_domains_low_confidence():
    raw = {"domains": {"product": {"dau": 500}}}
    snap = RealityNormalizer().normalize_game("g", "t", raw)
    assert snap.domain_coverage() == 1
    assert snap.confidence == 0.2
    assert snap.product.dau == 500
    assert snap.revenue is None
