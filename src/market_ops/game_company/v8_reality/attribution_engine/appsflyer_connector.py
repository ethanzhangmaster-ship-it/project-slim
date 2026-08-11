from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class AppsFlyerInstall:
    install_id: str
    user_id: str
    install_time: datetime
    network: str
    campaign: str
    ad_group: Optional[str] = None
    creative: Optional[str] = None
    country: Optional[str] = None
    device_type: Optional[str] = None
    os_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "install_id": self.install_id,
            "user_id": self.user_id,
            "install_time": self.install_time.isoformat(),
            "network": self.network,
            "campaign": self.campaign,
            "ad_group": self.ad_group,
            "creative": self.creative,
            "country": self.country,
            "device_type": self.device_type,
            "os_version": self.os_version,
        }


@dataclass
class AppsFlyerEvent:
    event_id: str
    event_name: str
    timestamp: datetime
    user_id: str
    install_id: str
    revenue: float = 0.0
    currency: str = "USD"
    campaign: Optional[str] = None
    country: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "install_id": self.install_id,
            "revenue": self.revenue,
            "currency": self.currency,
            "campaign": self.campaign,
            "country": self.country,
        }


@dataclass
class AppsFlyerRevenue:
    transaction_id: str
    timestamp: datetime
    user_id: str
    install_id: str
    revenue: float
    currency: str = "USD"
    event_name: Optional[str] = None
    campaign: Optional[str] = None
    network: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "install_id": self.install_id,
            "revenue": self.revenue,
            "currency": self.currency,
            "event_name": self.event_name,
            "campaign": self.campaign,
            "network": self.network,
        }


class AppsFlyerConnector:
    def __init__(self):
        self._connected = False
        self._app_ids: Dict[str, bool] = {}

    def connect(self) -> bool:
        self._connected = True
        return True

    def get_installs(self, app_id: str) -> List[AppsFlyerInstall]:
        if not self._connected:
            return []

        now = datetime.now()
        networks = ["Google Ads", "Meta", "TikTok", "Apple Search Ads"]
        installs = [
            AppsFlyerInstall(
                install_id=f"install_{i}",
                user_id=f"user_{i}",
                install_time=now,
                network=networks[i % len(networks)],
                campaign=f"campaign_{i % 3}",
                country="US" if i % 3 == 0 else "CN" if i % 3 == 1 else "JP",
                device_type="iOS" if i % 2 == 0 else "Android",
                os_version="16.0" if i % 2 == 0 else "13.0",
            )
            for i in range(15)
        ]
        return installs

    def get_events(self, app_id: str) -> List[AppsFlyerEvent]:
        if not self._connected:
            return []

        now = datetime.now()
        event_names = ["install", "first_open", "purchase", "level_complete"]
        events = [
            AppsFlyerEvent(
                event_id=f"evt_{i}",
                event_name=event_names[i % len(event_names)],
                timestamp=now,
                user_id=f"user_{i}",
                install_id=f"install_{i}",
                revenue=4.99 if event_names[i % len(event_names)] == "purchase" else 0.0,
                campaign=f"campaign_{i % 2}",
            )
            for i in range(20)
        ]
        return events

    def get_revenue(self, app_id: str) -> List[AppsFlyerRevenue]:
        if not self._connected:
            return []

        now = datetime.now()
        revenues = [
            AppsFlyerRevenue(
                transaction_id=f"txn_{i}",
                timestamp=now,
                user_id=f"user_{i}",
                install_id=f"install_{i}",
                revenue=2.99 + i * 1.5,
                event_name="purchase",
                campaign=f"campaign_{i % 3}",
                network="Google Ads" if i % 2 == 0 else "Meta",
            )
            for i in range(8)
        ]
        return revenues

    def get_attribution(self, app_id: str) -> List[AppsFlyerInstall]:
        if not self._connected:
            return []

        return self.get_installs(app_id)

    def sync_data(self) -> Dict[str, Any]:
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        return {
            "success": True,
            "installs_synced": 150,
            "events_synced": 200,
            "revenue_synced": 80,
            "attribution_synced": 150,
            "timestamp": datetime.now().isoformat(),
        }