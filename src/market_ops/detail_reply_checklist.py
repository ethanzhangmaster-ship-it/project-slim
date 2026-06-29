from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class DetailReplyChecklistResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class DetailReplyChecklistBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> DetailReplyChecklistResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"detail_reply_checklist_{suffix}.md"
        json_path = output_dir / f"detail_reply_checklist_{suffix}.json"
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
                data_quality_audit_markdown=(output_dir / f"data_quality_audit_{suffix}.md")
                if (output_dir / f"data_quality_audit_{suffix}.md").exists()
                else None,
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
                project_detail_coverage_markdown=(output_dir / f"project_detail_coverage_{suffix}.md")
                if (output_dir / f"project_detail_coverage_{suffix}.md").exists()
                else None,
                p04_source_checklist_markdown=(output_dir / f"p04_source_checklist_{suffix}.md")
                if (output_dir / f"p04_source_checklist_{suffix}.md").exists()
                else None,
                detail_reply_checklist_markdown=markdown_path,
                management_action_list_markdown=(output_dir / f"management_action_list_{suffix}.md")
                if (output_dir / f"management_action_list_{suffix}.md").exists()
                else None,
            )
        return DetailReplyChecklistResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        observed_path = self._settings.active_output_dir / "feishu_detail_chat_observations.json"
        observed = self._load_json(observed_path).get("items", []) if observed_path.exists() else []
        real_chat_ids = [str(item.get("chat_id") or "") for item in observed if str(item.get("chat_id") or "").startswith("oc_")]
        configured_chat_ids = list(self._settings.feishu_detail_allowed_chat_ids or [])
        latest_observed = observed[0] if observed else {}
        preview_paths = self._load_preview_paths(report_date)

        passed = bool(configured_chat_ids)
        checklist = [
            {
                "step": "在真实飞书群触发详细版回复",
                "status": "done" if real_chat_ids else "pending",
                "needed": "@机器人并发送详细版触发词",
                "current": f"最近观察: chat_id={latest_observed.get('chat_id', '无')} | keyword={latest_observed.get('matched_keyword', '无')}",
                "done_when": "观察文件里出现真实 oc_... 群 chat_id",
            },
            {
                "step": "确认真实群 chat_id",
                "status": "done" if real_chat_ids else "pending",
                "needed": "至少 1 个真实 oc_... 群 ID",
                "current": ", ".join(real_chat_ids) if real_chat_ids else "当前只有本地模拟 chat-test / chat-observe-test",
                "done_when": "拿到真实群 chat_id，并确认不是测试占位值",
            },
            {
                "step": "写回 FEISHU_DETAIL_ALLOWED_CHAT_IDS",
                "status": "done" if configured_chat_ids else "pending",
                "needed": "把真实群 chat_id 写入 allowlist",
                "current": ", ".join(configured_chat_ids) if configured_chat_ids else "未配置",
                "done_when": ".env 中存在 FEISHU_DETAIL_ALLOWED_CHAT_IDS=oc_...",
            },
            {
                "step": "重新跑健康检查验证锁群",
                "status": "done" if configured_chat_ids else "pending",
                "needed": "健康检查显示是否已锁群=是",
                "current": "当前健康检查仍显示未锁群" if not configured_chat_ids else "健康检查已显示是否已锁群=是",
                "done_when": "weekly_health_check 里“是否已锁群=是”，且非 allowlisted 群不会回复",
            },
        ]
        return {
            "report_date": report_date.isoformat(),
            "passed": passed,
            "summary": {
                "problem": "详细版群内回复已锁定到真实飞书群。" if configured_chat_ids else "详细版群内回复当前还没有锁到真实飞书群。",
                "root_cause": (
                    "当前观察记录里还没有真实 oc_... 群 ID，allowlist 也还没有写回 .env。"
                    if not configured_chat_ids
                    else "allowlist 已配置。"
                ),
                "safe_mode_enabled": not configured_chat_ids,
                "configured_chat_ids": configured_chat_ids,
                "real_chat_ids": real_chat_ids,
                "observed_path": str(observed_path),
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
            f"# 详细版回复锁群清单 | {payload['report_date']}",
            "",
            f"- 当前问题：{summary.get('problem', '')}",
            f"- 当前根因：{summary.get('root_cause', '')}",
            f"- 当前 allowlist：{', '.join(summary.get('configured_chat_ids') or []) or '未配置'}",
            f"- 当前真实群 chat_id：{', '.join(summary.get('real_chat_ids') or []) or '未观察到'}",
            f"- 观察文件：{summary.get('observed_path', '')}",
            "",
            "## 核对步骤",
            "",
        ]
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
