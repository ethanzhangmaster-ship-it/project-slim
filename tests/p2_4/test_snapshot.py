"""P2.4.3 Snapshot Layer 测试：采集 / 降级 / strict / 失败 BLOCK / 落盘。"""

import json
from pathlib import Path

import pytest

from src.execution.models import ExecutionAction, ExecutionDomain, ExecutionIntent
from src.execution.safe_executor.snapshot import (
    InMemorySnapshotStore,
    JsonlSnapshotStore,
    SnapshotError,
    Snapshotter,
)
from tests.p2_4.conftest import BadSnapshotProvider


def _request_with_intent():
    intent = ExecutionIntent(
        intent_id="i", decision_id="d", domain=ExecutionDomain.UA,
        action=ExecutionAction.PAUSE_CAMPAIGN, target_id="p04", reason="r",
        confidence=0.8, risk_level=0.3,
    )
    req = type("R", (), {})()
    req.intent = intent
    return req


class TestInMemorySnapshotStore:
    def test_save_load(self):
        store = InMemorySnapshotStore()
        store.save("exe_1", {"a": 1})
        assert store.load("exe_1") == {"a": 1}

    def test_load_missing_none(self):
        store = InMemorySnapshotStore()
        assert store.load("nope") is None

    def test_save_copies(self):
        store = InMemorySnapshotStore()
        snap = {"a": 1}
        store.save("e", snap)
        snap["a"] = 99
        assert store.load("e") == {"a": 1}


class TestJsonlSnapshotStore:
    def test_save_load_roundtrip(self, tmp_path):
        store = JsonlSnapshotStore(str(tmp_path / "snaps"))
        store.save("exe_abc", {"network": "off"})
        loaded = store.load("exe_abc")
        assert loaded == {"network": "off"}

    def test_file_created(self, tmp_path):
        store = JsonlSnapshotStore(str(tmp_path / "snaps"))
        store.save("exe_abc", {})
        path = tmp_path / "snaps" / "exe_abc.json"
        assert path.exists()
        payload = json.loads(path.read_text())
        assert payload["snapshot"] == {}

    def test_invalid_execution_id_raises(self, tmp_path):
        store = JsonlSnapshotStore(str(tmp_path / "snaps"))
        # 过滤后不含任何 alnum/_- 字符 -> safe 为空 -> 抛 SnapshotError
        with pytest.raises(SnapshotError):
            store.save("///", {"x": 1})

    def test_load_missing_none(self, tmp_path):
        store = JsonlSnapshotStore(str(tmp_path / "snaps"))
        assert store.load("never") is None


class TestSnapshotter:
    def test_provider_snapshot_used(self):
        class P:
            provider_id = "max"

            def snapshot_state(self, request):
                return {"provider": "max", "state": "on"}

        store = InMemorySnapshotStore()
        snap = Snapshotter(store=store).take(P(), _request_with_intent(), "exe_1")
        assert snap == {"provider": "max", "state": "on"}
        assert store.load("exe_1") == snap

    def test_fallback_when_no_snapshot_state(self):
        class P:
            provider_id = "max"

        store = InMemorySnapshotStore()
        snap = Snapshotter(store=store, strict=False).take(
            P(), _request_with_intent(), "exe_2"
        )
        assert snap["fallback"] is True
        assert snap["provider"] == "max"
        assert snap["target_id"] == "p04"

    def test_strict_raises_when_no_snapshot_state(self):
        class P:
            provider_id = "max"

        store = InMemorySnapshotStore()
        with pytest.raises(SnapshotError):
            Snapshotter(store=store, strict=True).take(
                P(), _request_with_intent(), "exe_3"
            )

    def test_provider_snapshot_raising_raises(self):
        store = InMemorySnapshotStore()
        with pytest.raises(SnapshotError):
            Snapshotter(store=store).take(
                BadSnapshotProvider(), _request_with_intent(), "exe_4"
            )

    def test_non_dict_snapshot_raises(self):
        class P:
            provider_id = "max"

            def snapshot_state(self, request):
                return "not a dict"

        store = InMemorySnapshotStore()
        with pytest.raises(SnapshotError):
            Snapshotter(store=store).take(P(), _request_with_intent(), "exe_5")

    def test_store_persist_failure_wrapped(self):
        class BoomStore:
            def save(self, execution_id, snapshot):
                raise OSError("disk full")

            def load(self, execution_id):
                return None

        with pytest.raises(SnapshotError):
            Snapshotter(store=BoomStore()).take(
                _ProviderWithSnapshot(), _request_with_intent(), "exe_6"
            )

    def test_jsonl_persist_and_reload(self, tmp_path):
        store = JsonlSnapshotStore(str(tmp_path / "snaps"))
        snap = Snapshotter(store=store).take(
            _ProviderWithSnapshot(), _request_with_intent(), "exe_7"
        )
        assert store.load("exe_7") == snap


class _ProviderWithSnapshot:
    provider_id = "max"

    def snapshot_state(self, request):
        return {"captured": True}
