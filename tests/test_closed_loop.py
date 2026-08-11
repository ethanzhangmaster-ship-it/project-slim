from pathlib import Path

from market_ops.product.closed_loop import GrowthLoop


def _results():
    return [
        {"experiment_id": "exp-winner", "creative_id": "creative-winner", "decision": "WINNER", "confidence": 0.92, "budget_before": 100.0},
        {"experiment_id": "exp-failed", "creative_id": "creative-failed", "decision": "FAILED", "confidence": 0.88, "budget_before": 80.0},
    ]


def test_loop_is_idempotent_and_requires_human_approval(tmp_path: Path):
    loop = GrowthLoop(tmp_path / "growth.db")
    first = loop.plan(_results(), total_budget=1000)
    second = loop.plan(_results(), total_budget=1000)
    assert first["cycle_id"] == second["cycle_id"]
    cycle = loop.execute(first["cycle_id"])
    assert cycle["status"] == "AWAITING_APPROVAL"
    assert any(task["status"] == "PENDING_APPROVAL" for task in cycle["tasks"])


def test_observation_creates_a_persisted_learning_signal(tmp_path: Path):
    loop = GrowthLoop(tmp_path / "growth.db")
    cycle = loop.plan(_results(), total_budget=1000)
    planned = loop.execute(cycle["cycle_id"])
    for task in planned["tasks"]:
        loop.approve(task["task_id"], "test-operator")
    executed = loop.execute(cycle["cycle_id"])
    task = executed["tasks"][0]
    evidence = loop.observe(task["task_id"], {"spend": 100, "revenue": 190, "status": "active"})
    assert evidence["signal"]["feedback_type"] == "SUCCESS"
    assert loop.cycle(cycle["cycle_id"])["observations"]
