"""E17.4 Test5：质量门禁（无指标 → 拒绝）。"""
from src.ceo_intelligence.strategy_planner.models import (
    GrowthStrategyPlan,
    StrategyTask,
)
from src.ceo_intelligence.strategy_planner.validator import StrategyValidator


def _task(order, deps):
    return StrategyTask(
        order=order, owner="x", action=f"a{order}",
        dependency=deps, expected_output="o", deadline=str(order),
    )


def test_quality_gate_rejects_no_metric():
    """Test5：缺 success_metrics / objective 被门禁拒绝。"""
    v = StrategyValidator()

    # 无指标 + 无目标
    bad = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="", strategy_type="x",
        tasks=[_task(1, [])], success_metrics={},
    )
    r = v.validate(bad)
    assert r.ok is False
    assert any("metric" in reason or "objective" in reason for reason in r.reasons)

    # 指标存在但不可量化（「提升收入」）
    vague_metric = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="增长收入", strategy_type="x",
        tasks=[_task(1, [])], success_metrics={"revenue": "提升收入"},
    )
    r2 = v.validate(vague_metric)
    assert r2.ok is False
    assert any("measurable" in reason for reason in r2.reasons)

    # 模糊目标词
    vague_obj = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="优化一下", strategy_type="x",
        tasks=[_task(1, [])], success_metrics={"roas": "+10%"},
    )
    r3 = v.validate(vague_obj)
    assert r3.ok is False
    assert any("objective" in reason for reason in r3.reasons)


def test_quality_gate_passes_with_metric():
    """对照：有可量化指标 + 明确目标 → 通过。"""
    good = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="Recover creative fatigue",
        strategy_type="creative_refresh", tasks=[_task(1, [])],
        success_metrics={"ctr": "+15%", "roas": "+10%"},
    )
    r = StrategyValidator().validate(good)
    assert r.ok is True
    assert r.reasons == []


def test_quality_gate_flags_high_risk_approval():
    """Gate 3：高风险决策 / 经济类策略 → 标记需审批（不拒绝）。"""
    v = StrategyValidator()
    # 高风险 decision_risk
    high = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="x", strategy_type="ua_scale",
        tasks=[_task(1, [])], success_metrics={"roas": "+5%"},
    )
    r = v.validate(high, decision_risk=0.7)
    assert r.ok is True
    assert r.needs_approval is True

    # 经济类策略默认需审批
    econ = GrowthStrategyPlan(
        game_id="g", decision_id="d", objective="x", strategy_type="monetization",
        tasks=[_task(1, [])], success_metrics={"arpu": "+8%"},
    )
    r2 = v.validate(econ)
    assert r2.ok is True
    assert r2.needs_approval is True
