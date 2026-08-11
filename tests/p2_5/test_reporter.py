"""P2.5.6 — Execution Daily Report 验收。"""

from src.execution.monitor.anomaly import AnomalyDetector
from src.execution.monitor.collector import ExecutionEventCollector
from src.execution.monitor.reporter import ExecutionDailyReport, ExecutionReporter
from src.execution.safe_executor.models import (
    VERDICT_BLOCKED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_ROLLED_BACK,
)
from tests.p2_5.conftest import make_outcome


def _outs(n_exec, n_fail, n_rollback, n_block):
    return (
        [make_outcome(VERDICT_EXECUTED) for _ in range(n_exec)]
        + [make_outcome(VERDICT_FAILED) for _ in range(n_fail)]
        + [make_outcome(VERDICT_ROLLED_BACK) for _ in range(n_rollback)]
        + [make_outcome(VERDICT_BLOCKED) for _ in range(n_block)]
    )


def test_report_counts():
    outs = _outs(7, 2, 1, 1)
    rep = ExecutionReporter().build("2026-07-30", outs)
    assert rep.total_executions == 11
    assert rep.success == 7
    assert rep.failed == 2
    assert rep.rollback == 1
    assert rep.blocked == 1


def test_report_provider_distribution():
    outs = [
        make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=3.0),
        make_outcome(VERDICT_EXECUTED, provider="meta", latency_seconds=15.0),
        make_outcome(VERDICT_EXECUTED, provider="max", latency_seconds=4.0),
    ]
    rep = ExecutionReporter().build("2026-07-30", outs)
    assert rep.providers.get("max") == 2
    assert rep.providers.get("meta") == 1


def test_report_warnings_from_anomalies():
    outs = _outs(8, 2, 0, 0)  # 失败率 20%
    summaries = [ExecutionEventCollector().summarize(None, o) for o in outs]
    anomalies = AnomalyDetector().analyze(summaries)
    rep = ExecutionReporter().build("2026-07-30", outs, anomalies=anomalies)
    assert len(rep.warnings) >= 1
    assert any("FAILURE_RATE_HIGH" in w for w in rep.warnings)


def test_report_learnings():
    outs = _outs(5, 0, 0, 0)
    rep = ExecutionReporter().build(
        "2026-07-30", outs, learnings=["动作 update_waterfall 真实成功率 100%"]
    )
    assert "真实成功率" in rep.learnings[0]


def test_report_markdown_contains_keys():
    outs = _outs(3, 1, 0, 0)
    rep = ExecutionReporter().build("2026-07-30", outs, health_level="GREEN")
    md = rep.to_markdown()
    assert "Execution Daily Report" in md
    assert "2026-07-30" in md
    assert "GREEN" in md
    assert "执行 **4**" in md


def test_report_roundtrip_dict():
    outs = _outs(2, 0, 0, 0)
    rep = ExecutionReporter().build("2026-07-30", outs)
    d = rep.to_dict()
    assert d["date"] == "2026-07-30"
    assert d["success"] == 2
    assert "report_id" in d


def test_report_dataclass_default_id():
    rep = ExecutionDailyReport(date="2026-07-30")
    assert rep.report_id.startswith("edr_")
