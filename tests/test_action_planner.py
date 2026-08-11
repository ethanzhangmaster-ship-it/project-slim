"""ActionPlanner 单元测试。

覆盖:
  - 策略 → 动作映射（SUPPRESS/SCALE/REFRESH/PAUSE/MAINTAIN）
  - 预算参数构建（current → target + 安全边界）
  - 风险等级计算
  - 审批需求计算
  - 缺失 adset_id 跳过
  - 批量生成
  - end-to-end: Diagnosis → Hypothesis → Strategy → Action
  - 序列化
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from src.market_ops.creative_vision_runtime.reality.meta_learning.models import (
    ContextDetail,
    ExperimentDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceResult,
    MutationDetail,
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


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


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


ADSET_MAP = {"c_001": "adset_123", "c_002": "adset_456"}
BUDGETS = {"adset_123": 200.0, "adset_456": 500.0}


# ──────────────────────────────────────────────
# 数据模型测试
# ──────────────────────────────────────────────


class TestExecutionActionModel:
    def test_auto_id_and_timestamp(self):
        a = ExecutionAction()
        assert a.action_id.startswith("exec_")
        assert a.created_at != ""

    def test_source_signal_id_auto_filled(self):
        a = ExecutionAction(signal_id="fs_001")
        assert a.source_signal_id == "fs_001"

    def test_to_dict_serializable(self):
        a = ExecutionAction(
            action_type=ActionType.UPDATE_BUDGET,
            adset_id="adset_1",
            parameters={"target_budget": 140},
            budget_impact=-60.0,
            risk_level="medium",
        )
        d = a.to_dict()
        assert d["action_type"] == "update_budget"
        assert d["adset_id"] == "adset_1"
        assert d["budget_impact"] == -60.0
        assert d["risk_level"] == "medium"
        assert "is_noop" in d
        assert "needs_execution" in d

    def test_is_noop(self):
        assert ExecutionAction(action_type=ActionType.NOOP).is_noop is True
        assert ExecutionAction(action_type=ActionType.UPDATE_BUDGET).is_noop is False

    def test_needs_execution(self):
        a = ExecutionAction(action_type=ActionType.UPDATE_BUDGET)
        assert a.needs_execution is True

        a_skip = ExecutionAction(
            action_type=ActionType.UPDATE_BUDGET,
            status=ActionStatus.SKIPPED,
        )
        assert a_skip.needs_execution is False

        a_noop = ExecutionAction(action_type=ActionType.NOOP)
        assert a_noop.needs_execution is False


# ──────────────────────────────────────────────
# 策略 → 动作映射测试
# ──────────────────────────────────────────────


class TestStrategyToActionMapping:
    def test_suppress_produces_update_budget(self):
        """SUPPRESS → UPDATE_BUDGET (reduce=True)。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.UPDATE_BUDGET
        assert actions[0].adset_id == "adset_123"

    def test_scale_produces_update_budget(self):
        """SCALE → UPDATE_BUDGET (reduce=False)。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SCALE, 1.20)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.UPDATE_BUDGET

    def test_refresh_produces_pause(self):
        """REFRESH → PAUSE_CAMPAIGN。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.REFRESH, 1.0)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.PAUSE_CAMPAIGN

    def test_pause_produces_pause(self):
        """PAUSE → PAUSE_CAMPAIGN。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.PAUSE, 1.0)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.PAUSE_CAMPAIGN

    def test_maintain_produces_noop(self):
        """MAINTAIN → NOOP (skipped)。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.MAINTAIN, 1.0)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.NOOP
        assert actions[0].status == ActionStatus.SKIPPED


# ──────────────────────────────────────────────
# 预算参数构建测试
# ──────────────────────────────────────────────


class TestBudgetParameters:
    def test_suppress_reduces_budget(self):
        """SUPPRESS 0.70 + $200 → target $140。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        params = actions[0].parameters
        assert params["current_budget"] == 200.0
        assert params["target_budget"] == 140.0
        assert params["change_ratio"] == 0.70
        assert actions[0].budget_impact == -60.0

    def test_scale_increases_budget(self):
        """SCALE 1.20 + $200 → target $240。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SCALE, 1.20)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        params = actions[0].parameters
        assert params["current_budget"] == 200.0
        assert params["target_budget"] == 240.0
        assert actions[0].budget_impact == 40.0

    def test_change_pct_calculated(self):
        """change_pct 正确计算。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert actions[0].parameters["change_pct"] == -30.0

    def test_min_daily_budget_floor(self):
        """目标预算不低于 $20 底线。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.10)  # 极端降
        budgets = {"adset_123": 30.0}
        actions = planner.plan(strat, ADSET_MAP, budgets)

        # 30 * 0.10 = 3, 但 min floor = 20
        assert actions[0].parameters["target_budget"] >= 20.0

    def test_max_reduce_50pct(self):
        """降预算不超过 50%。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.10)  # 要求降 90%
        budgets = {"adset_123": 1000.0}
        actions = planner.plan(strat, ADSET_MAP, budgets)

        # 1000 * 0.10 = 100, 但 max reduce 50% → min 500
        assert actions[0].parameters["target_budget"] >= 500.0

    def test_max_increase_30pct(self):
        """升预算不超过 30%。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SCALE, 2.0)  # 要求升 100%
        budgets = {"adset_123": 1000.0}
        actions = planner.plan(strat, ADSET_MAP, budgets)

        # 1000 * 2.0 = 2000, 但 max increase 30% → max 1300
        assert actions[0].parameters["target_budget"] <= 1300.0

    def test_zero_budget_produces_zero_target(self):
        """当前预算为 0 → 目标预算为 min_floor。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        budgets = {"adset_123": 0.0}
        actions = planner.plan(strat, ADSET_MAP, budgets)

        assert actions[0].parameters["target_budget"] == 20.0  # min floor


# ──────────────────────────────────────────────
# 风险等级与审批测试
# ──────────────────────────────────────────────


class TestRiskAndApproval:
    def test_small_budget_low_risk(self):
        """<$50 → low risk, 自动执行。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.90)  # $200 → $180, -$20
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert actions[0].risk_level == "low"
        assert actions[0].requires_approval is False
        assert actions[0].approval_level == 0

    def test_medium_budget_warn(self):
        """$50-$200 → medium risk。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)  # $200 → $140, -$60
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert actions[0].risk_level == "medium"
        assert actions[0].requires_approval is False

    def test_large_budget_approval(self):
        """$200-$500 → high risk, 需确认。"""
        planner = ActionPlanner()
        strat = _make_strategy(
            StrategyType.SUPPRESS, 0.50, creative_id="c_002"
        )  # $500 → $250, -$250
        budgets = {"adset_456": 500.0}
        adset_map = {"c_002": "adset_456"}
        actions = planner.plan(strat, adset_map, budgets)

        assert actions[0].risk_level == "high"
        assert actions[0].requires_approval is True
        assert actions[0].approval_level == 1

    def test_huge_budget_block(self):
        """>$500 → critical risk, 需审批。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.50)
        budgets = {"adset_123": 2000.0}
        actions = planner.plan(strat, ADSET_MAP, budgets)

        # $2000 → $1000, -$1000 > $500
        assert actions[0].risk_level == "critical"
        assert actions[0].requires_approval is True
        assert actions[0].approval_level == 2

    def test_pause_zero_budget_impact(self):
        """PAUSE → budget_impact=0, medium risk。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.PAUSE, 1.0)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert actions[0].budget_impact == 0.0
        assert actions[0].risk_level == "medium"
        assert actions[0].requires_approval is False


# ──────────────────────────────────────────────
# 缺失 adset_id 测试
# ──────────────────────────────────────────────


class TestMissingAdsetId:
    def test_missing_adset_skipped(self):
        """creative_id 无映射 → SKIPPED。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70, creative_id="c_unknown")
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert len(actions) == 1
        assert actions[0].status == ActionStatus.SKIPPED
        assert "adset_id" in actions[0].reason
        assert actions[0].action_type == ActionType.NOOP

    def test_empty_map_skipped(self):
        """空映射表 → SKIPPED。"""
        planner = ActionPlanner()
        strat = _make_strategy()
        actions = planner.plan(strat, {}, {})

        assert actions[0].status == ActionStatus.SKIPPED

    def test_none_map_skipped(self):
        """None 映射表 → SKIPPED。"""
        planner = ActionPlanner()
        strat = _make_strategy()
        actions = planner.plan(strat, None, None)

        assert actions[0].status == ActionStatus.SKIPPED


# ──────────────────────────────────────────────
# 全链路追溯测试
# ──────────────────────────────────────────────


class TestTraceability:
    def test_action_contains_all_ids(self):
        """ExecutionAction 包含全链路 ID。"""
        planner = ActionPlanner()
        strat = _make_strategy(
            signal_id="fs_001",
        )
        strat.hypothesis_id = "hyp_001"
        strat.diagnosis_id = "diag_001"
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        a = actions[0]
        assert a.signal_id == "fs_001"
        assert a.source_signal_id == "fs_001"
        assert a.strategy_id == strat.strategy_id
        assert a.hypothesis_id == "hyp_001"
        assert a.diagnosis_id == "diag_001"

    def test_reason_contains_strategy_and_root_cause(self):
        """reason 包含策略类型和根因。"""
        planner = ActionPlanner()
        strat = _make_strategy(root_cause="creative_fatigue")
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        assert "suppress" in actions[0].reason
        assert "creative_fatigue" in actions[0].reason


# ──────────────────────────────────────────────
# 批量生成测试
# ──────────────────────────────────────────────


class TestBatchPlan:
    def test_batch_multiple_strategies(self):
        planner = ActionPlanner()
        strategies = [
            _make_strategy(StrategyType.SUPPRESS, 0.70, creative_id="c_001"),
            _make_strategy(StrategyType.SCALE, 1.20, creative_id="c_002"),
            _make_strategy(StrategyType.MAINTAIN, 1.0, creative_id="c_003"),
        ]
        actions = planner.plan_batch(strategies, ADSET_MAP, BUDGETS)

        assert len(actions) == 3
        types = {a.action_type for a in actions}
        assert ActionType.UPDATE_BUDGET in types
        assert ActionType.NOOP in types

    def test_batch_empty(self):
        planner = ActionPlanner()
        assert planner.plan_batch([], ADSET_MAP, BUDGETS) == []

    def test_batch_missing_adset_skipped(self):
        """批量中部分缺失 adset_id → 对应动作 SKIPPED。"""
        planner = ActionPlanner()
        strategies = [
            _make_strategy(creative_id="c_001"),  # 有映射
            _make_strategy(creative_id="c_missing"),  # 无映射
        ]
        actions = planner.plan_batch(strategies, ADSET_MAP, BUDGETS)

        assert len(actions) == 2
        assert actions[0].status == ActionStatus.PENDING
        assert actions[1].status == ActionStatus.SKIPPED


# ──────────────────────────────────────────────
# End-to-End: Diagnosis → Hypothesis → Strategy → Action
# ──────────────────────────────────────────────


class TestEndToEnd:
    def test_full_chain_creative_fatigue(self):
        """完整链路: 信号 → 诊断 → 假设 → 策略 → 动作。"""
        from dataclasses import dataclass
        from enum import Enum

        class _SigType(str, Enum):
            ROAS_DECLINE = "roas_decline"

        @dataclass
        class _MockSignal:
            signal_id: str = "fs_e2e"
            creative_id: str = "c_e2e"
            signal_type: _SigType = _SigType.ROAS_DECLINE

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

        # Step 2: 假设
        store = _build_store(5, improvement=0.25)
        hyp_gen = HypothesisGenerator(store)
        hyp = hyp_gen.generate(diag, {"total_records": 10, "success_rate": 0.7})

        # Step 3: 策略
        selector = StrategySelector(store)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.SUPPRESS

        # Step 4: 动作
        planner = ActionPlanner()
        adset_map = {"c_e2e": "adset_e2e"}
        budgets = {"adset_e2e": 300.0}
        actions = planner.plan(strat, adset_map, budgets)

        # 验证动作
        assert len(actions) == 1
        a = actions[0]
        assert a.action_type == ActionType.UPDATE_BUDGET
        assert a.adset_id == "adset_e2e"
        assert a.parameters["current_budget"] == 300.0
        assert a.parameters["target_budget"] < 300.0  # 降预算
        assert a.budget_impact < 0
        assert a.needs_execution is True

        # 全链路追溯
        assert a.signal_id == "fs_e2e"
        assert a.source_signal_id == "fs_e2e"
        assert a.diagnosis_id == diag.diagnosis_id
        assert a.hypothesis_id == hyp.hypothesis_id
        assert a.strategy_id == strat.strategy_id

    def test_maintain_chain_produces_noop(self):
        """undiagnosed → MAINTAIN → NOOP。"""
        # 诊断
        diag = DiagnosisResult(
            signal_id="fs_maintain",
            creative_id="c_maintain",
            signal_type="data_collection",
            root_cause=RootCause.UNDIAGNOSED,
            confidence=0.20,
            recommended_strategy_type=StrategyType.MAINTAIN,
        )
        # 假设
        hyp_gen = HypothesisGenerator(None)
        hyp = hyp_gen.generate(diag)
        # 策略
        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.MAINTAIN
        # 动作
        planner = ActionPlanner()
        actions = planner.plan(strat, {"c_maintain": "adset_1"}, {"adset_1": 100})

        assert len(actions) == 1
        assert actions[0].action_type == ActionType.NOOP
        assert actions[0].status == ActionStatus.SKIPPED
        assert actions[0].needs_execution is False

    def test_scale_chain_produces_budget_increase(self):
        """SCALE → UPDATE_BUDGET (increase)。"""
        diag = DiagnosisResult(
            signal_id="fs_scale",
            creative_id="c_scale",
            signal_type="scale_opportunity",
            root_cause=RootCause.UNDIAGNOSED,
            confidence=0.80,
            recommended_strategy_type=StrategyType.SCALE,
        )
        hyp_gen = HypothesisGenerator(None)
        hyp = hyp_gen.generate(diag)
        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)
        assert strat.strategy_type == StrategyType.SCALE

        planner = ActionPlanner()
        adset_map = {"c_scale": "adset_scale"}
        budgets = {"adset_scale": 200.0}
        actions = planner.plan(strat, adset_map, budgets)

        assert actions[0].action_type == ActionType.UPDATE_BUDGET
        assert actions[0].parameters["target_budget"] > 200.0
        assert actions[0].budget_impact > 0

    def test_action_to_dict_full_chain(self):
        """动作 to_dict 包含全链路 ID。"""
        diag = DiagnosisResult(
            signal_id="fs_dict",
            creative_id="c_dict",
            signal_type="roas_decline",
            root_cause=RootCause.CREATIVE_FATIGUE,
            confidence=0.85,
            recommended_strategy_type=StrategyType.SUPPRESS,
        )
        hyp_gen = HypothesisGenerator(None)
        hyp = hyp_gen.generate(diag)
        selector = StrategySelector(None)
        strat = selector.select(hyp, diag)
        planner = ActionPlanner()
        actions = planner.plan(
            strat, {"c_dict": "adset_dict"}, {"adset_dict": 200.0}
        )

        d = actions[0].to_dict()
        assert d["signal_id"] == "fs_dict"
        assert d["diagnosis_id"] == diag.diagnosis_id
        assert d["hypothesis_id"] == hyp.hypothesis_id
        assert d["strategy_id"] == strat.strategy_id
        assert d["action_type"] == "update_budget"
        assert d["needs_execution"] is True


# ──────────────────────────────────────────────
# 领域无关性测试
# ──────────────────────────────────────────────


class TestDomainAgnostic:
    def test_action_type_generic(self):
        """ActionType 不含平台特定术语。"""
        for at in ActionType:
            assert "facebook" not in at.value.lower()
            assert "meta" not in at.value.lower()
            assert "google" not in at.value.lower()

    def test_parameters_generic_keys(self):
        """parameters 使用通用键名。"""
        planner = ActionPlanner()
        strat = _make_strategy(StrategyType.SUPPRESS, 0.70)
        actions = planner.plan(strat, ADSET_MAP, BUDGETS)

        params = actions[0].parameters
        assert "adset_id" in params  # 通用广告术语
        assert "current_budget" in params
        assert "target_budget" in params
