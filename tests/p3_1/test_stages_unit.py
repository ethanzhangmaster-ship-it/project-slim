"""P3.1 — 执行/监控/恢复三段胶水的单元测试（stub 注入，不跑全链）。"""
from __future__ import annotations

from typing import Any, List

from src.execution.safe_executor.models import (
    VERDICT_BLOCKED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
)
from src.operator.context import OperatorContext
from src.operator.models import (
    STAGE_EXECUTIONS,
    STAGE_MONITOR,
    STAGE_OK,
    STAGE_RECOVERY,
    STAGE_SKIPPED,
)
from src.operator.pipeline import DailyOperatorPipeline


# --------------------------------------------------------------------------- #
# stubs（鸭子类型，仅覆盖 pipeline 用到的属性）
# --------------------------------------------------------------------------- #
class StubResult:
    def __init__(self, real_api_called=False):
        self.real_api_called = real_api_called


class StubOutcome:
    def __init__(self, verdict: str, real_api=False):
        self.verdict = verdict
        self.result = StubResult(real_api)

    @property
    def ok(self) -> bool:
        return self.verdict in (VERDICT_EXECUTED, "RETURN_EXISTING")


class StubSafeExecutor:
    def __init__(self, outcomes: List[StubOutcome]):
        self._outcomes = list(outcomes)
        self.calls: List[Any] = []

    def execute(self, request):
        self.calls.append(request)
        return self._outcomes.pop(0)


class StubMonitor:
    def __init__(self):
        self.batches = []

    def observe_batch(self, paired, date=""):
        self.batches.append((paired, date))

        class R:
            health_level = "GREEN"
            warnings: List[str] = []
            report_id = "edr_stub"
        return [object()] * len(paired), R()


class StubRecovery:
    def __init__(self):
        self.handled = []

    def handle(self, outcome, request, alert=None, expected_state=None):
        self.handled.append((outcome, request))

        class R:
            status = "recovered"
            incident_id = "inc_stub"
        return R()


def _ctx(tmp_path, safe_executor=None, monitor=None, recovery=None):
    return OperatorContext(
        agent=object(),
        auditor=object(),
        registry=object(),
        approval_service=object(),
        safe_executor=safe_executor or StubSafeExecutor([]),
        monitor=monitor or StubMonitor(),
        recovery=recovery or StubRecovery(),
        out_dir=str(tmp_path / "out"),
    )


# --------------------------------------------------------------------------- #
class TestExecutionsStage:
    def test_skipped_when_nothing_authorized(self, tmp_path):
        pipe = DailyOperatorPipeline(_ctx(tmp_path))
        s = {"executable": [], "paired": []}
        r = pipe._executions("2026-07-30", s, "op-1")
        assert r.status == STAGE_SKIPPED

    def test_counts_ok_blocked_failed(self, tmp_path):
        execu = StubSafeExecutor([
            StubOutcome(VERDICT_EXECUTED),
            StubOutcome(VERDICT_BLOCKED),
            StubOutcome(VERDICT_FAILED),
        ])
        pipe = DailyOperatorPipeline(_ctx(tmp_path, safe_executor=execu))
        s = {"executable": ["r1", "r2", "r3"], "paired": []}
        r = pipe._executions("2026-07-30", s, "op-1")
        assert r.status == STAGE_OK
        assert r.payload["ok"] == 1
        assert r.payload["blocked"] == 1
        assert r.payload["failed"] == 1
        assert len(execu.calls) == 3
        assert len(s["paired"]) == 3

    def test_real_api_flag_propagated(self, tmp_path):
        execu = StubSafeExecutor([StubOutcome(VERDICT_EXECUTED, real_api=True)])
        pipe = DailyOperatorPipeline(_ctx(tmp_path, safe_executor=execu))
        s = {"executable": ["r1"], "paired": []}
        r = pipe._executions("2026-07-30", s, "op-1")
        assert r.payload["real_api_called"] is True


class TestMonitorStage:
    def test_skipped_without_outcomes(self, tmp_path):
        pipe = DailyOperatorPipeline(_ctx(tmp_path))
        r = pipe._monitor("2026-07-30", {"paired": []}, "op-1")
        assert r.status == STAGE_SKIPPED

    def test_observe_batch_called(self, tmp_path):
        mon = StubMonitor()
        pipe = DailyOperatorPipeline(_ctx(tmp_path, monitor=mon))
        paired = [("req", StubOutcome(VERDICT_EXECUTED))]
        s = {"paired": paired}
        r = pipe._monitor("2026-07-30", s, "op-1")
        assert r.status == STAGE_OK
        assert r.payload["observed"] == 1
        assert mon.batches[0][1] == "2026-07-30"
        assert s["exec_report"] is not None


class TestRecoveryStage:
    def test_skipped_when_all_ok(self, tmp_path):
        rec = StubRecovery()
        pipe = DailyOperatorPipeline(_ctx(tmp_path, recovery=rec))
        s = {"paired": [("r", StubOutcome(VERDICT_EXECUTED))], "recoveries": []}
        r = pipe._recovery("2026-07-30", s, "op-1")
        assert r.status == STAGE_SKIPPED
        assert rec.handled == []

    def test_blocked_not_treated_as_failure(self, tmp_path):
        """BLOCKED 是拦截不是失败 —— 不进恢复（P2.6 语义）。"""
        rec = StubRecovery()
        pipe = DailyOperatorPipeline(_ctx(tmp_path, recovery=rec))
        s = {"paired": [("r", StubOutcome(VERDICT_BLOCKED))], "recoveries": []}
        r = pipe._recovery("2026-07-30", s, "op-1")
        assert r.status == STAGE_SKIPPED
        assert rec.handled == []

    def test_failed_outcome_handled(self, tmp_path):
        rec = StubRecovery()
        pipe = DailyOperatorPipeline(_ctx(tmp_path, recovery=rec))
        s = {
            "paired": [
                ("r1", StubOutcome(VERDICT_EXECUTED)),
                ("r2", StubOutcome(VERDICT_FAILED)),
            ],
            "recoveries": [],
        }
        r = pipe._recovery("2026-07-30", s, "op-1")
        assert r.status == STAGE_OK
        assert r.payload["incidents"] == 1
        assert r.payload["recovered"] == 1
        assert len(rec.handled) == 1
        assert rec.handled[0][1] == "r2"
