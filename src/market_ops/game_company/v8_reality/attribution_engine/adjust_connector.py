from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class AdjustEvent:
    event_id: str
    event_name: str
    timestamp: datetime
    user_id: str
    revenue: float = 0.0
    currency: str = "USD"
    campaign: Optional[str] = None
    ad_group: Optional[str] = None
    creative: Optional[str] = None
    country: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "revenue": self.revenue,
            "currency": self.currency,
            "campaign": self.campaign,
            "ad_group": self.ad_group,
            "creative": self.creative,
            "country": self.country,
        }


@dataclass
class AdjustRetention:
    cohort_date: datetime
    retention_day: int
    retention_rate: float
    user_count: int
    total_users: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_date": self.cohort_date.isoformat(),
            "retention_day": self.retention_day,
            "retention_rate": self.retention_rate,
            "user_count": self.user_count,
            "total_users": self.total_users,
        }


@dataclass
class AdjustRevenue:
    transaction_id: str
    timestamp: datetime
    user_id: str
    revenue: float
    currency: str = "USD"
    event_name: Optional[str] = None
    campaign: Optional[str] = None
    country: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "revenue": self.revenue,
            "currency": self.currency,
            "event_name": self.event_name,
            "campaign": self.campaign,
            "country": self.country,
        }


@dataclass
class AttributionData:
    attribution_id: str
    user_id: str
    network: str
    campaign: str
    ad_group: Optional[str] = None
    creative: Optional[str] = None
    country: Optional[str] = None
    install_time: Optional[datetime] = None
    attribution_time: Optional[datetime] = None
    cost: float = 0.0
    cost_currency: str = "USD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attribution_id": self.attribution_id,
            "user_id": self.user_id,
            "network": self.network,
            "campaign": self.campaign,
            "ad_group": self.ad_group,
            "creative": self.creative,
            "country": self.country,
            "install_time": self.install_time.isoformat() if self.install_time else None,
            "attribution_time": self.attribution_time.isoformat() if self.attribution_time else None,
            "cost": self.cost,
            "cost_currency": self.cost_currency,
        }


class AdjustConnector:
    def __init__(self):
        self._connected = False
        self._app_tokens: Dict[str, bool] = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_events(self, app_token: str) -> List[AdjustEvent]:
        if not self._connected:
            return []

        now = datetime.now()
        events = [
            AdjustEvent(
                event_id=f"evt_{i}",
                event_name="install" if i == 0 else "purchase",
                timestamp=now,
                user_id=f"user_{i}",
                revenue=9.99 * i,
                campaign=f"campaign_{i % 3}",
                country="US" if i % 2 == 0 else "CN",
            )
            for i in range(10)
        ]
        return events

    def get_retention(self, app_token: str) -> List[AdjustRetention]:
        if not self._connected:
            return []

        today = datetime.now().date()
        retentions = [
            AdjustRetention(
                cohort_date=datetime(today.year, today.month, today.day - i),
                retention_day=i,
                retention_rate=max(0.1, 1.0 - i * 0.15),
                user_count=1000 - i * 100,
                total_users=1000,
            )
            for i in range(7)
        ]
        return retentions

    def get_revenue(self, app_token: str) -> List[AdjustRevenue]:
        if not self._connected:
            return []

        now = datetime.now()
        revenues = [
            AdjustRevenue(
                transaction_id=f"txn_{i}",
                timestamp=now,
                user_id=f"user_{i}",
                revenue=4.99 + i * 2.5,
                event_name="purchase",
                campaign=f"campaign_{i % 2}",
            )
            for i in range(5)
        ]
        return revenues

    def get_attribution_data(self, app_token: str) -> List[AttributionData]:
        if not self._connected:
            return []

        now = datetime.now()
        networks = ["google", "facebook", "tiktok", "apple"]
        attributions = [
            AttributionData(
                attribution_id=f"attr_{i}",
                user_id=f"user_{i}",
                network=networks[i % len(networks)],
                campaign=f"campaign_{i % 3}",
                country="US" if i % 3 == 0 else "CN" if i % 3 == 1 else "JP",
                install_time=now,
                attribution_time=now,
                cost=1.2 + i * 0.3,
            )
            for i in range(8)
        ]
        return attributions

    def sync_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        return {
            "success": True,
            "events_synced": 100,
            "retention_synced": 7,
            "revenue_synced": 50,
            "attribution_synced": 80,
            "timestamp": datetime.now().isoformat(),
        }