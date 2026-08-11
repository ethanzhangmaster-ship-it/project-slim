"""P3.1 — OperatorRunStore（防重复运行守卫）测试。"""
from __future__ import annotations

from src.operator.models import OperatorRunResult, RunStatus
from src.operator.state import OperatorRunStore

D = "2026-07-30"


def _res(date=D, status=RunStatus.COMPLETED, run_id="op-x-1"):
    return OperatorRunResult(run_id=run_id, date=date, status=status)


class TestOperatorRunStore:
    def test_empty(self, run_store: OperatorRunStore):
        assert run_store.get(D) is None
        assert not run_store.has_completed(D)
        assert run_store.runs_on(D) == 0
        assert run_store.history() == []

    def test_record_and_get(self, run_store):
        run_store.record(_res())
        row = run_store.get(D)
        assert row is not None
        assert row["status"] == "completed"

    def test_latest_wins(self, run_store):
        run_store.record(_res(run_id="op-1", status=RunStatus.FAILED))
        run_store.record(_res(run_id="op-2", status=RunStatus.COMPLETED))
        assert run_store.get(D)["run_id"] == "op-2"

    def test_has_completed_semantics(self, run_store):
        run_store.record(_res(status=RunStatus.FAILED))
        assert not run_store.has_completed(D)  # FAILED 可重跑
        run_store.record(_res(status=RunStatus.PARTIAL))
        assert run_store.has_completed(D)      # PARTIAL 视为已完成
        run_store.record(_res(status=RunStatus.COMPLETED))
        assert run_store.has_completed(D)

    def test_skipped_not_completed(self, run_store):
        run_store.record(_res(status=RunStatus.SKIPPED))
        assert not run_store.has_completed(D)

    def test_runs_on_counts_all(self, run_store):
        run_store.record(_res(status=RunStatus.FAILED))
        run_store.record(_res(status=RunStatus.COMPLETED))
        run_store.record(_res(date="2026-07-31"))
        assert run_store.runs_on(D) == 2

    def test_history_dedup_sorted(self, run_store):
        run_store.record(_res(date="2026-07-31", run_id="b"))
        run_store.record(_res(date=D, run_id="a1"))
        run_store.record(_res(date=D, run_id="a2"))
        rows = run_store.history()
        assert [r["date"] for r in rows] == [D, "2026-07-31"]
        assert rows[0]["run_id"] == "a2"  # 同日取最后一条

    def test_bad_line_tolerated(self, run_store):
        run_store.record(_res())
        with run_store.path.open("a", encoding="utf-8") as f:
            f.write("{not valid json\n")
        run_store.record(_res(run_id="op-after"))
        assert run_store.get(D)["run_id"] == "op-after"
        assert run_store.runs_on(D) == 2
