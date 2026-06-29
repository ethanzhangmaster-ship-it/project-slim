from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class P04SourceChecklistResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class P04SourceChecklistBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> P04SourceChecklistResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"p04_source_checklist_{suffix}.md"
        json_path = output_dir / f"p04_source_checklist_{suffix}.json"
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
                tecdo_probe_markdown=(output_dir / f"tecdo_probe_{suffix}.md") if (output_dir / f"tecdo_probe_{suffix}.md").exists() else None,
                tecdo_account_reconciliation_markdown=(output_dir / f"tecdo_account_reconciliation_{suffix}.md") if (output_dir / f"tecdo_account_reconciliation_{suffix}.md").exists() else None,
                tecdo_sync_checklist_markdown=(output_dir / f"tecdo_sync_checklist_{suffix}.md") if (output_dir / f"tecdo_sync_checklist_{suffix}.md").exists() else None,
                closure_status_markdown=(output_dir / f"closure_status_{suffix}.md") if (output_dir / f"closure_status_{suffix}.md").exists() else None,
                project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md") if (output_dir / f"project_detail_coverage_{suffix}.md").exists() else None,
                p04_source_checklist_markdown=markdown_path,
                detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{suffix}.md") if (output_dir / f"detail_reply_checklist_{suffix}.md").exists() else None,
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md") if (output_dir / f"management_action_list_{suffix}.md").exists() else None,
            )
        return P04SourceChecklistResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        coverage = self._load_json(output_dir / f"project_detail_coverage_{suffix}.json")
        p04_row = next(
            (row for row in (coverage.get("rows") or []) if str(row.get("project_key") or "") == "P04"),
            {},
        )
        preview_paths = self._load_preview_paths(report_date)
        current_default_daily = str(self._settings.feishu_daily_data_url or "")
        current_default_roi = str(self._settings.feishu_roi_url or "")
        configured_sources = list(self._settings.project_sheet_sources or [])
        p04_template_path = output_dir / "p04_project_sheet_sources_template.env"
        verify_example_command = f"python -m market_ops.cli p04-verify-after-mapping --report-date {report_date.isoformat()}"
        p04_explicit_source = next(
            (item for item in configured_sources if str(item.get("game") or "").strip() == "P04 Witch"),
            None,
        )

        checklist = [
            {
                "step": "确认 P04 专属投放明细飞书链接",
                "status": "done" if p04_explicit_source and str(p04_explicit_source.get("daily_url") or "").strip() else "pending",
                "needed": "P04 专属 daily_url",
                "current": str((p04_explicit_source or {}).get("daily_url") or "未配置"),
                "done_when": "P04 的 daily 飞书链接已进入项目映射",
            },
            {
                "step": "确认 P04 专属 ROI / 回收飞书链接",
                "status": "done" if p04_explicit_source and str((p04_explicit_source.get("roi_url") or p04_explicit_source.get('daily_url') or '')).strip() else "pending",
                "needed": "P04 专属 roi_url",
                "current": str((p04_explicit_source or {}).get("roi_url") or "未配置"),
                "done_when": "P04 的 ROI 飞书链接已进入项目映射",
            },
            {
                "step": "沿用已锁定项目映射并补入 P04",
                "status": "done" if p04_template_path.exists() else "pending",
                "needed": "基于当前 P02/P07 锁定映射，补一条 P04 映射",
                "current": str(p04_template_path) if p04_template_path.exists() else "未生成模板",
                "done_when": "模板已生成，你只需要把 P04 两个链接填进去",
            },
            {
                "step": "避免继续复用默认来源",
                "status": "done",
                "needed": "把默认来源保留给默认项目，不再假定它就是 P04",
                "current": f"default_daily={current_default_daily or '未配置'} | default_roi={current_default_roi or '未配置'}",
                "done_when": "当前系统已确认默认来源不会自动当成 P04 源",
            },
            {
                "step": "补链后重新同步并验证",
                "status": "pending",
                "needed": "运行一键验证命令，并看到 P04 出现在项目级明细覆盖里",
                "current": verify_example_command,
                "done_when": "project_detail_coverage 里 P04 = trusted，且 detail_row_count > 0；同时生成 p04_mapping_verify_YYYYMMDD.md",
            },
        ]
        return {
            "report_date": report_date.isoformat(),
            "passed": bool(p04_explicit_source),
            "summary": {
                "problem": "P04 当前没有进入项目级投放明细同步源，所以不能产出可信项目明细。",
                "root_cause": str(p04_row.get("reason") or "P04 未进入同步源解析"),
                "what_you_need_to_provide": [
                    "P04 专属 daily_url",
                    "P04 专属 roi_url",
                ],
                "template_path": str(p04_template_path),
                "verify_command": verify_example_command,
            },
            "current_state": {
                "default_daily_url": current_default_daily,
                "default_roi_url": current_default_roi,
                "p04_coverage_status": str(p04_row.get("status") or "unknown"),
                "p04_detail_row_count": int(p04_row.get("detail_row_count") or 0),
                "configured_project_sources": configured_sources,
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
        current = payload.get("current_state") or {}
        lines = [
            f"# P04 来源核对清单 | {payload['report_date']}",
            "",
            f"- 当前问题：{summary.get('problem', '')}",
            f"- 当前根因：{summary.get('root_cause', '')}",
            f"- 默认 daily：{current.get('default_daily_url', '') or '未配置'}",
            f"- 默认 roi：{current.get('default_roi_url', '') or '未配置'}",
            f"- P04 当前覆盖状态：{current.get('p04_coverage_status', '')}",
            f"- P04 当前明细行数：{current.get('p04_detail_row_count', 0)}",
            f"- 可直接填写的模板：{summary.get('template_path', '') or '未生成'}",
            f"- 补完后验证命令：{summary.get('verify_command', '') or '未生成'}",
            "",
            "## 你需要提供",
            "",
        ]
        for item in summary.get("what_you_need_to_provide") or []:
            lines.append(f"- {item}")
        lines.extend(["", "## 当前已锁定项目映射", ""])
        for item in current.get("configured_project_sources") or []:
            lines.extend(
                [
                    f"### {item.get('game', '')}",
                    f"- Daily 来源：{item.get('daily_url', '')}",
                    f"- ROI 来源：{item.get('roi_url', '') or item.get('daily_url', '')}",
                    "",
                ]
            )
        lines.extend(["## 核对步骤", ""])
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
