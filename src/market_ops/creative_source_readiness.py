from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.clients.tecdo_report import TecDoReportCreativeClient
from market_ops.config import Settings


@dataclass(slots=True)
class ProviderReadiness:
    provider: str
    client_code_present: bool
    dependency_ready: bool
    env_ready: bool
    can_run_now: bool
    missing_env: list[str]
    requested_fields: list[str]
    output_fields: list[str]
    gaps: list[str]
    notes: list[str]
    probe_status: str = "not_run"
    probe_message: str = ""
    probe_http_status: int = 0
    probe_code: str = ""
    probe_accounts: list[dict[str, Any]] | None = None
    probe_has_rows: bool | None = None
    probe_rows: int = 0


class CreativeSourceReadinessBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> dict[str, Path]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.output_dir
        active_output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        active_output_dir.mkdir(parents=True, exist_ok=True)

        summary_path = active_output_dir / f"creative_source_readiness_{suffix}.md"
        json_path = active_output_dir / f"creative_source_readiness_{suffix}.json"

        meta = self._meta_readiness()
        tecdo = self._tecdo_readiness(report_date)
        google = self._google_readiness()
        payload = self._build_payload(report_date=report_date, meta=meta, tecdo=tecdo, google=google)

        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_path.write_text(self._render_markdown(payload), encoding="utf-8")
        return {"summary": summary_path, "json": json_path}

    def _meta_readiness(self) -> ProviderReadiness:
        client_path = Path("src/market_ops/clients/meta_ads.py")
        client_code_present = client_path.exists()
        dependency_ready = self._import_ready("requests")
        missing_env: list[str] = []
        if not self._settings.meta_access_token:
            missing_env.append("META_ACCESS_TOKEN")
        if not self._settings.meta_ad_account_id:
            missing_env.append("META_AD_ACCOUNT_ID")
        env_ready = not missing_env
        return ProviderReadiness(
            provider="Facebook",
            client_code_present=client_code_present,
            dependency_ready=dependency_ready,
            env_ready=env_ready,
            can_run_now=client_code_present and dependency_ready and env_ready,
            missing_env=missing_env,
            requested_fields=[
                "creative.id",
                "creative.name",
                "ad_id",
                "ad_name",
                "campaign_name",
                "adset_name",
                "spend",
                "clicks",
                "impressions",
                "actions",
                "action_values",
                "purchase_roas",
            ],
            output_fields=[
                "asset_id",
                "creative_name",
                "creative_type",
                "video_path",
                "game",
                "country",
                "channel",
                "campaign",
                "campaign_id",
                "adgroup",
                "adgroup_id",
                "ad_id",
                "ad_name",
                "source_name",
                "source_id",
                "ctr",
                "cvr",
                "roas",
                "spend",
                "status",
                "hook_type",
                "duration",
                "installs",
                "conversions",
                "revenue_value",
            ],
            gaps=[
                "当前 Facebook 素材输出里的国家仍统一为 All。",
                "Facebook 素材源还没有回填 Adjust 收入后的完整替换链路。",
            ],
            notes=[
                "代码链路已存在，补齐凭证后可切换到 Facebook 官方素材接口。",
                "当前环境还没有启用 Facebook 官方素材接口。",
            ],
        )

    def _tecdo_readiness(self, report_date: date) -> ProviderReadiness:
        client_path = Path("src/market_ops/clients/tecdo_report.py")
        client_code_present = client_path.exists()
        dependency_ready = self._import_ready("requests")
        missing_env: list[str] = []
        if not self._settings.tecdo_app_secret:
            missing_env.append("TECDO_APP_SECRET")
        if not self._settings.tecdo_effective_media_accounts:
            missing_env.append("TECDO_MEDIA_ACCOUNTS_JSON or TECDO_MEDIA_ACCOUNT_IDS")
        env_ready = not missing_env
        gaps = [
            "TecDo report-query 当前只到广告层，不是真正的素材 ID / 素材名称层。",
            "TecDo 当前维度里还没有国家字段。",
            "TecDo 当前指标里还没有 ROAS / revenue_value。",
        ]
        notes = [
            "TecDo 当前更适合做 adId / adName 代理素材分析。",
            "它适合广告层代理分析，不适合真正的素材 ID 归因。",
        ]
        probe_status = "not_run"
        probe_message = ""
        probe_http_status = 0
        probe_code = ""
        probe_accounts = self._tecdo_probe_accounts()
        probe_has_rows: bool | None = None
        probe_rows = 0
        can_run_now = client_code_present and dependency_ready and env_ready

        if can_run_now and probe_accounts:
            client = TecDoReportCreativeClient(
                app_secret=self._settings.tecdo_app_secret or "",
                base_url=self._settings.tecdo_base_url,
                media_accounts=probe_accounts,
                default_game_name=self._settings.default_game_name,
            )
            try:
                result = client.probe_access(
                    media_accounts=probe_accounts,
                    start_date=report_date,
                    end_date=report_date,
                )
                probe_http_status = int(result.get("http_status") or 0)
                probe_code = str(result.get("code") or "")
                probe_message = str(result.get("message") or "")
                probe_rows = int(result.get("rows") or 0)
                probe_has_rows = probe_rows > 0
                if result.get("ok"):
                    probe_status = "ok"
                    if not probe_has_rows:
                        probe_status = "sync_pending"
                        gaps.insert(0, "TecDo 实时探针已授权可调用，但报表侧仍在等待服务商后台完成同步。")
                        notes.insert(0, "当前 TecDo 凭证有效，接口方向也正确；现在卡在服务商后台同步，不是代码或权限报错。")
                else:
                    probe_status = "failed"
                    can_run_now = False
                    if probe_message:
                        gaps.insert(0, f"TecDo 实时探针失败：{probe_message}")
            except Exception as exc:
                probe_status = "exception"
                probe_message = str(exc)
                can_run_now = False
                gaps.insert(0, f"TecDo 实时探针异常：{exc}")
        elif can_run_now and not probe_accounts:
            can_run_now = False
            gaps.insert(0, "TecDo 实时探针当前没有可测试的账户。")

        return ProviderReadiness(
            provider="TecDo",
            client_code_present=client_code_present,
            dependency_ready=dependency_ready,
            env_ready=env_ready,
            can_run_now=can_run_now,
            missing_env=missing_env,
            requested_fields=[
                "campaignId",
                "adsetId",
                "adId",
                "campaignName",
                "adsetName",
                "adName",
                "spend",
                "impressions",
                "clicks",
                "installs",
            ],
            output_fields=[
                "asset_id(proxy=adId)",
                "creative_name(proxy=adName)",
                "game",
                "country=All",
                "channel",
                "campaign",
                "campaign_id",
                "adgroup",
                "adgroup_id",
                "ad_id",
                "ad_name",
                "source_name",
                "source_id",
                "ctr",
                "cvr",
                "spend",
                "installs",
            ],
            gaps=gaps,
            notes=notes,
            probe_status=probe_status,
            probe_message=probe_message,
            probe_http_status=probe_http_status,
            probe_code=probe_code,
            probe_accounts=probe_accounts,
            probe_has_rows=probe_has_rows,
            probe_rows=probe_rows,
        )

    def _google_readiness(self) -> ProviderReadiness:
        client_path = Path("src/market_ops/clients/google_ads.py")
        client_code_present = client_path.exists()
        dependency_ready = self._import_ready("google.ads.googleads.client")
        missing_env: list[str] = []
        required_env = [
            ("GOOGLE_ADS_DEVELOPER_TOKEN", self._settings.google_ads_developer_token),
            ("GOOGLE_ADS_CLIENT_ID", self._settings.google_ads_client_id),
            ("GOOGLE_ADS_CLIENT_SECRET", self._settings.google_ads_client_secret),
            ("GOOGLE_ADS_REFRESH_TOKEN", self._settings.google_ads_refresh_token),
            ("GOOGLE_ADS_CUSTOMER_ID", self._settings.google_ads_customer_id),
        ]
        for env_name, value in required_env:
            if not value:
                missing_env.append(env_name)
        env_ready = not missing_env
        return ProviderReadiness(
            provider="Google Ads",
            client_code_present=client_code_present,
            dependency_ready=dependency_ready,
            env_ready=env_ready,
            can_run_now=client_code_present and dependency_ready and env_ready,
            missing_env=missing_env,
            requested_fields=[
                "asset.id",
                "asset.name",
                "asset.type",
                "campaign.name",
                "ad_group.name",
                "asset_group.name",
                "metrics.cost_micros",
                "metrics.impressions",
                "metrics.clicks",
                "metrics.conversions",
                "metrics.conversions_value",
            ],
            output_fields=[
                "asset_id",
                "creative_name",
                "creative_type",
                "video_path",
                "game",
                "country",
                "channel",
                "campaign",
                "campaign_id",
                "adgroup",
                "adgroup_id",
                "ad_id",
                "ad_name",
                "source_name",
                "source_id",
                "ctr",
                "cvr",
                "roas",
                "spend",
                "status",
                "hook_type",
                "duration",
                "installs",
                "conversions",
                "revenue_value",
            ],
            gaps=[
                "当前 Google Ads 查询里还没有请求 ad_id 和 ad_name。",
                "当前 Google 素材输出里的国家仍统一为 All。",
                "Google 素材修复链路已接入，但当前环境还不能直接跑 Google 官方素材接口。",
            ],
            notes=[
                "代码链路已存在，补齐凭证后可切换到 Google 官方素材接口。",
                "当前环境还没有启用 Google 官方素材接口。",
                "有了凭证后，可用 source_id / adgroup_id / campaign_id 去修复 Adjust 里的通用占位素材值。",
            ],
        )

    def _tecdo_probe_accounts(self) -> list[dict[str, Any]]:
        if self._settings.tecdo_effective_media_accounts and self._settings.tecdo_app_secret:
            try:
                client = TecDoReportCreativeClient(
                    app_secret=self._settings.tecdo_app_secret or "",
                    base_url=self._settings.tecdo_base_url,
                    media_accounts=self._settings.tecdo_effective_media_accounts,
                    default_game_name=self._settings.default_game_name,
                )
                resolved_accounts = client._resolved_media_accounts()
                if resolved_accounts:
                    return list(resolved_accounts[:10])
            except Exception:
                pass
        if self._settings.tecdo_effective_media_accounts:
            return list(self._settings.tecdo_effective_media_accounts[:10])
        return []

    def _build_payload(self, report_date: date, meta: ProviderReadiness, tecdo: ProviderReadiness, google: ProviderReadiness) -> dict[str, Any]:
        blockers: list[str] = []
        tecdo_ready = tecdo.can_run_now and tecdo.probe_has_rows is True
        if not meta.can_run_now and not tecdo_ready:
            blockers.append("Facebook 官方素材接口当前不可运行。")
        if not tecdo.can_run_now:
            blockers.append("TecDo 代理素材源当前不可运行。")
        if not google.can_run_now and not tecdo_ready:
            blockers.append("Google 官方素材接口当前不可运行。")
        return {
            "report_date": report_date.isoformat(),
            "passed": True,
            "summary": {
                "meta_can_run_now": meta.can_run_now,
                "tecdo_can_run_now": tecdo.can_run_now,
                "google_can_run_now": google.can_run_now,
                "google_resolver_ready": True,
                "meta_missing_env": list(meta.missing_env),
                "tecdo_missing_env": list(tecdo.missing_env) or ([tecdo.probe_message] if tecdo.probe_message else []),
                "tecdo_probe_status": tecdo.probe_status,
                "tecdo_probe_message": tecdo.probe_message,
                "tecdo_probe_has_rows": tecdo.probe_has_rows,
                "tecdo_probe_rows": tecdo.probe_rows,
                "tecdo_is_formal_source": tecdo_ready,
                "tecdo_business_status": (
                    "已授权，等待服务商同步报表数据"
                    if tecdo.can_run_now and tecdo.probe_has_rows is False
                    else ("已作为当前代理素材主来源" if tecdo_ready else ("可用于代理素材分析" if tecdo.can_run_now else "当前不可用"))
                ),
                "google_missing_env": list(google.missing_env),
            },
            "blockers": blockers,
            "providers": {
                "meta": asdict(meta),
                "tecdo": asdict(tecdo),
                "google_ads": asdict(google),
            },
            "next_actions": [
                "如果 TecDo 状态是“已授权，等待服务商同步报表数据”，先等服务商完成 report/query 同步，再重新验证是否出数。",
                "如果要把 Facebook / Google 的代理广告层分析升级成原生 creative id 归因，再补官方接口凭证。",
                "如果要把 Google 占位素材升级成真正的素材标识，补齐 Google Ads 凭证。",
                "如果后续需要更细的 Google 广告 / 素材映射，再扩展 ad_id / ad_name 联表。",
            ],
        }

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        meta = payload["providers"]["meta"]
        tecdo = payload["providers"]["tecdo"]
        google = payload["providers"]["google_ads"]
        lines = [
            f"# 素材源准备度 | {payload['report_date']}",
            "",
            "## 结论",
            "",
            f"- Facebook 素材源：{'已具备运行条件' if meta['can_run_now'] else ('当前由 TecDo 代理素材源承接' if payload.get('summary', {}).get('tecdo_is_formal_source') else '当前不可用')}",
            f"- TecDo 素材源：{payload.get('summary', {}).get('tecdo_business_status', '当前不可用')}",
            f"- Google 素材源：{'已具备运行条件' if google['can_run_now'] else ('当前由 TecDo 代理素材源承接' if payload.get('summary', {}).get('tecdo_is_formal_source') else '当前不可用')}",
            f"- Google 素材修复链路：{'已接入' if payload.get('summary', {}).get('google_resolver_ready') else '未接入'}",
        ]
        for blocker in payload.get("blockers") or []:
            lines.append(f"- 阻塞：{blocker}")

        lines.extend(["", "## Facebook", ""])
        lines.extend(self._provider_lines(meta))
        lines.extend(["", "## TecDo", ""])
        lines.extend(self._provider_lines(tecdo))
        lines.extend(["", "## Google Ads", ""])
        lines.extend(self._provider_lines(google))

        lines.extend(["", "## 下一步", ""])
        for item in payload.get("next_actions") or []:
            lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _provider_lines(provider: dict[str, Any]) -> list[str]:
        lines = [
            f"- 代码链路：{'已接入' if provider['client_code_present'] else '未接入'}",
            f"- 依赖环境：{'可用' if provider['dependency_ready'] else '缺失'}",
            f"- 凭证状态：{'已齐' if provider['env_ready'] else '未齐'}",
            f"- 当前可运行：{'是' if provider['can_run_now'] else '否'}",
        ]
        missing_env = provider.get("missing_env") or []
        if missing_env:
            if provider.get("provider") in {"Facebook", "Google Ads"}:
                lines.append(f"- 官方接口增强项未补齐：{', '.join(missing_env)}")
            else:
                lines.append(f"- 缺少凭证：{', '.join(missing_env)}")
        if provider.get("probe_status") and provider.get("probe_status") != "not_run":
            probe_line = f"- 实时探针：{provider.get('probe_status')} | http={provider.get('probe_http_status', 0)}"
            if provider.get("probe_code"):
                probe_line += f" | code={provider.get('probe_code')}"
            if provider.get("probe_has_rows") is not None:
                probe_line += f" | rows={provider.get('probe_rows', 0)}"
            lines.append(probe_line)
        if provider.get("probe_message"):
            lines.append(f"- 探针返回：{provider.get('probe_message')}")
        probe_accounts = provider.get("probe_accounts") or []
        if probe_accounts:
            lines.append(f"- 探针账户：{json.dumps(probe_accounts, ensure_ascii=False)}")
        requested_fields = provider.get("requested_fields") or []
        if requested_fields:
            lines.append(f"- 已请求字段：{', '.join(requested_fields)}")
        output_fields = provider.get("output_fields") or []
        if output_fields:
            lines.append(f"- 当前标准化输出字段：{', '.join(output_fields)}")
        for item in provider.get("gaps") or []:
            lines.append(f"- 缺口：{item}")
        for item in provider.get("notes") or []:
            lines.append(f"- 说明：{item}")
        return lines

    @staticmethod
    def _import_ready(module_name: str) -> bool:
        try:
            __import__(module_name)
            return True
        except Exception:
            return False
