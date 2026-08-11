"""OutcomeEvaluator 单元测试。

覆盖:
  - ActionOutcome 数据模型
  - 指标变化计算 (metrics_delta)
  - 改善幅度计算 (positive / negative / neutral direction)
  - Outcome 判定 (SUCCESS / MARGINAL / FAILURE / INCONCLUSIVE)
  - 回滚检测
  - 经验写入 (仅对真实执行动作)
  - 批量评估
  - End-to-End: Strategy → Action → Evaluate → Experience
  - 闭环验证: 经验增强下一轮假设生成
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperienceOutcome,
    ExperienceRecord,
    MutationType,
)
from src.market_ops.creative_vision_runtime.reality.meta_learning.experience_store import (
    ExperienceStore,
)
from scripts.diagnostic_engine import (
    DiagnosisResult,
    DiagnosticEngine,
    RootCause,
    StrategyType,
)
from scripts.hypothesis_generator import (
    GrowthHypothesis,
    HypothesisGenerator,
)
from scripts.strategy_selector import (
    GrowthStrategy,
    StrategySelector,
)
from scripts.action_planner import (
    ActionPlanner,
    ActionStatus,
    ActionType,
    ExecutionAction,
)
from scripts.outcome_evaluator import (
    ActionOutcome,
    OutcomeEvaluator,
)


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────


def _make_action(
    action_type: ActionType = ActionType.UPDATE_BUDGET,
    creative_id: str = "c_001",
    signal_id: str = "fs_001",
    expected_impact: dict | None = None,
    confidence: float = 0.75,
    status: ActionStatus = ActionStatus.PENDING,
) -> ExecutionAction:
    if expected_impact is None:
        expected_impact = {
            "metric": "roas",
            "direction": "positive",
            "estimated_change": 0.15,
            "strategy_type": "suppress",
        }
    return ExecutionAction(
        strategy_id="strat_001",
        hypothesis_id="hyp_001",
        diagnosis_id="diag_001",
        signal_id=signal_id,
        creative_id=creative_id,
        adset_id="adset_001",
        action_type=action_type,
        parameters={"target_budget": 140.0, "current_budget": 200.0},
        confidence=confidence,
        risk_level="medium",
        expected_impact=expected_impact,
        reason="suppress: 降低预算 30%",
        budget_impact=-60.0,
        status=status,
    )


def _make_strategy(
    strategy_type: StrategyType = StrategyType.SUPPRESS,
    intensity: float = 0.70,
    creative_id: str = "c_001",
    confidence: float = 0.75,
    root_cause: str = "creative_fatigue",
    signal_id: str = "fs_test001",
) -> GrowthStrategy:
    return GrowthStrategy(
        strategy_type=strategy_type,
        target_creative_id=creative_id,
        intensity=intensity,
        confidence=confidence,
        root_cause=root_cause,
        signal_id=signal_id,
        expected_impact={
            "metric": "roas",
            "direction": "positive",
            "estimated_change": 0.15,
        },
        rollback_condition="ROAS 继续下降 > 10%",
    )


def _build_store(
    count=5, outcome=ExperienceOutcome.SUCCESS, improvement=0.20
):
    """构建含历史经验的 store（用于闭环测试）。"""
    from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
        ExperimentDetail,
        ExperienceResult,
        MutationDetail,
    )

    store = ExperienceStore()
    for i in range(count):
        store.add(
            ExperienceRecord(
                product_id="P01",
                creative_id=f"c_{i}",
                mutation=MutationDetail(mutation_type=MutationType.REFRESH_HOOK),
                experiment=ExperimentDetail(improvement=improvement),
                context=ContextDetail(product_id="P01", platform="facebook"),
                result=ExperienceResult(
                    outcome=outcome,
                    success=(outcome == ExperienceOutcome.SUCCESS),
                ),
            )
        )
    return store


# ──────────────────────────────────────────────
# ActionOutcome 数据模型测试
# ──────────────────────────────────────────────


class TestActionOutcomeModel:
    def test_auto_id_and_timestamp(self):
        o = ActionOutcome()
        assert o.outcome_id.startswith("outcome_")
        assert o.evaluated_at != ""

    def test_to_dict_serializable(self):
        o = ActionOutcome(
            action_id="exec_001",
            outcome=ExperienceOutcome.SUCCESS,
            improvement=0.25,
            target_metric="roas",
        )
        d = o.to_dict()
        assert d["action_id"] == "exec_001"
        assert d["outcome"] == "success"
        assert d["improvement"] == 0.25
        assert d["target_metric"] == "roas"
        assert "is_actionable" in d

    def test_is_actionable(self):
        assert ActionOutcome(outcome=ExperienceOutcome.SUCCESS).is_actionable is True
        assert ActionOutcome(outcome=ExperienceOutcome.FAILURE).is_actionable is True
        assert ActionOutcome(outcome=ExperienceOutcome.MARGINAL).is_actionable is False
        assert ActionOutcome(outcome=ExperienceOutcome.INCONCLUSIVE).is_actionable is False


# ──────────────────────────────────────────────
# 指标变化计算测试
# ──────────────────────────────────────────────


class TestMetricsDelta:
    def test_basic_delta(self):
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.50, "ctr": 0.02, "spend": 200.0}
        post = {"roas": 0.60, "ctr": 0.025, "spend": 180.0}
        delta = evaluator._compute_metrics_delta(pre, post)

        assert delta["roas"] == pytest.approx(0.20, abs=0.001)  # +20%
        assert delta["ctr"] == pytest.approx(0.25, abs=0.001)   # +25%
        assert delta["spend"] == pytest.approx(-0.10, abs=0.001)  # -10%

    def test_zero_pre_value(self):
        """pre=0 时用绝对差值。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.0}
        post = {"roas": 0.5}
        delta = evaluator._compute_metrics_delta(pre, post)
        assert delta["roas"] == 0.5  # 绝对差值

    def test_new_key_in_post(self):
        """post 中有 pre 没有的 key。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.5}
        post = {"roas": 0.6, "ctr": 0.03}
        delta = evaluator._compute_metrics_delta(pre, post)
        assert "ctr" in delta
        assert delta["ctr"] == 0.03  # pre=0 → 绝对差值

    def test_empty_metrics(self):
        evaluator = OutcomeEvaluator()
        assert evaluator._compute_metrics_delta({}, {}) == {}


# ──────────────────────────────────────────────
# 改善幅度计算测试
# ──────────────────────────────────────────────


class TestImprovementCalculation:
    def test_positive_direction_improves(self):
        """direction=positive: actual_change > 0 = 改善。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "positive"})
        imp = evaluator._compute_improvement(
            "roas", "positive", 0.20, action
        )
        assert imp == 0.20

    def test_negative_direction_improves(self):
        """direction=negative: actual_change < 0 = 改善（如 CPI 下降）。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(
            action_type=ActionType.UPDATE_BUDGET,
            expected_impact={"direction": "negative"},
        )
        imp = evaluator._compute_improvement(
            "cpi", "negative", -0.15, action
        )
        assert imp == 0.15  # CPI 降 15% → improvement=0.15

    def test_neutral_direction_zero(self):
        """direction=neutral: improvement=0。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "neutral"})
        imp = evaluator._compute_improvement(
            "none", "neutral", 0.30, action
        )
        assert imp == 0.0

    def test_pause_clamped_to_zero(self):
        """PAUSE 动作改善不低于 0。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(
            action_type=ActionType.PAUSE_CAMPAIGN,
            expected_impact={"direction": "positive"},
        )
        imp = evaluator._compute_improvement(
            "roas", "positive", -0.20, action  # ROAS 下降 20%
        )
        assert imp == 0.0  # PAUSE 不产生负改善


# ──────────────────────────────────────────────
# Outcome 判定测试
# ──────────────────────────────────────────────


class TestOutcomeDetermination:
    def test_success(self):
        """improvement > 0.15 → SUCCESS。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.50}
        post = {"roas": 0.65}  # +30% > 15%
        outcome, success = evaluator._determine_outcome(
            0.30, False, pre, post, "roas"
        )
        assert outcome == ExperienceOutcome.SUCCESS
        assert success is True

    def test_marginal(self):
        """0 < improvement ≤ 0.15 → MARGINAL。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.50}
        post = {"roas": 0.55}  # +10%
        outcome, success = evaluator._determine_outcome(
            0.10, False, pre, post, "roas"
        )
        assert outcome == ExperienceOutcome.MARGINAL
        assert success is False

    def test_failure(self):
        """improvement ≤ 0 → FAILURE。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.50}
        post = {"roas": 0.45}  # -10%
        outcome, success = evaluator._determine_outcome(
            -0.10, False, pre, post, "roas"
        )
        assert outcome == ExperienceOutcome.FAILURE
        assert success is False

    def test_inconclusive_missing_metric(self):
        """目标指标缺失 → INCONCLUSIVE。"""
        evaluator = OutcomeEvaluator()
        pre = {"spend": 100}
        post = {"spend": 120}
        outcome, success = evaluator._determine_outcome(
            0.20, False, pre, post, "roas"  # roas 不在 pre/post 中
        )
        assert outcome == ExperienceOutcome.INCONCLUSIVE
        assert success is False

    def test_inconclusive_zero_pre(self):
        """pre=0 → INCONCLUSIVE（无法计算百分比）。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.0}
        post = {"roas": 0.5}
        outcome, success = evaluator._determine_outcome(
            0.5, False, pre, post, "roas"
        )
        assert outcome == ExperienceOutcome.INCONCLUSIVE

    def test_rollback_forces_failure(self):
        """回滚触发 → 强制 FAILURE（即使 improvement > 0.15）。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.50}
        post = {"roas": 0.80}
        outcome, success = evaluator._determine_outcome(
            0.30, True, pre, post, "roas"  # rollback=True
        )
        assert outcome == ExperienceOutcome.FAILURE
        assert success is False

    def test_unknown_metric_inconclusive(self):
        """metric=unknown → INCONCLUSIVE。"""
        evaluator = OutcomeEvaluator()
        pre = {"roas": 0.5}
        post = {"roas": 0.6}
        outcome, _ = evaluator._determine_outcome(
            0.20, False, pre, post, "unknown"
        )
        assert outcome == ExperienceOutcome.INCONCLUSIVE


# ──────────────────────────────────────────────
# 回滚检测测试
# ──────────────────────────────────────────────


class TestRollbackDetection:
    def test_positive_direction_rollback(self):
        """direction=positive, 指标下降 > 10% → 回滚。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "positive"})
        pre = {"roas": 0.50}
        post = {"roas": 0.40}  # -20% < -10%
        assert evaluator._check_rollback(action, pre, post, "roas", "positive") is True

    def test_negative_direction_rollback(self):
        """direction=negative, 指标上升 > 10% → 回滚。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "negative"})
        pre = {"cpi": 5.0}
        post = {"cpi": 6.5}  # +30% > 10%
        assert evaluator._check_rollback(action, pre, post, "cpi", "negative") is True

    def test_no_rollback_small_change(self):
        """变化 < 10% → 不回滚。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "positive"})
        pre = {"roas": 0.50}
        post = {"roas": 0.47}  # -6% > -10%
        assert evaluator._check_rollback(action, pre, post, "roas", "positive") is False

    def test_no_rollback_correct_direction(self):
        """指标按预期方向变化 → 不回滚。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "positive"})
        pre = {"roas": 0.50}
        post = {"roas": 0.80}  # +60%, 正方向
        assert evaluator._check_rollback(action, pre, post, "roas", "positive") is False

    def test_unknown_metric_no_rollback(self):
        """metric=unknown → 不回滚。"""
        evaluator = OutcomeEvaluator()
        action = _make_action()
        assert evaluator._check_rollback(
            action, {"x": 1}, {"x": 0}, "none", "positive"
        ) is False

    def test_zero_pre_no_rollback(self):
        """pre=0 → 不回滚（无法计算变化）。"""
        evaluator = OutcomeEvaluator()
        action = _make_action(expected_impact={"direction": "positive"})
        assert evaluator._check_rollback(
            action, {"roas": 0}, {"roas": 1}, "roas", "positive"
        ) is False


# ──────────────────────────────────────────────
# 经验写入测试
# ──────────────────────────────────────────────


class TestExperienceWriting:
    def test_update_budget_writes_experience(self):
        """UPDATE_BUDGET 动作 → 写入经验。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(ActionType.UPDATE_BUDGET)
        pre = {"roas": 0.50, "spend": 200}
        post = {"roas": 0.70, "spend": 140}

        evaluator.evaluate(action, pre, post)
        assert len(store) == 1

    def test_pause_writes_experience(self):
        """PAUSE_CAMPAIGN 动作 → 写入经验。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(ActionType.PAUSE_CAMPAIGN)
        pre = {"roas": 0.50}
        post = {"roas": 0.60}

        evaluator.evaluate(action, pre, post)
        assert len(store) == 1

    def test_noop_does_not_write(self):
        """NOOP 动作 → 不写入。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(ActionType.NOOP)
        pre = {"roas": 0.50}
        post = {"roas": 0.60}

        evaluator.evaluate(action, pre, post)
        assert len(store) == 0

    def test_skipped_does_not_write(self):
        """SKIPPED 状态 → 不写入。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(
            ActionType.UPDATE_BUDGET, status=ActionStatus.SKIPPED
        )
        pre = {"roas": 0.50}
        post = {"roas": 0.60}

        evaluator.evaluate(action, pre, post)
        assert len(store) == 0

    def test_no_store_does_not_crash(self):
        """store=None → 只评估不写入，不崩溃。"""
        evaluator = OutcomeEvaluator(None)
        action = _make_action()
        pre = {"roas": 0.50}
        post = {"roas": 0.70}

        outcome = evaluator.evaluate(action, pre, post)
        assert outcome.outcome == ExperienceOutcome.SUCCESS

    def test_experience_record_fields(self):
        """写入的 ExperienceRecord 字段正确。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(
            ActionType.UPDATE_BUDGET,
            signal_id="fs_001",
            expected_impact={
                "metric": "roas",
                "direction": "positive",
                "estimated_change": 0.15,
                "strategy_type": "suppress",
            },
        )
        pre = {"roas": 0.50, "spend": 200}
        post = {"roas": 0.70, "spend": 140}

        outcome = evaluator.evaluate(action, pre, post)
        record = store.query_all()[0]

        # creative_id
        assert record.creative_id == "c_001"
        # mutation 从 strategy_type 推导
        assert record.mutation.mutation_type == MutationType.REFRESH_HOOK
        assert "hook" in record.mutation.changed_genes
        # experiment
        assert record.experiment.baseline_metrics["roas"] == 0.50
        assert record.experiment.winner_metrics["roas"] == 0.70
        assert record.experiment.improvement == outcome.improvement
        assert record.experiment.confidence == 0.75
        # result
        assert record.result.outcome == ExperienceOutcome.SUCCESS
        assert record.result.success is True
        assert record.result.insight != ""
        # related_ids (全链路)
        assert record.related_ids["signal_id"] == "fs_001"
        assert record.related_ids["diagnosis_id"] == "diag_001"
        assert record.related_ids["hypothesis_id"] == "hyp_001"
        assert record.related_ids["strategy_id"] == "strat_001"
        assert record.related_ids["action_id"] == action.action_id
        assert record.related_ids["outcome_id"] == outcome.outcome_id

    def test_experience_mutation_type_for_pause(self):
        """PAUSE 动作 → FULL_REBUILD mutation。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(
            ActionType.PAUSE_CAMPAIGN,
            expected_impact={
                "metric": "roas",
                "direction": "positive",
                "strategy_type": "pause",
            },
        )
        pre = {"roas": 0.50}
        post = {"roas": 0.60}

        evaluator.evaluate(action, pre, post)
        record = store.query_all()[0]
        assert record.mutation.mutation_type == MutationType.FULL_REBUILD

    def test_experience_mutation_type_for_scale(self):
        """SCALE 动作 → VISUAL_VARIATION mutation。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        action = _make_action(
            ActionType.UPDATE_BUDGET,
            expected_impact={
                "metric": "roas",
                "direction": "positive",
                "strategy_type": "scale",
            },
        )
        pre = {"roas": 0.50}
        post = {"roas": 0.70}

        evaluator.evaluate(action, pre, post)
        record = store.query_all()[0]
        assert record.mutation.mutation_type == MutationType.VISUAL_VARIATION


# ──────────────────────────────────────────────
# 批量评估测试
# ──────────────────────────────────────────────


class TestBatchEvaluation:
    def test_batch_multiple_actions(self):
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        actions_with_metrics = [
            (
                _make_action(ActionType.UPDATE_BUDGET, creative_id="c_1"),
                {"roas": 0.5},
                {"roas": 0.7},
            ),
            (
                _make_action(ActionType.PAUSE_CAMPAIGN, creative_id="c_2"),
                {"roas": 0.5},
                {"roas": 0.6},
            ),
        ]
        outcomes = evaluator.evaluate_batch(actions_with_metrics)

        assert len(outcomes) == 2
        assert all(o.outcome == ExperienceOutcome.SUCCESS for o in outcomes)
        assert len(store) == 2

    def test_batch_empty(self):
        evaluator = OutcomeEvaluator()
        assert evaluator.evaluate_batch([]) == []

    def test_batch_mixed_noop(self):
        """批量中含 NOOP → NOOP 不写入经验。"""
        store = ExperienceStore()
        evaluator = OutcomeEvaluator(store)
        actions_with_metrics = [
            (
                _make_action(ActionType.UPDATE_BUDGET, creative_id="c_1"),
                {"roas": 0.5},
                {"roas": 0.7},
            ),
            (
                _make_action(ActionType.NOOP, creative_id="c_2"),
                {"roas": 0.5},
                {"roas": 0.6},
            ),
        ]
        outcomes = evaluator.evaluate_batch(actions_with_metrics)

        assert len(outcomes) == 2
        assert len(store) == 1  # 只有 UPDATE_BUDGET 写入


# ──────────────────────────────────────────────
# End-to-End: Strategy → Action → Evaluate
# ──────────────────────────────────────────────


class TestEndToEnd:
    def test_suppress_success(self):
        """SUPPRESS → UPDATE_BUDGET → 评估成功 → 写入经验。"""
        store = ExperienceStore()
        # 1. 策略
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        strat.hypothesis_id = "hyp_e2e"
        strat.diagnosis_id = "diag_e2e"

        # 2. 动作
        planner = ActionPlanner()
        adset_map = {"c_001": "adset_e2e"}
        budgets = {"adset_e2e": 200.0}
        actions = planner.plan(strat, adset_map, budgets)
        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.UPDATE_BUDGET

        # 3. 评估（ROAS 从 0.50 → 0.70, +40% > 15% → SUCCESS）
        evaluator = OutcomeEvaluator(store)
        pre = {"roas": 0.50, "spend": 200, "ctr": 0.02}
        post = {"roas": 0.70, "spend": 140, "ctr": 0.025}
        outcome = evaluator.evaluate(action, pre, post)

        # 验证评估结果
        assert outcome.outcome == ExperienceOutcome.SUCCESS
        assert outcome.success is True
        assert outcome.improvement > 0.15
        assert outcome.target_metric == "roas"

        # 验证经验写入
        assert len(store) == 1
        record = store.query_all()[0]
        assert record.is_success is True
        assert record.improvement > 0.15

        # 全链路追溯
        assert record.related_ids["strategy_id"] == strat.strategy_id
        assert record.related_ids["action_id"] == action.action_id
        assert record.related_ids["outcome_id"] == outcome.outcome_id

    def test_suppress_failure_rollback(self):
        """SUPPRESS → ROAS 继续下降 > 10% → 回滚 → FAILURE。"""
        store = ExperienceStore()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        planner = ActionPlanner()
        actions = planner.plan(strat, {"c_001": "adset_1"}, {"adset_1": 200})
        action = actions[0]

        # ROAS 从 0.50 → 0.40, -20% < -10% → 回滚
        evaluator = OutcomeEvaluator(store)
        pre = {"roas": 0.50}
        post = {"roas": 0.40}
        outcome = evaluator.evaluate(action, pre, post)

        assert outcome.rollback_triggered is True
        assert outcome.outcome == ExperienceOutcome.FAILURE
        assert outcome.success is False

    def test_pause_marginal(self):
        """PAUSE → ROAS 小幅恢复 → MARGINAL。"""
        store = ExperienceStore()
        strat = _make_strategy(StrategyType.PAUSE, 1.0)
        planner = ActionPlanner()
        actions = planner.plan(strat, {"c_001": "adset_1"}, {"adset_1": 200})
        action = actions[0]
        assert action.action_type == ActionType.PAUSE_CAMPAIGN

        # ROAS 从 0.50 → 0.55, +10% → MARGINAL
        evaluator = OutcomeEvaluator(store)
        pre = {"roas": 0.50}
        post = {"roas": 0.55}
        outcome = evaluator.evaluate(action, pre, post)

        assert outcome.outcome == ExperienceOutcome.MARGINAL
        assert outcome.improvement == pytest.approx(0.10, abs=0.001)

    def test_inconclusive_missing_post_metric(self):
        """post 缺少目标指标 → INCONCLUSIVE。"""
        evaluator = OutcomeEvaluator()
        action = _make_action()
        pre = {"roas": 0.50}
        post = {"spend": 140}  # 没有 roas

        outcome = evaluator.evaluate(action, pre, post)
        assert outcome.outcome == ExperienceOutcome.INCONCLUSIVE

    def test_outcome_to_dict_full_chain(self):
        """outcome.to_dict 包含全链路 ID。"""
        store = ExperienceStore()
        strat = _make_strategy(signal_id="fs_dict")
        planner = ActionPlanner()
        actions = planner.plan(strat, {"c_001": "adset_1"}, {"adset_1": 200})
        action = actions[0]

        evaluator = OutcomeEvaluator(store)
        outcome = evaluator.evaluate(action, {"roas": 0.5}, {"roas": 0.7})

        d = outcome.to_dict()
        assert d["signal_id"] == "fs_dict"
        assert d["strategy_id"] == strat.strategy_id
        assert d["action_id"] == action.action_id
        assert d["outcome"] == "success"
        assert d["is_actionable"] is True


# ──────────────────────────────────────────────
# 闭环验证: 经验增强下一轮假设生成
# ──────────────────────────────────────────────


class TestGrowthLoopClosure:
    def test_experience_enhances_next_hypothesis(self):
        """闭环验证: 执行结果写入经验 → 下一轮假设 basis 从 signal 升级为 historical。"""
        from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
            ContextDetail,
            ExperimentDetail,
            ExperienceResult,
            MutationDetail,
        )

        # 1. 空 store → 第一轮假设 basis=signal
        empty_store = ExperienceStore()
        diag = DiagnosisResult(
            signal_id="fs_loop",
            creative_id="c_loop",
            signal_type="roas_decline",
            root_cause=RootCause.CREATIVE_FATIGUE,
            confidence=0.85,
            recommended_strategy_type=StrategyType.SUPPRESS,
        )
        hyp_gen_1 = HypothesisGenerator(empty_store)
        hyp_1 = hyp_gen_1.generate(diag)
        assert hyp_1.basis == "signal"  # 无历史数据

        # 2. 写入 5 条成功经验
        store = ExperienceStore()
        for i in range(5):
            store.add(
                ExperienceRecord(
                    product_id="P01",
                    creative_id=f"c_{i}",
                    mutation=MutationDetail(
                        mutation_type=MutationType.REFRESH_HOOK,
                        changed_genes=["hook"],
                    ),
                    experiment=ExperimentDetail(
                        improvement=0.25,
                        confidence=0.8,
                    ),
                    context=ContextDetail(
                        product_id="P01", platform="facebook"
                    ),
                    result=ExperienceResult(
                        outcome=ExperienceOutcome.SUCCESS,
                        success=True,
                    ),
                )
            )

        # 3. 有历史经验 → 第二轮假设 basis 升级
        hyp_gen_2 = HypothesisGenerator(store)
        hyp_2 = hyp_gen_2.generate(diag)
        assert hyp_2.basis in ("historical", "mixed")
        # 置信度应因历史成功而提升
        assert hyp_2.confidence >= hyp_1.confidence

    def test_full_growth_loop(self):
        """完整 Growth Loop: 信号 → 诊断 → 假设 → 策略 → 动作 → 评估 → 经验 → 下一轮假设。"""
        from dataclasses import dataclass
        from enum import Enum

        @dataclass
        class _MockSignal:
            signal_id: str = "fs_full"
            creative_id: str = "c_full"
            signal_type: str = "roas_decline"

        store = ExperienceStore()

        # 预置 2 条历史经验（后续评估写入 1 条，共 3 条触发 basis 升级）
        from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
            ExperimentDetail as _ED,
            ExperienceResult as _ER,
            MutationDetail as _MD,
        )
        for i in range(2):
            store.add(ExperienceRecord(
                product_id="P01",
                creative_id=f"c_prev_{i}",
                mutation=_MD(mutation_type=MutationType.REFRESH_HOOK, changed_genes=["hook"]),
                experiment=_ED(improvement=0.20, confidence=0.8),
                context=ContextDetail(product_id="P01", platform="facebook"),
                result=_ER(outcome=ExperienceOutcome.SUCCESS, success=True),
            ))

        # Step 1: 诊断
        engine = DiagnosticEngine()
        diag = engine.diagnose(
            _MockSignal(),
            {"spend": 200, "clicks": 60, "ctr": 0.015, "cpi": 5.0,
             "roas": 0.4, "impressions": 12000, "installs": 2000, "revenue": 80},
            {"spend": 200, "clicks": 100, "ctr": 0.025, "cpi": 5.0,
             "roas": 0.6, "impressions": 10000, "installs": 2000, "revenue": 120},
        )
        assert diag.root_cause == RootCause.CREATIVE_FATIGUE

        # Step 2: 假设（已有 2 条历史, 但 < 3 → basis=signal）
        hyp_gen = HypothesisGenerator(store)
        hyp = hyp_gen.generate(diag)
        assert hyp.basis == "signal"

        # Step 3: 策略
        selector = StrategySelector(store)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.SUPPRESS

        # Step 4: 动作
        planner = ActionPlanner()
        adset_map = {"c_full": "adset_full"}
        budgets = {"adset_full": 300.0}
        actions = planner.plan(strat, adset_map, budgets)
        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.UPDATE_BUDGET

        # Step 5: 评估（ROAS 从 0.40 → 0.65, +62.5% → SUCCESS）
        evaluator = OutcomeEvaluator(store)
        pre = {"roas": 0.40, "spend": 300, "ctr": 0.015}
        post = {"roas": 0.65, "spend": 210, "ctr": 0.022}
        outcome = evaluator.evaluate(action, pre, post, observation_window_days=7)

        assert outcome.outcome == ExperienceOutcome.SUCCESS
        assert len(store) == 3  # 2 预置 + 1 新评估

        # Step 6: 下一轮假设生成（有 3 条历史经验, basis 升级）
        hyp_gen_2 = HypothesisGenerator(store)
        hyp_2 = hyp_gen_2.generate(diag)
        assert hyp_2.basis in ("historical", "mixed", "pattern")

        # 全链路追溯: 最后一条经验记录包含所有 ID
        record = store.query_all()[-1]  # 最新写入的
        assert record.related_ids["signal_id"] == "fs_full"
        assert record.related_ids["diagnosis_id"] == diag.diagnosis_id
        assert record.related_ids["hypothesis_id"] == hyp.hypothesis_id
        assert record.related_ids["strategy_id"] == strat.strategy_id
        assert record.related_ids["action_id"] == action.action_id
        assert record.related_ids["outcome_id"] == outcome.outcome_id

    def test_failure_experience_also_written(self):
        """失败经验也写入 store（用于后续避免重复错误）。"""
        store = ExperienceStore()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        planner = ActionPlanner()
        actions = planner.plan(strat, {"c_001": "adset_1"}, {"adset_1": 200})
        action = actions[0]

        # ROAS 恶化 → FAILURE
        evaluator = OutcomeEvaluator(store)
        outcome = evaluator.evaluate(action, {"roas": 0.5}, {"roas": 0.4})

        assert outcome.outcome == ExperienceOutcome.FAILURE
        assert len(store) == 1
        record = store.query_all()[0]
        assert record.result.outcome == ExperienceOutcome.FAILURE
        assert record.is_success is False
