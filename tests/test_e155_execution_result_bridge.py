"""E15.5 Execution Result Bridge 测试 — 执行结果到经验记忆的桥接测试.

测试覆盖:
  - BridgeEntry 创建与状态
  - capture() 基本流程
  - evaluate() 业务结果评估
  - bridge() 一步桥接
  - 指标变化计算 (delta)
  - 改善分数计算 (improvement_score)
  - Reward 计算
  - 结果等级分类
  - 学习摘要生成
  - GrowthExperience 创建
  - ExperienceStore 写入
  - 真实场景模拟 (ROAS +59% after creative_refresh)
  - 批量桥接
  - 查询与统计
  - 边界情况
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.execution.feedback.execution_result_bridge import (
    BridgeEntry,
    BridgeResult,
    ExecutionResultBridge,
    BUSINESS_METRIC_WEIGHTS,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.execution_core import (
    EngineResult,
)
from market_ops.creative_vision_runtime.growth_runtime.execution.base_executor import (
    ExecutionResultStatus,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.experience_store import (
    ExperienceStore,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    ExperienceOutcomeLevel,
    GrowthExperience,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_engine_result(
    plan_id: str = "plan_001",
    success_count: int = 5,
    failure_count: int = 0,
    total_nodes: int = 5,
) -> EngineResult:
    """创建测试用 EngineResult."""
    status = (
        ExecutionResultStatus.SUCCESS
        if failure_count == 0
        else ExecutionResultStatus.FAILED
    )
    return EngineResult(
        plan_id=plan_id,
        task_id="task_001",
        total_nodes=total_nodes,
        success_count=success_count,
        failure_count=failure_count,
        status=status,
    )


# ═══════════════════════════════════════════════════════════════
# Test: BridgeEntry
# ═══════════════════════════════════════════════════════════════


class TestBridgeEntry:
    """BridgeEntry 数据模型测试."""

    def test_create_default(self):
        entry = BridgeEntry()
        assert entry.bridge_id
        assert entry.engine_result is None
        assert entry.metrics_before == {}
        assert entry.action_type == ""
        assert not entry.has_metrics_before
        assert not entry.is_ready

    def test_create_with_metrics(self):
        entry = BridgeEntry(
            metrics_before={"roas": 0.42, "ctr": 0.021},
            action_type="replace_creative",
        )
        assert entry.has_metrics_before
        assert not entry.is_ready  # no engine_result

    def test_create_with_engine_result(self):
        er = _make_engine_result()
        entry = BridgeEntry(
            engine_result=er,
            metrics_before={"roas": 0.42},
            action_type="replace_creative",
        )
        assert entry.is_ready
        assert entry.has_metrics_before

    def test_to_dict(self):
        er = _make_engine_result()
        entry = BridgeEntry(
            engine_result=er,
            metrics_before={"roas": 0.42},
            action_type="replace_creative",
            opportunity_id="opp_001",
            decision_id="dec_001",
        )
        d = entry.to_dict()
        assert d["action_type"] == "replace_creative"
        assert d["opportunity_id"] == "opp_001"
        assert d["decision_id"] == "dec_001"
        assert d["metrics_before"] == {"roas": 0.42}
        assert d["engine_result"] is not None

    def test_unique_bridge_id(self):
        e1 = BridgeEntry()
        e2 = BridgeEntry()
        assert e1.bridge_id != e2.bridge_id

    def test_repr(self):
        entry = BridgeEntry(action_type="replace_creative")
        r = repr(entry)
        assert "BridgeEntry" in r
        assert "replace_creative" in r


# ═══════════════════════════════════════════════════════════════
# Test: BridgeResult
# ═══════════════════════════════════════════════════════════════


class TestBridgeResult:
    """BridgeResult 数据模型测试."""

    def test_create_default(self):
        result = BridgeResult()
        assert result.bridge_id == ""
        assert result.reward == 0.0
        assert result.improvement_score == 0.0
        assert result.outcome_level == "neutral"
        assert not result.is_successful
        assert not result.is_significant_improvement
        assert not result.is_degradation

    def test_successful(self):
        result = BridgeResult(improvement_score=0.20)
        assert result.is_successful
        assert result.is_significant_improvement
        assert not result.is_degradation

    def test_degradation(self):
        result = BridgeResult(improvement_score=-0.15)
        assert not result.is_successful
        assert not result.is_significant_improvement
        assert result.is_degradation

    def test_neutral(self):
        result = BridgeResult(improvement_score=0.03)
        assert not result.is_successful
        assert not result.is_degradation

    def test_to_dict(self):
        result = BridgeResult(
            bridge_id="b001",
            reward=0.82,
            improvement_score=0.21,
            outcome_level="success",
            metrics_delta={"roas": 0.214, "ctr": 0.09},
            learning_summary="ROAS improved by 21%",
            experience_stored=True,
        )
        d = result.to_dict()
        assert d["reward"] == 0.82
        assert d["improvement_score"] == 0.21
        assert d["outcome_level"] == "success"
        assert d["is_successful"] is True
        assert d["experience_stored"] is True

    def test_significant_improvement_threshold(self):
        # 刚好超过 15%
        result = BridgeResult(improvement_score=0.151)
        assert result.is_significant_improvement
        # 低于 15%
        result2 = BridgeResult(improvement_score=0.149)
        assert not result2.is_significant_improvement

    def test_repr(self):
        result = BridgeResult(
            bridge_id="b001",
            improvement_score=0.21,
            outcome_level="success",
        )
        r = repr(result)
        assert "BridgeResult" in r
        assert "+21.0%" in r


# ═══════════════════════════════════════════════════════════════
# Test: ExecutionResultBridge — Capture
# ═══════════════════════════════════════════════════════════════


class TestBridgeCapture:
    """Capture 测试."""

    def test_capture_basic(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.42, "ctr": 0.021},
            action_type="replace_creative",
            opportunity_id="opp_001",
        )
        assert entry.bridge_id
        assert entry.engine_result is not None
        assert entry.metrics_before == {"roas": 0.42, "ctr": 0.021}
        assert entry.action_type == "replace_creative"
        assert entry.opportunity_id == "opp_001"
        assert entry.is_ready
        assert bridge.pending_count == 1

    def test_capture_adds_to_pending(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5})
        bridge.capture(engine_result=er, metrics_before={"roas": 0.6})
        bridge.capture(engine_result=er, metrics_before={"roas": 0.7})
        assert bridge.pending_count == 3

    def test_capture_with_context(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        from market_ops.creative_vision_runtime.growth_runtime.execution.execution_context import (
            ExecutionContext,
        )
        ctx = ExecutionContext(opportunity_id="ctx_opp", decision_id="ctx_dec")
        entry = bridge.capture(
            engine_result=er,
            context=ctx,
            metrics_before={"roas": 0.5},
        )
        assert entry.opportunity_id == "ctx_opp"
        assert entry.decision_id == "ctx_dec"

    def test_capture_context_override(self):
        """显式传入的 ID 优先于 context 中的."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        from market_ops.creative_vision_runtime.growth_runtime.execution.execution_context import (
            ExecutionContext,
        )
        ctx = ExecutionContext(opportunity_id="ctx_opp")
        entry = bridge.capture(
            engine_result=er,
            context=ctx,
            metrics_before={"roas": 0.5},
            opportunity_id="explicit_opp",
        )
        assert entry.opportunity_id == "explicit_opp"

    def test_capture_batch(self):
        bridge = ExecutionResultBridge()
        er1 = _make_engine_result("plan_1", 5, 0, 5)
        er2 = _make_engine_result("plan_2", 3, 2, 5)
        entries = bridge.capture_batch(
            engine_results=[er1, er2],
            metrics_before_list=[{"roas": 0.5}, {"roas": 0.6}],
            action_types=["scale", "pause_campaign"],
            opportunity_ids=["opp_1", "opp_2"],
        )
        assert len(entries) == 2
        assert entries[0].action_type == "scale"
        assert entries[1].action_type == "pause_campaign"
        assert bridge.pending_count == 2

    def test_capture_capacity_control(self):
        bridge = ExecutionResultBridge(max_pending=3)
        er = _make_engine_result()
        for i in range(5):
            bridge.capture(engine_result=er, metrics_before={"roas": float(i)})
        assert bridge.pending_count <= 3


# ═══════════════════════════════════════════════════════════════
# Test: ExecutionResultBridge — Evaluate
# ═══════════════════════════════════════════════════════════════


class TestBridgeEvaluate:
    """Evaluate 测试."""

    def test_evaluate_improvement(self):
        """ROAS 从 0.32 升到 0.51 → 改善."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.32, "ctr": 0.021, "cvr": 0.08},
            action_type="replace_creative",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.51, "ctr": 0.028, "cvr": 0.11},
        )
        assert result.improvement_score > 0.1  # ROAS +59%
        assert result.is_successful
        assert result.outcome_level in ("success", "strong_success")
        assert result.metrics_delta["roas"] > 0.5
        assert "ROAS" in result.learning_summary

    def test_evaluate_degradation(self):
        """ROAS 从 0.50 降到 0.30 → 退化."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.50, "ctr": 0.025, "cvr": 0.10},
            action_type="replace_creative",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.30, "ctr": 0.020, "cvr": 0.08},
        )
        assert result.improvement_score < -0.05
        assert result.is_degradation
        assert result.outcome_level in ("failure", "strong_failure")
        assert "declined" in result.learning_summary or "degradation" in result.learning_summary

    def test_evaluate_neutral(self):
        """ROAS 基本不变 → 中性."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.50, "ctr": 0.025},
            action_type="scale",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.51, "ctr": 0.026},
        )
        assert abs(result.improvement_score) < 0.05
        assert result.outcome_level == "neutral"

    def test_evaluate_removes_from_pending(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.5},
            action_type="scale",
        )
        assert bridge.pending_count == 1
        bridge.evaluate(entry, metrics_after={"roas": 0.6})
        assert bridge.pending_count == 0

    def test_evaluate_by_id(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.5},
            action_type="scale",
        )
        result = bridge.evaluate_by_id(entry.bridge_id, {"roas": 0.6})
        assert result is not None
        assert result.improvement_score > 0

    def test_evaluate_by_id_not_found(self):
        bridge = ExecutionResultBridge()
        result = bridge.evaluate_by_id("nonexistent", {"roas": 0.6})
        assert result is None

    def test_evaluate_with_execution_failure(self):
        """执行失败但业务指标改善."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result(
            plan_id="plan_fail",
            success_count=2,
            failure_count=3,
            total_nodes=5,
        )
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.3},
            action_type="replace_creative",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.35},
        )
        # 业务改善但执行质量差 → reward 应低于纯改善
        assert result.reward < 0.85  # 执行质量拖低 reward

    def test_evaluate_strong_success(self):
        """ROAS 大幅提升 > 30% + 高 reward."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.30, "ctr": 0.020, "cvr": 0.07, "cpi": 5.0},
            action_type="replace_creative",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.55, "ctr": 0.032, "cvr": 0.12, "cpi": 3.0},
        )
        assert result.outcome_level == "strong_success"
        assert result.is_significant_improvement

    def test_evaluate_strong_failure(self):
        """ROAS 大幅下降 > 30% + 低 reward."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result(success_count=2, failure_count=3, total_nodes=5)
        entry = bridge.capture(
            engine_result=er,
            metrics_before={"roas": 0.70, "ctr": 0.035, "cvr": 0.12, "cpi": 3.0},
            action_type="scale",
        )
        result = bridge.evaluate(
            entry=entry,
            metrics_after={"roas": 0.20, "ctr": 0.012, "cvr": 0.05, "cpi": 6.0},
        )
        assert result.outcome_level == "strong_failure"
        assert result.is_degradation


# ═══════════════════════════════════════════════════════════════
# Test: ExecutionResultBridge — Bridge (一步)
# ═══════════════════════════════════════════════════════════════


class TestBridgeOneShot:
    """一步桥接 (bridge) 测试."""

    def test_bridge_basic(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.32, "ctr": 0.021},
            metrics_after={"roas": 0.51, "ctr": 0.028},
            action_type="replace_creative",
            opportunity_id="opp_001",
        )
        assert result.improvement_score > 0.1
        assert result.is_successful
        assert result.bridge_id

    def test_bridge_batch(self):
        bridge = ExecutionResultBridge()
        er1 = _make_engine_result("plan_1")
        er2 = _make_engine_result("plan_2")
        results = bridge.bridge_batch(
            engine_results=[er1, er2],
            metrics_before_list=[
                {"roas": 0.40, "ctr": 0.020},
                {"roas": 0.50, "ctr": 0.025},
            ],
            metrics_after_list=[
                {"roas": 0.55, "ctr": 0.027},
                {"roas": 0.45, "ctr": 0.022},
            ],
            action_types=["replace_creative", "scale"],
            opportunity_ids=["opp_1", "opp_2"],
        )
        assert len(results) == 2
        assert results[0].is_successful  # ROAS improved
        assert results[1].is_degradation  # ROAS dropped

    def test_bridge_with_metadata(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5},
            metrics_after={"roas": 0.6},
            action_type="scale",
            metadata={"product_id": "P04", "game": "merge_game"},
        )
        assert result.metadata.get("product_id") == "P04"


# ═══════════════════════════════════════════════════════════════
# Test: Metric Computation
# ═══════════════════════════════════════════════════════════════


class TestMetricComputation:
    """指标计算测试."""

    def test_compute_delta_positive(self):
        deltas = ExecutionResultBridge._compute_metrics_delta(
            {"roas": 0.40}, {"roas": 0.60}
        )
        assert deltas["roas"] == pytest.approx(0.50)

    def test_compute_delta_negative(self):
        deltas = ExecutionResultBridge._compute_metrics_delta(
            {"roas": 0.60}, {"roas": 0.30}
        )
        assert deltas["roas"] == pytest.approx(-0.50)

    def test_compute_delta_zero_before(self):
        deltas = ExecutionResultBridge._compute_metrics_delta(
            {"roas": 0.0}, {"roas": 0.50}
        )
        assert deltas["roas"] == pytest.approx(1.0)

    def test_compute_delta_multi_metric(self):
        deltas = ExecutionResultBridge._compute_metrics_delta(
            {"roas": 0.40, "ctr": 0.020, "cvr": 0.08},
            {"roas": 0.60, "ctr": 0.030, "cvr": 0.12},
        )
        assert deltas["roas"] == pytest.approx(0.50)
        assert deltas["ctr"] == pytest.approx(0.50)
        assert deltas["cvr"] == pytest.approx(0.50)

    def test_improvement_score_all_positive(self):
        score = ExecutionResultBridge._compute_improvement_score({
            "roas": 0.50, "ctr": 0.50, "cvr": 0.50, "cpi": -0.30,
        })
        # CPI is LOWER_IS_BETTER, so -0.30 becomes +0.30
        # weighted: 0.35*0.50 + 0.25*0.50 + 0.20*0.50 + 0.20*0.30 = 0.175+0.125+0.10+0.06 = 0.46
        assert score == pytest.approx(0.46, abs=0.02)

    def test_improvement_score_all_negative(self):
        score = ExecutionResultBridge._compute_improvement_score({
            "roas": -0.50, "ctr": -0.50, "cvr": -0.50, "cpi": 0.30,
        })
        # CPI +0.30 (worse) → -0.30
        # weighted: 0.35*(-0.50) + 0.25*(-0.50) + 0.20*(-0.50) + 0.20*(-0.30) = -0.175-0.125-0.10-0.06 = -0.46
        assert score == pytest.approx(-0.46, abs=0.02)

    def test_improvement_score_partial_metrics(self):
        """只有部分指标有数据."""
        score = ExecutionResultBridge._compute_improvement_score({
            "roas": 0.30,
        })
        # Only roas weight 0.35 contributes: 0.35*0.30 = 0.105, total_weight = 0.35
        assert score == pytest.approx(0.30, abs=0.01)

    def test_reward_with_engine_result(self):
        er = _make_engine_result(success_count=5, total_nodes=5)  # success_rate=1.0
        reward = ExecutionResultBridge._compute_reward(0.50, er)
        # outcome_reward = (0.50+1.0)/2.0 = 0.75
        # 0.7*0.75 + 0.3*1.0 = 0.525 + 0.3 = 0.825
        assert reward == pytest.approx(0.825, abs=0.01)

    def test_reward_no_engine_result(self):
        reward = ExecutionResultBridge._compute_reward(0.20, None)
        # outcome_reward = (0.20+1.0)/2.0 = 0.60
        # 0.7*0.60 + 0.3*1.0 = 0.42 + 0.3 = 0.72
        assert reward == pytest.approx(0.72, abs=0.01)

    def test_reward_negative_improvement(self):
        er = _make_engine_result(success_count=5, total_nodes=5)
        reward = ExecutionResultBridge._compute_reward(-0.30, er)
        # outcome_reward = (-0.30+1.0)/2.0 = 0.35
        # 0.7*0.35 + 0.3*1.0 = 0.245 + 0.3 = 0.545
        assert reward == pytest.approx(0.545, abs=0.01)


# ═══════════════════════════════════════════════════════════════
# Test: Outcome Classification
# ═══════════════════════════════════════════════════════════════


class TestOutcomeClassification:
    """结果等级分类测试."""

    def test_strong_success(self):
        level = ExecutionResultBridge._classify_outcome(0.35, 0.80)
        assert level == "strong_success"

    def test_success(self):
        level = ExecutionResultBridge._classify_outcome(0.10, 0.60)
        assert level == "success"

    def test_neutral(self):
        level = ExecutionResultBridge._classify_outcome(0.03, 0.50)
        assert level == "neutral"

    def test_failure(self):
        level = ExecutionResultBridge._classify_outcome(-0.10, 0.40)
        assert level == "failure"

    def test_strong_failure(self):
        level = ExecutionResultBridge._classify_outcome(-0.35, 0.20)
        assert level == "strong_failure"

    def test_boundary_success(self):
        """刚好在成功边界."""
        level = ExecutionResultBridge._classify_outcome(0.051, 0.50)
        assert level == "success"

    def test_boundary_neutral(self):
        """刚好在中性边界."""
        level = ExecutionResultBridge._classify_outcome(0.049, 0.50)
        assert level == "neutral"


# ═══════════════════════════════════════════════════════════════
# Test: Learning Summary
# ═══════════════════════════════════════════════════════════════


class TestLearningSummary:
    """学习摘要生成测试."""

    def test_improvement_summary(self):
        summary = ExecutionResultBridge._generate_learning_summary(
            improvement_score=0.21,
            metrics_delta={"roas": 0.59, "ctr": 0.10},
            metrics_before={"roas": 0.32, "ctr": 0.021},
            metrics_after={"roas": 0.51, "ctr": 0.028},
            action_type="replace_creative",
        )
        assert "replace_creative" in summary
        assert "improved" in summary
        assert "21" in summary

    def test_degradation_summary(self):
        summary = ExecutionResultBridge._generate_learning_summary(
            improvement_score=-0.15,
            metrics_delta={"roas": -0.25},
            metrics_before={"roas": 0.50},
            metrics_after={"roas": 0.375},
            action_type="scale",
        )
        assert "degradation" in summary

    def test_neutral_summary(self):
        summary = ExecutionResultBridge._generate_learning_summary(
            improvement_score=0.02,
            metrics_delta={"roas": 0.03},
            metrics_before={"roas": 0.50},
            metrics_after={"roas": 0.515},
            action_type="scale",
        )
        assert "no significant change" in summary

    def test_empty_delta(self):
        summary = ExecutionResultBridge._generate_learning_summary(
            improvement_score=0.0,
            metrics_delta={},
            metrics_before={},
            metrics_after={},
        )
        assert "No metrics delta" in summary

    def test_cpi_decrease_positive(self):
        """CPI 下降是好事."""
        summary = ExecutionResultBridge._generate_learning_summary(
            improvement_score=0.15,
            metrics_delta={"cpi": -0.30},
            metrics_before={"cpi": 5.0},
            metrics_after={"cpi": 3.5},
            action_type="replace_creative",
        )
        assert "decreased" in summary


# ═══════════════════════════════════════════════════════════════
# Test: ExperienceStore Integration
# ═══════════════════════════════════════════════════════════════


class TestExperienceStoreIntegration:
    """ExperienceStore 集成测试."""

    def test_bridge_writes_to_experience_store(self):
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.32, "ctr": 0.021},
            metrics_after={"roas": 0.51, "ctr": 0.028},
            action_type="replace_creative",
            opportunity_id="opp_roas_recovery",
            metadata={"product_id": "P04", "creative_id": "crt_001"},
        )
        assert result.experience_stored
        assert result.experience is not None
        assert store.count == 1

    def test_bridge_creates_growth_experience(self):
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.42, "ctr": 0.021, "cvr": 0.08},
            metrics_after={"roas": 0.51, "ctr": 0.028, "cvr": 0.11},
            action_type="replace_creative",
            metadata={"product_id": "P04", "creative_id": "crt_001"},
        )
        exp = result.experience
        assert isinstance(exp, GrowthExperience)
        assert exp.action_type == "replace_creative"
        assert exp.outcome.success is True
        assert exp.reward > 0.5
        assert exp.context.product_id == "P04"

    def test_multiple_bridges_accumulate(self):
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()
        for i in range(5):
            bridge.bridge(
                engine_result=er,
                metrics_before={"roas": 0.5},
                metrics_after={"roas": 0.5 + 0.05 * i},
                action_type="replace_creative",
            )
        assert store.count == 5

    def test_experience_category_creative(self):
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.4},
            metrics_after={"roas": 0.5},
            action_type="replace_creative",
        )
        assert result.experience.category.value == "creative"

    def test_experience_category_ua(self):
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.4},
            metrics_after={"roas": 0.5},
            action_type="scale",
        )
        assert result.experience.category.value == "ua"

    def test_bridge_without_store(self):
        """没有 ExperienceStore 也能正常工作."""
        bridge = ExecutionResultBridge()  # no store
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5},
            metrics_after={"roas": 0.6},
            action_type="scale",
        )
        assert not result.experience_stored
        assert result.experience is None  # 没有 store 时不创建 experience


# ═══════════════════════════════════════════════════════════════
# Test: Real UA Scenario
# ═══════════════════════════════════════════════════════════════


class TestRealUAScenario:
    """真实 UA 场景模拟."""

    def test_creative_refresh_roas_recovery(self):
        """素材刷新后 ROAS 恢复场景.

        场景:
          before: ROAS D7 = 0.32, CTR = 0.021, CVR = 0.08
          action: creative_refresh (replace_creative)
          after:  ROAS D7 = 0.51, CTR = 0.028, CVR = 0.11
        """
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()

        # 模拟用户描述的素材疲劳场景
        result = bridge.bridge(
            engine_result=er,
            metrics_before={
                "roas": 0.32,
                "ctr": 0.021,
                "cvr": 0.08,
            },
            metrics_after={
                "roas": 0.51,
                "ctr": 0.028,
                "cvr": 0.11,
            },
            action_type="replace_creative",
            opportunity_id="opp_fatigue_001",
            metadata={
                "product_id": "P04",
                "creative_id": "crt_fatigue_001",
                "game": "merge_game",
                "country": "US",
                "platform": "iOS",
                "reason": "ROAS decay -35%, fatigue score 0.82",
            },
        )

        # 验证结果
        assert result.is_successful
        assert result.is_significant_improvement  # ROAS +59% > 15%
        assert result.outcome_level == "strong_success"
        assert result.reward > 0.75
        assert result.experience_stored
        assert "ROAS" in result.learning_summary
        assert "improved" in result.learning_summary

        # 验证 Experience 写入
        exp = result.experience
        assert exp.context.product_id == "P04"
        assert exp.context.entity_id == "crt_fatigue_001"
        assert exp.reward > 0.75
        assert exp.is_successful()

    def test_pause_campaign_prevent_loss(self):
        """暂停止损场景.

        场景:
          before: ROAS = 0.42, CTR = 0.025
          action: pause_campaign (止损)
          after:  ROAS = 0.30 (假设继续跑会更差, 但暂停避免了损失)
        """
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()

        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.42, "ctr": 0.025, "cvr": 0.09},
            metrics_after={"roas": 0.35, "ctr": 0.022, "cvr": 0.08},
            action_type="pause_campaign",
            opportunity_id="opp_roas_drop",
            metadata={"product_id": "P04", "campaign_id": "camp_001"},
        )

        # 暂停后指标继续恶化 (因为存量数据), 但避免了下行风险
        # 这里业务指标可能显示退化, 但 prevention 类型的 reward 逻辑不同
        assert result.experience_stored
        assert result.experience.category.value == "ua"

    def test_scale_success(self):
        """放量成功场景.

        场景:
          before: ROAS = 0.55, CTR = 0.028
          action: scale (放量 1.3x)
          after:  ROAS = 0.62, CTR = 0.030
        """
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()

        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.55, "ctr": 0.028, "cvr": 0.12},
            metrics_after={"roas": 0.62, "ctr": 0.030, "cvr": 0.13},
            action_type="scale",
            opportunity_id="opp_scale_001",
            metadata={"product_id": "P04", "campaign_id": "camp_scale_001"},
        )

        assert result.is_successful
        assert result.experience_stored
        assert result.experience.category.value == "ua"

    def test_scale_failure(self):
        """放量失败场景.

        场景:
          before: ROAS = 0.60, CTR = 0.030
          action: scale (放量 2x)
          after:  ROAS = 0.45, CTR = 0.025  (边际递减)
        """
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()

        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.60, "ctr": 0.030, "cvr": 0.12},
            metrics_after={"roas": 0.45, "ctr": 0.025, "cvr": 0.10},
            action_type="scale",
            opportunity_id="opp_scale_fail",
            metadata={"product_id": "P04"},
        )

        assert result.is_degradation
        assert result.experience is not None
        assert result.experience.outcome.outcome_level == ExperienceOutcomeLevel.FAILURE

    def test_multi_action_sequence(self):
        """多动作序列场景: pause + creative_refresh.

        模拟 Day 3 验收中的真实场景:
          1. PAUSE campaign (止损)
          2. MUTATE creative (素材刷新)
        """
        store = ExperienceStore()
        bridge = ExecutionResultBridge(experience_store=store)
        er = _make_engine_result()

        # Action 1: PAUSE
        r1 = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.27, "ctr": 0.018},
            metrics_after={"roas": 0.30, "ctr": 0.020},
            action_type="pause_campaign",
            opportunity_id="opp_critical_001",
            metadata={"priority": "critical"},
        )

        # Action 2: MUTATE (creative_refresh)
        r2 = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.32, "ctr": 0.021, "cvr": 0.08},
            metrics_after={"roas": 0.51, "ctr": 0.028, "cvr": 0.11},
            action_type="replace_creative",
            opportunity_id="opp_high_001",
            metadata={"priority": "high"},
        )

        assert r1.experience_stored
        assert r2.experience_stored
        assert r2.is_significant_improvement
        assert store.count == 2

        # 验证 ExperienceStore 可以按 action_type 查询
        creative_exps = store.get_by_action_type("replace_creative")
        assert len(creative_exps) == 1
        assert creative_exps[0].reward > 0.75

        ua_exps = store.get_by_action_type("pause_campaign")
        assert len(ua_exps) == 1


# ═══════════════════════════════════════════════════════════════
# Test: Query & Statistics
# ═══════════════════════════════════════════════════════════════


class TestBridgeQueryAndStats:
    """查询与统计测试."""

    def test_get_pending(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5}, action_type="scale")
        bridge.capture(engine_result=er, metrics_before={"roas": 0.6}, action_type="replace_creative")
        assert bridge.pending_count == 2
        pending = bridge.get_pending()
        assert len(pending) == 2

    def test_get_pending_by_action(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5}, action_type="scale")
        bridge.capture(engine_result=er, metrics_before={"roas": 0.6}, action_type="replace_creative")
        assert len(bridge.get_pending_by_action("scale")) == 1
        assert len(bridge.get_pending_by_action("replace_creative")) == 1
        assert len(bridge.get_pending_by_action("nonexistent")) == 0

    def test_get_pending_by_opportunity(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5}, opportunity_id="opp_1")
        bridge.capture(engine_result=er, metrics_before={"roas": 0.6}, opportunity_id="opp_2")
        assert len(bridge.get_pending_by_opportunity("opp_1")) == 1

    def test_get_history(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        for i in range(5):
            bridge.bridge(
                engine_result=er,
                metrics_before={"roas": 0.5},
                metrics_after={"roas": 0.5 + 0.02 * i},
                action_type="scale",
            )
        assert len(bridge.get_history()) == 5
        assert len(bridge.get_history(limit=3)) == 3

    def test_get_successful(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        # 好的
        bridge.bridge(er, {"roas": 0.4}, {"roas": 0.6}, action_type="scale")
        # 坏的
        bridge.bridge(er, {"roas": 0.6}, {"roas": 0.4}, action_type="scale")
        # 好的
        bridge.bridge(er, {"roas": 0.3}, {"roas": 0.5}, action_type="replace_creative")
        assert len(bridge.get_successful()) == 2
        assert len(bridge.get_degradations()) == 1

    def test_get_significant_improvements(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.bridge(er, {"roas": 0.3}, {"roas": 0.55}, action_type="replace_creative")  # sig
        bridge.bridge(er, {"roas": 0.4}, {"roas": 0.45}, action_type="scale")  # not sig
        assert len(bridge.get_significant_improvements()) == 1

    def test_stats_empty(self):
        bridge = ExecutionResultBridge()
        stats = bridge.stats()
        assert stats["total_bridged"] == 0
        assert stats["success_rate"] == 0.0

    def test_stats_with_data(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.bridge(er, {"roas": 0.4}, {"roas": 0.6}, action_type="scale")
        bridge.bridge(er, {"roas": 0.6}, {"roas": 0.4}, action_type="scale")
        bridge.bridge(er, {"roas": 0.3}, {"roas": 0.5}, action_type="replace_creative")
        stats = bridge.stats()
        assert stats["total_bridged"] == 3
        assert stats["successful_count"] == 2
        assert stats["degradation_count"] == 1
        assert stats["success_rate"] > 0.5
        assert "by_action" in stats

    def test_get_improvement_trend(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        for i in range(5):
            bridge.bridge(
                er,
                {"roas": 0.5},
                {"roas": 0.5 + 0.03 * i},
                action_type="scale",
            )
        trend = bridge.get_improvement_trend()
        assert len(trend) == 5
        # 趋势应为递增
        assert trend[-1] > trend[0]

    def test_get_by_action(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.bridge(er, {"roas": 0.4}, {"roas": 0.6}, action_type="scale")
        bridge.bridge(er, {"roas": 0.3}, {"roas": 0.5}, action_type="replace_creative")
        assert len(bridge.get_by_action("scale")) == 1
        assert len(bridge.get_by_action("replace_creative")) == 1

    def test_total_bridged_counter(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        for i in range(3):
            bridge.bridge(er, {"roas": 0.5}, {"roas": 0.5 + i * 0.05}, action_type="scale")
        assert bridge.total_bridged == 3
        assert bridge.history_count == 3


# ═══════════════════════════════════════════════════════════════
# Test: Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestBridgeEdgeCases:
    """边界情况测试."""

    def test_empty_metrics(self):
        """空指标."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={},
            metrics_after={},
            action_type="scale",
        )
        assert result.improvement_score == 0.0
        assert result.outcome_level == "neutral"

    def test_zero_metrics_before(self):
        """执行前指标全为 0."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.0, "ctr": 0.0},
            metrics_after={"roas": 0.5, "ctr": 0.025},
        )
        assert result.improvement_score > 0

    def test_same_metrics(self):
        """指标完全不变."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5, "ctr": 0.025},
            metrics_after={"roas": 0.5, "ctr": 0.025},
        )
        assert result.improvement_score == pytest.approx(0.0)
        assert result.outcome_level == "neutral"

    def test_extra_metrics_in_after(self):
        """执行后指标比执行前多."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5},
            metrics_after={"roas": 0.55, "cvr": 0.10},
        )
        assert "cvr" in result.metrics_delta

    def test_cpi_improvement(self):
        """CPI 下降 (改善)."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5, "cpi": 5.0},
            metrics_after={"roas": 0.6, "cpi": 3.5},
        )
        # CPI delta = -0.30, but LOWER_IS_BETTER so it's +0.30 in improvement
        assert result.improvement_score > 0.05

    def test_cpi_worsening(self):
        """CPI 上升 (恶化)."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.5, "cpi": 3.0},
            metrics_after={"roas": 0.45, "cpi": 5.0},
        )
        assert result.improvement_score < -0.05

    def test_clear_pending(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5})
        bridge.capture(engine_result=er, metrics_before={"roas": 0.6})
        assert bridge.pending_count == 2
        bridge.clear_pending()
        assert bridge.pending_count == 0

    def test_clear_history(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.bridge(er, {"roas": 0.5}, {"roas": 0.6}, action_type="scale")
        assert bridge.history_count == 1
        bridge.clear_history()
        assert bridge.history_count == 0

    def test_reset(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        bridge.capture(engine_result=er, metrics_before={"roas": 0.5})
        bridge.bridge(er, {"roas": 0.5}, {"roas": 0.6}, action_type="scale")
        # bridge()'s capture+evaluate removes its own entry, but the first capture() entry remains
        assert bridge.pending_count == 1
        assert bridge.history_count == 1
        bridge.reset()
        assert bridge.pending_count == 0
        assert bridge.history_count == 0
        assert bridge.total_bridged == 0

    def test_large_improvement_clamped(self):
        """极大改善时 reward 不超过 1.0."""
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        result = bridge.bridge(
            engine_result=er,
            metrics_before={"roas": 0.01},
            metrics_after={"roas": 10.0},
        )
        assert result.reward <= 1.0

    def test_expire_old_entries(self):
        bridge = ExecutionResultBridge()
        er = _make_engine_result()
        entry = bridge.capture(engine_result=er, metrics_before={"roas": 0.5})
        # 修改 captured_at 使条目看起来过期
        old_time = "2020-01-01T00:00:00+00:00"
        # 直接修改 pending 中的 entry
        bridge._pending[entry.bridge_id].captured_at = old_time
        expired = bridge.expire_old_entries(max_age_hours=1)
        assert expired >= 1
        assert bridge.pending_count == 0

    def test_engine_result_failure_affects_reward(self):
        """执行失败时 reward 更低."""
        bridge = ExecutionResultBridge()
        er_success = _make_engine_result(success_count=5, failure_count=0, total_nodes=5)
        er_failure = _make_engine_result(success_count=2, failure_count=3, total_nodes=5)

        r_success = bridge.bridge(
            er_success, {"roas": 0.4}, {"roas": 0.5}, action_type="scale"
        )
        r_failure = bridge.bridge(
            er_failure, {"roas": 0.4}, {"roas": 0.5}, action_type="scale"
        )
        # 相同业务改善, 执行质量差 → reward 低
        assert r_failure.reward < r_success.reward

    def test_bridge_entry_repr(self):
        entry = BridgeEntry(action_type="scale")
        r = repr(entry)
        assert "BridgeEntry" in r

    def test_bridge_result_repr(self):
        result = BridgeResult(improvement_score=0.15, outcome_level="success")
        r = repr(result)
        assert "BridgeResult" in r
        assert "+15.0%" in r


# ═══════════════════════════════════════════════════════════════
# Test: Constants
# ═══════════════════════════════════════════════════════════════


class TestConstants:
    """常量测试."""

    def test_business_metric_weights_sum(self):
        """权重和应接近 1.0."""
        total = sum(BUSINESS_METRIC_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_higher_is_better(self):
        assert "roas" in HIGHER_IS_BETTER
        assert "ctr" in HIGHER_IS_BETTER
        assert "cvr" in HIGHER_IS_BETTER

    def test_lower_is_better(self):
        assert "cpi" in LOWER_IS_BETTER
        assert "cpa" in LOWER_IS_BETTER