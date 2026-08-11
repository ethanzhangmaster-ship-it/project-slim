"""E7.1: Creative Reality Feedback — campaign performance tracker.

Bridges the gap between AI predictions and actual market reality.
Ingests real performance data (spend, impressions, clicks, installs, revenue, retention)
and feeds it back into the system for learning.

Input sources:
  - Facebook/Meta Ads API (campaign performance)
  - Adjust/Appsflyer (attribution)
  - In-game analytics (D1/D7 retention, ARPDAU)

Output:
  - CreativePerformanceSnapshot: per-genome reality metrics
  - GenomePerformanceDelta: how reality differs from prediction
  - Updated genome fitness scores
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome, Fitness


@dataclass
class CampaignReality:
    """Real performance data for a single campaign."""
    campaign_id: str = ""
    creative_id: str = ""
    genome_id: str = ""            # Which genome was tested
    # Spend
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    # Performance
    ctr: float = 0.0
    cpm: float = 0.0
    cpc: float = 0.0
    installs: int = 0
    cpi: float = 0.0
    cvr: float = 0.0              # install → purchase/event
    # Revenue
    revenue_d0: float = 0.0
    revenue_d7: float = 0.0
    d7_roas: float = 0.0
    # Retention (game-side)
    d1_retention: float = 0.0
    d7_retention: float = 0.0
    arpdau: float = 0.0
    session_length: float = 0.0
    # Meta
    is_statistically_significant: bool = False
    confidence_interval: tuple[float, float] = (0, 0)
    date_collected: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id, "genome_id": self.genome_id,
            "spend": round(self.spend, 2),
            "ctr": round(self.ctr, 4), "cpi": round(self.cpi, 2),
            "d7_roas": round(self.d7_roas, 3),
            "d1_retention": round(self.d1_retention, 3),
            "d7_retention": round(self.d7_retention, 3),
            "is_significant": self.is_statistically_significant,
        }


@dataclass
class GenomePerformanceDelta:
    """How reality differs from AI prediction for a genome."""
    genome_id: str
    genome_name: str
    # Predicted vs Actual
    predicted_score: float       # AI's predicted score (0-100)
    actual_roas: float           # Real D7 ROAS
    actual_ctr: float            # Real CTR
    actual_cpi: float            # Real CPI
    # Delta
    score_delta: float           # positive = AI overestimated
    roas_delta: float
    # Classification
    was_winner: bool             # ROAS >= 1.0
    was_failure: bool            # ROAS < 0.3 and spent enough
    prediction_correct: bool     # Did AI correctly predict outcome?
    # Attribution — WHY was the prediction wrong?
    error_attribution: dict[str, float] = field(default_factory=dict)  # agent → responsibility
    lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "predicted": self.predicted_score,
            "actual_roas": round(self.actual_roas, 3),
            "score_delta": round(self.score_delta, 1),
            "was_winner": self.was_winner,
            "prediction_correct": self.prediction_correct,
            "error_attribution": self.error_attribution,
            "lessons": self.lessons,
        }


class RealityTracker:
    """Tracks real campaign performance and computes deltas from predictions.

    The bridge between "AI analysis" and "what actually happened in market".

    Usage:
        tracker = RealityTracker()
        tracker.ingest_campaign(campaign_data)
        deltas = tracker.compute_deltas(predicted_genomes)
        tracker.update_genome_fitness(deltas)
    """

    def __init__(self) -> None:
        self._campaigns: list[CampaignReality] = []
        self._by_genome: dict[str, list[CampaignReality]] = {}

    def ingest_campaign(self, campaign: CampaignReality) -> None:
        """Ingest real campaign data."""
        self._campaigns.append(campaign)
        self._by_genome.setdefault(campaign.genome_id, []).append(campaign)

    def ingest_batch(self, campaigns: list[CampaignReality]) -> None:
        for c in campaigns:
            self.ingest_campaign(c)

    def compute_deltas(
        self, predictions: dict[str, float]  # genome_id → predicted_score
    ) -> list[GenomePerformanceDelta]:
        """Compare reality to AI predictions."""
        deltas: list[GenomePerformanceDelta] = []

        for genome_id, campaigns in self._by_genome.items():
            # Aggregate across all campaigns for this genome
            total_spend = sum(c.spend for c in campaigns)
            total_revenue = sum(c.revenue_d7 for c in campaigns)
            avg_ctr = sum(c.ctr for c in campaigns) / len(campaigns) if campaigns else 0
            avg_cpi = sum(c.cpi for c in campaigns) / len(campaigns) if campaigns else 0
            actual_roas = total_revenue / max(0.01, total_spend)

            predicted = predictions.get(genome_id, 50)
            # Normalize prediction to ROAS scale (0-100 → 0-3 ROAS)
            predicted_roas = predicted / 100 * 3.0

            was_winner = actual_roas >= 1.0
            was_failure = actual_roas < 0.3 and total_spend >= 100
            predicted_winner = predicted >= 70  # AI predicted success

            delta = GenomePerformanceDelta(
                genome_id=genome_id,
                genome_name=f"genome_{genome_id[:8]}",
                predicted_score=predicted,
                actual_roas=actual_roas,
                actual_ctr=avg_ctr,
                actual_cpi=avg_cpi,
                score_delta=round(predicted - actual_roas * 33.3, 1),
                roas_delta=round(predicted_roas - actual_roas, 3),
                was_winner=was_winner,
                was_failure=was_failure,
                prediction_correct=(was_winner == predicted_winner),
                lessons=self._extract_lessons(predicted, actual_roas, avg_ctr, avg_cpi),
            )
            deltas.append(delta)

        return deltas

    def get_aggregate_stats(self) -> dict[str, Any]:
        """Get aggregate reality stats."""
        if not self._campaigns:
            return {"status": "no_data"}

        total_spend = sum(c.spend for c in self._campaigns)
        total_revenue = sum(c.revenue_d7 for c in self._campaigns)
        total_installs = sum(c.installs for c in self._campaigns)
        winners = sum(1 for c in self._campaigns
                      if c.d7_roas >= 1.0 and c.spend >= 100)

        return {
            "total_campaigns": len(self._campaigns),
            "unique_genomes": len(self._by_genome),
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "aggregate_roi": round(total_revenue / max(0.01, total_spend), 2),
            "total_installs": total_installs,
            "avg_cpi": round(total_spend / max(1, total_installs), 2),
            "winner_rate": round(winners / max(1, len(self._campaigns)), 2),
        }

    @staticmethod
    def _extract_lessons(predicted: float, actual_roas: float, actual_ctr: float,
                         actual_cpi: float) -> list[str]:
        lessons = []
        if predicted > 70 and actual_roas < 0.5:
            lessons.append("AI overestimated market potential")
        if actual_ctr < 0.01:
            lessons.append("Hook/visual failed to capture attention")
        if actual_ctr > 0.03 and actual_roas < 0.5:
            lessons.append("High CTR but low conversion — gameplay/retention issue")
        if actual_cpi > 5:
            lessons.append("CPI too high — creative cannot scale in current market")
        return lessons
