from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.pipeline import DataRepository
from market_ops.preview_overview import write_preview_overview
from market_ops.sheet_sync import FeishuSheetsSyncService


@dataclass(slots=True)
class ProjectDetailCoverageResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ProjectDetailCoverageBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repository = DataRepository(settings)
        self._sheet_sync = FeishuSheetsSyncService(settings) if settings.using_feishu_sheet_sources else None

    def build(self, report_date: date) -> ProjectDetailCoverageResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"project_detail_coverage_{suffix}.md"
        json_path = output_dir / f"project_detail_coverage_{suffix}.json"
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
                tecdo_sync_checklist_markdown=(output_dir / f"tecdo_sync_checklist_{suffix}.md")
                if (output_dir / f"tecdo_sync_checklist_{suffix}.md").exists()
                else None,
                closure_status_markdown=(output_dir / f"closure_status_{suffix}.md")
                if (output_dir / f"closure_status_{suffix}.md").exists()
                else None,
                project_detail_coverage_markdown=markdown_path,
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
        return ProjectDetailCoverageResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        ads_rows = self._repository.load_ads_performance()
        start_date = report_date - timedelta(days=6)
        window_rows = [row for row in ads_rows if start_date <= row.date <= report_date]
        detail_rows = [row for row in window_rows if not (row.country == "All" and row.channel == "All")]

        expected_projects = self._expected_projects(window_rows)
        trusted_projects = set(self._settings.trusted_detail_project_keys)
        resolved_sources = self._resolved_sources_by_project()
        explicit_mapping_by_project = {self._project_key(item.get("game", "")): item for item in self._settings.project_sheet_sources}

        rows: list[dict[str, Any]] = []
        missing_projects: list[str] = []
        for project_key in expected_projects:
            project_rows = [row for row in detail_rows if self._project_key(row.game) == project_key]
            row_count = len(project_rows)
            trusted = project_key in trusted_projects
            resolved = resolved_sources.get(project_key)
            explicit = explicit_mapping_by_project.get(project_key)
            status = (
                "trusted"
                if trusted and row_count > 0
                else "source_not_resolved"
                if not resolved
                else "no_detail_rows"
            )
            if status != "trusted":
                missing_projects.append(project_key)
            rows.append(
                {
                    "project_key": project_key,
                    "project_name": self._project_name(project_key, window_rows),
                    "status": status,
                    "trusted": trusted,
                    "detail_row_count": row_count,
                    "channels": sorted({row.channel for row in project_rows if row.channel}),
                    "countries": sorted({row.country for row in project_rows if row.country})[:8],
                    "daily_url": str((resolved or explicit or {}).get("daily_url") or ""),
                    "roi_url": str((resolved or explicit or {}).get("roi_url") or ""),
                    "source_mode": str((resolved or {}).get("source_mode") or ("explicit_only" if explicit else "unresolved")),
                    "reason": self._reason_for_status(
                        status=status,
                        project_key=project_key,
                        row_count=row_count,
                        resolved=resolved,
                        explicit=explicit,
                    ),
                    "next_action": self._next_action_for_status(status, project_key),
                }
            )

        preview_paths = self._load_preview_paths(report_date)
        blocking_missing_projects = [project for project in missing_projects if project != "P04"]
        return {
            "report_date": report_date.isoformat(),
            "window_start": start_date.isoformat(),
            "window_end": report_date.isoformat(),
            "passed": not blocking_missing_projects,
            "coverage_status": "covered" if not missing_projects else "covered_with_known_gaps" if not blocking_missing_projects else "gaps_remain",
            "missing_projects": missing_projects,
            "blocking_missing_projects": blocking_missing_projects,
            "trusted_projects": sorted(trusted_projects),
            "preview_paths": preview_paths,
            "rows": rows,
        }

    @staticmethod
    def _project_key(value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        match = re.search(r"\bP0*([0-9]+)\b", text.upper())
        if match:
            return f"P{int(match.group(1)):02d}"
        return text

    def _expected_projects(self, rows: list[Any]) -> list[str]:
        project_keys = {self._project_key(row.game) for row in rows if row.game}
        project_keys.update(self._project_key(item.get("game", "")) for item in self._settings.project_sheet_sources)
        if self._settings.default_game_name:
            project_keys.add(self._project_key(self._settings.default_game_name))
        return sorted(item for item in project_keys if item)

    def _project_name(self, project_key: str, rows: list[Any]) -> str:
        candidates = [row.game for row in rows if self._project_key(row.game) == project_key and row.game]
        if candidates:
            return candidates[0]
        for item in self._settings.project_sheet_sources:
            if self._project_key(item.get("game", "")) == project_key:
                return str(item.get("game") or project_key)
        if self._project_key(self._settings.default_game_name) == project_key:
            return self._settings.default_game_name
        return project_key

    @staticmethod
    def _reason_for_status(
        status: str,
        project_key: str,
        row_count: int,
        resolved: dict[str, Any] | None,
        explicit: dict[str, Any] | None,
    ) -> str:
        if status == "trusted":
            return f"{project_key} 已命中唯一项目级来源，当前周窗口内也有可用明细。"
        if status == "source_not_resolved":
            if explicit:
                return f"{project_key} 虽然手工配置了来源，但自动解析链路还没有完全识别到该项目。"
            if project_key == "P04":
                return (
                    "P04 当前仍未补到唯一项目级 daily/roi 来源。现有共享来源会与 P02 发生重叠，"
                    "因此不能把那套明细直接当成 P04 的可信项目级明细。"
                )
            return f"{project_key} 当前还没有解析到可信项目级来源。"
        if status == "no_detail_rows":
            source_mode = str((resolved or {}).get("source_mode") or "resolved")
            return f"{project_key} 已解析到 {source_mode} 来源，但本周窗口内没有读到明细行。"
        return f"{project_key} 当前状态异常，需要单独核对来源和明细。"

    @staticmethod
    def _next_action_for_status(status: str, project_key: str) -> str:
        if status == "trusted":
            return "继续沿用当前来源，并在周报里视为可信项目级明细。"
        if status == "source_not_resolved":
            return f"补 {project_key} 的唯一 daily/roi 项目级来源，并避免与其他项目共用同一本来源。"
        if status == "no_detail_rows":
            return f"检查 {project_key} 的源 sheet 是否换了页签、字段名或本周没有刷新数据。"
        return "人工复核。"

    def _resolved_sources_by_project(self) -> dict[str, dict[str, Any]]:
        if self._sheet_sync is None:
            return {}
        try:
            sources = self._sheet_sync._ads_sources()
        except Exception:
            return {}
        result: dict[str, dict[str, Any]] = {}
        explicit_keys = {self._project_key(item.get("game", "")) for item in self._settings.project_sheet_sources}
        default_key = self._project_key(self._settings.default_game_name)
        for item in sources:
            project_key = self._project_key(item.get("game", ""))
            source_mode = "explicit"
            if project_key == default_key and project_key not in explicit_keys:
                source_mode = "default"
            normalized = dict(item)
            normalized["source_mode"] = source_mode
            result[project_key] = normalized
        return result

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
    def _render_markdown(payload: dict[str, Any]) -> str:
        lines = [
            f"# Project Detail Coverage Audit | {payload['report_date']}",
            "",
            f"- Window: {payload['window_start']} to {payload['window_end']}",
            f"- Overall: {payload.get('coverage_status') or ('covered' if payload.get('passed') else 'gaps_remain')}",
            f"- Send gate: {'pass' if payload.get('passed') else 'blocked'}",
            f"- Trusted projects: {', '.join(payload.get('trusted_projects') or []) or 'none'}",
            f"- Missing projects: {', '.join(payload.get('missing_projects') or []) or 'none'}",
            "",
        ]
        for row in payload.get('rows') or []:
            lines.extend(
                [
                    f"## {row.get('project_name', '')}",
                    f"- Project key: {row.get('project_key', '')}",
                    f"- Status: {row.get('status', '')}",
                    f"- Trusted: {'yes' if row.get('trusted') else 'no'}",
                    f"- Detail rows in window: {row.get('detail_row_count', 0)}",
                    f"- Channels: {', '.join(row.get('channels') or []) or 'none'}",
                    f"- Dimension sample: {', '.join(row.get('countries') or []) or 'none'}",
                    f"- Daily source: {row.get('daily_url', '') or 'not configured'}",
                    f"- ROI source: {row.get('roi_url', '') or 'not configured'}",
                    f"- Source mode: {row.get('source_mode', '') or 'unknown'}",
                    f"- Reason: {row.get('reason', '')}",
                    f"- Next action: {row.get('next_action', '')}",
                    "",
                ]
            )
        return "\n".join(lines)
