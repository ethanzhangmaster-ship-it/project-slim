"""P0 ApprovalGate V2 — 无人值守 Growth Loop 集成测试。

Spec: docs/p0_approval_gate_v2_spec.md §10.2（Week 2 Day 13）

测试目标（Spec §10.2）：
  - 模拟 24h growth loop 循环（4 cycles × 6h，每 cycle 注入 5 个动作 = 20 动作）
  - 注入 20 个动作：5 个 Level 0 + 10 个 Level 1 + 5 个 Level 2
  - 验证 Level 0 自动执行 + Level 1 dry_run 升级 + Level 2 阻塞 + audit log 完整性

测试矩阵：
  TestUnattended24hSimulation     — 主 24h 模拟（20 动作分级执行）
  TestUnattendedV1Compat          — V1 兼容（无 v2_executor 时 V2 统计恒 0）
  TestUnattendedShadowMode        — Shadow 模式（Level 0 只记 audit 不执行）
  TestUnattendedBudgetWindow      — 累计窗口溢出升级 Level 2
  TestUnattendedEndToEnd          — run_cycle 端到端验证 V2 路径激活
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

# 确保 scripts/ 与 src/ 在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.config import ApprovalConfig
from src.execution.approval.dry_run_verifier import DryRunVerifier
from src.execution.approval.policy import ApprovalPolicy
from src.execution.approval.v2_executor import V2ActionExecutor
from scripts.action_executor import (
    ActionExecutor,
    ExecutionResult,
    MockPlatformAdapter,
    SafetyGate,
)
from scripts.action_planner import (
    ActionStatus,
    ActionType,
    ExecutionAction,
)
from scripts.growth_loop_orchestrator import CycleResult, GrowthLoopOrchestrator


# ──────────────────────────────────────────────
# 辅助构造
# ──────────────────────────────────────────────


@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@dataclass
class MockV1Executor:
    """轻量 V1 ActionExecutor mock，记录调用次数与 dry_run 标志。

    与 tests/p2_3/test_v2_executor.py 中的 MockV1Executor 同构，
    便于 V2 集成层在 dry_run 验证 + 真实执行链路中复用。
    """
    result_success: bool = True
    call_count: int = 0
    dry_run_calls: int = 0
    real_calls: int = 0
    _raise: Exception | None = field(default=None, repr=False)

    def execute(self, action: Any, dry_run: bool = False) -> ExecutionResult:
        self.call_count += 1
        if dry_run:
            self.dry_run_calls += 1
        else:
            self.real_calls += 1
        if self._raise is not None:
            raise self._raise
        return ExecutionResult(
            success=self.result_success,
            status=__import__(
                "scripts.action_executor", fromlist=["ActionExecutionStatus"]
            ).ActionExecutionStatus.COMPLETED,
            dry_run=dry_run,
        )


def _build_v2_stack(
    tmp_path: Path,
    level0_enabled: bool = True,
    shadow_mode: bool = False,
    dry_run_verify_enabled: bool = True,
    auto_daily_cumulative_usd: float = 5000.0,
) -> tuple[V2ActionExecutor, MockV1Executor, BudgetWindowTracker, ApprovalConfig]:
    """构造完整 V2 审批栈：config + tracker + policy + verifier + executor。"""
    cfg = ApprovalConfig(
        auto_budget_threshold_usd=50.0,
        auto_daily_cumulative_usd=auto_daily_cumulative_usd,
        level1_budget_threshold_usd=500.0,
        auto_max_risk=0.3,
        auto_min_confidence=0.9,
        level1_max_risk=0.6,
        level0_enabled=level0_enabled,
        shadow_mode=shadow_mode,
        dry_run_verify_enabled=dry_run_verify_enabled,
        audit_log_dir=str(tmp_path),
    )
    tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
    policy = ApprovalPolicy(config=cfg, window_tracker=tracker)
    v1_executor = MockV1Executor(result_success=True)
    verifier = DryRunVerifier(executor=v1_executor)
    v2 = V2ActionExecutor(
        executor=v1_executor,
        policy=policy,
        config=cfg,
        window_tracker=tracker,
        dry_run_verifier=verifier,
    )
    return v2, v1_executor, tracker, cfg


def _make_action(
    action_id: str,
    creative_id: str,
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    budget_impact: float = 0.0,
    confidence: float = 0.95,
    risk_level: str = "low",
) -> ExecutionAction:
    """构造测试用 ExecutionAction（action_planner 版本）。

    注意：expected_impact 留空（{}），避免 V1 兼容的 _impact_magnitude
    将 budget_delta 误解为归一化 impact 触发 ADMIN 升级。V2 路径的金额
    分级完全通过 budget_amount_usd（来自 budget_impact 绝对值）实现。
    """
    return ExecutionAction(
        action_id=action_id,
        strategy_id="strat_test",
        hypothesis_id="hyp_test",
        diagnosis_id="diag_test",
        signal_id="sig_test",
        creative_id=creative_id,
        adset_id=f"adset_{creative_id}",
        action_type=action_type,
        parameters={"adset_id": f"adset_{creative_id}"},
        confidence=confidence,
        risk_level=risk_level,
        expected_impact={},  # V2 不依赖 expected_impact 做分级
        reason=f"test action {action_id}",
        budget_impact=budget_impact,
        status=ActionStatus.PENDING,
    )


def _build_orchestrator(
    tmp_data_dir: str,
    v2_executor: V2ActionExecutor | None = None,
) -> GrowthLoopOrchestrator:
    """构造测试用 GrowthLoopOrchestrator。"""
    return GrowthLoopOrchestrator(
        data_dir=tmp_data_dir,
        adapter=MockPlatformAdapter(),
        safety_gate=SafetyGate(auto_approve_max_level=2),
        dry_run=False,
        v2_executor=v2_executor,
    )


# ═══════════════════════════════════════════════════════════
# TestUnattended24hSimulation — Spec §10.2 主测试
# ═══════════════════════════════════════════════════════════


class TestUnattended24hSimulation:
    """Spec §10.2：24h 无人值守 growth loop 模拟。

    分布：4 cycles × 5 actions = 20 actions
      - 5× Level 0（PAUSE + 低风险 + 高置信 + 0 金额）
      - 10× Level 1（UPDATE_BUDGET + $100 + medium risk → dry_run 通过升级）
      - 5× Level 2（UPDATE_BUDGET + $600 + 低风险 → 大额阻塞）
    """

    def test_24h_simulation_20_actions(self, tmp_data_dir):
        """24h 模拟：4 cycles × 5 actions = 20 动作分级执行。"""
        import os

        audit_dir = os.path.join(tmp_data_dir, "audit")
        os.makedirs(audit_dir, exist_ok=True)
        audit_path = Path(audit_dir)

        v2, v1, tracker, cfg = _build_v2_stack(audit_path)
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        # 构造 20 个动作：5 L0 + 10 L1 + 5 L2
        actions: list[ExecutionAction] = []
        # 5× Level 0：PAUSE_CAMPAIGN, risk=low, conf=0.95, amount=0
        for i in range(5):
            actions.append(_make_action(
                action_id=f"l0_{i}",
                creative_id=f"cr_l0_{i}",
                action_type=ActionType.PAUSE_CAMPAIGN,
                budget_impact=0.0,
                confidence=0.95,
                risk_level="low",
            ))
        # 10× Level 1：UPDATE_BUDGET, risk=medium, conf=0.9, amount=100
        for i in range(10):
            actions.append(_make_action(
                action_id=f"l1_{i}",
                creative_id=f"cr_l1_{i}",
                action_type=ActionType.UPDATE_BUDGET,
                budget_impact=100.0,
                confidence=0.9,
                risk_level="medium",
            ))
        # 5× Level 2：UPDATE_BUDGET, risk=low, conf=0.95, amount=600
        for i in range(5):
            actions.append(_make_action(
                action_id=f"l2_{i}",
                creative_id=f"cr_l2_{i}",
                action_type=ActionType.UPDATE_BUDGET,
                budget_impact=600.0,
                confidence=0.95,
                risk_level="low",
            ))

        assert len(actions) == 20

        # 模拟 24h：4 cycles，每 cycle 处理 5 个动作
        # 直接调 _execute_via_v2 绕过 Diagnose→Plan，控制精确的 20 动作分布
        all_cycle_results: list[CycleResult] = []
        for cycle_idx in range(4):
            cycle_result = CycleResult()
            cycle_result.cycle_number = cycle_idx + 1
            cycle_actions = actions[cycle_idx * 5:(cycle_idx + 1) * 5]
            for action in cycle_actions:
                executed, exec_result = orch._execute_via_v2(action, cycle_result)
            all_cycle_results.append(cycle_result)

        # 汇总 4 cycles 的 V2 统计
        total_l0_executed = sum(cr.v2_level0_executed for cr in all_cycle_results)
        total_l0_shadow = sum(cr.v2_level0_shadow for cr in all_cycle_results)
        total_l1_promoted = sum(cr.v2_level1_promoted for cr in all_cycle_results)
        total_l1_blocked = sum(cr.v2_level1_blocked for cr in all_cycle_results)
        total_l2_blocked = sum(cr.v2_level2_blocked for cr in all_cycle_results)
        total_denied = sum(cr.v2_denied for cr in all_cycle_results)
        total_fallback_v1 = sum(cr.v2_fallback_v1 for cr in all_cycle_results)
        total_blocked = sum(
            len(cr.v2_blocked_actions) for cr in all_cycle_results
        )

        # ── 验证 V2 分级统计（Spec §10.2 核心断言）──
        # 5× Level 0 全部自动执行
        assert total_l0_executed == 5, (
            f"Expected 5 Level 0 executed, got {total_l0_executed}"
        )
        assert total_l0_shadow == 0, "非 shadow 模式不应有 shadow 计数"

        # 10× Level 1 全部 dry_run 通过后升级执行
        assert total_l1_promoted == 10, (
            f"Expected 10 Level 1 promoted, got {total_l1_promoted}"
        )
        assert total_l1_blocked == 0, "dry_run 通过的 Level 1 不应阻塞"

        # 5× Level 2 全部阻塞
        assert total_l2_blocked == 5, (
            f"Expected 5 Level 2 blocked, got {total_l2_blocked}"
        )
        assert total_denied == 0, "无未知动作，不应有 DENY"
        assert total_fallback_v1 == 0, "PAUSE/UPDATE_BUDGET 均可映射，无 V1 回退"

        # 阻塞动作详情
        assert total_blocked == 5, (
            f"Expected 5 blocked action records, got {total_blocked}"
        )

        # ── 验证 V1 executor 调用次数 ──
        # Level 0: 5 次真实执行
        # Level 1: 10 × 2 = 20 次（dry_run + 真实执行）
        # Level 2: 0 次（阻塞，不调用 V1 executor）
        # 总计：5 + 20 = 25
        assert v1.real_calls == 15, (
            f"Expected 15 real V1 calls (5 L0 + 10 L1 promoted), "
            f"got {v1.real_calls}"
        )
        assert v1.dry_run_calls == 10, (
            f"Expected 10 dry_run V1 calls (Level 1 verification), "
            f"got {v1.dry_run_calls}"
        )
        assert v1.call_count == 25, (
            f"Expected 25 total V1 calls, got {v1.call_count}"
        )

        # ── 验证 audit log 完整性 ──
        audit_file = audit_path / "approval_decisions.jsonl"
        assert audit_file.exists(), "audit log 文件应存在"

        audit_lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
        # 20 个动作每个产生一条 audit 记录
        assert len(audit_lines) == 20, (
            f"Expected 20 audit records, got {len(audit_lines)}"
        )

        # 验证每条 audit 记录可解析且字段完整
        audit_records: list[dict] = []
        for line in audit_lines:
            record = json.loads(line)
            audit_records.append(record)
            # Spec §8 必需字段
            assert "ts" in record
            assert "action_id" in record
            assert "level" in record
            assert "outcome" in record
            assert "executed" in record
            assert "shadow" in record

        # 验证 level 分布：5×L0 + 10×L1 + 5×L2
        level_counts = {0: 0, 1: 0, 2: 0}
        for r in audit_records:
            level_counts[r["level"]] = level_counts.get(r["level"], 0) + 1
        assert level_counts[0] == 5, f"L0 audit count: {level_counts[0]}"
        assert level_counts[1] == 10, f"L1 audit count: {level_counts[1]}"
        assert level_counts[2] == 5, f"L2 audit count: {level_counts[2]}"

        # 验证 executed 分布：15 True（5 L0 + 10 L1 promoted）+ 5 False（L2 blocked）
        executed_true = sum(1 for r in audit_records if r["executed"])
        executed_false = sum(1 for r in audit_records if not r["executed"])
        assert executed_true == 15, f"executed=True count: {executed_true}"
        assert executed_false == 5, f"executed=False count: {executed_false}"

    def test_24h_simulation_state_progression(self, tmp_data_dir):
        """24h 模拟后 LoopState.total_actions_executed 正确累加。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(audit_dir)
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        # 注入 3 个 L0 动作
        actions = [
            _make_action(
                action_id=f"a_{i}",
                creative_id=f"cr_{i}",
                action_type=ActionType.PAUSE_CAMPAIGN,
                budget_impact=0.0,
                confidence=0.95,
                risk_level="low",
            )
            for i in range(3)
        ]

        cycle_result = CycleResult()
        for action in actions:
            orch._execute_via_v2(action, cycle_result)

        # LoopState.total_actions_executed 应累加 3
        assert orch.state.total_actions_executed == 3
        assert cycle_result.v2_level0_executed == 3


# ═══════════════════════════════════════════════════════════
# TestUnattendedV1Compat — V1 兼容性
# ═══════════════════════════════════════════════════════════


class TestUnattendedV1Compat:
    """未注入 v2_executor 时完全保留 V1 行为。"""

    def test_no_v2_executor_all_stats_zero(self, tmp_data_dir):
        """无 v2_executor → V2 统计恒 0，走 V1 路径。"""
        orch = _build_orchestrator(tmp_data_dir, v2_executor=None)
        assert orch._v2_executor is None
        assert orch.get_status()["v2_approval_gate_enabled"] is False

        cycle_result = CycleResult()
        action = _make_action(
            action_id="v1_test",
            creative_id="cr_v1",
            action_type=ActionType.PAUSE_CAMPAIGN,
        )
        # _execute_via_v2 在无 v2_executor 时不应被调用（Phase B 走 V1 分支）
        # 但若直接调用，_action_to_intent 仍会工作，v2_executor.execute_with_approval
        # 会抛 AttributeError。验证 Phase B 路径分流正确：
        # 此处仅验证 status 字段，不直接调 _execute_via_v2
        assert orch.get_status()["v2_approval_gate_enabled"] is False

    def test_v1_path_executes_normally(self, tmp_data_dir):
        """V1 模式下 run_cycle 正常执行，V2 统计全 0。"""
        from src.market_ops.creative_vision_runtime.reality.feedback.models import (
            FeedbackSignalType,
            RealityFeedbackSignal,
        )

        orch = _build_orchestrator(tmp_data_dir, v2_executor=None)

        signal = RealityFeedbackSignal(
            creative_id="cr_v1_e2e",
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.8,
            confidence=0.8,
            reason=["ROAS 下降"],
        )
        metrics = {"cr_v1_e2e": {"roas": 0.5, "cpi": 2.0, "ctr": 0.02, "spend": 200.0, "frequency": 3.5}}
        prev = {"cr_v1_e2e": {"roas": 0.8, "cpi": 2.0, "ctr": 0.02, "spend": 200.0, "frequency": 2.0}}

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_v1_e2e": "adset_v1"},
            current_budgets={"adset_v1": 200.0},
        )

        # V1 模式：V2 统计全 0
        assert result.v2_level0_executed == 0
        assert result.v2_level1_promoted == 0
        assert result.v2_level2_blocked == 0
        assert result.v2_fallback_v1 == 0
        assert len(result.v2_blocked_actions) == 0


# ═══════════════════════════════════════════════════════════
# TestUnattendedShadowMode — Spec §9 Shadow 灰度
# ═══════════════════════════════════════════════════════════


class TestUnattendedShadowMode:
    """Shadow 模式：Level 0 决策正确但只记 audit，不真实执行。"""

    def test_shadow_mode_level0_not_executed(self, tmp_data_dir):
        """Shadow 模式下 Level 0 动作只记 audit，不调用 V1 executor。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(
            audit_dir, level0_enabled=True, shadow_mode=True
        )
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        action = _make_action(
            action_id="shadow_l0",
            creative_id="cr_shadow",
            action_type=ActionType.PAUSE_CAMPAIGN,
            budget_impact=0.0,
            confidence=0.95,
            risk_level="low",
        )
        cycle_result = CycleResult()
        executed, exec_result = orch._execute_via_v2(action, cycle_result)

        # Shadow 模式：Level 0 决策正确但未执行
        assert executed is False
        assert exec_result is None
        assert cycle_result.v2_level0_shadow == 1
        assert cycle_result.v2_level0_executed == 0
        # V1 executor 不应被调用
        assert v1.call_count == 0

        # audit log 应有 1 条记录，executed=False, shadow=True
        audit_file = audit_dir / "approval_decisions.jsonl"
        assert audit_file.exists()
        records = [
            json.loads(line)
            for line in audit_file.read_text(encoding="utf-8").strip().split("\n")
            if line
        ]
        assert len(records) == 1
        assert records[0]["executed"] is False
        assert records[0]["shadow"] is True
        assert records[0]["level"] == 0

    def test_shadow_mode_level2_still_blocked(self, tmp_data_dir):
        """Shadow 模式不影响 Level 2 阻塞语义。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(
            audit_dir, level0_enabled=True, shadow_mode=True
        )
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        action = _make_action(
            action_id="shadow_l2",
            creative_id="cr_shadow_l2",
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=600.0,
            confidence=0.95,
            risk_level="low",
        )
        cycle_result = CycleResult()
        executed, _ = orch._execute_via_v2(action, cycle_result)

        # Level 2 阻塞（shadow 模式不改变 Level 2 语义）
        assert executed is False
        assert cycle_result.v2_level2_blocked == 1
        assert cycle_result.v2_level0_shadow == 0


# ═══════════════════════════════════════════════════════════
# TestUnattendedBudgetWindow — Spec §3 累计窗口
# ═══════════════════════════════════════════════════════════


class TestUnattendedBudgetWindow:
    """累计窗口溢出 → Level 2 阻塞。"""

    def test_cumulative_overflow_escalates_to_level2(self, tmp_data_dir):
        """累计金额溢出 → 原 Level 0 动作升级为 Level 2 阻塞。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        # 用低累计上限以便触发溢出
        v2, v1, tracker, cfg = _build_v2_stack(
            audit_dir,
            level0_enabled=True,
            dry_run_verify_enabled=False,  # 简化：不测 dry_run
            auto_daily_cumulative_usd=80.0,  # 累计上限 $80
        )
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        # 同一 creative_id + 同一 action_type 累计
        # 第 1 个动作：$30 → 累计 $30，未超 $80 → Level 0
        action1 = _make_action(
            action_id="cum_1",
            creative_id="cr_cum",
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=30.0,
            confidence=0.95,
            risk_level="low",
        )
        cr1 = CycleResult()
        exec1, _ = orch._execute_via_v2(action1, cr1)
        assert exec1 is True
        assert cr1.v2_level0_executed == 1

        # 第 2 个动作：$60 → 累计 $30+$60=$90 > $80 → Level 2 阻塞
        action2 = _make_action(
            action_id="cum_2",
            creative_id="cr_cum",  # 同一 creative → 同一累计窗口
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=60.0,
            confidence=0.95,
            risk_level="low",
        )
        cr2 = CycleResult()
        exec2, _ = orch._execute_via_v2(action2, cr2)
        assert exec2 is False
        assert cr2.v2_level2_blocked == 1
        # 阻塞原因应包含 cumulative overflow
        assert len(cr2.v2_blocked_actions) == 1
        assert "cumulative" in cr2.v2_blocked_actions[0]["reason"].lower()

    def test_different_creatives_no_shared_cumulative(self, tmp_data_dir):
        """不同 creative_id 不共享累计窗口。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(
            audit_dir,
            level0_enabled=True,
            dry_run_verify_enabled=False,
            auto_daily_cumulative_usd=80.0,
        )
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        # creative_A: $30 → Level 0
        action_a = _make_action(
            action_id="a_1",
            creative_id="cr_A",
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=30.0,
            confidence=0.95,
            risk_level="low",
        )
        cr_a = CycleResult()
        exec_a, _ = orch._execute_via_v2(action_a, cr_a)
        assert exec_a is True

        # creative_B: $30 → 不共享 A 的累计，仍 Level 0
        action_b = _make_action(
            action_id="b_1",
            creative_id="cr_B",
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=30.0,
            confidence=0.95,
            risk_level="low",
        )
        cr_b = CycleResult()
        exec_b, _ = orch._execute_via_v2(action_b, cr_b)
        assert exec_b is True
        assert cr_b.v2_level0_executed == 1


# ═══════════════════════════════════════════════════════════
# TestUnattendedEndToEnd — run_cycle 端到端验证
# ═══════════════════════════════════════════════════════════


class TestUnattendedEndToEnd:
    """通过 run_cycle 端到端验证 V2 路径激活。"""

    def test_run_cycle_with_v2_path(self, tmp_data_dir):
        """注入 v2_executor 后 run_cycle 走 V2 路径。"""
        from src.market_ops.creative_vision_runtime.reality.feedback.models import (
            FeedbackSignalType,
            RealityFeedbackSignal,
        )

        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(audit_dir)
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        assert orch.get_status()["v2_approval_gate_enabled"] is True

        signal = RealityFeedbackSignal(
            creative_id="cr_e2e",
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.8,
            confidence=0.8,
            reason=["ROAS 下降"],
        )
        metrics = {"cr_e2e": {"roas": 0.5, "cpi": 2.0, "ctr": 0.02, "spend": 200.0, "frequency": 3.5}}
        prev = {"cr_e2e": {"roas": 0.8, "cpi": 2.0, "ctr": 0.02, "spend": 200.0, "frequency": 2.0}}

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=metrics,
            previous_metrics=prev,
            creative_to_adset_map={"cr_e2e": "adset_e2e"},
            current_budgets={"adset_e2e": 200.0},
        )

        # V2 路径激活：至少有一个动作被 V2 处理（L0/L1/L2/退V1 任一）
        v2_total = (
            result.v2_level0_executed + result.v2_level0_shadow
            + result.v2_level1_promoted + result.v2_level1_blocked
            + result.v2_level2_blocked + result.v2_denied
            + result.v2_fallback_v1
        )
        assert v2_total > 0, "V2 路径应处理至少 1 个动作"
        assert result.cycle_number == 1

    def test_action_to_intent_mapping(self, tmp_data_dir):
        """_action_to_intent 正确映射 ActionType → ExecutionAction。"""
        orch = _build_orchestrator(tmp_data_dir, v2_executor=None)

        # UPDATE_BUDGET → SCALE_BUDGET
        action_ub = _make_action(
            action_id="map_ub",
            creative_id="cr_map_ub",
            action_type=ActionType.UPDATE_BUDGET,
            budget_impact=50.0,
        )
        intent_ub = orch._action_to_intent(action_ub)
        assert intent_ub is not None
        assert intent_ub.action.value == "scale_budget"
        assert intent_ub.budget_amount_usd == 50.0

        # PAUSE_CAMPAIGN → PAUSE_CAMPAIGN
        action_pc = _make_action(
            action_id="map_pc",
            creative_id="cr_map_pc",
            action_type=ActionType.PAUSE_CAMPAIGN,
            budget_impact=0.0,
        )
        intent_pc = orch._action_to_intent(action_pc)
        assert intent_pc is not None
        assert intent_pc.action.value == "pause_campaign"

        # RESUME_CAMPAIGN → None（V2 无对应，回退 V1）
        action_rc = _make_action(
            action_id="map_rc",
            creative_id="cr_map_rc",
            action_type=ActionType.RESUME_CAMPAIGN,
            budget_impact=0.0,
        )
        intent_rc = orch._action_to_intent(action_rc)
        assert intent_rc is None

    def test_fallback_v1_for_resume_campaign(self, tmp_data_dir):
        """RESUME_CAMPAIGN 无 V2 映射 → 回退 V1 执行。"""
        audit_dir = Path(tmp_data_dir) / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        v2, v1, tracker, cfg = _build_v2_stack(audit_dir)
        orch = _build_orchestrator(tmp_data_dir, v2_executor=v2)

        action = _make_action(
            action_id="resume_fb",
            creative_id="cr_resume",
            action_type=ActionType.RESUME_CAMPAIGN,
            budget_impact=0.0,
        )
        cycle_result = CycleResult()
        executed, _ = orch._execute_via_v2(action, cycle_result)

        # 回退 V1 路径执行
        assert executed is True
        assert cycle_result.v2_fallback_v1 == 1
        assert cycle_result.v2_level0_executed == 0
