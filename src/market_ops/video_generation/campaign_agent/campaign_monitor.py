from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class CampaignStatus:
    campaign_id: str
    platform: str
    status: str
    budget: float
    spend: float
    impressions: int = 0
    clicks: int = 0
    installs: int = 0
    purchases: int = 0
    revenue: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceAlert:
    alert_id: str
    campaign_id: str
    type: str
    severity: str
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class CampaignMonitor:
    def __init__(self):
        self.campaigns: Dict[str, CampaignStatus] = {}
        self.alerts: List[PerformanceAlert] = []

    def update_status(self, campaign_id: str, data: Dict[str, Any]) -> CampaignStatus:
        status = CampaignStatus(
            campaign_id=campaign_id,
            platform=data.get("platform", ""),
            status=data.get("status", "active"),
            budget=data.get("budget", 0.0),
            spend=data.get("spend", 0.0),
            impressions=data.get("impressions", 0),
            clicks=data.get("clicks", 0),
            installs=data.get("installs", 0),
            purchases=data.get("purchases", 0),
            revenue=data.get("revenue", 0.0),
        )
        self.campaigns[campaign_id] = status
        return status

    def check_alerts(self, campaign_id: str) -> List[PerformanceAlert]:
        status = self.campaigns.get(campaign_id)
        if not status:
            return []

        alerts = []
        ctr = status.clicks / status.impressions if status.impressions > 0 else 0

        if status.spend > 300 and status.purchases == 0:
            alerts.append(PerformanceAlert(
                alert_id=f"alert_{hash(campaign_id + 'no_purchase') % 10000:04d}",
                campaign_id=campaign_id,
                type="NO_PURCHASE",
                severity="CRITICAL",
                message=f"Spend ${status.spend:.0f} with 0 purchases",
                metrics={"spend": status.spend, "purchases": status.purchases},
            ))

        if ctr < 0.01 and status.impressions > 1000:
            alerts.append(PerformanceAlert(
                alert_id=f"alert_{hash(campaign_id + 'low_ctr') % 10000:04d}",
                campaign_id=campaign_id,
                type="LOW_CTR",
                severity="WARNING",
                message=f"CTR {ctr:.2%} below 1% threshold",
                metrics={"ctr": ctr, "impressions": status.impressions},
            ))

        if status.installs > 0:
            cpi = status.spend / status.installs
            if cpi > 5.0:
                alerts.append(PerformanceAlert(
                    alert_id=f"alert_{hash(campaign_id + 'high_cpi') % 10000:04d}",
                    campaign_id=campaign_id,
                    type="HIGH_CPI",
                    severity="WARNING",
                    message=f"CPI ${cpi:.2f} above $5 threshold",
                    metrics={"cpi": cpi, "installs": status.installs},
                ))

        self.alerts.extend(alerts)
        return alerts

    def get_status(self, campaign_id: str) -> Optional[CampaignStatus]:
        return self.campaigns.get(campaign_id)

    def get_all_alerts(self) -> List[PerformanceAlert]:
        return self.alerts

    def monitor_demo(self) -> List[PerformanceAlert]:
        self.update_status("campaign_001", {
            "platform": "meta",
            "status": "active",
            "budget": 500.0,
            "spend": 350.0,
            "impressions": 5000,
            "clicks": 200,
            "installs": 100,
            "purchases": 0,
            "revenue": 0.0,
        })
        return self.check_alerts("campaign_001")
