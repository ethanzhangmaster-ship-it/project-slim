from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime, timedelta
import random


@dataclass
class GenreForecast:
    genre: str
    month: str
    predicted_users: int
    predicted_revenue: float
    confidence: float


@dataclass
class GrowthTrend:
    genre: str
    monthly_growth: List[float]
    avg_growth_rate: float
    trend_direction: str


@dataclass
class PeakPrediction:
    genre: str
    predicted_peak_month: str
    peak_user_count: int
    peak_revenue: float
    confidence: float


class GenreForecaster:
    """Forecast genre performance and trends."""

    def forecast(self, genre: str, months: int) -> List[GenreForecast]:
        """Forecast genre performance for upcoming months."""
        forecasts = []
        base_users = random.randint(100000, 10000000)
        base_revenue = random.uniform(100000, 10000000)
        for i in range(months):
            month_date = (datetime.now() + timedelta(days=30 * i)).strftime("%Y-%m")
            growth_factor = 1 + random.uniform(-0.1, 0.2)
            base_users = int(base_users * growth_factor)
            base_revenue = base_revenue * growth_factor
            forecasts.append(
                GenreForecast(
                    genre=genre,
                    month=month_date,
                    predicted_users=base_users,
                    predicted_revenue=round(base_revenue, 2),
                    confidence=round(random.uniform(0.6, 0.95), 2),
                )
            )
        return forecasts

    def get_growth_trend(self, genre: str) -> GrowthTrend:
        """Get historical and projected growth trend for a genre."""
        monthly = [round(random.uniform(-0.15, 0.35), 4) for _ in range(12)]
        avg = round(sum(monthly) / len(monthly), 4)
        direction = "upward" if avg > 0.05 else "downward" if avg < -0.05 else "stable"
        return GrowthTrend(
            genre=genre,
            monthly_growth=monthly,
            avg_growth_rate=avg,
            trend_direction=direction,
        )

    def predict_peak(self, genre: str) -> PeakPrediction:
        """Predict peak performance month for a genre."""
        peak_month = (datetime.now() + timedelta(days=random.randint(60, 365))).strftime("%Y-%m")
        return PeakPrediction(
            genre=genre,
            predicted_peak_month=peak_month,
            peak_user_count=random.randint(500000, 50000000),
            peak_revenue=round(random.uniform(500000, 50000000), 2),
            confidence=round(random.uniform(0.5, 0.9), 2),
        )
