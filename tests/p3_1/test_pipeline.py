"""P3.1 — DailyOperatorPipeline 端到端测试（SIM，确定性）。"""
from __future__ import annotations

from pathlib import Path

from src.operator.models import (
    ALL_STAGES,
    STAGE_APPROVAL,
    STAGE_AUDIT,
    STAGE_CEO_REPORT,
    STAGE_DECISIONS,
    STAGE_EXECUTIONS,
    STAGE_FAILED,
    STAGE_MEMORY,
    STAGE_MONITOR,
    STAGE_OK,
    STAGE_REALITY,
    STAGE_RECOVERY,
    STAGE_REPORT,
    STAGE_SKIPPED,
)
from src.operator.pipeline import DailyOperatorPipeline

from .conftest import AS_OF


class TestPipelineE2E:
    def _run(self, ctx):
        pipe = DailyOperatorPipeline(ctx)
        return pipe.execute(AS_OF, run_id="op-test-1")

    def test_eleven_stages_in_order(self, ctx):
        stages, _ = self._run(ctx)
        assert [s.stage for s in stages] == list(ALL_STAGES)

    def test_no_failed_stage(self, ctx):
        stages, _ = self._run(ctx)
        failed = [s for s in stages if s.status == STAGE_FAILED]
        assert failed == [], f"意外失败阶段: {[(s.stage, s.detail) for s in failed]}"

    def test_reality_and_audit_ok(self, ctx):
        stages, _ = self._run(ctx)
        by = {s.stage: s for s in stages}
        assert by[STAGE_REALITY].status == STAGE_OK
        assert by[STAGE_REALITY].payload["game_count"] == 8
        assert by[STAGE_AUDIT].status == STAGE_OK
        assert by[STAGE_AUDIT].payload["total_games"] == 8

    def test_decisions_extracted(self, ctx):
        stages, agg = self._run(ctx)
        by = {s.stage: s for s in stages}
        assert by[STAGE_DECISIONS].status == STAGE_OK
        assert by[STAGE_DECISIONS].payload["total"] > 0
        assert agg["decisions"]["total"] == by[STAGE_DECISIONS].payload["total"]

    def test_approval_counts_consistent(self, ctx):
        stages, _ = self._run(ctx)
        p = {s.stage: s for s in stages}[STAGE_APPROVAL].payload
        assert p["contracts"] == (
            p["blocked"] + p["auto_approved"] + p["pending"] + p["denied"]
        )

    def test_dry_run_discipline(self, ctx):
        """验收硬指标：全程 DRY_RUN，real_api_called 恒 False。"""
        _, agg = self._run(ctx)
        assert agg["real_api_called"] is False

    def test_executions_only_authorized(self, ctx):
        """无自动批准授权 → 执行阶段必须 SKIPPED（纪律：不执行未授权请求）。"""
        stages, _ = self._run(ctx)
        by = {s.stage: s for s in stages}
        auto = by[STAGE_APPROVAL].payload["auto_approved"]
        if auto == 0:
            assert by[STAGE_EXECUTIONS].status == STAGE_SKIPPED
            assert by[STAGE_MONITOR].status == STAGE_SKIPPED
            assert by[STAGE_RECOVERY].status == STAGE_SKIPPED
        else:
            assert by[STAGE_EXECUTIONS].payload["total"] == auto

    def test_pending_visible_in_approval_service(self, ctx):
        stages, _ = self._run(ctx)
        p = {s.stage: s for s in stages}[STAGE_APPROVAL].payload
        assert len(ctx.approval_service.pending()) == p["pending"]

    def test_memory_stage_verifies_day_record(self, ctx):
        stages, _ = self._run(ctx)
        by = {s.stage: s for s in stages}
        assert by[STAGE_MEMORY].status == STAGE_OK
        assert by[STAGE_MEMORY].payload["operator_day_record"]["date"] == AS_OF

    def test_report_written(self, ctx):
        stages, agg = self._run(ctx)
        by = {s.stage: s for s in stages}
        # 工程日志仍保留（可追溯）
        assert by[STAGE_REPORT].status == STAGE_OK
        eng = Path(agg["engineering_report_path"])
        assert eng.exists()
        eng_text = eng.read_text(encoding="utf-8")
        assert "工程日志" in eng_text
        assert "CEO 晨报" in eng_text
        # P3.2 CEO 决策单（交付物）
        assert by[STAGE_CEO_REPORT].status == STAGE_OK
        path = Path(agg["report_path"])
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "每日 CEO 决策单" in text
        assert "今日行动队列" in text
        # 三文件齐全
        assert Path(agg["ceo_report_json"]).exists()
        assert Path(agg["actions_path"]).exists()

    def test_stage_failure_isolated(self, ctx):
        """单阶段失败不毁整轮：破坏 auditor → 仅 audit 阶段 failed。"""
        class Broken:
            def audit(self, *a, **k):
                raise RuntimeError("audit exploded")

        ctx.auditor = Broken()
        stages, _ = self._run(ctx)
        by = {s.stage: s for s in stages}
        assert by[STAGE_AUDIT].status == STAGE_FAILED
        assert "audit exploded" in by[STAGE_AUDIT].detail
        # 其余关键阶段照常
        assert by[STAGE_REALITY].status == STAGE_OK
        assert by[STAGE_REPORT].status == STAGE_OK

    def test_deterministic(self, ctx):
        """确定性：同数据两次运行，决策与审批统计一致。"""
        s1, a1 = self._run(ctx)
        s2, a2 = self._run(ctx)
        b1 = {s.stage: s for s in s1}
        b2 = {s.stage: s for s in s2}
        assert (
            b1[STAGE_DECISIONS].payload == b2[STAGE_DECISIONS].payload
        )
        assert a1["decisions"] == a2["decisions"]
