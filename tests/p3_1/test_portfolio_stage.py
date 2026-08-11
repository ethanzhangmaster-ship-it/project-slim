"""P3.1 — Scheduler Integration：把 P3.4.5 PortfolioOptimizer 接入每日 CEO Decision Loop。

覆盖：
- P3.1.1 portfolio 阶段：从 company.per_game 装配输入 → 跑 PortfolioOptimizer →
          结果挂 s["portfolio_result"]；无 company 时 SKIP；绝不触发执行链
          （real_api_called 恒 False，不调 safe_executor）。
- P3.1.2 CEODailyReport.portfolio_recommendation：模型层 round-trip；build_ceo_report 接入。
- P3.1.3 Renderer：markdown 含 "## 七、Portfolio Recommendation"；无建议时优雅省略。

纪律红线（继承 P3.4 + 用户 P3.1 边界）：
- portfolio 阶段只编排不决策、不执行；
- 产出 recommendation-only，real_api_called 恒 False；
- 结果只并入 CEO 报告，绝不进入执行链。
"""
from __future__ import annotations

import json
from pathlib import Path

from src.operator.context import OperatorContext
from src.operator.models import STAGE_OK, STAGE_PORTFOLIO, STAGE_SKIPPED
from src.operator.pipeline import DailyOperatorPipeline
from src.operator.portfolio import (
    AllocationConstraints,
    GamePortfolioSnapshot,
    PortfolioOptimizationInput,
    PortfolioOptimizationResult,
    PortfolioOptimizer,
    PortfolioSnapshot,
)
from src.operator.report.models import (
    CEODailyReport,
    ExecutionSummary,
    HealthSummary,
)
from src.operator.report.sections import build_portfolio_recommendation_section

from .conftest import AS_OF


class TestPortfolioStageUnit:
    def test_skips_without_company(self):
        pipe = DailyOperatorPipeline(_stub_ctx())
        s: dict = {"company": None}
        r = pipe._portfolio(AS_OF, s, "op-1")
        assert r.stage == STAGE_PORTFOLIO
        assert r.status == STAGE_SKIPPED
        assert "portfolio_result" not in s

    def test_runs_with_company_and_attaches_result(self, ctx):
        pipe = DailyOperatorPipeline(ctx)
        s: dict = {"company": ctx.company}
        r = pipe._portfolio(AS_OF, s, "op-1")
        assert r.stage == STAGE_PORTFOLIO
        assert r.status == STAGE_OK
        assert "portfolio_result" in s
        res = s["portfolio_result"]
        assert isinstance(res, PortfolioOptimizationResult)
        assert res.real_api_called is False
        assert r.payload["real_api_called"] is False
        assert r.payload["status"] in (
            "completed", "blocked", "insufficient_data"
        )

    def test_does_not_invoke_execution_layer(self, ctx):
        """行为红线：portfolio 阶段不得调用执行链（safe_executor）。"""
        recorder = _RecordingExecutor(ctx.safe_executor)
        ctx.safe_executor = recorder
        pipe = DailyOperatorPipeline(ctx)
        pipe._portfolio(AS_OF, {"company": ctx.company}, "op-1")
        assert recorder.calls == [], "portfolio 阶段不应触发任何执行"


class TestPortfolioStageE2E:
    def test_full_pipeline_emits_portfolio(self, ctx):
        pipe = DailyOperatorPipeline(ctx)
        stages, agg = pipe.execute(AS_OF, run_id="op-p3-1")
        by = {s.stage: s for s in stages}
        assert by[STAGE_PORTFOLIO].status == STAGE_OK, by[STAGE_PORTFOLIO].detail
        assert agg["portfolio_status"] in (
            "completed", "blocked", "insufficient_data"
        )
        assert agg["summary"]["portfolio"] is not None
        # 报告落盘含 Portfolio Recommendation 段
        md = Path(agg["report_path"]).read_text(encoding="utf-8")
        assert "## 七、Portfolio Recommendation" in md
        assert "real_api_called" in md
        js = json.loads(Path(agg["ceo_report_json"]).read_text(encoding="utf-8"))
        assert js["portfolio_recommendation"] is not None
        assert js["portfolio_recommendation"]["real_api_called"] is False

    def test_aggregates_exposes_portfolio_status(self, ctx):
        pipe = DailyOperatorPipeline(ctx)
        _, agg = pipe.execute(AS_OF, run_id="op-p3-1-b")
        assert "portfolio_status" in agg
        assert agg["portfolio_status"] is not None


class TestCEOReportPortfolioModel:
    def test_roundtrip_with_section(self):
        section = build_portfolio_recommendation_section(_mini_result())
        rep = CEODailyReport(
            report_id="ceo-x", date="2026-07-30",
            health_summary=_health(),
            opportunities=[], actions=[], risks=[],
            learning_summary=[],
            execution_summary=ExecutionSummary(
                total_executions=0, success=0, failed=0,
                rollback=0, blocked=0, health_level="",
            ),
            portfolio_recommendation=section,
        )
        d = rep.to_dict()
        assert d["portfolio_recommendation"]["status"] == section["status"]
        r2 = CEODailyReport.from_dict(d)
        assert r2.portfolio_recommendation == section

    def test_absent_section_roundtrip(self):
        rep = CEODailyReport(
            report_id="ceo-y", date="2026-07-30",
            health_summary=_health(),
            opportunities=[], actions=[], risks=[],
            learning_summary=[],
            execution_summary=ExecutionSummary(
                total_executions=0, success=0, failed=0,
                rollback=0, blocked=0, health_level="",
            ),
        )
        assert rep.to_dict()["portfolio_recommendation"] is None
        assert CEODailyReport.from_dict(rep.to_dict()).portfolio_recommendation is None


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
def _stub_ctx() -> OperatorContext:
    return OperatorContext(
        agent=object(), auditor=object(), registry=object(),
        approval_service=object(), safe_executor=object(),
        monitor=object(), recovery=object(), out_dir="out",
    )


def _health() -> HealthSummary:
    return HealthSummary(
        company_status="healthy", status_label="🟢 健康",
        game_count=1, total_revenue=0.0, total_dau=0,
        total_spend=0.0, avg_confidence=1.0,
    )


class _RecordingExecutor:
    def __init__(self, wrapped):
        self._wrapped = wrapped
        self.calls: list = []

    def execute(self, *a, **k):
        self.calls.append((a, k))
        if hasattr(self._wrapped, "execute"):
            return self._wrapped.execute(*a, **k)
        return None


def _mini_result() -> PortfolioOptimizationResult:
    """构造一个最小但真实的 PortfolioOptimizationResult（走一遍 optimizer）。"""
    snap = PortfolioSnapshot(
        generated_at="2026-07-30",
        games=[GamePortfolioSnapshot(
            game_id="g1", revenue=1000.0, spend=100.0, roas=2.0,
            confidence=0.7, coverage=1.0,
        )],
        total_revenue=1000.0, total_spend=100.0, coverage=1.0,
    )
    return PortfolioOptimizer().optimize(PortfolioOptimizationInput(
        snapshots=snap,
        rankings=[],
        constraints=AllocationConstraints(total_budget=100.0),
        current_allocation={"g1": 100.0},
        as_of="2026-07-30",
    ))
