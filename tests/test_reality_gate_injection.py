"""RealityGate 门控注入测试 (接线 1)。

验证 RealityGate → ActionExecutor 的门控逻辑:
  - BLOCKED 区间 (composite < 0.5): 动作被 SKIPPED
  - APPROVE 区间 (0.5 ≤ composite < 0.8): 低 approval_level 动作被 SKIPPED
  - EXECUTE 区间 (composite >= 0.8): 动作正常执行
  - 未配置 reality_scores: 向后兼容, 不门控
  - NOOP 动作: 不受 RealityGate 限制
  - 未知 game_id: 不门控
  - GrowthLoopOrchestrator 传递 reality_scores
  - update_reality_scores 动态更新
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.growth_reality.validation.models import RealityScore
from scripts.action_planner import (
    ActionPlanner,
    ActionStatus,
    ActionType,
    ExecutionAction,
)
from scripts.action_executor import (
    ActionExecutionStatus,
    ActionExecutor,
    MockPlatformAdapter,
    SafetyGate,
)
from scripts.diagnostic_engine import (
    DiagnosisResult,
    DiagnosticEngine,
    RootCause,
    StrategyType,
)
from scripts.growth_loop_orchestrator import GrowthLoopOrchestrator


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────


def _make_action(
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    creative_id: str = "c_001",
    approval_level: int = 0,
    adset_id: str = "adset_001",
) -> ExecutionAction:
    return ExecutionAction(
        strategy_id="strat_001",
        hypothesis_id="hyp_001",
        diagnosis_id="diag_001",
        signal_id="fs_001",
        creative_id=creative_id,
        adset_id=adset_id,
        action_type=action_type,
        parameters={"target_budget": 140.0, "current_budget": 200.0},
        confidence=0.75,
        risk_level="medium",
        expected_impact={
            "metric": "roas",
            "direction": "positive",
            "estimated_change": 0.15,
            "strategy_type": "suppress",
        },
        reason="suppress: 降低预算 30%",
        budget_impact=-60.0,
        approval_level=approval_level,
        status=ActionStatus.PENDING,
    )


def _make_score(composite: float, game_id: str = "P04") -> RealityScore:
    """构造 RealityScore。"""
    return RealityScore(
        game_id=game_id,
        coverage=1.0,
        freshness=1.0,
        consistency=composite,
        composite=composite,
        decision_level=(
            "BLOCKED" if composite < 0.5
            else "APPROVE" if composite < 0.8
            else "EXECUTE"
        ),
    )


def _make_resolver(mapping: dict[str, str] | None = None):
    """构造 creative_id → game_id 解析器。"""
    mapping = mapping or {"c_001": "P04", "c_002": "P04"}

    def resolver(creative_id: str) -> str:
        return mapping.get(creative_id, "")

    return resolver


# ──────────────────────────────────────────────
# ActionExecutor RealityGate 测试
# ──────────────────────────────────────────────


class TestRealityGateInjection:
    """ActionExecutor 的 RealityGate 门控测试。"""

    def test_blocked_composite_skips_action(self):
        """composite < 0.5 → 动作被 SKIPPED。"""
        scores = {"P04": _make_score(0.3)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert result.success is False
        assert "RealityGate blocked" in result.error_message
        assert "BLOCKED" in result.error_message

    def test_execute_composite_allows_action(self):
        """composite >= 0.8 → 动作正常执行。"""
        scores = {"P04": _make_score(0.9)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_approve_composite_low_approval_skips(self):
        """0.5 ≤ composite < 0.8 且 approval_level=0 → SKIPPED (需人工审批)。"""
        scores = {"P04": _make_score(0.6)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action(approval_level=0)
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "APPROVE" in result.error_message

    def test_approve_composite_high_approval_allows(self):
        """0.5 ≤ composite < 0.8 且 approval_level >= 1 → 允许执行 (已有审批)。"""
        scores = {"P04": _make_score(0.6)}
        # SafetyGate 也允许 approval_level=1 通过
        executor = ActionExecutor(
            safety_gate=SafetyGate(auto_approve_max_level=1),
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action(approval_level=1)
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_no_reality_scores_backward_compat(self):
        """未配置 reality_scores → 不门控 (向后兼容)。"""
        executor = ActionExecutor()  # 无 reality_scores
        action = _make_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_no_game_id_resolver_skips_gate(self):
        """有 reality_scores 但无 game_id_resolver → 不门控。"""
        scores = {"P04": _make_score(0.1)}  # 极低分
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=None,
        )
        action = _make_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_noop_action_not_gated(self):
        """NOOP 动作不受 RealityGate 限制。"""
        scores = {"P04": _make_score(0.1)}  # BLOCKED
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action(action_type=ActionType.NOOP)
        result = executor.execute(action, dry_run=True)

        # NOOP 会被 SafetyGate 跳过, 但不是被 RealityGate 阻止
        assert result.status == ActionExecutionStatus.SKIPPED
        assert "Safety check failed" in result.error_message
        assert "NOOP" in result.error_message

    def test_unknown_game_id_not_gated(self):
        """creative_id 对应的 game_id 不在 scores 中 → 不门控。"""
        scores = {"OTHER_GAME": _make_score(0.1)}  # 只有 OTHER_GAME
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver({"c_001": "P04"}),  # P04 不在 scores
        )
        action = _make_action(creative_id="c_001")
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_unknown_creative_id_not_gated(self):
        """creative_id 无法解析为 game_id → 不门控。"""
        scores = {"P04": _make_score(0.1)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver({"c_001": "P04"}),
        )
        action = _make_action(creative_id="c_UNKNOWN")  # 不在 resolver mapping
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_boundary_0_5_is_approve(self):
        """composite=0.5 恰好在 APPROVE 区间边界 (0.5 ≤ composite < 0.8)。"""
        scores = {"P04": _make_score(0.5)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action(approval_level=0)
        result = executor.execute(action, dry_run=True)

        # 0.5 在 APPROVE 区间, approval_level=0 → SKIPPED
        assert result.status == ActionExecutionStatus.SKIPPED
        assert "APPROVE" in result.error_message

    def test_boundary_0_8_is_execute(self):
        """composite=0.8 恰好在 EXECUTE 区间边界 (composite >= 0.8)。"""
        scores = {"P04": _make_score(0.8)}
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action(approval_level=0)
        result = executor.execute(action, dry_run=True)

        # 0.8 在 EXECUTE 区间 → 允许执行
        assert result.status == ActionExecutionStatus.COMPLETED
        assert result.success is True

    def test_gate_before_safety_check(self):
        """RealityGate 检查在 SafetyGate 之前 (数据不可信时优先阻止)。"""
        scores = {"P04": _make_score(0.1)}  # BLOCKED
        # SafetyGate 会因为 budget < min_budget 阻止, 但 RealityGate 先阻止
        executor = ActionExecutor(
            safety_gate=SafetyGate(min_budget=10000.0),  # 极高 min_budget
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        action = _make_action()
        result = executor.execute(action, dry_run=True)

        assert result.status == ActionExecutionStatus.SKIPPED
        assert "RealityGate blocked" in result.error_message
        # 不应该到达 SafetyGate
        assert "Safety check" not in result.error_message

    def test_batch_execution_with_gate(self):
        """批量执行: 部分动作被门控, 部分正常执行。"""
        scores = {"P04": _make_score(0.3)}  # BLOCKED
        executor = ActionExecutor(
            reality_scores=scores,
            game_id_resolver=_make_resolver(),
        )
        actions = [
            _make_action(creative_id="c_001"),
            _make_action(creative_id="c_002"),
        ]
        results = executor.execute_batch(actions, dry_run=True)

        assert len(results) == 2
        assert all(r.status == ActionExecutionStatus.SKIPPED for r in results)
        assert all("RealityGate blocked" in r.error_message for r in results)


# ──────────────────────────────────────────────
# GrowthLoopOrchestrator RealityGate 传递测试
# ──────────────────────────────────────────────


class TestOrchestratorRealityGate:
    """GrowthLoopOrchestrator 的 RealityGate 参数传递测试。"""

    def test_orchestrator_passes_reality_scores_to_executor(self, tmp_path):
        """Orchestrator 将 reality_scores 传递给 ActionExecutor。"""
        scores = {"P04": _make_score(0.3)}
        resolver = _make_resolver()

        orch = GrowthLoopOrchestrator(
            data_dir=str(tmp_path),
            reality_scores=scores,
            game_id_resolver=resolver,
        )

        assert orch.action_executor._reality_scores is scores
        assert orch.action_executor._game_id_resolver is resolver

    def test_orchestrator_no_reality_scores_default(self, tmp_path):
        """未传 reality_scores 时, ActionExecutor 内部为 None (向后兼容)。"""
        orch = GrowthLoopOrchestrator(data_dir=str(tmp_path))

        assert orch.action_executor._reality_scores is None
        assert orch.action_executor._game_id_resolver is None

    def test_update_reality_scores(self, tmp_path):
        """update_reality_scores 动态更新可信分。"""
        orch = GrowthLoopOrchestrator(data_dir=str(tmp_path))
        assert orch.action_executor._reality_scores is None

        new_scores = {"P04": _make_score(0.9)}
        new_resolver = _make_resolver()
        orch.update_reality_scores(new_scores, new_resolver)

        assert orch.action_executor._reality_scores is new_scores
        assert orch.action_executor._game_id_resolver is new_resolver

    def test_update_reality_scores_preserves_resolver(self, tmp_path):
        """update_reality_scores 不传 resolver 时保留原 resolver。"""
        original_resolver = _make_resolver()
        orch = GrowthLoopOrchestrator(
            data_dir=str(tmp_path),
            game_id_resolver=original_resolver,
        )

        new_scores = {"P04": _make_score(0.9)}
        orch.update_reality_scores(new_scores)  # 不传 resolver

        assert orch.action_executor._reality_scores is new_scores
        assert orch.action_executor._game_id_resolver is original_resolver


# ──────────────────────────────────────────────
# 端到端: RealityGate → Growth Loop 闭环
# ──────────────────────────────────────────────


class TestEndToEndRealityGate:
    """端到端: RealityGate 在 Growth Loop 中实际拦截动作。"""

    def test_blocked_score_prevents_execution_in_loop(self, tmp_path):
        """BLOCKED 可信分在 Growth Loop 中阻止动作执行。"""
        from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
            ExperienceStore,
        )
        from scripts.hypothesis_generator import GrowthHypothesis, HypothesisGenerator
        from scripts.strategy_selector import GrowthStrategy, StrategySelector

        # 构造 BLOCKED 可信分
        scores = {"P04": _make_score(0.2)}
        resolver = _make_resolver({"c_001": "P04"})

        store = ExperienceStore()
        orch = GrowthLoopOrchestrator(
            data_dir=str(tmp_path),
            store=store,
            dry_run=True,
            reality_scores=scores,
            game_id_resolver=resolver,
        )

        # 构造一个会触发 SUPPRESS 策略的信号
        signal = type("Signal", (), {
            "signal_type": "roas_decline",
            "creative_id": "c_001",
            "signal_id": "fs_test001",
        })()

        current_metrics = {
            "c_001": {
                "spend": 200.0, "clicks": 100, "ctr": 0.02,
                "cpi": 2.0, "roas": 0.3, "impressions": 5000,
                "installs": 100, "revenue": 60.0,
            }
        }
        previous_metrics = {
            "c_001": {
                "spend": 200.0, "clicks": 120, "ctr": 0.025,
                "cpi": 2.0, "roas": 0.5, "impressions": 5000,
                "installs": 100, "revenue": 100.0,
            }
        }

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=current_metrics,
            previous_metrics=previous_metrics,
            creative_to_adset_map={"c_001": "adset_001"},
            current_budgets={"c_001": 200.0},
        )

        # 应该有诊断和策略, 但执行结果为 SKIPPED
        assert len(result.diagnoses) > 0
        assert len(result.strategies) > 0
        assert len(result.actions) > 0

        # 检查执行结果: 被 RealityGate 阻止
        for exec_result in result.execution_results:
            assert exec_result.status == ActionExecutionStatus.SKIPPED
            assert "RealityGate blocked" in exec_result.error_message

    def test_execute_score_allows_execution_in_loop(self, tmp_path):
        """EXECUTE 可信分在 Growth Loop 中允许动作执行。"""
        from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
            ExperienceStore,
        )

        # 构造 EXECUTE 可信分
        scores = {"P04": _make_score(0.9)}
        resolver = _make_resolver({"c_001": "P04"})

        store = ExperienceStore()
        orch = GrowthLoopOrchestrator(
            data_dir=str(tmp_path),
            store=store,
            dry_run=True,
            reality_scores=scores,
            game_id_resolver=resolver,
        )

        signal = type("Signal", (), {
            "signal_type": "roas_decline",
            "creative_id": "c_001",
            "signal_id": "fs_test002",
        })()

        current_metrics = {
            "c_001": {
                "spend": 200.0, "clicks": 100, "ctr": 0.02,
                "cpi": 2.0, "roas": 0.3, "impressions": 5000,
                "installs": 100, "revenue": 60.0,
            }
        }
        previous_metrics = {
            "c_001": {
                "spend": 200.0, "clicks": 120, "ctr": 0.025,
                "cpi": 2.0, "roas": 0.5, "impressions": 5000,
                "installs": 100, "revenue": 100.0,
            }
        }

        result = orch.run_cycle(
            signals=[signal],
            current_metrics=current_metrics,
            previous_metrics=previous_metrics,
            creative_to_adset_map={"c_001": "adset_001"},
            current_budgets={"c_001": 200.0},
        )

        # 执行结果应该有成功的 (COMPLETED)
        assert len(result.execution_results) > 0
        has_completed = any(
            r.status == ActionExecutionStatus.COMPLETED
            for r in result.execution_results
        )
        assert has_completed, "EXECUTE 区间应允许动作执行"
