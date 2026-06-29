from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class TecDoSyncChecklistResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class TecDoSyncChecklistBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> TecDoSyncChecklistResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"tecdo_sync_checklist_{suffix}.md"
        json_path = output_dir / f"tecdo_sync_checklist_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        preview_paths = payload.get("preview_paths") or {}
        if preview_paths:
            write_preview_overview(
                report_date,
                output_dir / f"weekly_preview_overview_{suffix}.md",
                summary_markdown=Path(preview_paths["summary_markdown"]),
                summary_json=Path(preview_paths["summary_json"]),
                index_markdown=Path(preview_paths["index_markdown"]),
                boss_markdown=Path(preview_paths["boss_markdown"]),
                market_markdown=Path(preview_paths["market_markdown"]),
                market_detail_markdown=Path(preview_paths["market_detail_markdown"]),
                recovery_markdown=Path(preview_paths["recovery_markdown"]),
                self_check_markdown=output_dir / f"self_check_{suffix}.md",
                report_audit_markdown=output_dir / f"report_audit_{suffix}.md",
                pre_send_summary_markdown=output_dir / f"pre_send_summary_{suffix}.md",
                health_check_markdown=output_dir / f"weekly_health_check_{suffix}.md",
                creative_source_readiness_markdown=output_dir / f"creative_source_readiness_{suffix}.md",
                creative_attribution_audit_markdown=output_dir / f"creative_attribution_audit_{suffix}.md",
                google_creative_repair_audit_markdown=output_dir / f"google_creative_repair_audit_{suffix}.md",
                tecdo_probe_markdown=(output_dir / f"tecdo_probe_{suffix}.md")
                if (output_dir / f"tecdo_probe_{suffix}.md").exists()
                else None,
                tecdo_account_reconciliation_markdown=(output_dir / f"tecdo_account_reconciliation_{suffix}.md")
                if (output_dir / f"tecdo_account_reconciliation_{suffix}.md").exists()
                else None,
                tecdo_sync_checklist_markdown=markdown_path,
                closure_status_markdown=(output_dir / f"closure_status_{suffix}.md")
                if (output_dir / f"closure_status_{suffix}.md").exists()
                else None,
                project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md")
                if (output_dir / f"project_detail_coverage_{suffix}.md").exists()
                else None,
                p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{suffix}.md")
                if (output_dir / f"p04_source_checklist_{suffix}.md").exists()
                else None,
                detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{suffix}.md")
                if (output_dir / f"detail_reply_checklist_{suffix}.md").exists()
                else None,
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md")
                if (output_dir / f"management_action_list_{suffix}.md").exists()
                else None,
            )
        return TecDoSyncChecklistResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        readiness = self._load_json(output_dir / f"creative_source_readiness_{suffix}.json")
        probe = self._load_json(output_dir / f"tecdo_probe_{suffix}.json")
        reconciliation = self._load_json(output_dir / f"tecdo_account_reconciliation_{suffix}.json")
        preview_paths = self._load_preview_paths(report_date)

        summary = readiness.get("summary") or {}
        tecdo_provider = ((readiness.get("providers") or {}).get("tecdo")) or {}
        probe_status = str(summary.get("tecdo_probe_status") or tecdo_provider.get("probe_status") or "")
        has_rows = summary.get("tecdo_probe_has_rows")
        rows = int(summary.get("tecdo_probe_rows") or tecdo_provider.get("probe_rows") or 0)
        account_count = len((probe.get("items") or [])) or len((reconciliation.get("accounts") or []))
        business_status = str(summary.get("tecdo_business_status") or "")
        if passed := bool(has_rows):
            root_cause = "TecDo 已返回报表行，当前可作为代理素材分析输入。"
        else:
            root_cause = "TecDo 已确认 report/query 接口可调用，当前空报表是因为服务商后台数据同步尚未完成。"

        checklist = [
            {
                "step": "确认 TecDo 当前不是权限失败",
                "status": "done",
                "needed": "确认接口可调用，状态不是鉴权失败",
                "current": f"probe_status={probe_status or 'unknown'}",
                "done_when": "系统状态明确显示为 ok 或 sync_pending，而不是权限失败",
            },
            {
                "step": "等待 TecDo 完成 report/query 报表同步",
                "status": "done" if passed else "pending",
                "needed": "服务商完成后台报表同步",
                "current": f"当前 probe rows={rows}；账户数={account_count}",
                "done_when": "重新跑 tecdo-probe 后，rows > 0",
            },
            {
                "step": "同步完成后复测 TecDo Probe",
                "status": "done" if passed else "pending",
                "needed": "运行 tecdo-probe",
                "current": "python -m market_ops.cli tecdo-probe --report-date latest",
                "done_when": "tecdo_probe_YYYYMMDD.json 里 has_rows=true",
            },
            {
                "step": "同步完成后复测 TecDo 账户核对",
                "status": "done" if passed else "pending",
                "needed": "运行 tecdo-account-reconciliation",
                "current": "python -m market_ops.cli tecdo-account-reconciliation --report-date latest --lookback-days 180",
                "done_when": "至少一个账户 has_report_rows=true",
            },
            {
                "step": "同步完成后再决定是否接入周报素材链路",
                "status": "done" if passed else "pending",
                "needed": "只有报表真正出数时，才把 TecDo 当成可用素材源",
                "current": "当前已可作为代理素材源" if passed else "当前仍处于等待同步，不能当成可用素材数据源",
                "done_when": "creative_source_readiness 显示可用于代理素材分析",
            },
        ]

        return {
            "report_date": report_date.isoformat(),
            "passed": passed,
            "summary": {
                "business_status": business_status,
                "probe_status": probe_status,
                "probe_has_rows": has_rows,
                "probe_rows": rows,
                "account_count": account_count,
                "root_cause": root_cause,
                "retest_commands": [
                    "python -m market_ops.cli tecdo-probe --report-date latest",
                    "python -m market_ops.cli tecdo-account-reconciliation --report-date latest --lookback-days 180",
                ],
            },
            "checklist": checklist,
            "preview_paths": preview_paths,
        }

    def _load_preview_paths(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        path = self._settings.active_output_dir / f"self_check_{suffix}.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        preview_paths = payload.get("preview_paths")
        return preview_paths if isinstance(preview_paths, dict) else {}

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        lines = [
            f"# TecDo 同步等待清单 | {payload['report_date']}",
            "",
            f"- 当前业务状态：{summary.get('business_status', '') or '未识别'}",
            f"- 当前 probe_status：{summary.get('probe_status', '') or 'unknown'}",
            f"- 当前是否已有报表行：{'是' if summary.get('probe_has_rows') else '否'}",
            f"- 当前报表行数：{summary.get('probe_rows', 0)}",
            f"- 当前已核对账户数：{summary.get('account_count', 0)}",
            f"- 根因：{summary.get('root_cause', '')}",
            "",
            "## 复测命令",
            "",
        ]
        for item in summary.get("retest_commands") or []:
            lines.append(f"- `{item}`")
        lines.extend(["", "## 执行清单", ""])
        for item in payload.get("checklist") or []:
            lines.extend(
                [
                    f"### {item.get('step', '')}",
                    f"- 状态：{item.get('status', '')}",
                    f"- 需要：{item.get('needed', '')}",
                    f"- 当前：{item.get('current', '')}",
                    f"- 完成标准：{item.get('done_when', '')}",
                    "",
                ]
            )
        return "\n".join(lines)
