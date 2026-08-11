"""
E15.2.3 — Simulation Ads Provider

Sample-backed AdsProvider returning deterministic fake data.
"""
from __future__ import annotations

from typing import Any, Dict, List

from operation.providers.contracts.ads import (
    AdMetrics, AdsProvider, AdUnitSpec, WaterfallConfig,
)


class SimulationAdsProvider(AdsProvider):
    """In-memory AdsProvider with sample ad units and metrics."""

    name = "simulation_ads"

    def __init__(self):
        self._units: Dict[str, list] = {}     # game_id → [unit dicts]
        self._waterfalls: Dict[str, dict] = {}
        self._metrics_store: Dict[str, list] = {}

    def create_ad_unit(self, spec: AdUnitSpec) -> Dict[str, Any]:
        unit_id = f"sim_{spec.game_id}_{spec.ad_type}_{spec.platform}"
        unit = {
            "ad_unit_id": unit_id,
            "game_id": spec.game_id,
            "platform": spec.platform,
            "ad_type": spec.ad_type,
            "network": spec.network,
            "status": "active",
        }
        self._units.setdefault(spec.game_id, []).append(unit)
        return {"success": True, "ad_unit_id": unit_id}

    def update_waterfall(self, config: WaterfallConfig) -> Dict[str, Any]:
        self._waterfalls[config.ad_unit_id] = {
            "networks": config.networks, "country": config.country,
        }
        return {"success": True, "ad_unit_id": config.ad_unit_id}

    def update_bid_floor(self, ad_unit_id: str, floor: float,
                         ad_type: str = "rewarded") -> Dict[str, Any]:
        return {"success": True, "ad_unit_id": ad_unit_id, "new_floor": floor}

    def get_ad_metrics(self, ad_unit_id: str, date_range: str = "7d",
                       country: str = "US") -> List[AdMetrics]:
        # Return sample metrics
        return [
            AdMetrics(
                ad_unit_id=ad_unit_id, date=f"2026-07-{20+d:02d}",
                impressions=5000 + d * 100,
                revenue=round(50.0 + d * 2.5, 2),
                ecpm=round(10.0 + d * 0.3, 2),
                fill_rate=round(0.88 + d * 0.01, 2),
                network="max", country=country,
            )
            for d in range(7)
        ]

    def list_ad_units(self, game_id: str) -> List[Dict[str, Any]]:
        return self._units.get(game_id, [])

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "simulation ads healthy"}


__all__ = ["SimulationAdsProvider"]
