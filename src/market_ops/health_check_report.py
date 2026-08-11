from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.pre_send_summary import PreSendSummaryBuilder, PreSendSummaryResult
from market_ops.preview_overview import write_preview_overview
from market_ops.report_audit import ReportAuditBuilder
from market_ops.self_check import run_self_check


@dataclass(slots=True)
class HealthCheckReportResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class HealthCheckReportBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(
        self,
        report_date: date,
        meeting_name: str,
        *,
        self_check_result=None,
        audit_payload: dict | None = None,
        pre_send_result=None,
    ) -> HealthCheckReportResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")

        self_check_payload = None
        if self_check_result is None:
            self_check_result = run_self_check(
                report_date=report_date,
                meeting_name=meeting_name,
                output_dir=output_dir,
            )
        if audit_payload is None:
            audit_payload = ReportAuditBuilder(self._settings).audit_payload(
                report_date=report_date,
                meeting_name=meeting_name,
                self_check_result=self_check_result,
            )
        if pre_send_result is None:
            pre_send_result = PreSendSummaryBuilder(self._settings).build(report_date=report_date)
            pre_send_payload = json.loads(pre_send_result.json_path.read_text(encoding="utf-8"))
        else:
            pre_send_payload = json.loads(pre_send_result.json_path.read_text(encoding="utf-8"))

        if self_check_result is not None:
            self_check_passed = self_check_result.passed
            self_check_markdown_path = str(self_check_result.markdown_path)
            self_check_issue_count = len(self_check_result.issues)
            self_check_warning_count = len(self_check_result.warnings)
        else:
            self_check_payload = self_check_payload or {}
            self_check_passed = bool(self_check_payload.get("passed"))
            self_check_markdown_path = str(output_dir / f"self_check_{suffix}.md")
            self_check_issue_count = len(self_check_payload.get("issues") or [])
            self_check_warning_count = len(self_check_payload.get("warnings") or [])

        google_revenue_attribution_payload = self._load_json_if_exists(output_dir / f"google_revenue_attribution_audit_{suffix}.json") or {}
        google_revenue_attribution_passed = bool(google_revenue_attribution_payload.get("passed", True))

        payload = {
            "report_date": report_date.isoformat(),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "meeting_name": meeting_name,
            "passed": bool(
                self_check_passed
                and audit_payload.get("passed")
                and pre_send_payload.get("passed")
                and google_revenue_attribution_passed
            ),
            "self_check": {
                "passed": self_check_passed,
                "markdown_path": self_check_markdown_path,
                "issue_count": self_check_issue_count,
                "warning_count": self_check_warning_count,
            },
            "report_audit": {
                "passed": bool(audit_payload.get("passed")),
                "path": str(output_dir / f"report_audit_{suffix}.md"),
            },
            "pre_send_summary": {
                "passed": bool(pre_send_payload.get("passed")),
                "path": str(pre_send_result.markdown_path),
                "headline": str(pre_send_payload.get("headline") or ""),
            },
            "data_quality_audit": self._load_json_if_exists(output_dir / f"data_quality_audit_{suffix}.json") or {},
            "data_quality_audit_path": str(output_dir / f"data_quality_audit_{suffix}.md"),
            "google_revenue_attribution_audit": google_revenue_attribution_payload,
            "google_revenue_attribution_audit_path": str(output_dir / f"google_revenue_attribution_audit_{suffix}.md"),
            "preview": {
                "overview_path": str(output_dir / f"weekly_preview_overview_{suffix}.md"),
                "summary_path": str(output_dir / f"card_preview_summary_{suffix}.md"),
                "index_path": str(output_dir / f"card_preview_index_{suffix}.md"),
            },
            "detail_reply": {
                "allowed_chat_ids_configured": bool(self._settings.feishu_detail_allowed_chat_ids),
                "keywords": list(self._settings.feishu_detail_trigger_keywords),
                "event_path": self._settings.feishu_event_path,
                "observed_chat_ids_path": str(output_dir / "feishu_detail_chat_observations.json"),
                "allowlist_suggestion_path": str(output_dir / "feishu_detail_allowlist_suggestion.env"),
                "observed_chat_ids": self._load_observed_chat_ids(output_dir / "feishu_detail_chat_observations.json"),
            },
            "closure_artifacts": {
                "closure_status_path": str(output_dir / f"closure_status_{suffix}.md"),
                "project_detail_coverage_path": str(output_dir / f"project_detail_coverage_{suffix}.md"),
                "p04_source_checklist_path": str(output_dir / f"p04_source_checklist_{suffix}.md"),
                "detail_reply_checklist_path": str(output_dir / f"detail_reply_checklist_{suffix}.md"),
            },
        }

        allowlist_suggestion_path = Path(payload["detail_reply"]["allowlist_suggestion_path"])
        if not allowlist_suggestion_path.exists():
            try:
                from market_ops.cli import _build_feishu_event_allowlist_suggestion

                suggestion, _, _ = _build_feishu_event_allowlist_suggestion(self._settings, 3)
                observed = payload["detail_reply"].get("observed_chat_ids") or []
                if any(str(item.get("chat_id") or "").startswith("oc_") for item in observed):
                    allowlist_suggestion_path.write_text(f"FEISHU_DETAIL_ALLOWED_CHAT_IDS={suggestion}\n", encoding="utf-8")
            except Exception:
                pass

        markdown_path = output_dir / f"weekly_health_check_{suffix}.md"
        json_path = output_dir / f"weekly_health_check_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._refresh_preview_overview(
            report_date=report_date,
            suffix=suffix,
            health_check_markdown=markdown_path,
        )
        return HealthCheckReportResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def load_cached(self, report_date: date) -> HealthCheckReportResult | None:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        markdown_path = output_dir / f"weekly_health_check_{suffix}.md"
        json_path = output_dir / f"weekly_health_check_{suffix}.json"
        if not markdown_path.exists() or not json_path.exists():
            return None
        payload = self._load_json_if_exists(json_path) or {}
        return HealthCheckReportResult(
            markdown_path=markdown_path,
            json_path=json_path,
            passed=bool(payload.get("passed")),
        )

    @staticmethod
    def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _refresh_preview_overview(self, *, report_date: date, suffix: str, health_check_markdown: Path) -> None:
        output_dir = self._settings.active_output_dir
        summary_markdown = output_dir / f"card_preview_summary_{suffix}.md"
        summary_json = output_dir / f"card_preview_summary_{suffix}.json"
        index_markdown = output_dir / f"card_preview_index_{suffix}.md"
        boss_markdown = output_dir / f"card_preview_boss_{suffix}.md"
        market_markdown = output_dir / f"card_preview_market_{suffix}.md"
        market_detail_markdown = output_dir / f"card_preview_market_detail_{suffix}.md"
        recovery_markdown = output_dir / f"card_preview_recovery_{suffix}.md"
        required = [
            summary_markdown,
            summary_json,
            index_markdown,
            boss_markdown,
            market_markdown,
            market_detail_markdown,
            recovery_markdown,
        ]
        if not all(path.exists() for path in required):
            return
        write_preview_overview(
            report_date,
            output_dir / f"weekly_preview_overview_{suffix}.md",
            summary_markdown=summary_markdown,
            summary_json=summary_json,
            index_markdown=index_markdown,
            boss_markdown=boss_markdown,
            market_markdown=market_markdown,
            market_detail_markdown=market_detail_markdown,
            recovery_markdown=recovery_markdown,
            self_check_markdown=output_dir / f"self_check_{suffix}.md",
            report_audit_markdown=output_dir / f"report_audit_{suffix}.md",
            pre_send_summary_markdown=output_dir / f"pre_send_summary_{suffix}.md",
            health_check_markdown=health_check_markdown,
            creative_source_readiness_markdown=output_dir / f"creative_source_readiness_{suffix}.md",
            data_quality_audit_markdown=(output_dir / f"data_quality_audit_{suffix}.md") if (output_dir / f"data_quality_audit_{suffix}.md").exists() else None,
            creative_attribution_audit_markdown=output_dir / f"creative_attribution_audit_{suffix}.md",
            google_creative_repair_audit_markdown=output_dir / f"google_creative_repair_audit_{suffix}.md",
            google_revenue_attribution_audit_markdown=(output_dir / f"google_revenue_attribution_audit_{suffix}.md") if (output_dir / f"google_revenue_attribution_audit_{suffix}.md").exists() else None,
            send_payload_consistency_markdown=(output_dir / f"send_payload_consistency_{suffix}.md") if (output_dir / f"send_payload_consistency_{suffix}.md").exists() else None,
            closure_status_markdown=(output_dir / f"closure_status_{suffix}.md") if (output_dir / f"closure_status_{suffix}.md").exists() else None,
            project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md") if (output_dir / f"project_detail_coverage_{suffix}.md").exists() else None,
            p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{suffix}.md") if (output_dir / f"p04_source_checklist_{suffix}.md").exists() else None,
            detail_reply_checklist_markdown=(output_dir / f"detail_reply_checklist_{suffix}.md") if (output_dir / f"detail_reply_checklist_{suffix}.md").exists() else None,
            management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md") if (output_dir / f"management_action_list_{suffix}.md").exists() else None,
        )

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        keywords = payload["detail_reply"].get("keywords") or []
        observed_chat_ids = payload["detail_reply"].get("observed_chat_ids") or []
        allowlist_suggestion = payload["detail_reply"]["allowlist_suggestion_path"]
        lines = [
            f"# 周报健康检查 | {payload['report_date']}",
            "",
            f"- 会议：{payload['meeting_name']}",
            f"- 状态：{'通过' if payload['passed'] else '失败'}",
            f"- 生成时间：{payload.get('generated_at', '')}",
            "",
            "## 核心门禁",
            "",
            f"- 自检：{'通过' if payload['self_check']['passed'] else '失败'}",
            f"- 自检报告：{payload['self_check']['markdown_path']}",
            f"- 自检问题数：{payload['self_check']['issue_count']}",
            f"- 自检提示数：{payload['self_check']['warning_count']}",
            f"- 审计：{'通过' if payload['report_audit']['passed'] else '失败'}",
            f"- 审计报告：{payload['report_audit']['path']}",
            f"- 数据质量：{'通过' if payload.get('data_quality_audit', {}).get('passed') else '失败'}",
            f"- 数据质量报告：{payload.get('data_quality_audit', {}).get('path') or payload.get('data_quality_audit_path', '')}",
            f"- Google收入归因：{'通过' if payload.get('google_revenue_attribution_audit', {}).get('passed') else '需复核'}",
            f"- Google收入归因报告：{payload.get('google_revenue_attribution_audit_path', '')}",
            f"- 发送摘要：{'通过' if payload['pre_send_summary']['passed'] else '失败'}",
            f"- 发送前摘要：{payload['pre_send_summary']['path']}",
            f"- 当前结论：{payload['pre_send_summary']['headline']}",
            "",
            "## 预览入口",
            "",
            f"- 总览页：{payload['preview']['overview_path']}",
            f"- 摘要卡：{payload['preview']['summary_path']}",
            f"- 预览索引：{payload['preview']['index_path']}",
            "",
            "## 闭环附件",
            "",
            f"- 闭环状态：{payload['closure_artifacts']['closure_status_path']}",
            f"- 项目明细覆盖：{payload['closure_artifacts']['project_detail_coverage_path']}",
            f"- P04 来源核对：{payload['closure_artifacts']['p04_source_checklist_path']}",
            f"- 详细版回复清单：{payload['closure_artifacts']['detail_reply_checklist_path']}",
            "",
            "## 群内详细版",
            "",
            f"- 事件路径：{payload['detail_reply']['event_path']}",
            f"- 触发关键词：{', '.join(keywords) if keywords else '未配置'}",
            f"- 已配置群白名单：{'是' if payload['detail_reply']['allowed_chat_ids_configured'] else '否'}",
            f"- 触发观测记录：{payload['detail_reply']['observed_chat_ids_path']}",
            f"- 白名单建议文件：{allowlist_suggestion if Path(allowlist_suggestion).exists() else '未生成'}",
            "",
            "## 群内用法",
            "",
            "- @机器人 详细",
            "- @机器人 详细版",
            "- @机器人 周报详细版",
            "- @机器人 老板版",
            "- @机器人 市场版",
            "- @机器人 回收",
            "- @机器人 管理层决策周报",
            "",
        ]
        if observed_chat_ids:
            lines.extend(["## 最近触发群", ""])
            for item in observed_chat_ids[:5]:
                lines.append(
                    "- "
                    f"chat_id={item.get('chat_id', '')} | "
                    f"last_seen={item.get('last_seen_at', '')} | "
                    f"keyword={item.get('matched_keyword', '') or '-'} | "
                    f"allowlist_configured={'是' if item.get('allowlist_configured') else '否'} | "
                    f"allowlisted={'是' if item.get('allowlisted') else '否'} | "
                    f"reply_sent={'是' if item.get('reply_sent') else '否'}"
                )
            lines.append("")
        if not payload["detail_reply"]["allowed_chat_ids_configured"]:
            lines.extend(
                [
                    "## ???",
                    "",
                    "- ????????????????????????????????????????? chat_id???? FEISHU_DETAIL_ALLOWED_CHAT_IDS?",
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _load_observed_chat_ids(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]
