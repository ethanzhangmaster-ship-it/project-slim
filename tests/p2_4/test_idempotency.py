"""P2.4.2 Idempotency Layer 测试：幂等键归一化 + 五态裁决 + 存储。"""

import json
from pathlib import Path

import pytest

from src.execution.models import ExecutionAction
from src.execution.safe_executor.idempotency import (
    IDEM_FAILED,
    IDEM_ROLLED_BACK,
    IDEM_RUNNING,
    IDEM_SUCCESS,
    VERDICT_ALLOW,
    VERDICT_ALLOW_RETRY,
    VERDICT_BLOCK_ROLLED_BACK,
    VERDICT_REJECT_RUNNING,
    VERDICT_RETURN_EXISTING,
    IdempotencyRecord,
    InMemoryIdempotencyStore,
    JsonlIdempotencyStore,
    check_idempotency,
    make_idempotency_key,
    verdict_allows_execution,
)


class TestIdempotencyKey:
    def test_deterministic(self):
        k1 = make_idempotency_key("disable_network", "p04", {"budget": 100})
        k2 = make_idempotency_key("disable_network", "p04", {"budget": 100})
        assert k1 == k2
        assert k1.startswith("sha256:") or len(k1) == 64  # hex sha256

    def test_different_target_different_key(self):
        k1 = make_idempotency_key("disable_network", "p04", {"budget": 100})
        k2 = make_idempotency_key("disable_network", "p05", {"budget": 100})
        assert k1 != k2

    def test_param_order_canonical(self):
        k1 = make_idempotency_key("a", "t", {"x": 1, "y": 2})
        k2 = make_idempotency_key("a", "t", {"y": 2, "x": 1})
        assert k1 == k2

    def test_action_enum_normalized(self):
        k1 = make_idempotency_key(ExecutionAction.DISABLE_NETWORK, "p04", None)
        k2 = make_idempotency_key("disable_network", "p04", None)
        assert k1 == k2

    def test_none_params_equal_empty(self):
        k1 = make_idempotency_key("a", "t", None)
        k2 = make_idempotency_key("a", "t", {})
        assert k1 == k2

    def test_date_window_isolation(self):
        k1 = make_idempotency_key("a", "t", None, date_window="2026-07-29")
        k2 = make_idempotency_key("a", "t", None, date_window="2026-07-30")
        assert k1 != k2

    def test_default_window_is_utc_today(self):
        # 不指定 date_window 也能正常生成（不抛错）
        k = make_idempotency_key("a", "t", None)
        assert isinstance(k, str) and len(k) > 0


class TestIdempotencyVerdict:
    def test_absent_allows(self):
        store = InMemoryIdempotencyStore()
        verdict, rec = check_idempotency(store, "missing")
        assert verdict == VERDICT_ALLOW
        assert rec is None

    def test_running_rejects(self):
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_RUNNING))
        verdict, rec = check_idempotency(store, "k")
        assert verdict == VERDICT_REJECT_RUNNING
        assert rec.execution_id == "e1"

    def test_success_returns_existing(self):
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(
            key="k", execution_id="e1", status=IDEM_SUCCESS, result={"ok": 1}
        ))
        verdict, rec = check_idempotency(store, "k")
        assert verdict == VERDICT_RETURN_EXISTING
        assert rec.result == {"ok": 1}

    def test_failed_allows_retry(self):
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_FAILED))
        verdict, rec = check_idempotency(store, "k")
        assert verdict == VERDICT_ALLOW_RETRY

    def test_rolled_back_blocks(self):
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_ROLLED_BACK))
        verdict, rec = check_idempotency(store, "k")
        assert verdict == VERDICT_BLOCK_ROLLED_BACK

    def test_verdict_allows_execution(self):
        assert verdict_allows_execution(VERDICT_ALLOW)
        assert verdict_allows_execution(VERDICT_ALLOW_RETRY)
        assert not verdict_allows_execution(VERDICT_REJECT_RUNNING)
        assert not verdict_allows_execution(VERDICT_BLOCK_ROLLED_BACK)
        assert not verdict_allows_execution(VERDICT_RETURN_EXISTING)


class TestIdempotencyRecord:
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            IdempotencyRecord(key="k", execution_id="e", status="BOGUS")

    def test_defaults_timestamps(self):
        rec = IdempotencyRecord(key="k", execution_id="e", status=IDEM_SUCCESS)
        assert rec.created_at
        assert rec.updated_at
        assert rec.status == IDEM_SUCCESS

    def test_roundtrip(self):
        rec = IdempotencyRecord(
            key="k", execution_id="e", status=IDEM_SUCCESS, result={"a": 1}
        )
        restored = IdempotencyRecord.from_dict(rec.to_dict())
        assert restored.key == "k"
        assert restored.result == {"a": 1}
        assert restored.status == IDEM_SUCCESS


class TestInMemoryStore:
    def test_put_get(self):
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e", status=IDEM_RUNNING))
        assert store.get("k").execution_id == "e"
        assert store.get("absent") is None

    def test_put_updates_updated_at(self):
        store = InMemoryIdempotencyStore()
        r = IdempotencyRecord(key="k", execution_id="e", status=IDEM_RUNNING)
        store.put(r)
        first = r.updated_at
        store.put(IdempotencyRecord(key="k", execution_id="e2", status=IDEM_SUCCESS))
        got = store.get("k")
        assert got.execution_id == "e2"
        assert got.updated_at >= first


class TestJsonlStore:
    def test_put_get_last_wins(self, tmp_path):
        path = str(tmp_path / "idem.jsonl")
        store = JsonlIdempotencyStore(path)
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_RUNNING))
        store.put(IdempotencyRecord(key="k", execution_id="e2", status=IDEM_SUCCESS))
        got = store.get("k")
        assert got.execution_id == "e2"
        assert got.status == IDEM_SUCCESS

    def test_missing_key_returns_none(self, tmp_path):
        store = JsonlIdempotencyStore(str(tmp_path / "idem.jsonl"))
        assert store.get("nope") is None

    def test_append_only_file_created(self, tmp_path):
        path = tmp_path / "idem.jsonl"
        store = JsonlIdempotencyStore(str(path))
        assert path.exists()
        store.put(IdempotencyRecord(key="k", execution_id="e", status=IDEM_SUCCESS))
        lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        json.loads(lines[0])
