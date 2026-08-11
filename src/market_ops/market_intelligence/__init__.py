"""E5.1 Market Brain — Entry point for market intelligence layer.

Export pipeline: TrendDetector → CompetitorTracker → CreativeSignalMiner →
                 CategoryHeatmap → OpportunityGenerator

Uses real data in production. Mock data simulates the full signal pipeline.
"""

from .trend_detector import TrendDetector, TrendSignal, TrendDirection, TrendConfidence
from .competitor_tracker import CompetitorTracker, CompetitorProfile, CompetitorTier
from .creative_signal_miner import CreativeSignalMiner, CreativeSignal
from .category_heatmap import CategoryHeatmapEngine, CategoryHeatmap, CategoryCell
from .opportunity_generator import OpportunityGenerator, CreativeOpportunity

__all__ = [
    "TrendDetector", "TrendSignal", "TrendDirection", "TrendConfidence",
    "CompetitorTracker", "CompetitorProfile", "CompetitorTier",
    "CreativeSignalMiner", "CreativeSignal",
    "CategoryHeatmapEngine", "CategoryHeatmap", "CategoryCell",
    "OpportunityGenerator", "CreativeOpportunity",
]
