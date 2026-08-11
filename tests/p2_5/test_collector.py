"""P2.5.2 — ExecutionEventCollector 事件采集 + 摘要 + JSONL 存储验收。"""

from src.execution.monitor.collector import (
    ExecutionEventCollector,
    JsonlExecutionEventStore,
)
from src.execution.monitor.models import (
    EVENT_APPROVAL_GRANTED,
    EVENT_CREATED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_PROVIDER_FAILED,
    EVENT_PROVIDER_SUCCESS,
    EVENT_ROLLBACK_FAILED,
    EVENT_ROLLBACK_STARTED,
    EVENT_ROLLBACK_SUCCESS,
    EVENT_VERIFIED,
)
from src.execution.safe_executor.models import (
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
)
from tests.p2_5.conftest import make_outcome, make_request

import os
import tempfile


def test_collect_executed_sequence():
    o = make_outcome(VERDICT_EXECUTED, latency_seconds=3.0)
    events = ExecutionEventCollector().collect(o)
    types = [e.event_type for e in events]
    assert types[0] == EVENT_CREATED
    assert EVENT_EXECUTION_STARTED in types
    assert EVENT_PROVIDER_CALLED in types
    assert EVENT_PROVIDER_SUCCESS in types
    assert EVENT_VERIFIED in types
    assert EVENT_PROVIDER_FAILED not in types
    # 真实执行，real_api_called=True 透出
    called = next(e for e in events if e.event_type == EVENT_PROVIDER_CALLED)
    assert called.metadata["real_api_called"] is True


def test_collect_approval_granted_present():
    o = make_outcome(VERDICT_EXECUTED, authorization_id="apr_123")
    events = ExecutionEventCollector().collect(o)
    assert any(e.event_type == EVENT_APPROVAL_GRANTED for e in events)


def test_collect_blocked_no_provider_call():
    o = make_outcome(VERDICT_BLOCKED)
    events = ExecutionEventCollector().collect(o)
    types = [e.event_type for e in events]
    assert types == [EVENT_CREATED]  # 闸门拦截，无后续事件


def test_collect_idempotent_short_circuit():
    o = make_outcome(VERDICT_RETURN_EXISTING)
    events = ExecutionEventCollector().collect(o)
    types = [e.event_type for e in events]
    assert EVENT_CREATED in types
    assert EVENT_VERIFIED in types
    assert EVENT_PROVIDER_CALLED not in types
    assert EVENT_EXECUTION_STARTED not in types


def test_collect_rolled_back_sequence():
    o = make_outcome(VERDICT_ROLLED_BACK)
    events = ExecutionEventCollector().collect(o)
    types = [e.event_type for e in events]
    assert EVENT_PROVIDER_FAILED in types
    assert EVENT_ROLLBACK_STARTED in types
    assert EVENT_ROLLBACK_SUCCESS in types
    assert EVENT_VERIFIED in types


def test_collect_escalated_sequence():
    o = make_outcome(VERDICT_ESCALATED)
    events = ExecutionEventCollector().collect(o)
    types = [e.event_type for e in events]
    assert EVENT_ROLLBACK_STARTED in types
    assert EVENT_ROLLBACK_FAILED in types
    assert EVENT_ROLLBACK_SUCCESS not in types


def test_summarize_extracts_latency_and_real():
    o = make_outcome(VERDICT_EXECUTED, latency_seconds=4.0)
    s = ExecutionEventCollector().summarize(None, o)
    assert s.latency_seconds == 4.0
    assert s.is_real is True
    assert s.verdict == "EXECUTED"
    assert s.status == "SUCCESS"


def test_summarize_intended_action_from_request():
    o = make_outcome(VERDICT_EXECUTED, action="update_waterfall")
    req = make_request(action="disable_network")
    s = ExecutionEventCollector().summarize(req, o)
    assert s.intended_action == "disable_network"
    assert s.action == "update_waterfall"
    assert s.drifted is True


def test_summarize_no_request_intended_blank():
    o = make_outcome(VERDICT_EXECUTED)
    s = ExecutionEventCollector().summarize(None, o)
    assert s.intended_action == ""
    assert s.drifted is False


def test_jsonl_store_roundtrip():
    o = make_outcome(VERDICT_EXECUTED, latency_seconds=2.0)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        store = JsonlExecutionEventStore(path)
        store.append(ExecutionEventCollector().collect(o))
        all_ev = store.all()
        assert len(all_ev) >= 5
        same = store.for_execution(o.context.execution_id)
        assert len(same) == len(all_ev)
        assert all(e.execution_id == o.context.execution_id for e in same)
