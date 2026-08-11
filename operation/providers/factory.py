"""
E15.2.3 — Provider Factory

Reads environment.yaml and instantiates the correct provider
(simulation or live) for each contract type.

monetization_ops calls: factory.get_ads() — never imports max_sdk directly.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

from operation.providers.contracts.ads import AdsProvider
from operation.providers.contracts.analytics import AnalyticsProvider
from operation.providers.contracts.config import ConfigProvider
from operation.providers.contracts.iap import IAPProvider
from operation.providers.contracts.revenue import RevenueProvider
from operation.providers.simulation.sim_ads import SimulationAdsProvider
from operation.providers.simulation.sim_analytics import SimulationAnalyticsProvider
from operation.providers.simulation.sim_config import SimulationConfigProvider
from operation.providers.simulation.sim_iap import SimulationIAPProvider
from operation.providers.simulation.sim_revenue import SimulationRevenueProvider
from operation.providers.live.max.provider import MaxAdsProvider
from operation.providers.live.admob.provider import AdMobAdsProvider
from operation.providers.live.adjust.provider import AdjustAnalyticsProvider
from operation.providers.live.appstore.provider import AppStoreIAPProvider
from operation.providers.live.googleplay.provider import GooglePlayIAPProvider


class ProviderFactory:
    """Central provider registry.

    Configure via environment.yaml:
        providers:
          ads: {type: simulation}
          revenue: {type: simulation}
          iap: {type: simulation}
          config: {type: simulation}
          analytics: {type: simulation}

    Production:
        providers:
          ads: {type: max, api_key: xxx, account_id: xxx}
          revenue: {type: max}
          iap: {type: appstore}
    """

    _instance: Optional["ProviderFactory"] = None
    _providers: Dict[str, Any] = {}

    def __init__(self, config_path: str = ""):
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(__file__), "environment.yaml")
        self._config = self._load_config(config_path)
        self._providers = {}

    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            return {"providers": {}}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"providers": {}}

    @classmethod
    def reset(cls):
        """Reset singleton for testing."""
        cls._instance = None
        cls._providers = {}

    def _get_config(self, name: str) -> Dict[str, Any]:
        return self._config.get("providers", {}).get(name, {})

    # ------------------------------------------------------------------ #
    # Provider accessors
    # ------------------------------------------------------------------ #
    def get_ads(self) -> AdsProvider:
        if "ads" not in self._providers:
            cfg = self._get_config("ads")
            ptype = cfg.get("type", "simulation")
            if ptype == "max":
                provider = MaxAdsProvider(
                    api_key=cfg.get("api_key", ""),
                    account_id=cfg.get("account_id", ""),
                )
            elif ptype == "admob":
                provider = AdMobAdsProvider()
            else:
                provider = SimulationAdsProvider()
            self._providers["ads"] = provider
        return self._providers["ads"]

    def get_revenue(self) -> RevenueProvider:
        if "revenue" not in self._providers:
            ptype = self._get_config("revenue").get("type", "simulation")
            provider = SimulationRevenueProvider()
            self._providers["revenue"] = provider
        return self._providers["revenue"]

    def get_iap(self) -> IAPProvider:
        if "iap" not in self._providers:
            cfg = self._get_config("iap")
            ptype = cfg.get("type", "simulation")
            if ptype == "appstore":
                provider = AppStoreIAPProvider()
            elif ptype == "googleplay":
                provider = GooglePlayIAPProvider()
            else:
                provider = SimulationIAPProvider()
            self._providers["iap"] = provider
        return self._providers["iap"]

    def get_config(self) -> ConfigProvider:
        if "config" not in self._providers:
            provider = SimulationConfigProvider()
            self._providers["config"] = provider
        return self._providers["config"]

    def get_analytics(self) -> AnalyticsProvider:
        if "analytics" not in self._providers:
            cfg = self._get_config("analytics")
            ptype = cfg.get("type", "simulation")
            if ptype == "adjust":
                provider = AdjustAnalyticsProvider()
            else:
                provider = SimulationAnalyticsProvider()
            self._providers["analytics"] = provider
        return self._providers["analytics"]

    def all_providers(self) -> Dict[str, Any]:
        return {
            "ads": self.get_ads(),
            "revenue": self.get_revenue(),
            "iap": self.get_iap(),
            "config": self.get_config(),
            "analytics": self.get_analytics(),
        }


__all__ = ["ProviderFactory"]
