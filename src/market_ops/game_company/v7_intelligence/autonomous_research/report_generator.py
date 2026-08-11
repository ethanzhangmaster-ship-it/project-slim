"""Report generator module for autonomous research."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class CEOReport:
    """Executive summary report for the CEO."""
    title: str
    period: str
    executive_summary: str
    top_priorities: List[str] = field(default_factory=list)
    market_headlines: List[str] = field(default_factory=list)
    competitive_alerts: List[str] = field(default_factory=list)
    tech_watch_items: List[str] = field(default_factory=list)
    financial_snapshot: dict = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyReport:
    """Strategic analysis report."""
    title: str
    period: str
    market_opportunities: List[str] = field(default_factory=list)
    strategic_initiatives: List[str] = field(default_factory=list)
    partnership_recommendations: List[str] = field(default_factory=list)
    portfolio_recommendations: List[str] = field(default_factory=list)
    long_term_outlook: str = ""
    generated_at: datetime = field(default_factory=datetime.now)


@dataclass
class RiskReport:
    """Risk assessment report."""
    title: str
    period: str
    risk_categories: dict = field(default_factory=dict)
    top_risks: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    compliance_updates: List[str] = field(default_factory=list)
    overall_risk_level: str = "medium"
    generated_at: datetime = field(default_factory=datetime.now)


class ReportGenerator:
    """Generates various reports for stakeholders."""

    def __init__(self):
        self._reports = {
            "ceo": [],
            "strategy": [],
            "risk": [],
        }

    def generate_ceo_report(self) -> CEOReport:
        """Generate a CEO executive summary report."""
        report = CEOReport(
            title="Weekly Executive Intelligence Brief",
            period="2026-W27",
            executive_summary=(
                "Market remains stable with mobile segment showing 3% growth. "
                "Key competitor launched aggressive pricing in APAC. "
                "Two emerging technologies flagged for strategic evaluation."
            ),
            top_priorities=[
                "Respond to competitor pricing in APAC",
                "Accelerate Gen AI art pipeline pilot",
                "Evaluate cloud-native engine for Project Titan",
            ],
            market_headlines=[
                "Mobile downloads up 5% WoW",
                "Unity fee policy reversal stabilizes indie sentiment",
                "China license approvals return to normal pace",
            ],
            competitive_alerts=[
                "RivalGames Inc launched AAA RPG in our core segment",
                "NextGen Studios acquired AI startup for $120M",
            ],
            tech_watch_items=[
                "Generative AI asset tools reaching production maturity",
                "Cloud-native engines enabling 10K player battles",
            ],
            financial_snapshot={
                "projected_q3_revenue_m": 145,
                "yoy_revenue_growth_pct": 8.5,
                "r_and_d_spend_pct": 18,
                "marketing_spend_pct": 22,
            },
        )
        self._reports["ceo"].append(report)
        return report

    def generate_strategy_report(self) -> StrategyReport:
        """Generate a strategic analysis report."""
        report = StrategyReport(
            title="Quarterly Strategic Intelligence Report",
            period="Q2 2026",
            market_opportunities=[
                "Emerging markets (SEA, LATAM) showing 15% growth",
                "Cross-platform RPGs underserved in mid-core segment",
                "AI-driven personalization gap in live-ops tooling",
            ],
            strategic_initiatives=[
                "Establish Gen AI Center of Excellence",
                "Expand APAC publishing team",
                "Pilot cloud-native backend for next MMO",
            ],
            partnership_recommendations=[
                "Co-development with leading anime IP holder",
                "Technology partnership with cloud-native engine vendor",
                "Acqui-hire target: AI gameplay startup",
            ],
            portfolio_recommendations=[
                "Increase investment in Project Titan (RPG)",
                "Sunset legacy title with declining MAU",
                "Fast-track casual title for LATAM market",
            ],
            long_term_outlook=(
                "Industry consolidation will accelerate. Companies with strong IP, "
                "AI-augmented pipelines, and global distribution will capture disproportionate value. "
                "Recommend positioning for M&A opportunities within 18 months."
            ),
        )
        self._reports["strategy"].append(report)
        return report

    def generate_risk_report(self) -> RiskReport:
        """Generate a risk assessment report."""
        report = RiskReport(
            title="Monthly Risk Intelligence Assessment",
            period="July 2026",
            risk_categories={
                "regulatory": "medium",
                "competitive": "high",
                "technology": "medium",
                "financial": "low",
                "operational": "medium",
            },
            top_risks=[
                "Competitor pricing war eroding APAC margins",
                "AI regulation uncertainty in EU and US",
                "Key talent attrition to well-funded startups",
                "Supply chain constraints for console dev kits",
            ],
            mitigation_strategies=[
                "Implement dynamic pricing engine for APAC",
                "Establish AI ethics committee and compliance framework",
                "Launch retention program for senior engineers",
                "Diversify hardware partner relationships",
            ],
            compliance_updates=[
                "China: New minor protection rules effective Aug 1",
                "EU: DSA transparency requirements for in-game stores",
                "US: FTC reviewing loot box disclosure practices",
            ],
            overall_risk_level="medium",
        )
        self._reports["risk"].append(report)
        return report

    def get_all_reports(self) -> dict:
        """Get all generated reports."""
        return self._reports
