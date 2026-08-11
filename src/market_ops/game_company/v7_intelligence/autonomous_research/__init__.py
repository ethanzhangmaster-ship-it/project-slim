"""Autonomous research module for game company market intelligence."""

from .paper_reader import PaperReader, PaperSummary, ResearchInsight
from .market_reporter import MarketReporter, MarketReport, MarketUpdate
from .competitor_watcher import CompetitorWatcher, CompetitorMove, CompetitorAnalysis, ThreatLevel
from .technology_tracker import TechnologyTracker, TechTrend, TechAssessment, ImpactLevel
from .report_generator import ReportGenerator, CEOReport, StrategyReport, RiskReport

__all__ = [
    "PaperReader",
    "PaperSummary",
    "ResearchInsight",
    "MarketReporter",
    "MarketReport",
    "MarketUpdate",
    "CompetitorWatcher",
    "CompetitorMove",
    "CompetitorAnalysis",
    "ThreatLevel",
    "TechnologyTracker",
    "TechTrend",
    "TechAssessment",
    "ImpactLevel",
    "ReportGenerator",
    "CEOReport",
    "StrategyReport",
    "RiskReport",
]
