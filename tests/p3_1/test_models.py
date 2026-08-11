"""P3.1 — models 契约测试。"""
from __future__ import annotations

import pytest

from src.operator.models import (
    ALL_STAGES,
    OperatorRunResult,
    RunStatus,
    STAGE_AUDIT,
    STAGE_FAILED,
    STAGE_OK,
    STAGE_REALITY,
    STAGE_SKIPPED,
    StageResult,
)


class TestStageResult:
    def test_valid_stage_ok(self):
        s = StageResult(stage=STAGE_REALITY, detail="ok")
        assert s.status == STAGE_OK

    def test_unknown_stage_rejected(self):
        with pytest.raises(ValueError):
            StageResult(stage="not_a_stage")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            StageResult(stage=STAGE_REALITY, status="weird")

    def test_roundtrip(self):
        s = StageResult(
            stage=STAGE_AUDIT, status=STAGE_FAILED,
            detail="boom", payload={"x": 1},
        )
        s2 = StageResult.from_dict(s.to_dict())
        assert s2.stage == STAGE_AUDIT
        assert s2.status == STAGE_FAILED
        assert s2.payload == {"x": 1}

    def test_all_stages_count(self):
        # reality→audit→opp→sim→dec→approval→exec→monitor→recovery→
        # memory→liveops→strategy_loop→portfolio→ceo_report→report = 15 阶段
        assert len(ALL_STAGES) == 15


class TestOperatorRunResult:
    def _result(self) -> OperatorRunResult:
        return OperatorRunResult(
            run_id="op-2026-07-30-1",
            date="2026-07-30",
            status=RunStatus.COMPLETED,
            stages=[
                StageResult(stage=STAGE_REALITY, detail="a"),
                StageResult(stage=STAGE_AUDIT, status=STAGE_SKIPPED),
            ],
            decisions={"total": 5, "execute": 2},
            executions={"auto": 1},
            report_id="outputs/operator/2026-07-30/daily_report.md",
        )

    def test_ok_property(self):
        r = self._result()
        assert r.ok
        r.status = RunStatus.PARTIAL
        assert r.ok
        r.status = RunStatus.FAILED
        assert not r.ok
        r.status = RunStatus.SKIPPED
        assert not r.ok

    def test_stage_lookup(self):
        r = self._result()
        assert r.stage(STAGE_AUDIT).status == STAGE_SKIPPED
        with pytest.raises(KeyError):
            r.stage("report")

    def test_status_serialized_as_plain_str(self):
        """py3.11 str-Enum 序列化陷阱：必须是 'completed'，不能是 'RunStatus.X'。"""
        d = self._result().to_dict()
        assert d["status"] == "completed"
        assert "RunStatus" not in d["status"]

    def test_roundtrip(self):
        r = self._result()
        r2 = OperatorRunResult.from_dict(r.to_dict())
        assert r2.run_id == r.run_id
        assert r2.status == RunStatus.COMPLETED
        assert r2.decisions == {"total": 5, "execute": 2}
        assert len(r2.stages) == 2
        assert r2.stages[1].status == STAGE_SKIPPED

    def test_defaults(self):
        r = OperatorRunResult(run_id="x", date="2026-07-30")
        assert r.status == RunStatus.COMPLETED
        assert r.real_api_called is False
        assert r.errors == []
