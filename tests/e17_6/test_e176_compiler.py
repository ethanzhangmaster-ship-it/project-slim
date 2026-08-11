"""E17.6 — ActionCompiler：StrategyTask → ExecutionAction 编译测试。"""
from src.ceo_intelligence.execution_router.executor import ActionCompiler
from src.ceo_intelligence.strategy_planner.models import GrowthStrategyPlan
from src.ceo_intelligence.strategy_planner.templates import build_tasks, get_template


def _plan(strategy_type: str, *, needs_approval: bool = False) -> GrowthStrategyPlan:
    tpl = get_template(strategy_type)
    return GrowthStrategyPlan(
        game_id="merge_witch",
        decision_id="dec_test",
        objective=tpl.objective,
        strategy_type=strategy_type,
        tasks=build_tasks(tpl),
        needs_approval=needs_approval,
    )


def test_compile_creative_refresh_domains():
    """模板 5 步映射：3×CREATIVE + 1×UA + 1×ANALYTICS，参数正确抽取。"""
    actions = ActionCompiler().compile_plan(_plan("creative_refresh"))
    assert [a.domain for a in actions] == [
        "creative", "creative", "creative", "ua", "analytics",
    ]
    assert actions[0].action_type == "analyze_dna"
    assert actions[1].action_type == "generate_creatives"
    assert actions[1].payload["count"] == 30          # "Generate 30 new creatives"
    assert actions[2].action_type == "clip_screen"
    assert actions[3].action_type == "run_experiment"  # "Run Meta experiment"
    assert actions[4].action_type == "evaluate_roas"
    # 血缘字段完整
    for a in actions:
        assert a.game_id == "merge_witch"
        assert a.decision_id == "dec_test"
        assert a.plan_strategy_type == "creative_refresh"
        assert a.action_id.startswith("act_")


def test_compile_ua_scale_budget_percent():
    """"Increase budget 20%" → increase_budget percent=20。"""
    actions = ActionCompiler().compile_plan(_plan("ua_scale"))
    inc = next(a for a in actions if a.action_type == "increase_budget")
    assert inc.domain == "ua"
    assert inc.payload["percent"] == 20
    assert abs(inc.risk_level - 0.5) < 1e-6
    # Monitor CPI / Monitor ROAS 归 analytics 只读
    monitors = [a for a in actions if a.domain == "analytics"]
    assert len(monitors) >= 2


def test_compile_human_tasks_tracked():
    """Product / Engineering / QA 的步骤编译为 ANALYTICS:track_human_task。"""
    actions = ActionCompiler().compile_plan(_plan("release_health"))
    # 1: Release Agent triage → release 域
    assert actions[0].domain == "release"
    assert actions[0].action_type == "triage_health"
    # 2: Engineering / 3: QA → 人类任务登记
    for a in actions[1:]:
        assert a.domain == "analytics"
        assert a.action_type == "track_human_task"
        assert a.payload["owner"] in ("Engineering", "QA")


def test_compile_dependency_and_approval_propagation():
    """依赖透传；plan.needs_approval 只传导到会动手的域。"""
    actions = ActionCompiler().compile_plan(
        _plan("aso_optimization", needs_approval=True)
    )
    listing = next(a for a in actions if a.action_type == "update_listing")
    assert listing.dependency == ["1"]
    assert listing.approval_required is True
    analytics = next(a for a in actions if a.domain == "analytics")
    assert analytics.approval_required is False
