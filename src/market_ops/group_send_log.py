from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(slots=True)
class GroupSendLogEntry:
    created_at: str
    chat_id: str
    message_id: str
    route: str
    report_date: str
    meeting_name: str
    gate_passed: bool
    status: str
    sent_items: list[str]
    overview_path: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "route": self.route,
            "report_date": self.report_date,
            "meeting_name": self.meeting_name,
            "gate_passed": self.gate_passed,
            "status": self.status,
            "sent_items": list(self.sent_items),
            "overview_path": self.overview_path,
            "detail": self.detail,
        }


class GroupSendLog:
    def __init__(self, active_output_dir: Path) -> None:
        self._json_path = active_output_dir / "group_send_log_latest.json"
        self._md_path = active_output_dir / "group_send_log_latest.md"
        self._lock = Lock()

    def append(
        self,
        *,
        chat_id: str,
        message_id: str,
        route: str,
        report_date: str,
        meeting_name: str,
        gate_passed: bool,
        status: str,
        sent_items: list[str],
        overview_path: str,
        detail: str,
    ) -> dict[str, Path]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = GroupSendLogEntry(
            created_at=now,
            chat_id=chat_id,
            message_id=message_id,
            route=route,
            report_date=report_date,
            meeting_name=meeting_name,
            gate_passed=gate_passed,
            status=status,
            sent_items=sent_items,
            overview_path=overview_path,
            detail=detail,
        )
        with self._lock:
            payload = self._load_payload()
            items = payload.get("items") or []
            items.insert(0, entry.as_dict())
            payload["items"] = items[:200]
            payload["updated_at"] = now
            self._write_payload(payload)
        return {"json": self._json_path, "markdown": self._md_path}

    def latest(self, *, chat_id: str = "", limit: int = 10) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = payload.get("items") or []
        if chat_id:
            items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
        return items[: max(1, limit)]

    def build_latest_reply(self, *, chat_id: str, limit: int = 3) -> str:
        items = self.latest(chat_id=chat_id, limit=limit)
        if not items:
            return "当前还没有发送记录。"
        lines = ["最近发送记录："]
        for item in items:
            sent_items = "/".join(item.get("sent_items") or []) or "无"
            lines.append(
                f"- {item.get('created_at')} | {item.get('status')} | {item.get('route')} | {sent_items}"
            )
        return "\n".join(lines)

    def cleanup_test_entries(self) -> dict[str, int]:
        with self._lock:
            payload = self._load_payload()
            items = payload.get("items") or []
            before = len(items)
            cleaned = [
                item
                for item in items
                if not self._looks_like_test_entry(item)
            ]
            payload["items"] = cleaned
            payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._write_payload(payload)
        return {"before": before, "after": len(cleaned), "removed": before - len(cleaned)}

    def _load_payload(self) -> dict[str, Any]:
        if not self._json_path.exists():
            return {"items": [], "updated_at": ""}
        try:
            payload = json.loads(self._json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": [], "updated_at": ""}
        if not isinstance(payload, dict):
            return {"items": [], "updated_at": ""}
        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = ["# Group Send Log", ""]
        for item in payload.get("items") or []:
            sent_items = ", ".join(item.get("sent_items") or []) or "无"
            lines.append(f"## {item.get('created_at')}")
            lines.append(f"- 群：{item.get('chat_id')}")
            lines.append(f"- 消息：{item.get('message_id')}")
            lines.append(f"- 路由：{item.get('route')}")
            lines.append(f"- 周窗口：{item.get('report_date')}")
            lines.append(f"- 门禁通过：{item.get('gate_passed')}")
            lines.append(f"- 状态：{item.get('status')}")
            lines.append(f"- 发送项目：{sent_items}")
            if item.get("overview_path"):
                lines.append(f"- 总览页：{item.get('overview_path')}")
            if item.get("detail"):
                lines.append(f"- 说明：{item.get('detail')}")
            lines.append("")
        self._md_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _looks_like_test_entry(item: dict[str, Any]) -> bool:
        chat_id = str(item.get("chat_id") or "")
        message_id = str(item.get("message_id") or "")
        detail = str(item.get("detail") or "")
        return (
            chat_id == "oc_test_group"
            or message_id.startswith("om_test_")
            or detail in {"test-detail", "?????????????"}
        )
