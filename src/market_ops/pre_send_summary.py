from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.metric_reconciliation import WeeklyMetricReconciliationBuilder
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class PreSendSummaryResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class PreSendSummaryBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> PreSendSummaryResult:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        reconciliation_json = output_dir / f"weekly_metric_reconciliation_{suffix}.json"
        if not reconciliation_json.exists():
            WeeklyMetricReconciliationBuilder(self._settings).build(report_date=report_date)

        self_check_payload = self._load_json(output_dir / f"self_check_{suffix}.json")
        audit_payload = self._load_json(output_dir / f"report_audit_{suffix}.json")
        reconciliation_payload = self._load_json(reconciliation_json)
        data_quality_payload = self._load_json(output_dir / f"data_quality_audit_{suffix}.json")

        summary = self._compose_summary(report_date, self_check_payload, audit_payload, reconciliation_payload, data_quality_payload)

        markdown_path = output_dir / f"pre_send_summary_{suffix}.md"
        json_path = output_dir / f"pre_send_summary_{suffix}.json"
        markdown_path.write_text(self._render_markdown(summary), encoding="utf-8")
        json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        self_check_preview = self_check_payload.get("preview_paths") or {}
        if self_check_preview:
            write_preview_overview(
                report_date,
                output_dir / f"weekly_preview_overview_{suffix}.md",
                summary_markdown=Path(self_check_preview["summary_markdown"]),
                summary_json=Path(self_check_preview["summary_json"]),
                index_markdown=Path(self_check_preview["index_markdown"]),
                boss_markdown=Path(self_check_preview["boss_markdown"]),
                market_markdown=Path(self_check_preview["market_markdown"]),
                market_detail_markdown=Path(self_check_preview["market_detail_markdown"]),
                recovery_markdown=Path(self_check_preview["recovery_markdown"]),
                self_check_markdown=output_dir / f"self_check_{suffix}.md",
                report_audit_markdown=output_dir / f"report_audit_{suffix}.md",
                pre_send_summary_markdown=markdown_path,
                health_check_markdown=output_dir / f"weekly_health_check_{suffix}.md",
                creative_source_readiness_markdown=output_dir / f"creative_source_readiness_{suffix}.md",
                data_quality_audit_markdown=(output_dir / f"data_quality_audit_{suffix}.md") if (output_dir / f"data_quality_audit_{suffix}.md").exists() else None,
                creative_attribution_audit_markdown=Path(
                    ((self_check_payload.get("creative_attribution_audit") or {}).get("summary_path"))
                    or output_dir / f"creative_attribution_audit_{suffix}.md"
                ),
                google_creative_repair_audit_markdown=Path(
                    ((self_check_payload.get("google_creative_repair_audit") or {}).get("summary_path"))
                    or output_dir / f"google_creative_repair_audit_{suffix}.md"
                ),
                closure_status_markdown=output_dir / f"closure_status_{suffix}.md",
                project_detail_coverage_markdown=output_dir / f"project_detail_coverage_{suffix}.md",
                p04_source_checklist_markdown=output_dir / f"p04_source_checklist_{suffix}.md",
                detail_reply_checklist_markdown=output_dir / f"detail_reply_checklist_{suffix}.md",
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md") if (output_dir / f"management_action_list_{suffix}.md").exists() else None,
            )

        return PreSendSummaryResult(markdown_path=markdown_path, json_path=json_path, passed=bool(summary["passed"]))

    @staticmethod
    def build_card(summary: dict[str, Any]) -> dict[str, Any]:
        executive_lines = [f"- {line}" for line in (summary.get("executive_summary") or [])]
        market_lines = [f"- {line}" for line in (summary.get("market_summary") or [])]
        risk_lines = [f"- {line}" for line in (summary.get("risks") or [])]
        company_metrics = summary.get("key_metrics", {}).get("公司", {}) if isinstance(summary.get("key_metrics"), dict) else {}
        company_roi = company_metrics.get("公司总收入ROI", "")
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green" if summary.get("passed") else "red",
                "title": {"tag": "plain_text", "content": f"发群前结论页 | {summary.get('report_date', '')}"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**发送建议**\n- {summary.get('send_recommendation', '')}\n\n"
                            f"**结论**\n- {summary.get('headline', '')}"
                            + (f"\n\n**公司总收入ROI**\n- {company_roi}" if company_roi else "")
                        ),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**老板版首页**\n" + "\n".join(executive_lines or ["- 暂无"]),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**市场版首页**\n" + "\n".join(market_lines or ["- 暂无"]),
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "**风险提醒**\n" + "\n".join(risk_lines or ["- 暂无"]),
                    },
                },
            ],
        }

    @staticmethod
    def build_console_summary(summary: dict[str, Any]) -> str:
        lines = [
            f"发送建议：{summary.get('send_recommendation', '')}",
            f"结论：{summary.get('headline', '')}",
        ]
        for item in (summary.get("executive_summary") or [])[:2]:
            lines.append(item)
        for item in (summary.get("market_summary") or [])[:2]:
            lines.append(item)
        return " | ".join(lines)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"available": False, "path": str(path), "issues": [f"missing: {path.name}"]}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload["available"] = True
            payload["path"] = str(path)
        return payload

    def _compose_summary(
        self,
        report_date: date,
        self_check_payload: dict[str, Any],
        audit_payload: dict[str, Any],
        reconciliation_payload: dict[str, Any],
        data_quality_payload: dict[str, Any],
    ) -> dict[str, Any]:
        self_check_passed = bool(self_check_payload.get("passed"))
        audit_passed = bool(audit_payload.get("passed"))
        reconciliation_passed = bool(reconciliation_payload.get("checks", {}).get("passed"))
        data_quality_passed = bool(data_quality_payload.get("passed"))
        gate_passed = self_check_passed and audit_passed and reconciliation_passed and data_quality_passed

        key_metrics = self._extract_key_metrics(reconciliation_payload)
        risks = self._build_risks(self_check_payload, audit_payload, reconciliation_payload, data_quality_payload)
        preview_paths = self_check_payload.get("preview_paths") or {}
        executive_summary = self._extract_summary_lines(Path(preview_paths["boss_markdown"])) if preview_paths.get("boss_markdown") else []
        market_summary = self._extract_summary_lines(Path(preview_paths["market_markdown"])) if preview_paths.get("market_markdown") else []
        next_focus = self._build_focus_points(key_metrics, executive_summary, market_summary)

        return {
            "report_date": report_date.isoformat(),
            "passed": gate_passed,
            "send_recommendation": "可发送" if gate_passed else "先不要发送",
            "headline": self._headline(gate_passed, risks),
            "key_metrics": key_metrics,
            "risks": risks,
            "focus_points": next_focus,
            "executive_summary": executive_summary[:5],
            "market_summary": market_summary[:6],
            "sources": {
                "self_check": self_check_payload.get("path", ""),
                "report_audit": audit_payload.get("path", ""),
                "metric_reconciliation": reconciliation_payload.get("path", ""),
                "data_quality_audit": data_quality_payload.get("path", ""),
            },
        }

    @staticmethod
    def _headline(passed: bool, risks: list[str]) -> str:
        if passed:
            return "本周周报已过门禁，核心数字口径一致，可以作为当前发送版本。"
        if risks:
            return f"本周周报暂不建议发送，当前主要卡点：{risks[0]}"
        return "本周周报暂不建议发送，当前仍有未通过项。"

    @staticmethod
    def _extract_key_metrics(reconciliation_payload: dict[str, Any]) -> dict[str, dict[str, str]]:
        traces = reconciliation_payload.get("traces") or []
        result: dict[str, dict[str, str]] = {}
        valid_scopes = {"公司", "P04 Witch", "P02 Mermaid", "P07 Vampire"}
        for item in traces:
            scope = str(item.get("scope") or "")
            metric = str(item.get("metric") or "")
            if scope not in valid_scopes:
                continue
            result.setdefault(scope, {})[metric] = str(item.get("display_value") or "")
        return result

    @staticmethod
    def _build_risks(
        self_check_payload: dict[str, Any],
        audit_payload: dict[str, Any],
        reconciliation_payload: dict[str, Any],
        data_quality_payload: dict[str, Any],
    ) -> list[str]:
        risks: list[str] = []
        for issue in self_check_payload.get("issues") or []:
            if isinstance(issue, dict):
                message = issue.get("message", "")
            else:
                message = str(issue)
            if message:
                risks.append(f"自检未通过：{message}")
        for issue in audit_payload.get("self_check", {}).get("issues") or []:
            if isinstance(issue, dict):
                message = issue.get("message", "")
            else:
                message = str(issue)
            if message:
                risks.append(f"审计发现问题：{message}")
        for section_name, label in (
            ("sheet_action_tracker", "飞书 Action Tracker"),
            ("sheet_meeting_reports", "飞书 Meeting Reports"),
        ):
            section = audit_payload.get(section_name) or {}
            configured = bool(audit_payload.get(f"{section_name}_configured"))
            if configured and not section.get("available"):
                reason = str(section.get("reason") or "不可用")
                risks.append(f"{label} 不可用：{reason}")
        for issue in reconciliation_payload.get("checks", {}).get("issues") or []:
            if issue:
                risks.append(f"对账未通过：{issue}")
        if data_quality_payload.get("available") and not data_quality_payload.get("passed"):
            weak_modules = [
                str(item.get("module"))
                for item in data_quality_payload.get("modules") or []
                if str(item.get("level") or "") == "低"
            ]
            if weak_modules:
                risks.append(f"数据质量未通过：{', '.join(weak_modules[:4])} 可信度低，只能预览，不能自动发群。")
            else:
                risks.append("数据质量未通过：核心数据仍需复核，只能预览，不能自动发群。")

        if risks:
            return risks

        warnings: list[str] = []
        for warning in self_check_payload.get("warnings") or []:
            if warning:
                warnings.append(str(warning))

        creative_source = self_check_payload.get("creative_source_readiness") or {}
        creative_summary = creative_source.get("summary") or {}
        if creative_summary.get("google_resolver_ready"):
            warnings.append("Google 素材修复链路已接入周报链路；当前仍先按修复候选清单呈现。")
        if not warnings and audit_payload.get("passed"):
            warnings.append("当前没有门禁阻断项。")
        return warnings

    @staticmethod
    def _build_focus_points(
        key_metrics: dict[str, dict[str, str]],
        executive_summary: list[str],
        market_summary: list[str],
    ) -> list[str]:
        focus: list[str] = []
        if executive_summary:
            focus.extend(executive_summary[:3])
        if market_summary:
            focus.extend(line for line in market_summary[:3] if line not in focus)

        company = key_metrics.get("公司", {})
        if company and not focus:
            focus.append(
                f"公司层先看 4 个值：花费 {company.get('本周花费', '-')}"
                f" / 收入 {company.get('整体收入', '-')}"
                f" / 公司总收入ROI {company.get('公司总收入ROI', '-')}"
                f" / 主投渠道 {company.get('主投渠道', '-')}"
            )

        for project in ("P04 Witch", "P02 Mermaid", "P07 Vampire"):
            block = key_metrics.get(project, {})
            if not block or len(focus) >= 6:
                continue
            focus.append(
                f"{project}：花费 {block.get('花费', '-')}"
                f" / 总收入 {block.get('总收入', '-')}"
                f" / 总收入ROI {block.get('总收入ROI', '-')}"
                f" / 付费净ROI {block.get('付费净ROI', '-')}"
            )
        return focus

    @staticmethod
    def _render_markdown(summary: dict[str, Any]) -> str:
        lines = [
            f"# 发群前结论页 | {summary['report_date']}",
            "",
            f"- 发送建议：{summary['send_recommendation']}",
            f"- 结论：{summary['headline']}",
            "",
            "## 老板版首页",
            "",
        ]
        for line in summary.get("executive_summary") or []:
            lines.append(f"- {line}")

        lines.extend(["", "## 市场版首页", ""])
        for line in summary.get("market_summary") or []:
            lines.append(f"- {line}")

        lines.extend(["", "## 风险提醒", ""])
        for line in summary.get("risks") or ["暂无"]:
            lines.append(f"- {line}")

        lines.extend(["", "## 来源文件", ""])
        sources = summary.get("sources") or {}
        lines.append(f"- 自检：{sources.get('self_check', '')}")
        lines.append(f"- 审计：{sources.get('report_audit', '')}")
        lines.append(f"- 对账：{sources.get('metric_reconciliation', '')}")
        lines.append(f"- 数据质量：{sources.get('data_quality_audit', '')}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _extract_summary_lines(path: Path) -> list[str]:
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        sections: list[tuple[str, list[str]]] = [
            ("**第一页：管理层摘要**", ["---", "**数据可信度**"]),
            ("## 第一层：管理层摘要", ["## 第二层：项目分析", "## 数据可信度"]),
            ("**市场负责人摘要**", ["---", "**1. 公司总体数据情况**"]),
            ("**市场负责人的摘要**", ["---", "**1. 公司总体数据情况**"]),
            ("## 市场负责人摘要", ["## 1. 公司总体数据情况"]),
        ]
        for start_marker, end_candidates in sections:
            start = text.find(start_marker)
            if start < 0:
                continue
            end_positions = [
                text.find(marker, start + len(start_marker))
                for marker in end_candidates
                if text.find(marker, start + len(start_marker)) >= 0
            ]
            end = min(end_positions) if end_positions else len(text)
            block = text[start:end]
            return [re.sub(r"^- ", "", line.strip()) for line in block.splitlines() if line.strip().startswith("- ")]
        return []
