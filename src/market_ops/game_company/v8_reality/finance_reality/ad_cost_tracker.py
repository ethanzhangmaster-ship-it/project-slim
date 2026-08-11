from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class AdPlatform(Enum):
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    TIKTOK_ADS = "tiktok_ads"
    FACEBOOK_ADS = "facebook_ads"
    TWITTER_ADS = "twitter_ads"
    OTHER = "other"


@dataclass
class AdCostRecord:
    platform: AdPlatform
    campaign_id: str
    amount: float
    date: datetime
    clicks: int = 0
    impressions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "campaign_id": self.campaign_id,
            "amount": self.amount,
            "date": self.date.isoformat(),
            "clicks": self.clicks,
            "impressions": self.impressions,
        }


@dataclass
class CostTrend:
    dates: List[str]
    amounts: List[float]
    total: float
    avg_daily: float
    cpc_trend: List[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dates": self.dates,
            "amounts": self.amounts,
            "total": self.total,
            "avg_daily": self.avg_daily,
            "cpc_trend": self.cpc_trend,
        }


class AdCostTracker:
    def __init__(self):
        self._records: List[AdCostRecord] = []

    def record_ad_cost(self, platform: str, campaign_id: str, amount: float, date: datetime,
                       clicks: int = 0, impressions: int = 0) -> AdCostRecord:
        try:
            platform_enum = AdPlatform(platform)
        except ValueError:
            platform_enum = AdPlatform.OTHER

        record = AdCostRecord(
            platform=platform_enum,
            campaign_id=campaign_id,
            amount=amount,
            date=date,
            clicks=clicks,
            impressions=impressions,
        )
        self._records.append(record)
        return record

    def get_daily_ad_cost(self, date: datetime) -> float:
        target_date = date.date()
        return sum(
            r.amount for r in self._records
            if r.date.date() == target_date
        )

    def get_campaign_cost(self, campaign_id: str) -> float:
        return sum(
            r.amount for r in self._records
            if r.campaign_id == campaign_id
        )

    def get_cost_by_platform(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for platform in AdPlatform:
            result[platform.value] = 0.0

        for record in self._records:
            result[record.platform.value] += record.amount

        return result

    def get_cost_trend(self, days: int) -> CostTrend:
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
        amounts = []
        cpc_trend = []

        for date_str in dates:
            date_obj = datetime.fromisoformat(date_str).date()
            daily_records = [r for r in self._records if r.date.date() == date_obj]
            daily_amount = sum(r.amount for r in daily_records)
            total_clicks = sum(r.clicks for r in daily_records)
            cpc = daily_amount / total_clicks if total_clicks > 0 else 0

            amounts.append(daily_amount)
            cpc_trend.append(cpc)

        total = sum(amounts)
        avg_daily = total / days if days > 0 else 0

        return CostTrend(
            dates=dates,
            amounts=amounts,
            total=total,
            avg_daily=avg_daily,
            cpc_trend=cpc_trend,
        )

    def get_all_records(self) -> List[AdCostRecord]:
        return list(self._records)

    def get_stats(self) -> Dict[str, Any]:
        total_cost = sum(r.amount for r in self._records)
        total_clicks = sum(r.clicks for r in self._records)
        total_impressions = sum(r.impressions for r in self._records)
        by_platform = self.get_cost_by_platform()
        unique_campaigns = len(set(r.campaign_id for r in self._records))

        return {
            "total_ad_cost": total_cost,
            "record_count": len(self._records),
            "cost_by_platform": by_platform,
            "unique_campaigns": unique_campaigns,
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "cpc": total_cost / total_clicks if total_clicks > 0 else 0,
            "cpm": (total_cost / total_impressions) * 1000 if total_impressions > 0 else 0,
        }