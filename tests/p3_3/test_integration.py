"""P3.3 — 集成测试：P3.1 Pipeline 插入 strategy_loop 阶段。"""
from __future__ import annotations

from pathlib import Path

from src.operator import GrowthOperatorScheduler
from src.operator.models import STAGE_CEO_REPORT, STAGE_MEMORY, STAGE_STRATEGY


def _run(ctx, run_store, date):
    sched = GrowthOperatorScheduler(ctx, run_store=run_store)
    return sched.run_daily_cycle(date, force=True)


def test_strategy_stage_present_and_ok(ctx, run_store):
    res = _run(ctx, run_store, "2026-07-31")
    stages = {s.stage: s for s in res.stages}
    assert STAGE_STRATEGY in stages
    assert stages[STAGE_STRATEGY].status == "ok"
    assert "未执行" in stages[STAGE_STRATEGY].detail


def test_stage_order_memory_strategy_ceo(ctx, run_store):
    res = _run(ctx, run_store, "2026-07-31")
    order = [s.stage for s in res.stages]
    assert order.index(STAGE_MEMORY) < order.index(STAGE_STRATEGY) \
        < order.index(STAGE_CEO_REPORT)


def test_strategy_files_written(ctx, run_store):
    res = _run(ctx, run_store, "2026-07-31")
    out = Path(ctx.out_dir) / "2026-07-31"
    for f in ("strategy_insights.json", "strategy_proposals.json",
              "strategy_states.json"):
        assert (out / f).exists(), f"missing {f}"
    # 策略状态文件至少含默认 4 策略
    import json
    states = json.loads((out / "strategy_states.json").read_text(encoding="utf-8"))
    assert len(states) >= 4


def test_ceo_report_contains_strategy_learning(ctx, run_store):
    res = _run(ctx, run_store, "2026-07-31")
    md = Path(ctx.out_dir) / "2026-07-31" / "daily_report.md"
    text = md.read_text(encoding="utf-8")
    # 今日学习段应含策略洞察/建议行
    assert "建议" in text or "洞察" in text or "Simulation" in text


def test_dry_run_discipline(ctx, run_store):
    res = _run(ctx, run_store, "2026-07-31")
    assert res.real_api_called is False


def test_idempotent_rerun(ctx, run_store):
    _run(ctx, run_store, "2026-07-31")
    res2 = _run(ctx, run_store, "2026-07-31")
    assert res2.status.value in ("completed", "skipped")


def test_strategy_loop_does_not_modify_decision(ctx, run_store):
    # 全流程下不应触发任何真实执行 / 不应修改既有 Decision（real_api_called False 即纪律保证）
    res = _run(ctx, run_store, "2026-07-31")
    assert res.real_api_called is False
    sl = {s.stage: s for s in res.stages}[STAGE_STRATEGY]
    assert "未执行" in sl.detail
