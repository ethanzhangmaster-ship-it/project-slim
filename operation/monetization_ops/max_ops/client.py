"""
E15.2.3 — Mock MAX Operation Client
Sample-backed. create_app, create_ad_unit, configure_waterfall, read_revenue.
"""
from typing import Dict, List


class MockMaxOperationClient:
    def __init__(self):
        self._apps: Dict[str, dict] = {}
        self._units: Dict[str, List[dict]] = {}

    def create_app(self, game_id: str, app_id: str = "", package_name: str = "") -> dict:
        app = {"game_id": game_id, "app_id": app_id or f"max_app_{game_id}",
               "package": package_name, "status": "active"}
        self._apps[game_id] = app
        return {"success": True, "app_id": app["app_id"]}

    def create_ad_unit(self, game_id: str, ad_unit_id: str, fmt: str,
                       platform: str, placement: str) -> dict:
        unit = {"ad_unit_id": ad_unit_id, "format": fmt,
                "platform": platform, "placement": placement, "status": "active"}
        self._units.setdefault(game_id, []).append(unit)
        return {"success": True, "ad_unit_id": ad_unit_id}

    def configure_waterfall(self, game_id: str, ad_unit_id: str,
                            networks: List[str], floor: float) -> dict:
        for u in self._units.get(game_id, []):
            if u["ad_unit_id"] == ad_unit_id:
                u["waterfall"] = networks
                u["floor"] = floor
                return {"success": True, "waterfall": networks, "floor": floor}
        # auto-create unit if not found
        unit = {"ad_unit_id": ad_unit_id, "format": "rewarded_video",
                "platform": "android", "placement": "auto",
                "waterfall": networks, "floor": floor, "status": "active"}
        self._units.setdefault(game_id, []).append(unit)
        return {"success": True, "waterfall": networks, "floor": floor}

    def read_revenue(self, game_id: str) -> dict:
        return {"game_id": game_id, "total_revenue": 15480.0,
                "ecpm": 7.94, "fill_rate": 0.95,
                "impressions": 1_950_000}

    def read_ecpm(self, game_id: str, fmt: str = "") -> dict:
        return {"game_id": game_id, "format": fmt or "reward",
                "ecpm": 14.2, "fill_rate": 0.92}

    def get_units(self, game_id: str) -> List[dict]:
        return self._units.get(game_id, [])

    def health_check(self) -> dict:
        return {"status": "healthy", "services": "all_available"}
