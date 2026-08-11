from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class CampaignRecord:
    campaign_id: str
    name: str
    platform: str
    objective: str
    budget: float
    status: str
    performance: Dict[str, Any] = field(default_factory=dict)
    audience_segment: Dict[str, str] = field(default_factory=dict)
    creative_dna: Dict[str, str] = field(default_factory=dict)
    success_rate: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class CampaignMemory:
    def __init__(self):
        self.records: Dict[str, CampaignRecord] = {}

    def add(self, record: CampaignRecord) -> None:
        self.records[record.campaign_id] = record

    def get(self, campaign_id: str) -> Optional[CampaignRecord]:
        return self.records.get(campaign_id)

    def search(self, criteria: Dict[str, Any]) -> List[CampaignRecord]:
        results = []
        for record in self.records.values():
            match = True
            for key, value in criteria.items():
                if hasattr(record, key) and getattr(record, key) != value:
                    match = False
                elif key in record.performance and record.performance.get(key) != value:
                    match = False
            if match:
                results.append(record)
        return results

    def get_winners(self, min_roas: float = 2.0) -> List[CampaignRecord]:
        winners = []
        for record in self.records.values():
            roas = record.performance.get("roas", 0.0)
            if roas >= min_roas and record.status == "active":
                winners.append(record)
        return sorted(winners, key=lambda r: r.performance.get("roas", 0), reverse=True)

    def get_failures(self) -> List[CampaignRecord]:
        failures = []
        for record in self.records.values():
            spend = record.performance.get("spend", 0.0)
            purchases = record.performance.get("purchases", 0)
            if spend > 300 and purchases == 0:
                failures.append(record)
        return failures

    def add_demo(self) -> CampaignRecord:
        record = CampaignRecord(
            campaign_id="campaign_0001",
            name="US_WITCH_WINNER_001",
            platform="meta",
            objective="purchase",
            budget=500.0,
            status="active",
            performance={"roas": 3.2, "cpi": 1.8, "spend": 500, "purchases": 45},
            audience_segment={"country": "US", "gender": "female", "age_range": "25-34"},
            creative_dna={"hook": "fast_action", "camera": "close_up", "emotion": "surprise"},
            success_rate=0.73,
        )
        self.add(record)
        return record
