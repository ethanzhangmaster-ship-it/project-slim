"""P3.2 — 集成测试：P3.1 Run -> CEO Report Builder -> 决策单三文件（Case4 完整链路）。"""
from __future__ import annotations

import json
from pathlib import Path

from src.operator import GrowthOperatorScheduler, RunStatus, STAGE_CEO_REPORT
from src.operator.report.models import ActionState

from .conftest import AS_OF


class TestFullLink:
    def _run(self, ctx, run_store):
        sched = GrowthOperatorScheduler(ctx, run_store=run_store)
        return sched.run_daily_cycle(AS_OF)

    def test_three_files_generated(self, ctx, run_store, tmp_path):
        res = self._run(ctx, run_store)
        assert res.status in (RunStatus.COMPLETED, RunStatus.PARTIAL)
        out_dir = Path(ctx.out_dir) / AS_OF
        md = out_dir / "daily_report.md"
        j = out_dir / "daily_report.json"
        acts = out_dir / "actions.json"
        assert md.exists()
        assert j.exists()
        assert acts.exists()

    def test_dry_run_discipline(self, ctx, run_store):
        res = self._run(ctx, run_store)
        assert res.real_api_called is False
        # e17_summary 也应已声明无真实调用
        assert res.summary.get("e17_summary", {}).get("real_api_called") is False

    def test_md_is_decision_sheet_not_log(self, ctx, run_store):
        self._run(ctx, run_store)
        text = (Path(ctx.out_dir) / AS_OF / "daily_report.md").read_text(
            encoding="utf-8"
        )
        # 决策单标记
        assert "每日 CEO 决策单" in text
        assert "今日行动队列" in text
        # 至少出现一个三态标题
        assert any(
            t in text
            for t in ("AUTO EXECUTE", "APPROVAL REQUIRED", "BLOCKED")
        )
        # 不应是旧工程日志标题
        assert "工程日志（每日增长经营日报）" not in text

    def test_ceo_stage_present_and_ok(self, ctx, run_store):
        res = self._run(ctx, run_store)
        by = {s.stage: s for s in res.stages}
        assert STAGE_CEO_REPORT in by
        assert by[STAGE_CEO_REPORT].status == "ok"

    def test_actions_json_three_state(self, ctx, run_store):
        self._run(ctx, run_store)
        acts = json.loads(
            (Path(ctx.out_dir) / AS_OF / "actions.json").read_text(encoding="utf-8")
        )
        assert isinstance(acts, list) and len(acts) > 0
        valid = {"auto", "approval", "blocked"}
        assert all(a["execution_mode"] in valid for a in acts)
        assert all(a["explanation"] for a in acts)
        assert all(a["source"] for a in acts)
        assert all(a["status"] for a in acts)

    def test_counts_consistent(self, ctx, run_store):
        self._run(ctx, run_store)
        report = json.loads(
            (Path(ctx.out_dir) / AS_OF / "daily_report.json").read_text(
                encoding="utf-8"
            )
        )
        acts = json.loads(
            (Path(ctx.out_dir) / AS_OF / "actions.json").read_text(encoding="utf-8")
        )
        hs = report["health_summary"]
        n_auto = sum(1 for a in acts if a["execution_mode"] == "auto")
        n_appr = sum(1 for a in acts if a["execution_mode"] == "approval")
        n_blk = sum(1 for a in acts if a["execution_mode"] == "blocked")
        assert n_auto == hs["auto_count"]
        assert n_appr == hs["approval_count"]
        assert n_blk == hs["blocked_count"]
        assert len(acts) == n_auto + n_appr + n_blk

    def test_idempotent_rerun_keeps_files(self, ctx, run_store):
        first = self._run(ctx, run_store)
        assert first.status in (RunStatus.COMPLETED, RunStatus.PARTIAL)
        second = self._run(ctx, run_store)
        # 幂等门拦截
        assert second.status == RunStatus.SKIPPED
        # 文件仍可读
        assert (Path(ctx.out_dir) / AS_OF / "daily_report.md").exists()
        assert (Path(ctx.out_dir) / AS_OF / "actions.json").exists()
