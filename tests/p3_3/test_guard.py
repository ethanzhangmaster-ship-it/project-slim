"""P3.3 — StrategyGuard 测试（Simulation Gate，Case4）。"""
from __future__ import annotations

from src.operator.strategy.guard import GuardVerdict, StrategyGuard
from src.operator.strategy.models import StrategyProposal


def _guard():
    return StrategyGuard()


def test_requires_simulation_true_allowed_and_gated():
    g = _guard()
    p = StrategyProposal("aggressive_scale", "switch conservative", "z", 0.6)
    v = g.validate(p)
    assert v.allowed is True
    assert v.gated is True


def test_requires_simulation_false_blocked():
    g = _guard()
    p = StrategyProposal("aggressive_scale", "switch conservative", "z", 0.6,
                         requires_simulation=False)
    v = g.validate(p)
    assert v.allowed is False
    assert v.gated is False
    assert "Simulation" in v.reason


def test_guard_does_not_execute():
    # guard 只裁决，绝不触发任何执行/Provider
    g = _guard()
    before = dict(g.__dict__)
    p = StrategyProposal("x", "y", "z", 0.5)
    g.validate(p)
    assert g.__dict__ == before  # 无状态变化、无副作用


def test_guard_verdict_fields():
    v = GuardVerdict(True, "ok", gated=True)
    assert v.allowed and v.gated and v.reason == "ok"


def test_all_emitted_proposals_pass_guard():
    g = _guard()
    proposals = [
        StrategyProposal("a", "b", "c", 0.5),
        StrategyProposal("d", "e", "f", 0.4),
    ]
    for p in proposals:
        assert g.validate(p).allowed


def test_case4_simulation_gate_enforced():
    # Case4：mutation 产出的 proposal 必须 requires_simulation=True 才能过闸
    g = _guard()
    risky = StrategyProposal("aggressive_scale", "预算增长 30%->10%",
                             "降低波动", 0.7, requires_simulation=True)
    assert g.validate(risky).allowed is True
    # 若有人试图绕过 Simulation（置 False），立即被拦截
    risky.requires_simulation = False
    assert g.validate(risky).allowed is False
