"""Market reporter module for autonomous research."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class MarketUpdate:
    """A single market update."""
    headline: str
    category: str
    summary: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    impact: str = "neutral"
    related_tickers: List[str] = field(default_factory=list)


@dataclass
class MarketReport:
    """Aggregated market report."""
    report_type: str
    period_start: datetime
    period_end: datetime
    highlights: List[str] = field(default_factory=list)
    updates: List[MarketUpdate] = field(default_factory=list)
    key_metrics: dict = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)


class MarketReporter:
    """Generates market reports and tracks updates."""

    def __init__(self):
        self._updates: List[MarketUpdate] = []
        self._reports: List[MarketReport] = []

    def generate_daily_report(self) -> MarketReport:
        """Generate a daily market report."""
        now = datetime.now()
        report = MarketReport(
            report_type="daily",
            period_start=now.replace(hour=0, minute=0, second=0),
            period_end=now,
            highlights=[
                "Mobile game downloads up 5% week-over-week",
                "Mid-core RPG segment showing strong monetization",
                "Ad CPMs stabilizing after holiday dip",
            ],
            updates=self.get_market_updates(),
            key_metrics={
                "total_downloads_m": 245,
                "total_revenue_m": 892,
                "avg_session_min": 28.5,
                "dau_growth_pct": 3.2,
            },
        )
        self._reports.append(report)
        return report

    def generate_weekly_report(self) -> MarketReport:
        """Generate a weekly market report."""
        now = datetime.now()
        report = MarketReport(
            report_type="weekly",
            period_start=now.replace(day=now.day - 7),
            period_end=now,
            highlights=[
                "New entrant in battle royale space gaining 8% market share",
                "Hyper-causal segment contraction continues",
                "Console-to-mobile ports outperforming original mobile titles",
            ],
            updates=self.get_market_updates(),
            key_metrics={
                "total_downloads_m": 1720,
                "total_revenue_m": 6200,
                "avg_session_min": 31.2,
                "mau_growth_pct": 1.8,
            },
        )
        self._reports.append(report)
        return report

    def get_market_updates(self) -> List[MarketUpdate]:
        """Get the latest market updates."""
        if not self._updates:
            self._updates = [
                MarketUpdate(
                    headline="Unity announces runtime fee rollback",
                    category="platform",
                    summary="Unity reverses controversial runtime fee policy after developer backlash",
                    source="TechCrunch",
                    impact="positive",
                    related_tickers=["U"],
                ),
                MarketUpdate(
                    headline="China approves 105 new game licenses",
                    category="regulation",
                    summary="NMPA issues 105 new game approvals including 3 AAA titles",
                    source="South China Morning Post",
                    impact="positive",
                    related_tickers=["NTES", "TCEHY"],
                ),
                MarketUpdate(
                    headline="Apple expands Arcade catalog",
                    category="platform",
                    summary="20 new titles added to Apple Arcade in Q3 refresh",
                    source="The Verge",
                    impact="neutral",
                    related_tickers=["AAPL"],
                ),
            ]
        return self._updates

    def get_key_metrics(self) -> dict:
        """Get current key market metrics."""
        return {
            "global_gaming_revenue_usd_b": 187.7,
            "mobile_share_pct": 49,
            "pc_share_pct": 21,
            "console_share_pct": 30,
            "yoy_growth_pct": 2.1,
            "top_genre": "RPG",
            "avg_cpi_usd": 1.85,
        }
