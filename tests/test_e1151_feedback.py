"""E11.5.1 — Performance Feedback Adapter (IAP) Test.

11 AC covering:
  1.  PerformanceFeedback Schema
  2.  UA Metrics 计算
  3.  IAP Metrics 计算
  4.  Engagement Metrics
  5.  UA Adapter
  6.  IAP Adapter
  7.  Analytics Adapter
  8.  Repository
  9.  Serialization
  10. Invalid Data
  11. Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.market import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
    UAPerformanceAdapter,
    IAPPerformanceAdapter,
    AnalyticsPerformanceAdapter,
    FeedbackRepository,
    MarketError,
    MarketAdapterError,
    InvalidMetricsError,
    RepositoryError,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_valid_ua_data() -> dict:
    return {
        "impressions": 100000,
        "clicks": 50000,
        "installs": 30000,
        "spend": 10000.0,
    }


def _make_valid_iap_data() -> dict:
    return {
        "revenue": 50000.0,
        "iap_revenue": 48000.0,
        "payer_count": 500,
        "purchase_count": 1200,
        "installs": 30000,
        "d7_ltv": 1.2,
        "d30_ltv": 3.5,
        "d90_ltv": 8.0,
    }


def _make_valid_engagement_data() -> dict:
    return {
        "d1_retention": 0.45,
        "d7_retention": 0.35,
        "d30_retention": 0.15,
        "sessions": 12.5,
        "playtime": 42.0,
        "level_progress": 5.3,
    }


def _make_full_feedback(creative_id: str = "creative_001") -> PerformanceFeedback:
    ua = UAPerformanceAdapter().normalize(_make_valid_ua_data())
    iap = IAPPerformanceAdapter().normalize(_make_valid_iap_data())
    eng = AnalyticsPerformanceAdapter().normalize(_make_valid_engagement_data())
    return PerformanceFeedback(
        creative_id=creative_id,
        campaign_id="campaign_001",
        source="facebook",
        period="2026-01-01_to_2026-01-07",
        ua_metrics=ua,
        engagement_metrics=eng,
        monetization_metrics=iap,
    )


# ═══════════════════════════════════════════════════════════
# AC1 — PerformanceFeedback Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_performance_feedback_create():
    """AC1a: PerformanceFeedback creates with all fields."""
    fb = _make_full_feedback()

    assert fb.feedback_id.startswith("fb_")
    assert fb.creative_id == "creative_001"
    assert fb.campaign_id == "campaign_001"
    assert fb.source == "facebook"
    assert fb.period == "2026-01-01_to_2026-01-07"
    assert fb.is_complete is True


def test_ac1b_feedback_has_ua_data():
    """AC1b: has_ua_data checks UA metrics presence."""
    fb = PerformanceFeedback(creative_id="c1")
    assert fb.has_ua_data is False

    fb.ua_metrics = UAMetrics()
    assert fb.has_ua_data is True


def test_ac1c_feedback_has_engagement_data():
    """AC1c: has_engagement_data checks engagement metrics."""
    fb = PerformanceFeedback(creative_id="c1")
    assert fb.has_engagement_data is False

    fb.engagement_metrics = EngagementMetrics()
    assert fb.has_engagement_data is True


def test_ac1d_feedback_has_monetization_data():
    """AC1d: has_monetization_data checks IAP metrics."""
    fb = PerformanceFeedback(creative_id="c1")
    assert fb.has_monetization_data is False

    fb.monetization_metrics = IAPMetrics()
    assert fb.has_monetization_data is True


def test_ac1e_feedback_is_complete():
    """AC1e: is_complete=True only when all 3 metrics present."""
    fb = PerformanceFeedback(creative_id="c1")
    assert fb.is_complete is False

    fb.ua_metrics = UAMetrics()
    assert fb.is_complete is False

    fb.engagement_metrics = EngagementMetrics()
    assert fb.is_complete is False

    fb.monetization_metrics = IAPMetrics()
    assert fb.is_complete is True


# ═══════════════════════════════════════════════════════════
# AC2 — UA Metrics 计算
# ═══════════════════════════════════════════════════════════

def test_ac2_ua_metrics_ctr():
    """AC2a: CTR = clicks / impressions."""
    ua = UAMetrics(impressions=100000, clicks=50000)
    assert ua.ctr == 0.5


def test_ac2b_ua_metrics_cpi():
    """AC2b: CPI = spend / installs."""
    ua = UAMetrics(installs=30000, spend=10000.0)
    assert ua.cpi == pytest.approx(0.3333, rel=1e-3)


def test_ac2c_ua_metrics_install_cvr():
    """AC2c: Install CVR = installs / clicks."""
    ua = UAMetrics(clicks=50000, installs=30000)
    assert ua.install_cvr == 0.6


def test_ac2d_ua_metrics_cpm():
    """AC2d: CPM = (spend / impressions) * 1000."""
    ua = UAMetrics(impressions=100000, spend=10000.0)
    assert ua.cpm == 100.0


def test_ac2e_ua_metrics_zero_division():
    """AC2e: Zero division returns 0.0."""
    ua = UAMetrics()
    assert ua.ctr == 0.0
    assert ua.cpi == 0.0
    assert ua.install_cvr == 0.0
    assert ua.cpm == 0.0


# ═══════════════════════════════════════════════════════════
# AC3 — IAP Metrics 计算
# ═══════════════════════════════════════════════════════════

def test_ac3_iap_metrics_pay_rate():
    """AC3a: Pay rate = payer_count / installs."""
    iap = IAPMetrics(revenue=50000, payer_count=500, installs=30000)
    assert iap.pay_rate == pytest.approx(0.0167, rel=1e-3)


def test_ac3b_iap_metrics_arpu():
    """AC3b: ARPU = revenue / installs."""
    iap = IAPMetrics(revenue=50000, installs=30000)
    assert iap.arpu == pytest.approx(1.6667, rel=1e-3)


def test_ac3c_iap_metrics_arppu():
    """AC3c: ARPPU = revenue / payer_count."""
    iap = IAPMetrics(revenue=50000, payer_count=500)
    assert iap.arppu == 100.0


def test_ac3d_iap_metrics_avg_purchase_value():
    """AC3d: Avg purchase = revenue / purchase_count."""
    iap = IAPMetrics(revenue=50000, purchase_count=1000)
    assert iap.avg_purchase_value == 50.0


def test_ac3e_iap_metrics_zero_division():
    """AC3e: Zero division returns 0.0."""
    iap = IAPMetrics()
    assert iap.pay_rate == 0.0
    assert iap.arpu == 0.0
    assert iap.arppu == 0.0
    assert iap.avg_purchase_value == 0.0


# ═══════════════════════════════════════════════════════════
# AC4 — Engagement Metrics
# ═══════════════════════════════════════════════════════════

def test_ac4_engagement_metrics_create():
    """AC4a: EngagementMetrics creates with all fields."""
    eng = EngagementMetrics(
        d1_retention=0.45,
        d7_retention=0.35,
        d30_retention=0.15,
        sessions=12.5,
        playtime=42.0,
        level_progress=5.3,
    )

    assert eng.d1_retention == 0.45
    assert eng.d7_retention == 0.35
    assert eng.d30_retention == 0.15
    assert eng.sessions == 12.5
    assert eng.playtime == 42.0
    assert eng.level_progress == 5.3


def test_ac4b_engagement_metrics_defaults():
    """AC4b: Defaults are all 0.0."""
    eng = EngagementMetrics()
    assert eng.d1_retention == 0.0
    assert eng.d7_retention == 0.0
    assert eng.d30_retention == 0.0
    assert eng.sessions == 0.0
    assert eng.playtime == 0.0
    assert eng.level_progress == 0.0


# ═══════════════════════════════════════════════════════════
# AC5 — UA Adapter
# ═══════════════════════════════════════════════════════════

def test_ac5_ua_adapter_normalize():
    """AC5a: UA Adapter normalizes valid data."""
    adapter = UAPerformanceAdapter()
    metrics = adapter.normalize(_make_valid_ua_data())

    assert metrics.impressions == 100000
    assert metrics.clicks == 50000
    assert metrics.installs == 30000
    assert metrics.spend == 10000.0
    assert metrics.ctr == 0.5
    assert metrics.cpi == pytest.approx(0.3333, rel=1e-3)


def test_ac5b_ua_adapter_validate():
    """AC5b: validate() checks required fields."""
    adapter = UAPerformanceAdapter()
    assert adapter.validate(_make_valid_ua_data()) is True
    assert adapter.validate({"impressions": 100}) is False


def test_ac5c_ua_adapter_missing_fields():
    """AC5c: Missing fields raises MarketAdapterError."""
    adapter = UAPerformanceAdapter()
    with pytest.raises(MarketAdapterError):
        adapter.normalize({"impressions": 100, "clicks": 50})


def test_ac5d_ua_adapter_invalid_logic():
    """AC5d: Invalid logic (clicks > impressions) raises error."""
    adapter = UAPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "impressions": 1000,
            "clicks": 2000,
            "installs": 500,
            "spend": 100.0,
        })


# ═══════════════════════════════════════════════════════════
# AC6 — IAP Adapter
# ═══════════════════════════════════════════════════════════

def test_ac6_iap_adapter_normalize():
    """AC6a: IAP Adapter normalizes valid data."""
    adapter = IAPPerformanceAdapter()
    metrics = adapter.normalize(_make_valid_iap_data())

    assert metrics.revenue == 50000.0
    assert metrics.iap_revenue == 48000.0
    assert metrics.payer_count == 500
    assert metrics.purchase_count == 1200
    assert metrics.installs == 30000
    assert metrics.pay_rate == pytest.approx(0.0167, rel=1e-3)
    assert metrics.arpu == pytest.approx(1.6667, rel=1e-3)
    assert metrics.d7_ltv == 1.2
    assert metrics.d30_ltv == 3.5
    assert metrics.d90_ltv == 8.0


def test_ac6b_iap_adapter_validate():
    """AC6b: validate() checks required fields."""
    adapter = IAPPerformanceAdapter()
    assert adapter.validate(_make_valid_iap_data()) is True
    assert adapter.validate({"revenue": 100}) is False


def test_ac6c_iap_adapter_missing_fields():
    """AC6c: Missing fields raises MarketAdapterError."""
    adapter = IAPPerformanceAdapter()
    with pytest.raises(MarketAdapterError):
        adapter.normalize({"revenue": 100, "payer_count": 5})


def test_ac6d_iap_adapter_invalid_logic():
    """AC6d: payer_count > installs raises error."""
    adapter = IAPPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "revenue": 1000,
            "payer_count": 500,
            "purchase_count": 600,
            "installs": 100,
        })


# ═══════════════════════════════════════════════════════════
# AC7 — Analytics Adapter
# ═══════════════════════════════════════════════════════════

def test_ac7_analytics_adapter_normalize():
    """AC7a: Analytics Adapter normalizes valid data."""
    adapter = AnalyticsPerformanceAdapter()
    metrics = adapter.normalize(_make_valid_engagement_data())

    assert metrics.d1_retention == 0.45
    assert metrics.d7_retention == 0.35
    assert metrics.d30_retention == 0.15
    assert metrics.sessions == 12.5
    assert metrics.playtime == 42.0
    assert metrics.level_progress == 5.3


def test_ac7b_analytics_adapter_validate():
    """AC7b: validate() checks required fields."""
    adapter = AnalyticsPerformanceAdapter()
    assert adapter.validate(_make_valid_engagement_data()) is True
    assert adapter.validate({"d1_retention": 0.45}) is False


def test_ac7c_analytics_adapter_missing_fields():
    """AC7c: Missing fields raises MarketAdapterError."""
    adapter = AnalyticsPerformanceAdapter()
    with pytest.raises(MarketAdapterError):
        adapter.normalize({"d1_retention": 0.45})


def test_ac7d_analytics_adapter_invalid_retention():
    """AC7d: Retention > 1.0 raises error."""
    adapter = AnalyticsPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "d1_retention": 1.5,
            "d7_retention": 0.35,
            "sessions": 10,
        })


# ═══════════════════════════════════════════════════════════
# AC8 — Repository
# ═══════════════════════════════════════════════════════════

def test_ac8_repository_save_and_get():
    """AC8a: save() then get() retrieves feedback."""
    repo = FeedbackRepository()
    fb = _make_full_feedback("creative_001")
    repo.save(fb)

    assert repo.count == 1
    assert repo.get(fb.feedback_id) == fb


def test_ac8b_repository_get_by_creative():
    """AC8b: get_by_creative() filters by creative_id."""
    repo = FeedbackRepository()
    fb1 = _make_full_feedback("creative_001")
    fb2 = _make_full_feedback("creative_002")
    repo.save(fb1)
    repo.save(fb2)

    results = repo.get_by_creative("creative_001")
    assert len(results) == 1
    assert results[0].creative_id == "creative_001"


def test_ac8c_repository_get_by_campaign():
    """AC8c: get_by_campaign() filters by campaign_id."""
    repo = FeedbackRepository()
    fb1 = _make_full_feedback("creative_001")
    fb1.campaign_id = "campaign_A"
    fb2 = _make_full_feedback("creative_002")
    fb2.campaign_id = "campaign_B"
    repo.save(fb1)
    repo.save(fb2)

    results = repo.get_by_campaign("campaign_A")
    assert len(results) == 1


def test_ac8d_repository_get_by_source():
    """AC8d: get_by_source() filters by source."""
    repo = FeedbackRepository()
    fb1 = _make_full_feedback("creative_001")
    fb1.source = "facebook"
    fb2 = _make_full_feedback("creative_002")
    fb2.source = "google"
    repo.save(fb1)
    repo.save(fb2)

    results = repo.get_by_source("facebook")
    assert len(results) == 1


def test_ac8e_repository_get_complete():
    """AC8e: get_complete() returns only complete feedbacks."""
    repo = FeedbackRepository()
    fb1 = _make_full_feedback("creative_001")
    fb2 = PerformanceFeedback(creative_id="creative_002")
    repo.save(fb1)
    repo.save(fb2)

    complete = repo.get_complete()
    assert len(complete) == 1


def test_ac8f_repository_latest():
    """AC8f: latest() returns most recent feedback."""
    from datetime import datetime, timezone, timedelta

    repo = FeedbackRepository()
    fb1 = _make_full_feedback("creative_001")
    fb1.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    fb2 = _make_full_feedback("creative_002")
    repo.save(fb1)
    repo.save(fb2)

    latest = repo.latest()
    assert latest is not None
    assert latest.creative_id == "creative_002"


def test_ac8g_repository_stats():
    """AC8g: creative_count and campaign_count work."""
    repo = FeedbackRepository()
    repo.save(_make_full_feedback("c1"))
    repo.save(_make_full_feedback("c2"))
    repo.save(_make_full_feedback("c1"))  # same creative

    assert repo.count == 3
    assert repo.creative_count == 2


def test_ac8h_repository_delete():
    """AC8h: delete() removes feedback."""
    repo = FeedbackRepository()
    fb = _make_full_feedback()
    repo.save(fb)

    assert repo.delete(fb.feedback_id) is True
    assert repo.count == 0
    assert repo.delete("nonexistent") is False


# ═══════════════════════════════════════════════════════════
# AC9 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac9_ua_metrics_serialization():
    """AC9a: UAMetrics to_dict/from_dict roundtrip."""
    ua = UAMetrics(impressions=100000, clicks=50000, installs=30000, spend=10000.0)
    d = ua.to_dict()
    restored = UAMetrics.from_dict(d)

    assert restored.impressions == ua.impressions
    assert restored.clicks == ua.clicks
    assert restored.installs == ua.installs
    assert restored.spend == ua.spend
    assert restored.ctr == ua.ctr


def test_ac9b_engagement_metrics_serialization():
    """AC9b: EngagementMetrics to_dict/from_dict roundtrip."""
    eng = EngagementMetrics(d1_retention=0.45, d7_retention=0.35, sessions=12.5)
    d = eng.to_dict()
    restored = EngagementMetrics.from_dict(d)

    assert restored.d1_retention == eng.d1_retention
    assert restored.d7_retention == eng.d7_retention
    assert restored.sessions == eng.sessions


def test_ac9c_iap_metrics_serialization():
    """AC9c: IAPMetrics to_dict/from_dict roundtrip."""
    iap = IAPMetrics(revenue=50000, payer_count=500, purchase_count=1200, installs=30000)
    d = iap.to_dict()
    restored = IAPMetrics.from_dict(d)

    assert restored.revenue == iap.revenue
    assert restored.payer_count == iap.payer_count
    assert restored.pay_rate == iap.pay_rate
    assert restored.arppu == iap.arppu


def test_ac9d_performance_feedback_serialization():
    """AC9d: PerformanceFeedback to_dict/from_dict roundtrip."""
    fb = _make_full_feedback()
    d = fb.to_dict()
    restored = PerformanceFeedback.from_dict(d)

    assert restored.feedback_id == fb.feedback_id
    assert restored.creative_id == fb.creative_id
    assert restored.source == fb.source
    assert restored.is_complete == fb.is_complete


def test_ac9e_repository_serialization():
    """AC9e: FeedbackRepository to_dict/from_dict roundtrip."""
    repo = FeedbackRepository()
    repo.save(_make_full_feedback("c1"))
    repo.save(_make_full_feedback("c2"))

    d = repo.to_dict()
    restored = FeedbackRepository.from_dict(d)

    assert restored.count == 2
    assert restored.creative_count == 2


# ═══════════════════════════════════════════════════════════
# AC10 — Invalid Data
# ═══════════════════════════════════════════════════════════

def test_ac10_ua_adapter_negative_values():
    """AC10a: Negative values in UA data raise error."""
    adapter = UAPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "impressions": -100,
            "clicks": 50,
            "installs": 30,
            "spend": 10.0,
        })


def test_ac10b_iap_adapter_negative_values():
    """AC10b: Negative values in IAP data raise error."""
    adapter = IAPPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "revenue": -100,
            "payer_count": 5,
            "purchase_count": 10,
            "installs": 100,
        })


def test_ac10c_analytics_adapter_negative_retention():
    """AC10c: Negative retention raises error."""
    adapter = AnalyticsPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "d1_retention": -0.1,
            "d7_retention": 0.35,
            "sessions": 10,
        })


def test_ac10d_ua_adapter_installs_gt_clicks():
    """AC10d: installs > clicks raises error."""
    adapter = UAPerformanceAdapter()
    with pytest.raises(InvalidMetricsError):
        adapter.normalize({
            "impressions": 1000,
            "clicks": 500,
            "installs": 600,
            "spend": 100.0,
        })


# ═══════════════════════════════════════════════════════════
# AC11 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac11_deterministic_ua_adapter():
    """AC11a: Same input → same UAMetrics."""
    data = _make_valid_ua_data()
    adapter = UAPerformanceAdapter()

    r1 = adapter.normalize(data)
    r2 = adapter.normalize(data)

    assert r1.ctr == r2.ctr
    assert r1.cpi == r2.cpi
    assert r1.install_cvr == r2.install_cvr


def test_ac11b_deterministic_iap_adapter():
    """AC11b: Same input → same IAPMetrics."""
    data = _make_valid_iap_data()
    adapter = IAPPerformanceAdapter()

    r1 = adapter.normalize(data)
    r2 = adapter.normalize(data)

    assert r1.pay_rate == r2.pay_rate
    assert r1.arpu == r2.arpu
    assert r1.arppu == r2.arppu


def test_ac11c_deterministic_metrics_calculation():
    """AC11c: Metrics calculations are deterministic."""
    ua1 = UAMetrics(impressions=100000, clicks=50000, installs=30000, spend=10000.0)
    ua2 = UAMetrics(impressions=100000, clicks=50000, installs=30000, spend=10000.0)

    assert ua1.ctr == ua2.ctr
    assert ua1.cpi == ua2.cpi
    assert ua1.install_cvr == ua2.install_cvr
    assert ua1.cpm == ua2.cpm