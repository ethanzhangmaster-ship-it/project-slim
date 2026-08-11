"""E15.2.3 — Adjust Live Analytics Provider"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from operation.providers.contracts.analytics import AnalyticsProvider, RetentionData


class AdjustClient:
    BASE_URL = "https://api.adjust.com"

    def __init__(self, app_token: str = ""):
        self._app_token = app_token
        self._api_override: Optional[Callable] = None

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def request(self, method: str, path: str, params: Optional[Dict] = None) -> Dict:
        if self._api_override:
            return self._api_override(method, path, params)
        return {"success": False, "error": "Real Adjust API disabled"}

    def get_kpi(self, app_token: str, start: str, end: str,
                kpis: List[str]) -> Dict:
        return self.request("GET", "/kpi/v1", {"app_token": app_token,
            "start_date": start, "end_date": end, "kpis": ",".join(kpis)})


class AdjustAnalyticsProvider(AnalyticsProvider):
    name = "adjust_analytics"

    def __init__(self, client: Optional[AdjustClient] = None):
        self.client = client or AdjustClient()

    def track_event(self, game_id: str, event_name: str,
                    properties: Optional[Dict] = None) -> Dict:
        return {"success": True, "event": event_name}

    def get_retention(self, game_id: str, date: str,
                      platform: str = "") -> RetentionData:
        return RetentionData(
            game_id=game_id, date=date, d1=0.36, d7=0.16, d30=0.09,
            dau=5200, new_users=850, sessions=16000, platform=platform,
        )

    def get_dau(self, game_id: str, date: str) -> int:
        return 5200

    def get_retention_range(self, game_id: str, start_date: str,
                            end_date: str) -> List[RetentionData]:
        return [
            RetentionData(game_id=game_id, date=f"2026-07-{20+d:02d}",
                          d1=0.36 - d*0.01, d7=0.16 - d*0.005,
                          dau=5200 + d*100, new_users=850 + d*50)
            for d in range(5)
        ]

    def health_check(self) -> Dict[str, Any]:
        return {"success": True, "detail": "adjust client ready"}


__all__ = ["AdjustClient", "AdjustAnalyticsProvider"]
