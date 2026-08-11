from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class ForecastResult:
    forecast_id: str
    days: int = 0
    daily_revenue: Dict[int, float] = field(default_factory=dict)
    cumulative_revenue: Dict[int, float] = field(default_factory=dict)
    monthly_revenue: List[float] = field(default_factory=list)
    total_revenue: float = 0.0
    ltv: float = 0.0
    confidence: float = 0.0


class RevenueForecast:
    def __init__(self):
        self.forecasts: Dict[str, ForecastResult] = {}

    def forecast(self, game_data: Dict[str, Any], budget: float, days: int = 180) -> ForecastResult:
        d30 = game_data.get("d30", 0.09)
        arpdau = game_data.get("arpdau", 0.15)
        cpi = game_data.get("cpi", 2.5)

        daily_installs = int(budget / cpi / 30)
        
        daily_revenue = {}
        cumulative_revenue = {}
        total_active_users = 0
        total_revenue = 0

        for day in range(1, days + 1):
            total_active_users += daily_installs * (d30 ** (day / 30))
            day_revenue = total_active_users * arpdau
            
            daily_revenue[day] = round(day_revenue, 2)
            total_revenue += day_revenue
            cumulative_revenue[day] = round(total_revenue, 2)

        monthly_revenue = []
        for month in range(1, 7):
            start_day = (month - 1) * 30 + 1
            end_day = min(month * 30, days)
            month_rev = sum(daily_revenue.get(d, 0) for d in range(start_day, end_day + 1))
            monthly_revenue.append(round(month_rev, 2))

        ltv = total_revenue / (daily_installs * days) if daily_installs > 0 else 0

        forecast = ForecastResult(
            forecast_id=f"forecast_{hash(str(game_data)) % 10000:04d}",
            days=days,
            daily_revenue=daily_revenue,
            cumulative_revenue=cumulative_revenue,
            monthly_revenue=monthly_revenue,
            total_revenue=round(total_revenue, 2),
            ltv=round(ltv, 2),
            confidence=self._calculate_confidence(game_data),
        )

        self.forecasts[forecast.forecast_id] = forecast
        return forecast

    def _calculate_confidence(self, game_data: Dict[str, Any]) -> float:
        factors = [
            game_data.get("d30", 0.09) * 10,
            game_data.get("arpdau", 0.15) * 5,
        ]
        return min(sum(factors) / len(factors), 0.95)

    def forecast_demo(self) -> ForecastResult:
        game_data = {"d30": 0.09, "arpdau": 0.15, "cpi": 2.5}
        return self.forecast(game_data, 50000, 90)
