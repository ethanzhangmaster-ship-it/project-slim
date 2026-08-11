"""AI Market Scanner — discover opportunities from market data.

MVP: Mock scanner with realistic simulation data.
Production: Integrate with Google Play, Meta Ads Library, TikTok Creative Center APIs.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from market_ops.creative_opportunity.schemas import (
    MarketSignal,
    Opportunity,
    OpportunityCategory,
    OpportunitySource,
    OpportunityStatus,
)


class MarketScanner(ABC):
    """Base class for market scanners."""

    @abstractmethod
    def scan(self) -> list[Opportunity]:
        """Scan market and return discovered opportunities."""
        raise NotImplementedError

    @abstractmethod
    def get_signals(self) -> list[MarketSignal]:
        """Get raw market signals."""
        raise NotImplementedError


class MockMarketScanner(MarketScanner):
    """Mock market scanner with realistic simulated opportunities.

    Simulates:
    - Google Play top chart movements
    - Meta Ads Library volume trends
    - TikTok Creative Center hot topics
    """

    # Pre-defined mock opportunities for deterministic testing
    MOCK_OPPORTUNITIES: list[dict[str, Any]] = [
        {
            "name": "Simulation Merge",
            "description": "Merge + Simulation hybrid. Factory production meets merge mechanics.",
            "category": OpportunityCategory.GAMEPLAY_INNOVATION,
            "market_momentum": 85,
            "competition_gap": 70,
            "ua_potential": 80,
            "production_cost": 60,
            "creative_fit": 75,
            "historical_success": 65,
            "reference_games": ["Merge Dragon", "Tasty Travels", "Goods Sort"],
            "tags": ["merge", "simulation", "factory", "hybrid"],
            "estimated_dev_days": 15,
        },
        {
            "name": "AI Pet Merge",
            "description": "AI-generated pet evolution through merge mechanics.",
            "category": OpportunityCategory.GAMEPLAY_INNOVATION,
            "market_momentum": 78,
            "competition_gap": 65,
            "ua_potential": 75,
            "production_cost": 55,
            "creative_fit": 70,
            "historical_success": 60,
            "reference_games": ["Merge Dragon", "Pocket Love"],
            "tags": ["merge", "ai", "pet", "evolution"],
            "estimated_dev_days": 20,
        },
        {
            "name": "Sort Factory",
            "description": "Sort mechanics applied to factory production line management.",
            "category": OpportunityCategory.GAMEPLAY_INNOVATION,
            "market_momentum": 72,
            "competition_gap": 80,
            "ua_potential": 70,
            "production_cost": 50,
            "creative_fit": 80,
            "historical_success": 55,
            "reference_games": ["Goods Sort", "Sort Puzzle"],
            "tags": ["sort", "factory", "puzzle"],
            "estimated_dev_days": 12,
        },
        {
            "name": "3D Merge Visual Trend",
            "description": "3D realistic merge animations becoming popular in ads.",
            "category": OpportunityCategory.VISUAL_TREND,
            "market_momentum": 68,
            "competition_gap": 50,
            "ua_potential": 85,
            "production_cost": 40,
            "creative_fit": 90,
            "historical_success": 70,
            "reference_games": ["Merge Dragon"],
            "tags": ["3d", "visual", "merge", "animation"],
            "estimated_dev_days": 7,
        },
        {
            "name": "Battle Pass in Merge Games",
            "description": "Battle pass monetization showing strong results in merge genre.",
            "category": OpportunityCategory.MONETIZATION_TREND,
            "market_momentum": 75,
            "competition_gap": 60,
            "ua_potential": 65,
            "production_cost": 45,
            "creative_fit": 50,
            "historical_success": 80,
            "reference_games": ["Merge Mansion", "Love & Pies"],
            "tags": ["monetization", "battle_pass", "merge"],
            "estimated_dev_days": 10,
        },
        {
            "name": "TikTok UGC Merge Content",
            "description": "User-generated merge content trending on TikTok with high engagement.",
            "category": OpportunityCategory.UA_OPPORTUNITY,
            "market_momentum": 88,
            "competition_gap": 55,
            "ua_potential": 90,
            "production_cost": 30,
            "creative_fit": 85,
            "historical_success": 50,
            "reference_games": [],
            "tags": ["tiktok", "ugc", "merge", "social"],
            "estimated_dev_days": 5,
        },
        {
            "name": "Cozy Merge Home",
            "description": "Home decoration + merge. Cozy aesthetic trend from lifestyle games.",
            "category": OpportunityCategory.MARKET_GAP,
            "market_momentum": 65,
            "competition_gap": 75,
            "ua_potential": 72,
            "production_cost": 55,
            "creative_fit": 78,
            "historical_success": 45,
            "reference_games": ["Merge Mansion", "Home Design"],
            "tags": ["cozy", "home", "merge", "decoration"],
            "estimated_dev_days": 18,
        },
    ]

    def __init__(self, seed: int | None = None) -> None:
        if seed is not None:
            random.seed(seed)

    def scan(self) -> list[Opportunity]:
        """Return mock opportunities with realistic scores."""
        opportunities = []
        for mock in self.MOCK_OPPORTUNITIES:
            score = self._compute_score(mock)
            opp = Opportunity(
                name=mock["name"],
                description=mock["description"],
                category=mock["category"],
                source=OpportunitySource.AI_SCANNER,
                score=score,
                confidence=round(random.uniform(0.70, 0.95), 2),
                market_momentum=mock["market_momentum"],
                competition_gap=mock["competition_gap"],
                ua_potential=mock["ua_potential"],
                production_cost=mock["production_cost"],
                creative_fit=mock["creative_fit"],
                historical_success=mock["historical_success"],
                reference_games=mock["reference_games"],
                tags=mock["tags"],
                estimated_dev_days=mock["estimated_dev_days"],
                status=OpportunityStatus.PENDING,
            )
            opportunities.append(opp)
        return opportunities

    def get_signals(self) -> list[MarketSignal]:
        """Return mock market signals."""
        return [
            MarketSignal(
                signal_id="sig_001",
                source="google_play",
                signal_type="ranking_jump",
                entity="Simulation Sort",
                value=+45,
                confidence=0.82,
            ),
            MarketSignal(
                signal_id="sig_002",
                source="meta_ads",
                signal_type="ad_volume",
                entity="Merge Factory",
                value=+180,
                confidence=0.75,
            ),
            MarketSignal(
                signal_id="sig_003",
                source="tiktok",
                signal_type="hashtag_trend",
                entity="#mergesimulation",
                value=+320,
                confidence=0.68,
            ),
        ]

    @staticmethod
    def _compute_score(mock: dict[str, Any]) -> float:
        """Compute opportunity score from component scores.

        Formula:
            Market Momentum:    25%
            Competition Gap:    20%
            UA Potential:       20%
            Production Cost:    15% (inverted: higher score = lower cost)
            Creative Fit:       10%
            Historical Success: 10%
        """
        weights = {
            "market_momentum": 0.25,
            "competition_gap": 0.20,
            "ua_potential": 0.20,
            "production_cost": 0.15,
            "creative_fit": 0.10,
            "historical_success": 0.10,
        }
        score = 0.0
        for key, weight in weights.items():
            value = mock.get(key, 50)
            score += value * weight
        return round(score, 1)
