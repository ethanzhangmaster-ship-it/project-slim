from dataclasses import dataclass
from typing import List, Dict, Any
import random


@dataclass
class RankerOpportunity:
    opportunity_id: str
    name: str
    genre: str
    market_size: int
    competition_score: float
    team_fit: float
    estimated_cost: float
    estimated_revenue: float
    risk_score: float
    strategic_alignment: float


@dataclass
class RankedOpportunity:
    opportunity: RankerOpportunity
    total_score: float
    rank: int
    tier: str


@dataclass
class OpportunityScoreBreakdown:
    opportunity: RankerOpportunity
    market_score: float
    competition_score: float
    team_fit_score: float
    financial_score: float
    risk_adjusted_score: float
    strategic_score: float


class OpportunityRanker:
    """Rank and score game development opportunities."""

    def rank(self, opportunities: List[RankerOpportunity]) -> List[RankedOpportunity]:
        """Rank a list of opportunities by total score."""
        scored = []
        for opp in opportunities:
            total = self.score_opportunity(opp)
            scored.append((opp, total))
        scored.sort(key=lambda x: x[1], reverse=True)
        ranked = []
        for idx, (opp, total) in enumerate(scored, start=1):
            tier = "S" if total >= 85 else "A" if total >= 70 else "B" if total >= 55 else "C"
            ranked.append(
                RankedOpportunity(
                    opportunity=opp,
                    total_score=total,
                    rank=idx,
                    tier=tier,
                )
            )
        return ranked

    def get_top_n(self, opportunities: List[RankerOpportunity], n: int) -> List[RankedOpportunity]:
        """Return top N opportunities."""
        ranked = self.rank(opportunities)
        return ranked[:n]

    def score_opportunity(self, opp: RankerOpportunity) -> float:
        """Calculate a composite score for an opportunity."""
        market = min(opp.market_size / 1000000, 100)
        competition = max(0, 100 - opp.competition_score)
        team = opp.team_fit
        financial = min((opp.estimated_revenue / max(opp.estimated_cost, 1)) * 10, 100)
        risk = max(0, 100 - opp.risk_score)
        strategic = opp.strategic_alignment
        total = round(
            (market * 0.2 + competition * 0.15 + team * 0.15 + financial * 0.2 + risk * 0.15 + strategic * 0.15),
            2,
        )
        return min(total, 100)
