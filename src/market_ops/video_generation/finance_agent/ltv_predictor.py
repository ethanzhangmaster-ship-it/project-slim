from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class LTVPrediction:
    country: str
    platform: str
    creative_id: str
    audience: Dict[str, str] = field(default_factory=dict)
    d1_ltv: float = 0.0
    d7_ltv: float = 0.0
    d30_ltv: float = 0.0
    d90_ltv: float = 0.0
    d180_ltv: float = 0.0
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class LTVPredictor:
    def __init__(self):
        self.base_ltv = {
            "US": {"meta": 3.5, "google": 3.0, "asa": 4.0, "tiktok": 2.5},
            "DE": {"meta": 2.8, "google": 2.5, "asa": 3.2},
            "JP": {"meta": 4.2, "google": 3.8, "asa": 4.5},
            "default": {"meta": 2.0, "google": 1.8, "asa": 2.2},
        }

    def predict(self, input_data: Dict[str, Any]) -> LTVPrediction:
        country = input_data.get("country", "US")
        platform = input_data.get("platform", "meta")
        audience = input_data.get("audience", {})

        if isinstance(audience, str):
            audience = self._parse_audience_string(audience)

        base = self.base_ltv.get(country, self.base_ltv["default"])
        base_ltv = base.get(platform, base.get("meta", 2.0))

        gender_multiplier = 1.1 if audience.get("gender") == "female" else 0.95
        age_multiplier = 1.2 if audience.get("age_range") in ["25-34", "30-44"] else 1.0
        os_multiplier = 1.15 if audience.get("os") == "iOS" else 0.9

        adjusted_ltv = base_ltv * gender_multiplier * age_multiplier * os_multiplier

        d1_ltv = adjusted_ltv * 0.15
        d7_ltv = adjusted_ltv * 0.45
        d30_ltv = adjusted_ltv * 0.75
        d90_ltv = adjusted_ltv * 0.9
        d180_ltv = adjusted_ltv

        confidence = 0.7 + (gender_multiplier - 1) * 0.1 + (age_multiplier - 1) * 0.05

        return LTVPrediction(
            country=country,
            platform=platform,
            creative_id=input_data.get("creative_id", ""),
            audience=audience,
            d1_ltv=round(d1_ltv, 2),
            d7_ltv=round(d7_ltv, 2),
            d30_ltv=round(d30_ltv, 2),
            d90_ltv=round(d90_ltv, 2),
            d180_ltv=round(d180_ltv, 2),
            confidence=round(min(confidence, 0.95), 2),
        )

    def _parse_audience_string(self, audience_str: str) -> Dict[str, str]:
        result = {}
        parts = audience_str.lower().split("_")
        if len(parts) >= 2:
            result["gender"] = parts[0]
            result["age_range"] = parts[1]
        return result

    def predict_demo(self) -> LTVPrediction:
        data = {
            "country": "US",
            "platform": "meta",
            "creative_id": "creative_001",
            "audience": {"gender": "female", "age_range": "25-34", "os": "iOS"},
        }
        return self.predict(data)
