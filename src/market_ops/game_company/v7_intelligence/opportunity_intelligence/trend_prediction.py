from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime, timedelta
import random


@dataclass
class Trend:
    trend_id: str
    name: str
    category: str
    start_date: str
    predicted_peak: str
    current_momentum: float
    related_genres: List[str]


@dataclass
class EmergingTrend:
    trend: Trend
    detection_confidence: float
    early_signals: List[str]
    potential_scale: str


@dataclass
class TrendScore:
    trend: Trend
    relevance_score: float
    longevity_score: float
    monetization_potential: float
    overall_score: float


class TrendPrediction:
    """Predict market trends and emerging patterns."""

    _trends: List[Trend] = []

    def __init__(self):
        self._trends = self._generate_mock_trends()

    def _generate_mock_trends(self) -> List[Trend]:
        names = [
            "AI-driven NPCs",
            "Cross-platform progression",
            "Social co-op puzzles",
            "Narrative hyper-casual",
            "Web3 integration",
            "VR fitness gaming",
            "Subscription bundles",
            "UGC platforms",
        ]
        categories = ["technology", "monetization", "gameplay", "platform", "social"]
        genres = ["RPG", "Strategy", "Puzzle", "Action", "Simulation", "Casual"]
        trends = []
        for i, name in enumerate(names):
            start = (datetime.now() - timedelta(days=random.randint(30, 180))).strftime("%Y-%m-%d")
            peak = (datetime.now() + timedelta(days=random.randint(90, 365))).strftime("%Y-%m-%d")
            trends.append(
                Trend(
                    trend_id=f"trend_{i:03d}",
                    name=name,
                    category=random.choice(categories),
                    start_date=start,
                    predicted_peak=peak,
                    current_momentum=round(random.uniform(10, 100), 2),
                    related_genres=random.sample(genres, k=random.randint(1, 3)),
                )
            )
        return trends

    def predict_trends(self) -> List[Trend]:
        """Return predicted trends."""
        return sorted(self._trends, key=lambda t: t.current_momentum, reverse=True)

    def get_emerging_trends(self) -> List[EmergingTrend]:
        """Return emerging trends with early signals."""
        emerging = []
        for trend in self._trends[:5]:
            signals = [f"Signal {i} for {trend.name}" for i in range(random.randint(2, 5))]
            emerging.append(
                EmergingTrend(
                    trend=trend,
                    detection_confidence=round(random.uniform(0.4, 0.9), 2),
                    early_signals=signals,
                    potential_scale=random.choice(["niche", "moderate", "mass_market"]),
                )
            )
        return emerging

    def score_trend(self, trend: Trend) -> TrendScore:
        """Score a trend for strategic value."""
        rel = round(random.uniform(40, 100), 2)
        long = round(random.uniform(30, 100), 2)
        mon = round(random.uniform(20, 100), 2)
        overall = round((rel + long + mon) / 3, 2)
        return TrendScore(
            trend=trend,
            relevance_score=rel,
            longevity_score=long,
            monetization_potential=mon,
            overall_score=overall,
        )
