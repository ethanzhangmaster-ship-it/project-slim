"""E16.1.3 Profit Intelligence tests."""
from src.revenue_intelligence.models import RevenueSnapshot
from src.revenue_intelligence.profit import (
    ProfitEngine,
    ProfitSnapshot,
)


def ps(date, revenue, ua=0.0, fee=0.0, other=0.0):
    return ProfitSnapshot(
        game_id="p04",
        date=date,
        revenue=revenue,
        ua_cost=ua,
        platform_fee=fee,
        other_cost=other,
    )


class TestProfitSnapshot:
    def test_profit_math(self):
        s = ps("d1", 12000.0, ua=8000.0, fee=3000.0, other=500.0)
        assert abs(s.total_cost - 11500.0) < 1e-6
        assert abs(s.profit - 500.0) < 1e-6
        assert abs(s.margin - 500.0 / 12000.0) < 1e-6
        assert abs(s.roi - 500.0 / 11500.0) < 1e-6

    def test_from_revenue_snapshot_fee_on_iap_only(self):
        snap = RevenueSnapshot(
            game_id="p04",
            date="2026-07-27",
            revenue_total=12000.0,
            iap_revenue=10000.0,
            ad_revenue=2000.0,
            spend=8000.0,
        )
        s = ProfitSnapshot.from_revenue_snapshot(snap, platform_fee_rate=0.30)
        assert abs(s.platform_fee - 3000.0) < 1e-6  # 30% of IAP only
        assert abs(s.profit - (12000.0 - 8000.0 - 3000.0)) < 1e-6

    def test_zero_revenue_margin(self):
        s = ps("d1", 0.0, ua=100.0)
        assert s.margin == 0.0
        assert s.profit == -100.0

    def test_roi_none_without_cost(self):
        assert ps("d1", 100.0).roi is None


class TestProfitEngine:
    def test_loss_making_critical(self):
        report = ProfitEngine().analyze(ps("d2", 5000.0, ua=7000.0))
        kinds = [i.kind for i in report.insights]
        assert "loss_making" in kinds
        assert report.insights[0].severity == "critical"

    def test_unprofitable_growth(self):
        prev = ps("d1", 10000.0, ua=5000.0)  # profit 5000
        cur = ps("d2", 12000.0, ua=9000.0)  # profit 3000, revenue +20%
        report = ProfitEngine().analyze(cur, prev)
        kinds = [i.kind for i in report.insights]
        assert "unprofitable_growth" in kinds
        assert "healthy_scaling" not in kinds

    def test_healthy_scaling(self):
        prev = ps("d1", 10000.0, ua=6000.0)  # profit 4000, margin 0.40
        cur = ps("d2", 13000.0, ua=7700.0)  # profit 5300, margin ~0.4077
        report = ProfitEngine().analyze(cur, prev)
        kinds = [i.kind for i in report.insights]
        assert "healthy_scaling" in kinds
        assert "unprofitable_growth" not in kinds

    def test_margin_compression(self):
        prev = ps("d1", 10000.0, ua=6000.0)  # profit 4000, margin 0.400
        cur = ps("d2", 20000.0, ua=13500.0)  # profit 6500, margin 0.325
        report = ProfitEngine().analyze(cur, prev)
        kinds = [i.kind for i in report.insights]
        assert "margin_compression" in kinds
        assert "healthy_scaling" not in kinds  # margin fell too much

    def test_delta_math(self):
        prev = ps("d1", 10000.0, ua=5000.0)
        cur = ps("d2", 12000.0, ua=5500.0)
        report = ProfitEngine().analyze(cur, prev)
        assert abs(report.delta.revenue_pct - 20.0) < 1e-6
        assert abs(report.delta.profit_abs - 1500.0) < 1e-6

    def test_to_dict_and_markdown(self):
        prev = ps("d1", 10000.0, ua=5000.0)
        cur = ps("d2", 12000.0, ua=5500.0)
        report = ProfitEngine().analyze(cur, prev)
        d = report.to_dict()
        assert d["current"]["profit"] == 6500.0
        md = report.to_markdown()
        assert "Profit Report" in md
        assert "p04" in md
