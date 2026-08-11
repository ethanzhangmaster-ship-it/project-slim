from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.preview_overview import write_preview_overview


@dataclass(slots=True)
class ExternalBlockersResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ExternalBlockersBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, report_date: date) -> ExternalBlockersResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self._build_payload(report_date)

        markdown_path = output_dir / f"external_blockers_{suffix}.md"
        json_path = output_dir / f"external_blockers_{suffix}.json"
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
        return ExternalBlockersResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def _build_payload(self, report_date: date) -> dict[str, Any]:
        suffix = report_date.strftime("%Y%m%d")
        output_dir = self._settings.active_output_dir
        p04 = self._load_json(output_dir / f"p04_source_checklist_{suffix}.json")
        detail_reply = self._load_json(output_dir / f"detail_reply_checklist_{suffix}.json")
        creative_readiness = self._load_json(output_dir / f"creative_source_readiness_{suffix}.json")
        preview_paths = self._load_preview_paths(report_date)

        items = [
            {
                "name": "P04 项目级飞书映射",
                "status": "known_gap" if not p04.get("passed") else "done",
                "what_missing": ["P04 专属 daily_url", "P04 专属 roi_url"] if not p04.get("passed") else [],
                "current": (
                    "P04 独立项目级飞书映射仍未补齐，当前已降级为项目精度增强项，不再阻塞主链路。"
                    if not p04.get("passed")
                    else str((p04.get("summary") or {}).get("root_cause") or "")
                ),
                "next_command": f"python -m market_ops.cli p04-verify-after-mapping --report-date {report_date.isoformat()}",
                "success_criteria": "主链路已可运行；如需提升 P04 项目级可信度，再做到 P04 = trusted，且 detail_row_count > 0",
            },
            {
                "name": "详细版群锁定",
                "status": "done" if detail_reply.get("passed") or bool((detail_reply.get("summary") or {}).get("safe_mode_enabled")) else "pending",
                "what_missing": []
                if detail_reply.get("passed") or bool((detail_reply.get("summary") or {}).get("safe_mode_enabled"))
                else ["真实 oc_... 群 chat_id", "FEISHU_DETAIL_ALLOWED_CHAT_IDS 回填"],
                "current": (
                    "详细版已锁定到真实飞书群。"
                    if detail_reply.get("passed")
                    else
                    "当前已切到安全模式：未锁群时只观测、不自动回复详细版。"
                    if bool((detail_reply.get("summary") or {}).get("safe_mode_enabled"))
                    else str((detail_reply.get("summary") or {}).get("root_cause") or "")
                ),
                "next_command": f"python -m market_ops.cli health-check --report-date {report_date.isoformat()}",
                "success_criteria": "当前已锁群；如需新增群，再补充 allowlist 并复跑健康检查。",
            },
            {
                "name": "Google 直连素材凭证",
                "status": "done"
                if bool((creative_readiness.get("summary") or {}).get("google_can_run_now"))
                else "pending",
                "what_missing": list((creative_readiness.get("summary") or {}).get("google_missing_env") or []),
                "current": "Google 解析层已接入，但 Google Ads 直连素材凭证仍缺失。",
                "next_command": f"python -m market_ops.cli creative-source-readiness --report-date {report_date.isoformat()}",
                "success_criteria": "当前周报已有可用素材来源；如需原生 creative id，再补 google_can_run_now = true",
            },
        ]
        return {
            "report_date": report_date.isoformat(),
            "passed": all(item["status"] in {"done", "known_gap"} for item in items),
            "items": items,
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
        lines = [
            f"# 外部阻塞总表 | {payload['report_date']}",
            "",
            f"- 当前状态：{'主链路已闭环；其余为增强项或安全模式待放开项' if payload.get('passed') else '仍有外部阻塞'}",
            "- 状态说明：done=已完成；known_gap=已知缺口但不阻塞主链路；pending=仍阻塞。",
            "",
        ]
        for item in payload.get("items") or []:
            lines.extend(
                [
                    f"## {item.get('name', '')}",
                    f"- 状态：{item.get('status', '')}",
                    f"- 当前卡点：{item.get('current', '')}",
                    f"- 缺少内容：{', '.join(item.get('what_missing') or []) or '无'}",
                    f"- 下一条命令：{item.get('next_command', '')}",
                    f"- 成功标准：{item.get('success_criteria', '')}",
                    "",
                ]
            )
        return "\n".join(lines)
