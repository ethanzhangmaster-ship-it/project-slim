from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, date


@dataclass
class SpendRecord:
    platform: str
    amount: float
    campaign_id: str
    date: date = field(default_factory=lambda: datetime.now().date())
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "amount": self.amount,
            "campaign_id": self.campaign_id,
            "date": self.date.isoformat(),
            "timestamp": self.timestamp.isoformat(),
        }


class SpendTracker:
    def __init__(self):
        self._spend_records: List[SpendRecord] = []

    def record_spend(self, platform: str, amount: float, campaign_id: str) -> SpendRecord:
        record = SpendRecord(
            platform=platform,
            amount=amount,
            campaign_id=campaign_id,
        )
        self._spend_records.append(record)
        return record

    def get_daily_spend(self, target_date: date) -> Dict[str, float]:
        daily_spend: Dict[str, float] = {}
        for record in self._spend_records:
            if record.date == target_date:
                daily_spend[record.platform] = daily_spend.get(record.platform, 0) + record.amount
        return daily_spend

    def get_campaign_spend(self, campaign_id: str) -> Dict[str, float]:
        campaign_spend: Dict[str, float] = {}
        for record in self._spend_records:
            if record.campaign_id == campaign_id:
                campaign_spend[record.platform] = campaign_spend.get(record.platform, 0) + record.amount
        return campaign_spend

    def get_total_spend(self) -> float:
        return sum(record.amount for record in self._spend_records)

    def get_spend_by_platform(self) -> Dict[str, float]:
        spend_by_platform: Dict[str, float] = {}
        for record in self._spend_records:
            spend_by_platform[record.platform] = spend_by_platform.get(record.platform, 0) + record.amount
        return spend_by_platform

    def get_spend_history(self, platform: str = None) -> List[SpendRecord]:
        if platform:
            return [record for record in self._spend_records if record.platform == platform]
        return self._spend_records