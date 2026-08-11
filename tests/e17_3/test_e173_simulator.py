"""E17.3 模拟层测试（Test4）。"""
from src.ceo_intelligence.decision_engine.simulator import (
    MemoryStats,
    OpportunitySimulator,
)


def test_simulate_deterministic():
    """Test4：同输入同输出，且给出合理预测。"""
    s = OpportunitySimulator()
    r1 = s.simulate("creative_refresh")
    r2 = s.simulate("creative_refresh")
    assert r1 == r2
    assert r1.expected_revenue_change > 0
    assert 0.0 < r1.risk < 1.0
    assert 0.0 < r1.confidence <= 1.0


def test_simulate_per_type_distinct():
    s = OpportunitySimulator()
    a = s.simulate("ua_scale")
    b = s.simulate("monetization")
    # 不同机会类型基线不同
    assert a.expected_revenue_change != b.expected_revenue_change


def test_simulate_memory_success_boosts():
    """历史成功率高 → 置信提升、风险下降。"""
    s = OpportunitySimulator()
    base = s.simulate("ua_scale")
    boosted = s.simulate(
        "ua_scale", MemoryStats(n=5, success_rate=0.9, avg_reward=0.2)
    )
    assert boosted.confidence > base.confidence
    assert boosted.risk < base.risk


def test_simulate_memory_failure_lowers():
    """历史失败率高 → 置信下降、风险上升。"""
    s = OpportunitySimulator()
    base = s.simulate("ua_scale")
    lowered = s.simulate(
        "ua_scale", MemoryStats(n=5, success_rate=0.2, avg_reward=-0.1)
    )
    assert lowered.confidence < base.confidence
    assert lowered.risk > base.risk


def test_simulate_insufficient_samples_no_tweak():
    s = OpportunitySimulator()
    base = s.simulate("ua_scale")
    same = s.simulate(
        "ua_scale", MemoryStats(n=1, success_rate=1.0, avg_reward=0.5)
    )
    assert same == base
