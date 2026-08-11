"""E13.7.6 Decision Impact Tracker — 专项测试.

测试覆盖:
  1. Basic capture:       基线捕获 / 增强捕获 / 结果记录
  2. Snapshot queries:    增强快照 / 基线快照 / 完成快照 / 历史
  3. Stats:               get_stats / 空统计 / 混合统计
  4. Dimensions:          action_type / strategy / opportunity
  5. Model validation:    DecisionQualitySnapshot / 属性
  6. Edge cases:          空追踪器 / 最大历史 / 不存在ID / 重复记录
  7. Integration:         完整流程 / 多决策 / 混合模式
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.intelligence.learning.evaluation import (
    DecisionImpactTracker,
    DecisionQualitySnapshot,
)


class TestBasicCapture:
    """1. 基础捕获."""

    def test_capture_baseline(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(
            decision_id="d_001",
            decision_type="EXECUTE",
            strategy_name="scale_winning",
            action_type="increase_budget",
            baseline_score=0.65,
            baseline_confidence=0.72,
        )
        assert snapshot.decision_id == "d_001"
        assert snapshot.decision_type == "EXECUTE"
        assert snapshot.baseline_score == 0.65
        assert snapshot.baseline_confidence == 0.72
        assert snapshot.learning_enhanced is False
        assert snapshot.enhanced_score == 0.65  # 默认与基线相同
        assert snapshot.actual_outcome == "pending"
        assert tracker.total_snapshots == 1

    def test_capture_baseline_defaults(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline()
        assert snapshot.decision_id == ""
        assert snapshot.baseline_score == 0.0
        assert snapshot.baseline_confidence == 0.0
        assert snapshot.learning_enhanced is False

    def test_capture_enhanced(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(
            decision_id="d_001",
            baseline_score=0.65,
            baseline_confidence=0.72,
        )
        updated = tracker.capture_enhanced(
            snapshot=snapshot,
            enhanced_score=0.78,
            enhanced_confidence=0.85,
            enhancer_recommendation="approve",
            enhancer_confidence=0.79,
        )
        assert updated.learning_enhanced is True
        assert updated.enhanced_score == 0.78
        assert updated.enhanced_confidence == 0.85
        assert updated.enhancer_recommendation == "approve"
        assert updated.enhancer_confidence == 0.79
        assert updated.score_adjustment == pytest.approx(0.13)

    def test_capture_enhanced_negative_adjustment(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(baseline_score=0.80)
        updated = tracker.capture_enhanced(
            snapshot=snapshot,
            enhanced_score=0.70,
            enhancer_recommendation="reject",
        )
        assert updated.score_adjustment == pytest.approx(-0.10)

    def test_record_outcome_success(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(decision_id="d_001")
        result = tracker.record_outcome(
            snapshot_id=snapshot.snapshot_id,
            success=True,
            reward=0.72,
        )
        assert result is not None
        assert result.actual_outcome == "success"
        assert result.actual_reward == 0.72
        assert result.has_outcome is True
        assert result.is_success is True

    def test_record_outcome_failure(self):
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(decision_id="d_001")
        result = tracker.record_outcome(
            snapshot_id=snapshot.snapshot_id,
            success=False,
            reward=0.0,
        )
        assert result.actual_outcome == "failure"
        assert result.is_success is False

    def test_record_outcome_not_found(self):
        tracker = DecisionImpactTracker()
        result = tracker.record_outcome(snapshot_id="nonexistent")
        assert result is None


class TestSnapshotQueries:
    """2. 快照查询."""

    def test_get_enhanced_snapshots(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(decision_id="d_001")
        s2 = tracker.capture_baseline(decision_id="d_002")
        tracker.capture_enhanced(s1, enhanced_score=0.78)
        enhanced = tracker.get_enhanced_snapshots()
        assert len(enhanced) == 1
        assert enhanced[0].decision_id == "d_001"

    def test_get_baseline_only_snapshots(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(decision_id="d_001")
        s2 = tracker.capture_baseline(decision_id="d_002")
        tracker.capture_enhanced(s1, enhanced_score=0.78)
        baseline_only = tracker.get_baseline_only_snapshots()
        assert len(baseline_only) == 1
        assert baseline_only[0].decision_id == "d_002"

    def test_get_completed_snapshots(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(decision_id="d_001")
        s2 = tracker.capture_baseline(decision_id="d_002")
        tracker.record_outcome(s1.snapshot_id, success=True)
        completed = tracker.get_completed_snapshots()
        assert len(completed) == 1
        assert completed[0].decision_id == "d_001"

    def test_get_history_preserves_order(self):
        tracker = DecisionImpactTracker()
        tracker.capture_baseline(decision_id="d_001")
        tracker.capture_baseline(decision_id="d_002")
        tracker.capture_baseline(decision_id="d_003")
        history = tracker.get_history()
        assert len(history) == 3
        assert history[0].decision_id == "d_001"
        assert history[2].decision_id == "d_003"

    def test_get_snapshot_by_id(self):
        tracker = DecisionImpactTracker()
        s = tracker.capture_baseline(decision_id="d_001")
        found = tracker.get_snapshot(s.snapshot_id)
        assert found is not None
        assert found.decision_id == "d_001"

    def test_get_snapshot_not_found(self):
        tracker = DecisionImpactTracker()
        assert tracker.get_snapshot("nonexistent") is None

    def test_completed_snapshots_count(self):
        tracker = DecisionImpactTracker()
        assert tracker.completed_snapshots == 0
        s1 = tracker.capture_baseline()
        s2 = tracker.capture_baseline()
        tracker.record_outcome(s1.snapshot_id, success=True)
        tracker.record_outcome(s2.snapshot_id, success=False)
        assert tracker.completed_snapshots == 2


class TestStats:
    """3. 统计."""

    def test_get_stats_basic(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(
            baseline_score=0.60, baseline_confidence=0.70
        )
        s2 = tracker.capture_baseline(
            baseline_score=0.70, baseline_confidence=0.80
        )
        tracker.capture_enhanced(s1, enhanced_score=0.75, enhanced_confidence=0.85)
        tracker.record_outcome(s1.snapshot_id, success=True)
        tracker.record_outcome(s2.snapshot_id, success=False)

        stats = tracker.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["completed_snapshots"] == 2
        assert stats["learning_enhanced_count"] == 1
        assert stats["baseline_only_count"] == 1
        assert stats["baseline_stats"]["avg_score"] == pytest.approx(0.65)
        assert stats["enhanced_stats"]["avg_score"] == 0.75
        assert stats["enhanced_stats"]["sample_count"] == 1

    def test_get_stats_empty(self):
        tracker = DecisionImpactTracker()
        stats = tracker.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["baseline_stats"]["success_rate"] == 0.0

    def test_get_stats_all_enhanced(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(baseline_score=0.60)
        s2 = tracker.capture_baseline(baseline_score=0.70)
        tracker.capture_enhanced(s1, enhanced_score=0.75)
        tracker.capture_enhanced(s2, enhanced_score=0.85)
        tracker.record_outcome(s1.snapshot_id, success=True)
        tracker.record_outcome(s2.snapshot_id, success=True)

        stats = tracker.get_stats()
        assert stats["learning_enhanced_count"] == 2
        assert stats["enhanced_stats"]["success_rate"] == 1.0
        assert stats["enhanced_stats"]["avg_score_adjustment"] == pytest.approx(0.15)

    def test_get_stats_no_enhanced(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(baseline_score=0.60)
        tracker.record_outcome(s1.snapshot_id, success=True)
        stats = tracker.get_stats()
        assert stats["learning_enhanced_count"] == 0
        assert stats["enhanced_stats"]["success_rate"] == 0.0


class TestDimensions:
    """4. 维度分组."""

    def test_get_stats_by_action_type(self):
        tracker = DecisionImpactTracker()
        s1 = tracker.capture_baseline(
            action_type="increase_budget", baseline_score=0.60
        )
        s2 = tracker.capture_baseline(
            action_type="refresh_creative", baseline_score=0.70
        )
        tracker.capture_enhanced(s1, enhanced_score=0.75)
        tracker.capture_enhanced(s2, enhanced_score=0.85)

        stats = tracker.get_stats_by_dimension("action_type")
        assert "increase_budget" in stats
        assert "refresh_creative" in stats
        assert stats["increase_budget"]["total"] == 1
        assert stats["increase_budget"]["enhanced_count"] == 1
        assert stats["increase_budget"]["avg_enhanced_score"] == 0.75

    def test_get_stats_by_strategy_name(self):
        tracker = DecisionImpactTracker()
        tracker.capture_baseline(strategy_name="scale_winning", baseline_score=0.60)
        tracker.capture_baseline(strategy_name="test_new", baseline_score=0.70)

        stats = tracker.get_stats_by_dimension("strategy_name")
        assert "scale_winning" in stats
        assert "test_new" in stats

    def test_get_stats_by_opportunity_type(self):
        tracker = DecisionImpactTracker()
        tracker.capture_baseline(opportunity_type="budget_optimization", baseline_score=0.60)
        tracker.capture_baseline(opportunity_type="creative_rotation", baseline_score=0.70)

        stats = tracker.get_stats_by_dimension("opportunity_type")
        assert "budget_optimization" in stats
        assert "creative_rotation" in stats

    def test_get_stats_by_dimension_empty(self):
        tracker = DecisionImpactTracker()
        stats = tracker.get_stats_by_dimension("action_type")
        assert stats == {}


class TestModelValidation:
    """5. 模型验证."""

    def test_snapshot_defaults(self):
        snapshot = DecisionQualitySnapshot()
        assert snapshot.snapshot_id != ""
        assert snapshot.decision_id == ""
        assert snapshot.learning_enhanced is False
        assert snapshot.has_outcome is False
        assert snapshot.is_success is False
        assert snapshot.learning_impact == 0.0

    def test_snapshot_learning_impact(self):
        snapshot = DecisionQualitySnapshot(
            baseline_score=0.60,
            enhanced_score=0.75,
            learning_enhanced=True,
        )
        assert snapshot.learning_impact == pytest.approx(0.15)

    def test_snapshot_learning_impact_not_enhanced(self):
        snapshot = DecisionQualitySnapshot(
            baseline_score=0.60,
            enhanced_score=0.75,
            learning_enhanced=False,
        )
        assert snapshot.learning_impact == 0.0

    def test_snapshot_to_dict(self):
        snapshot = DecisionQualitySnapshot(
            decision_id="d_001",
            decision_type="EXECUTE",
            baseline_score=0.65,
        )
        d = snapshot.to_dict()
        assert d["decision_id"] == "d_001"
        assert d["baseline_score"] == 0.65
        assert "snapshot_id" in d

    def test_snapshot_is_success(self):
        snapshot = DecisionQualitySnapshot(actual_outcome="success")
        assert snapshot.is_success is True
        assert snapshot.has_outcome is True
        snapshot2 = DecisionQualitySnapshot(actual_outcome="failure")
        assert snapshot2.is_success is False


class TestEdgeCases:
    """6. 边界情况."""

    def test_empty_tracker(self):
        tracker = DecisionImpactTracker()
        assert tracker.total_snapshots == 0
        assert tracker.completed_snapshots == 0
        assert tracker.get_history() == []
        assert tracker.get_enhanced_snapshots() == []
        assert tracker.get_baseline_only_snapshots() == []
        assert tracker.get_completed_snapshots() == []

    def test_max_history_trim(self):
        tracker = DecisionImpactTracker(max_history=5)
        for i in range(10):
            tracker.capture_baseline(decision_id=f"d_{i:03d}")
        assert tracker.total_snapshots == 5
        history = tracker.get_history()
        assert history[0].decision_id == "d_005"  # 最旧5条被删除

    def test_clear_tracker(self):
        tracker = DecisionImpactTracker()
        for i in range(5):
            tracker.capture_baseline(decision_id=f"d_{i}")
        assert tracker.total_snapshots == 5
        tracker.clear()
        assert tracker.total_snapshots == 0
        assert tracker.get_history() == []

    def test_duplicate_record_outcome(self):
        tracker = DecisionImpactTracker()
        s = tracker.capture_baseline(decision_id="d_001")
        tracker.record_outcome(s.snapshot_id, success=True, reward=0.5)
        # 第二次记录应该覆盖
        result = tracker.record_outcome(s.snapshot_id, success=False, reward=0.1)
        assert result.actual_outcome == "failure"
        assert result.actual_reward == 0.1

    def test_zero_baseline_score(self):
        # 零分基线不应导致错误
        tracker = DecisionImpactTracker()
        snapshot = tracker.capture_baseline(baseline_score=0.0)
        tracker.capture_enhanced(snapshot, enhanced_score=0.5)
        assert snapshot.score_adjustment == 0.5

    def test_all_enhanced_equal_scores(self):
        tracker = DecisionImpactTracker()
        for i in range(5):
            s = tracker.capture_baseline(baseline_score=0.80)
            tracker.capture_enhanced(s, enhanced_score=0.80)
            tracker.record_outcome(s.snapshot_id, success=True)
        stats = tracker.get_stats()
        assert stats["learning_enhanced_count"] == 5
        assert stats["enhanced_stats"]["avg_score_adjustment"] == 0.0


class TestIntegration:
    """7. 集成测试."""

    def test_full_workflow(self):
        tracker = DecisionImpactTracker()

        # 决策1: 增强 + 成功
        s1 = tracker.capture_baseline(
            decision_id="d_001",
            decision_type="EXECUTE",
            baseline_score=0.65,
            baseline_confidence=0.72,
        )
        tracker.capture_enhanced(
            s1,
            enhanced_score=0.78,
            enhanced_confidence=0.85,
            enhancer_recommendation="approve",
            enhancer_confidence=0.79,
        )
        tracker.record_outcome(s1.snapshot_id, success=True, reward=0.72)

        # 决策2: 无增强 + 失败
        s2 = tracker.capture_baseline(
            decision_id="d_002",
            decision_type="TEST",
            baseline_score=0.40,
            baseline_confidence=0.50,
        )
        tracker.record_outcome(s2.snapshot_id, success=False, reward=0.0)

        stats = tracker.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["baseline_stats"]["success_rate"] == 0.0  # 只有s2是无增强且有结果的
        assert stats["enhanced_stats"]["success_rate"] == 1.0  # s1是增强且有结果的

    def test_multiple_decisions_mixed(self):
        tracker = DecisionImpactTracker()
        for i in range(10):
            s = tracker.capture_baseline(
                decision_id=f"d_{i:03d}",
                baseline_score=0.5 + i * 0.02,
            )
            if i % 2 == 0:
                tracker.capture_enhanced(
                    s,
                    enhanced_score=0.5 + i * 0.02 + 0.1,
                )
            tracker.record_outcome(
                s.snapshot_id,
                success=(i % 3 != 0),
            )

        assert tracker.total_snapshots == 10
        assert tracker.completed_snapshots == 10
        enhanced = tracker.get_enhanced_snapshots()
        assert len(enhanced) == 5  # i=0,2,4,6,8

    def test_metadata_preservation(self):
        tracker = DecisionImpactTracker()
        s = tracker.capture_baseline(
            decision_id="d_001",
            metadata={"campaign_id": "c_123", "platform": "facebook"},
        )
        assert s.metadata["campaign_id"] == "c_123"
        assert s.metadata["platform"] == "facebook"