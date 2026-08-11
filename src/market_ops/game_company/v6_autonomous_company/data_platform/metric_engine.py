from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
from .event_collector import EventCollector, EventType, EventRecord


@dataclass
class MetricResult:
    metric_name: str
    value: float
    period: str
    start_date: str
    end_date: str
    breakdown: Dict[str, float] = field(default_factory=dict)


class MetricEngine:
    def __init__(self, event_collector: EventCollector = None):
        self.event_collector = event_collector or EventCollector()
        self._cached_metrics: Dict[str, MetricResult] = {}

    def calculate_dau(self, date_str: str = None) -> MetricResult:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        value = self.event_collector.get_dau(date_str)
        return MetricResult(
            metric_name="dau",
            value=value,
            period="daily",
            start_date=date_str,
            end_date=date_str,
        )

    def calculate_retention(self, cohort_date: str, day: int = 1) -> MetricResult:
        events = self.event_collector.get_events_by_date(cohort_date)
        cohort_users = set(e.user_id for e in events if e.event_type == EventType.INSTALL)

        if not cohort_users:
            return MetricResult(
                metric_name=f"d{day}_retention",
                value=0.0,
                period=f"day_{day}",
                start_date=cohort_date,
                end_date=cohort_date,
            )

        target_date = (datetime.strptime(cohort_date, "%Y-%m-%d") + timedelta(days=day)).strftime("%Y-%m-%d")
        target_events = self.event_collector.get_events_by_date(target_date)
        returning_users = set(e.user_id for e in target_events) & cohort_users

        retention = len(returning_users) / len(cohort_users) if cohort_users else 0

        return MetricResult(
            metric_name=f"d{day}_retention",
            value=round(retention, 4),
            period=f"day_{day}",
            start_date=cohort_date,
            end_date=target_date,
        )

    def calculate_revenue(self, start_date: str = None, end_date: str = None) -> MetricResult:
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        purchase_events = self.event_collector.get_events_by_type(EventType.PURCHASE)
        ad_revenue_events = self.event_collector.get_events_by_type(EventType.AD_REVENUE)

        iap_revenue = sum(
            e.properties.get("revenue", 0)
            for e in purchase_events
            if start_date <= e.timestamp.strftime("%Y-%m-%d") <= end_date
        )
        ad_revenue = sum(
            e.properties.get("revenue", 0)
            for e in ad_revenue_events
            if start_date <= e.timestamp.strftime("%Y-%m-%d") <= end_date
        )
        total = iap_revenue + ad_revenue

        return MetricResult(
            metric_name="revenue",
            value=round(total, 2),
            period="custom",
            start_date=start_date,
            end_date=end_date,
            breakdown={"iap_revenue": round(iap_revenue, 2), "ad_revenue": round(ad_revenue, 2)},
        )

    def calculate_arpdau(self, date_str: str = None) -> MetricResult:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        revenue_result = self.calculate_revenue(date_str, date_str)
        dau_result = self.calculate_dau(date_str)
        arpdau = revenue_result.value / dau_result.value if dau_result.value > 0 else 0

        return MetricResult(
            metric_name="arpdau",
            value=round(arpdau, 4),
            period="daily",
            start_date=date_str,
            end_date=date_str,
        )

    def calculate_ltv(self, cohort_date: str, day: int = 30) -> MetricResult:
        purchase_events = self.event_collector.get_events_by_type(EventType.PURCHASE)
        cohort_installs = [
            e for e in self.event_collector.get_events_by_type(EventType.INSTALL)
            if e.timestamp.strftime("%Y-%m-%d") == cohort_date
        ]
        cohort_users = set(e.user_id for e in cohort_installs)

        if not cohort_users:
            return MetricResult(
                metric_name=f"d{day}_ltv",
                value=0.0,
                period=f"day_{day}",
                start_date=cohort_date,
                end_date=cohort_date,
            )

        end_date = (datetime.strptime(cohort_date, "%Y-%m-%d") + timedelta(days=day)).strftime("%Y-%m-%d")
        cohort_revenue = sum(
            e.properties.get("revenue", 0)
            for e in purchase_events
            if e.user_id in cohort_users
            and cohort_date <= e.timestamp.strftime("%Y-%m-%d") <= end_date
        )

        ltv = cohort_revenue / len(cohort_users) if cohort_users else 0

        return MetricResult(
            metric_name=f"d{day}_ltv",
            value=round(ltv, 4),
            period=f"day_{day}",
            start_date=cohort_date,
            end_date=end_date,
        )

    def calculate_roas(self, spend: float, cohort_date: str, day: int = 30) -> MetricResult:
        ltv_result = self.calculate_ltv(cohort_date, day)
        installs = len([
            e for e in self.event_collector.get_events_by_type(EventType.INSTALL)
            if e.timestamp.strftime("%Y-%m-%d") == cohort_date
        ])
        total_revenue = ltv_result.value * installs
        roas = total_revenue / spend if spend > 0 else 0

        return MetricResult(
            metric_name=f"d{day}_roas",
            value=round(roas, 4),
            period=f"day_{day}",
            start_date=cohort_date,
            end_date=(datetime.strptime(cohort_date, "%Y-%m-%d") + timedelta(days=day)).strftime("%Y-%m-%d"),
            breakdown={"spend": spend, "total_revenue": round(total_revenue, 2)},
        )

    def get_all_metrics(self, date_str: str = None) -> Dict[str, Any]:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        return {
            "dau": self.calculate_dau(date_str).value,
            "arpdau": self.calculate_arpdau(date_str).value,
            "revenue": self.calculate_revenue(date_str, date_str).value,
        }
