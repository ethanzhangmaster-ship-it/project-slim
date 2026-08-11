"""E11 Phase 1 — Facebook Graph API Client。

负责：
  - Token 管理
  - Graph API 请求
  - 分页处理
  - 错误重试
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import requests


class FacebookClient:
    """Facebook Graph API 客户端。

    封装 API 调用、分页、重试逻辑。

    Usage:
        client = FacebookClient(access_token="xxx", ad_account_id="123456", api_version="v22.0")
        ads = client.get_ads()
        insights = client.get_insights(start_date, end_date)
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds
    PAGE_LIMIT = 500

    def __init__(
        self,
        access_token: str,
        ad_account_id: str,
        api_version: str = "v22.0",
    ) -> None:
        self._token = access_token.strip()
        self._account_id = ad_account_id.replace("act_", "").strip()
        self._version = api_version.strip()
        self._base = f"https://graph.facebook.com/{self._version}"

    # ── Public API ──────────────────────────────────────

    def get_ads(
        self,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """获取广告账户下所有广告。

        GET /act_{ad_account_id}/ads
        """
        default_fields = [
            "id", "name", "creative{id,image_url,thumbnail_url,video_id}",
            "campaign_id", "campaign{name}",
            "adset_id", "adset{name}",
            "status", "created_time", "updated_time",
        ]
        return self._get_paginated(
            f"/act_{self._account_id}/ads",
            {
                "access_token": self._token,
                "fields": ",".join(fields or default_fields),
                "limit": self.PAGE_LIMIT,
            },
        )

    def get_creative(self, creative_id: str) -> dict[str, Any] | None:
        """获取单个 Creative 详情。

        GET /{creative_id}
        """
        params = {
            "access_token": self._token,
            "fields": "id,image_url,thumbnail_url,video_id,body,title,description,"
                       "call_to_action_type,object_story_spec",
        }
        return self._get_single(f"/{creative_id}", params)

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        """获取单个 Video 详情。

        GET /{video_id}
        """
        params = {
            "access_token": self._token,
            "fields": "id,title,description,length,picture,source,width,height",
        }
        return self._get_single(f"/{video_id}", params)

    def get_insights(
        self,
        start_date: date,
        end_date: date,
        level: str = "ad",
    ) -> list[dict[str, Any]]:
        """获取广告成效数据。

        GET /act_{ad_account_id}/insights

        Args:
            start_date: 开始日期
            end_date:   结束日期
            level:      聚合级别 (ad/adset/campaign)
        """
        params = {
            "access_token": self._token,
            "level": level,
            "time_range": json.dumps({
                "since": start_date.isoformat(),
                "until": end_date.isoformat(),
            }),
            "fields": "ad_id,ad_name,campaign_id,campaign_name,adset_id,adset_name,"
                       "spend,impressions,clicks,ctr,cpc,cpm,actions,"
                       "date_start,date_stop",
            "limit": self.PAGE_LIMIT,
        }
        return self._get_paginated(
            f"/act_{self._account_id}/insights",
            params,
        )

    def get_creative_insights(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """获取 Creative 级别的 Insights（含 creative_id 关联）。"""
        params = {
            "access_token": self._token,
            "level": "ad",
            "time_range": json.dumps({
                "since": start_date.isoformat(),
                "until": end_date.isoformat(),
            }),
            "fields": "ad_id,ad_name,creative{id},"
                       "spend,impressions,clicks,ctr,cpc,cpm,actions,"
                       "date_start,date_stop",
            "limit": self.PAGE_LIMIT,
        }
        return self._get_paginated(
            f"/act_{self._account_id}/insights",
            params,
        )

    # ── Internal ────────────────────────────────────────

    def _get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """分页获取所有结果。"""
        results: list[dict[str, Any]] = []
        url = f"{self._base}{endpoint}"
        next_url: str | None = url

        while next_url:
            try:
                resp = self._request_with_retry(next_url, params)
                data = resp.json()
                results.extend(data.get("data", []))

                paging = data.get("paging", {})
                next_url = paging.get("next")
                # 第一页之后用 paging.next 的完整 URL，不再传 params
                params = {}
            except Exception:
                break

        return results

    def _get_single(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict[str, Any] | None:
        """获取单个对象。"""
        url = f"{self._base}{endpoint}"
        try:
            resp = self._request_with_retry(url, params)
            return resp.json()
        except Exception:
            return None

    def _request_with_retry(
        self,
        url: str,
        params: dict[str, Any],
    ) -> requests.Response:
        """带重试的 HTTP 请求。"""
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                last_error = e
                if e.response is not None and e.response.status_code == 429:
                    # Rate limit — 等待后重试
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise
            except requests.RequestException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                continue

        raise last_error or RuntimeError("Facebook API request failed after retries")

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def base_url(self) -> str:
        return self._base

    def __repr__(self) -> str:
        return f"FacebookClient(account={self._account_id}, version={self._version})"