from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _project_key_from_name(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    import re

    match = re.search(r"\bP0*([0-9]+)\b", text.upper())
    if match:
        return f"P{int(match.group(1)):02d}"
    simplified = re.sub(r"(?i)\bamazon\b", "", text)
    simplified = re.sub(r"\s+", " ", simplified).strip(" -")
    return simplified or text


@dataclass(slots=True)
class Settings:
    ai_provider: str
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str | None
    feishu_app_id: str | None
    feishu_app_secret: str | None
    feishu_bitable_app_token: str | None
    ads_performance_table_id: str | None
    creative_library_table_id: str | None
    adjust_revenue_table_id: str | None
    action_tracker_table_id: str | None
    meeting_reports_table_id: str | None
    bitable_kpi_overview_table_id: str | None
    bitable_project_analysis_table_id: str | None
    bitable_campaign_detail_table_id: str | None
    bitable_creative_analysis_table_id: str | None
    bitable_decision_distribution_table_id: str | None
    bitable_action_tracking_table_id: str | None
    bitable_video_creative_table_id: str | None
    feishu_overview_url: str | None
    feishu_daily_data_url: str | None
    feishu_roi_url: str | None
    project_sheet_sources: list[dict[str, str]]
    feishu_creative_url: str | None
    feishu_adjust_url: str | None
    feishu_action_tracker_url: str | None
    feishu_action_tracker_sheet_title: str | None
    feishu_meeting_reports_url: str | None
    feishu_meeting_reports_sheet_title: str | None
    meta_access_token: str | None
    meta_ad_account_id: str | None
    meta_api_version: str
    meta_creative_lookback_days: int
    tecdo_app_id: str | None
    tecdo_app_secret: str | None
    tecdo_base_url: str
    tecdo_media_accounts: list[dict[str, Any]]
    tecdo_media_account_ids: list[str]
    tecdo_probe_platforms: list[int]
    tecdo_creative_lookback_days: int
    google_ads_developer_token: str | None
    google_ads_client_id: str | None
    google_ads_client_secret: str | None
    google_ads_refresh_token: str | None
    google_ads_customer_id: str | None
    google_ads_login_customer_id: str | None
    google_ads_creative_lookback_days: int
    creative_action_min_spend: float
    creative_action_min_roi: float
    adjust_api_token: str | None
    adjust_dashboard_config_path: Path | None
    feishu_bot_webhook: str | None
    feishu_market_webhook: str | None
    feishu_boss_webhook: str | None
    allow_boss_send: bool
    feishu_event_verification_token: str | None
    feishu_event_encrypt_key: str | None
    feishu_event_path: str
    feishu_detail_trigger_keywords: list[str]
    feishu_detail_allowed_chat_ids: list[str]
    company_overview_url: str | None
    company_overview_markdown: Path | None
    ads_performance_csv: Path | None
    creative_library_csv: Path | None
    adjust_revenue_csv: Path | None
    geo_performance_csv: Path | None
    action_tracker_csv: Path | None
    meeting_reports_csv: Path | None
    output_dir: Path
    default_task_owner: str
    default_task_due_days: int
    default_game_name: str
    task_owner_rules: dict[str, dict[str, str]]

    @property
    def active_output_dir(self) -> Path:
        return self.output_dir / "active"

    @property
    def archive_output_dir(self) -> Path:
        return self.output_dir / "archive"

    @property
    def using_csv(self) -> bool:
        return any(
            path is not None
            for path in (
                self.ads_performance_csv,
                self.creative_library_csv,
                self.adjust_revenue_csv,
                self.action_tracker_csv,
                self.meeting_reports_csv,
            )
        )

    @property
    def using_feishu_bitable(self) -> bool:
        return bool(
            self.feishu_app_id
            and self.feishu_app_secret
            and self.feishu_bitable_app_token
            and self.ads_performance_table_id
            and self.creative_library_table_id
        )

    @property
    def using_bitable_report(self) -> bool:
        return bool(
            self.feishu_app_id
            and self.feishu_app_secret
            and self.feishu_bitable_app_token
        )

    @property
    def using_feishu_sheet_sources(self) -> bool:
        return bool(
            self.feishu_app_id
            and self.feishu_app_secret
            and (self.feishu_daily_data_url or self.project_sheet_sources)
            and (self.feishu_creative_url or self.using_api_creative_source)
        )

    @property
    def using_feishu_sheet_writeback(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    @property
    def using_meta_creative_source(self) -> bool:
        return bool(self.meta_access_token and self.meta_ad_account_id)

    @property
    def using_tecdo_creative_source(self) -> bool:
        return bool(self.tecdo_app_secret and self.tecdo_effective_media_accounts)

    @property
    def using_google_creative_source(self) -> bool:
        return bool(
            self.google_ads_developer_token
            and self.google_ads_client_id
            and self.google_ads_client_secret
            and self.google_ads_refresh_token
            and self.google_ads_customer_id
        )

    @property
    def using_api_creative_source(self) -> bool:
        return self.using_meta_creative_source or self.using_tecdo_creative_source or self.using_google_creative_source

    @property
    def tecdo_effective_media_accounts(self) -> list[dict[str, Any]]:
        if self.tecdo_media_accounts:
            return list(self.tecdo_media_accounts)
        accounts: list[dict[str, Any]] = []
        for media_account_id in self.tecdo_media_account_ids:
            for platform in self.tecdo_probe_platforms:
                accounts.append(
                    {
                        "mediaPlatform": int(platform),
                        "mediaAccountId": str(media_account_id),
                    }
                )
        return accounts

    @property
    def trusted_detail_project_keys(self) -> set[str]:
        pair_to_games: dict[tuple[str, str], set[str]] = {}
        daily_to_games: dict[str, set[str]] = {}
        roi_to_games: dict[str, set[str]] = {}
        for item in self.project_sheet_sources:
            game = str(item.get("game") or "").strip()
            daily_url = str(item.get("daily_url") or "").strip()
            roi_url = str(item.get("roi_url") or "").strip() or daily_url
            if not game or not daily_url:
                continue
            pair_to_games.setdefault((daily_url, roi_url), set()).add(game)
            daily_to_games.setdefault(daily_url, set()).add(game)
            roi_to_games.setdefault(roi_url, set()).add(game)

        trusted: set[str] = set()
        for games in pair_to_games.values():
            if len(games) == 1:
                trusted.add(_project_key_from_name(next(iter(games))))

        default_daily_url = str(self.feishu_daily_data_url or "").strip()
        default_roi_url = str(self.feishu_roi_url or "").strip() or default_daily_url
        default_game_key = _project_key_from_name(self.default_game_name)
        if default_daily_url:
            default_games = pair_to_games.get((default_daily_url, default_roi_url))
            daily_games = daily_to_games.get(default_daily_url, set())
            roi_games = roi_to_games.get(default_roi_url, set())
            if (
                (default_games is None or default_games == {self.default_game_name.strip()})
                and (not daily_games or daily_games == {self.default_game_name.strip()})
                and (not roi_games or roi_games == {self.default_game_name.strip()})
            ):
                trusted.add(default_game_key)

        return {item for item in trusted if item}


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _list_from_env(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = [item.strip() for item in value.split(",")]
    return [item for item in parsed if item]


def _int_list_from_env(value: str | None, default: list[int]) -> list[int]:
    if not value:
        return list(default)
    items: list[int] = []
    for raw in value.replace("\n", ",").split(","):
        text = raw.strip()
        if not text:
            continue
        try:
            items.append(int(text))
        except ValueError:
            continue
    return items or list(default)


def _id_list_from_env(value: str | None) -> list[str]:
    if not value:
        return []
    items: list[str] = []
    for raw in value.replace("\r", "\n").replace(",", "\n").split("\n"):
        text = raw.strip()
        if text:
            items.append(text)
    return items


def _owner_rules_from_env(value: str | None) -> dict[str, dict[str, str]]:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}

    result: dict[str, dict[str, str]] = {}
    for section in ("by_action_type", "by_game", "by_target_keyword"):
        section_value = payload.get(section)
        if not isinstance(section_value, dict):
            continue
        normalized = {
            str(key).strip(): str(owner).strip()
            for key, owner in section_value.items()
            if str(key).strip() and str(owner).strip()
        }
        if normalized:
            result[section] = normalized
    return result


def _project_sheet_sources_from_env(value: str | None) -> list[dict[str, str]]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    sources: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        daily_url = str(item.get("daily_url") or "").strip()
        game = str(item.get("game") or "").strip()
        if not daily_url or not game:
            continue
        roi_url = str(item.get("roi_url") or "").strip()
        source: dict[str, str] = {
            "game": game,
            "daily_url": daily_url,
        }
        if roi_url:
            source["roi_url"] = roi_url
        sources.append(source)
    return sources


def _tecdo_media_accounts_from_env(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    accounts: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        media_platform = item.get("mediaPlatform")
        media_account_id = str(item.get("mediaAccountId") or "").strip()
        if media_platform in (None, "") or not media_account_id:
            continue
        try:
            platform_value = int(media_platform)
        except (TypeError, ValueError):
            continue
        account: dict[str, Any] = {
            "mediaPlatform": platform_value,
            "mediaAccountId": media_account_id,
        }
        game = str(item.get("game") or "").strip()
        if game:
            account["game"] = game
        channel = str(item.get("channel") or "").strip()
        if channel:
            account["channel"] = channel
        accounts.append(account)
    return accounts


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        ai_provider=os.getenv("AI_PROVIDER", "mock").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        feishu_app_id=os.getenv("FEISHU_APP_ID") or None,
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET") or None,
        feishu_bitable_app_token=os.getenv("FEISHU_BITABLE_APP_TOKEN") or None,
        ads_performance_table_id=os.getenv("ADS_PERFORMANCE_TABLE_ID") or None,
        creative_library_table_id=os.getenv("CREATIVE_LIBRARY_TABLE_ID") or None,
        adjust_revenue_table_id=os.getenv("ADJUST_REVENUE_TABLE_ID") or None,
        action_tracker_table_id=os.getenv("ACTION_TRACKER_TABLE_ID") or None,
        meeting_reports_table_id=os.getenv("MEETING_REPORTS_TABLE_ID") or None,
        bitable_kpi_overview_table_id=os.getenv("BITABLE_KPI_OVERVIEW_TABLE_ID") or None,
        bitable_project_analysis_table_id=os.getenv("BITABLE_PROJECT_ANALYSIS_TABLE_ID") or None,
        bitable_campaign_detail_table_id=os.getenv("BITABLE_CAMPAIGN_DETAIL_TABLE_ID") or None,
        bitable_creative_analysis_table_id=os.getenv("BITABLE_CREATIVE_ANALYSIS_TABLE_ID") or None,
        bitable_decision_distribution_table_id=os.getenv("BITABLE_DECISION_DISTRIBUTION_TABLE_ID") or None,
        bitable_action_tracking_table_id=os.getenv("BITABLE_ACTION_TRACKING_TABLE_ID") or None,
        bitable_video_creative_table_id=os.getenv("BITABLE_VIDEO_CREATIVE_TABLE_ID") or None,
        feishu_overview_url=os.getenv("FEISHU_OVERVIEW_URL") or None,
        feishu_daily_data_url=os.getenv("FEISHU_DAILY_DATA_URL") or None,
        feishu_roi_url=os.getenv("FEISHU_ROI_URL") or None,
        project_sheet_sources=_project_sheet_sources_from_env(os.getenv("FEISHU_PROJECT_SHEET_SOURCES_JSON")),
        feishu_creative_url=os.getenv("FEISHU_CREATIVE_URL") or None,
        feishu_adjust_url=os.getenv("FEISHU_ADJUST_URL") or None,
        feishu_action_tracker_url=os.getenv("FEISHU_ACTION_TRACKER_URL") or None,
        feishu_action_tracker_sheet_title=os.getenv("FEISHU_ACTION_TRACKER_SHEET_TITLE") or None,
        feishu_meeting_reports_url=os.getenv("FEISHU_MEETING_REPORTS_URL") or None,
        feishu_meeting_reports_sheet_title=os.getenv("FEISHU_MEETING_REPORTS_SHEET_TITLE") or None,
        meta_access_token=os.getenv("META_ACCESS_TOKEN") or None,
        meta_ad_account_id=os.getenv("META_AD_ACCOUNT_ID") or None,
        meta_api_version=os.getenv("META_API_VERSION", "v22.0").strip(),
        meta_creative_lookback_days=int(os.getenv("META_CREATIVE_LOOKBACK_DAYS", "7")),
        tecdo_app_id=os.getenv("TECDO_APP_ID") or None,
        tecdo_app_secret=os.getenv("TECDO_APP_SECRET") or None,
        tecdo_base_url=os.getenv("TECDO_BASE_URL", "https://open-power.tec-do.cn").strip().rstrip("/"),
        tecdo_media_accounts=_tecdo_media_accounts_from_env(os.getenv("TECDO_MEDIA_ACCOUNTS_JSON")),
        tecdo_media_account_ids=_id_list_from_env(os.getenv("TECDO_MEDIA_ACCOUNT_IDS")),
        tecdo_probe_platforms=_int_list_from_env(os.getenv("TECDO_PROBE_PLATFORMS"), [1, 2]),
        tecdo_creative_lookback_days=int(os.getenv("TECDO_CREATIVE_LOOKBACK_DAYS", "7")),
        google_ads_developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") or None,
        google_ads_client_id=os.getenv("GOOGLE_ADS_CLIENT_ID") or None,
        google_ads_client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET") or None,
        google_ads_refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN") or None,
        google_ads_customer_id=os.getenv("GOOGLE_ADS_CUSTOMER_ID") or None,
        google_ads_login_customer_id=os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or None,
        google_ads_creative_lookback_days=int(os.getenv("GOOGLE_ADS_CREATIVE_LOOKBACK_DAYS", "7")),
        creative_action_min_spend=float(os.getenv("CREATIVE_ACTION_MIN_SPEND", "50")),
        creative_action_min_roi=float(os.getenv("CREATIVE_ACTION_MIN_ROI", "1.0")),
        adjust_api_token=os.getenv("ADJUST_API_TOKEN") or None,
        adjust_dashboard_config_path=_optional_path(os.getenv("ADJUST_DASHBOARD_CONFIG_PATH")),
        feishu_bot_webhook=os.getenv("FEISHU_BOT_WEBHOOK") or None,
        feishu_market_webhook=os.getenv("FEISHU_MARKET_WEBHOOK") or None,
        feishu_boss_webhook=os.getenv("FEISHU_BOSS_WEBHOOK") or None,
        allow_boss_send=str(os.getenv("ALLOW_BOSS_SEND", "")).strip().lower() in {"1", "true", "yes", "on"},
        feishu_event_verification_token=os.getenv("FEISHU_EVENT_VERIFICATION_TOKEN") or None,
        feishu_event_encrypt_key=os.getenv("FEISHU_EVENT_ENCRYPT_KEY") or None,
        feishu_event_path=os.getenv("FEISHU_EVENT_PATH", "/feishu/events").strip() or "/feishu/events",
        feishu_detail_trigger_keywords=_list_from_env(
            os.getenv("FEISHU_DETAIL_TRIGGER_KEYWORDS", "详细,详细版,周报详细版,详版")
        ),
        feishu_detail_allowed_chat_ids=_list_from_env(os.getenv("FEISHU_DETAIL_ALLOWED_CHAT_IDS")),
        company_overview_url=os.getenv("COMPANY_OVERVIEW_URL") or None,
        company_overview_markdown=_optional_path(os.getenv("COMPANY_OVERVIEW_MARKDOWN")),
        ads_performance_csv=_optional_path(os.getenv("ADS_PERFORMANCE_CSV")),
        creative_library_csv=_optional_path(os.getenv("CREATIVE_LIBRARY_CSV")),
        adjust_revenue_csv=_optional_path(os.getenv("ADJUST_REVENUE_CSV")),
        geo_performance_csv=_optional_path(os.getenv("GEO_PERFORMANCE_CSV")),
        action_tracker_csv=_optional_path(os.getenv("ACTION_TRACKER_CSV")),
        meeting_reports_csv=_optional_path(os.getenv("MEETING_REPORTS_CSV")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
        default_task_owner=os.getenv("DEFAULT_TASK_OWNER", "TBD").strip(),
        default_task_due_days=int(os.getenv("DEFAULT_TASK_DUE_DAYS", "7")),
        default_game_name=os.getenv("DEFAULT_GAME_NAME", "P04 Witch").strip(),
        task_owner_rules=_owner_rules_from_env(os.getenv("TASK_OWNER_RULES_JSON")),
    )
