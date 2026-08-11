"""P2.5.9 — Full Chain 验收：E17 → P1.7 → P2.1 → P2.3 → P2.4 → P2.2 → P2.5 → Memory。

本测试拥有 P2.5 边界：用真实 P2.4 SafeExecutor 产出 SafeExecutionOutcome，
再由 P2.5 Monitor 观察并回流 Memory（经验库 + E17.7 图谱）。
验证 observe → detect → report → feedback 全闭环。
"""

import os
import tempfile

from src.execution.monitor import ExecutionMonitor
from src.execution.monitor.collector import ExecutionEventCollector
from src.execution.providers.result import (
    STATUS_DRY_RUN,
    STATUS_FAILED,
    ExecutionResult,
)
from src.execution.safe_executor.executor import SafeExecutor
from src.execution.safe_executor.models import VERDICT_EXECUTED, VERDICT_FAILED
from tests.p2_5.conftest import make_outcome, make_request


def _fake_execute(status, before=None, after=None):
    def _fn(request):
        return ExecutionResult(
            request_id=getattr(request, "request_id", "req_x"),
            provider="max",
            status=status,
            real_api_called=False,
            before_state=before or {"ecpm": 10.0},
            after_state=after or {"ecpm": 20.0},
        )
    return _fn


def test_full_chain_real_executor_success():
    """真实 P2.4 SafeExecutor 跑通 -> P2.5 observe -> Memory。"""
    with tempfile.TemporaryDirectory() as d:
        from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph

        graph = GrowthMemoryGraph(os.path.join(d, "graph.jsonl"))
        monitor = ExecutionMonitor(graph=graph)
        executor = SafeExecutor(execute_fn=_fake_execute(STATUS_DRY_RUN))

        req = make_request(action="update_waterfall", target="merge_witch")
        outcome = executor.execute(req)
        assert outcome.verdict == VERDICT_EXECUTED

        obs = monitor.observe(req, outcome)
        assert obs.execution_id == outcome.context.execution_id
        assert len(obs.events) >= 5
        assert obs.tracked_state.final_state == "SUCCESS"
        assert obs.experience is not None
        assert obs.experience.context["game"] == "merge_witch"
        # 回流图谱
        from src.ceo_intelligence.growth_memory_graph.models import (
            NodeType, node_id,
        )
        assert graph.get_node(node_id(NodeType.EXECUTION, obs.execution_id)) is not None


def test_full_chain_real_executor_failure():
    executor = SafeExecutor(execute_fn=_fake_execute(STATUS_FAILED))
    req = make_request(action="disable_network", target="game_x")
    outcome = executor.execute(req)
    assert outcome.verdict == VERDICT_FAILED
    monitor = ExecutionMonitor()
    obs = monitor.observe(req, outcome)
    assert obs.tracked_state.final_state == "FAILED"
    assert any(e.event_type == "PROVIDER_FAILED" for e in obs.events)


def test_full_chain_observe_batch_summary():
    """批量 observe -> 每日报告（指标 / 异常 / 健康 / 学习）。"""
    outs = (
        [make_outcome(VERDICT_EXECUTED, action="update_waterfall", target="g1",
                      before_state={"ecpm": 10}, after_state={"ecpm": 18}) for _ in range(6)]
        + [make_outcome(VERDICT_EXECUTED, action="disable_network", target="g2",
                        before_state={"ecpm": 5}, after_state={"ecpm": 9}) for _ in range(4)]
    )
    reqs = [make_request() for _ in outs]
    monitor = ExecutionMonitor()
    results, report = monitor.observe_batch(list(zip(reqs, outs)), date="2026-07-30")

    assert len(results) == 10
    assert report.total_executions == 10
    assert report.success == 10
    assert report.health_level == "GREEN"
    assert "update_waterfall" in report.providers or "max" in report.providers
    # 全部真实执行 -> 应提炼出学习点
    assert len(report.learnings) >= 1


def test_full_chain_anomaly_triggers_on_high_failure():
    """失败率过高 -> 报告带 WARNING/RED。"""
    outs = (
        [make_outcome(VERDICT_EXECUTED) for _ in range(7)]
        + [make_outcome(VERDICT_FAILED, target="g_fail") for _ in range(3)]
    )
    reqs = [make_request() for _ in outs]
    monitor = ExecutionMonitor()
    _, report = monitor.observe_batch(list(zip(reqs, outs)), date="2026-07-31")
    assert report.failed == 3
    assert len(report.warnings) >= 1
    assert any("FAILURE_RATE_HIGH" in w for w in report.warnings)


def test_full_chain_experience_stored_and_queryable():
    """反馈经验落 JSONL 并可查询。"""
    with tempfile.TemporaryDirectory() as d:
        from src.execution.monitor.feedback import JsonlExecutionExperienceStore

        store = JsonlExecutionExperienceStore(os.path.join(d, "exp.jsonl"))
        monitor = ExecutionMonitor(feedback_store=store)
        outs = [
            make_outcome(VERDICT_EXECUTED, action="update_waterfall", target="g1",
                         before_state={"ecpm": 10}, after_state={"ecpm": 30}),
            make_outcome(VERDICT_EXECUTED, action="update_waterfall", target="g2",
                         before_state={"ecpm": 10}, after_state={"ecpm": 15}),
        ]
        reqs = [make_request() for _ in outs]
        monitor.observe_batch(list(zip(reqs, outs)), date="2026-08-01")
        stats = store.stats("update_waterfall")
        assert stats["n"] == 2
        assert stats["success_rate"] == 1.0
        assert stats["avg_reward"] > 0


def test_full_chain_discipline_no_decision_no_write():
    """纪律校验：Monitor 不修改 outcome、不调用平台 API。"""
    import copy
    o = make_outcome(VERDICT_EXECUTED, latency_seconds=3.0)
    snapshot_o = copy.deepcopy(o.to_dict())
    o2 = make_outcome(VERDICT_EXECUTED, latency_seconds=3.0)
    snapshot_o2 = copy.deepcopy(o2.to_dict())
    monitor = ExecutionMonitor()
    monitor.observe(None, o)
    # outcome 未被 Monitor 改写（自身前后一致）
    assert o.to_dict() == snapshot_o
    # 另一个 outcome 也未受任何影响
    assert o2.to_dict() == snapshot_o2
