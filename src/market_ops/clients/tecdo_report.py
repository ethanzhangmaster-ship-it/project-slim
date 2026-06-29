from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import requests

from market_ops.models import CreativeAssetRow


class TecDoReportCreativeClient:
    _MAX_FILTER_DATAS = 10
    _MAX_DATE_SPAN_DAYS = 30
    _PROJECT_NAME_MAP = {
        "P02": "P02 Mermaid",
        "P04": "P04 Witch",
        "P07": "P07 Vampire",
    }

    def __init__(
        self,
        app_secret: str,
        base_url: str,
        media_accounts: list[dict[str, Any]],
        default_game_name: str,
    ) -> None:
        self._app_secret = app_secret.strip()
        self._base_url = base_url.strip().rstrip("/")
        self._media_accounts = list(media_accounts)
        self._default_game_name = default_game_name.strip()
        self._resolved_media_accounts_cache: list[dict[str, Any]] | None = None

    def probe_access(
        self,
        *,
        media_accounts: list[dict[str, Any]] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        filter_accounts = list(media_accounts) if media_accounts is not None else list(self._media_accounts)
        if not filter_accounts:
            return {
                "ok": False,
                "http_status": 0,
                "code": "",
                "message": "missing media accounts",
                "rows": 0,
                "pages": 0,
                "request_accounts": [],
            }
        report_end = end_date or date.today()
        report_start = start_date or report_end
        return self._query_report(
            filter_accounts=filter_accounts,
            dimensions=["mediaPlatform", "mediaAccountId"],
            metrics=["spend"],
            start_date=report_start,
            end_date=report_end,
            page_number=1,
            page_size=1,
        )

    def fetch_account_inventory(self) -> list[dict[str, Any]]:
        return self._resolved_media_accounts()

    def summarize_account_report_rows(
        self,
        *,
        report_end: date,
        lookback_days: int,
    ) -> list[dict[str, Any]]:
        resolved_accounts = self._resolved_media_accounts()
        summary_rows: list[dict[str, Any]] = []
        report_start = report_end - timedelta(days=max(lookback_days - 1, 0))
        for account in resolved_accounts:
            total_rows = 0
            checked_windows: list[dict[str, str | int]] = []
            for window_start, window_end in self._iter_date_windows(report_start, report_end):
                result = self._query_report(
                    filter_accounts=[
                        {
                            "mediaPlatform": int(account.get("mediaPlatform") or 0),
                            "mediaAccountId": str(account.get("mediaAccountId") or ""),
                        }
                    ],
                    dimensions=["mediaPlatform", "mediaAccountId", "campaignId", "adsetId", "adId", "campaignName", "adsetName", "adName"],
                    metrics=["spend", "impressions", "clicks", "installs"],
                    start_date=window_start,
                    end_date=window_end,
                    page_number=1,
                    page_size=1,
                )
                rows = int(result.get("rows") or 0)
                total_rows += rows
                checked_windows.append(
                    {
                        "start_date": window_start.isoformat(),
                        "end_date": window_end.isoformat(),
                        "rows": rows,
                        "code": str(result.get("code") or ""),
                        "message": str(result.get("message") or ""),
                    }
                )
            summary_rows.append(
                {
                    "mediaPlatform": int(account.get("mediaPlatform") or 0),
                    "mediaAccountId": str(account.get("mediaAccountId") or ""),
                    "mediaAccountName": str(account.get("mediaAccountName") or ""),
                    "game": str(account.get("game") or ""),
                    "channel": str(account.get("channel") or ""),
                    "has_report_rows": total_rows > 0,
                    "total_rows": total_rows,
                    "lookback_days": lookback_days,
                    "windows": checked_windows,
                }
            )
        return summary_rows

    def fetch_creative_rows(self, start_date: date, end_date: date) -> list[CreativeAssetRow]:
        resolved_accounts = self._resolved_media_accounts()
        rows = self._fetch_rows(start_date=start_date, end_date=end_date)
        aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}
        account_game_map = {
            (int(item.get("mediaPlatform")), str(item.get("mediaAccountId"))): str(item.get("game") or "").strip()
            for item in resolved_accounts
        }
        account_channel_map = {
            (int(item.get("mediaPlatform")), str(item.get("mediaAccountId"))): str(item.get("channel") or "").strip()
            for item in resolved_accounts
        }

        for row in rows:
            platform = self._to_int(row.get("mediaPlatform"))
            media_account_id = str(row.get("mediaAccountId") or "").strip()
            ad_id = str(row.get("adId") or "").strip()
            ad_name = str(row.get("adName") or "").strip()
            campaign_id = str(row.get("campaignId") or "").strip()
            campaign_name = str(row.get("campaignName") or "").strip()
            adset_id = str(row.get("adsetId") or "").strip()
            adset_name = str(row.get("adsetName") or "").strip()
            asset_id = ad_id or ad_name or campaign_id or media_account_id
            if not asset_id:
                continue

            channel = account_channel_map.get((platform, media_account_id)) or self._platform_label(platform)
            game = account_game_map.get((platform, media_account_id)) or self._infer_game_name(
                [ad_name, campaign_name, adset_name]
            )
            key = (channel, game, asset_id)
            item = aggregated.setdefault(
                key,
                {
                    "asset_id": asset_id,
                    "creative_name": ad_name or asset_id,
                    "creative_type": "proxy_ad",
                    "video_path": "",
                    "game": game,
                    "country": "All",
                    "channel": channel,
                    "campaign": campaign_name,
                    "campaign_id": campaign_id,
                    "adgroup": adset_name,
                    "adgroup_id": adset_id,
                    "ad_id": ad_id,
                    "ad_name": ad_name,
                    "source_name": adset_name or campaign_name,
                    "source_id": adset_id or campaign_id,
                    "status": "ACTIVE",
                    "hook_type": (ad_name or campaign_name or asset_id)[:40],
                    "duration": 0.0,
                    "spend": 0.0,
                    "impressions": 0.0,
                    "clicks": 0.0,
                    "installs": 0.0,
                },
            )
            item["spend"] += self._to_float(row.get("spend"))
            item["impressions"] += self._to_float(row.get("impressions"))
            item["clicks"] += self._to_float(row.get("clicks"))
            item["installs"] += self._to_float(row.get("installs"))

        creative_rows = [self._to_creative_row(item) for item in aggregated.values()]
        creative_rows.sort(key=lambda row: (row.game, row.channel, -row.spend, row.asset_id))
        return creative_rows

    def _fetch_rows(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        resolved_accounts = self._resolved_media_accounts()
        dimensions = [
            "mediaPlatform",
            "mediaAccountId",
            "campaignId",
            "adsetId",
            "adId",
            "campaignName",
            "adsetName",
            "adName",
        ]
        metrics = ["spend", "impressions", "clicks", "installs"]
        rows: list[dict[str, Any]] = []
        for window_start, window_end in self._iter_date_windows(start_date, end_date):
            for account_batch in self._iter_account_batches(resolved_accounts):
                page_number = 1
                while True:
                    result = self._query_report(
                        filter_accounts=account_batch,
                        dimensions=dimensions,
                        metrics=metrics,
                        start_date=window_start,
                        end_date=window_end,
                        page_number=page_number,
                        page_size=1000,
                    )
                    if not result.get("ok"):
                        raise RuntimeError(f"Tec-Do report API error: {result.get('message') or result}")
                    data = result.get("data") or {}
                    rows.extend(self._normalize_report_rows(data.get("list") or []))
                    pages = self._to_int(data.get("pages"))
                    if page_number >= max(pages, 1):
                        break
                    page_number += 1
        return rows

    def _resolved_media_accounts(self) -> list[dict[str, Any]]:
        if self._resolved_media_accounts_cache is not None:
            return list(self._resolved_media_accounts_cache)
        resolved = self._query_media_accounts()
        if resolved:
            self._resolved_media_accounts_cache = resolved
        else:
            self._resolved_media_accounts_cache = list(self._media_accounts)
        return list(self._resolved_media_accounts_cache)

    def _query_media_accounts(self) -> list[dict[str, Any]]:
        account_ids = []
        seen_ids: set[str] = set()
        for item in self._media_accounts:
            media_account_id = str(item.get("mediaAccountId") or "").strip()
            if not media_account_id or media_account_id in seen_ids:
                continue
            account_ids.append(media_account_id)
            seen_ids.add(media_account_id)
        if not account_ids:
            return []

        url = f"{self._base_url}/uni-agency/openApi/v1/mediaAccount/query"
        headers = {
            "X-App-Secret": self._app_secret,
            "Content-Type": "application/json",
        }
        payload = {
            "mediaAccountIds": account_ids,
            "pageNumber": 1,
            "pageSize": 250,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        body = response.json()
        if str(body.get("code") or "") != "0":
            return []
        data = body.get("data") or {}
        media_accounts = data.get("mediaAccounts") or []
        configured_by_id = {
            str(item.get("mediaAccountId") or "").strip(): item
            for item in self._media_accounts
            if str(item.get("mediaAccountId") or "").strip()
        }
        resolved: list[dict[str, Any]] = []
        for item in media_accounts:
            if not isinstance(item, dict):
                continue
            media_account_id = str(item.get("mediaAccountId") or "").strip()
            if not media_account_id:
                continue
            configured = configured_by_id.get(media_account_id, {})
            media_platform = self._to_int(item.get("mediaPlatform"))
            account_name = str(item.get("mediaAccountName") or "").strip()
            game = str(configured.get("game") or "").strip() or self._infer_game_name([account_name])
            channel = str(configured.get("channel") or "").strip() or self._platform_label(media_platform)
            resolved.append(
                {
                    "mediaPlatform": media_platform,
                    "mediaAccountId": media_account_id,
                    "mediaAccountName": account_name,
                    "game": game,
                    "channel": channel,
                }
            )
        return resolved

    @staticmethod
    def _normalize_report_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            metrics = item.get("metrics")
            dimensions = item.get("dimensions")
            if isinstance(metrics, dict) and isinstance(dimensions, dict):
                merged = dict(dimensions)
                merged.update(metrics)
                normalized.append(merged)
            else:
                normalized.append(item)
        return normalized

    def _iter_account_batches(self, accounts: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        return [
            accounts[index : index + self._MAX_FILTER_DATAS]
            for index in range(0, len(accounts), self._MAX_FILTER_DATAS)
        ]

    def _iter_date_windows(self, start_date: date, end_date: date) -> list[tuple[date, date]]:
        if start_date > end_date:
            return []
        windows: list[tuple[date, date]] = []
        cursor = start_date
        max_span = timedelta(days=self._MAX_DATE_SPAN_DAYS - 1)
        while cursor <= end_date:
            window_end = min(cursor + max_span, end_date)
            windows.append((cursor, window_end))
            cursor = window_end + timedelta(days=1)
        return windows

    def _query_report(
        self,
        *,
        filter_accounts: list[dict[str, Any]],
        dimensions: list[str],
        metrics: list[str],
        start_date: date,
        end_date: date,
        page_number: int,
        page_size: int,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/uni-agency/openApi/v1/report/query"
        headers = {
            "X-App-Secret": self._app_secret,
            "Content-Type": "application/json",
        }
        payload = {
            "filterDatas": [
                {
                    "mediaPlatform": int(item["mediaPlatform"]),
                    "mediaAccountId": str(item["mediaAccountId"]),
                }
                for item in filter_accounts
            ],
            "dimensions": dimensions,
            "metrics": metrics,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        http_status = int(response.status_code)
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text}
        code = str(body.get("code") or "")
        message = str(body.get("message") or "")
        data = body.get("data") or {}
        return {
            "ok": http_status == 200 and code == "0",
            "http_status": http_status,
            "code": code,
            "message": message,
            "data": data,
            "rows": self._to_int(data.get("total")),
            "pages": self._to_int(data.get("pages")),
            "request_accounts": payload["filterDatas"],
        }

    def _to_creative_row(self, item: dict[str, Any]) -> CreativeAssetRow:
        impressions = float(item["impressions"])
        clicks = float(item["clicks"])
        spend = float(item["spend"])
        installs = float(item["installs"])
        ctr = clicks / impressions if impressions else 0.0
        cvr = installs / clicks if clicks else 0.0
        return CreativeAssetRow(
            asset_id=str(item["asset_id"]),
            creative_type=str(item["creative_type"]),
            video_path=str(item["video_path"]),
            game=str(item["game"]),
            country=str(item["country"]),
            channel=str(item["channel"]),
            ctr=ctr,
            cvr=cvr,
            roas=0.0,
            spend=spend,
            status=str(item["status"]),
            hook_type=str(item["hook_type"]),
            duration=float(item["duration"]),
            creative_name=str(item["creative_name"]),
            campaign=str(item["campaign"]),
            campaign_id=str(item["campaign_id"]),
            adgroup=str(item["adgroup"]),
            adgroup_id=str(item["adgroup_id"]),
            ad_id=str(item["ad_id"]),
            ad_name=str(item["ad_name"]),
            source_name=str(item["source_name"]),
            source_id=str(item["source_id"]),
            installs=installs,
            conversions=installs,
            revenue_value=0.0,
        )

    def _infer_game_name(self, texts: list[str]) -> str:
        for text in texts:
            raw_text = str(text or "")
            match = re.search(r"\bP\d{2}\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", raw_text)
            if match:
                project_key = match.group(0).strip().split()[0]
                return self._PROJECT_NAME_MAP.get(project_key, match.group(0).strip())
            account_match = re.search(r"(?:^|_)0?(\d{2})(?:_|$)", raw_text)
            if account_match:
                project_key = f"P{int(account_match.group(1)):02d}"
                if project_key in self._PROJECT_NAME_MAP:
                    return self._PROJECT_NAME_MAP[project_key]
        return self._default_game_name

    @staticmethod
    def _platform_label(value: int) -> str:
        return {
            1: "Facebook",
            2: "Google Ads",
            4: "Snapchat",
            5: "TikTok",
        }.get(value, f"Media-{value}")

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
