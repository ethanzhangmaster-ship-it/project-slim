from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import re
from typing import Any, Callable

from market_ops.clean_analyzers import CleanAnalysisService
from market_ops.clients.clean_ai import build_clean_ai_client
from market_ops.clients.adjust import AdjustClient
from market_ops.clients.feishu import FeishuClient
from market_ops.clients.feishu_bot import FeishuBotClient
from market_ops.clients.feishu_sheets import FeishuSheetsClient
from market_ops.clients.google_ads import GoogleAdsCreativeClient
from market_ops.clients.meta_ads import MetaAdsCreativeClient
from market_ops.config import Settings
from market_ops.final_executive import FinalExecutiveReportBuilder
from market_ops.forecast_validation import ForecastValidationReportBuilder
from market_ops.final_digest import FinalWeeklyDigestBuilder
from market_ops.management_action_list import ManagementActionListBuilder
from market_ops.models import ActionItem, AdsPerformanceRow, AnalysisSection, CreativeAssetRow, RevenueBreakdownRow, RevenueRow, WeeklyReport
from market_ops.reports import save_daily_sync_report, save_markdown_report
from market_ops.sheet_sync import FeishuSheetsSyncService
from market_ops.task_sync import TaskSyncService

BLACKLISTED_ADJUST_APPS = (
    "Mergeland - Merge Dragons and Build dragon home",
    "Merge Legend",
    "Merge Legend Amazon",
    "Test App",
    "Placeholder",
)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, list):
        value = value[0] if value else 0
    return float(value)


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, list):
        value = value[0] if value else 0
    return int(float(value))


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


class DataRepository:
    ACTION_FIELDS = [
        "Task ID",
        "Source Meeting",
        "Type",
        "Title",
        "Owner",
        "Status",
        "Acceptance Metric",
        "Due Date",
        "Description",
        "Latest Note",
    ]
    REPORT_FIELDS = [
        "Meeting Name",
        "Report Date",
        "Growth Summary",
        "Creative Summary",
        "Revenue Summary",
        "Report Path",
    ]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._feishu = None
        self._feishu_sheets = None
        self._adjust_breakdown_cache: dict[tuple[str, str], list[RevenueBreakdownRow]] = {}
        if settings.using_feishu_bitable:
            self._feishu = FeishuClient(
                settings.feishu_app_id or "",
                settings.feishu_app_secret or "",
                settings.feishu_bitable_app_token or "",
            )
        if settings.using_feishu_sheet_writeback:
            self._feishu_sheets = FeishuSheetsClient(
                settings.feishu_app_id or "",
                settings.feishu_app_secret or "",
            )

    def load_ads_performance(self) -> list[AdsPerformanceRow]:
        if self._settings.ads_performance_csv and self._settings.ads_performance_csv.exists():
            return self._read_csv(self._settings.ads_performance_csv, self._map_ads_csv)
        if self._feishu and self._settings.ads_performance_table_id:
            return self._read_feishu_fields(self._settings.ads_performance_table_id, self._map_ads_feishu)
        raise ValueError("No ads performance source configured.")

    def load_creative_library(self) -> list[CreativeAssetRow]:
        adjust_rows = self._load_adjust_creative_library_from_ads_window()
        if adjust_rows:
            return adjust_rows

        api_rows: list[CreativeAssetRow] = []
        if (
            self._settings.using_meta_creative_source
            or self._settings.using_google_creative_source
        ):
            ads_rows = self.load_ads_performance()
            if not ads_rows:
                return []
            end_date = max(row.date for row in ads_rows)
            if self._settings.using_meta_creative_source:
                meta_start_date = max(
                    min(row.date for row in ads_rows),
                    end_date - timedelta(days=max(self._settings.meta_creative_lookback_days - 1, 0)),
                )
                meta_client = MetaAdsCreativeClient(
                    access_token=self._settings.meta_access_token or "",
                    ad_account_id=self._settings.meta_ad_account_id or "",
                    api_version=self._settings.meta_api_version,
                    default_game_name=self._settings.default_game_name,
                )
                api_rows.extend(meta_client.fetch_creative_rows(start_date=meta_start_date, end_date=end_date))
            if self._settings.using_google_creative_source:
                google_start_date = max(
                    min(row.date for row in ads_rows),
                    end_date - timedelta(days=max(self._settings.google_ads_creative_lookback_days - 1, 0)),
                )
                google_client = GoogleAdsCreativeClient(
                    developer_token=self._settings.google_ads_developer_token or "",
                    client_id=self._settings.google_ads_client_id or "",
                    client_secret=self._settings.google_ads_client_secret or "",
                    refresh_token=self._settings.google_ads_refresh_token or "",
                    customer_id=self._settings.google_ads_customer_id or "",
                    login_customer_id=self._settings.google_ads_login_customer_id,
                    default_game_name=self._settings.default_game_name,
                )
                api_rows.extend(google_client.fetch_creative_rows(start_date=google_start_date, end_date=end_date))
            deduped = {
                (row.channel, row.asset_id, row.game, row.country): row
                for row in api_rows
            }
            if deduped:
                return sorted(deduped.values(), key=lambda row: (row.game, row.channel, row.asset_id, row.country))
        if self._settings.creative_library_csv and self._settings.creative_library_csv.exists():
            return self._read_csv(self._settings.creative_library_csv, self._map_creative_csv)
        if self._feishu and self._settings.creative_library_table_id:
            return self._read_feishu_fields(self._settings.creative_library_table_id, self._map_creative_feishu)
        raise ValueError("No creative library source configured.")

    def load_adjust_creative_library(self, start_date: date, end_date: date) -> list[CreativeAssetRow]:
        rows = self.load_adjust_revenue_breakdown(start_date, end_date)
        return self._aggregate_adjust_creative_rows(rows)

    def _load_adjust_creative_library_from_ads_window(self) -> list[CreativeAssetRow]:
        if not self._settings.adjust_api_token and not (
            self._settings.adjust_dashboard_config_path and self._settings.adjust_dashboard_config_path.exists()
        ):
            return []
        try:
            ads_rows = self.load_ads_performance()
        except Exception:
            ads_rows = []
        if not ads_rows:
            return []
        end_date = max(row.date for row in ads_rows)
        start_date = end_date - timedelta(days=6)
        return self.load_adjust_creative_library(start_date, end_date)

    def _aggregate_adjust_creative_rows(self, rows: list[RevenueBreakdownRow]) -> list[CreativeAssetRow]:
        buckets: dict[tuple[str, str, str, str, str, str, str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "spend": 0.0,
                "revenue": 0.0,
                "installs": 0.0,
                "source_modes": set(),
                "stores": set(),
            }
        )
        for row in rows:
            cost = float(getattr(row, "cost", 0.0) or 0.0)
            revenue = float(getattr(row, "total_revenue_gross", 0.0) or 0.0)
            installs = float(getattr(row, "installs", 0.0) or 0.0)
            if cost <= 0 and revenue <= 0 and installs <= 0:
                continue
            channel = self._normalize_paid_channel(str(getattr(row, "partner", "") or ""))
            if channel not in {"Facebook", "Google", "Apple Search", "Applovin", "Unity Ads", "TikTok"}:
                continue
            identity_id, identity_name, identity_mode = self._adjust_creative_identity(row, channel)
            if not identity_id and not identity_name:
                continue
            key = (
                self._project_key(str(getattr(row, "game", "") or "")),
                channel,
                str(getattr(row, "country", "") or "Global"),
                identity_id,
                identity_name,
                str(getattr(row, "campaign_id", "") or ""),
                str(getattr(row, "adgroup_id", "") or ""),
            )
            bucket = buckets[key]
            bucket["game"] = str(getattr(row, "game", "") or "")
            bucket["country"] = str(getattr(row, "country", "") or "Global")
            bucket["channel"] = channel
            bucket["asset_id"] = identity_id or identity_name
            bucket["creative_name"] = identity_name or identity_id
            bucket["identity_mode"] = identity_mode
            bucket["campaign"] = str(getattr(row, "campaign", "") or "")
            bucket["campaign_id"] = str(getattr(row, "campaign_id", "") or "")
            bucket["adgroup"] = str(getattr(row, "adgroup", "") or "")
            bucket["adgroup_id"] = str(getattr(row, "adgroup_id", "") or "")
            bucket["source_name"] = str(getattr(row, "source_name", "") or "")
            bucket["source_id"] = str(getattr(row, "source_id", "") or "")
            bucket["spend"] += cost
            bucket["revenue"] += revenue
            bucket["installs"] += installs
            bucket["source_modes"].add(identity_mode)
            if str(getattr(row, "store", "") or "").strip():
                bucket["stores"].add(str(getattr(row, "store", "") or "").strip())

        creative_rows: list[CreativeAssetRow] = []
        for bucket in buckets.values():
            spend = float(bucket["spend"])
            revenue = float(bucket["revenue"])
            installs = float(bucket["installs"])
            if spend <= 0:
                continue
            identity_mode = str(bucket.get("identity_mode") or "creative_id")
            identity_label = {
                "creative_id": "Adjust creative",
                "source_proxy": "Adjust source proxy",
                "adgroup_proxy": "Adjust adgroup proxy",
                "campaign_proxy": "Adjust campaign proxy",
            }.get(identity_mode, "Adjust creative")
            sample_status = "有效样本" if spend >= 50 or installs >= 20 else "观察样本"
            status = f"{identity_label} | {sample_status} | 花费 {spend:.0f} / 安装 {installs:.0f} / 收入 {revenue:.0f}"
            creative_rows.append(
                CreativeAssetRow(
                    asset_id=str(bucket.get("asset_id") or bucket.get("creative_name") or ""),
                    creative_type=identity_label,
                    video_path="",
                    game=str(bucket.get("game") or ""),
                    country=str(bucket.get("country") or "Global"),
                    channel=str(bucket.get("channel") or ""),
                    ctr=0.0,
                    cvr=0.0,
                    roas=(revenue / spend if spend else 0.0),
                    spend=spend,
                    status=status,
                    hook_type=identity_label,
                    creative_name=str(bucket.get("creative_name") or bucket.get("asset_id") or ""),
                    campaign=str(bucket.get("campaign") or ""),
                    campaign_id=str(bucket.get("campaign_id") or ""),
                    adgroup=str(bucket.get("adgroup") or ""),
                    adgroup_id=str(bucket.get("adgroup_id") or ""),
                    source_name=str(bucket.get("source_name") or ""),
                    source_id=str(bucket.get("source_id") or ""),
                    installs=installs,
                    conversions=installs,
                    revenue_value=revenue,
                )
            )
        return sorted(
            creative_rows,
            key=lambda row: (row.game, row.channel, -float(row.spend or 0.0), row.asset_id),
        )

    @classmethod
    def _adjust_creative_identity(cls, row: RevenueBreakdownRow, channel: str) -> tuple[str, str, str]:
        creative_id = str(getattr(row, "creative_id", "") or "").strip()
        creative_name = str(getattr(row, "creative_name", "") or "").strip()
        if cls._is_valid_adjust_creative_value(creative_id) and cls._is_valid_adjust_creative_value(creative_name):
            return creative_id or creative_name, creative_name or creative_id, "creative_id"
        if channel == "Google":
            adgroup_id = str(getattr(row, "adgroup_id", "") or "").strip()
            adgroup = str(getattr(row, "adgroup", "") or "").strip()
            if cls._is_valid_adjust_creative_value(adgroup_id):
                return adgroup_id, adgroup or adgroup_id, "adgroup_proxy"
            source_id = str(getattr(row, "source_id", "") or "").strip()
            source_name = str(getattr(row, "source_name", "") or "").strip()
            if cls._is_valid_adjust_creative_value(source_id):
                return source_id, source_name or source_id, "source_proxy"
            campaign_id = str(getattr(row, "campaign_id", "") or "").strip()
            campaign = str(getattr(row, "campaign", "") or "").strip()
            if cls._is_valid_adjust_creative_value(campaign_id):
                return campaign_id, campaign or campaign_id, "campaign_proxy"
        if cls._is_valid_adjust_creative_value(creative_id) or cls._is_valid_adjust_creative_value(creative_name):
            return creative_id or creative_name, creative_name or creative_id, "creative_id"
        return "", "", ""

    @staticmethod
    def _is_valid_adjust_creative_value(value: str) -> bool:
        normalized = str(value or "").strip().lower()
        return normalized not in {
            "",
            "-",
            "display",
            "search googlesearch",
            "youtube youtubevideos",
            "unknown",
            "(not set)",
            "nan",
            "none",
        }

    @staticmethod
    def _normalize_paid_channel(value: str) -> str:
        normalized = (value or "").strip().lower()
        if "google" in normalized:
            return "Google"
        if "facebook" in normalized or "instagram" in normalized or "off-facebook" in normalized or "meta" in normalized:
            return "Facebook"
        if "apple" in normalized or "asa" in normalized:
            return "Apple Search"
        if "applovin" in normalized:
            return "Applovin"
        if "unity" in normalized:
            return "Unity Ads"
        if "tiktok" in normalized or "bytedance" in normalized:
            return "TikTok"
        return value or "Unknown"

    @staticmethod
    def _project_key(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return ""
        match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
        if match:
            return f"P{int(match.group(1)):02d}"
        simplified = re.sub(r"(?i)\bamazon\b", "", cleaned)
        simplified = re.sub(r"\s+", " ", simplified).strip(" -")
        return simplified or cleaned

    def load_adjust_revenue(self) -> list[RevenueRow]:
        if self._settings.adjust_revenue_csv and self._settings.adjust_revenue_csv.exists():
            rows = self._read_csv(self._settings.adjust_revenue_csv, self._map_revenue_csv)
            return [row for row in rows if not self._is_blacklisted_adjust_app(row.game)]
        if self._feishu and self._settings.adjust_revenue_table_id:
            rows = self._read_feishu_fields(self._settings.adjust_revenue_table_id, self._map_revenue_feishu)
            return [row for row in rows if not self._is_blacklisted_adjust_app(row.game)]
        return []

    def load_adjust_revenue_breakdown(self, start_date: date, end_date: date) -> list[RevenueBreakdownRow]:
        cache_key = (start_date.isoformat(), end_date.isoformat())
        if cache_key in self._adjust_breakdown_cache:
            return self._adjust_breakdown_cache[cache_key]

        rows: list[RevenueBreakdownRow] = []
        if self._settings.adjust_api_token:
            try:
                client = AdjustClient(self._settings.adjust_api_token)
                raw_rows = client.fetch_revenue_breakdown(start_date.isoformat(), end_date.isoformat())
                rows = [self._map_revenue_breakdown_api(row) for row in raw_rows]
            except Exception:
                rows = []
        if not rows and self._settings.adjust_dashboard_config_path and self._settings.adjust_dashboard_config_path.exists():
            try:
                client = AdjustClient.from_dashboard_config(self._settings.adjust_dashboard_config_path)
                raw_rows = client.fetch_revenue_breakdown(start_date.isoformat(), end_date.isoformat())
                rows = [self._map_revenue_breakdown_api(row) for row in raw_rows]
            except Exception:
                rows = []
        if not rows:
            latest_csv = self._latest_breakdown_csv()
            if latest_csv is not None:
                rows = self._read_csv(latest_csv, self._map_revenue_breakdown_csv)

        filtered = [
            row
            for row in rows
            if start_date <= row.date <= end_date and not self._is_blacklisted_adjust_app(row.game)
        ]
        self._adjust_breakdown_cache[cache_key] = filtered
        return filtered

    @staticmethod
    def _is_blacklisted_adjust_app(game: str) -> bool:
        normalized = (game or "").strip()
        return any(name in normalized for name in BLACKLISTED_ADJUST_APPS)

    def load_action_tracker(self) -> list[ActionItem]:
        if self._settings.action_tracker_csv and self._settings.action_tracker_csv.exists():
            return self._read_csv(self._settings.action_tracker_csv, self._map_action_csv)
        if self._feishu and self._settings.action_tracker_table_id:
            records = self._feishu.list_records(self._settings.action_tracker_table_id)
            return [self._map_action_feishu(record) for record in records]
        return []

    def write_action_items(self, action_items: list[dict[str, Any]]) -> None:
        if self._settings.action_tracker_csv:
            self._upsert_action_tracker_csv(self._settings.action_tracker_csv, action_items)
        if self._feishu and self._settings.action_tracker_table_id:
            self._upsert_action_tracker_bitable(self._settings.action_tracker_table_id, action_items)
        self._sync_action_tracker_to_sheet()

    def update_action_items(self, action_items: list[ActionItem]) -> None:
        action_records = [self.action_to_record(item) for item in action_items]
        if self._settings.action_tracker_csv:
            self._upsert_csv_records(
                self._settings.action_tracker_csv,
                key_field="Task ID",
                records=action_records,
                field_order=self.ACTION_FIELDS,
            )
        if self._feishu and self._settings.action_tracker_table_id:
            updates = [
                {
                    "record_id": item.record_id,
                    "fields": {
                        "Status": item.status,
                        "Latest Note": item.latest_note,
                    },
                }
                for item in action_items
                if item.record_id
            ]
            if updates:
                self._feishu.batch_update_records(self._settings.action_tracker_table_id, updates)
        self._sync_action_tracker_to_sheet()

    def write_meeting_report(self, report_record: dict[str, Any]) -> None:
        if self._settings.meeting_reports_csv:
            self._upsert_meeting_report_csv(self._settings.meeting_reports_csv, report_record)
        if self._feishu and self._settings.meeting_reports_table_id:
            self._upsert_meeting_report_bitable(self._settings.meeting_reports_table_id, report_record)
        self._sync_meeting_reports_to_sheet()

    def _read_csv(self, path: Path, mapper: Callable[[dict[str, str]], Any]) -> list[Any]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [mapper(row) for row in reader if any(value not in ("", None) for value in row.values())]

    def _read_feishu_fields(self, table_id: str, mapper: Callable[[dict[str, Any]], Any]) -> list[Any]:
        if not self._feishu:
            raise ValueError("Feishu Bitable is not configured.")
        records = self._feishu.list_records(table_id)
        return [mapper(record["fields"]) for record in records]

    def _upsert_csv_records(
        self,
        path: Path,
        key_field: str,
        records: list[dict[str, Any]],
        field_order: list[str],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, dict[str, Any]] = {}
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    existing[row[key_field]] = row
        for record in records:
            normalized = {field: record.get(field, "") for field in field_order}
            existing[str(normalized[key_field])] = normalized
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=field_order)
            writer.writeheader()
            writer.writerows(existing.values())

    def _upsert_meeting_report_csv(self, path: Path, report_record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, dict[str, Any]] = {}
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    normalized = self._normalize_meeting_report_row(row)
                    existing[self._meeting_report_identity(normalized)] = normalized

        normalized_record = self._normalize_meeting_report_row(report_record)
        existing[self._meeting_report_identity(normalized_record)] = normalized_record

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.REPORT_FIELDS)
            writer.writeheader()
            writer.writerows(existing.values())

    def _upsert_action_tracker_csv(self, path: Path, action_items: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, dict[str, Any]] = {}
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    normalized = self._normalize_action_record(row)
                    existing[self._action_tracker_identity(normalized)] = normalized

        report_prefixes = self._action_report_prefixes(action_items)
        if report_prefixes:
            existing = {
                identity: row
                for identity, row in existing.items()
                if not self._is_current_report_action(row, report_prefixes)
            }

        for record in action_items:
            normalized = self._normalize_action_record(record)
            identity = self._action_tracker_identity(normalized)
            existing[identity] = self._merge_action_tracker_record(existing.get(identity), normalized)

        if report_prefixes:
            existing = self._dedupe_current_action_records(existing, report_prefixes)

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.ACTION_FIELDS)
            writer.writeheader()
            writer.writerows(existing.values())

    def _upsert_action_tracker_bitable(self, table_id: str, action_items: list[dict[str, Any]]) -> None:
        existing_records = self._feishu.list_records(table_id)
        identity_to_record: dict[str, dict[str, Any]] = {}
        for record in existing_records:
            normalized = self._normalize_action_record(record.get("fields", {}))
            identity_to_record[self._action_tracker_identity(normalized)] = record

        updates: list[dict[str, Any]] = []
        creates: list[dict[str, Any]] = []
        for item in action_items:
            normalized = self._normalize_action_record(item)
            identity = self._action_tracker_identity(normalized)
            existing = identity_to_record.get(identity)
            if existing:
                merged = self._merge_action_tracker_record(
                    self._normalize_action_record(existing.get("fields", {})),
                    normalized,
                )
                updates.append({"record_id": existing["record_id"], "fields": merged})
            else:
                creates.append(normalized)

        if updates:
            self._feishu.batch_update_records(table_id, updates)
        if creates:
            self._feishu.batch_create_records(table_id, creates)

    def _upsert_meeting_report_bitable(self, table_id: str, report_record: dict[str, Any]) -> None:
        normalized_record = self._normalize_meeting_report_row(report_record)
        identity = self._meeting_report_identity(normalized_record)
        records = self._feishu.list_records(table_id)
        for record in records:
            fields = self._normalize_meeting_report_row(record.get("fields", {}))
            if self._meeting_report_identity(fields) != identity:
                continue
            self._feishu.batch_update_records(
                table_id,
                [{"record_id": record["record_id"], "fields": normalized_record}],
            )
            return
        self._feishu.create_record(table_id, normalized_record)

    def _sync_action_tracker_to_sheet(self) -> None:
        if not (
            self._feishu_sheets
            and self._settings.feishu_action_tracker_url
            and self._settings.action_tracker_csv
            and self._settings.action_tracker_csv.exists()
        ):
            return
        rows = self._read_csv_rows(self._settings.action_tracker_csv, self.ACTION_FIELDS)
        try:
            self._feishu_sheets.overwrite_rows(
                self._settings.feishu_action_tracker_url,
                headers=self.ACTION_FIELDS,
                rows=rows,
                sheet_title=self._settings.feishu_action_tracker_sheet_title,
            )
        except Exception as exc:
            self._write_sheet_sync_warning("action_tracker", exc)

    def _sync_meeting_reports_to_sheet(self) -> None:
        if not (
            self._feishu_sheets
            and self._settings.feishu_meeting_reports_url
            and self._settings.meeting_reports_csv
            and self._settings.meeting_reports_csv.exists()
        ):
            return
        rows = self._read_csv_rows(self._settings.meeting_reports_csv, self.REPORT_FIELDS)
        try:
            self._feishu_sheets.overwrite_rows(
                self._settings.feishu_meeting_reports_url,
                headers=self.REPORT_FIELDS,
                rows=rows,
                sheet_title=self._settings.feishu_meeting_reports_sheet_title,
            )
        except Exception as exc:
            self._write_sheet_sync_warning("meeting_reports", exc)

    def _write_sheet_sync_warning(self, target: str, exc: Exception) -> None:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "target": target,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "error": self._format_sheet_sync_error(exc),
            "impact": "local_csv_updated_but_feishu_sheet_sync_failed",
        }
        (output_dir / "sheet_writeback_warning_latest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        lines = [
            "# Sheet Writeback Warning",
            "",
            f"- target: {target}",
            f"- generated_at: {payload['generated_at']}",
            "- impact: local CSV was updated, but Feishu Sheet sync failed",
            f"- error: {payload['error']}",
            "",
        ]
        (output_dir / "sheet_writeback_warning_latest.md").write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _format_sheet_sync_error(exc: Exception) -> str:
        text = str(exc)
        if "spreadsheet_token is deleted" in text or "note has been deleted" in text:
            return "飞书 Sheet 链接已失效或表格已删除，本地 CSV 已更新，但飞书任务/会议表未同步。"
        return text

    @staticmethod
    def _read_csv_rows(path: Path, field_order: list[str]) -> list[list[str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [[row.get(field, "") for field in field_order] for row in reader]

    def _normalize_meeting_report_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = {field: row.get(field, "") for field in self.REPORT_FIELDS}
        normalized["Report Path"] = self._normalize_meeting_report_path(str(normalized.get("Report Path", "")).strip())
        return normalized

    def _normalize_action_record(self, row: dict[str, Any]) -> dict[str, Any]:
        return {field: row.get(field, "") for field in self.ACTION_FIELDS}

    @staticmethod
    def _action_report_prefixes(action_items: list[dict[str, Any]]) -> set[str]:
        prefixes: set[str] = set()
        for item in action_items:
            task_id = str(item.get("Task ID", "") or "").strip()
            if re.match(r"^\d{8}-", task_id):
                prefixes.add(task_id[:8])
        return prefixes

    @classmethod
    def _is_current_report_action(cls, row: dict[str, Any], report_prefixes: set[str]) -> bool:
        task_id = str(row.get("Task ID", "") or "").strip()
        return any(task_id.startswith(prefix) for prefix in report_prefixes)

    @classmethod
    def _is_stale_current_action(cls, row: dict[str, Any], report_prefixes: set[str]) -> bool:
        task_id = str(row.get("Task ID", "") or "").strip()
        if not any(task_id.startswith(prefix) for prefix in report_prefixes):
            return False
        text = " ".join(str(row.get(field, "") or "") for field in cls.ACTION_FIELDS)
        stale_snippets = (
            "先把付费净 ROI 拉回到 0.80",
            "付费净 ROI 拉回到 0.80",
            "3日 ROAS 恢复到 1.00",
            "再决定是否恢复预算",
            "再决定是否恢复或扩大预算",
            "降权或停测",
            "放量期间收入/花费比保持在目标线以上",
            "P02 Mermaid / iOS/Facebook 低回收预算",
            "P02 Mermaid / iOS/Facebook 低效付费预算",
            "P02 Mermaid 高回收投放",
            "ROAS=0.00",
            "ROAS 0.00",
        )
        if any(snippet in text for snippet in stale_snippets):
            return True
        if "复制素材" in text and ("已验证效果" in text or "CTR 高于账户中位数" in text):
            return True
        if "暂停" in text and "低效付费投放" in text:
            return True
        return False

    @classmethod
    def _dedupe_current_action_records(
        cls,
        records: dict[str, dict[str, Any]],
        report_prefixes: set[str],
    ) -> dict[str, dict[str, Any]]:
        selected_by_semantic_key: dict[str, str] = {}
        for identity, row in records.items():
            task_id = str(row.get("Task ID", "") or "")
            if not any(task_id.startswith(prefix) for prefix in report_prefixes):
                continue
            semantic_key = cls._action_semantic_key(str(row.get("Type", "") or ""), str(row.get("Title", "") or ""))
            previous_identity = selected_by_semantic_key.get(semantic_key)
            if previous_identity is None or task_id > str(records[previous_identity].get("Task ID", "") or ""):
                selected_by_semantic_key[semantic_key] = identity
        keep_identities = {
            identity
            for identity, row in records.items()
            if not any(str(row.get("Task ID", "") or "").startswith(prefix) for prefix in report_prefixes)
        }
        keep_identities.update(selected_by_semantic_key.values())
        return {identity: row for identity, row in records.items() if identity in keep_identities}

    @staticmethod
    def _merge_action_tracker_record(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
        if not existing:
            return incoming
        merged = dict(incoming)
        existing_status = str(existing.get("Status", "")).strip()
        incoming_status = str(incoming.get("Status", "")).strip()
        if existing_status and incoming_status in {"", "待确认", "Draft"}:
            merged["Status"] = existing_status
        existing_note = str(existing.get("Latest Note", "")).strip()
        if existing_note:
            merged["Latest Note"] = existing_note
        return merged

    @classmethod
    def _dedupe_action_items(cls, items: list[ActionItem]) -> list[ActionItem]:
        deduped: dict[str, ActionItem] = {}
        for item in items:
            key = cls._action_semantic_key(item.action_type, item.title)
            if key not in deduped:
                deduped[key] = item
        return list(deduped.values())

    @classmethod
    def _action_semantic_key(cls, action_type: str, title: str) -> str:
        text = cls._normalize_action_scope(title)
        project = ""
        project_match = re.search(r"\bP0?([247])\b(?:\s+[A-Za-z][A-Za-z0-9_-]*)?", text)
        if project_match:
            project = project_match.group(0)
        segment_match = re.search(r"\b(iOS|Android|Amazon)\s*/\s*(Facebook|Google|ASA|Unity|Applovin|Mintegral)\b", text, re.IGNORECASE)
        segment = segment_match.group(0).lower().replace(" ", "") if segment_match else text.lower()
        return f"{action_type.strip()}||{project.lower()}||{segment}"

    @staticmethod
    def _normalize_action_scope(text: str) -> str:
        normalized = str(text or "")
        normalized = normalized.replace("／", "/")
        normalized = re.sub(r"\s*/\s*", "/", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _normalize_meeting_report_path(self, report_path: str) -> str:
        if not report_path:
            return ""
        normalized = report_path.replace("/", "\\")
        if normalized.startswith("output\\active\\"):
            return normalized
        if normalized.startswith("output\\"):
            suffix = normalized[len("output\\"):]
            candidate = f"output\\active\\{suffix}"
            if Path(candidate).exists():
                return candidate
        return normalized

    @staticmethod
    def _meeting_report_identity(row: dict[str, Any]) -> str:
        meeting_name = str(row.get("Meeting Name", "")).strip()
        report_date = str(row.get("Report Date", "")).strip()
        return f"{meeting_name}||{report_date}"

    @staticmethod
    def _action_tracker_identity(row: dict[str, Any]) -> str:
        source_meeting = str(row.get("Source Meeting", "")).strip()
        title = str(row.get("Title", "")).strip()
        return f"{source_meeting}||{title}"

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row:
                return row[key]
        return ""

    @staticmethod
    def _parse_maybe_date(value: str) -> date:
        match = re.search(r"\d{4}-\d{2}-\d{2}", value or "")
        if not match:
            raise ValueError(f"Unsupported date value: {value!r}")
        return _parse_date(match.group(0))

    @staticmethod
    def _latest_breakdown_csv() -> Path | None:
        downloads_dir = Path.home() / "Downloads"
        candidates = sorted(
            downloads_dir.glob("revenue_breakdown_day_*.csv"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    @classmethod
    def _map_ads_csv(cls, row: dict[str, str]) -> AdsPerformanceRow:
        return AdsPerformanceRow(
            date=_parse_date(str(cls._pick(row, "Date", "date"))),
            game=str(cls._pick(row, "Game", "game") or ""),
            country=str(cls._pick(row, "Country", "country") or ""),
            channel=str(cls._pick(row, "Channel", "channel") or ""),
            ad_id=str(cls._pick(row, "Ad ID", "ad_id") or ""),
            creative_id=str(cls._pick(row, "Creative ID", "creative_id") or ""),
            spend=float(cls._pick(row, "Spend", "spend") or 0),
            clicks=int(float(cls._pick(row, "Clicks", "clicks") or 0)),
            ctr=float(cls._pick(row, "CTR", "ctr") or 0),
            cpi=float(cls._pick(row, "CPI", "cpi") or 0),
            roas=float(cls._pick(row, "ROAS", "roas") or 0),
            retention_d1=float(cls._pick(row, "Retention D1", "retention_d1") or 0),
            retention_d7=float(cls._pick(row, "Retention D7", "retention_d7") or 0),
            retention_d30=float(cls._pick(row, "Retention D30", "retention_d30") or 0),
        )

    @staticmethod
    def _map_ads_feishu(fields: dict[str, Any]) -> AdsPerformanceRow:
        return AdsPerformanceRow(
            date=_parse_date(_to_str(fields.get("Date"))),
            game=_to_str(fields.get("Game")),
            country=_to_str(fields.get("Country")),
            channel=_to_str(fields.get("Channel")),
            ad_id=_to_str(fields.get("Ad ID")),
            creative_id=_to_str(fields.get("Creative ID")),
            spend=_to_float(fields.get("Spend")),
            clicks=_to_int(fields.get("Clicks")),
            ctr=_to_float(fields.get("CTR")),
            cpi=_to_float(fields.get("CPI")),
            roas=_to_float(fields.get("ROAS")),
            retention_d1=_to_float(fields.get("Retention D1")),
            retention_d7=_to_float(fields.get("Retention D7")),
            retention_d30=_to_float(fields.get("Retention D30")),
        )

    @classmethod
    def _map_creative_csv(cls, row: dict[str, str]) -> CreativeAssetRow:
        return CreativeAssetRow(
            asset_id=str(cls._pick(row, "Asset ID", "素材ID", "asset_id") or ""),
            creative_type=str(cls._pick(row, "Creative Type", "素材类型", "creative_type") or ""),
            video_path=str(cls._pick(row, "Video Path", "视频路径", "video_path") or ""),
            game=str(cls._pick(row, "Game", "game") or ""),
            country=str(cls._pick(row, "Country", "country") or ""),
            channel=str(cls._pick(row, "Channel", "channel") or ""),
            ctr=float(cls._pick(row, "CTR", "ctr") or 0),
            cvr=float(cls._pick(row, "CVR", "cvr") or 0),
            roas=float(cls._pick(row, "ROAS", "roas") or 0),
            spend=float(cls._pick(row, "Spend", "花费", "spend") or 0),
            status=str(cls._pick(row, "Status", "status") or ""),
            hook_type=str(cls._pick(row, "Hook Type", "hook_type") or ""),
            duration=float(cls._pick(row, "Duration", "duration") or 0),
            creative_name=str(cls._pick(row, "Creative Name", "素材名称", "creative_name") or ""),
            campaign=str(cls._pick(row, "Campaign", "推广活动", "campaign") or ""),
            campaign_id=str(cls._pick(row, "Campaign ID", "推广活动ID", "campaign_id") or ""),
            adgroup=str(cls._pick(row, "Ad Group", "广告组", "adgroup") or ""),
            adgroup_id=str(cls._pick(row, "Ad Group ID", "广告组ID", "adgroup_id") or ""),
            ad_id=str(cls._pick(row, "Ad ID", "广告ID", "ad_id") or ""),
            ad_name=str(cls._pick(row, "Ad Name", "广告名称", "ad_name") or ""),
            source_name=str(cls._pick(row, "Source", "来源", "source_name") or ""),
            source_id=str(cls._pick(row, "Source ID", "来源ID", "source_id") or ""),
            installs=float(cls._pick(row, "Installs", "安装", "installs") or 0),
            conversions=float(cls._pick(row, "Conversions", "转化", "conversions") or 0),
            revenue_value=float(cls._pick(row, "Revenue Value", "收入值", "revenue_value") or 0),
        )

    @staticmethod
    def _map_creative_feishu(fields: dict[str, Any]) -> CreativeAssetRow:
        return CreativeAssetRow(
            asset_id=_to_str(fields.get("素材ID")),
            creative_type=_to_str(fields.get("素材类型")),
            video_path=_to_str(fields.get("视频路径")),
            game=_to_str(fields.get("游戏")),
            country=_to_str(fields.get("国家")),
            channel=_to_str(fields.get("渠道")),
            ctr=_to_float(fields.get("CTR")),
            cvr=_to_float(fields.get("CVR")),
            roas=_to_float(fields.get("ROAS")),
            spend=_to_float(fields.get("花费")),
            status=_to_str(fields.get("状态")),
            hook_type=_to_str(fields.get("Hook类型")),
            duration=_to_float(fields.get("时长")),
            creative_name=_to_str(fields.get("素材名称")),
            campaign=_to_str(fields.get("推广活动")),
            campaign_id=_to_str(fields.get("推广活动ID")),
            adgroup=_to_str(fields.get("广告组")),
            adgroup_id=_to_str(fields.get("广告组ID")),
            ad_id=_to_str(fields.get("广告ID")),
            ad_name=_to_str(fields.get("广告名称")),
            source_name=_to_str(fields.get("来源")),
            source_id=_to_str(fields.get("来源ID")),
            installs=_to_float(fields.get("安装")),
            conversions=_to_float(fields.get("转化")),
            revenue_value=_to_float(fields.get("收入值")),
        )

    @classmethod
    def _map_revenue_csv(cls, row: dict[str, str]) -> RevenueRow:
        return RevenueRow(
            game=str(cls._pick(row, "Game", "game") or ""),
            date=_parse_date(str(cls._pick(row, "Date", "date"))),
            total_revenue=float(cls._pick(row, "Total Revenue", "总收入", "total_revenue") or 0),
            ltv=float(cls._pick(row, "LTV", "ltv") or 0),
            arpu=float(cls._pick(row, "ARPU", "arpu") or 0),
            arppu=float(cls._pick(row, "ARPPU", "arppu") or 0),
            total_cost=float(cls._pick(row, "Total Cost", "总花费", "total_cost", "cost") or 0),
        )

    @staticmethod
    def _map_revenue_feishu(fields: dict[str, Any]) -> RevenueRow:
        return RevenueRow(
            game=_to_str(fields.get("游戏")),
            date=_parse_date(_to_str(fields.get("日期"))),
            total_revenue=_to_float(fields.get("总收入")),
            ltv=_to_float(fields.get("LTV")),
            arpu=_to_float(fields.get("ARPU")),
            arppu=_to_float(fields.get("ARPPU")),
            total_cost=_to_float(fields.get("总花费") or fields.get("花费") or fields.get("Cost")),
        )

    @classmethod
    def _map_revenue_breakdown_api(cls, row: dict[str, Any]) -> RevenueBreakdownRow:
        iap_revenue_gross = _to_float(row.get("revenue"))
        ad_revenue = _to_float(row.get("ad_revenue"))
        total_revenue_gross = _to_float(row.get("all_revenue")) or (iap_revenue_gross + ad_revenue)
        return RevenueBreakdownRow(
            game=_to_str(row.get("app")),
            date=cls._parse_maybe_date(_to_str(row.get("day") or row.get("date"))),
            store=_to_str(row.get("store_type") or row.get("store")),
            partner=_to_str(row.get("partner_name") or row.get("network") or row.get("partner")),
            country=_to_str(row.get("country") or row.get("geo") or "Global"),
            cost=_to_float(row.get("cost")),
            iap_revenue_gross=iap_revenue_gross,
            ad_revenue=ad_revenue,
            total_revenue_gross=total_revenue_gross,
            campaign=_to_str(row.get("campaign_network") or row.get("campaign")),
            campaign_id=_to_str(row.get("campaign_id_network") or row.get("campaign_id")),
            adgroup=_to_str(row.get("adgroup_network") or row.get("adgroup")),
            adgroup_id=_to_str(row.get("adgroup_id_network") or row.get("adgroup_id")),
            creative_name=_to_str(row.get("creative_network") or row.get("creative")),
            creative_id=_to_str(row.get("creative_id_network") or row.get("creative_id")),
            source_name=_to_str(row.get("source_network") or row.get("source_name") or row.get("source")),
            source_id=_to_str(row.get("source_id_network") or row.get("source_id")),
            installs=_to_float(row.get("installs")),
        )

    @classmethod
    def _map_revenue_breakdown_csv(cls, row: dict[str, str]) -> RevenueBreakdownRow:
        return RevenueBreakdownRow(
            game=str(cls._pick(row, "应用名称", "App", "app") or ""),
            date=cls._parse_maybe_date(str(cls._pick(row, "日期/周期", "日期", "Date") or "")),
            store=str(cls._pick(row, "商店", "Store", "store") or ""),
            partner=str(cls._pick(row, "合作伙伴", "Network", "partner") or ""),
            country=str(cls._pick(row, "国家/地区", "Country", "country") or "Global"),
            cost=float(cls._pick(row, "消耗", "Cost", "cost") or 0),
            iap_revenue_gross=float(cls._pick(row, "内购收入(Gross)", "IAP Revenue (Gross)", "revenue") or 0),
            ad_revenue=float(cls._pick(row, "广告收入", "Ad Revenue", "ad_revenue") or 0),
            total_revenue_gross=float(cls._pick(row, "总收入(Gross)", "Total Revenue (Gross)", "all_revenue") or 0),
            campaign=str(cls._pick(row, "推广活动", "Campaign", "campaign") or ""),
            campaign_id=str(cls._pick(row, "推广活动ID", "Campaign ID", "campaign_id") or ""),
            adgroup=str(cls._pick(row, "广告组", "Ad Group", "Adgroup", "adgroup") or ""),
            adgroup_id=str(cls._pick(row, "广告组ID", "Ad Group ID", "adgroup_id") or ""),
            creative_name=str(cls._pick(row, "素材名称", "Creative", "Creative Name", "creative_name", "creative") or ""),
            creative_id=str(cls._pick(row, "素材ID", "Creative ID", "creative_id") or ""),
            source_name=str(cls._pick(row, "来源名称", "Source Name", "source_name", "source") or ""),
            source_id=str(cls._pick(row, "来源ID", "Source ID", "source_id") or ""),
            installs=float(cls._pick(row, "Installs", "安装", "installs") or 0),
        )

    @staticmethod
    def _map_action_csv(row: dict[str, str]) -> ActionItem:
        return ActionItem(
            task_id=row["Task ID"],
            source_meeting=row["Source Meeting"],
            action_type=row["Type"],
            title=row["Title"],
            owner=row["Owner"],
            status=row["Status"],
            acceptance_metric=row["Acceptance Metric"],
            due_date=_parse_date(row["Due Date"]),
            description=row["Description"],
            latest_note=row.get("Latest Note", ""),
        )

    @staticmethod
    def _map_action_feishu(record: dict[str, Any]) -> ActionItem:
        fields = record["fields"]
        return ActionItem(
            task_id=_to_str(fields.get("Task ID")),
            source_meeting=_to_str(fields.get("Source Meeting")),
            action_type=_to_str(fields.get("Type")),
            title=_to_str(fields.get("Title")),
            owner=_to_str(fields.get("Owner")),
            status=_to_str(fields.get("Status")),
            acceptance_metric=_to_str(fields.get("Acceptance Metric")),
            due_date=_parse_date(_to_str(fields.get("Due Date"))),
            description=_to_str(fields.get("Description")),
            latest_note=_to_str(fields.get("Latest Note")),
            record_id=_to_str(record.get("record_id")) or None,
        )

    @staticmethod
    def action_to_record(item: ActionItem) -> dict[str, Any]:
        return {
            "Task ID": item.task_id,
            "Source Meeting": item.source_meeting,
            "Type": item.action_type,
            "Title": item.title,
            "Owner": item.owner,
            "Status": item.status,
            "Acceptance Metric": item.acceptance_metric,
            "Due Date": item.due_date.isoformat(),
            "Description": item.description,
            "Latest Note": item.latest_note,
        }


class WeeklyPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._analysis_service = CleanAnalysisService(
            ai_client=build_clean_ai_client(settings),
            default_task_owner=settings.default_task_owner,
            default_task_due_days=settings.default_task_due_days,
            task_owner_rules=settings.task_owner_rules,
        )
        self._digest_builder = FinalWeeklyDigestBuilder(settings)

    def run(self, report_date: date, meeting_name: str, *, writeback: bool = True) -> tuple[WeeklyReport, Path]:
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        revenue_rows = self._repository.load_adjust_revenue()

        window_start = report_date - timedelta(days=6)
        weekly_ads = [row for row in ads_rows if window_start <= row.date <= report_date]
        detailed_ads = [row for row in weekly_ads if not (row.channel == "All" and row.country == "All")]
        trusted_detail_ads = self._trusted_detail_ads(detailed_ads)
        company_ads = weekly_ads
        decision_ads = trusted_detail_ads or detailed_ads or weekly_ads
        weekly_creatives = [row for row in creative_rows if row.spend > 0 or row.roas > 0 or row.ctr > 0]
        if not weekly_creatives:
            weekly_creatives = creative_rows
        ad_games = {row.game for row in weekly_ads if row.game}
        weekly_revenue = [
            row
            for row in revenue_rows
            if window_start <= row.date <= report_date and (not ad_games or row.game in ad_games)
        ]
        digest_breakdown_rows = self._repository.load_adjust_revenue_breakdown(report_date - timedelta(days=13), report_date)
        weekly_revenue_breakdown = [
            row for row in digest_breakdown_rows if window_start <= row.date <= report_date
        ]
        if not decision_ads:
            raise ValueError("No ads rows found on or before the requested report date.")

        growth_analysis = self._analysis_service.growth_analysis(company_ads, weekly_revenue)
        creative_analysis = self._analysis_service.creative_analysis(weekly_creatives, decision_ads)
        revenue_analysis = self._analysis_service.revenue_analysis(weekly_revenue, company_ads)
        self._analysis_service.apply_paid_roi_guardrails_to_sections(
            growth_analysis,
            revenue_analysis,
            weekly_revenue_breakdown,
        )
        decisions = self._analysis_service.decisions(
            growth_analysis,
            creative_analysis,
            revenue_analysis,
            weekly_revenue_breakdown,
            weekly_creatives,
        )
        management_action_payload = ManagementActionListBuilder(self._settings).build_payload(report_date)
        management_actions = self._management_actions_to_action_items(
            meeting_name=meeting_name,
            report_date=report_date,
            payload=management_action_payload,
        )
        draft_actions = management_actions or self._analysis_service.draft_actions(meeting_name, report_date, decisions)
        decisions = self._action_items_to_decisions(draft_actions)

        report = WeeklyReport(
            meeting_name=meeting_name,
            report_date=report_date,
            growth_analysis=growth_analysis,
            creative_analysis=creative_analysis,
            revenue_analysis=revenue_analysis,
            decisions=decisions,
            draft_actions=draft_actions,
        )
        digest = self._digest_builder.build(report, ads_rows, creative_rows, revenue_rows, digest_breakdown_rows)
        self._sync_report_sections_from_digest(report, digest)
        report_path = save_markdown_report(report, self._settings.active_output_dir)
        if writeback:
            self._repository.write_action_items([self._repository.action_to_record(item) for item in draft_actions])
            self._repository.write_meeting_report(self._report_to_record(report, report_path))
        return report, report_path

    @staticmethod
    def _sync_report_sections_from_digest(report: WeeklyReport, digest) -> None:
        metric_map = {item.label: item.value for item in digest.company_metrics}
        company_conclusions = [
            f"本周花费 {metric_map.get('本周花费', 'n/a')}，整体收入 {metric_map.get('整体收入', 'n/a')}。",
            f"公司总收入ROI {metric_map.get('公司总收入ROI', 'n/a')}，主投渠道 {metric_map.get('主投渠道', 'n/a')}。",
        ]
        if digest.company_highlights:
            company_conclusions.extend(digest.company_highlights[:2])
        company_highlights = digest.company_highlights[:4] if digest.company_highlights else ["当前暂无公司层亮点。"]
        focus_line = next(
            (line for line in digest.company_highlights if line.startswith("下周重点关注：")),
            "下周重点关注：先检查主要风险段，再决定是否调整预算。",
        )
        if not focus_line.startswith("下周重点关注："):
            focus_line = f"下周重点关注：{focus_line.rstrip('。')}"
        company_recommendations = [
            focus_line,
            f"建议动作：{digest.next_actions[0]}" if digest.next_actions else "建议动作：本周暂无新增动作。",
        ]
        report.growth_analysis = AnalysisSection(
            title="公司总体情况",
            conclusions=company_conclusions[:4],
            highlights=company_highlights,
            recommendations=company_recommendations,
            raw_output={
                "source": "final_digest",
                "company_metrics": metric_map,
                "company_highlights": digest.company_highlights,
            },
        )

        creative_notes = list(digest.creative_notes or [])
        creative_items = list(digest.creative_items or [])
        report.creative_analysis = AnalysisSection(
            title="素材分析",
            conclusions=creative_notes[:3] or ["当前素材层仅作观察，不作为预算增减的主要依据。"],
            highlights=[
                f"{item.asset_id}：样本={item.sample_status or '观察'}，花费={item.spend:.0f}，ROI={item.roas:.2f}"
                for item in creative_items[:3]
            ] or ["当前没有达到复用门槛的素材样本。"],
            recommendations=[
                line
                for line in creative_notes
                if "不作为" in line or "观察" in line or "门槛" in line
            ][:3]
            or ["素材未满足花费或安装门槛前，不生成复制素材任务。"],
            raw_output={
                "source": "final_digest",
                "creative_notes": creative_notes,
                "creative_items": [
                    {
                        "asset_id": item.asset_id,
                        "spend": item.spend,
                        "installs": item.installs,
                        "roas": item.roas,
                        "sample_status": item.sample_status,
                    }
                    for item in creative_items
                ],
            },
        )

        project_conclusions: list[str] = []
        project_highlights: list[str] = []
        project_recommendations: list[str] = []
        for item in digest.project_items[:3]:
            paid_roi_text = f"{item.paid_roi_net:.2f}" if item.paid_roi_net is not None else "n/a"
            project_conclusions.append(
                f"{item.game}：花费 {item.spend:.0f}，总收入ROI {item.project_roi:.2f}，付费净ROI {paid_roi_text}。"
                if item.paid_roi_net is not None
                else f"{item.game}：花费 {item.spend:.0f}，总收入ROI {item.project_roi:.2f}。"
            )
            project_highlights.append(
                f"{item.game}：总收入 {item.total_revenue:.0f}，主投渠道 {item.top_channel or 'n/a'}，风险组合 {item.risk_segment or 'n/a'}。"
            )
            project_recommendations.append(f"{item.game}：{item.forecast_recommendation or item.judgement}")
        report.revenue_analysis = AnalysisSection(
            title="项目收入与回收判断",
            conclusions=project_conclusions or ["当前暂无项目结论。"],
            highlights=project_highlights or ["当前暂无项目重点。"],
            recommendations=project_recommendations or ["当前暂无项目建议。"],
            raw_output={
                "source": "final_digest",
                "project_items": [
                    {
                        "game": item.game,
                        "spend": item.spend,
                        "project_roi": item.project_roi,
                        "paid_roi_net": item.paid_roi_net,
                        "total_revenue": item.total_revenue,
                        "top_channel": item.top_channel,
                        "risk_segment": item.risk_segment,
                        "forecast_recommendation": item.forecast_recommendation,
                        "judgement": item.judgement,
                    }
                    for item in digest.project_items
                ],
            },
        )

    @staticmethod
    def _management_actions_to_action_items(meeting_name: str, report_date: date, payload: dict[str, Any]) -> list[ActionItem]:
        items: list[ActionItem] = []
        due_date_default = report_date + timedelta(days=7)
        for raw in payload.get("items", [])[:3]:
            action_type = ManagementActionListBuilder._infer_action_type(str(raw.get("action") or ""))
            project = str(raw.get("project") or "").strip()
            scope = str(raw.get("scope") or "").strip()
            target = f"{project} / {scope}".strip(" /")
            if not target:
                continue
            due_date = DataRepository._parse_maybe_date(str(raw.get("due_date") or due_date_default.isoformat()))
            kpi = str(raw.get("verification_metric") or "先看3日ROAS与项目级回收是否改善，再决定是否提高验证预算")
            reason = str(raw.get("reason") or raw.get("problem") or "")
            impact = str(raw.get("action") or "")
            items.append(
                ActionItem(
                    task_id=CleanAnalysisService.build_task_id(report_date, action_type, target),
                    source_meeting=meeting_name,
                    action_type=action_type,
                    title=f"{action_type}：{target}",
                    owner=str(raw.get("owner") or "林凯"),
                    status="待确认",
                    acceptance_metric=kpi,
                    due_date=due_date,
                    description=f"{reason} 行动：{impact}".strip(),
                )
            )
        return DataRepository._dedupe_action_items(items)

    @staticmethod
    def _action_items_to_decisions(action_items: list[ActionItem]) -> list[Any]:
        from market_ops.models import DecisionItem

        decisions: list[DecisionItem] = []
        for item in action_items:
            prefix = f"{item.action_type}："
            target = item.title[len(prefix) :] if item.title.startswith(prefix) else item.title
            decisions.append(
                DecisionItem(
                    recommendation_type=item.action_type,
                    target=target,
                    owner=item.owner,
                    kpi_target=item.acceptance_metric,
                    estimated_impact=item.description,
                    reason=item.description,
                )
            )
        return decisions

    def _trusted_detail_ads(self, rows: list[AdsPerformanceRow]) -> list[AdsPerformanceRow]:
        trusted_projects = self._settings.trusted_detail_project_keys
        return [
            row
            for row in rows
            if not (row.channel == "All" and row.country == "All") and self._project_key(row.game) in trusted_projects
        ]

    @staticmethod
    def _project_key(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            return ""
        match = re.search(r"\bP0*([0-9]+)\b", cleaned.upper())
        if match:
            return f"P{int(match.group(1)):02d}"
        simplified = re.sub(r"(?i)\bamazon\b", "", cleaned)
        simplified = re.sub(r"\s+", " ", simplified).strip(" -")
        return simplified or cleaned

    @staticmethod
    def _report_to_record(report: WeeklyReport, report_path: Path) -> dict[str, Any]:
        return {
            "Meeting Name": report.meeting_name,
            "Report Date": report.report_date.isoformat(),
            "Growth Summary": " | ".join(report.growth_analysis.conclusions),
            "Creative Summary": " | ".join(report.creative_analysis.conclusions),
            "Revenue Summary": " | ".join(report.revenue_analysis.conclusions),
            "Report Path": str(report_path),
        }


class MeetingApprovalPipeline:
    def __init__(self, settings: Settings) -> None:
        self._repository = DataRepository(settings)

    def run(self, meeting_name: str, report_date: date) -> int:
        action_items = self._repository.load_action_tracker()
        prefix = report_date.strftime("%Y%m%d")
        updated = 0
        for item in action_items:
            if item.source_meeting != meeting_name:
                continue
            if not item.task_id.startswith(prefix):
                continue
            if item.status not in {"待确认", "Draft"}:
                continue
            item.status = "执行中"
            item.latest_note = f"已于 {report_date.isoformat()} 会议确认，进入执行。"
            updated += 1
        self._repository.update_action_items(action_items)
        return updated


class DailySyncPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._task_sync_service = TaskSyncService()

    def run(self, as_of_date: date) -> Path:
        action_items = self._repository.load_action_tracker()
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        sync_report = self._task_sync_service.sync(
            action_items=action_items,
            ads_rows=[row for row in ads_rows if row.date <= as_of_date],
            creative_rows=creative_rows,
            as_of_date=as_of_date,
        )
        self._repository.update_action_items(action_items)
        return save_daily_sync_report(sync_report, self._settings.active_output_dir)


class FeishuSourceSyncPipeline:
    def __init__(self, settings: Settings) -> None:
        self._service = FeishuSheetsSyncService(settings)

    def run(self) -> dict[str, Any]:
        return self._service.sync()


class WeeklyDigestPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._weekly_pipeline = WeeklyPipeline(settings)
        self._digest_builder = FinalWeeklyDigestBuilder(settings)

    def run(
        self,
        report_date: date,
        meeting_name: str,
        send: bool,
        market_detailed: bool = False,
    ) -> tuple[Path, dict[str, Any] | None]:
        report, _ = self._weekly_pipeline.run(report_date=report_date, meeting_name=meeting_name)
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        revenue_rows = self._repository.load_adjust_revenue()
        revenue_breakdown_rows = self._repository.load_adjust_revenue_breakdown(report_date - timedelta(days=13), report_date)
        digest = self._digest_builder.build(report, ads_rows, creative_rows, revenue_rows, revenue_breakdown_rows)
        digest_path = self._digest_builder.save_markdown(digest, self._settings.active_output_dir)

        send_result = None
        if send:
            webhook = (self._settings.feishu_market_webhook or self._settings.feishu_bot_webhook or "").strip()
            if not webhook:
                raise ValueError("FEISHU_MARKET_WEBHOOK is required when --send is used.")
            bot = FeishuBotClient(webhook)
            market_card = self._digest_builder.build_card(digest) if market_detailed else self._digest_builder.build_simple_card(digest)
            send_result = bot.send_card(market_card)
        return digest_path, send_result


class ExecutiveReportPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._builder = FinalExecutiveReportBuilder(settings)
        self._weekly_pipeline = WeeklyPipeline(settings)
        self._digest_builder = FinalWeeklyDigestBuilder(settings)

    def run(self, report_date: date, period: str, send: bool) -> tuple[Path, dict[str, Any] | None]:
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        revenue_rows = self._repository.load_adjust_revenue()
        revenue_breakdown_rows = self._repository.load_adjust_revenue_breakdown(report_date - timedelta(days=70), report_date)
        market_digest = None
        if period == "weekly":
            weekly_report, _ = self._weekly_pipeline.run(report_date=report_date, meeting_name="Weekly Market Ops Review")
            market_digest = self._digest_builder.build(
                weekly_report,
                ads_rows,
                creative_rows,
                revenue_rows,
                self._repository.load_adjust_revenue_breakdown(report_date - timedelta(days=13), report_date),
            )
        report = self._builder.build(
            period=period,
            report_date=report_date,
            ads_rows=ads_rows,
            creative_rows=creative_rows,
            revenue_rows=revenue_rows,
            revenue_breakdown_rows=revenue_breakdown_rows,
            market_digest=market_digest,
        )
        report_path = self._builder.save_markdown(report, self._settings.active_output_dir, period)

        send_result = None
        if send:
            if not self._settings.allow_boss_send:
                raise ValueError("Boss send is locked. Set ALLOW_BOSS_SEND=true and FEISHU_BOSS_WEBHOOK before using --send.")
            webhook = (self._settings.feishu_boss_webhook or "").strip()
            if not webhook:
                raise ValueError("FEISHU_BOSS_WEBHOOK is required when sending the executive report.")
            bot = FeishuBotClient(webhook)
            send_result = bot.send_card(self._builder.build_card(report))
        return report_path, send_result


class ForecastValidationPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._weekly_pipeline = WeeklyPipeline(settings)
        self._digest_builder = FinalWeeklyDigestBuilder(settings)
        self._builder = ForecastValidationReportBuilder(self._digest_builder)

    def run(self, report_date: date, meeting_name: str) -> Path:
        report, _ = self._weekly_pipeline.run(report_date=report_date, meeting_name=meeting_name)
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        revenue_rows = self._repository.load_adjust_revenue()
        revenue_breakdown_rows = self._repository.load_adjust_revenue_breakdown(report_date - timedelta(days=13), report_date)
        digest = self._digest_builder.build(report, ads_rows, creative_rows, revenue_rows, revenue_breakdown_rows)
        validation_report = self._builder.build(digest, revenue_breakdown_rows)
        return self._builder.save_markdown(validation_report, self._settings.active_output_dir)


class WeeklyBroadcastPipeline:
    def __init__(self, settings: Settings) -> None:
        self._digest_pipeline = WeeklyDigestPipeline(settings)
        self._executive_pipeline = ExecutiveReportPipeline(settings)

    def run(
        self,
        report_date: date,
        meeting_name: str,
        send: bool,
        digest_market_detailed: bool = False,
    ) -> tuple[dict[str, Path], dict[str, Any] | None]:
        digest_path, digest_send_result = self._digest_pipeline.run(
            report_date=report_date,
            meeting_name=meeting_name,
            send=send,
            market_detailed=digest_market_detailed,
        )
        executive_path, executive_send_result = self._executive_pipeline.run(
            report_date=report_date,
            period="weekly",
            send=send,
        )
        send_result = None
        if send:
            send_result = {
                "weekly_digest": digest_send_result,
                "executive_report": executive_send_result,
            }
        return {
            "weekly_digest": digest_path,
            "executive_report": executive_path,
        }, send_result


class MeetingCloseoutPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)

    def run(
        self,
        report_date: date,
        meeting_name: str,
        send: bool,
    ) -> tuple[int, Path, dict[str, Any] | None]:
        action_items = self._repository.load_action_tracker()
        approved_items = self._approve_pending_items(
            action_items=action_items,
            report_date=report_date,
            meeting_name=meeting_name,
        )
        if approved_items:
            self._repository.update_action_items(action_items)

        summary_path = self._save_summary(
            report_date=report_date,
            meeting_name=meeting_name,
            approved_items=approved_items,
        )

        send_result = None
        if send:
            webhook = (self._settings.feishu_market_webhook or self._settings.feishu_bot_webhook or "").strip()
            if not webhook:
                raise ValueError("FEISHU_MARKET_WEBHOOK is required when sending meeting closeout.")
            bot = FeishuBotClient(webhook)
            send_result = bot.send_card(
                self._build_card(
                    report_date=report_date,
                    meeting_name=meeting_name,
                    approved_items=approved_items,
                )
            )
        return len(approved_items), summary_path, send_result

    def _approve_pending_items(
        self,
        action_items: list[ActionItem],
        report_date: date,
        meeting_name: str,
    ) -> list[ActionItem]:
        prefix = report_date.strftime("%Y%m%d")
        approved_items: list[ActionItem] = []
        for item in action_items:
            if item.source_meeting != meeting_name:
                continue
            if not item.task_id.startswith(prefix):
                continue
            if item.status not in {"待确认", "Draft"}:
                continue
            item.status = "执行中"
            item.latest_note = f"已于 {report_date.isoformat()} 会议确认，进入执行。"
            approved_items.append(item)
        return approved_items

    def _save_summary(
        self,
        report_date: date,
        meeting_name: str,
        approved_items: list[ActionItem],
    ) -> Path:
        self._settings.active_output_dir.mkdir(parents=True, exist_ok=True)
        path = self._settings.active_output_dir / f"meeting_closeout_{report_date.strftime('%Y%m%d')}.md"

        lines = [
            f"# {meeting_name} | {report_date.isoformat()} 会后确认",
            "",
            f"- 本次推进执行的动作数：{len(approved_items)}",
        ]
        if approved_items:
            owner_counts = Counter(item.owner or self._settings.default_task_owner for item in approved_items)
            action_counts = Counter(item.action_type for item in approved_items)
            lines.append(f"- 负责人分布：{self._format_counter(owner_counts)}")
            lines.append(f"- 动作类型分布：{self._format_counter(action_counts)}")
            lines.extend(["", "## 已确认动作", ""])
            for item in approved_items:
                owner = item.owner or self._settings.default_task_owner
                lines.append(
                    f"- {item.task_id} | {item.action_type} | {owner} | 截止 {item.due_date.isoformat()} | KPI: {item.acceptance_metric}"
                )
        else:
            lines.append("- 本次没有新的待确认动作被推进执行。")
        lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _build_card(
        self,
        report_date: date,
        meeting_name: str,
        approved_items: list[ActionItem],
    ) -> dict[str, Any]:
        owner_counts = Counter(item.owner or self._settings.default_task_owner for item in approved_items)
        action_counts = Counter(item.action_type for item in approved_items)
        summary_lines = [
            f"- 会议：{meeting_name}",
            f"- 日期：{report_date.isoformat()}",
            f"- 本次推进执行动作数：{len(approved_items)}",
        ]
        if approved_items:
            summary_lines.append(f"- 负责人分布：{self._format_counter(owner_counts)}")
            summary_lines.append(f"- 动作类型分布：{self._format_counter(action_counts)}")
            action_lines = [
                (
                    f"- `{item.task_id}` {item.action_type} | {item.owner or self._settings.default_task_owner}"
                    f" | 截止 `{item.due_date.isoformat()}` | KPI：{item.acceptance_metric}"
                )
                for item in approved_items
            ]
        else:
            action_lines = ["- 本次没有新的待确认动作被推进执行。"]

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green",
                "title": {"tag": "plain_text", "content": f"{meeting_name} | 会后确认 | {report_date.isoformat()}"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "**会议收尾结果**\n" + "\n".join(summary_lines)},
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "**已进入执行的动作**\n" + "\n".join(action_lines)},
                },
            ],
        }

    @staticmethod
    def _format_counter(counter: Counter[str]) -> str:
        if not counter:
            return "无"
        return "，".join(f"{key} {value}" for key, value in counter.items())


class BitableSyncPipeline:
    """将周报结构化数据写入飞书多维表格 + 生成 HTML 图表报告。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._weekly_pipeline = WeeklyPipeline(settings)
        if settings.using_bitable_report:
            self._feishu = FeishuClient(
                settings.feishu_app_id or "",
                settings.feishu_app_secret or "",
                settings.feishu_bitable_app_token or "",
            )
        else:
            self._feishu = None

    def run(
        self,
        report_date: date,
        meeting_name: str = "Weekly Market Ops Review",
        html_only: bool = False,
        bitable_only: bool = False,
    ) -> BitableSyncResult:
        # 1) 构建周报 + digest
        report, _report_path = self._weekly_pipeline.run(
            meeting_name=meeting_name,
            report_date=report_date,
            writeback=False,
        )
        ads_rows = self._repository.load_ads_performance()
        creative_rows = self._repository.load_creative_library()
        revenue_rows = self._repository.load_adjust_revenue()
        window_start = report_date - timedelta(days=6)
        weekly_ads = [row for row in ads_rows if window_start <= row.date <= report_date]
        breakdown_rows = self._repository.load_adjust_revenue_breakdown(
            report_date - timedelta(days=13), report_date
        )
        weekly_breakdown = [
            row for row in breakdown_rows if window_start <= row.date <= report_date
        ]
        digest = self._weekly_pipeline._digest_builder.build(
            report, ads_rows, creative_rows, revenue_rows, breakdown_rows
        )

        # 2) 加载/构建分析模块 JSON payload
        decision_payload = self._load_analysis_payload("decision_engine", report_date)
        creative_fatigue_payload = self._load_analysis_payload("creative_fatigue", report_date)
        lifecycle_payload = self._load_analysis_payload("lifecycle_prediction", report_date)
        dynamic_payback_payload = self._load_analysis_payload("dynamic_payback", report_date)

        # 3) 构建 Bitable records + chart data
        from market_ops.bitable_report import BitableReportBuilder
        builder = BitableReportBuilder(self._settings)
        payload = builder.build_payload(
            report_date=report_date,
            digest=digest,
            decision_payload=decision_payload,
            creative_fatigue_payload=creative_fatigue_payload,
            lifecycle_payload=lifecycle_payload,
            action_items=report.draft_actions,
            dynamic_payback_payload=dynamic_payback_payload,
        )

        # 4) 写入多维表格
        tables_synced: list[str] = []
        records_written: dict[str, int] = {}
        table_ids: dict[str, str] = {}
        if not html_only and self._feishu:
            table_map = self._sync_all_tables(payload)
            for name, info in table_map.items():
                tables_synced.append(name)
                records_written[name] = info["count"]
                table_ids[name] = info["table_id"]

        # 5) 生成 HTML 报告
        html_path: Path | None = None
        if not bitable_only:
            from market_ops.bitable_html import BitableHtmlReportBuilder
            html_builder = BitableHtmlReportBuilder(self._settings)
            html_path = html_builder.build(report_date, payload)

        return BitableSyncResult(
            report_date=report_date,
            tables_synced=tables_synced,
            records_written=records_written,
            html_path=html_path,
            table_ids=table_ids,
        )

    def _sync_all_tables(
        self, payload: Any
    ) -> dict[str, dict[str, Any]]:
        from market_ops.bitable_schema import get_table_id_map, get_table_schema
        table_id_map = get_table_id_map(self._settings)
        records_map = {
            "公司指标总览": payload.kpi_overview_records,
            "项目分析表": payload.project_records,
            "Campaign明细表": payload.campaign_records,
            "素材分析表": payload.creative_records,
            "决策分布表": payload.decision_records,
            "行动追踪表": payload.action_records,
        }
        result: dict[str, dict[str, Any]] = {}
        for table_name, records in records_map.items():
            table_id = table_id_map.get(table_name)
            if not table_id:
                schema = get_table_schema(table_name)
                table_id = self._feishu.create_table(table_name, schema)
            if table_name == "行动追踪表":
                # Phase 5: upsert 模式 — 按 Task ID 匹配更新，保留历史状态
                count = self._upsert_action_table(table_id, records)
                result[table_name] = {"table_id": table_id, "count": count}
                continue
            existing = self._feishu.list_records(table_id)
            if existing:
                record_ids = [r["record_id"] for r in existing]
                self._feishu.batch_delete_records(table_id, record_ids)
            if records:
                self._feishu.batch_create_records(table_id, records)
            result[table_name] = {"table_id": table_id, "count": len(records)}
        return result

    def _upsert_action_table(
        self, table_id: str, records: list[dict[str, Any]]
    ) -> int:
        """Phase 5: 行动追踪表 upsert — 按 Task ID 匹配，已有则更新，新则创建。"""
        if not self._feishu:
            return 0
        existing = self._feishu.list_records(table_id) or []
        # Build lookup: Task ID -> record_id
        existing_map: dict[str, str] = {}
        for rec in existing:
            fields = rec.get("fields", {})
            task_id = fields.get("Task ID", "")
            if task_id:
                existing_map[task_id] = rec["record_id"]

        to_create: list[dict[str, Any]] = []
        to_update: list[dict[str, Any]] = []
        for record in records:
            task_id = record.get("Task ID", "")
            if task_id and task_id in existing_map:
                to_update.append({
                    "record_id": existing_map[task_id],
                    "fields": record,
                })
            else:
                to_create.append(record)

        # Batch create new records
        if to_create:
            self._feishu.batch_create_records(table_id, to_create)
        # Batch update existing records
        if to_update:
            self._feishu.batch_update_records(table_id, to_update)

        return len(records)

    def _load_analysis_payload(self, module_name: str, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        active = self._settings.active_output_dir
        path = active / f"{module_name}_{suffix}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        builders = {
            "decision_engine": "market_ops.decision_engine.DecisionEngineBuilder",
            "creative_fatigue": "market_ops.creative_fatigue.CreativeFatigueBuilder",
            "lifecycle_prediction": "market_ops.lifecycle_prediction.LifecyclePredictionBuilder",
            "dynamic_payback": "market_ops.dynamic_payback.DynamicPaybackBuilder",
        }
        builder_path = builders.get(module_name)
        if not builder_path:
            return {}
        try:
            module_import, class_name = builder_path.rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_import)
            cls = getattr(mod, class_name)
            builder = cls(self._settings)
            builder.build(report_date)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}


@dataclass(slots=True)
class BitableSyncResult:
    report_date: date
    tables_synced: list[str]
    records_written: dict[str, int]
    html_path: Path | None
    table_ids: dict[str, str]
