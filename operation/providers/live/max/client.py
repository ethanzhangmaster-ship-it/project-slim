"""
E15.2.3 — AppLovin MAX Live Client

HTTP client for AppLovin MAX API.
Real Report API: GET https://r.applovin.com/maxReport?api_key=...
Management API: https://o.applovin.com/mediation/v1 with Api-Key header.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
from typing import Any, Callable, Dict, Optional


class MaxClient:
    """AppLovin MAX API client. Credential-driven."""

    REPORT_URL = "https://r.applovin.com/maxReport"

    def __init__(self, api_key: str = "", account_id: str = "",
                 report_key: str = "", management_key: str = ""):
        self._api_key = api_key          # SDK Key
        self._report_key = report_key     # Reporting API key
        self._management_key = management_key  # Management API key
        self._account_id = account_id
        self._api_override: Optional[Callable] = None

    def arm_real_client(self, override: Callable) -> None:
        self._api_override = override

    def request(self, method: str, endpoint: str,
                data: Optional[Dict] = None) -> Dict[str, Any]:
        if self._api_override:
            return self._api_override(method, endpoint, data)

        # Real API — route by method type
        if method == "GET" and "maxReport" in endpoint:
            return self._call_report_api(data or {})
        if method in ("POST", "PUT") and "/mediation/" in endpoint:
            return self._call_management_api(method, endpoint, data or {})

        return {"success": False, "error": f"unsupported: {method} {endpoint}"}

    # ------------------------------------------------------------------ #
    def _call_report_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call the real MAX Report API."""
        if not self._report_key:
            return {"success": False, "error": "no report key configured"}
        full_params = {
            "api_key": self._report_key,
            "format": "json",
            "columns": params.get("columns", "day,application,ad_format,country,impressions,ecpm,estimated_revenue"),
            "start": params.get("start", "2026-07-17"),
            "end": params.get("end", "2026-07-24"),
            "limit": params.get("limit", 500),
        }
        url = f"{self.REPORT_URL}?{urllib.parse.urlencode(full_params)}"
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "data": data.get("results", []),
                    "count": data.get("count", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    def _call_management_api(self, method: str, path: str,
                             data: Dict[str, Any]) -> Dict[str, Any]:
        """Call the MAX Management API."""
        if not self._management_key:
            return {"success": False, "error": "no management key configured"}
        url = f"https://o.applovin.com{path}"
        try:
            body = json.dumps(data).encode("utf-8") if data else None
            req = urllib.request.Request(url, data=body, method=method,
                headers={"Api-Key": self._management_key,
                         "Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "data": result}
        except urllib.error.HTTPError as e:
            err = e.read()[:500].decode("utf-8", errors="replace")
            return {"success": False, "error": f"HTTP {e.code}: {err}"}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    # ------------------------------------------------------------------ #
    def get_revenue(self, game_id: str, start: str, end: str) -> Dict[str, Any]:
        return self._call_report_api({
            "start": start, "end": end,
            "filter_application": game_id,
            "columns": "day,application,ad_format,country,impressions,ecpm,estimated_revenue",
        })

    def get_ecpm(self, ad_unit_id: str = "", days: int = 7) -> Dict[str, Any]:
        return self._call_report_api({
            "start": "2026-07-17", "end": "2026-07-24",
            "columns": "day,ad_format,ecpm,country",
        })

    def get_all_revenue(self, start: str = "2026-07-17",
                        end: str = "2026-07-24") -> Dict[str, Any]:
        """Get all revenue across all apps."""
        return self._call_report_api({
            "start": start, "end": end, "limit": 1000,
            "columns": "day,application,ad_format,country,impressions,ecpm,estimated_revenue",
        })

    def create_app(self, name: str, platform: str,
                   package_name: str) -> Dict[str, Any]:
        return self._call_management_api("POST", "/mediation/v1/ad_units", {})

    # ------------------------------------------------------------------ #
    # Contract methods used by MaxAdsProvider (E15.2.3).
    # All route through request() so the arm_real_client seam intercepts
    # them in tests; real calls hit the Management API, which currently
    # rejects writes on expanded-targeting waterfalls (platform limit).
    def create_ad_unit(self, app_id: str, ad_type: str,
                       name: str) -> Dict[str, Any]:
        return self.request("POST", "/mediation/v1/ad_units", {
            "app_id": app_id, "ad_format": ad_type, "name": name,
        })

    def update_waterfall(self, ad_unit_id: str,
                         networks: list) -> Dict[str, Any]:
        return self.request("PUT", f"/mediation/v1/ad_unit/{ad_unit_id}", {
            "networks": networks,
        })

    def update_bid_floor(self, ad_unit_id: str,
                         floor: float) -> Dict[str, Any]:
        return self.request("PUT", f"/mediation/v1/ad_unit/{ad_unit_id}", {
            "bid_floor": floor,
        })



__all__ = ["MaxClient"]
