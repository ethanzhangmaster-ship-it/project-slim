from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(slots=True)
class GroupRequirementRecord:
    id: str
    created_at: str
    chat_id: str
    user_text: str
    intent_type: str
    request_summary: str
    suggested_scope: list[str]
    risk_level: str
    requires_manual_confirmation: bool
    status: str
    notes: list[str] | None = None
    normalized_brief: str = ""
    suggested_action: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "chat_id": self.chat_id,
            "user_text": self.user_text,
            "intent_type": self.intent_type,
            "request_summary": self.request_summary,
            "suggested_scope": list(self.suggested_scope),
            "risk_level": self.risk_level,
            "requires_manual_confirmation": self.requires_manual_confirmation,
            "status": self.status,
            "notes": list(self.notes or []),
            "normalized_brief": self.normalized_brief,
            "suggested_action": self.suggested_action,
        }


class GroupRequirementsQueue:
    _OPEN_STATUSES = {"new", "confirmed", "in_progress", "approved"}

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()

    def append(
        self,
        *,
        chat_id: str,
        user_text: str,
        request_summary: str,
        suggested_scope: list[str],
        risk_level: str,
        normalized_brief: str = "",
        suggested_action: str = "",
        requires_manual_confirmation: bool = True,
    ) -> GroupRequirementRecord:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            payload = self._load_payload()
            next_index = len(payload["items"]) + 1
            record = GroupRequirementRecord(
                id=f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{next_index:03d}",
                created_at=now,
                chat_id=chat_id,
                user_text=user_text,
                intent_type="change_request",
                request_summary=request_summary,
                suggested_scope=suggested_scope,
                risk_level=risk_level,
                requires_manual_confirmation=requires_manual_confirmation,
                status="new",
                normalized_brief=normalized_brief,
                suggested_action=suggested_action,
            )
            payload["items"].append(record.as_dict())
            payload["updated_at"] = now
            self._write_payload(payload)
        return record

    def latest(self, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = payload.get("items") or []
        return list(reversed(items[-max(1, limit) :]))

    def latest_for_chat(self, chat_id: str, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = [item for item in (payload.get("items") or []) if str(item.get("chat_id") or "") == chat_id]
        return list(reversed(items[-max(1, limit) :]))

    def latest_open_for_chat(self, chat_id: str) -> dict[str, Any] | None:
        items = self.latest_for_chat(chat_id, limit=50)
        for item in items:
            status = str(item.get("status") or "").strip().lower()
            if status in self._OPEN_STATUSES:
                return item
        return None

    def latest_open_list_for_chat(self, chat_id: str, limit: int = 20) -> list[dict[str, Any]]:
        items = self.latest_for_chat(chat_id, limit=max(1, limit * 5))
        open_items: list[dict[str, Any]] = []
        for item in items:
            status = str(item.get("status") or "").strip().lower()
            if status not in self._OPEN_STATUSES:
                continue
            open_items.append(item)
            if len(open_items) >= max(1, limit):
                break
        return open_items

    def append_note(self, *, request_id: str, note: str) -> dict[str, Any] | None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            payload = self._load_payload()
            items = payload.get("items") or []
            for item in items:
                if str(item.get("id") or "") != request_id:
                    continue
                notes = item.get("notes")
                if not isinstance(notes, list):
                    notes = []
                notes.append(f"{now} | {note}")
                item["notes"] = notes
                item["updated_at"] = now
                payload["updated_at"] = now
                self._write_payload(payload)
                return item
        return None

    def get(self, request_id: str) -> dict[str, Any] | None:
        payload = self._load_payload()
        for item in (payload.get("items") or []):
            if str(item.get("id") or "") == request_id:
                return item
        return None

    def list_by_status(self, *, chat_id: str = "", statuses: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = payload.get("items") or []
        if chat_id:
            items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
        if statuses:
            wanted = {status.strip().lower() for status in statuses if status.strip()}
            items = [item for item in items if str(item.get("status") or "").strip().lower() in wanted]
        return list(reversed(items[-max(1, limit) :]))

    def status_counts(self, *, chat_id: str = "") -> dict[str, int]:
        payload = self._load_payload()
        items = payload.get("items") or []
        if chat_id:
            items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
        counts: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "unknown").strip().lower() or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def update_status(self, *, request_id: str, status: str, note: str = "") -> dict[str, Any] | None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            payload = self._load_payload()
            items = payload.get("items") or []
            for item in items:
                if str(item.get("id") or "") != request_id:
                    continue
                item["status"] = status
                item["updated_at"] = now
                notes = item.get("notes")
                if not isinstance(notes, list):
                    notes = []
                if note:
                    notes.append(f"{now} | {note}")
                item["notes"] = notes
                payload["updated_at"] = now
                self._write_payload(payload)
                return item
        return None

    def list_by_scope(self, *, chat_id: str = "", scopes: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = payload.get("items") or []
        if chat_id:
            items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
        if scopes:
            wanted = {scope.strip() for scope in scopes if scope.strip()}
            items = [
                item
                for item in items
                if any(str(scope).strip() in wanted for scope in (item.get("suggested_scope") or []))
            ]
        return list(reversed(items[-max(1, limit) :]))

    def list_by_risk(self, *, chat_id: str = "", risk_levels: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._load_payload()
        items = payload.get("items") or []
        if chat_id:
            items = [item for item in items if str(item.get("chat_id") or "") == chat_id]
        if risk_levels:
            wanted = {level.strip().lower() for level in risk_levels if level.strip()}
            items = [item for item in items if str(item.get("risk_level") or "").strip().lower() in wanted]
        return list(reversed(items[-max(1, limit) :]))

    def _load_payload(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"items": [], "updated_at": ""}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": [], "updated_at": ""}
        if not isinstance(payload, dict):
            return {"items": [], "updated_at": ""}
        items = payload.get("items")
        if not isinstance(items, list):
            payload["items"] = []
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
