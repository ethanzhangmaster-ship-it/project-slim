"""E10.2 Facebook Graph API Client.

Encapsulates all HTTP communication with the Facebook Graph API.
This is the ONLY module in the entire system that may make HTTP
calls to Facebook. All other modules must go through this client.

In sandbox mode (default), returns deterministic mock responses
without making any real API calls — safe for CI and development.

API Mapping:
    SCALE  → POST /{campaign_id}?daily_budget={amount}
    KILL   → POST /{campaign_id}?status=PAUSED
    WATCH  → GET  /{campaign_id}?fields=...
    RETEST → POST /{campaign_id}/copies
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from market_ops.execution_runtime.adapters.facebook.facebook_config import FacebookConfig
from market_ops.execution_runtime.adapters.facebook.exceptions import (
    FacebookTimeoutError,
    FacebookAPIError,
    map_facebook_error,
)


class FacebookClient:
    """HTTP client for Facebook Graph API.

    Args:
        config: FacebookConfig with credentials and settings.
    """

    def __init__(self, config: FacebookConfig | None = None) -> None:
        self._config = config or FacebookConfig()
        self._request_count = 0
        # Sandbox 状态缓存 — 模拟平台侧状态
        self._sandbox_budgets: dict[str, str] = {}
        self._sandbox_statuses: dict[str, str] = {}

    # ───────────────────────────────────────────────────────
    # Public API
    # ───────────────────────────────────────────────────────

    def update_campaign_budget(self, campaign_id: str, daily_budget: int) -> dict[str, Any]:
        """Update campaign daily budget. Maps to SCALE.

        Args:
            campaign_id: Facebook campaign ID.
            daily_budget: New daily budget in cents (e.g., 50000 = $500.00).

        Returns:
            API response dict with success flag and campaign data.
        """
        params = {"daily_budget": str(daily_budget)}
        return self._request("POST", campaign_id, params)

    def pause_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Pause a campaign. Maps to KILL.

        Args:
            campaign_id: Facebook campaign ID.

        Returns:
            API response dict with status=PAUSED.
        """
        params = {"status": "PAUSED"}
        return self._request("POST", campaign_id, params)

    def resume_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Resume a paused campaign. Maps to RESUME.

        Args:
            campaign_id: Facebook campaign ID.

        Returns:
            API response dict with status=ACTIVE.
        """
        params = {"status": "ACTIVE"}
        return self._request("POST", campaign_id, params)

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Get campaign details and metrics. Maps to WATCH.

        Args:
            campaign_id: Facebook campaign ID.

        Returns:
            API response dict with campaign fields and insights.
        """
        fields = "id,name,status,daily_budget,lifetime_budget,objective,insights{impressions,clicks,spend,actions,cpm,cpc,ctr}"
        return self._request("GET", campaign_id, {"fields": fields})

    def duplicate_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Duplicate a campaign. Maps to RETEST.

        Args:
            campaign_id: Facebook campaign ID to copy.

        Returns:
            API response dict with new campaign ID.
        """
        return self._request("POST", f"{campaign_id}/copies", {})

    # ───────────────────────────────────────────────────────
    # Internal
    # ───────────────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Execute an HTTP request against the Graph API.

        In sandbox mode, returns mock responses without network calls.
        """
        self._request_count += 1

        if self._config.sandbox:
            return self._mock_response(method, endpoint, params)

        return self._http_request(method, endpoint, params)

    def _http_request(self, method: str, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Execute a real HTTP request with retry logic."""
        url = f"{self._config.graph_url}/{endpoint}"
        params = {**params, "access_token": self._config.access_token}

        last_error: Exception | None = None
        for attempt in range(self._config.max_retries):
            try:
                if method == "GET":
                    qs = "&".join(f"{k}={v}" for k, v in params.items())
                    full_url = f"{url}?{qs}"
                    req = urllib.request.Request(full_url, method="GET")
                else:
                    data = "&".join(f"{k}={v}" for k, v in params.items()).encode("utf-8")
                    req = urllib.request.Request(url, data=data, method="POST")
                    req.add_header("Content-Type", "application/x-www-form-urlencoded")

                with urllib.request.urlopen(req, timeout=self._config.timeout) as resp:
                    body = resp.read().decode("utf-8")
                    return self._parse_response(json.loads(body))

            except urllib.error.HTTPError as exc:
                error_body = {}
                try:
                    error_body = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    pass
                last_error = self._handle_error_response(error_body)
                if not isinstance(last_error, FacebookTimeoutError):
                    raise last_error from exc

            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = FacebookTimeoutError(endpoint, self._config.timeout)

            if attempt < self._config.max_retries - 1:
                time.sleep(self._config.retry_delay * (attempt + 1))

        raise last_error  # type: ignore[misc]

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse Facebook API response, raising on error."""
        if "error" in data:
            return self._handle_error_response(data)
        return {"success": True, "data": data}

    def _handle_error_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Extract error info and raise appropriate exception."""
        error = data.get("error", {})
        code = error.get("code", 1)
        message = error.get("message", "Unknown error")
        raise map_facebook_error(code, message, data)

    # ───────────────────────────────────────────────────────
    # Sandbox — Mock responses
    # ───────────────────────────────────────────────────────

    def _mock_response(self, method: str, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Return deterministic mock responses for sandbox mode.

        No real HTTP calls are made. Safe for CI and local dev.
        Stateful: POST updates are reflected in subsequent GET queries.
        """
        campaign_id = endpoint.split("/")[0] if endpoint else "unknown"

        if method == "POST" and "copies" in endpoint:
            return {
                "success": True,
                "data": {
                    "id": f"{campaign_id}_copy_{self._request_count}",
                    "name": f"Copy of {campaign_id}",
                    "status": "PAUSED",
                    "daily_budget": params.get("daily_budget", "0"),
                    "created_time": "2024-01-01T00:00:00+0000",
                },
            }

        if method == "POST" and "status" in params:
            # 记录状态变更
            self._sandbox_statuses[campaign_id] = params["status"]
            return {
                "success": True,
                "data": {
                    "id": campaign_id,
                    "status": params["status"],
                    "success": True,
                },
            }

        if method == "POST" and "daily_budget" in params:
            # 记录预算变更
            self._sandbox_budgets[campaign_id] = params["daily_budget"]
            return {
                "success": True,
                "data": {
                    "id": campaign_id,
                    "daily_budget": params["daily_budget"],
                    "success": True,
                },
            }

        if method == "GET":
            # 返回有状态的数据 — 反映之前的 POST 变更
            return {
                "success": True,
                "data": {
                    "id": campaign_id,
                    "name": f"Campaign {campaign_id}",
                    "status": self._sandbox_statuses.get(campaign_id, "ACTIVE"),
                    "daily_budget": self._sandbox_budgets.get(campaign_id, "50000"),
                    "objective": "OUTCOME_APP_INSTALLS",
                    "insights": {
                        "data": [{
                            "impressions": "15000",
                            "clicks": "450",
                            "spend": "320.50",
                            "cpm": "21.37",
                            "cpc": "0.71",
                            "ctr": "3.00",
                        }],
                    },
                },
            }

        return {
            "success": True,
            "data": {
                "id": campaign_id,
                "success": True,
            },
        }

    # ───────────────────────────────────────────────────────
    # Properties
    # ───────────────────────────────────────────────────────

    @property
    def request_count(self) -> int:
        return self._request_count