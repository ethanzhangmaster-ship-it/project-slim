"""Phase D.1 — Opportunity Intelligence Layer.

Human-AI Creative Evolution Platform.
"""

from .schemas import (
    HumanIdea,
    Opportunity,
    RankedOpportunity,
    OpportunityCategory,
    OpportunitySource,
    ExperimentPlan,
    ExperimentVariant,
    OpportunityReport,
    OpportunityStatus,
)
from .human_idea import HumanIdeaInbox
from .market_scanner import MockMarketScanner, MarketScanner
from .opportunity_engine import OpportunityIntelligenceEngine
from .opportunity_ranker import OpportunityRanker, Recommendation
from .hypothesis_engine import HypothesisEngine
from .genome_builder import OpportunityGenomeBuilder
from .opportunity_report import OpportunityReportGenerator

__all__ = [
    "HumanIdea",
    "Opportunity",
    "RankedOpportunity",
    "OpportunityCategory",
    "OpportunitySource",
    "ExperimentPlan",
    "ExperimentVariant",
    "OpportunityReport",
    "OpportunityStatus",
    "HumanIdeaInbox",
    "MarketScanner",
    "MockMarketScanner",
    "OpportunityIntelligenceEngine",
    "OpportunityRanker",
    "Recommendation",
    "HypothesisEngine",
    "OpportunityGenomeBuilder",
    "OpportunityReportGenerator",
]
