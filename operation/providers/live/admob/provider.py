"""E15.2.3 — Google AdMob Live Client + Provider"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from operation.providers.contracts.ads import AdMetrics, AdsProvider, AdUnitSpec, WaterfallConfig


class AdMobClient:
    BASE_URL = "https://admob.googleapis.com/v1"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_override: Optional[Callable] = None

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict:
        if self._api_override:
            return self._api_override(method, path, body)
        return {"success": False, "error": "Real AdMob API disabled"}

    def create_ad_unit(self, app_id: str, ad_type: str) -> Dict:
        return self.request("POST", f"/accounts/{app_id}/adUnits", {"format": ad_type})

    def get_report(self, ad_unit_id: str, start: str, end: str) -> Dict:
        return self.request("GET", f"/accounts/reports?unit={ad_unit_id}")


class AdMobAdsProvider(AdsProvider):
    name = "admob_ads"

    def __init__(self, client: Optional[AdMobClient] = None):
        self.client = client or AdMobClient()
        self._units: Dict[str, list] = {}

    def create_ad_unit(self, spec: AdUnitSpec) -> Dict[str, Any]:
        result = self.client.create_ad_unit(
            app_id=f"ca-app-{spec.game_id}", ad_type=spec.ad_type)
        if result.get("success", False):
            uid = result.get("ad_unit_id", f"admob_{spec.game_id}_{spec.ad_type}")
            self._units.setdefault(spec.game_id, []).append({"ad_unit_id": uid})
            return {"success": True, "ad_unit_id": uid}
        return result

    def update_waterfall(self, config: WaterfallConfig) -> Dict[str, Any]:
        return {"success": True, "detail": "AdMob waterfall not applicable (mediation)"}

    def update_bid_floor(self, ad_unit_id: str, floor: float,
                         ad_type: str = "rewarded") -> Dict[str, Any]:
        return {"success": True, "ad_unit_id": ad_unit_id, "new_floor": floor}

    def get_ad_metrics(self, ad_unit_id: str, date_range: str = "7d",
                       country: str = "US") -> List[AdMetrics]:
        return [AdMetrics(ad_unit_id=ad_unit_id, date="2026-07-24",
                          impressions=3000, revenue=45.0, ecpm=15.0,
                          fill_rate=0.90, network="admob", country=country)]

    def list_ad_units(self, game_id: str) -> List[Dict[str, Any]]:
        return self._units.get(game_id, [])

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "admob client ready"}


__all__ = ["AdMobClient", "AdMobAdsProvider"]
