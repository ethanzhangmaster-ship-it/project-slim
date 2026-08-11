from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PlatformRecord:
    platform_id: str
    name: str
    api_status: str
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    historical_success: float = 0.0
    best_performing_creatives: List[str] = field(default_factory=list)
    last_sync: Optional[datetime] = None


class PlatformMemory:
    def __init__(self):
        self.records: Dict[str, PlatformRecord] = {}

    def add(self, record: PlatformRecord) -> None:
        self.records[record.platform_id] = record

    def get(self, platform_id: str) -> Optional[PlatformRecord]:
        return self.records.get(platform_id)

    def get_best_performing(self) -> List[PlatformRecord]:
        return sorted(
            self.records.values(),
            key=lambda r: r.performance_metrics.get("roas", 0),
            reverse=True,
        )

    def get_recommended_platforms(self, audience: Dict[str, str]) -> List[str]:
        platform_preferences = {
            ("US", "female", "25-34"): ["meta", "google"],
            ("US", "male", "18-24"): ["tiktok", "google"],
            ("DE", "female", "30-44"): ["meta", "google"],
            ("JP", "female", "25-34"): ["apple", "google"],
        }
        
        key = (audience.get("country", ""), audience.get("gender", ""), audience.get("age_range", ""))
        return platform_preferences.get(key, ["meta", "google"])

    def add_demo(self) -> PlatformRecord:
        record = PlatformRecord(
            platform_id="meta",
            name="Meta",
            api_status="connected",
            performance_metrics={"roas": 2.8, "cpi": 2.1, "ctr": 0.045},
            historical_success=0.73,
            best_performing_creatives=["creative_A", "creative_B"],
        )
        self.add(record)
        return record
