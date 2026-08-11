"""E15.2.8 — Monetization Orchestrator (detect gaps → plan → execute → verify → report)"""
from dataclasses import dataclass, field
from typing import List

from operation.monetization_ops.ads.agent import AdsAgent, AdIntegrationReport
from operation.monetization_ops.config.agent import ConfigAgent, MonetizationConfig
from operation.monetization_ops.iap.provider import IAPOperationProvider
from operation.monetization_ops.max_ops.provider import MaxOperationProvider
from operation.monetization_ops.monitor.agent import MonitorAgent, MonetizationHealthReport
from operation.monetization_ops.providers.models import (
    MonetizationOpChange, OP_CREATE, OP_UPDATE, OP_FETCH, OP_HEALTH_CHECK,
    AD_REWARDED, IAP_CONSUMABLE, IAP_SUBSCRIPTION, IAP_NON_CONSUMABLE,
)
from operation.monetization_ops.revenue.agent import RevenueAgent, RevenueReport


@dataclass
class MonetizationReport:
    game_id: str
    ad_report: dict = field(default_factory=dict)
    iap_report: dict = field(default_factory=dict)
    revenue: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    health: dict = field(default_factory=dict)
    tasks: List[str] = field(default_factory=list)
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id, "status": self.status,
            "ad_report": self.ad_report, "iap_report": self.iap_report,
            "revenue": self.revenue, "config": self.config,
            "health": self.health, "tasks": self.tasks,
        }


class MonetizationOrchestrator:
    def __init__(self, max_prov: MaxOperationProvider = None,
                 iap_prov: IAPOperationProvider = None,
                 ads_agent: AdsAgent = None,
                 config_agent: ConfigAgent = None,
                 revenue_agent: RevenueAgent = None,
                 monitor_agent: MonitorAgent = None):
        self.max = max_prov or MaxOperationProvider()
        self.iap = iap_prov or IAPOperationProvider()
        self.ads = ads_agent or AdsAgent()
        self.config = config_agent or ConfigAgent()
        self.revenue = revenue_agent or RevenueAgent()
        self.monitor = monitor_agent or MonitorAgent()

    def setup_game(self, game_id: str, package_name: str = "",
                   platforms: list = None) -> MonetizationReport:
        report = MonetizationReport(game_id=game_id)
        platforms = platforms or ["android", "ios"]

        # 1. detect ad gaps → create ad units
        report.tasks.append("detect_ad_gaps")
        ad_units = self.ads.create_all(game_id, network="max")
        ad_report = self.ads.validate(ad_units)
        report.ad_report = ad_report.to_dict()

        # 2. MAX create app
        report.tasks.append("max_create_app")
        ch = MonetizationOpChange(
            target=f"{game_id}/max/create", operation=OP_CREATE,
            provider="max_ops", game_id=game_id,
            new={"package_name": package_name or f"com.fake.{game_id}"})
        r = self.max.apply_change(ch)
        if not r.success:
            report.status = "failed"; return report

        # 3. MAX create ad units (rewarded, interstitial, banner)
        for unit in ad_units:
            report.tasks.append(f"max_create_{unit.format}")
            ch = MonetizationOpChange(
                target=f"{game_id}/max/ad_unit", operation=OP_CREATE,
                provider="max_ops", game_id=game_id,
                new={"ad_unit_id": unit.ad_unit_id, "format": unit.format,
                     "platform": unit.platform, "placement": unit.placement})
            self.max.apply_change(ch)

        # 4. IAP create products
        report.tasks.append("iap_create_products")
        products = [
            ("coin100", IAP_CONSUMABLE, 0.99),
            ("vip_monthly", IAP_SUBSCRIPTION, 9.99),
            ("remove_ads", IAP_NON_CONSUMABLE, 3.99),
        ]
        iap_results = []
        for pid, ptype, price in products:
            ch = MonetizationOpChange(
                target=f"{game_id}/iap/create", operation=OP_CREATE,
                provider="iap_ops", game_id=game_id,
                new={"product_id": f"com.{game_id}.{pid}",
                     "product_type": ptype, "price": price,
                     "platform": "android", "title": pid})
            r = self.iap.apply_change(ch)
            iap_results.append({"product_id": pid, "success": r.success})
        report.iap_report = {"products": iap_results}

        # 5. config
        report.tasks.append("build_config")
        cfg = self.config.build_default(game_id)
        report.config = cfg.to_dict()

        # 6. revenue snapshot
        report.tasks.append("revenue_snapshot")
        rev = self.revenue.aggregate(game_id, [])
        report.revenue = rev.to_dict()

        # 7. health check
        report.tasks.append("health_check")
        h = self.monitor.check(game_id,
                               self.max.client.read_revenue(game_id),
                               self.iap.client.check_status(game_id, f"com.{game_id}.coin100"))
        report.health = h.to_dict()

        report.status = "setup_complete"
        return report
