from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class FatigueStatus:
    creative_id: str
    fatigue_score: float
    status: str
    impressions: int = 0
    clicks: int = 0
    ctr_trend: float = 0.0
    recommended_action: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class FatigueManager:
    def __init__(self):
        self.fatigue_threshold = 0.7
        self.warning_threshold = 0.5

    def calculate_fatigue(self, creative_id: str, metrics: Dict[str, Any]) -> FatigueStatus:
        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        ctr_current = metrics.get("ctr_current", 0.0)
        ctr_initial = metrics.get("ctr_initial", 0.0)

        if ctr_initial > 0:
            ctr_trend = (ctr_current - ctr_initial) / ctr_initial
        else:
            ctr_trend = 0.0

        impression_factor = min(impressions / 50000, 1.0)
        ctr_factor = max(-ctr_trend, 0)
        fatigue_score = (impression_factor * 0.4) + (ctr_factor * 0.6)

        if fatigue_score >= self.fatigue_threshold:
            status = "fatigued"
            recommended_action = "rotate"
        elif fatigue_score >= self.warning_threshold:
            status = "warning"
            recommended_action = "monitor"
        else:
            status = "healthy"
            recommended_action = "keep"

        return FatigueStatus(
            creative_id=creative_id,
            fatigue_score=round(fatigue_score, 2),
            status=status,
            impressions=impressions,
            clicks=clicks,
            ctr_trend=round(ctr_trend, 2),
            recommended_action=recommended_action,
        )

    def get_fatigued_creatives(self, all_creatives: Dict[str, Dict[str, Any]]) -> List[FatigueStatus]:
        fatigued = []
        for creative_id, metrics in all_creatives.items():
            status = self.calculate_fatigue(creative_id, metrics)
            if status.status == "fatigued":
                fatigued.append(status)
        return sorted(fatigued, key=lambda x: x.fatigue_score, reverse=True)

    def calculate_demo(self) -> FatigueStatus:
        metrics = {
            "impressions": 60000,
            "clicks": 1200,
            "ctr_current": 0.015,
            "ctr_initial": 0.04,
        }
        return self.calculate_fatigue("creative_001", metrics)
