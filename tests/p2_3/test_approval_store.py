"""P2.3.5 store tests — append-only JSONL + in-memory 双实现同契约。"""

import json

import pytest

from src.execution.approval.models import (
    ApprovalRequest,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from src.execution.approval.store import InMemoryApprovalStore, JsonlApprovalStore


def _request(action="pause_campaign"):
    return ApprovalRequest(
        execution_request_id="req_1",
        intent_id="int_1",
        action=action,
        domain="ua",
        target="p04",
    )


@pytest.fixture(params=["memory", "jsonl"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryApprovalStore()
    return JsonlApprovalStore(
        path=str(tmp_path / "approvals.jsonl"),
        executed_path=str(tmp_path / "executed.jsonl"),
    )


class TestStoreContract:
    def test_save_and_get(self, store):
        req = _request()
        store.save(req)
        loaded = store.get(req.approval_id)
        assert loaded is not None
        assert loaded.approval_id == req.approval_id
        assert loaded.status == STATUS_PENDING

    def test_get_missing_returns_none(self, store):
        assert store.get("apr_missing") is None

    def test_pending_lists_only_pending(self, store):
        a, b = _request(), _request()
        store.save(a)
        store.save(b)
        store.resolve(a.approval_id, STATUS_APPROVED, resolved_by="ethan")
        pending_ids = {r.approval_id for r in store.pending()}
        assert pending_ids == {b.approval_id}

    def test_resolve_sets_status_and_resolver(self, store):
        req = _request()
        store.save(req)
        resolved = store.resolve(
            req.approval_id, STATUS_REJECTED, resolved_by="ethan", reason="too risky"
        )
        assert resolved is not None
        assert resolved.status == STATUS_REJECTED
        assert resolved.resolved_by == "ethan"
        assert resolved.resolved_at
        assert resolved.reason == "too risky"

    def test_resolve_non_pending_returns_none(self, store):
        req = _request()
        store.save(req)
        store.resolve(req.approval_id, STATUS_APPROVED, resolved_by="ethan")
        # 二次 resolve 已非 PENDING
        assert store.resolve(req.approval_id, STATUS_REJECTED) is None

    def test_resolve_invalid_status_raises(self, store):
        req = _request()
        store.save(req)
        with pytest.raises(ValueError):
            store.resolve(req.approval_id, STATUS_PENDING)
        with pytest.raises(ValueError):
            store.resolve(req.approval_id, "NOT_A_STATUS")

    def test_mark_executed_single_use(self, store):
        req = _request()
        store.save(req)
        assert store.mark_executed(req.approval_id) is True
        assert store.mark_executed(req.approval_id) is False  # Rule 4
        assert store.was_executed(req.approval_id)
        assert not store.was_executed("apr_other")


class TestJsonlAppendOnly:
    def test_resolution_appends_new_line_history_preserved(self, tmp_path):
        path = tmp_path / "approvals.jsonl"
        store = JsonlApprovalStore(
            path=str(path), executed_path=str(tmp_path / "executed.jsonl")
        )
        req = _request()
        store.save(req)
        store.resolve(req.approval_id, STATUS_APPROVED, resolved_by="ethan")

        lines = [
            json.loads(l)
            for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        # append-only：两行同 approval_id，第一行 PENDING 历史保留
        assert len(lines) == 2
        assert lines[0]["status"] == STATUS_PENDING
        assert lines[1]["status"] == STATUS_APPROVED
        # latest wins
        assert store.get(req.approval_id).status == STATUS_APPROVED

    def test_survives_reload(self, tmp_path):
        path = str(tmp_path / "approvals.jsonl")
        executed = str(tmp_path / "executed.jsonl")
        store1 = JsonlApprovalStore(path=path, executed_path=executed)
        req = _request()
        store1.save(req)
        store1.mark_executed(req.approval_id)

        store2 = JsonlApprovalStore(path=path, executed_path=executed)
        assert store2.get(req.approval_id) is not None
        assert store2.was_executed(req.approval_id)
        assert store2.mark_executed(req.approval_id) is False

    def test_corrupt_lines_skipped(self, tmp_path):
        path = tmp_path / "approvals.jsonl"
        store = JsonlApprovalStore(
            path=str(path), executed_path=str(tmp_path / "executed.jsonl")
        )
        req = _request()
        store.save(req)
        with open(path, "a", encoding="utf-8") as f:
            f.write("{not json}\n")
        assert store.get(req.approval_id) is not None
        assert len(store.pending()) == 1
