from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_ops.clients.feishu_sheets import FeishuSheetsClient
from market_ops.config import Settings
from market_ops.preview_overview import write_preview_overview
from market_ops.self_check import SelfCheckResult, run_self_check


class ReportAuditBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sheet_client: FeishuSheetsClient | None = None
        if settings.feishu_app_id and settings.feishu_app_secret:
            self._sheet_client = FeishuSheetsClient(settings.feishu_app_id, settings.feishu_app_secret)

    def build(
        self,
        report_date: date,
        meeting_name: str,
        *,
        self_check_result: SelfCheckResult | None = None,
    ) -> dict[str, Path]:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.audit_payload(
            report_date=report_date,
            meeting_name=meeting_name,
            self_check_result=self_check_result,
        )

        markdown_path = output_dir / f"report_audit_{suffix}.md"
        json_path = output_dir / f"report_audit_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self_check = payload.get("self_check") or {}
        preview_paths = self_check.get("preview_paths") or {}
        if preview_paths:
            pre_send_summary_path = output_dir / f"pre_send_summary_{suffix}.md"
            creative_source_readiness_path = output_dir / f"creative_source_readiness_{suffix}.md"
            creative_attribution_audit_path = output_dir / f"creative_attribution_audit_{suffix}.md"
            google_creative_repair_audit_path = output_dir / f"google_creative_repair_audit_{suffix}.md"
            google_revenue_attribution_audit_path = output_dir / f"google_revenue_attribution_audit_{suffix}.md"
            send_payload_consistency_path = output_dir / f"send_payload_consistency_{suffix}.md"
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
                self_check_markdown=Path(self_check["markdown_path"]),
                report_audit_markdown=markdown_path,
                pre_send_summary_markdown=pre_send_summary_path if pre_send_summary_path.exists() else None,
                health_check_markdown=(output_dir / f"weekly_health_check_{suffix}.md") if (output_dir / f"weekly_health_check_{suffix}.md").exists() else None,
                creative_source_readiness_markdown=creative_source_readiness_path if creative_source_readiness_path.exists() else None,
                data_quality_audit_markdown=(output_dir / f"data_quality_audit_{suffix}.md") if (output_dir / f"data_quality_audit_{suffix}.md").exists() else None,
                creative_attribution_audit_markdown=creative_attribution_audit_path if creative_attribution_audit_path.exists() else None,
                google_creative_repair_audit_markdown=google_creative_repair_audit_path if google_creative_repair_audit_path.exists() else None,
                google_revenue_attribution_audit_markdown=google_revenue_attribution_audit_path if google_revenue_attribution_audit_path.exists() else None,
                send_payload_consistency_markdown=send_payload_consistency_path if send_payload_consistency_path.exists() else None,
                closure_status_markdown=(output_dir / f"closure_status_{suffix}.md") if (output_dir / f"closure_status_{suffix}.md").exists() else None,
                project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md") if (output_dir / f"project_detail_coverage_{suffix}.md").exists() else None,
                p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{suffix}.md") if (output_dir / f"p04_source_checklist_{suffix}.md").exists() else None,
                detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{suffix}.md") if (output_dir / f"detail_reply_checklist_{suffix}.md").exists() else None,
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md") if (output_dir / f"management_action_list_{suffix}.md").exists() else None,
            )
        return {
            "summary": markdown_path,
            "json": json_path,
        }

    def audit_payload(
        self,
        report_date: date,
        meeting_name: str,
        *,
        self_check_result: SelfCheckResult | None = None,
    ) -> dict[str, Any]:
        self_check = self_check_result or run_self_check(
            report_date=report_date,
            meeting_name=meeting_name,
            output_dir=self._settings.active_output_dir,
        )
        payload = {
            "report_date": report_date.isoformat(),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "report_window": f"{(report_date.fromordinal(report_date.toordinal() - 6)).isoformat()} ~ {report_date.isoformat()}",
            "meeting_name": meeting_name,
            "self_check": self._self_check_payload(self_check),
            "local_action_tracker": self._audit_local_action_tracker(report_date),
            "local_meeting_reports": self._audit_local_meeting_reports(report_date),
            "sheet_action_tracker": self._audit_sheet_action_tracker(report_date),
            "sheet_meeting_reports": self._audit_sheet_meeting_reports(report_date),
            "sheet_action_tracker_configured": bool(self._settings.feishu_action_tracker_url),
            "sheet_meeting_reports_configured": bool(self._settings.feishu_meeting_reports_url),
        }
        payload["passed"] = self._is_payload_passed(payload)
        return payload

    @staticmethod
    def _is_payload_passed(payload: dict[str, Any]) -> bool:
        if not payload.get("self_check", {}).get("passed"):
            return False
        for section_name in (
            "local_action_tracker",
            "local_meeting_reports",
            "sheet_action_tracker",
            "sheet_meeting_reports",
        ):
            section = payload.get(section_name) or {}
            if not section.get("available"):
                if section_name == "sheet_action_tracker" and payload.get("sheet_action_tracker_configured"):
                    return False
                if section_name == "sheet_meeting_reports" and payload.get("sheet_meeting_reports_configured"):
                    return False
                continue
            if int(section.get("duplicate_count", 0) or 0) > 0:
                return False
            if int(section.get("old_path_count", 0) or 0) > 0:
                return False
            if section_name.endswith("meeting_reports") and int(section.get("current_report_date_count", 0) or 0) <= 0:
                return False
        return True

    @staticmethod
    def _self_check_payload(result: SelfCheckResult) -> dict[str, Any]:
        return {
            "passed": result.passed,
            "issue_count": len(result.issues),
            "warning_count": len(result.warnings),
            "markdown_path": str(result.markdown_path),
            "json_path": str(result.json_path),
            "preview_paths": {
                "overview_markdown": str(result.preview_paths.overview_markdown),
                "summary_markdown": str(result.preview_paths.summary_markdown),
                "summary_json": str(result.preview_paths.summary_json),
                "boss_markdown": str(result.preview_paths.boss_markdown),
                "boss_json": str(result.preview_paths.boss_json),
                "market_markdown": str(result.preview_paths.market_markdown),
                "market_json": str(result.preview_paths.market_json),
                "market_detail_markdown": str(result.preview_paths.market_detail_markdown),
                "market_detail_json": str(result.preview_paths.market_detail_json),
                "recovery_markdown": str(result.preview_paths.recovery_markdown),
                "recovery_json": str(result.preview_paths.recovery_json),
                "index_markdown": str(result.preview_paths.index_markdown),
            },
            "issues": [
                {
                    "code": item.code,
                    "source": item.source,
                    "message": item.message,
                    "actual": item.actual,
                    "expected": item.expected,
                }
                for item in result.issues
            ],
            "warnings": list(result.warnings),
        }

    def _audit_local_action_tracker(self, report_date: date) -> dict[str, Any]:
        path = self._settings.action_tracker_csv
        if not path or not path.exists():
            return {"available": False, "reason": "missing local action_tracker.csv"}
        rows = self._read_csv_dicts(path)
        duplicates = self._find_duplicates(rows, self._action_tracker_identity)
        prefix = report_date.strftime("%Y%m%d")
        current_tasks = [str(row.get("Task ID", "")).strip() for row in rows if str(row.get("Task ID", "")).strip().startswith(prefix)]
        return {
            "available": True,
            "path": str(path),
            "row_count": len(rows),
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "task_ids": [str(row.get("Task ID", "")).strip() for row in rows],
            "current_report_date": report_date.isoformat(),
            "current_report_task_count": len(current_tasks),
            "current_report_task_ids": current_tasks,
        }

    def _audit_local_meeting_reports(self, report_date: date) -> dict[str, Any]:
        path = self._settings.meeting_reports_csv
        if not path or not path.exists():
            return {"available": False, "reason": "missing local meeting_reports.csv"}
        rows = self._read_csv_dicts(path)
        duplicates = self._find_duplicates(rows, self._meeting_report_identity)
        old_paths = self._old_meeting_report_paths(rows)
        current_rows = [row for row in rows if str(row.get("Report Date", "")).strip() == report_date.isoformat()]
        return {
            "available": True,
            "path": str(path),
            "row_count": len(rows),
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "old_path_count": len(old_paths),
            "old_paths": old_paths,
            "current_report_date": report_date.isoformat(),
            "current_report_date_count": len(current_rows),
            "current_report_paths": [str(row.get("Report Path", "")).strip() for row in current_rows],
        }

    def _audit_sheet_action_tracker(self, report_date: date) -> dict[str, Any]:
        if not self._sheet_client or not self._settings.feishu_action_tracker_url:
            return {"available": False, "reason": "missing feishu action tracker sheet config"}
        try:
            rows = self._read_sheet_rows(
                url=self._settings.feishu_action_tracker_url,
                sheet_title=self._settings.feishu_action_tracker_sheet_title or "Action Tracker",
                width="J",
            )
        except Exception as exc:
            return {
                "available": False,
                "reason": self._format_sheet_unavailable_reason(exc),
            }
        duplicates = self._find_duplicates(rows, self._action_tracker_identity)
        prefix = report_date.strftime("%Y%m%d")
        current_tasks = [str(row.get("Task ID", "")).strip() for row in rows if str(row.get("Task ID", "")).strip().startswith(prefix)]
        return {
            "available": True,
            "url": self._settings.feishu_action_tracker_url,
            "sheet_title": self._settings.feishu_action_tracker_sheet_title or "Action Tracker",
            "row_count": len(rows),
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "task_ids": [str(row.get("Task ID", "")).strip() for row in rows],
            "current_report_date": report_date.isoformat(),
            "current_report_task_count": len(current_tasks),
            "current_report_task_ids": current_tasks,
        }

    def _audit_sheet_meeting_reports(self, report_date: date) -> dict[str, Any]:
        if not self._sheet_client or not self._settings.feishu_meeting_reports_url:
            return {"available": False, "reason": "missing feishu meeting reports sheet config"}
        try:
            rows = self._read_sheet_rows(
                url=self._settings.feishu_meeting_reports_url,
                sheet_title=self._settings.feishu_meeting_reports_sheet_title or "Meeting Reports",
                width="F",
            )
        except Exception as exc:
            return {
                "available": False,
                "reason": self._format_sheet_unavailable_reason(exc),
            }
        duplicates = self._find_duplicates(rows, self._meeting_report_identity)
        old_paths = self._old_meeting_report_paths(rows)
        current_rows = [row for row in rows if str(row.get("Report Date", "")).strip() == report_date.isoformat()]
        return {
            "available": True,
            "url": self._settings.feishu_meeting_reports_url,
            "sheet_title": self._settings.feishu_meeting_reports_sheet_title or "Meeting Reports",
            "row_count": len(rows),
            "duplicate_count": len(duplicates),
            "duplicates": duplicates,
            "old_path_count": len(old_paths),
            "old_paths": old_paths,
            "current_report_date": report_date.isoformat(),
            "current_report_date_count": len(current_rows),
            "current_report_paths": [str(row.get("Report Path", "")).strip() for row in current_rows],
        }

    @staticmethod
    def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [row for row in reader if any(str(value).strip() for value in row.values())]

    def _read_sheet_rows(self, *, url: str, sheet_title: str, width: str) -> list[dict[str, Any]]:
        assert self._sheet_client is not None
        sheet_id = self._sheet_client.find_sheet_id_by_title(url, sheet_title)
        values = self._sheet_client.read_values(url, f"A1:{width}500", sheet_id=sheet_id)
        if not values:
            return []
        headers = [str(item) for item in values[0]]
        rows: list[dict[str, Any]] = []
        for row in values[1:]:
            if not any(str(cell).strip() for cell in row):
                continue
            padded = list(row) + [""] * (len(headers) - len(row))
            rows.append(dict(zip(headers, padded)))
        return rows

    @staticmethod
    def _find_duplicates(rows: list[dict[str, Any]], identity_fn) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        duplicates: list[dict[str, Any]] = []
        for row in rows:
            identity = identity_fn(row)
            if identity in seen:
                duplicates.append(
                    {
                        "identity": identity,
                        "first_task_or_path": seen[identity].get("Task ID") or seen[identity].get("Report Path") or "",
                        "duplicate_task_or_path": row.get("Task ID") or row.get("Report Path") or "",
                    }
                )
            else:
                seen[identity] = row
        return duplicates

    def _old_meeting_report_paths(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        old_paths: list[dict[str, Any]] = []
        for row in rows:
            path = str(row.get("Report Path", "")).strip().replace("/", "\\")
            if path.startswith("output\\") and not path.startswith("output\\active\\"):
                old_paths.append(
                    {
                        "meeting_name": str(row.get("Meeting Name", "")).strip(),
                        "report_date": str(row.get("Report Date", "")).strip(),
                        "report_path": path,
                    }
                )
        return old_paths

    @staticmethod
    def _action_tracker_identity(row: dict[str, Any]) -> str:
        source_meeting = str(row.get("Source Meeting", "")).strip()
        title = str(row.get("Title", "")).strip()
        return f"{source_meeting}||{title}"

    @staticmethod
    def _meeting_report_identity(row: dict[str, Any]) -> str:
        meeting_name = str(row.get("Meeting Name", "")).strip()
        report_date = str(row.get("Report Date", "")).strip()
        return f"{meeting_name}||{report_date}"

    def _render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [f"# 周报审计 | {payload['report_date']}", ""]
        overall_status = "通过" if payload.get("passed") else "失败"
        lines.extend(
            [
                "## 总体结论",
                "",
                f"- 状态：{overall_status}",
                f"- 周窗口：{payload.get('report_window', '')}",
                f"- 生成时间：{payload.get('generated_at', '')}",
                "- 规则：任一自检失败、重复记录、旧路径残留，都会拦截发送。",
                "",
            ]
        )

        self_check = payload["self_check"]
        self_check_status = "通过" if self_check["passed"] else "失败"
        lines.extend(
            [
                "## 自检门禁",
                "",
                f"- 状态：{self_check_status}",
                f"- 问题数：{self_check['issue_count']}",
                f"- 提示数：{self_check.get('warning_count', 0)}",
                f"- 自检报告：{self_check['markdown_path']}",
                f"- 先看摘要卡：{self_check['preview_paths'].get('summary_markdown', '')}",
                f"- 预览索引：{self_check['preview_paths']['index_markdown']}",
            ]
        )
        if self_check["issues"]:
            lines.extend(["", "### 自检问题", ""])
            for item in self_check["issues"]:
                lines.append(f"- {item['source']} | {item['code']} | {item['message']}")
        warnings = self_check.get("warnings") or []
        if warnings:
            lines.extend(["", "### 自检提示", ""])
            for item in warnings:
                lines.append(f"- {item}")

        lines.extend(["", "## Action Tracker", ""])
        lines.extend(self._render_audit_section(payload["local_action_tracker"], "本地 CSV"))
        lines.extend([""])
        lines.extend(self._render_audit_section(payload["sheet_action_tracker"], "飞书 Sheet"))

        lines.extend(["", "## Meeting Reports", ""])
        lines.extend(self._render_audit_section(payload["local_meeting_reports"], "本地 CSV"))
        lines.extend([""])
        lines.extend(self._render_audit_section(payload["sheet_meeting_reports"], "飞书 Sheet"))
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_audit_section(section: dict[str, Any], title: str) -> list[str]:
        lines = [f"### {title}", ""]
        if not section.get("available"):
            lines.append(f"- 未检查：{section.get('reason', 'unavailable')}")
            return lines
        lines.append(f"- 行数：{section.get('row_count', 0)}")
        lines.append(f"- 重复数：{section.get('duplicate_count', 0)}")
        if "current_report_date" in section:
            if "current_report_date_count" in section:
                lines.append(f"- 本期({section.get('current_report_date')})落账数：{section.get('current_report_date_count', 0)}")
            if "current_report_task_count" in section:
                lines.append(f"- 本期({section.get('current_report_date')})任务数：{section.get('current_report_task_count', 0)}")
        if "old_path_count" in section:
            lines.append(f"- 旧路径数：{section.get('old_path_count', 0)}")
        duplicates = section.get("duplicates") or []
        if duplicates:
            lines.append("- 重复项：")
            for item in duplicates:
                lines.append(
                    f"  - {item['identity']} | first={item['first_task_or_path']} | duplicate={item['duplicate_task_or_path']}"
                )
        old_paths = section.get("old_paths") or []
        if old_paths:
            lines.append("- 旧路径项：")
            for item in old_paths:
                lines.append(f"  - {item['meeting_name']} | {item['report_date']} | {item['report_path']}")
        return lines

    @staticmethod
    def _format_sheet_unavailable_reason(exc: Exception) -> str:
        text = str(exc)
        if "spreadsheet_token is deleted" in text or "note has been deleted" in text:
            return "飞书 Sheet 链接已失效或表格已删除，请更新 FEISHU_ACTION_TRACKER_URL / FEISHU_MEETING_REPORTS_URL 后重跑。"
        return f"飞书 Sheet 审计不可用：{text}"

