"""P0 ApprovalGate V2 — 完整 12 场景汇总测试（Spec §10.1 发布门控）。

本文件是 Spec docs/p0_approval_gate_v2_spec.md §10.1 定义的 12 场景完整汇总。
每个场景对应 Spec 表格一行，是 Week 1 出口的发布门控。

场景分布：
  1-7: policy.evaluate() 分级（Day 4 test_policy_v2_scenarios_1_7.py 已覆盖）
  8-12: 开关控制 + dry_run 验证（Day 5 test_policy_v2_scenarios_8_12.py 已覆盖）

本文件作为汇总入口，重新声明 12 场景的契约，确保 Spec 与实现一致。
详细测试见各场景文件，此处用 parametrize 一次性验证 12 场景的 level + outcome 契约。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.config import ApprovalConfig
from src.execution.approval.dry_run_verifier import DryRunVerifier
from src.execution.approval.policy import (
    OUTCOME_ADMIN,
    OUTCOME_AUTO,
    OUTCOME_DENY,
    OUTCOME_MANUAL,
    ApprovalPolicy,
)
from src.execution.approval.v2_executor import V2ActionExecutor, V2ExecutionOutcome
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
)


# ──────────────────────────────────────────────
# 场景定义（Spec §10.1 表格）
# ──────────────────────────────────────────────


@dataclass
class Scenario:
    """Spec §10.1 测试矩阵一行。"""
    id: int
    name: str
    action: ExecutionAction
    risk: float
    confidence: float
    budget_amount_usd: float
    expected_level: int
    expected_outcome: str
    # 特殊配置
    level0_enabled: bool = True
    shadow_mode: bool = False
    dry_run_verify_enabled: bool = True
    # 场景 5 特殊：预填累计
    prefill_cumulative: float = 0.0
    # 场景 10/11 特殊：dry_run 结果
    dry_run_success: bool = True


SCENARIOS: list[Scenario] = [
    Scenario(
        id=1, name="小额 PAUSE + 低风险 + 高置信",
        action=ExecutionAction.PAUSE_CAMPAIGN,
        risk=0.1, confidence=0.95, budget_amount_usd=0.0,
        expected_level=0, expected_outcome=OUTCOME_AUTO,
    ),
    Scenario(
        id=2, name="小额 SCALE + 低风险 + 高置信",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.2, confidence=0.92, budget_amount_usd=30.0,
        expected_level=0, expected_outcome=OUTCOME_AUTO,
    ),
    Scenario(
        id=3, name="中额 SCALE",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        expected_level=1, expected_outcome=OUTCOME_MANUAL,
    ),
    Scenario(
        id=4, name="大额 SCALE",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.4, confidence=0.9, budget_amount_usd=600.0,
        expected_level=2, expected_outcome=OUTCOME_MANUAL,
    ),
    Scenario(
        id=5, name="超日累计",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.1, confidence=0.95, budget_amount_usd=30.0,
        expected_level=2, expected_outcome=OUTCOME_MANUAL,
        prefill_cumulative=180.0,  # 180 + 30 = 210 > 200
    ),
    Scenario(
        id=6, name="CREATE_RELEASE",
        action=ExecutionAction.CREATE_RELEASE,
        risk=0.05, confidence=0.99, budget_amount_usd=0.0,
        expected_level=2, expected_outcome=OUTCOME_ADMIN,
    ),
    Scenario(
        id=7, name="未知动作",
        action=ExecutionAction.PAUSE_CAMPAIGN,  # 构造后改为未知
        risk=0.1, confidence=0.95, budget_amount_usd=0.0,
        expected_level=2, expected_outcome=OUTCOME_DENY,
    ),
    Scenario(
        id=8, name="Level 0 关闭",
        action=ExecutionAction.PAUSE_CAMPAIGN,
        risk=0.1, confidence=0.95, budget_amount_usd=0.0,
        expected_level=1, expected_outcome=OUTCOME_MANUAL,  # fallback manual
        level0_enabled=False,
        dry_run_verify_enabled=False,  # Level 0 关闭时 fallback manual 不要求 dry_run
    ),
    Scenario(
        id=9, name="Shadow 模式",
        action=ExecutionAction.PAUSE_CAMPAIGN,
        risk=0.1, confidence=0.95, budget_amount_usd=0.0,
        expected_level=0, expected_outcome=OUTCOME_MANUAL,  # log only
        shadow_mode=True,
    ),
    Scenario(
        id=10, name="dry_run 验证通过",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        expected_level=1, expected_outcome=OUTCOME_MANUAL,  # policy 层 MANUAL，executor 升 AUTO
        dry_run_success=True,
    ),
    Scenario(
        id=11, name="dry_run 验证失败",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        expected_level=1, expected_outcome=OUTCOME_MANUAL,
        dry_run_success=False,
    ),
    Scenario(
        id=12, name="risk 过高",
        action=ExecutionAction.SCALE_BUDGET,
        risk=0.7, confidence=0.95, budget_amount_usd=30.0,
        expected_level=2, expected_outcome=OUTCOME_MANUAL,
    ),
]


# ──────────────────────────────────────────────
# 辅助构造
# ──────────────────────────────────────────────


def _build_intent(scenario: Scenario) -> ExecutionIntent:
    intent = ExecutionIntent(
        intent_id="",
        decision_id="dec_test",
        domain=ExecutionDomain.RELEASE if scenario.action == ExecutionAction.CREATE_RELEASE else ExecutionDomain.UA,
        action=scenario.action,
        target_id="p04_witch_merge",
        reason=scenario.name,
        confidence=scenario.confidence,
        expected_impact=None,
        risk_level=scenario.risk,
    )
    intent.budget_amount_usd = scenario.budget_amount_usd  # type: ignore[attr-defined]
    if scenario.id == 7:
        intent.action = "UNKNOWN_ACTION"  # type: ignore[assignment]
    return intent


def _build_policy(
    tmp_path: Path, scenario: Scenario, tracker: BudgetWindowTracker
) -> ApprovalPolicy:
    cfg = ApprovalConfig(
        auto_budget_threshold_usd=50.0,
        auto_daily_cumulative_usd=200.0,
        level1_budget_threshold_usd=500.0,
        auto_max_risk=0.3,
        auto_min_confidence=0.9,
        level1_max_risk=0.6,
        level0_enabled=scenario.level0_enabled,
        shadow_mode=scenario.shadow_mode,
        dry_run_verify_enabled=scenario.dry_run_verify_enabled,
        audit_log_dir=str(tmp_path),
    )
    return ApprovalPolicy(config=cfg, window_tracker=tracker)


# ──────────────────────────────────────────────
# 12 场景 parametrize：policy 层契约
# ──────────────────────────────────────────────


class TestPolicyLevelContract:
    """Spec §10.1：12 场景的 policy.evaluate() level + outcome 契约。

    这是 ApprovalGate V2 的核心发布门控：任何破坏此契约的改动都会被捕获。
    """

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: f"#{s.id}_{s.name}")
    def test_policy_level_and_outcome(
        self, tmp_path: Path, scenario: Scenario
    ):
        tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        # 场景 5：预填累计
        if scenario.prefill_cumulative > 0:
            tracker.record(
                "p04_witch_merge",
                str(ExecutionAction.SCALE_BUDGET),
                scenario.prefill_cumulative,
                "prefill",
                day=date.today(),
            )
        policy = _build_policy(tmp_path, scenario, tracker)
        intent = _build_intent(scenario)
        decision = policy.evaluate(intent)
        assert decision.level == scenario.expected_level, (
            f"scenario #{scenario.id} '{scenario.name}': "
            f"level={decision.level} expected={scenario.expected_level} "
            f"reason={decision.reason}"
        )
        assert decision.outcome == scenario.expected_outcome, (
            f"scenario #{scenario.id} '{scenario.name}': "
            f"outcome={decision.outcome} expected={scenario.expected_outcome}"
        )


# ──────────────────────────────────────────────
# 12 场景 parametrize：V2ActionExecutor 端到端
# ──────────────────────────────────────────────


@dataclass
class MockResult:
    success: bool = True
    error_message: str = ""
    response: Any = None


class MockV1Executor:
    def __init__(self, result: MockResult, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise = raise_exc
        self.call_count = 0

    def execute(self, action: Any, dry_run: bool = False) -> MockResult:
        self.call_count += 1
        if self._raise is not None:
            raise self._raise
        return self._result


class TestV2ExecutorEndToEnd:
    """12 场景的 V2ActionExecutor 端到端：executed + blocked_reason 契约。"""

    @pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: f"#{s.id}_{s.name}")
    def test_v2_executor_outcome(
        self, tmp_path: Path, scenario: Scenario
    ):
        tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
        if scenario.prefill_cumulative > 0:
            tracker.record(
                "p04_witch_merge",
                str(ExecutionAction.SCALE_BUDGET),
                scenario.prefill_cumulative,
                "prefill",
                day=date.today(),
            )
        policy = _build_policy(tmp_path, scenario, tracker)
        cfg = policy._cfg  # type: ignore[attr-defined]

        # Mock V1 executor：dry_run_success 控制返回
        v1_result = MockResult(success=scenario.dry_run_success)
        v1 = MockV1Executor(result=v1_result)
        verifier = DryRunVerifier(executor=v1)
        v2 = V2ActionExecutor(
            executor=v1,
            policy=policy,
            config=cfg,
            window_tracker=tracker,
            dry_run_verifier=verifier,
        )

        intent = _build_intent(scenario)

        @dataclass
        class _Action:
            action_id: str = f"act_scenario_{scenario.id}"
            expected_impact: Any = None

        action = _Action()
        outcome = v2.execute_with_approval(action, intent)

        # 验证 executed 契约
        if scenario.expected_outcome == OUTCOME_DENY:
            assert outcome.executed is False, f"#{scenario.id}: DENY should not execute"
        elif scenario.expected_outcome == OUTCOME_ADMIN:
            assert outcome.executed is False, f"#{scenario.id}: ADMIN should not execute"
        elif scenario.expected_level == 2:
            assert outcome.executed is False, f"#{scenario.id}: Level 2 should not execute"
        elif scenario.expected_level == 0 and scenario.shadow_mode:
            assert outcome.executed is False, f"#{scenario.id}: shadow should not execute"
        elif scenario.expected_level == 0 and not scenario.shadow_mode and scenario.level0_enabled:
            assert outcome.executed is True, f"#{scenario.id}: Level 0 should execute"
        elif scenario.expected_level == 0 and not scenario.level0_enabled:
            # 场景 8: Level 0 关闭 → fallback manual → 阻塞
            assert outcome.executed is False, f"#{scenario.id}: Level 0 disabled should block"
        elif scenario.expected_level == 1:
            # Level 1: dry_run 通过则执行，失败则不执行
            # 但若 dry_run_required=False（如 dry_run_verify_enabled=False）→ 阻塞
            if scenario.dry_run_success and scenario.dry_run_verify_enabled:
                assert outcome.executed is True, f"#{scenario.id}: Level 1 dry_run pass should execute"
            else:
                assert outcome.executed is False, f"#{scenario.id}: Level 1 should block"

        # 验证 audit_record 非空
        assert outcome.audit_record, f"#{scenario.id}: audit_record should not be empty"
        assert "level" in outcome.audit_record
        assert "outcome" in outcome.audit_record


# ──────────────────────────────────────────────
# 12 场景计数验证（确保 SCENARIOS 完整）
# ──────────────────────────────────────────────


class TestScenarioCompleteness:
    """确保 12 场景全部定义（防止漏加）。"""

    def test_exactly_12_scenarios(self):
        assert len(SCENARIOS) == 12

    def test_scenario_ids_sequential(self):
        ids = [s.id for s in SCENARIOS]
        assert ids == list(range(1, 13))

    def test_all_outcomes_covered(self):
        """12 场景覆盖 AUTO/MANUAL/ADMIN/DENY 四种 outcome。"""
        outcomes = {s.expected_outcome for s in SCENARIOS}
        assert OUTCOME_AUTO in outcomes
        assert OUTCOME_MANUAL in outcomes
        assert OUTCOME_ADMIN in outcomes
        assert OUTCOME_DENY in outcomes

    def test_all_levels_covered(self):
        """12 场景覆盖 Level 0/1/2 三级。"""
        levels = {s.expected_level for s in SCENARIOS}
        assert levels == {0, 1, 2}
