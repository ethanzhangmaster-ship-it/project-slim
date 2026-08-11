"""P2.5.5 — Anomaly Detector（Rule1~4）验收。"""

from src.execution.monitor.anomaly import (
    AnomalyDetector,
    AnomalyReport,
    FAILURE_RATE_RED,
    ROLLBACK_RATE_WARNING,
    ACTION_LOOP_THRESHOLD,
)
from src.execution.monitor.collector import ExecutionEventCollector
from src.execution.monitor.models import (
    SEVERITY_ALERT,
    SEVERITY_BLOCK,
    SEVERITY_RED,
    SEVERITY_WARNING,
)
from src.execution.safe_executor.models import (
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_ROLLED_BACK,
)
from tests.p2_5.conftest import make_outcome, make_request


def _summaries(outcomes):
    c = ExecutionEventCollector()
    return [c.summarize(None, o) for o in outcomes]


def test_rule1_failure_rate_red():
    outs = ([make_outcome(VERDICT_EXECUTED) for _ in range(8)]
            + [make_outcome(VERDICT_FAILED) for _ in range(2)])
    report = AnomalyDetector().analyze(_summaries(outs))
    codes = {f.code for f in report.findings}
    assert "FAILURE_RATE_HIGH" in codes
    sev = {f.severity for f in report.findings if f.code == "FAILURE_RATE_HIGH"}
    assert SEVERITY_RED in sev
    assert FAILURE_RATE_RED == 0.10


def test_rule1_boundary_not_triggered():
    # 恰好 10% 失败（1/10）不应触发（严格 >）
    outs = ([make_outcome(VERDICT_EXECUTED) for _ in range(9)]
            + [make_outcome(VERDICT_FAILED) for _ in range(1)])
    report = AnomalyDetector().analyze(_summaries(outs))
    assert "FAILURE_RATE_HIGH" not in {f.code for f in report.findings}


def test_rule2_rollback_rate_warning():
    outs = ([make_outcome(VERDICT_EXECUTED) for _ in range(9)]
            + [make_outcome(VERDICT_ROLLED_BACK) for _ in range(1)])
    report = AnomalyDetector().analyze(_summaries(outs))
    codes = {f.code for f in report.findings}
    assert "ROLLBACK_RATE_HIGH" in codes
    sev = {f.severity for f in report.findings if f.code == "ROLLBACK_RATE_HIGH"}
    assert SEVERITY_WARNING in sev
    assert ROLLBACK_RATE_WARNING == 0.05


def test_rule3_action_loop_warning():
    outs = [make_outcome(VERDICT_EXECUTED, action="pause_campaign", target="loopgame")
            for _ in range(4)]
    report = AnomalyDetector().analyze(_summaries(outs))
    codes = {f.code for f in report.findings}
    assert "ACTION_LOOP" in codes
    sev = {f.severity for f in report.findings if f.code == "ACTION_LOOP"}
    assert SEVERITY_WARNING in sev
    assert ACTION_LOOP_THRESHOLD == 3


def test_rule3_boundary_not_triggered():
    outs = [make_outcome(VERDICT_EXECUTED, action="pause_campaign", target="loopgame")
            for _ in range(3)]
    report = AnomalyDetector().analyze(_summaries(outs))
    assert "ACTION_LOOP" not in {f.code for f in report.findings}


def test_rule4_execution_drift_alert():
    # 请求动作 ≠ 实际动作
    o = make_outcome(VERDICT_EXECUTED, action="update_waterfall")
    req = make_request(action="disable_network")
    s = ExecutionEventCollector().summarize(req, o)
    report = AnomalyDetector().analyze([s])
    codes = {f.code for f in report.findings}
    assert "EXECUTION_DRIFT" in codes
    f = next(x for x in report.findings if x.code == "EXECUTION_DRIFT")
    assert f.severity == SEVERITY_ALERT


def test_empty_report_no_anomaly():
    # 不同 target，避免触发 Rule3 动作循环；全成功无失败/回滚/漂移
    outs = [make_outcome(VERDICT_EXECUTED, target=f"game_{i}") for i in range(5)]
    report = AnomalyDetector().analyze(_summaries(outs))
    assert report.empty is True
    assert report.severity == ""
    assert "正常" in report.to_markdown()


def test_severity_ranking_alert_highest():
    # 同报告含 RED（失败率）与 ALERT（漂移），最高严重度应为 ALERT
    o = make_outcome(VERDICT_EXECUTED, action="update_waterfall")
    req = make_request(action="disable_network")
    drift = ExecutionEventCollector().summarize(req, o)
    outs = [make_outcome(VERDICT_FAILED)] + [o]
    report = AnomalyDetector().analyze(_summaries(outs))
    report.findings.extend(AnomalyDetector().analyze([drift]).findings)
    assert report.severity == SEVERITY_ALERT


def test_report_roundtrip_dict():
    outs = ([make_outcome(VERDICT_EXECUTED) for _ in range(8)]
            + [make_outcome(VERDICT_FAILED) for _ in range(2)])
    report = AnomalyDetector().analyze(_summaries(outs))
    d = report.to_dict()
    assert d["scope"] == "all"
    assert len(d["findings"]) >= 1
    assert "report_id" in d
