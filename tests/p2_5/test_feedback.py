"""P2.5.7 — Feedback Bridge（经验回流 Memory + 图谱）验收。"""

import os
import tempfile

from src.execution.monitor.feedback import (
    ExecutionExperienceRecord,
    FeedbackBridge,
    JsonlExecutionExperienceStore,
    default_reward,
)
from src.execution.monitor.models import SEVERITY_WARNING
from src.execution.safe_executor.models import VERDICT_EXECUTED
from tests.p2_5.conftest import make_outcome, make_request


def test_default_reward_relative_uplift():
    rec = ExecutionExperienceRecord(
        action="update_waterfall",
        result={"before_ecpm": 10.0, "after_ecpm": 20.0},
    )
    reward, success = default_reward(rec)
    assert abs(reward - 1.0) < 1e-6
    assert success is True


def test_default_reward_decline():
    rec = ExecutionExperienceRecord(
        action="x", result={"before_ecpm": 10.0, "after_ecpm": 5.0}
    )
    reward, success = default_reward(rec)
    assert reward < 0
    assert success is False


def test_default_reward_zero_before_positive_after():
    rec = ExecutionExperienceRecord(action="x", result={"before_ecpm": 0.0, "after_ecpm": 5.0})
    reward, success = default_reward(rec)
    assert reward == 1.0


def test_default_reward_no_signal():
    rec = ExecutionExperienceRecord(action="x", result={"before_ecpm": 0.0, "after_ecpm": 0.0})
    reward, success = default_reward(rec)
    assert reward == 0.0
    assert success is False


def test_record_roundtrip():
    rec = ExecutionExperienceRecord(
        action="update_waterfall",
        context={"game": "merge_witch", "network": "max"},
        result={"before_ecpm": 12.3, "after_ecpm": 22.4},
        provider="max", execution_id="exe_1", verdict="EXECUTED",
    )
    d = rec.to_dict()
    assert d["context"]["game"] == "merge_witch"
    assert d["result"]["after_ecpm"] == 22.4
    rec2 = ExecutionExperienceRecord.from_dict(d)
    assert rec2.action == "update_waterfall"
    assert rec2.result["before_ecpm"] == 12.3


def test_jsonl_store_add_and_query():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "exp.jsonl")
        store = JsonlExecutionExperienceStore(path)
        store.add(ExecutionExperienceRecord(
            action="update_waterfall",
            context={"game": "g", "network": "max"},
            result={"before_ecpm": 10.0, "after_ecpm": 20.0},
        ))
        store.add(ExecutionExperienceRecord(
            action="update_waterfall",
            context={"game": "g", "network": "max"},
            result={"before_ecpm": 10.0, "after_ecpm": 12.0},
        ))
        rows = store.for_action("update_waterfall")
        assert len(rows) == 2
        stats = store.stats("update_waterfall")
        assert stats["n"] == 2
        assert stats["success_rate"] == 1.0
        assert stats["avg_reward"] > 0


def test_feedback_bridge_push_builds_record():
    o = make_outcome(
        VERDICT_EXECUTED, action="update_waterfall", target="merge_witch",
        before_state={"ecpm": 10.0}, after_state={"ecpm": 20.0},
    )
    req = make_request(action="update_waterfall", target="merge_witch")
    bridge = FeedbackBridge()
    rec = bridge.push(req, o)
    assert rec.context["game"] == "merge_witch"
    assert rec.context["network"] == "max"
    assert rec.result["before_ecpm"] == 10.0
    assert rec.result["after_ecpm"] == 20.0
    assert rec.reward == 1.0
    assert rec.success is True


def test_feedback_bridge_push_to_graph():
    from src.ceo_intelligence.growth_memory_graph.models import (
        EdgeType,
        NodeType,
        node_id,
    )
    from src.ceo_intelligence.growth_memory_graph.store import GrowthMemoryGraph

    with tempfile.TemporaryDirectory() as d:
        graph = GrowthMemoryGraph(os.path.join(d, "graph.jsonl"))
        o = make_outcome(
            VERDICT_EXECUTED, action="update_waterfall", target="merge_witch",
            before_state={"ecpm": 10.0}, after_state={"ecpm": 20.0},
        )
        req = make_request(action="update_waterfall", target="merge_witch")
        bridge = FeedbackBridge(graph=graph)
        rec = bridge.push(req, o)
        result = bridge.push_to_graph(rec)
        assert result["skipped"] is False
        assert len(result["nodes_added"]) == 3
        # 图谱确实新增了 execution/action/result 节点
        exe_id = rec.execution_id
        assert graph.get_node(node_id(NodeType.EXECUTION, exe_id)) is not None
        assert graph.get_node(node_id(NodeType.ACTION, exe_id)) is not None
        assert graph.get_node(node_id(NodeType.RESULT, exe_id)) is not None


def test_feedback_bridge_push_to_graph_skipped_without_graph():
    o = make_outcome(VERDICT_EXECUTED)
    bridge = FeedbackBridge()  # 无 graph
    rec = bridge.push(None, o)
    result = bridge.push_to_graph(rec)
    assert result["skipped"] is True
