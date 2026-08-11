from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class RetentionPrediction:
    prediction_id: str
    d1: float = 0.0
    d7: float = 0.0
    d30: float = 0.0
    arpdau: float = 0.0
    ltv: float = 0.0
    confidence: float = 0.0


class RetentionPredictor:
    def __init__(self):
        self.predictions: Dict[str, RetentionPrediction] = {}

    def predict(self, game_data, features: List[str] = None) -> RetentionPrediction:
        if isinstance(game_data, str):
            genre = game_data
            audience = "Female 25-44"
            mechanics_count = len(features) if features else 4
        else:
            genre = game_data.get("genre", "")
            audience = game_data.get("audience", "")
            mechanics_count = len(game_data.get("mechanics", []))

        d1 = self._predict_d1(genre, audience)
        d7 = self._predict_d7(d1, mechanics_count)
        d30 = self._predict_d30(d7, genre)
        arpdau = self._predict_arpdau(genre, audience)
        ltv = self._predict_ltv(d30, arpdau)

        prediction = RetentionPrediction(
            prediction_id=f"ret_{hash(genre + audience) % 10000:04d}",
            d1=round(d1, 2),
            d7=round(d7, 2),
            d30=round(d30, 2),
            arpdau=round(arpdau, 2),
            ltv=round(ltv, 2),
            confidence=self._calculate_confidence(genre),
        )

        self.predictions[prediction.prediction_id] = prediction
        return prediction

    def _predict_d1(self, genre: str, audience: str) -> float:
        base = 0.35
        
        if "Merge" in genre:
            base += 0.05
        if "Decoration" in genre:
            base += 0.03
        if "Cozy" in genre:
            base += 0.02
        
        if "Female" in audience:
            base += 0.03
        
        return min(base, 0.5)

    def _predict_d7(self, d1: float, mechanics_count: int) -> float:
        retention_factor = 0.55 + mechanics_count * 0.02
        return d1 * retention_factor

    def _predict_d30(self, d7: float, genre: str) -> float:
        long_term_factor = 0.5
        
        if "Collection" in genre or "Quest" in genre:
            long_term_factor = 0.6
        
        return d7 * long_term_factor

    def _predict_arpdau(self, genre: str, audience: str) -> float:
        base = 0.12
        
        if "Merge" in genre:
            base += 0.03
        if "Decoration" in genre:
            base += 0.02
        
        if "35-54" in audience:
            base += 0.05
        
        return min(base, 0.25)

    def _predict_ltv(self, d30: float, arpdau: float) -> float:
        days = 180
        decay = 0.98
        total = 0
        
        for day in range(1, days + 1):
            retention = d30 * (decay ** (day - 30)) if day > 30 else d30
            total += retention * arpdau
        
        return total

    def _calculate_confidence(self, genre: str) -> float:
        if "Merge" in genre and "Decoration" in genre:
            return 0.85
        if "Cozy" in genre:
            return 0.8
        return 0.7

    def predict_demo(self) -> RetentionPrediction:
        game_data = {
            "genre": "Merge + Decoration",
            "audience": "US Female 25-44",
            "mechanics": ["Merge", "Decoration", "Collection", "Quests"],
        }
        return self.predict(game_data)
