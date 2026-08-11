"""E16.1.4 Portfolio Intelligence tests."""
from src.revenue_intelligence.portfolio import (
    GamePortfolioEntry,
    PortfolioIntelligence,
    PortfolioVerdict,
)


def entry(game_id, revenue, profit, roas, dau, trend="flat", genre=None):
    return GamePortfolioEntry(
        game_id=game_id,
        revenue=revenue,
        profit=profit,
        roas=roas,
        dau=dau,
        trend=trend,
        genre=genre,
    )


def fleet():
    return [
        entry("winner", 20000.0, 5000.0, 1.8, 10000, trend="up", genre="puzzle"),
        entry("scaler", 8000.0, 2000.0, 1.5, 6000, trend="up", genre="puzzle"),
        entry("stable", 3000.0, 500.0, 1.1, 3000, trend="flat"),
        entry("bleeder", 2000.0, -300.0, 0.8, 4000, trend="down"),
        entry("zombie", 50.0, -20.0, 0.5, 80, trend="down"),
    ]


class TestVerdicts:
    def test_fleet_verdicts(self):
        report = PortfolioIntelligence().evaluate(fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        assert v["winner"] == PortfolioVerdict.REPLICATE
        assert v["scaler"] == PortfolioVerdict.SCALE
        assert v["stable"] == PortfolioVerdict.MAINTAIN
        assert v["bleeder"] == PortfolioVerdict.REDUCE
        assert v["zombie"] == PortfolioVerdict.SUNSET

    def test_replicate_targets_same_genre(self):
        report = PortfolioIntelligence().evaluate(fleet())
        top = report.decisions[0]
        assert top.verdict == PortfolioVerdict.REPLICATE
        assert top.replicate_targets == ["scaler"]

    def test_ranked_by_score_descending(self):
        report = PortfolioIntelligence().evaluate(fleet())
        scores = [d.score for d in report.decisions]
        assert scores == sorted(scores, reverse=True)
        assert report.decisions[0].game_id == "winner"

    def test_no_replicate_when_top_is_weak(self):
        weak = [
            entry("a", 100.0, 10.0, 1.05, 100, trend="flat"),
            entry("b", 90.0, -5.0, 0.9, 90, trend="down"),
        ]
        report = PortfolioIntelligence().evaluate(weak)
        verdicts = [d.verdict for d in report.decisions]
        assert PortfolioVerdict.REPLICATE not in verdicts

    def test_sunset_requires_low_volume(self):
        # unprofitable but high volume → REDUCE, not SUNSET
        e = [entry("big_loser", 5000.0, -1000.0, 0.7, 50000, trend="down")]
        report = PortfolioIntelligence().evaluate(e)
        assert report.decisions[0].verdict == PortfolioVerdict.REDUCE


class TestReport:
    def test_totals(self):
        report = PortfolioIntelligence().evaluate(fleet())
        assert report.fleet_size == 5
        assert abs(report.total_revenue - 33050.0) < 1e-6
        assert abs(report.total_profit - 7180.0) < 1e-6

    def test_by_verdict_filter(self):
        report = PortfolioIntelligence().evaluate(fleet())
        assert len(report.by_verdict(PortfolioVerdict.SUNSET)) == 1

    def test_to_dict_and_markdown(self):
        report = PortfolioIntelligence().evaluate(fleet())
        d = report.to_dict()
        assert d["fleet_size"] == 5
        md = report.to_markdown()
        assert "Portfolio Report" in md
        assert "REPLICATE" in md

    def test_empty_fleet(self):
        report = PortfolioIntelligence().evaluate([])
        assert report.fleet_size == 0
        assert report.decisions == []

    def test_deterministic(self):
        a = PortfolioIntelligence().evaluate(fleet())
        b = PortfolioIntelligence().evaluate(fleet())
        assert a.to_dict() == b.to_dict()


class TestOrganicMode:
    """Organic titles (no UA spend, roas == 0) must not be judged by ROAS.

    Discovered on the real fleet 2026-07-28: all 15 earning titles are
    organic, and ROAS-based rules verdicted the $706 fleet winner as REDUCE.
    """

    def organic_fleet(self):
        return [
            entry("hero", 700.0, 700.0, 0.0, 6000, trend="flat", genre="merge"),
            entry("mid", 190.0, 190.0, 0.0, 3000, trend="down", genre="quiz"),
            entry("small_up", 35.0, 35.0, 0.0, 500, trend="up"),
            entry("dust", 2.0, 2.0, 0.0, 50, trend="down"),
        ]

    def test_organic_winner_not_reduced(self):
        report = PortfolioIntelligence().evaluate(self.organic_fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        assert v["hero"] in (PortfolioVerdict.SCALE, PortfolioVerdict.REPLICATE)

    def test_organic_dominant_winner_becomes_replicate(self):
        report = PortfolioIntelligence().evaluate(self.organic_fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        # hero holds >50% of fleet revenue and is not declining
        assert v["hero"] == PortfolioVerdict.REPLICATE

    def test_organic_dust_sunset(self):
        report = PortfolioIntelligence().evaluate(self.organic_fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        assert v["dust"] == PortfolioVerdict.SUNSET

    def test_organic_marginal_maintained_not_reduced(self):
        report = PortfolioIntelligence().evaluate(self.organic_fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        assert v["mid"] == PortfolioVerdict.MAINTAIN
        assert v["small_up"] == PortfolioVerdict.MAINTAIN
        assert PortfolioVerdict.REDUCE not in v.values()

    def test_ua_fleet_unaffected_by_organic_rules(self):
        # original UA-driven fleet still gets identical verdicts
        report = PortfolioIntelligence().evaluate(fleet())
        v = {d.game_id: d.verdict for d in report.decisions}
        assert v["winner"] == PortfolioVerdict.REPLICATE
        assert v["bleeder"] == PortfolioVerdict.REDUCE


class TestAgentWiring:
    def test_agent_thin_delegation(self):
        from src.revenue_intelligence.agent import RevenueIntelligenceAgent
        from src.revenue_intelligence.models import RevenueSnapshot

        agent = RevenueIntelligenceAgent()

        # forecast
        hist = [
            RevenueSnapshot(game_id="p04", date=f"d{i}", revenue_total=100.0 + i * 10)
            for i in range(4)
        ]
        fc = agent.forecast(hist)
        assert fc.trend == "up"

        # profit
        cur = RevenueSnapshot(
            game_id="p04",
            date="d2",
            revenue_total=12000.0,
            iap_revenue=10000.0,
            spend=8000.0,
        )
        pr = agent.profit_report(cur)
        assert abs(pr.current.profit - 1000.0) < 1e-6

        # portfolio
        report = agent.portfolio_report(fleet())
        assert report.fleet_size == 5
