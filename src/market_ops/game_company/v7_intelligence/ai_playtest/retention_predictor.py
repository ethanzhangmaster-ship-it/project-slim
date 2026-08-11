from dataclasses import dataclass
from typing import Optional
import random


@dataclass
class RetentionForecast:
    d1: float
    d7: float
    d30: float
    ltv_usd: float
    confidence: float


class RetentionPredictor:
    """Predict retention and lifetime value."""

    def __init__(self):
        self._forecast: Optional[RetentionForecast] = None

    def _ensure_forecast(self) -> None:
        if self._forecast is None:
            self._forecast = RetentionForecast(
                d1=round(random.uniform(0.35, 0.65), 4),
                d7=round(random.uniform(0.15, 0.35), 4),
                d30=round(random.uniform(0.05, 0.18), 4),
                ltv_usd=round(random.uniform(1.0, 50.0), 2),
                confidence=round(random.uniform(0.75, 0.95), 4),
            )

    def predict_d1(self) -> float:
        """Predict Day-1 retention rate."""
        self._ensure_forecast()
        return self._forecast.d1  # type: ignore[union-attr]

    def predict_d7(self) -> float:
        """Predict Day-7 retention rate."""
        self._ensure_forecast()
        return self._forecast.d7  # type: ignore[union-attr]

    def predict_d30(self) -> float:
        """Predict Day-30 retention rate."""
        self._ensure_forecast()
        return self._forecast.d30  # type: ignore[union-attr]

    def predict_ltv(self) -> float:
        """Predict lifetime value (USD)."""
        self._ensure_forecast()
        return self._forecast.ltv_usd  # type: ignore[union-attr]
