from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GrowthRecord:
    capability_id: str
    old_level: float
    new_level: float
    improvement: float
    method: str
    timestamp: datetime = field(default_factory=datetime.now)


class CapabilityGrowth:
    def __init__(self):
        self.capabilities = {
            "creative_generation": 0.7,
            "audience_segmentation": 0.6,
            "budget_allocation": 0.65,
            "roas_prediction": 0.55,
            "opportunity_detection": 0.5,
        }
        self.growth_history: List[GrowthRecord] = []

    def grow(self, capability_id: str, method: str, data_points: int) -> GrowthRecord:
        current_level = self.capabilities.get(capability_id, 0.5)
        
        improvement = min(data_points * 0.001, 0.2)
        new_level = min(current_level + improvement, 0.95)

        record = GrowthRecord(
            capability_id=capability_id,
            old_level=round(current_level, 2),
            new_level=round(new_level, 2),
            improvement=round(improvement, 2),
            method=method,
        )

        self.capabilities[capability_id] = new_level
        self.growth_history.append(record)
        return record

    def grow_all(self, data_points: int) -> List[GrowthRecord]:
        records = []
        for capability_id in self.capabilities:
            records.append(self.grow(capability_id, f"Data-driven learning with {data_points} points", data_points))
        return records

    def get_capabilities(self) -> Dict[str, float]:
        return self.capabilities

    def get_growth_history(self) -> List[GrowthRecord]:
        return self.growth_history

    def grow_demo(self) -> List[GrowthRecord]:
        return self.grow_all(150)
