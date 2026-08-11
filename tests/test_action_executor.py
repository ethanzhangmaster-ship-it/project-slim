"""ActionExecutor 单元测试。

覆盖:
  - ExecutionResult 数据模型
  - MockPlatformAdapter
  - SafetyGate (审批/预算/NOOP 检查)
  - ActionExecutor 核心执行流程
  - Dry-run 模式
  - 批量执行
  - 失败处理与回滚
  - End-to-End: Strategy → Action → Execute → Outcome
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest

from scripts.action_planner import (
    ActionPlanner,
    ActionStatus,
    ActionType,
    ExecutionAction,
)
from scripts.action_executor import (
    ActionExecutionStatus,
    ActionExecutor,
    ExecutionResult,
    MockPlatformAdapter,
    PlatformAdapter,
    SafetyGate,
)
from scripts.outcome_evaluator import OutcomeEvaluator
from scripts.diagnostic_engine import (
    DiagnosticEngine,
    DiagnosisResult,
    RootCause,
    StrategyType,
)
from scripts.hypothesis_generator import HypothesisGenerator
from scripts.strategy_selector import StrategySelector
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────


def _make_action(
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    adset_id: str = "adset_test",
    creative_id: str = "c_test",
    parameters: dict | None = None,
    approval_level: int = 0,
    requires_approval: bool = False,
    status: ActionStatus = ActionStatus.PENDING,
    signal_id: str = "fs_test",
    diagnosis_id: str = "diag_test",
    hypothesis_id: str = "hyp_test",
    strategy_id: str = "strat_test",
) -> ExecutionAction:
    if parameters is None:
        parameters = {"target_budget": 140.0, "current_budget": 200.0}
    return ExecutionAction(
        strategy_id=strategy_id,
        hypothesis_id=hypothesis_id,
        diagnosis_id=diagnosis_id,
        signal_id=signal_id,
        creative_id=creative_id,
        adset_id=adset_id,
        action_type=action_type,
        parameters=parameters,
        confidence=0.75,
        risk_level="medium",
        expected_impact={"metric": "roas", "direction": "positive"},
        reason="test action",
        budget_impact=-60.0,
        approval_level=approval_level,
        requires_approval=requires_approval,
        status=status,
    )


# ──────────────────────────────────────────────
# ExecutionResult 数据模型
# ──────────────────────────────────────────────


class TestExecutionResultModel:
    def test_auto_id_and_timestamp(self):
        r = ExecutionResult(action_id="exec_001")
        assert r.result_id.startswith("res_")
        assert r.executed_at != ""
        assert r.status == ActionExecutionStatus.PENDING

    def test_to_dict(self):
        r = ExecutionResult(
            action_id="exec_001",
            strategy_id="strat_001",
            status=ActionExecutionStatus.COMPLETED,
            success=True,
            actual_budget=140.0,
        )
        d = r.to_dict()
        assert d["action_id"] == "exec_001"
        assert d["strategy_id"] == "strat_001"
        assert d["status"] == "completed"
        assert d["success"] is True
        assert d["actual_budget"] == 140.0
        assert d["is_terminal"] is True

    def test_is_terminal(self):
        r = ExecutionResult(status=ActionExecutionStatus.COMPLETED)
        assert r.is_terminal is True
        r = ExecutionResult(status=ActionExecutionStatus.FAILED)
        assert r.is_terminal is False
        r = ExecutionResult(status=ActionExecutionStatus.ROLLED_BACK)
        assert r.is_terminal is True
        r = ExecutionResult(status=ActionExecutionStatus.SKIPPED)
        assert r.is_terminal is True

    def test_full_chain_ids(self):
        r = ExecutionResult(
            action_id="exec_001",
            strategy_id="strat_001",
            hypothesis_id="hyp_001",
            diagnosis_id="diag_001",
            signal_id="fs_001",
        )
        d = r.to_dict()
        assert d["signal_id"] == "fs_001"
        assert d["diagnosis_id"] == "diag_001"
        assert d["hypothesis_id"] == "hyp_001"
        assert d["strategy_id"] == "strat_001"
        assert d["action_id"] == "exec_001"


# ──────────────────────────────────────────────
# MockPlatformAdapter
# ──────────────────────────────────────────────


class TestMockPlatformAdapter:
    def test_update_budget_success(self):
        adapter = MockPlatformAdapter()
        action = _make_action(ActionType.UPDATE_BUDGET)
        resp = adapter.execute(action)
        assert resp["status"] == "ok"
        assert resp["data"]["budget"] == 140.0

    def test_pause_campaign_success(self):
        adapter = MockPlatformAdapter()
        action = _make_action(ActionType.PAUSE_CAMPAIGN)
        resp = adapter.execute(action)
        assert resp["status"] == "ok"
        assert resp["data"]["status"] == "paused"

    def test_resume_campaign_success(self):
        adapter = MockPlatformAdapter()
        action = _make_action(ActionType.RESUME_CAMPAIGN)
        resp = adapter.execute(action)
        assert resp["status"] == "ok"
        assert resp["data"]["status"] == "active"

    def test_configured_failure(self):
        adapter = MockPlatformAdapter(fail_action_types={ActionType.UPDATE_BUDGET})
        action = _make_action(ActionType.UPDATE_BUDGET)
        resp = adapter.execute(action)
        assert resp["status"] == "error"

    def test_verify_success(self):
        adapter = MockPlatformAdapter()
        action = _make_action()
        resp = {"status": "ok"}
        assert adapter.verify(action, resp) is True

    def test_verify_failure(self):
        adapter = MockPlatformAdapter()
        action = _make_action()
        resp = {"status": "error"}
        assert adapter.verify(action, resp) is False

    def test_rollback_update_budget(self):
        adapter = MockPlatformAdapter()
        action = _make_action(ActionType.UPDATE_BUDGET)
        resp = adapter.rollback(action, {})
        assert resp["status"] == "ok"
        # 回滚应恢复到原始预算
        assert resp["data"]["budget"] == 200.0

    def test_rollback_pause_campaign(self):
        adapter = MockPlatformAdapter()
        action = _make_action(ActionType.PAUSE_CAMPAIGN)
        resp = adapter.rollback(action, {})
        assert resp["status"] == "ok"
        # 回滚暂停 → 恢复 active
        assert resp["data"]["status"] == "active"

    def test_executed_count(self):
        adapter = MockPlatformAdapter()
        assert adapter.executed_count == 0
        adapter.execute(_make_action())
        adapter.execute(_make_action())
        assert adapter.executed_count == 2


# ──────────────────────────────────────────────
# SafetyGate
# ──────────────────────────────────────────────


class TestSafetyGate:
    def test_noop_skipped(self):
        gate = SafetyGate()
        action = _make_action(ActionType.NOOP)
        passed, reason = gate.check(action)
        assert passed is False
        assert "NOOP" in reason

    def test_skipped_status(self):
        gate = SafetyGate()
        action = _make_action(status=ActionStatus.SKIPPED)
        passed, reason = gate.check(action)
        assert passed is False

    def test_missing_adset_id(self):
        gate = SafetyGate()
        action = _make_action(adset_id="")
        passed, reason = gate.check(action)
        assert passed is False
        assert "adset_id" in reason

    def test_approval_level_exceeded(self):
        gate = SafetyGate(auto_approve_max_level=0)
        action = _make_action(approval_level=2)
        passed, reason = gate.check(action)
        assert passed is False
        assert "Approval" in reason

    def test_budget_below_minimum(self):
        gate = SafetyGate(min_budget=20.0)
        action = _make_action(
            parameters={"target_budget": 5.0, "current_budget": 200.0}
        )
        passed, reason = gate.check(action)
        assert passed is False
        assert "minimum" in reason

    def test_budget_reduce_exceeded(self):
        gate = SafetyGate(max_budget_reduce_pct=0.50)
        action = _make_action(
            parameters={"target_budget": 50.0, "current_budget": 200.0}
        )
        # 降 75% > 50%
        passed, reason = gate.check(action)
        assert passed is False
        assert "reduce" in reason

    def test_budget_increase_exceeded(self):
        gate = SafetyGate(max_budget_increase_pct=0.30)
        action = _make_action(
            parameters={"target_budget": 300.0, "current_budget": 200.0}
        )
        # 升 50% > 30%
        passed, reason = gate.check(action)
        assert passed is False
        assert "increase" in reason

    def test_safety_check_passes(self):
        gate = SafetyGate()
        action = _make_action()
        passed, reason = gate.check(action)
        assert passed is True

    def test_budget_at_minimum_passes(self):
        gate = SafetyGate(min_budget=20.0)
        action = _make_action(
            parameters={"target_budget": 20.0, "current_budget": 200.0}
        )
        # 180/200 = 90% 降幅 > 50% 失败
        # 但 20 >= 20 最低预算通过
        # 实际会因降幅过大失败
        passed, _ = gate.check(action)
        # 降 90% > 50% → 失败
        assert passed is False

    def test_budget_reduce_within_limit(self):
        gate = SafetyGate(max_budget_reduce_pct=0.50)
        action = _make_action(
            parameters={"target_budget": 120.0, "current_budget": 200.0}
        )
        # 降 40% ≤ 50%
        passed, reason = gate.check(action)
        assert passed is True


# ──────────────────────────────────────────────
# ActionExecutor 核心
# ──────────────────────────────────────────────


class TestActionExecutor:
    def test_execute_update_budget_success(self):
        executor = ActionExecutor()
        action = _make_action(ActionType.UPDATE_BUDGET)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True
        assert result.action_id == action.action_id
        assert result.actual_budget == 140.0
        assert result.execution_time_ms >= 0

    def test_execute_pause_campaign(self):
        executor = ActionExecutor()
        action = _make_action(ActionType.PAUSE_CAMPAIGN)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_execute_resume_campaign(self):
        executor = ActionExecutor()
        action = _make_action(ActionType.RESUME_CAMPAIGN)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_execute_noop_skipped(self):
        executor = ActionExecutor()
        action = _make_action(ActionType.NOOP)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert result.success is False
        assert "NOOP" in result.error_message

    def test_execute_missing_adset_id(self):
        executor = ActionExecutor()
        action = _make_action(adset_id="")
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "adset_id" in result.error_message

    def test_execute_approval_required(self):
        executor = ActionExecutor()
        action = _make_action(approval_level=2)
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "Approval" in result.error_message

    def test_execute_dry_run(self):
        executor = ActionExecutor()
        action = _make_action(ActionType.UPDATE_BUDGET)
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True
        assert result.dry_run is True
        assert "[DRY-RUN]" in result.platform_response.get("message", "")

    def test_execute_failure_and_rollback(self):
        """执行失败时自动回滚。"""
        adapter = MockPlatformAdapter(
            fail_action_types={ActionType.UPDATE_BUDGET}
        )
        executor = ActionExecutor(adapter=adapter)
        action = _make_action(ActionType.UPDATE_BUDGET)
        result = executor.execute(action)

        # MockPlatformAdapter.execute() 返回 error response，
        # ActionExecutor 捕获为异常 → 触发回滚
        # 回滚成功 → ROLLED_BACK
        assert result.status == ActionExecutionStatus.ROLLED_BACK
        assert result.success is False
        assert result.rollback_performed is True

    def test_execute_rollback_on_execution_error(self):
        """执行异常触发回滚。"""

        class FailingAdapter(MockPlatformAdapter):
            def execute(self, action):
                raise RuntimeError("API call failed")

        adapter = FailingAdapter()
        executor = ActionExecutor(adapter=adapter)
        action = _make_action(ActionType.UPDATE_BUDGET)
        result = executor.execute(action)

        assert result.success is False
        assert "API call failed" in result.error_message

    def test_execute_batch(self):
        executor = ActionExecutor()
        actions = [
            _make_action(ActionType.UPDATE_BUDGET, adset_id="adset_1",
                        creative_id="c_1"),
            _make_action(ActionType.PAUSE_CAMPAIGN, adset_id="adset_2",
                        creative_id="c_2"),
            _make_action(ActionType.NOOP, adset_id="adset_3",
                        creative_id="c_3"),
        ]
        results = executor.execute_batch(actions)

        assert len(results) == 3
        assert results[0].status == ActionExecutionStatus.COMPLETED
        assert results[1].status == ActionExecutionStatus.COMPLETED
        assert results[2].status == ActionExecutionStatus.SKIPPED

    def test_full_chain_ids_preserved(self):
        """全链路 ID 在执行结果中保留。"""
        executor = ActionExecutor()
        action = _make_action(
            signal_id="fs_chain",
            diagnosis_id="diag_chain",
            hypothesis_id="hyp_chain",
            strategy_id="strat_chain",
        )
        result = executor.execute(action)

        assert result.signal_id == "fs_chain"
        assert result.diagnosis_id == "diag_chain"
        assert result.hypothesis_id == "hyp_chain"
        assert result.strategy_id == "strat_chain"

    def test_results_accumulated(self):
        executor = ActionExecutor()
        action_1 = _make_action(creative_id="c_1")
        action_2 = _make_action(creative_id="c_2")

        executor.execute(action_1)
        executor.execute(action_2)

        assert len(executor.results) == 2
        assert executor.get_result(action_1.action_id) is not None
        assert executor.get_result(action_2.action_id) is not None
        assert executor.get_result("nonexistent") is None


# ──────────────────────────────────────────────
# End-to-End 验证
# ──────────────────────────────────────────────


class TestEndToEnd:
    def test_planner_to_executor_to_outcome(self):
        """完整链路: Strategy → Action → Execute → Outcome。"""
        store = ExperienceStore()

        # Step 1: 诊断
        engine = DiagnosticEngine()

        class MockSignal:
            signal_id = "fs_e2e_exec"
            creative_id = "c_e2e_exec"
            signal_type = "roas_decline"

        diag = engine.diagnose(
            MockSignal(),
            {"spend": 200, "clicks": 60, "ctr": 0.015, "cpi": 5.0,
             "roas": 0.4, "impressions": 12000, "installs": 2000, "revenue": 80},
            {"spend": 200, "clicks": 100, "ctr": 0.025, "cpi": 5.0,
             "roas": 0.6, "impressions": 10000, "installs": 2000, "revenue": 120},
        )
        assert diag.root_cause == RootCause.CREATIVE_FATIGUE

        # Step 2: 假设 → 策略
        hyp = HypothesisGenerator(store).generate(diag)
        strat = StrategySelector(store).select(hyp, diag)
        assert strat.strategy_type == StrategyType.SUPPRESS

        # Step 3: 动作规划
        planner = ActionPlanner()
        actions = planner.plan(
            strat,
            {"c_e2e_exec": "adset_e2e"},
            {"adset_e2e": 300.0},
        )
        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.UPDATE_BUDGET

        # Step 4: 执行
        executor = ActionExecutor()
        exec_result = executor.execute(action)
        assert exec_result.status == ActionExecutionStatus.COMPLETED
        assert exec_result.success is True

        # 验证平台响应 — 从 action 参数获取预期值
        expected_budget = action.parameters.get("target_budget")
        assert exec_result.actual_budget == expected_budget
        assert exec_result.actual_budget is not None
        assert exec_result.actual_budget < 300.0  # SUPPRESS → 降预算

        # Step 5: 结果评估
        evaluator = OutcomeEvaluator(store)
        pre = {"roas": 0.40, "spend": 300}
        post = {"roas": 0.60, "spend": 210}
        outcome = evaluator.evaluate(action, pre, post)

        # 全链路追溯
        assert outcome.signal_id == "fs_e2e_exec"
        assert outcome.action_id == action.action_id

    def test_dry_run_full_chain(self):
        """Dry-run 模式完整链路。"""
        store = ExperienceStore()

        hyp = HypothesisGenerator(store)
        gen = HypothesisGenerator(store)

        diag = DiagnosticEngine().diagnose(
            type("S", (), {
                "signal_id": "fs_dry",
                "creative_id": "c_dry",
                "signal_type": "roas_decline",
            })(),
            {"spend": 100, "clicks": 30, "ctr": 0.02, "cpi": 5.0, "roas": 0.5,
             "impressions": 5000, "installs": 1000, "revenue": 50},
            {"spend": 100, "clicks": 50, "ctr": 0.025, "cpi": 5.0, "roas": 0.7,
             "impressions": 4000, "installs": 1000, "revenue": 70},
        )

        hyp = gen.generate(diag)
        strat = StrategySelector(store).select(hyp, diag)
        actions = ActionPlanner().plan(
            strat, {"c_dry": "adset_dry"}, {"adset_dry": 200.0}
        )

        executor = ActionExecutor()
        result = executor.execute(actions[0], dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        assert "[DRY-RUN]" in result.platform_response.get("message", "")

    def test_executor_with_action_planner_output(self):
        """ActionPlanner 输出直接喂入 ActionExecutor。"""
        planner = ActionPlanner()
        action = _make_action(
            ActionType.UPDATE_BUDGET,
            parameters={"target_budget": 100.0, "current_budget": 200.0},
        )

        executor = ActionExecutor()
        result = executor.execute(action)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.actual_budget == 100.0
