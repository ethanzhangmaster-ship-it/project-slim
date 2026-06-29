from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from market_ops.clients.tecdo_report import TecDoReportCreativeClient
from market_ops.config import Settings


@dataclass(slots=True)
class TecDoAccountReconciliationResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class TecDoAccountReconciliationBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date, *, lookback_days: int = 180) -> TecDoAccountReconciliationResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        markdown_path = output_dir / f"tecdo_account_reconciliation_{suffix}.md"
        json_path = output_dir / f"tecdo_account_reconciliation_{suffix}.json"

        payload = self._build_payload(report_date=report_date, lookback_days=lookback_days)
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return TecDoAccountReconciliationResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload.get("passed")),
        )

    def _build_payload(self, *, report_date: date, lookback_days: int) -> dict:
        accounts = list(self._settings.tecdo_effective_media_accounts)
        if not self._settings.tecdo_app_secret:
            return {
                "report_date": report_date.isoformat(),
                "lookback_days": lookback_days,
                "passed": False,
                "summary": "missing_app_secret",
                "accounts": [],
                "issues": ["缺少 TECDO_APP_SECRET"],
            }
        if not accounts:
            return {
                "report_date": report_date.isoformat(),
                "lookback_days": lookback_days,
                "passed": False,
                "summary": "missing_accounts",
                "accounts": [],
                "issues": ["缺少 TECDO_MEDIA_ACCOUNTS_JSON 或 TECDO_MEDIA_ACCOUNT_IDS"],
            }

        client = TecDoReportCreativeClient(
            app_secret=self._settings.tecdo_app_secret,
            base_url=self._settings.tecdo_base_url,
            media_accounts=accounts,
            default_game_name=self._settings.default_game_name,
        )
        inventory = client.fetch_account_inventory()
        report_rows = client.summarize_account_report_rows(report_end=report_date, lookback_days=lookback_days)
        report_map = {
            (int(item.get("mediaPlatform") or 0), str(item.get("mediaAccountId") or "")): item
            for item in report_rows
        }

        accounts_payload: list[dict] = []
        for item in inventory:
            key = (int(item.get("mediaPlatform") or 0), str(item.get("mediaAccountId") or ""))
            report_item = report_map.get(key, {})
            accounts_payload.append(
                {
                    "mediaPlatform": key[0],
                    "mediaAccountId": key[1],
                    "mediaAccountName": str(item.get("mediaAccountName") or ""),
                    "game": str(item.get("game") or ""),
                    "channel": str(item.get("channel") or ""),
                    "has_report_rows": bool(report_item.get("has_report_rows")),
                    "total_rows": int(report_item.get("total_rows") or 0),
                    "windows": list(report_item.get("windows") or []),
                }
            )

        any_rows = any(item["has_report_rows"] for item in accounts_payload)
        summary = "has_report_rows" if any_rows else "authorized_but_no_report_rows"
        issues = [] if any_rows else ["所有已授权 TecDo 账号在近180天窗口内都没有返回报表行"]
        return {
            "report_date": report_date.isoformat(),
            "lookback_days": lookback_days,
            "passed": True,
            "summary": summary,
            "accounts": accounts_payload,
            "issues": issues,
        }

    @staticmethod
    def _platform_name(value: int) -> str:
        return {
            1: "Facebook",
            2: "Google Ads",
            4: "Snapchat",
            5: "TikTok",
        }.get(value, f"Media-{value}")

    def _render_markdown(self, payload: dict) -> str:
        lines = [
            f"# TecDo 账号核对表 | {payload.get('report_date', '')}",
            "",
            f"- 近检窗口：最近 {payload.get('lookback_days', 0)} 天",
            f"- 摘要：{payload.get('summary', '')}",
            f"- 状态：{'通过' if payload.get('passed') else '失败'}",
        ]
        for issue in payload.get("issues") or []:
            lines.append(f"- 问题：{issue}")
        lines.extend(["", "## 账号列表", ""])

        accounts = payload.get("accounts") or []
        if not accounts:
            lines.append("- 无可核对账号")
            lines.append("")
            return "\n".join(lines)

        for item in accounts:
            lines.append(
                "- "
                f"{self._platform_name(int(item.get('mediaPlatform') or 0))} / "
                f"{item.get('mediaAccountId', '')} / "
                f"{item.get('mediaAccountName', '') or '-'} / "
                f"项目={item.get('game', '') or '-'} / "
                f"渠道={item.get('channel', '') or '-'} / "
                f"近180天有报表行={'是' if item.get('has_report_rows') else '否'} / "
                f"总行数={item.get('total_rows', 0)}"
            )
        lines.append("")
        return "\n".join(lines)
