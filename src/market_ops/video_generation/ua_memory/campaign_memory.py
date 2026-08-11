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
    audience_segment: Dict[str, str] = field(default_factory=dict)
    creative_dna: Dict[str, str] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    success_rate: float = 0.0


class CampaignMemory:
    def __init__(self):
        self.records: Dict[str, CampaignRecord] = {}

    def add(self, record: CampaignRecord) -> None:
        self.records[record.campaign_id] = record

    def get(self, campaign_id: str) -> Optional[CampaignRecord]:
        return self.records.get(campaign_id)

    def get_by_platform(self, platform: str) -> List[CampaignRecord]:
        return [r for r in self.records.values() if r.platform == platform]

    def get_winners(self, min_roas: float = 2.0) -> List[CampaignRecord]:
        winners = []
        for record in self.records.values():
            roas = record.performance.get("roas", 0.0)
            if roas >= min_roas:
                winners.append(record)
        return sorted(winners, key=lambda r: r.performance.get("roas", 0), reverse=True)

    def get_success_rate(self, audience_segment: Dict[str, str]) -> float:
        matches = []
        for record in self.records.values():
            match = True
            for key, value in audience_segment.items():
                if record.audience_segment.get(key) != value:
                    match = False
                    break
            if match:
                matches.append(record)
        
        if not matches:
            return 0.0
        
        successes = sum(1 for r in matches if r.performance.get("roas", 0) >= 2.0)
        return successes / len(matches)

    def add_demo(self) -> CampaignRecord:
        record = CampaignRecord(
            campaign_id="campaign_0001",
            name="US_WITCH_WINNER_001",
            platform="meta",
            objective="purchase",
            budget=500.0,
            status="active",
            audience_segment={"country": "US", "gender": "female", "age_range": "25-34"},
            creative_dna={"hook": "fast_action", "camera": "close_up", "emotion": "surprise"},
            performance={"roas": 3.2, "cpi": 1.8, "spend": 500, "purchases": 45},
            success_rate=0.73,
        )
        self.add(record)
        return record
