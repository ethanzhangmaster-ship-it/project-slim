from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.clients.tecdo_report import TecDoReportCreativeClient
from market_ops.config import Settings


@dataclass(slots=True)
class TecDoProbeResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class TecDoProbeBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> TecDoProbeResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        markdown_path = output_dir / f"tecdo_probe_{suffix}.md"
        json_path = output_dir / f"tecdo_probe_{suffix}.json"

        payload = self._build_payload(report_date)
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return TecDoProbeResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload.get("passed")))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        accounts = list(self._settings.tecdo_effective_media_accounts)
        if not self._settings.tecdo_app_secret:
            return {
                "report_date": report_date.isoformat(),
                "passed": False,
                "summary": "missing_app_secret",
                "items": [],
                "issues": ["缺少 TECDO_APP_SECRET"],
            }
        if not accounts:
            return {
                "report_date": report_date.isoformat(),
                "passed": False,
                "summary": "missing_accounts",
                "items": [],
                "issues": ["缺少 TECDO_MEDIA_ACCOUNTS_JSON 或 TECDO_MEDIA_ACCOUNT_IDS"],
            }

        client = TecDoReportCreativeClient(
            app_secret=self._settings.tecdo_app_secret,
            base_url=self._settings.tecdo_base_url,
            media_accounts=accounts,
            default_game_name=self._settings.default_game_name,
        )

        resolved_accounts = client._resolved_media_accounts()
        items: list[dict[str, Any]] = []
        passed = False
        has_rows = False
        global_messages: list[str] = []
        for item in resolved_accounts:
            probe = client.probe_access(
                media_accounts=[item],
                start_date=report_date,
                end_date=report_date,
            )
            row = {
                "mediaPlatform": int(item.get("mediaPlatform") or 0),
                "mediaAccountId": str(item.get("mediaAccountId") or ""),
                "game": str(item.get("game") or ""),
                "channel": str(item.get("channel") or ""),
                "ok": bool(probe.get("ok")),
                "http_status": int(probe.get("http_status") or 0),
                "code": str(probe.get("code") or ""),
                "message": str(probe.get("message") or ""),
                "rows": int(probe.get("rows") or 0),
                "pages": int(probe.get("pages") or 0),
            }
            if item.get("mediaAccountName"):
                row["mediaAccountName"] = str(item.get("mediaAccountName") or "")
            items.append(row)
            if row["ok"]:
                passed = True
            if row["rows"] > 0:
                has_rows = True
            if row["message"] and row["message"] not in global_messages:
                global_messages.append(row["message"])

        if passed:
            summary = "success_with_rows" if has_rows else "authorized_but_empty"
            issues: list[str] = [] if has_rows else ["TecDo 账号已授权，但当前探针日期下没有返回任何报表行"]
        else:
            summary = "all_failed"
            issues = global_messages or ["全部账户探针失败"]

        return {
            "report_date": report_date.isoformat(),
            "passed": passed,
            "summary": summary,
            "has_rows": has_rows,
            "items": items,
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

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# TecDo Probe | {payload.get('report_date', '')}",
            "",
            f"- 结果：{'通过' if payload.get('passed') else '失败'}",
            f"- 摘要：{payload.get('summary', '')}",
            f"- 是否有报表行：{'是' if payload.get('has_rows') else '否'}",
        ]
        issues = payload.get("issues") or []
        for issue in issues:
            lines.append(f"- 问题：{issue}")
        lines.extend(["", "## 账户结果", ""])
        items = payload.get("items") or []
        if not items:
            lines.append("- 无可用探针账户")
            lines.append("")
            return "\n".join(lines)
        for item in items:
            lines.append(
                "- "
                f"{self._platform_name(int(item.get('mediaPlatform') or 0))} / "
                f"{item.get('mediaAccountId', '')} | "
                f"name={item.get('mediaAccountName', '-') or '-'} | "
                f"{'OK' if item.get('ok') else 'FAIL'} | "
                f"http={item.get('http_status', 0)} | "
                f"code={item.get('code', '') or '-'} | "
                f"rows={item.get('rows', 0)} | "
                f"message={item.get('message', '') or '-'}"
            )
        lines.append("")
        return "\n".join(lines)
