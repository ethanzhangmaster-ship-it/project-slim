from __future__ import annotations

import json
from pathlib import Path
from time import sleep
from typing import Any

import requests


class AdjustClient:
    RECOVERY_DAY_SUFFIXES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 20, 29, 59, 89, 99, 119, 120)

    def __init__(self, user_token: str, use_proxy: bool = False, iap_revenue_factor: float = 1.0) -> None:
        self._user_token = user_token.strip()
        self._use_proxy = use_proxy
        self._base_url = "https://automate.adjust.com/reports-service/report"
        self._iap_revenue_factor = iap_revenue_factor

    @classmethod
    def from_dashboard_config(cls, config_path: Path) -> "AdjustClient":
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        token = payload["adjust_api"]["user_token"]
        use_proxy = bool(payload.get("adjust_api", {}).get("use_proxy"))
        revenue_mode = ""
        for block in payload.get("data_blocks", []):
            mode = str(block.get("revenue_mode") or "").strip().lower()
            if mode:
                revenue_mode = mode
                break
        iap_revenue_factor = 0.8 if revenue_mode == "80_gross" else 1.0
        return cls(user_token=token, use_proxy=use_proxy, iap_revenue_factor=iap_revenue_factor)

    @property
    def iap_revenue_factor(self) -> float:
        return self._iap_revenue_factor

    def fetch_daily_revenue(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        params = {
            "date_period": f"{start_date}:{end_date}",
            "dimensions": "app,app_token,day",
            "metrics": "cost,all_revenue,revenue,ad_revenue,installs,first_paying_users_d0,all_revenue_total_d0",
            "ad_spend_mode": "network",
        }
        response = self._request("GET", self._base_url, params=params)
        return response.json().get("rows", [])

    def fetch_revenue_breakdown(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        params = {
            "date_period": f"{start_date}:{end_date}",
            "dimensions": (
                "app,app_token,store_type,partner_name,country,day,"
                "campaign_network,campaign_id_network,"
                "adgroup_network,adgroup_id_network,"
                "creative_network,creative_id_network,"
                "source_network,source_id_network"
            ),
            "metrics": "cost,all_revenue,revenue,ad_revenue,installs,daus,sessions",
            "ad_spend_mode": "network",
        }
        response = self._request("GET", self._base_url, params=params)
        return response.json().get("rows", [])

    def fetch_recovery_cohort_rows(
        self,
        start_date: str,
        end_date: str,
        app_names: set[str] | None = None,
        dimensions: str = "app,app_token,day",
        day_suffixes: tuple[int, ...] | None = None,
    ) -> list[dict[str, Any]]:
        metrics = ["cost"]
        for suffix in day_suffixes or self.RECOVERY_DAY_SUFFIXES:
            metrics.extend(
                [
                    f"roas_d{suffix}",
                    f"revenue_total_d{suffix}",
                    f"ad_revenue_total_d{suffix}",
                ]
            )
        params = {
            "date_period": f"{start_date}:{end_date}",
            "dimensions": dimensions,
            "metrics": ",".join(metrics),
            "ad_spend_mode": "network",
        }
        response = self._request("GET", self._base_url, params=params)
        rows = response.json().get("rows", [])
        if not app_names:
            return rows
        return [row for row in rows if str(row.get("app") or "").strip() in app_names]

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = self._user_token if self._user_token.startswith("Bearer ") else f"Bearer {self._user_token}"
        headers["Accept"] = "application/json"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 2:
                    break
                sleep(1.5 * (attempt + 1))
        if last_error:
            raise last_error
        raise RuntimeError("Unknown Adjust API request failure.")
