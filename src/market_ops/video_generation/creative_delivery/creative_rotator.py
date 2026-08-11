from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class RotationResult:
    campaign_id: str
    rotated_creatives: List[str]
    removed_creatives: List[str]
    added_creatives: List[str]
    rotation_strategy: str
    timestamp: datetime = field(default_factory=datetime.now)


class CreativeRotator:
    def __init__(self):
        self.strategies = {
            "performance_based": self._rotate_performance_based,
            "round_robin": self._rotate_round_robin,
            "fatigue_based": self._rotate_fatigue_based,
        }

    def rotate(self, campaign_id: str, current_creatives: List[str], performance_data: Dict[str, Any], strategy: str = "performance_based") -> RotationResult:
        rotator = self.strategies.get(strategy, self._rotate_performance_based)
        return rotator(campaign_id, current_creatives, performance_data)

    def _rotate_performance_based(self, campaign_id: str, current_creatives: List[str], performance_data: Dict[str, Any]) -> RotationResult:
        if not performance_data:
            return RotationResult(
                campaign_id=campaign_id,
                rotated_creatives=current_creatives,
                removed_creatives=[],
                added_creatives=[],
                rotation_strategy="performance_based",
            )

        scores = {}
        for creative_id in current_creatives:
            metrics = performance_data.get(creative_id, {})
            roas = metrics.get("roas", 0.0)
            ctr = metrics.get("ctr", 0.0)
            scores[creative_id] = roas * 0.6 + ctr * 0.4

        sorted_creatives = sorted(current_creatives, key=lambda x: scores.get(x, 0), reverse=True)
        keep = sorted_creatives[:3]
        remove = [c for c in current_creatives if c not in keep]
        add = [f"new_creative_{i}" for i in range(len(remove))]

        return RotationResult(
            campaign_id=campaign_id,
            rotated_creatives=keep + add,
            removed_creatives=remove,
            added_creatives=add,
            rotation_strategy="performance_based",
        )

    def _rotate_round_robin(self, campaign_id: str, current_creatives: List[str], performance_data: Dict[str, Any]) -> RotationResult:
        if len(current_creatives) <= 3:
            return RotationResult(
                campaign_id=campaign_id,
                rotated_creatives=current_creatives,
                removed_creatives=[],
                added_creatives=[],
                rotation_strategy="round_robin",
            )

        remove = current_creatives[:2]
        add = [f"new_creative_{i}" for i in range(2)]
        rotated = current_creatives[2:] + add

        return RotationResult(
            campaign_id=campaign_id,
            rotated_creatives=rotated,
            removed_creatives=remove,
            added_creatives=add,
            rotation_strategy="round_robin",
        )

    def _rotate_fatigue_based(self, campaign_id: str, current_creatives: List[str], performance_data: Dict[str, Any]) -> RotationResult:
        if not performance_data:
            return RotationResult(
                campaign_id=campaign_id,
                rotated_creatives=current_creatives,
                removed_creatives=[],
                added_creatives=[],
                rotation_strategy="fatigue_based",
            )

        fatigued = []
        for creative_id in current_creatives:
            metrics = performance_data.get(creative_id, {})
            fatigue = metrics.get("fatigue_score", 0.0)
            if fatigue > 0.7:
                fatigued.append(creative_id)

        add = [f"new_creative_{i}" for i in range(len(fatigued))]
        rotated = [c for c in current_creatives if c not in fatigued] + add

        return RotationResult(
            campaign_id=campaign_id,
            rotated_creatives=rotated,
            removed_creatives=fatigued,
            added_creatives=add,
            rotation_strategy="fatigue_based",
        )

    def rotate_demo(self) -> RotationResult:
        current = ["creative_001", "creative_002", "creative_003", "creative_004", "creative_005"]
        performance = {
            "creative_001": {"roas": 3.2, "ctr": 0.05},
            "creative_002": {"roas": 2.8, "ctr": 0.04},
            "creative_003": {"roas": 1.2, "ctr": 0.02},
            "creative_004": {"roas": 0.8, "ctr": 0.01},
            "creative_005": {"roas": 2.5, "ctr": 0.03},
        }
        return self.rotate("campaign_001", current, performance)
