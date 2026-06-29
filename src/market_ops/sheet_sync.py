from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from market_ops.clients.adjust import AdjustClient
from market_ops.clients.feishu_sheets import FeishuSheetsClient
from market_ops.clients.google_ads import GoogleAdsCreativeClient
from market_ops.clients.meta_ads import MetaAdsCreativeClient
from market_ops.clients.tecdo_report import TecDoReportCreativeClient
from market_ops.config import Settings
from market_ops.models import AdsPerformanceRow, CreativeAssetRow, RevenueRow

BLACKLISTED_ADJUST_APPS = (
    "Mergeland - Merge Dragons and Build dragon home",
    "Merge Legend",
    "Merge Legend Amazon",
    "Test App",
    "Placeholder",
)


class FeishuSheetsSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = FeishuSheetsClient(settings.feishu_app_id or "", settings.feishu_app_secret or "")
        self._adjust_dashboard_config = self._load_adjust_dashboard_config()

    def sync(self) -> dict[str, Any]:
        if not self._settings.using_feishu_sheet_sources:
            raise ValueError("Feishu sheet source URLs are not fully configured.")

        ads_rows = self._build_ads_rows()
        if self._settings.using_api_creative_source:
            creative_rows = self._build_creative_rows_from_apis(ads_rows)
        else:
            creative_rows = self._build_creative_rows()
        revenue_rows = self._build_revenue_rows(ads_rows)

        self._write_csv(self._settings.ads_performance_csv, ads_rows)
        self._write_csv(self._settings.creative_library_csv, creative_rows)
        self._write_csv(self._settings.adjust_revenue_csv, revenue_rows)

        latest_date = max((row.date for row in ads_rows), default=None)
        return {
            "ads_rows": len(ads_rows),
            "creative_rows": len(creative_rows),
            "adjust_rows": len(revenue_rows),
            "latest_date": latest_date.isoformat() if latest_date else "",
            "ads_csv": str(self._settings.ads_performance_csv) if self._settings.ads_performance_csv else "",
            "creative_csv": str(self._settings.creative_library_csv) if self._settings.creative_library_csv else "",
            "adjust_csv": str(self._settings.adjust_revenue_csv) if self._settings.adjust_revenue_csv else "",
        }

    def _build_ads_rows(self) -> list[AdsPerformanceRow]:
        rows: list[AdsPerformanceRow] = []
        for source in self._ads_sources():
            rows.extend(
                self._build_ads_rows_for_source(
                    game_name=source["game"],
                    daily_url=source["daily_url"],
                    roi_url=source.get("roi_url") or source["daily_url"],
                )
            )

        deduped = {
            (row.date, row.game, row.country, row.channel, row.ad_id, row.creative_id): row
            for row in rows
        }
        result = sorted(
            deduped.values(),
            key=lambda row: (row.date, row.game, row.country, row.channel, row.ad_id, row.creative_id),
        )
        return result

    def _build_ads_rows_for_source(
        self,
        *,
        game_name: str,
        daily_url: str,
        roi_url: str,
    ) -> list[AdsPerformanceRow]:
        daily_sheets = self._client.list_sheets(daily_url)
        roi_sources = self._roi_sheet_sources([daily_url, roi_url])

        rows: list[AdsPerformanceRow] = []
        for sheet in daily_sheets:
            title = str(sheet["title"]).strip()
            if not title.startswith("每日数据"):
                continue
            daily_values = self._client.read_values(daily_url, "A1:Q1200", sheet_id=sheet["sheet_id"])
            if not daily_values:
                continue

            roi_map = self._load_roi_map(roi_sources, self._candidate_roi_titles(title))
            headers = daily_values[0]
            for raw_row in daily_values[1:]:
                parsed = self._parse_ads_row(title, headers, raw_row, roi_map, game_name)
                if parsed:
                    rows.append(parsed)
        return rows

    def _build_creative_rows(self) -> list[CreativeAssetRow]:
        creative_url = self._settings.feishu_creative_url or ""
        request_sheet_id = self._client.find_sheet_id_by_title(creative_url, "视频制作需求")
        request_rows = self._client.read_values(creative_url, "A1:Q2000", sheet_id=request_sheet_id)
        creative_meta = self._build_creative_request_map(request_rows)

        rows: list[CreativeAssetRow] = []
        for title in ("视频-投放数据-AND", "视频-投放数据-IOS"):
            try:
                sheet_id = self._client.find_sheet_id_by_title(creative_url, title)
            except ValueError:
                continue
            values = self._client.read_values(creative_url, "A1:Z2000", sheet_id=sheet_id)
            if not values:
                continue
            headers = values[0]
            for raw_row in values[1:]:
                parsed = self._parse_creative_row(headers, raw_row, creative_meta, title)
                if parsed:
                    rows.append(parsed)

        deduped = {(row.asset_id, row.channel, row.country): row for row in rows}
        result = sorted(deduped.values(), key=lambda row: (row.game, row.asset_id, row.channel, row.country))
        return result

    def _build_creative_rows_from_apis(self, ads_rows: list[AdsPerformanceRow]) -> list[CreativeAssetRow]:
        if not ads_rows:
            return []
        end_date = max(row.date for row in ads_rows)
        min_ads_date = min(row.date for row in ads_rows)
        rows: list[CreativeAssetRow] = []

        if self._settings.using_meta_creative_source:
            meta_client = MetaAdsCreativeClient(
                access_token=self._settings.meta_access_token or "",
                ad_account_id=self._settings.meta_ad_account_id or "",
                api_version=self._settings.meta_api_version,
                default_game_name=self._settings.default_game_name,
            )
            meta_start_date = max(
                min_ads_date,
                end_date - timedelta(days=max(self._settings.meta_creative_lookback_days - 1, 0)),
            )
            rows.extend(meta_client.fetch_creative_rows(start_date=meta_start_date, end_date=end_date))

        if self._settings.using_tecdo_creative_source:
            tecdo_client = TecDoReportCreativeClient(
                app_secret=self._settings.tecdo_app_secret or "",
                base_url=self._settings.tecdo_base_url,
                media_accounts=self._settings.tecdo_effective_media_accounts,
                default_game_name=self._settings.default_game_name,
            )
            tecdo_start_date = max(
                min_ads_date,
                end_date - timedelta(days=max(self._settings.tecdo_creative_lookback_days - 1, 0)),
            )
            try:
                rows.extend(tecdo_client.fetch_creative_rows(start_date=tecdo_start_date, end_date=end_date))
            except Exception:
                pass

        if self._settings.using_google_creative_source:
            google_client = GoogleAdsCreativeClient(
                developer_token=self._settings.google_ads_developer_token or "",
                client_id=self._settings.google_ads_client_id or "",
                client_secret=self._settings.google_ads_client_secret or "",
                refresh_token=self._settings.google_ads_refresh_token or "",
                customer_id=self._settings.google_ads_customer_id or "",
                login_customer_id=self._settings.google_ads_login_customer_id,
                default_game_name=self._settings.default_game_name,
            )
            google_start_date = max(
                min_ads_date,
                end_date - timedelta(days=max(self._settings.google_ads_creative_lookback_days - 1, 0)),
            )
            rows.extend(google_client.fetch_creative_rows(start_date=google_start_date, end_date=end_date))

        deduped = {
            (row.channel, row.asset_id, row.game, row.country): row
            for row in rows
        }
        return sorted(deduped.values(), key=lambda row: (row.game, row.channel, row.asset_id, row.country))

    def _build_revenue_rows(self, ads_rows: list[AdsPerformanceRow]) -> list[RevenueRow]:
        if self._settings.adjust_dashboard_config_path and self._settings.adjust_dashboard_config_path.exists():
            return self._build_revenue_rows_from_adjust_dashboard(ads_rows)
        if self._settings.adjust_api_token and ads_rows:
            return self._build_revenue_rows_from_adjust_api(ads_rows)
        if not self._settings.feishu_adjust_url:
            return []

        adjust_url = self._settings.feishu_adjust_url
        sheets = self._client.list_sheets(adjust_url)
        target_sheet_id = None
        for sheet in sheets:
            title = str(sheet["title"]).lower()
            if "adjust" in title or "收入" in title or "revenue" in title:
                target_sheet_id = sheet["sheet_id"]
                break
        if target_sheet_id is None and sheets:
            target_sheet_id = sheets[0]["sheet_id"]
        if not target_sheet_id:
            return []

        values = self._client.read_values(adjust_url, "A1:M2000", sheet_id=target_sheet_id)
        if not values:
            return []

        headers = values[0]
        rows: list[RevenueRow] = []
        for raw_row in values[1:]:
            parsed = self._parse_revenue_row(headers, raw_row)
            if parsed:
                rows.append(parsed)
        rows.sort(key=lambda row: (row.date, row.game))
        return rows

    def _build_revenue_rows_from_adjust_dashboard(self, ads_rows: list[AdsPerformanceRow]) -> list[RevenueRow]:
        if not ads_rows:
            return []
        start_date = min(row.date for row in ads_rows).isoformat()
        end_date = max(row.date for row in ads_rows).isoformat()
        client = AdjustClient.from_dashboard_config(self._settings.adjust_dashboard_config_path)
        raw_rows = client.fetch_daily_revenue(start_date, end_date)
        rows: list[RevenueRow] = []
        for raw_row in raw_rows:
            game = self._normalize_game_name(self._to_str(raw_row.get("app")))
            row_date = self._to_date(raw_row.get("day"))
            total_revenue = self._to_float(raw_row.get("all_revenue"))
            installs = self._to_float(raw_row.get("installs"))
            payers = self._to_float(raw_row.get("first_paying_users_d0"))
            if not game or not row_date or self._is_blacklisted_adjust_app(game):
                continue
            arpu = total_revenue / installs if installs else 0.0
            arppu = total_revenue / payers if payers else 0.0
            rows.append(
                RevenueRow(
                    game=game,
                    date=row_date,
                    total_revenue=total_revenue,
                    ltv=arpu,
                    arpu=arpu,
                    arppu=arppu,
                    total_cost=self._to_float(raw_row.get("cost")),
                )
            )
        rows.sort(key=lambda row: (row.date, row.game))
        return rows

    def _build_revenue_rows_from_adjust_api(self, ads_rows: list[AdsPerformanceRow]) -> list[RevenueRow]:
        if not ads_rows:
            return []
        start_date = min(row.date for row in ads_rows).isoformat()
        end_date = max(row.date for row in ads_rows).isoformat()
        client = AdjustClient(self._settings.adjust_api_token)
        raw_rows = client.fetch_daily_revenue(start_date, end_date)
        rows: list[RevenueRow] = []
        for raw_row in raw_rows:
            game = self._normalize_game_name(self._to_str(raw_row.get("app")))
            row_date = self._to_date(raw_row.get("day"))
            total_revenue = self._to_float(raw_row.get("all_revenue"))
            installs = self._to_float(raw_row.get("installs"))
            payers = self._to_float(raw_row.get("first_paying_users_d0"))
            if not game or not row_date or self._is_blacklisted_adjust_app(game):
                continue
            arpu = total_revenue / installs if installs else 0.0
            arppu = total_revenue / payers if payers else 0.0
            rows.append(
                RevenueRow(
                    game=game,
                    date=row_date,
                    total_revenue=total_revenue,
                    ltv=arpu,
                    arpu=arpu,
                    arppu=arppu,
                    total_cost=self._to_float(raw_row.get("cost")),
                )
            )
        rows.sort(key=lambda row: (row.date, row.game))
        return rows

    @staticmethod
    def _is_blacklisted_adjust_app(game: str) -> bool:
        normalized = (game or "").strip()
        return any(name in normalized for name in BLACKLISTED_ADJUST_APPS)

    def _ads_sources(self) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        explicit_pairs = {
            (
                self._to_str(item.get("daily_url")),
                self._to_str(item.get("roi_url")) or self._to_str(item.get("daily_url")),
            ): self._to_str(item.get("game"))
            for item in self._settings.project_sheet_sources
            if self._to_str(item.get("game")) and self._to_str(item.get("daily_url"))
        }
        explicit_daily = {
            self._to_str(item.get("daily_url")): self._to_str(item.get("game"))
            for item in self._settings.project_sheet_sources
            if self._to_str(item.get("game")) and self._to_str(item.get("daily_url"))
        }
        explicit_roi = {
            (self._to_str(item.get("roi_url")) or self._to_str(item.get("daily_url"))): self._to_str(item.get("game"))
            for item in self._settings.project_sheet_sources
            if self._to_str(item.get("game")) and self._to_str(item.get("daily_url"))
        }
        default_daily_url = self._to_str(self._settings.feishu_daily_data_url)
        default_roi_url = self._to_str(self._settings.feishu_roi_url) or default_daily_url
        default_game = self._default_game_name()
        default_pair = (default_daily_url, default_roi_url)
        explicit_owner = explicit_pairs.get(default_pair)
        explicit_daily_owner = explicit_daily.get(default_daily_url)
        explicit_roi_owner = explicit_roi.get(default_roi_url)

        if default_daily_url and (
            (not explicit_owner or explicit_owner == default_game)
            and (not explicit_daily_owner or explicit_daily_owner == default_game)
            and (not explicit_roi_owner or explicit_roi_owner == default_game)
        ):
            sources.append(
                {
                    "game": default_game,
                    "daily_url": default_daily_url,
                    "roi_url": default_roi_url,
                }
            )

        seen: set[tuple[str, str, str]] = {
            (item["game"], item["daily_url"], item.get("roi_url", item["daily_url"])) for item in sources
        }
        for item in self._settings.project_sheet_sources:
            game = self._to_str(item.get("game"))
            daily_url = self._to_str(item.get("daily_url"))
            roi_url = self._to_str(item.get("roi_url")) or daily_url
            key = (game, daily_url, roi_url)
            if not game or not daily_url or key in seen:
                continue
            seen.add(key)
            sources.append({"game": game, "daily_url": daily_url, "roi_url": roi_url})
        return sources

    def _roi_sheet_sources(self, urls: list[str]) -> dict[str, tuple[str, str]]:
        sources: dict[str, tuple[str, str]] = {}
        for url in filter(None, urls):
            for sheet in self._client.list_sheets(url):
                title = str(sheet["title"]).strip()
                if title.startswith("ROI") or title.startswith("【"):
                    sources[title] = (url, sheet["sheet_id"])
        return sources

    def _load_roi_map(
        self,
        sources: dict[str, tuple[str, str]],
        candidate_titles: list[str],
    ) -> dict[date, float]:
        for title in candidate_titles:
            source = sources.get(title)
            if not source:
                continue
            url, sheet_id = source
            values = self._client.read_values(url, "A1:Z2000", sheet_id=sheet_id)
            return self._build_roi_map(values)
        return {}

    def _build_roi_map(self, values: list[list[Any]]) -> dict[date, float]:
        if not values:
            return {}
        headers = values[0]
        result: dict[date, float] = {}
        for raw_row in values[1:]:
            row_date = self._to_date(self._cell(headers, raw_row, "日期"))
            if not row_date:
                continue
            roas_value = self._to_float(self._cell(headers, raw_row, "7日ROI", "7d ROI", "7D ROAS"))
            if roas_value:
                result[row_date] = roas_value
        return result

    def _parse_ads_row(
        self,
        title: str,
        headers: list[Any],
        raw_row: list[Any],
        roi_map: dict[date, float],
        game_name: str,
    ) -> AdsPerformanceRow | None:
        row_date = self._to_date(self._cell(headers, raw_row, "日期"))
        spend = self._to_float(self._cell(headers, raw_row, "消耗($)", "Cost($)", "Cost（$）"))
        cpi = self._to_float(self._cell(headers, raw_row, "CPI"))
        if not row_date or spend == 0:
            return None

        game = self._normalize_game_name(game_name) or self._default_game_name()
        country = self._infer_country_from_title(title)
        channel = self._infer_channel_from_title(title)
        roas = roi_map.get(row_date) or self._to_float(self._cell(headers, raw_row, "首日ROI", "ROAS"))

        return AdsPerformanceRow(
            date=row_date,
            game=game,
            country=country,
            channel=channel,
            ad_id="",
            creative_id="",
            spend=spend,
            clicks=0,
            ctr=0.0,
            cpi=cpi,
            roas=roas,
            retention_d1=self._normalize_rate(self._to_float(self._cell(headers, raw_row, "1日留存", "D1留存"))),
            retention_d7=0.0,
            retention_d30=0.0,
        )

    def _build_creative_request_map(self, rows: list[list[Any]]) -> dict[str, dict[str, Any]]:
        if not rows:
            return {}
        headers = rows[0]
        mapping: dict[str, dict[str, Any]] = {}
        for raw_row in rows[1:]:
            asset_id = self._to_str(self._cell(headers, raw_row, "编号", "素材编号"))
            if not asset_id:
                continue
            creative_type = self._to_str(self._cell(headers, raw_row, "视频种类", "素材类型"))
            game = self._normalize_game_name(self._to_str(self._cell(headers, raw_row, "项目", "游戏")))
            mapping[asset_id] = {
                "creative_type": creative_type,
                "status": self._to_str(self._cell(headers, raw_row, "状态")),
                "video_path": self._attachment_text(self._cell(headers, raw_row, "完成视频链接", "视频路径")),
                "game": game or self._default_game_name(),
                "country": self._to_str(self._cell(headers, raw_row, "国家")),
                "channel": self._to_str(self._cell(headers, raw_row, "渠道")),
                "hook_type": creative_type,
                "duration": self._infer_duration_seconds(self._to_str(self._cell(headers, raw_row, "命名格式"))),
            }
        return mapping

    def _parse_creative_row(
        self,
        headers: list[Any],
        raw_row: list[Any],
        creative_meta: dict[str, dict[str, Any]],
        title: str,
    ) -> CreativeAssetRow | None:
        asset_id = self._to_str(self._cell(headers, raw_row, "素材编号", "素材ID"))
        if not asset_id:
            return None

        meta = creative_meta.get(asset_id, {})
        spend = self._to_float(self._cell(headers, raw_row, "Cost（$）", "Cost($)", "花费", "消耗($)"))
        ctr = self._normalize_rate(self._to_float(self._cell(headers, raw_row, "CTR （%）", "CTR(%)", "CTR")))
        cvr = self._normalize_rate(self._to_float(self._cell(headers, raw_row, "CVR")))
        roas = self._to_float(self._cell(headers, raw_row, "Roas", "ROAS", "D0 ROAS"))
        if not roas:
            value = self._to_float(self._cell(headers, raw_row, "转化价值（$）", "转化价值($)"))
            roas = value / spend if spend else 0.0

        video_path = meta.get("video_path") or self._attachment_text(self._cell(headers, raw_row, "素材链接", "视频路径"))
        status = self._to_str(self._cell(headers, raw_row, "素材评级", "状态")) or str(meta.get("status") or "")
        if not video_path and spend == 0 and ctr == 0 and cvr == 0 and roas == 0 and not status:
            return None

        return CreativeAssetRow(
            asset_id=asset_id,
            creative_type=self._to_str(meta.get("creative_type")) or "视频",
            video_path=video_path,
            game=self._normalize_game_name(self._to_str(meta.get("game"))) or self._default_game_name(),
            country=self._to_str(meta.get("country")) or self._infer_country_from_title(title),
            channel=self._to_str(meta.get("channel")) or self._infer_channel_from_title(title),
            ctr=ctr,
            cvr=cvr,
            roas=roas,
            spend=spend,
            status=status or "Unknown",
            hook_type=self._to_str(meta.get("hook_type")) or self._to_str(meta.get("creative_type")) or "Unknown",
            duration=float(meta.get("duration") or self._infer_duration_seconds(video_path)),
        )

    def _parse_revenue_row(self, headers: list[Any], raw_row: list[Any]) -> RevenueRow | None:
        row_date = self._to_date(self._cell(headers, raw_row, "日期"))
        game = self._normalize_game_name(self._to_str(self._cell(headers, raw_row, "游戏", "项目"))) or self._default_game_name()
        total_revenue = self._to_float(self._cell(headers, raw_row, "总收入", "Revenue"))
        total_cost = self._to_float(self._cell(headers, raw_row, "总花费", "花费", "Cost"))
        ltv = self._to_float(self._cell(headers, raw_row, "LTV"))
        arpu = self._to_float(self._cell(headers, raw_row, "ARPU"))
        arppu = self._to_float(self._cell(headers, raw_row, "ARPPU"))
        if not row_date or (total_revenue == 0 and total_cost == 0 and ltv == 0 and arpu == 0 and arppu == 0):
            return None
        return RevenueRow(
            game=game,
            date=row_date,
            total_revenue=total_revenue,
            ltv=ltv,
            arpu=arpu,
            arppu=arppu,
            total_cost=total_cost,
        )

    def _write_csv(self, path: Path | None, rows: list[Any]) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        row_dicts = [asdict(row) for row in rows]
        for row in row_dicts:
            for key, value in list(row.items()):
                if isinstance(value, date):
                    row[key] = value.isoformat()
        with path.open("w", encoding="utf-8", newline="") as handle:
            if not row_dicts:
                handle.write("")
                return
            writer = csv.DictWriter(handle, fieldnames=list(row_dicts[0].keys()))
            writer.writeheader()
            writer.writerows(row_dicts)

    def _cell(self, headers: list[Any], row: list[Any], *aliases: str) -> Any:
        for alias in aliases:
            alias_key = self._header_key(alias)
            for index, header in enumerate(headers):
                if self._header_key(header) == alias_key:
                    return row[index] if index < len(row) else None
        return None

    @staticmethod
    def _header_key(value: Any) -> str:
        text = str(value or "").strip().lower()
        return re.sub(r"[\s\u3000（）()_\-%/]+", "", text)

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text or text.startswith("="):
            return 0.0
        text = text.replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            number = float(text)
        except ValueError:
            return 0.0
        return number / 100 if "%" in str(value) else number

    @staticmethod
    def _to_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(FeishuSheetsSyncService._attachment_text(item) for item in value if item)
        if isinstance(value, dict):
            return FeishuSheetsSyncService._attachment_text(value)
        return str(value).strip()

    @staticmethod
    def _attachment_text(value: Any) -> str:
        if isinstance(value, list):
            parts = [FeishuSheetsSyncService._attachment_text(item) for item in value]
            return ", ".join(part for part in parts if part)
        if isinstance(value, dict):
            return str(value.get("text") or value.get("fileToken") or value.get("link") or "").strip()
        return str(value or "").strip()

    @staticmethod
    def _normalize_rate(value: float) -> float:
        return value / 100 if value > 1 else value

    @staticmethod
    def _infer_duration_seconds(text: str) -> float:
        match = re.search(r"-(\d+)s-", text or "")
        return float(match.group(1)) if match else 0.0

    @staticmethod
    def _infer_country_from_title(title: str) -> str:
        upper = title.upper()
        if "IOS" in upper:
            return "iOS"
        if "AND" in upper or "GP" in upper:
            return "Android"
        return "All"

    @staticmethod
    def _infer_channel_from_title(title: str) -> str:
        upper = title.upper()
        if "FB" in upper:
            return "Facebook"
        if "GG" in upper or "GOOGLE" in upper or "GP" in upper:
            return "Google"
        return "All"

    @staticmethod
    def _to_date(value: Any) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            excel_epoch = date(1899, 12, 30)
            return excel_epoch + timedelta(days=int(float(value)))
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y/%m/%d %A", "%Y年%m月%d日", "%Y年%m月"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _candidate_roi_titles(self, daily_title: str) -> list[str]:
        if daily_title == "每日数据(总)":
            return ["ROI（总）", "ROI(总)", "②总回收ROI"]
        if daily_title.startswith("每日数据-"):
            suffix = daily_title.replace("每日数据-", "")
            parts = suffix.split("-")
            candidates = [f"ROI-{suffix}"]
            if len(parts) == 2:
                candidates.append(f"【{parts[1]}-{parts[0]}】")
            return candidates
        if daily_title.startswith("数据-"):
            suffix = daily_title.replace("数据-", "")
            parts = suffix.split("-")
            candidates = []
            if len(parts) == 2:
                candidates.extend([f"【{parts[0]}-{parts[1]}】", f"ROI-{parts[0]}-{parts[1]}", f"ROI-{parts[1]}-{parts[0]}"])
            return candidates
        return []

    def _load_adjust_dashboard_config(self) -> dict[str, Any] | None:
        path = self._settings.adjust_dashboard_config_path
        if not path or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _default_game_name(self) -> str:
        selected = (
            ((self._adjust_dashboard_config or {}).get("feishu_config") or {}).get("selected_apps") or []
        )
        if len(selected) == 1 and selected[0]:
            return str(selected[0]).strip()
        return self._settings.default_game_name

    def _normalize_game_name(self, game: str) -> str:
        cleaned = self._to_str(game)
        if not cleaned:
            return ""
        if "amazon" in cleaned.lower():
            return cleaned
        default_name = self._default_game_name()
        default_code = self._game_code(default_name)
        if default_code and self._game_code(cleaned) == default_code:
            return default_name
        return cleaned

    @staticmethod
    def _game_code(value: str) -> str:
        match = re.search(r"\bP0*([0-9]+)\b", value.upper())
        return f"P{int(match.group(1)):02d}" if match else ""
