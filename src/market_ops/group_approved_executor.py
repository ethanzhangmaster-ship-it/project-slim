from __future__ import annotations

import json
from datetime import date

from market_ops.config import Settings
from market_ops.group_requirements_queue import GroupRequirementsQueue
from market_ops.health_check_report import HealthCheckReportBuilder
from market_ops.pre_send_summary import PreSendSummaryBuilder
from market_ops.report_audit import ReportAuditBuilder
from market_ops.self_check import run_self_check


def execute_group_approved_tasks(
    settings: Settings,
    *,
    report_date: date,
    meeting_name: str,
    chat_id: str = "",
    request_ids: list[str] | None = None,
) -> tuple[dict[str, object], dict[str, str]]:
    queue = GroupRequirementsQueue(settings.active_output_dir / "group_requirements_queue.json")
    approved_items = queue.list_by_status(chat_id=chat_id, statuses=["approved"], limit=200)
    wanted = {item.strip() for item in (request_ids or []) if item.strip()}
    if wanted:
        approved_items = [item for item in approved_items if str(item.get("id") or "") in wanted]

    supported_scopes = {"boss_report", "market_report", "recovery_report"}
    executed_items: list[dict[str, object]] = []
    skipped_items: list[dict[str, object]] = []
    preview_paths: dict[str, str] = {}
    send_recommendation = ""
    next_focus = ""

    need_preview_regen = any(
        supported_scopes.intersection({str(scope).strip() for scope in (item.get("suggested_scope") or [])})
        for item in approved_items
    )

    if need_preview_regen:
        gate_result = run_self_check(
            report_date=report_date,
            meeting_name=meeting_name,
            output_dir=settings.active_output_dir,
        )
        audit_builder = ReportAuditBuilder(settings)
        audit_payload = audit_builder.audit_payload(
            report_date=report_date,
            meeting_name=meeting_name,
            self_check_result=gate_result,
        )
        audit_paths = audit_builder.build(
            report_date=report_date,
            meeting_name=meeting_name,
            self_check_result=gate_result,
        )
        pre_send_result = PreSendSummaryBuilder(settings).build(report_date=report_date)
        pre_send_payload = json.loads(pre_send_result.json_path.read_text(encoding="utf-8"))
        health_result = HealthCheckReportBuilder(settings).build(
            report_date=report_date,
            meeting_name=meeting_name,
            self_check_result=gate_result,
            audit_payload=audit_payload,
            pre_send_result=pre_send_result,
        )
        preview_paths = {
            "overview": str(gate_result.preview_paths.overview_markdown),
            "summary": str(gate_result.preview_paths.summary_markdown),
            "market": str(gate_result.preview_paths.market_markdown),
            "market_detail": str(gate_result.preview_paths.market_detail_markdown),
            "boss": str(gate_result.preview_paths.boss_markdown),
            "recovery": str(gate_result.preview_paths.recovery_markdown),
            "audit": str(audit_paths["summary"]),
            "health_check": str(health_result.markdown_path),
        }
        send_recommendation = str(pre_send_payload.get("send_recommendation") or "")
        focus_points = pre_send_payload.get("focus_points") or []
        if isinstance(focus_points, list) and focus_points:
            next_focus = str(focus_points[0] or "")

    for item in approved_items:
        scopes = {str(scope).strip() for scope in (item.get("suggested_scope") or []) if str(scope).strip()}
        request_id = str(item.get("id") or "")
        summary = str(item.get("request_summary") or "")
        if not supported_scopes.intersection(scopes):
            skipped_items.append(
                {
                    "id": request_id,
                    "summary": summary,
                    "reason": "scope_not_supported_yet",
                    "scopes": sorted(scopes),
                }
            )
            continue
        queue.append_note(
            request_id=request_id,
            note=f"已执行预览重生成，周窗口={report_date.isoformat()}，请先核对本地预览后再决定是否继续发布。",
        )
        updated = queue.update_status(
            request_id=request_id,
            status="done",
            note="状态更新为 已完成",
        )
        executed_items.append(
            {
                "id": request_id,
                "summary": summary,
                "scopes": sorted(scopes),
                "status": str((updated or item).get("status") or "done"),
            }
        )

    result_payload: dict[str, object] = {
        "report_date": report_date.isoformat(),
        "meeting_name": meeting_name,
        "chat_id": chat_id,
        "request_ids": sorted(wanted),
        "executed_count": len(executed_items),
        "skipped_count": len(skipped_items),
        "executed_items": executed_items,
        "skipped_items": skipped_items,
        "preview_paths": preview_paths,
        "send_recommendation": send_recommendation,
        "next_focus": next_focus,
    }
    json_path = settings.active_output_dir / "group_approved_execution_latest.json"
    md_path = settings.active_output_dir / "group_approved_execution_latest.md"
    json_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Group Approved Execution", ""]
    lines.append(f"- 周窗口：{report_date.isoformat()}")
    lines.append(f"- 已执行：{len(executed_items)}")
    lines.append(f"- 已跳过：{len(skipped_items)}")
    if send_recommendation:
        lines.append(f"- 当前发送建议：{send_recommendation}")
    if next_focus:
        lines.append(f"- 当前优先关注：{next_focus}")
    if preview_paths:
        lines.extend(["", "## 本地预览", ""])
        for name, path in preview_paths.items():
            lines.append(f"- {name}: {path}")
    if executed_items:
        lines.extend(["", "## 已执行", ""])
        for item in executed_items:
            lines.append(f"- {item['id']} | {item['summary']} | 状态={item['status']}")
    if skipped_items:
        lines.extend(["", "## 已跳过", ""])
        for item in skipped_items:
            lines.append(f"- {item['id']} | {item['summary']} | 原因={item['reason']}")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return result_payload, {"json": str(json_path), "markdown": str(md_path)}


def build_group_approved_execution_reply(result_payload: dict[str, object], output_paths: dict[str, str]) -> str:
    executed_count = int(result_payload.get("executed_count") or 0)
    skipped_count = int(result_payload.get("skipped_count") or 0)
    preview_paths = result_payload.get("preview_paths") or {}
    overview = str((preview_paths or {}).get("overview") or "")
    market = str((preview_paths or {}).get("market") or "")
    boss = str((preview_paths or {}).get("boss") or "")
    recovery = str((preview_paths or {}).get("recovery") or "")
    send_recommendation = str(result_payload.get("send_recommendation") or "")
    next_focus = str(result_payload.get("next_focus") or "")

    if executed_count == 0 and skipped_count == 0:
        lines = [
            "没有可执行的已批准任务：",
            "- 当前 approved 队列为空",
        ]
    else:
        lines = [
            "已批准任务执行完成：",
            f"- 已执行：{executed_count}",
            f"- 已跳过：{skipped_count}",
        ]
    if send_recommendation:
        lines.append(f"- 当前发送建议：{send_recommendation}")
    if next_focus:
        lines.append(f"- 当前优先关注：{next_focus}")
    if overview:
        lines.append(f"- 先看总览页：{overview}")
    if market:
        lines.append(f"- 市场版预览：{market}")
    if boss:
        lines.append(f"- 老板版预览：{boss}")
    if recovery:
        lines.append(f"- 回收版预览：{recovery}")
    lines.append(f"- 执行记录：{output_paths.get('markdown', '')}")
    return "\n".join(lines)
