from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class ConnectorStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


@dataclass
class ConnectorResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    rate_limit_remaining: int = 0
    rate_limit_reset: Optional[datetime] = None


@dataclass
class CampaignMetrics:
    campaign_id: str
    campaign_name: str
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    ctr: float = 0.0
    cvr: float = 0.0
    cpi: float = 0.0
    cpm: float = 0.0
    revenue: float = 0.0
    roas: float = 0.0
    purchases: int = 0
    d1_revenue: float = 0.0
    d7_revenue: float = 0.0
    d30_revenue: float = 0.0
    date: str = ""


class BaseConnector:
    def __init__(self, access_token: str = None, account_id: str = None):
        self.access_token = access_token
        self.account_id = account_id
        self.status = ConnectorStatus.DISCONNECTED
        self.rate_limit_remaining = 1000
        self.rate_limit_reset = datetime.now() + timedelta(hours=1)

    def connect(self) -> bool:
        self.status = ConnectorStatus.CONNECTED
        return True

    def disconnect(self):
        self.status = ConnectorStatus.DISCONNECTED

    def is_connected(self) -> bool:
        return self.status == ConnectorStatus.CONNECTED

    def _check_rate_limit(self) -> bool:
        if self.rate_limit_remaining <= 0:
            if datetime.now() >= self.rate_limit_reset:
                self.rate_limit_remaining = 1000
                self.rate_limit_reset = datetime.now() + timedelta(hours=1)
                return True
            return False
        self.rate_limit_remaining -= 1
        return True

    def _make_result(self, success: bool, data: Dict = None, error: str = None) -> ConnectorResult:
        return ConnectorResult(
            success=success,
            data=data or {},
            error=error,
            rate_limit_remaining=self.rate_limit_remaining,
            rate_limit_reset=self.rate_limit_reset,
        )
