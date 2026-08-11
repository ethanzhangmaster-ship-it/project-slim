"""E16.1.2 Revenue Forecasting tests."""
from src.revenue_intelligence.forecasting import (
    RevenueForecast,
    RevenueForecaster,
)
from src.revenue_intelligence.models import RevenueSnapshot


def snap(date, revenue, spend=100.0, dau=1000, **kw):
    return RevenueSnapshot(
        game_id="p04",
        date=date,
        revenue_total=revenue,
        spend=spend,
        dau=dau,
        **kw,
    )


def linear_history():
    return [
        snap("2026-07-21", 100.0),
        snap("2026-07-22", 110.0),
        snap("2026-07-23", 120.0),
        snap("2026-07-24", 130.0),
    ]


class TestForecastProjection:
    def test_linear_trend_up(self):
        fc = RevenueForecaster().forecast(linear_history())
        assert fc.trend == "up"
        assert fc.trend_slope_pct > 1.0
        # slope=10/day, intercept=100 → next day = 140
        assert abs(fc.daily_run_rate - 140.0) < 1e-6

    def test_7d_and_30d_sums(self):
        fc = RevenueForecaster().forecast(linear_history())
        # sum_{i=4..10} (100 + 10 i) = 700 + 10 * 49 = 1190
        assert abs(fc.next_7d_revenue - 1190.0) < 1e-6
        assert fc.next_30d_revenue > fc.next_7d_revenue

    def test_declining_projection_floors_at_zero(self):
        hist = [
            snap("d1", 60.0),
            snap("d2", 40.0),
            snap("d3", 20.0),
            snap("d4", 0.0),
        ]
        fc = RevenueForecaster().forecast(hist)
        assert fc.trend == "down"
        assert fc.next_30d_revenue >= 0.0
        assert "revenue_decline" in fc.risk_flags

    def test_single_point_run_rate(self):
        fc = RevenueForecaster().forecast([snap("d1", 200.0)])
        assert abs(fc.daily_run_rate - 200.0) < 1e-6
        assert abs(fc.next_7d_revenue - 1400.0) < 1e-6
        assert "insufficient_history" in fc.risk_flags
        assert fc.confidence <= 0.4


class TestRisksAndConfidence:
    def test_version_fatigue_detected(self):
        hist = [
            snap("d1", 200.0, spend=100.0),
            snap("d2", 180.0, spend=100.0),
            snap("d3", 160.0, spend=102.0),
            snap("d4", 140.0, spend=98.0),
        ]
        fc = RevenueForecaster().forecast(hist)
        assert "version_fatigue" in fc.risk_flags

    def test_no_fatigue_when_spend_was_cut(self):
        hist = [
            snap("d1", 200.0, spend=100.0),
            snap("d2", 180.0, spend=60.0),
            snap("d3", 160.0, spend=40.0),
            snap("d4", 140.0, spend=20.0),
        ]
        fc = RevenueForecaster().forecast(hist)
        assert "version_fatigue" not in fc.risk_flags

    def test_high_volatility_flag(self):
        hist = [
            snap("d1", 10.0),
            snap("d2", 500.0),
            snap("d3", 20.0),
            snap("d4", 480.0),
        ]
        fc = RevenueForecaster().forecast(hist)
        assert "high_volatility" in fc.risk_flags

    def test_more_history_more_confidence(self):
        short = RevenueForecaster().forecast(linear_history()[:3])
        long_hist = linear_history() + [
            snap("2026-07-25", 140.0),
            snap("2026-07-26", 150.0),
            snap("2026-07-27", 160.0),
            snap("2026-07-28", 170.0),
        ]
        long = RevenueForecaster().forecast(long_hist)
        assert long.confidence > short.confidence

    def test_empty_history(self):
        fc = RevenueForecaster().forecast([])
        assert fc.confidence == 0.0
        assert "no_history" in fc.risk_flags


class TestLtvAndSerialization:
    def test_ltv_retention_weighted(self):
        s = snap(
            "d1",
            300.0,
            dau=1000,
            retention_d1=0.4,
            retention_d7=0.2,
            retention_d30=0.1,
        )
        fc = RevenueForecaster().forecast([s])
        # arpdau 0.3 * (1 + 2.4 + 4.6 + 6.0) = 0.3 * 14 = 4.2
        assert abs(fc.ltv_estimate - 4.2) < 1e-6

    def test_to_dict_and_markdown(self):
        fc = RevenueForecaster().forecast(linear_history())
        d = fc.to_dict()
        assert d["game_id"] == "p04"
        assert d["trend"] == "up"
        md = fc.to_markdown()
        assert "Revenue Forecast" in md
        assert "p04" in md

    def test_deterministic(self):
        a = RevenueForecaster().forecast(linear_history())
        b = RevenueForecaster().forecast(linear_history())
        assert a.to_dict() == b.to_dict()
