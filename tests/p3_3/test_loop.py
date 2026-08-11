"""P3.3 — StrategyLoop 测试（Observe→Evaluate→Learn→Adjust→Emit，不执行）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.operator.strategy.guard import StrategyGuard
from src.operator.strategy.loop import StrategyLoop, write_strategy_outputs
from src.operator.strategy.memory import StrategyMemoryAdapter
from src.operator.strategy.models import StrategyStatus
from src.operator.strategy.mutation import StrategyMutationEngine
from .conftest import make_feedback


@pytest.fixture
def loop(adapter, tmp_store):
    return StrategyLoop(
        memory_adapter=adapter,
        mutation_engine=StrategyMutationEngine(),
        guard=StrategyGuard(),
        graph=None,
    )


def test_run_produces_feedbacks_and_insights(loop, daily_with_actions):
    res = loop.run(daily_with_actions)
    assert len(res.feedbacks) == 3
    assert len(res.insights) >= 4  # 默认 4 策略 + action 衍生


def test_run_does_not_mutate_decision(loop, daily_with_actions):
    # Case3：Strategy Loop 绝不修改 E17.3 Decision
    class FakeDec:
        def __init__(self):
            self.calls = []
        def to_dict(self):
            self.calls.append("to_dict")
            return {"audit_id": "x", "decisions": []}
    dec = FakeDec()
    daily_with_actions.dec_report = dec
    loop.run(daily_with_actions)
    assert daily_with_actions.dec_report is dec
    assert dec.calls == []  # 全程未触碰 Decision


def test_run_has_no_executor_or_provider(loop):
    # Case3：loop 对象本身不持有执行器 / Provider
    assert not hasattr(loop, "safe_executor")
    assert not hasattr(loop, "provider")
    assert not hasattr(loop, "execution_router")


def test_auto_success_boosts_confidence(loop, daily_with_actions, adapter):
    start = adapter.all_states()["network_cleanup"].confidence
    loop.run(daily_with_actions)
    end = adapter.all_states()["network_cleanup"].confidence
    assert end > start  # AUTO 行动 → SUCCESS 反馈 → 增信


def test_block_action_is_neutral_no_penalty(loop, daily_with_actions, adapter):
    # aggressive_scale 在 demo 里是 BLOCK（中性）→ 不应被降权
    st = adapter.all_states()["aggressive_scale"]
    start = st.confidence
    loop.run(daily_with_actions)
    assert adapter.all_states()["aggressive_scale"].confidence == start


def test_emitted_proposals_all_gated(loop, daily_with_actions):
    res = loop.run(daily_with_actions)
    # 默认 demo 不触发突变 → 可能为空；若非空则必须 requires_simulation
    assert all(p.requires_simulation for p in res.proposals)


def test_patterns_nonempty_when_insights(loop, daily_with_actions):
    res = loop.run(daily_with_actions)
    assert res.patterns  # 至少包含洞察行


def test_run_writes_outputs(loop, daily_with_actions, tmp_path):
    out = tmp_path / "out"
    res = loop.run(daily_with_actions)
    paths = write_strategy_outputs("2026-07-31", str(out), res)
    for k in ("strategy_insights", "strategy_proposals", "strategy_states"):
        assert Path(paths[k]).exists()
    data = json.loads(Path(paths["strategy_states"]).read_text(encoding="utf-8"))
    assert isinstance(data, dict) and len(data) >= 4


def test_loop_with_graph_uses_patterns(loop, daily_with_actions, monkeypatch, fake_patterns):
    import src.operator.strategy.memory as mm
    monkeypatch.setattr(mm, "extract_patterns", lambda g: fake_patterns)
    loop.graph = object()
    res = loop.run(daily_with_actions)
    net = [i for i in res.insights if i.strategy_id == "network_cleanup"][0]
    assert net.historical_success_rate == 0.87


def test_loop_triggers_mutation_when_strategy_disabled(tmp_store, daily_with_actions):
    # 预置 aggressive_scale 连续失败 → DISABLED → 突变引擎应产出 gated 建议
    a = StrategyMemoryAdapter(store_path=tmp_store)
    for _ in range(5):
        a.apply_feedback(make_feedback("aggressive_scale", "FAILURE", -0.4))
    a.save()
    loop = StrategyLoop(
        memory_adapter=a,
        mutation_engine=StrategyMutationEngine(),
        guard=StrategyGuard(),
    )
    res = loop.run(daily_with_actions)
    assert len(res.proposals) >= 1
    assert all(p.requires_simulation for p in res.proposals)
    # 不执行：状态未因 proposal 被改回 ACTIVE
    assert a.all_states()["aggressive_scale"].status == StrategyStatus.DISABLED


def test_loop_is_deterministic(tmp_path, daily_with_actions):
    a1 = StrategyMemoryAdapter(store_path=str(tmp_path / "s1.jsonl"))
    a2 = StrategyMemoryAdapter(store_path=str(tmp_path / "s2.jsonl"))
    r1 = StrategyLoop(a1).run(daily_with_actions)
    r2 = StrategyLoop(a2).run(daily_with_actions)
    assert [i.to_dict() for i in r1.insights] == [i.to_dict() for i in r2.insights]
