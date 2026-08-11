from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class RevenueSource(Enum):
    IN_APP_PURCHASE = "in_app_purchase"
    AD_REVENUE = "ad_revenue"
    SUBSCRIPTION = "subscription"
    PREMIUM = "premium"
    OTHER = "other"


@dataclass
class RevenueRecord:
    source: RevenueSource
    amount: float
    date: datetime
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "amount": self.amount,
            "date": self.date.isoformat(),
            "description": self.description,
        }


@dataclass
class RevenueTrend:
    dates: List[str]
    amounts: List[float]
    total: float
    avg_daily: float
    growth_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dates": self.dates,
            "amounts": self.amounts,
            "total": self.total,
            "avg_daily": self.avg_daily,
            "growth_rate": self.growth_rate,
        }


class RevenueTracker:
    def __init__(self):
        self._records: List[RevenueRecord] = []

    def record_revenue(self, source: str, amount: float, date: datetime, description: Optional[str] = None) -> RevenueRecord:
        try:
            source_enum = RevenueSource(source)
        except ValueError:
            source_enum = RevenueSource.OTHER

        record = RevenueRecord(
            source=source_enum,
            amount=amount,
            date=date,
            description=description,
        )
        self._records.append(record)
        return record

    def get_daily_revenue(self, date: datetime) -> float:
        target_date = date.date()
        return sum(
            r.amount for r in self._records
            if r.date.date() == target_date
        )

    def get_monthly_revenue(self, month: int, year: Optional[int] = None) -> float:
        target_year = year or datetime.now().year
        return sum(
            r.amount for r in self._records
            if r.date.year == target_year and r.date.month == month
        )

    def get_revenue_by_source(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for source in RevenueSource:
            result[source.value] = 0.0

        for record in self._records:
            result[record.source.value] += record.amount

        return result

    def get_revenue_trend(self, days: int) -> RevenueTrend:
        today = datetime.now().date()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
        amounts = []

        for date_str in dates:
            date_obj = datetime.fromisoformat(date_str).date()
            daily = sum(
                r.amount for r in self._records
                if r.date.date() == date_obj
            )
            amounts.append(daily)

        total = sum(amounts)
        avg_daily = total / days if days > 0 else 0
        growth_rate = 0.0

        if len(amounts) >= 2:
            prev_avg = sum(amounts[:-1]) / (len(amounts) - 1) if len(amounts) > 1 else 0
            if prev_avg > 0:
                growth_rate = (amounts[-1] - prev_avg) / prev_avg

        return RevenueTrend(
            dates=dates,
            amounts=amounts,
            total=total,
            avg_daily=avg_daily,
            growth_rate=growth_rate,
        )

    def get_all_records(self) -> List[RevenueRecord]:
        return list(self._records)

    def get_stats(self) -> Dict[str, Any]:
        total_revenue = sum(r.amount for r in self._records)
        record_count = len(self._records)
        by_source = self.get_revenue_by_source()
        return {
            "total_revenue": total_revenue,
            "record_count": record_count,
            "revenue_by_source": by_source,
            "avg_transaction": total_revenue / record_count if record_count > 0 else 0,
        }