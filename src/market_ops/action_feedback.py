from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from market_ops.config import Settings
from market_ops.models import ActionItem
from market_ops.pipeline import DataRepository


@dataclass(slots=True)
class ActionFeedbackResult:
    markdown_path: Path
    json_path: Path
    passed: bool


class ActionFeedbackBuilder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._repo = DataRepository(settings)

    def build(self, report_date: date) -> ActionFeedbackResult:
        output_dir = self._settings.active_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = report_date.strftime("%Y%m%d")
        payload = self.build_payload(report_date)

        markdown_path = output_dir / f"action_feedback_{suffix}.md"
        json_path = output_dir / f"action_feedback_{suffix}.json"
        markdown_path.write_text(self._render_markdown(payload), encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return ActionFeedbackResult(markdown_path=markdown_path, json_path=json_path, passed=bool(payload["passed"]))

    def build_payload(self, report_date: date) -> dict[str, Any]:
        try:
            actions = self._repo.load_action_tracker()
        except Exception as exc:
            actions = []
            load_error = str(exc)
        else:
            load_error = ""

        feedback_items = [self._feedback_item(item, report_date) for item in actions]
        return {
            "report_date": report_date.isoformat(),
            "mode": "parallel_validation",
            "passed": True,
            "source": str(self._settings.action_tracker_csv or "configured action tracker"),
            "load_error": load_error,
            "summary": {
                "action_count": len(feedback_items),
                "success_count": sum(1 for item in feedback_items if item["success"] is True),
                "failed_count": sum(1 for item in feedback_items if item["success"] is False),
                "unknown_count": sum(1 for item in feedback_items if item["success"] is None),
            },
            "items": feedback_items,
        }

    @staticmethod
    def _feedback_item(item: ActionItem, report_date: date) -> dict[str, Any]:
        status = str(item.status or "")
        latest_note = str(item.latest_note or "")
        success = _infer_success(status, latest_note)
        return {
            "action_id": item.task_id,
            "source_meeting": item.source_meeting,
            "action": item.action_type,
            "target": item.title,
            "owner": item.owner,
            "expected_result": {
                "acceptance_metric": item.acceptance_metric,
                "due_date": item.due_date.isoformat() if item.due_date else "",
            },
            "actual_result": {
                "status": status,
                "latest_note": latest_note,
                "as_of_date": report_date.isoformat(),
            },
            "success": success,
            "failure_reason": _infer_failure_reason(status, latest_note),
            "raw_action": _json_safe_action(item),
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        lines = [
            f"# V2.5 动作反馈记录 | {payload['report_date']}",
            "",
            f"- 动作数：{summary['action_count']}；成功：{summary['success_count']}；失败：{summary['failed_count']}；未定：{summary['unknown_count']}。",
            "- 作用：记录历史动作结果，供后续决策权重调整；当前不自动改写模型权重。",
            "",
        ]
        if payload.get("load_error"):
            lines.extend(["## 读取提示", "", f"- {payload['load_error']}", ""])
        lines.extend(["## 反馈明细", ""])
        if not payload["items"]:
            lines.append("- 暂无动作记录。")
        for item in payload["items"][:30]:
            success_text = "成功" if item["success"] is True else ("失败" if item["success"] is False else "未定")
            reason = "；".join(item["failure_reason"]) if item["failure_reason"] else "无"
            lines.append(f"- {item['action_id']} | {item['action']} | {success_text} | {item['target']} | 原因：{reason}")
        lines.append("")
        return "\n".join(lines)


def _infer_success(status: str, note: str) -> bool | None:
    text = f"{status} {note}"
    if any(token in text for token in ("完成", "达成", "成功", "通过", "ROI提升", "回升")):
        return True
    if any(token in text for token in ("失败", "未达", "下降", "恶化", "爆炸", "回滚")):
        return False
    return None


def _infer_failure_reason(status: str, note: str) -> list[str]:
    text = f"{status} {note}"
    reasons: list[str] = []
    if any(token in text for token in ("素材疲劳", "CTR下降", "CTR 下降")):
        reasons.append("素材疲劳或 CTR 下滑")
    if any(token in text for token in ("CPI上升", "CPI 上升", "成本上升")):
        reasons.append("成本上升")
    if any(token in text for token in ("ROI下降", "ROI 下降", "ROAS下降", "ROAS 下降")):
        reasons.append("ROI/ROAS 下滑")
    if any(token in text for token in ("归因", "零收入", "数据")):
        reasons.append("数据或归因问题")
    return reasons


def _json_safe_action(item: ActionItem) -> dict[str, Any]:
    payload = asdict(item)
    for key, value in list(payload.items()):
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload
