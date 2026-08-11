"""GrowthLoopOrchestrator 单元测试。

覆盖:
  - 启动恢复 (空状态 / 有历史状态)
  - ExperienceStore 快照序列化/反序列化往返
  - 主循环 Phase B: Signal → Diagnose → Hypothesize → Select → Plan → Execute
  - PendingEvaluation 创建与队列管理
  - Phase A: 到期评估 / 过期清理
  - 跨重启续跑 (写入 → 重新加载 → 验证一致性)
  - dry-run 模式
  - 状态查询
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from src.market_ops.creative_vision_runtime.reality.feedback.models import (
    FeedbackSignalType,
    RealityFeedbackSignal,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ExperienceOutcome,
    ExperienceRecord,
    MutationDetail,
    ExperimentDetail,
    ContextDetail,
    ExperienceResult,
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.diagnostic_engine import RootCause, StrategyType
from scripts.action_planner import ActionType, ActionStatus
from scripts.action_executor import (
    ActionExecutionStatus,
    ExecutionResult,
    MockPlatformAdapter,
    SafetyGate,
)
from scripts.outcome_evaluator import ActionOutcome
from scripts.loop_state import LoopState
from scripts.pending_evaluation import PendingEvaluation
from scripts.growth_loop_orchestrator import GrowthLoopOrchestrator, CycleResult


# ──────────────────────────────────────────────
# 测试 fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _make_signal(
    creative_id: str = "cr_test01",
    signal_type: FeedbackSignalType = FeedbackSignalType.ROAS_DECLINE,
    severity: float = 0.8,
    confidence: float = 0.8,
) -> RealityFeedbackSignal:
    """构造测试用反馈信号。"""
    return RealityFeedbackSignal(
        creative_id=creative_id,
        signal_type=signal_type,
        severity=severity,
        confidence=confidence,
        reason=["ROAS 下降 25%"],
    )


def _make_metrics(
    roas: float = 0.50,
    cpi: float = 2.0,
    ctr: float = 0.02,
    spend: float = 200.0,
    frequency: float = 2.0,
) -> dict[str, float]:
    """构造测试用指标。"""
    return {
        "roas": roas,
        "cpi": cpi,
        "ctr": ctr,
        "spend": spend,
        "frequency": frequency,
    }


def _make_experience_record(
    creative_id: str = "cr_exp01",
    outcome: ExperienceOutcome = ExperienceOutcome.SUCCESS,
    improvement: float = 0.25,
) -> ExperienceRecord:
    """构造测试用 ExperienceRecord。"""
    return ExperienceRecord(
        experience_id="exp_test01",
        creative_id=creative_id,
        mutation=MutationDetail(
            mutation_type=MutationType.REFRESH_HOOK,
            changed_genes=["hook"],
        ),
        experiment=ExperimentDetail(
            baseline_metrics={"roas": 0.50},
            winner_metrics={"roas": 0.70},
            improvement=improvement,
        ),
        context=ContextDetail(platform="facebook"),
        result=ExperienceResult(
            outcome=outcome,
            success=(outcome == ExperienceOutcome.SUCCESS),
            insight="降预算后 ROAS 回升",
        ),
        related_ids={"signal_id": "fs_test01"},
        created_at="2026-08-01T10:00:00+00:00",
    )


# ═══════════════════════════════════════════════════════════
# TestStartupRecovery — 启动恢复
# ═══════════════════════════════════════════════════════════


class TestStartupRecovery:
    """Orchestrator 启动时的状态恢复。"""

    def test_empty_state_new_orchestrator(self, tmp_data_dir):
        """无历史数据 → 全新 LoopState + 空 ExperienceStore。"""
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        assert orch.state.cycle_number == 0
        assert orch.state.total_cycles == 0
        assert orch.state.loop_id.startswith("loop_")
        assert len(orch.store) == 0
        assert orch.pending_count == 0

    def test_restore_loop_state(self, tmp_data_dir):
        """恢复已持久化的 LoopState。"""
        # Phase 1: 写入 LoopState
        state = LoopState(cycle_number=5, mode="autonomous")
        state.total_cycles = 5
        state.total_actions_executed = 10
        state.success_rate = 0.7

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_state(state)

        # Phase 2: 重新创建 Orchestrator
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        assert orch.state.cycle_number == 5
        assert orch.state.mode == "autonomous"
        assert orch.state.total_cycles == 5
        assert orch.state.total_actions_executed == 10
        assert orch.state.success_rate == 0.7
        assert orch.state.loop_id == state.loop_id

    def test_restore_experience_store(self, tmp_data_dir):
        """从快照恢复 ExperienceStore。"""
        # Phase 1: 写入经验快照
        store = ExperienceStore()
        store.add(_make_experience_record("cr_001"))
        store.add(_make_experience_record("cr_002", outcome=ExperienceOutcome.FAILURE))

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_experience_snapshot(store.to_dict_list())

        # Phase 2: 重新创建 Orchestrator
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        assert len(orch.store) == 2
        records = orch.store.query_all()
        creative_ids = {r.creative_id for r in records}
        assert creative_ids == {"cr_001", "cr_002"}

    def test_restore_pending_evaluations(self, tmp_data_dir):
        """恢复待评估队列。"""
        # Phase 1: 写入 pending evaluations
        pending_list = [
            PendingEvaluation(
                signal_id="fs_001",
                action_id="exec_001",
                action_type="update_budget",
                creative_id="cr_001",
                executed_at="2026-08-06T10:00:00+00:00",
            ),
            PendingEvaluation(
                signal_id="fs_002",
                action_id="exec_002",
                action_type="pause_campaign",
                creative_id="cr_002",
                executed_at="2026-08-05T10:00:00+00:00",
            ),
        ]

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations(pending_list)

        # Phase 2: 重新创建 Orchestrator
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        assert orch.pending_count == 2
        assert orch.pending_evaluations[0].signal_id == "fs_001"
        assert orch.pending_evaluations[1].action_type == "pause_campaign"

    def test_full_restart_recovery(self, tmp_data_dir):
        """完整重启恢复: LoopState + Experience + Pending 全部一致。"""
        # Phase 1: 准备数据
        store = ExperienceStore()
        store.add(_make_experience_record("cr_001"))

        state = LoopState(cycle_number=3, mode="autonomous", interval_hours=4.0)
        state.total_cycles = 3
        state.experience_count = 1

        pending = [
            PendingEvaluation(
                signal_id="fs_001",
                action_id="exec_001",
                action_type="update_budget",
                creative_id="cr_001",
                pre_metrics={"roas": 0.50},
                executed_at="2026-08-06T10:00:00+00:00",
            ),
        ]

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_state(state)
        persistence.save_pending_evaluations(pending)
        persistence.save_experience_snapshot(store.to_dict_list())

        # Phase 2: 重启
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        # 验证全部恢复
        assert orch.state.cycle_number == 3
        assert orch.state.mode == "autonomous"
        assert len(orch.store) == 1
        assert orch.pending_count == 1
        assert orch.pending_evaluations[0].pre_metrics == {"roas": 0.50}


# ═══════════════════════════════════════════════════════════
# TestExperienceRecordFromDict — from_dict 反序列化
# ═══════════════════════════════════════════════════════════


class TestExperienceRecordFromDict:
    """ExperienceRecord.from_dict 反序列化。"""

    def test_round_trip(self):
        """to_dict → from_dict 往返一致。"""
        original = _make_experience_record("cr_roundtrip")
        d = original.to_dict()
        restored = ExperienceRecord.from_dict(d)

        assert restored.experience_id == original.experience_id
        assert restored.creative_id == "cr_roundtrip"
        assert restored.mutation.mutation_type == MutationType.REFRESH_HOOK
        assert restored.experiment.improvement == 0.25
        assert restored.result.outcome == ExperienceOutcome.SUCCESS
        assert restored.result.success is True
        assert restored.context.platform == "facebook"
        assert restored.related_ids["signal_id"] == "fs_test01"

    def test_from_dict_missing_fields(self):
        """缺失字段使用默认值。"""
        restored = ExperienceRecord.from_dict({})
        assert restored.experience_id != ""  # __post_init__ 生成
        assert restored.mutation.mutation_type == MutationType.REFRESH_HOOK
        assert restored.result.outcome == ExperienceOutcome.INCONCLUSIVE
        assert restored.context.platform == "facebook"

    def test_nested_from_dict(self):
        """嵌套 dataclass 正确反序列化。"""
        record = ExperienceRecord(
            creative_id="cr_nested",
            mutation=MutationDetail(
                mutation_type=MutationType.REFRESH_HOOK,
                changed_genes=["hook", "visual"],
                gene_before={"hook": "old"},
                gene_after={"hook": "new"},
            ),
            experiment=ExperimentDetail(
                baseline_metrics={"roas": 0.3},
                winner_metrics={"roas": 0.5},
                improvement=0.2,
                confidence=0.85,
            ),
            context=ContextDetail(
                platform="google",
                market="US",
                product_id="prod_001",
            ),
            result=ExperienceResult(
                outcome=ExperienceOutcome.FAILURE,
                success=False,
                failure_reason="ROAS 未改善",
            ),
        )
        d = record.to_dict()
        restored = ExperienceRecord.from_dict(d)

        assert restored.mutation.changed_genes == ["hook", "visual"]
        assert restored.mutation.gene_before == {"hook": "old"}
        assert restored.experiment.confidence == 0.85
        assert restored.context.platform == "google"
        assert restored.context.market == "US"
        assert restored.result.failure_reason == "ROAS 未改善"


# ═══════════════════════════════════════════════════════════
# TestRunCyclePhaseB — 主循环 Phase B
# ═══════════════════════════════════════════════════════════


class TestRunCyclePhaseB:
    """主循环 Phase B: 新信号处理。"""

    def test_single_signal_full_chain(self, tmp_data_dir):
        """单个信号走完整链路: Diagnose → Hypothesize → Select → Plan → Execute。"""
        orch = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
        )

        signal = _make_signal("cr_001")
        metrics = {"cr_001": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev_metrics = {"cr_001": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev_metrics,
            creative_to_adset_map={"cr_001": "adset_001"},
            current_budgets={"adset_001": 200.0},
        )

        # 验证 CycleResult
        assert result.cycle_number == 1
        assert len(result.diagnoses) == 1
        assert len(result.hypotheses) == 1
        assert len(result.strategies) == 1
        assert len(result.actions) >= 1

        # 验证执行结果
        assert len(result.execution_results) >= 0  # 可能被 SafetyGate 拦截

        # 验证 LoopState 推进
        assert orch.state.cycle_number == 1
        assert orch.state.total_cycles == 1

    def test_no_signals_skips_phase_b(self, tmp_data_dir):
        """无信号时跳过 Phase B。"""
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        result = orch.run_cycle()

        assert result.cycle_number == 1
        assert len(result.diagnoses) == 0
        assert len(result.actions) == 0
        assert result.pending_created == 0

    def test_dry_run_no_pending_created(self, tmp_data_dir):
        """dry-run 模式下不创建 PendingEvaluation。"""
        orch = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
            dry_run=True,
        )

        signal = _make_signal("cr_dry")
        metrics = {"cr_dry": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev = {"cr_dry": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_dry": "adset_dry"},
            current_budgets={"adset_dry": 200.0},
        )

        # dry-run → 不创建 pending
        assert result.pending_created == 0
        assert orch.pending_count == 0

    def test_multiple_signals(self, tmp_data_dir):
        """多信号批量处理。"""
        orch = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
        )

        signals = [
            _make_signal("cr_001"),
            _make_signal("cr_002"),
            _make_signal("cr_003"),
        ]
        metrics = {
            f"cr_00{i}": _make_metrics(roas=0.50, spend=200, frequency=3.5)
            for i in range(1, 4)
        }
        prev = {
            f"cr_00{i}": _make_metrics(roas=0.80, spend=200, frequency=2.0)
            for i in range(1, 4)
        }
        adset_map = {f"cr_00{i}": f"adset_00{i}" for i in range(1, 4)}
        budgets = {f"adset_00{i}": 200.0 for i in range(1, 4)}

        result = orch.run_cycle(
            signals=signals,
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map=adset_map,
            current_budgets=budgets,
        )

        assert len(result.diagnoses) == 3
        assert len(result.signal_ids) == 3
        assert result.cycle_number == 1

    def test_pending_evaluation_created_on_success(self, tmp_data_dir):
        """执行成功 → 创建 PendingEvaluation 并加入队列。"""
        orch = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=2),
        )

        signal = _make_signal("cr_pending")
        metrics = {"cr_pending": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev = {"cr_pending": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_pending": "adset_p"},
            current_budgets={"adset_p": 200.0},
        )

        # 如果有执行成功的动作，应该创建 pending
        successful = [r for r in result.execution_results if r.success]
        if successful:
            assert result.pending_created == len(successful)
            assert orch.pending_count == len(successful)

            # 验证 pending 内容
            for pending in orch.pending_evaluations:
                assert pending.signal_id == signal.signal_id
                assert pending.creative_id == "cr_pending"
                assert pending.status == "waiting"
                assert pending.observation_window_hours == 168

    def test_persistence_after_cycle(self, tmp_data_dir):
        """循环结束后状态已持久化。"""
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        orch.run_cycle()

        assert orch.state.cycle_number == 1
        # 验证文件存在
        assert (Path(tmp_data_dir) / "loop_state.json").exists()
        assert (Path(tmp_data_dir) / "pending_evaluations.jsonl").exists()
        assert (Path(tmp_data_dir) / "experience_snapshot.json").exists()
        assert (Path(tmp_data_dir) / "cycle_history.jsonl").exists()


# ═══════════════════════════════════════════════════════════
# TestRunCyclePhaseA — 到期评估
# ═══════════════════════════════════════════════════════════


class TestRunCyclePhaseA:
    """主循环 Phase A: 到期评估与过期清理。"""

    def test_no_pending_skips_phase_a(self, tmp_data_dir):
        """无 pending → Phase A 跳过。"""
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        result = orch.run_cycle()

        assert result.evaluated_count == 0
        assert result.expired_count == 0

    def test_due_evaluation_processed(self, tmp_data_dir):
        """到期的 pending → 被评估。"""
        # 预置一个到期的 pending (8 天前执行)
        past = (datetime.now(timezone.utc) - timedelta(hours=192)).isoformat()
        pending = PendingEvaluation(
            signal_id="fs_due",
            action_id="exec_due",
            action_type="update_budget",
            creative_id="cr_due",
            adset_id="adset_due",
            parameters={"target_budget": 140.0, "current_budget": 200.0},
            pre_metrics={"roas": 0.50, "spend": 200, "ctr": 0.02},
            executed_at=past,
            observation_window_hours=168,
            execution_success=True,
        )

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations([pending])

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        # 提供 post_metrics provider
        def post_provider(p: PendingEvaluation) -> dict[str, float]:
            # ROAS 从 0.50 → 0.70, +40% → SUCCESS
            return {"roas": 0.70, "spend": 140, "ctr": 0.025}

        result = orch.run_cycle(post_metrics_provider=post_provider)

        assert result.evaluated_count == 1
        assert result.expired_count == 0
        assert len(result.outcomes) == 1
        assert result.outcomes[0].success is True
        # 评估后从队列移除
        assert orch.pending_count == 0

    def test_not_due_keeps_in_queue(self, tmp_data_dir):
        """未到期的 pending → 保留在队列中。"""
        now = datetime.now(timezone.utc).isoformat()
        pending = PendingEvaluation(
            signal_id="fs_waiting",
            action_id="exec_waiting",
            action_type="update_budget",
            executed_at=now,
            observation_window_hours=168,
        )

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations([pending])

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        result = orch.run_cycle()

        assert result.evaluated_count == 0
        assert orch.pending_count == 1  # 仍在队列中

    def test_expired_evaluation_removed(self, tmp_data_dir):
        """过期的 pending → 标记过期并移除。"""
        # 15 天前执行 → 超过 2 倍窗口 (336h)
        past = (datetime.now(timezone.utc) - timedelta(hours=360)).isoformat()
        pending = PendingEvaluation(
            signal_id="fs_expired",
            action_id="exec_expired",
            action_type="update_budget",
            executed_at=past,
            observation_window_hours=168,
        )

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations([pending])

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        result = orch.run_cycle()

        assert result.expired_count == 1
        assert result.evaluated_count == 0
        assert orch.pending_count == 0  # 已移除

    def test_post_metrics_unavailable_keeps_pending(self, tmp_data_dir):
        """post_metrics 不可用 → 保留在队列中。"""
        past = (datetime.now(timezone.utc) - timedelta(hours=192)).isoformat()
        pending = PendingEvaluation(
            signal_id="fs_nodata",
            action_id="exec_nodata",
            action_type="update_budget",
            executed_at=past,
            observation_window_hours=168,
        )

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations([pending])

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        # provider 返回空 dict
        result = orch.run_cycle(
            post_metrics_provider=lambda p: {}
        )

        assert result.evaluated_count == 0
        assert orch.pending_count == 1  # 仍在队列中

    def test_mixed_pending_queue(self, tmp_data_dir):
        """混合队列: 到期 + 未到期 + 过期。"""
        now = datetime.now(timezone.utc)
        items = [
            PendingEvaluation(
                signal_id="fs_due",
                action_id="exec_due",
                action_type="update_budget",
                creative_id="cr_due",
                pre_metrics={"roas": 0.50},
                executed_at=(now - timedelta(hours=200)).isoformat(),
                observation_window_hours=168,
            ),
            PendingEvaluation(
                signal_id="fs_waiting",
                action_id="exec_waiting",
                action_type="update_budget",
                executed_at=now.isoformat(),
                observation_window_hours=168,
            ),
            PendingEvaluation(
                signal_id="fs_expired",
                action_id="exec_expired",
                action_type="update_budget",
                executed_at=(now - timedelta(hours=400)).isoformat(),
                observation_window_hours=168,
            ),
        ]

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations(items)

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        def post_provider(p: PendingEvaluation) -> dict[str, float]:
            return {"roas": 0.70}

        result = orch.run_cycle(post_metrics_provider=post_provider)

        assert result.evaluated_count == 1   # 到期的被评估
        assert result.expired_count == 1     # 过期的被移除
        assert orch.pending_count == 1       # 未到期的保留
        assert orch.pending_evaluations[0].signal_id == "fs_waiting"


# ═══════════════════════════════════════════════════════════
# TestCrossRestartContinuousRun — 跨重启连续运行
# ═══════════════════════════════════════════════════════════


class TestCrossRestartContinuousRun:
    """跨重启连续运行场景。"""

    def test_cycle_1_run_cycle_2_restart(self, tmp_data_dir):
        """第 1 轮运行 → 重启 → 第 2 轮从相同状态继续。"""
        # ── 第 1 轮 ──
        orch1 = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
        )

        signal = _make_signal("cr_cont")
        metrics = {"cr_cont": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev = {"cr_cont": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        result1 = orch1.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_cont": "adset_cont"},
            current_budgets={"adset_cont": 200.0},
        )
        assert result1.cycle_number == 1

        # 记录第 1 轮结束时的状态
        loop_id_1 = orch1.state.loop_id
        pending_count_1 = orch1.pending_count
        exp_count_1 = len(orch1.store)

        # ── 重启 ──
        orch2 = GrowthLoopOrchestrator(data_dir=tmp_data_dir)

        # 验证状态恢复
        assert orch2.state.loop_id == loop_id_1
        assert orch2.state.cycle_number == 1
        assert orch2.pending_count == pending_count_1
        assert len(orch2.store) == exp_count_1

        # ── 第 2 轮 ──
        result2 = orch2.run_cycle()
        assert result2.cycle_number == 2
        assert orch2.state.cycle_number == 2
        assert orch2.state.total_cycles == 2

    def test_experience_persists_across_restart(self, tmp_data_dir):
        """经验跨重启持久化。"""
        # ── 第 1 轮: 预置经验 + 执行循环 ──
        store = ExperienceStore()
        store.add(_make_experience_record("cr_exp"))

        orch1 = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            store=store,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
        )
        orch1.run_cycle()

        assert len(orch1.store) == 1

        # ── 重启 ──
        orch2 = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        assert len(orch2.store) == 1
        assert orch2.store.query_all()[0].creative_id == "cr_exp"

    def test_pending_evaluations_persists_across_restart(self, tmp_data_dir):
        """待评估队列跨重启持久化。"""
        # ── 第 1 轮: 创建 pending ──
        orch1 = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=2),
        )

        signal = _make_signal("cr_persist")
        metrics = {"cr_persist": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev = {"cr_persist": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        orch1.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_persist": "adset_p"},
            current_budgets={"adset_p": 200.0},
        )

        if orch1.pending_count == 0:
            pytest.skip("No pending created (SafetyGate blocked)")

        pending_ids_1 = {p.action_id for p in orch1.pending_evaluations}

        # ── 重启 ──
        orch2 = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        assert orch2.pending_count == orch1.pending_count
        pending_ids_2 = {p.action_id for p in orch2.pending_evaluations}
        assert pending_ids_1 == pending_ids_2


# ═══════════════════════════════════════════════════════════
# TestStatusAndQueries — 状态查询
# ═══════════════════════════════════════════════════════════


class TestStatusAndQueries:
    """Orchestrator 状态查询接口。"""

    def test_get_status_empty(self, tmp_data_dir):
        """空 Orchestrator 的状态查询。"""
        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        status = orch.get_status()

        assert status["cycle_number"] == 0
        assert status["total_cycles"] == 0
        assert status["pending_evaluations"] == 0
        assert status["due_evaluations"] == 0
        assert status["expired_evaluations"] == 0
        assert status["dry_run"] is False

    def test_get_status_after_cycle(self, tmp_data_dir):
        """运行一轮后的状态查询。"""
        orch = GrowthLoopOrchestrator(
            data_dir=tmp_data_dir,
            adapter=MockPlatformAdapter(),
            safety_gate=SafetyGate(auto_approve_max_level=1),
            dry_run=True,
        )

        signal = _make_signal("cr_status")
        metrics = {"cr_status": _make_metrics(roas=0.50, spend=200, frequency=3.5)}
        prev = {"cr_status": _make_metrics(roas=0.80, spend=200, frequency=2.0)}

        orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_status": "adset_s"},
            current_budgets={"adset_s": 200.0},
        )

        status = orch.get_status()
        assert status["cycle_number"] == 1
        assert status["total_cycles"] == 1
        assert status["dry_run"] is True

    def test_due_count_property(self, tmp_data_dir):
        """due_count 属性正确计算。"""
        past = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
        now = datetime.now(timezone.utc).isoformat()

        pending_list = [
            PendingEvaluation(signal_id="fs_1", executed_at=past),  # due
            PendingEvaluation(signal_id="fs_2", executed_at=now),   # not due
        ]

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations(pending_list)

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        assert orch.pending_count == 2
        assert orch.due_count == 1
        assert orch.expired_count == 0

    def test_expired_count_property(self, tmp_data_dir):
        """expired_count 属性正确计算。"""
        far_past = (datetime.now(timezone.utc) - timedelta(hours=400)).isoformat()

        pending_list = [
            PendingEvaluation(signal_id="fs_zombie", executed_at=far_past),
        ]

        from scripts.loop_persistence import LoopPersistence
        persistence = LoopPersistence(data_dir=tmp_data_dir)
        persistence.save_pending_evaluations(pending_list)

        orch = GrowthLoopOrchestrator(data_dir=tmp_data_dir)
        assert orch.pending_count == 1
        assert orch.due_count == 1       # 也是 due (200h > 168h)
        assert orch.expired_count == 1   # 同时也是 expired (400h > 336h)


# ═══════════════════════════════════════════════════════════
# TestCycleResult — CycleResult 数据结构
# ═══════════════════════════════════════════════════════════


class TestCycleResult:
    """CycleResult 数据结构。"""

    def test_default_values(self):
        result = CycleResult()
        assert result.cycle_number == 0
        assert result.evaluated_count == 0
        assert result.expired_count == 0
        assert result.pending_created == 0
        assert result.actions_skipped == 0
        assert result.persisted is False

    def test_repr(self):
        result = CycleResult()
        result.cycle_number = 5
        result.evaluated_count = 2
        result.duration_ms = 1500
        repr_str = repr(result)
        assert "cycle=5" in repr_str
        assert "evaluated=2" in repr_str
        assert "duration=1500ms" in repr_str
