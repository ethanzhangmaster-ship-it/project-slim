"""P2.3.5 Approval Store.

Append-only JSONL persistence for ApprovalRequest records, following the
EP0 audit-trail discipline: history is never mutated; a resolution is a NEW
line with the updated status. The latest line for an approval_id wins.

Also tracks executed approval_ids (Rule 4: one approval -> one execution)
via a separate append-only file.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from src.execution.approval.models import (
    ApprovalRequest,
    STATUS_PENDING,
    VALID_STATUSES,
    _now_iso,
)

DEFAULT_APPROVALS_PATH = os.path.join("data", "execution", "approvals.jsonl")
DEFAULT_EXECUTED_PATH = os.path.join("data", "execution", "approvals_executed.jsonl")


class InMemoryApprovalStore:
    """Volatile store for tests and simulation."""

    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRequest] = {}
        self._executed: set = set()

    # -- write -------------------------------------------------------------

    def save(self, request: ApprovalRequest) -> ApprovalRequest:
        self._records[request.approval_id] = request
        return request

    def resolve(
        self,
        approval_id: str,
        status: str,
        resolved_by: str = "",
        reason: str = "",
    ) -> Optional[ApprovalRequest]:
        if status not in VALID_STATUSES or status == STATUS_PENDING:
            raise ValueError(f"invalid resolution status: {status}")
        current = self._records.get(approval_id)
        if current is None or not current.is_pending:
            return None
        updated = ApprovalRequest.from_dict(current.to_dict())
        updated.status = status
        updated.resolved_at = _now_iso()
        updated.resolved_by = resolved_by
        if reason:
            updated.reason = reason
        self._records[approval_id] = updated
        return updated

    def mark_executed(self, approval_id: str) -> bool:
        """Returns True if this is the FIRST execution (Rule 4)."""
        if approval_id in self._executed:
            return False
        self._executed.add(approval_id)
        return True

    # -- read --------------------------------------------------------------

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._records.get(approval_id)

    def pending(self) -> List[ApprovalRequest]:
        return [r for r in self._records.values() if r.is_pending]

    def was_executed(self, approval_id: str) -> bool:
        return approval_id in self._executed


class JsonlApprovalStore:
    """Durable append-only store at data/execution/approvals.jsonl."""

    def __init__(
        self,
        path: str = DEFAULT_APPROVALS_PATH,
        executed_path: str = DEFAULT_EXECUTED_PATH,
    ) -> None:
        self.path = path
        self.executed_path = executed_path

    # -- low-level ---------------------------------------------------------

    def _append(self, path: str, record: Dict) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _read_all(self) -> List[Dict]:
        if not os.path.exists(self.path):
            return []
        records: List[Dict] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def _latest_by_id(self) -> Dict[str, ApprovalRequest]:
        latest: Dict[str, ApprovalRequest] = {}
        for raw in self._read_all():
            try:
                request = ApprovalRequest.from_dict(raw)
            except (ValueError, TypeError):
                continue
            latest[request.approval_id] = request
        return latest

    # -- write -------------------------------------------------------------

    def save(self, request: ApprovalRequest) -> ApprovalRequest:
        self._append(self.path, request.to_dict())
        return request

    def resolve(
        self,
        approval_id: str,
        status: str,
        resolved_by: str = "",
        reason: str = "",
    ) -> Optional[ApprovalRequest]:
        if status not in VALID_STATUSES or status == STATUS_PENDING:
            raise ValueError(f"invalid resolution status: {status}")
        current = self.get(approval_id)
        if current is None or not current.is_pending:
            return None
        updated = ApprovalRequest.from_dict(current.to_dict())
        updated.status = status
        updated.resolved_at = _now_iso()
        updated.resolved_by = resolved_by
        if reason:
            updated.reason = reason
        # append-only: resolution is a new line, history preserved
        self._append(self.path, updated.to_dict())
        return updated

    def mark_executed(self, approval_id: str) -> bool:
        if self.was_executed(approval_id):
            return False
        self._append(
            self.executed_path,
            {"approval_id": approval_id, "executed_at": _now_iso()},
        )
        return True

    # -- read --------------------------------------------------------------

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._latest_by_id().get(approval_id)

    def pending(self) -> List[ApprovalRequest]:
        return [r for r in self._latest_by_id().values() if r.is_pending]

    def was_executed(self, approval_id: str) -> bool:
        if not os.path.exists(self.executed_path):
            return False
        with open(self.executed_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("approval_id") == approval_id:
                    return True
        return False
