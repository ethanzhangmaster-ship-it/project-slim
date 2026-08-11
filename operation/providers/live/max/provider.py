"""
E15.2.3 — MAX Live Ads Provider

AdsProvider implementation backed by MaxClient (real AppLovin MAX API).
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from operation.providers.contracts.ads import (
    AdMetrics, AdsProvider, AdUnitSpec, WaterfallConfig,
)
from operation.providers.live.max.client import MaxClient


class MaxAdsProvider(AdsProvider):
    """Real AppLovin MAX AdsProvider. Implements AdsProvider contract."""

    name = "max_ads"

    def __init__(self, client: Optional[MaxClient] = None,
                 api_key: str = "", account_id: str = ""):
        self.client = client or MaxClient(api_key=api_key, account_id=account_id)
        self._created_units: Dict[str, list] = {}

    def create_ad_unit(self, spec: AdUnitSpec) -> Dict[str, Any]:
        result = self.client.create_ad_unit(
            app_id=f"app_{spec.game_id}",
            ad_type=spec.ad_type,
            name=spec.placement_name or f"{spec.game_id}_{spec.ad_type}",
        )
        if result.get("success", False):
            unit_id = result.get("ad_unit_id", f"max_{spec.game_id}_{spec.ad_type}")
            self._created_units.setdefault(spec.game_id, []).append({
                "ad_unit_id": unit_id, "ad_type": spec.ad_type,
            })
            return {"success": True, "ad_unit_id": unit_id}
        return result

    def update_waterfall(self, config: WaterfallConfig) -> Dict[str, Any]:
        return self.client.update_waterfall(
            config.ad_unit_id,
            [{"network": n["network"], "priority": n.get("priority", i)}
             for i, n in enumerate(config.networks)],
        )

    def update_bid_floor(self, ad_unit_id: str, floor: float,
                         ad_type: str = "rewarded") -> Dict[str, Any]:
        return self.client.update_bid_floor(ad_unit_id, floor)

    def get_ad_metrics(self, ad_unit_id: str, date_range: str = "7d",
                       country: str = "US") -> List[AdMetrics]:
        result = self.client.get_ecpm(ad_unit_id, days=7)
        if not result.get("success", False):
            return []
        data = result.get("data", [])
        return [
            AdMetrics(
                ad_unit_id=ad_unit_id,
                date=d.get("date", ""),
                impressions=d.get("impressions", 0),
                revenue=d.get("revenue", 0.0),
                ecpm=d.get("ecpm", 0.0),
                fill_rate=d.get("fill_rate", 0.0),
                network="max", country=country,
            )
            for d in data
        ]

    def list_ad_units(self, game_id: str) -> List[Dict[str, Any]]:
        return self._created_units.get(game_id, [])

    def health_check(self) -> Dict[str, Any]:
        result = self.client.request("GET", "/health")
        return {"success": result.get("success", False),
                "detail": result.get("detail", "max client check")}


__all__ = ["MaxAdsProvider"]
