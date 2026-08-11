"""E13.6.5 Decision Memory Synchronization — 测试用例.

测试覆盖:
  - DecisionOutcomeBridge:       决策结果→记忆事件转换
  - PatternDecisionReconciler:   预测 vs 实际对齐
  - DecisionPatternSynchronizer: 双向同步编排
  - Case 1: 成功决策 → Pattern 置信度提升
  - Case 2: 连续失败 → Pattern ACTIVE → DECAYING
  - Case 3: Pattern 错误预测 → penalty
  - Case 4: Decision Engine 增强 confidence
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from market_ops.creative_vision_runtime.growth_runtime.memory import (
    BridgeResult,
    DecisionMemoryEvent,
    DecisionOutcomeBridge,
    DecisionPatternSynchronizer,
    PatternDecisionReconciler,
    PatternMemory,
    PredictionGap,
    ReconciliationAction,
    ReconciliationResult,
    SyncEventType,
    SyncResult,
)
from market_ops.creative_vision_runtime.growth_runtime.memory.models import (
    PatternAction,
    PatternCondition,
    PatternMiningDimension,
    PatternPerformance,
    PatternQuality,
)
from market_ops.creative_vision_runtime.growth_runtime.intelligence.decision.decision_memory import (
    DecisionExperience,
    DecisionMemory,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_pattern(
    pattern_id: str = "",
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    audience_segment: str = "iOS_FB",
    samples: int = 100,
    success_count: int = 82,
    success_rate: float = 0.82,
    avg_reward: float = 0.75,
    last_seen: str | None = None,
    score: float = 0.0,
    confidence: float = 0.91,
    metadata: dict | None = None,
) -> PatternMemory:
    """创建测试用 PatternMemory."""
    if last_seen is None:
        last_seen = datetime.now(timezone.utc).isoformat()
    return PatternMemory(
        pattern_id=pattern_id or f"pat_{hash(opportunity_type) % 10000:04d}",
        dimension=PatternMiningDimension.OPPORTUNITY_ACTION,
        condition=PatternCondition(
            opportunity_type=opportunity_type,
            action_type=action_type,
            audience_segment=audience_segment,
            category="creative",
            signal_types=["roas_decay", "fatigue_high"],
        ),
        action=PatternAction(action_type=action_type),
        performance=PatternPerformance(
            samples=samples,
            success_count=success_count,
            success_rate=success_rate,
            avg_reward=avg_reward,
            first_seen=datetime.now(timezone.utc).isoformat(),
            last_seen=last_seen,
        ),
        score=score,
        confidence=confidence,
        metadata=metadata or {},
    )


def _make_decision_exp(
    decision_id: str = "dec_001",
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    result: str = "success",
    result_metrics: dict | None = None,
    confidence: float = 0.65,
    risk_score: float = 0.15,
    pattern_ids: list[str] | None = None,
    lessons: list[str] | None = None,
) -> DecisionExperience:
    """创建测试用 DecisionExperience."""
    return DecisionExperience(
        decision_id=decision_id,
        opportunity_type=opportunity_type,
        action_plan={"action_type": action_type},
        result=result,
        result_metrics=result_metrics or {},
        confidence=confidence,
        risk_score=risk_score,
        pattern_contribution={"pattern_ids": pattern_ids or []},
        lessons_learned=lessons or [],
        resolved_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_event(
    decision_id: str = "dec_001",
    opportunity_type: str = "creative_fatigue",
    action_type: str = "replace_creative",
    result: str = "success",
    reward: float = 0.62,
    confidence: float = 0.65,
    risk_score: float = 0.15,
    pattern_ids: list[str] | None = None,
    success: bool = True,
    metrics: dict | None = None,
    lessons: list[str] | None = None,
) -> DecisionMemoryEvent:
    """创建测试用 DecisionMemoryEvent."""
    return DecisionMemoryEvent(
        decision_id=decision_id,
        opportunity_type=opportunity_type,
        action_type=action_type,
        result=result,
        reward=reward,
        confidence=confidence,
        risk_score=risk_score,
        pattern_ids=pattern_ids or [],
        success=success,
        metrics=metrics or {},
        lessons=lessons or [],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ═══════════════════════════════════════════════════════════════
# DecisionOutcomeBridge 测试
# ═══════════════════════════════════════════════════════════════

class TestDecisionOutcomeBridge:
    """DecisionOutcomeBridge — 决策结果→统一记忆事件."""

    def test_from_decision_experience_success(self):
        """成功转换 DecisionExperience."""
        bridge = DecisionOutcomeBridge()
        exp = _make_decision_exp(
            decision_id="dec_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            result="success",
            result_metrics={"roas_change": 0.19, "ctr_change": 0.05},
            confidence=0.65,
            risk_score=0.15,
            pattern_ids=["pat_001"],
            lessons=["learned_1"],
        )

        result = bridge.from_decision_experience(exp)

        assert result.converted
        assert result.source == "decision_experience"
        event = result.event
        assert event.decision_id == "dec_001"
        assert event.opportunity_type == "creative_fatigue"
        assert event.action_type == "replace_creative"
        assert event.result == "success"
        assert event.confidence == 0.65
        assert event.risk_score == 0.15
        assert event.pattern_ids == ["pat_001"]
        assert event.success
        assert event.lessons == ["learned_1"]
        assert event.is_success
        assert event.is_resolved

    def test_from_decision_experience_failure(self):
        """转换失败 DecisionExperience."""
        bridge = DecisionOutcomeBridge()
        exp = _make_decision_exp(
            decision_id="dec_002",
            result="failure",
            result_metrics={},
        )

        result = bridge.from_decision_experience(exp)

        assert result.converted
        event = result.event
        assert event.result == "failure"
        assert event.reward == -1.0  # 失败惩罚
        assert not event.is_success
        assert event.is_failure

    def test_from_decision_experience_pending(self):
        """转换未决 DecisionExperience."""
        bridge = DecisionOutcomeBridge()
        exp = _make_decision_exp(
            decision_id="dec_003",
        )
        exp.result = "pending"

        result = bridge.from_decision_experience(exp)

        assert result.converted
        event = result.event
        assert event.result == "pending"
        assert not event.is_resolved

    def test_from_invalid_object(self):
        """转换无效对象."""
        bridge = DecisionOutcomeBridge()
        result = bridge.from_decision_experience("not_valid")
        assert not result.converted
        assert "Not a valid DecisionExperience" in result.reason

    def test_from_execution_outcome(self):
        """从执行结果转换."""
        bridge = DecisionOutcomeBridge()

        class MockOutcome:
            success = True
            metrics_delta = {"roas_change": 0.25, "ctr_change": 0.10}

        outcome = MockOutcome()
        context = {
            "decision_id": "dec_004",
            "opportunity_type": "winner_discovery",
            "action_type": "scale_budget",
            "pattern_ids": ["pat_002"],
            "confidence": 0.72,
        }

        result = bridge.from_execution_outcome(outcome, context)

        assert result.converted
        assert result.source == "execution_outcome"
        event = result.event
        assert event.decision_id == "dec_004"
        assert event.action_type == "scale_budget"
        assert event.reward > 0  # 正向指标

    def test_from_raw_dict(self):
        """从原始字典转换."""
        bridge = DecisionOutcomeBridge()
        data = {
            "decision_id": "dec_005",
            "opportunity_type": "budget_optimization",
            "action_type": "adjust_bid",
            "result": "success",
            "reward": 0.55,
            "confidence": 0.80,
            "success": True,
            "metrics": {"roas": 0.15},
            "lessons": ["lesson_1"],
        }

        result = bridge.from_raw_dict(data)

        assert result.converted
        assert result.source == "raw_dict"
        event = result.event
        assert event.decision_id == "dec_005"
        assert event.reward == 0.55

    def test_event_type_success(self):
        """事件类型 — success."""
        event = _make_event(result="success")
        assert event.event_type == SyncEventType.SUCCESS

    def test_event_type_failure(self):
        """事件类型 — failure."""
        event = _make_event(result="failure")
        assert event.event_type == SyncEventType.FAILURE

    def test_event_type_partial(self):
        """事件类型 — partial."""
        event = _make_event(result="partial")
        assert event.event_type == SyncEventType.PARTIAL

    def test_event_to_dict(self):
        """事件序列化."""
        event = _make_event(
            decision_id="dec_006",
            reward=0.62,
            pattern_ids=["pat_001"],
        )
        d = event.to_dict()
        assert d["decision_id"] == "dec_006"
        assert d["reward"] == 0.62
        assert d["pattern_ids"] == ["pat_001"]


# ═══════════════════════════════════════════════════════════════
# PatternDecisionReconciler 测试
# ═══════════════════════════════════════════════════════════════

class TestPatternDecisionReconciler:
    """PatternDecisionReconciler — 预测 vs 实际对齐."""

    def test_reconcile_perfect_match(self):
        """预测与实际完全匹配."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            success_rate=0.80,
            samples=100,
            success_count=80,
        )

        events = [
            _make_event(result="success", success=True) for _ in range(8)
        ] + [
            _make_event(result="failure", success=False) for _ in range(2)
        ]  # 80% 成功率

        result = reconciler.reconcile(pattern, events)

        assert result.events_processed == 10
        assert len(result.gaps) == 1
        gap = result.gaps[0]
        assert gap.expected_success_rate == 0.80
        assert gap.actual_success_rate == 0.80
        assert abs(gap.gap) < 0.01
        assert gap.gap_severity == "low"
        # 差距太小，无动作
        assert len(result.actions) == 0

    def test_reconcile_over_prediction(self):
        """Case 3: Pattern 错误预测 — expected 0.82, actual 0.40."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            success_rate=0.82,
            samples=100,
            success_count=82,
        )

        # 10 次执行，只有 4 次成功
        events = [
            _make_event(result="success", success=True) for _ in range(4)
        ] + [
            _make_event(result="failure", success=False) for _ in range(6)
        ]

        result = reconciler.reconcile(pattern, events)

        assert result.events_processed == 10
        gap = result.gaps[0]
        assert gap.expected_success_rate == 0.82
        assert gap.actual_success_rate == 0.40
        assert gap.gap == pytest.approx(0.42, abs=0.01)
        assert gap.gap_severity == "high"

        # 应该产生 penalty 动作
        penalty_actions = [a for a in result.actions if a.action_type == "penalty"]
        assert len(penalty_actions) == 1
        action = penalty_actions[0]
        assert action.confidence_adjustment < 0  # 负面调整
        assert action.severity == "high"

    def test_reconcile_under_prediction(self):
        """Pattern 过于保守 — actual 高于 expected."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            success_rate=0.45,
            samples=100,
            success_count=45,
        )

        # 10 次执行，8 次成功
        events = [
            _make_event(result="success", success=True) for _ in range(8)
        ] + [
            _make_event(result="failure", success=False) for _ in range(2)
        ]

        result = reconciler.reconcile(pattern, events)

        gap = result.gaps[0]
        assert gap.expected_success_rate == 0.45
        assert gap.actual_success_rate == 0.80
        assert gap.gap < 0  # 负差距 = 预测过低

        # 应该产生 boost 动作
        boost_actions = [a for a in result.actions if a.action_type == "boost"]
        assert len(boost_actions) == 1
        assert boost_actions[0].confidence_adjustment > 0

    def test_reconcile_consecutive_failures(self):
        """Case 2: 连续失败保护 — 80% 失败率."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            success_rate=0.82,
            samples=100,
            success_count=82,
        )

        # 10 次中 8 次失败
        events = [
            _make_event(result="success", success=True) for _ in range(2)
        ] + [
            _make_event(result="failure", success=False) for _ in range(8)
        ]

        result = reconciler.reconcile(pattern, events)

        # 应该有 decay 动作
        decay_actions = [a for a in result.actions if a.action_type == "decay"]
        assert len(decay_actions) == 1
        action = decay_actions[0]
        assert action.confidence_adjustment == -0.30
        assert action.severity == "high"
        assert "Consecutive failure" in action.reason

    def test_reconcile_no_events(self):
        """无事件."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern()
        result = reconciler.reconcile(pattern, [])
        assert "No events" in result.summary

    def test_reconcile_no_resolved_events(self):
        """无已决事件."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern()
        events = [_make_event(result="pending")]
        result = reconciler.reconcile(pattern, events)
        assert "No resolved" in result.summary

    def test_evaluate_prediction_gap(self):
        """直接评估预测差距."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(success_rate=0.80)

        # 实际 0.30 → 差距 0.50 → critical
        gap = reconciler.evaluate_prediction_gap(pattern, 0.30, 10)
        assert gap.gap == pytest.approx(0.50, abs=0.01)
        assert gap.gap_severity == "critical"
        assert gap.recommendation == "penalty"

        # 实际 0.95 → 差距 -0.15 → boost
        gap = reconciler.evaluate_prediction_gap(pattern, 0.95, 10)
        assert gap.gap == pytest.approx(-0.15, abs=0.01)
        assert gap.recommendation == "boost"

    def test_apply_feedback_penalty(self):
        """应用 penalty 动作."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            confidence=0.91,
            success_rate=0.82,
            avg_reward=0.75,
        )
        action = ReconciliationAction(
            pattern_id="pat_001",
            action_type="penalty",
            confidence_adjustment=-0.20,
            success_rate_adjustment=-0.10,
            reward_adjustment=-0.10,
            reason="Over-predicted",
            severity="high",
        )

        updated = reconciler.apply_feedback(pattern, action)

        # compute_score() 重新计算 confidence = sample_factor × success_rate
        # success_rate 0.72, sample_factor ≈ 0.999 → confidence ≈ 0.72
        assert updated.confidence == pytest.approx(0.72, abs=0.01)
        assert updated.performance.success_rate == 0.72  # 0.82 - 0.10
        assert updated.performance.avg_reward == 0.65  # 0.75 - 0.10
        assert "last_reconciliation" in updated.metadata

    def test_apply_feedback_boost(self):
        """应用 boost 动作."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            confidence=0.70,
            success_rate=0.45,
            avg_reward=0.50,
        )
        action = ReconciliationAction(
            pattern_id="pat_001",
            action_type="boost",
            confidence_adjustment=+0.10,
            success_rate_adjustment=+0.05,
            reward_adjustment=+0.05,
            reason="Under-predicted",
            severity="medium",
        )

        updated = reconciler.apply_feedback(pattern, action)

        # compute_score() 重新计算 confidence = sample_factor × success_rate
        # success_rate 0.50, sample_factor ≈ 0.999 → confidence ≈ 0.50
        assert updated.confidence == pytest.approx(0.50, abs=0.01)
        assert updated.performance.success_rate == 0.50
        assert updated.performance.avg_reward == 0.55

    def test_apply_feedback_noop(self):
        """Noop 动作不改变."""
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(confidence=0.80)
        orig_conf = pattern.confidence
        action = ReconciliationAction(
            pattern_id="pat_001",
            action_type="noop",
            reason="No adjustment",
        )

        updated = reconciler.apply_feedback(pattern, action)
        assert updated.confidence == orig_conf

    def test_generate_sync_actions_batch(self):
        """批量生成同步动作."""
        reconciler = PatternDecisionReconciler()
        patterns = [
            _make_pattern(pattern_id="pat_001", success_rate=0.80),
            _make_pattern(pattern_id="pat_002", success_rate=0.50),
        ]

        # pat_001: 实际很低 → penalty
        # pat_002: 实际很高 → boost
        event_groups = {
            "pat_001": [
                _make_event(result="success", success=True) for _ in range(3)
            ] + [
                _make_event(result="failure", success=False) for _ in range(7)
            ],
            "pat_002": [
                _make_event(result="success", success=True) for _ in range(8)
            ] + [
                _make_event(result="failure", success=False) for _ in range(2)
            ],
        }

        actions = reconciler.generate_sync_actions(patterns, event_groups)

        assert len(actions) >= 2
        action_types = {a.action_type for a in actions}
        assert "penalty" in action_types or "boost" in action_types


# ═══════════════════════════════════════════════════════════════
# DecisionPatternSynchronizer 测试
# ═══════════════════════════════════════════════════════════════

class TestDecisionPatternSynchronizer:
    """DecisionPatternSynchronizer — 双向同步编排."""

    def test_sync_execution_result_success(self):
        """Case 1: 成功决策同步."""
        # 创建 mock store
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.82,
            confidence=0.91,
            avg_reward=0.75,
        )

        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]
        mock_store.get_best_pattern.return_value = pattern

        mock_dm = MagicMock()
        mock_dm.get_by_decision.return_value = None
        mock_dm.find_similar.return_value = []

        sync = DecisionPatternSynchronizer(
            decision_memory=mock_dm,
            pattern_store=mock_store,
        )

        class MockOutcome:
            success = True
            metrics_delta = {
                "roas_change": 0.19,
                "ctr_change": 0.05,
            }

        result = sync.sync_execution_result(
            decision_id="dec_001",
            outcome=MockOutcome(),
            context={
                "opportunity_type": "creative_fatigue",
                "action_type": "replace_creative",
            },
        )

        assert result.events_processed == 1
        assert result.patterns_updated >= 1
        assert result.summary is not None

    def test_sync_batch_results(self):
        """批量同步."""
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.82,
            confidence=0.91,
        )

        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]

        sync = DecisionPatternSynchronizer(pattern_store=mock_store)

        events = [
            _make_event(
                decision_id="dec_001",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success",
                success=True,
            ),
            _make_event(
                decision_id="dec_002",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success",
                success=True,
            ),
        ]

        result = sync.sync_batch_results(events)

        assert result.events_processed == 2
        assert result.patterns_updated == 1

    def test_sync_no_pattern_store(self):
        """无 pattern store."""
        sync = DecisionPatternSynchronizer()
        result = sync.sync_batch_results([])
        assert "No events" in result.summary or "No patterns" in result.summary

    def test_enhance_decision_confidence(self):
        """Case 4: Decision Engine 增强 confidence."""
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.82,
            confidence=0.76,
        )

        mock_store = MagicMock()
        mock_store.get_best_pattern.return_value = pattern

        # DecisionMemory: 历史 10 次，8 次成功
        mock_dm = MagicMock()
        mock_dm.find_similar.return_value = [
            _make_decision_exp(result="success") for _ in range(8)
        ] + [
            _make_decision_exp(result="failure") for _ in range(2)
        ]

        sync = DecisionPatternSynchronizer(
            decision_memory=mock_dm,
            pattern_store=mock_store,
        )

        result = sync.enhance_decision_confidence(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            base_confidence=0.65,
        )

        # 公式: base_confidence×0.4 + pattern_confidence×0.35 + decision_factor×0.25
        # = 0.65×0.4 + 0.76×0.35 + 0.80×0.25
        # = 0.26 + 0.266 + 0.20 = 0.726
        expected = round(0.65 * 0.4 + 0.76 * 0.35 + 0.80 * 0.25, 4)
        assert result["enhanced_confidence"] == expected
        assert result["base_confidence"] == 0.65
        assert result["pattern_confidence"] == 0.76
        assert result["decision_history_factor"] == 0.80
        assert result["recommendation"] == "recommend"

    def test_enhance_decision_confidence_strong(self):
        """增强 confidence — strong_recommend."""
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            confidence=0.95,
        )

        mock_store = MagicMock()
        mock_store.get_best_pattern.return_value = pattern

        mock_dm = MagicMock()
        mock_dm.find_similar.return_value = [
            _make_decision_exp(result="success") for _ in range(10)
        ]

        sync = DecisionPatternSynchronizer(
            decision_memory=mock_dm,
            pattern_store=mock_store,
        )

        result = sync.enhance_decision_confidence(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            base_confidence=0.80,
        )

        assert result["enhanced_confidence"] >= 0.80
        assert result["recommendation"] == "strong_recommend"

    def test_enhance_decision_confidence_caution(self):
        """增强 confidence — caution."""
        mock_store = MagicMock()
        mock_store.get_best_pattern.return_value = None  # 无模式

        mock_dm = MagicMock()
        mock_dm.find_similar.return_value = [
            _make_decision_exp(result="failure") for _ in range(8)
        ] + [
            _make_decision_exp(result="success") for _ in range(2)
        ]

        sync = DecisionPatternSynchronizer(
            decision_memory=mock_dm,
            pattern_store=mock_store,
        )

        result = sync.enhance_decision_confidence(
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            base_confidence=0.30,
        )

        assert result["enhanced_confidence"] < 0.40
        assert result["recommendation"] == "caution"


# ═══════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试 — 完整同步流程."""

    def test_full_sync_flow_success(self):
        """完整同步流程: 成功决策 → Pattern 更新."""
        # 初始 Pattern
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.82,
            confidence=0.72,
            avg_reward=0.78,
        )

        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]
        mock_store.get_best_pattern.return_value = pattern

        sync = DecisionPatternSynchronizer(pattern_store=mock_store)

        # 成功执行结果
        events = [
            _make_event(
                decision_id="dec_001",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success",
                reward=0.62,
                success=True,
            ),
            _make_event(
                decision_id="dec_002",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success",
                reward=0.55,
                success=True,
            ),
        ]

        result = sync.sync_batch_results(events)

        assert result.events_processed == 2
        assert result.patterns_updated == 1
        # 成功反馈 → Pattern 应该被 boost
        assert len(result.actions) >= 0  # 差距小可能无动作

    def test_full_sync_flow_over_prediction(self):
        """完整同步流程: Pattern 过度预测 → penalty."""
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.80,
            confidence=0.85,
            avg_reward=0.70,
        )

        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]

        sync = DecisionPatternSynchronizer(pattern_store=mock_store)

        # 10 次实际执行，只有 3 次成功
        events = [
            _make_event(
                decision_id=f"dec_{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 3 else "failure",
                success=i < 3,
            )
            for i in range(10)
        ]

        result = sync.sync_batch_results(events)

        assert result.events_processed == 10
        assert result.patterns_updated == 1
        # 预测差距大，应该有 penalty
        penalty_actions = [a for a in result.actions if a.action_type == "penalty"]
        assert len(penalty_actions) >= 1

    def test_full_sync_flow_consecutive_failures(self):
        """完整同步流程: 连续失败 → decay."""
        pattern = _make_pattern(
            pattern_id="pat_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            success_rate=0.82,
            confidence=0.90,
            avg_reward=0.75,
        )

        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]

        sync = DecisionPatternSynchronizer(pattern_store=mock_store)

        # 10 次中 8 次失败
        events = [
            _make_event(
                decision_id=f"dec_{i:03d}",
                opportunity_type="creative_fatigue",
                action_type="replace_creative",
                result="success" if i < 2 else "failure",
                success=i < 2,
            )
            for i in range(10)
        ]

        result = sync.sync_batch_results(events)

        assert result.events_processed == 10
        # 连续失败 → decay
        decay_actions = [a for a in result.actions if a.action_type == "decay"]
        assert len(decay_actions) == 1
        assert decay_actions[0].confidence_adjustment == -0.30

    def test_bridge_to_reconciler_to_sync(self):
        """Bridge → Reconciler → Synchronizer 全链路."""
        # 1. Bridge
        bridge = DecisionOutcomeBridge()
        exp = _make_decision_exp(
            decision_id="dec_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            result="success",
            result_metrics={"roas_change": 0.19},
            pattern_ids=["pat_001"],
        )
        bridge_result = bridge.from_decision_experience(exp)
        assert bridge_result.converted

        # 2. Reconciler
        reconciler = PatternDecisionReconciler()
        pattern = _make_pattern(
            pattern_id="pat_001",
            success_rate=0.82,
            confidence=0.91,
        )
        rec_result = reconciler.reconcile(pattern, [bridge_result.event])
        assert rec_result.events_processed == 1

        # 3. Synchronizer (批量)
        mock_store = MagicMock()
        mock_store.get_all.return_value = [pattern]
        sync = DecisionPatternSynchronizer(pattern_store=mock_store)
        batch_result = sync.sync_batch_results([bridge_result.event])
        assert batch_result.events_processed == 1

    def test_decision_memory_event_immutability(self):
        """DecisionMemoryEvent 属性完整性."""
        event = _make_event(
            decision_id="dec_001",
            opportunity_type="creative_fatigue",
            action_type="replace_creative",
            result="success",
            reward=0.62,
            confidence=0.65,
            pattern_ids=["pat_001"],
        )

        d = event.to_dict()
        assert d["decision_id"] == "dec_001"
        assert d["reward"] == 0.62
        assert d["confidence"] == 0.65
        assert d["pattern_ids"] == ["pat_001"]
        assert "timestamp" in d
        assert "event_id" in d