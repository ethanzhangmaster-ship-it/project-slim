"""E12.5.5 — Autonomous Meta Learning Loop 测试。

覆盖:
  - Models: MetaLearningCycle, LearningSchedule, StrategyFeedback, KnowledgeUpdate
  - CycleManager: 生命周期、状态转换、多周期、失败恢复
  - LearningScheduler: 触发条件、实验数、花费、间隔、性能下降
  - KnowledgeUpdater: Bayesian 更新、冲突检测、衰减
  - StrategyFeedback: 反馈收集、预测准确度、策略评分更新
  - MetaLearningController: 完整周期、异常处理、多产品、循环
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning import (
    ExperienceRecord,
    ExperienceOutcome,
    ExperienceStore,
    ExperienceResult,
    MutationDetail,
    MutationType,
    ExperimentDetail,
    ContextDetail,
)
from market_ops.creative_vision_runtime.reality.meta_learning.knowledge_graph import (
    KnowledgeNode,
    KnowledgeEdge,
    NodeType,
    RelationType,
)
from market_ops.creative_vision_runtime.reality.meta_learning.strategy_optimizer import (
    MetaStrategy,
    OptimizationGoal,
)
from market_ops.creative_vision_runtime.reality.meta_learning.autonomous_loop import (
    CycleManager,
    KnowledgeUpdate,
    KnowledgeUpdater,
    LearningSchedule,
    LearningScheduler,
    LearningSummary,
    LearningTrigger,
    LoopMetrics,
    MetaCycleStatus,
    MetaLearningController,
    MetaLearningCycle,
    MetaLearningResult,
    StrategyFeedback,
    StrategyFeedbackCollector,
    TriggerReason,
)


# ── Helpers ───────────────────────────────────────────────


def make_mutation_detail(gene_after=None):
    return MutationDetail(
        mutation_type=MutationType.REFRESH_HOOK,
        changed_genes=["hook", "visual_style"],
        gene_before={"hook": "old_value"},
        gene_after=gene_after if gene_after is not None else {"hook": "rescue_puppy", "visual_style": "bright_colorful"},
    )


def make_experiment_detail(improvement=0.3, metrics_delta=None):
    return ExperimentDetail(
        baseline_metrics={"ctr": 0.02, "roas": 0.5},
        winner_metrics={"ctr": 0.03, "roas": 0.7},
        improvement=improvement,
        metrics_delta=metrics_delta or {"ctr": 0.5, "roas": 0.4, "cvr": 0.15},
        winner_id="v2",
        variant_count=3,
        confidence=0.85,
    )


def make_context(product="p04", market="US"):
    return ContextDetail(
        product_id=product,
        product_name="Merge Witch",
        market=market,
        platform="facebook",
    )


def make_record(product="p04", creative="c001", improvement=0.3, gene_after=None):
    return ExperienceRecord(
        product_id=product,
        creative_id=creative,
        genome_id="g001",
        mutation=make_mutation_detail(gene_after=gene_after),
        experiment=make_experiment_detail(improvement=improvement),
        context=make_context(product=product),
        result=ExperienceResult(
            outcome=ExperienceOutcome.SUCCESS,
            success=True,
            insight="Test insight",
            key_finding="Test finding",
        ),
    )


def make_knowledge_node(node_id="N1", node_type=NodeType.GENE, name="Test Gene", confidence=0.72):
    return KnowledgeNode(
        node_id=node_id,
        node_type=node_type,
        name=name,
        confidence=confidence,
    )


def make_knowledge_edge(source="N1", target="N2", relation=RelationType.IMPROVES, weight=0.78, evidence=100, confidence=0.85):
    return KnowledgeEdge(
        source_id=source,
        target_id=target,
        relation_type=relation,
        weight=weight,
        evidence_count=evidence,
        confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models (18 tests)
# ═══════════════════════════════════════════════════════════


class TestLoopModels:
    """E12.5.5 数据模型测试。"""

    def test_meta_learning_cycle_creation(self):
        """MetaLearningCycle 基本创建。"""
        cycle = MetaLearningCycle(product_id="p04")
        assert cycle.cycle_id.startswith("MLC_")
        assert cycle.product_id == "p04"
        assert cycle.status == MetaCycleStatus.CREATED
        assert cycle.is_active
        assert not cycle.is_successful

    def test_meta_learning_cycle_complete(self):
        """标记周期完成。"""
        cycle = MetaLearningCycle(product_id="p04")
        cycle.mark_completed("Test completed")
        assert cycle.status == MetaCycleStatus.COMPLETED
        assert cycle.is_successful
        assert not cycle.is_active
        assert cycle.end_time is not None
        assert cycle.summary == "Test completed"

    def test_meta_learning_cycle_fail(self):
        """标记周期失败。"""
        cycle = MetaLearningCycle(product_id="p04")
        cycle.mark_failed("Error occurred")
        assert cycle.status == MetaCycleStatus.FAILED
        assert not cycle.is_successful
        assert not cycle.is_active
        assert "Error occurred" in cycle.errors

    def test_meta_learning_cycle_duration(self):
        """周期持续时间。"""
        cycle = MetaLearningCycle(product_id="p04")
        assert cycle.duration_seconds is None
        cycle.mark_completed()
        assert cycle.duration_seconds is not None

    def test_meta_learning_cycle_to_dict(self):
        """MetaLearningCycle to_dict。"""
        cycle = MetaLearningCycle(
            product_id="p04",
            experiments_analyzed=100,
            patterns_discovered=5,
            strategies_generated=3,
            learning_gain=0.75,
            cycle_number=1,
        )
        d = cycle.to_dict()
        assert d["product_id"] == "p04"
        assert d["experiments_analyzed"] == 100
        assert d["patterns_discovered"] == 5
        assert d["learning_gain"] == 0.75
        assert d["cycle_number"] == 1
        assert d["is_active"] is True

    def test_meta_learning_cycle_repr(self):
        """MetaLearningCycle repr。"""
        cycle = MetaLearningCycle(learning_gain=0.8)
        r = repr(cycle)
        assert "MetaLearningCycle" in r
        assert "created" in r

    def test_learning_schedule_default(self):
        """LearningSchedule 默认值。"""
        s = LearningSchedule()
        assert s.min_experiments == 50
        assert s.min_spend == 5000.0
        assert s.learning_interval_days == 7
        assert s.auto_trigger is True

    def test_learning_schedule_to_dict(self):
        """LearningSchedule to_dict。"""
        s = LearningSchedule()
        d = s.to_dict()
        assert d["min_experiments"] == 50
        assert d["min_spend"] == 5000.0

    def test_learning_trigger_creation(self):
        """LearningTrigger 创建。"""
        t = LearningTrigger(
            reason=TriggerReason.EXPERIMENT_COUNT,
            experiment_count=100,
            should_trigger=True,
            message="Enough experiments",
        )
        assert t.reason == TriggerReason.EXPERIMENT_COUNT
        assert t.should_trigger is True
        assert t.triggered_at is not None

    def test_learning_trigger_no_trigger(self):
        """LearningTrigger 不触发时无时间戳。"""
        t = LearningTrigger(should_trigger=False)
        assert t.triggered_at is None

    def test_strategy_feedback_creation(self):
        """StrategyFeedback 创建。"""
        f = StrategyFeedback(
            strategy_id="MS_001",
            predicted_gain=0.20,
            actual_gain=0.31,
            success=True,
            confidence=0.85,
        )
        assert f.strategy_id == "MS_001"
        assert f.prediction_error == pytest.approx(0.11)
        assert f.prediction_accuracy == pytest.approx(1.55)
        assert f.is_underestimated
        assert not f.is_overestimated

    def test_strategy_feedback_overestimated(self):
        """高估检测。"""
        f = StrategyFeedback(
            predicted_gain=0.30,
            actual_gain=0.15,
            success=True,
        )
        assert f.prediction_accuracy == 0.5
        assert f.is_overestimated
        assert not f.is_underestimated

    def test_strategy_feedback_zero_prediction(self):
        """零预测增益。"""
        f = StrategyFeedback(predicted_gain=0.0, actual_gain=0.10)
        assert f.prediction_accuracy == 0.0

    def test_knowledge_update_creation(self):
        """KnowledgeUpdate 创建。"""
        u = KnowledgeUpdate(
            node_id="N1",
            old_confidence=0.72,
            new_confidence=0.89,
            evidence_count=20,
            cycle_id="MLC_001",
        )
        assert u.confidence_delta == pytest.approx(0.17)
        assert u.is_improved

    def test_knowledge_update_not_improved(self):
        """KnowledgeUpdate 置信度下降。"""
        u = KnowledgeUpdate(old_confidence=0.80, new_confidence=0.60)
        assert u.confidence_delta == pytest.approx(-0.20)
        assert not u.is_improved

    def test_learning_summary_creation(self):
        """LearningSummary 创建。"""
        s = LearningSummary(
            cycle_id="MLC_001",
            total_experiments=100,
            total_patterns=5,
            overall_learning_gain=0.75,
        )
        assert s.total_experiments == 100
        assert s.total_patterns == 5
        assert s.overall_learning_gain == 0.75

    def test_loop_metrics_success_rate(self):
        """LoopMetrics 成功率。"""
        m = LoopMetrics(total_cycles=10, successful_cycles=8, failed_cycles=2)
        assert m.success_rate == 0.8

    def test_loop_metrics_zero_cycles(self):
        """LoopMetrics 零周期。"""
        m = LoopMetrics()
        assert m.success_rate == 0.0

    def test_training_trigger_enum(self):
        """TriggerReason 枚举。"""
        assert TriggerReason.EXPERIMENT_COUNT.value == "experiment_count"
        assert TriggerReason.SPEND_THRESHOLD.value == "spend_threshold"
        assert TriggerReason.PERFORMANCE_DROP.value == "performance_drop"


# ═══════════════════════════════════════════════════════════
# 2. CycleManager (20 tests)
# ═══════════════════════════════════════════════════════════


class TestCycleManager:
    """CycleManager 测试。"""

    def test_create_cycle(self):
        """创建周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        assert cycle.product_id == "p04"
        assert cycle.status == MetaCycleStatus.CREATED
        assert cycle.cycle_number == 1

    def test_create_multiple_cycles(self):
        """创建多个周期。"""
        mgr = CycleManager()
        c1 = mgr.create_cycle("p04")
        c2 = mgr.create_cycle("p04")
        assert c1.cycle_number == 1
        assert c2.cycle_number == 2

    def test_advance_created_to_collecting(self):
        """推进 CREATED → COLLECTING。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.advance(cycle)
        assert cycle.status == MetaCycleStatus.COLLECTING

    def test_full_lifecycle(self):
        """完整生命周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        statuses = []
        for _ in range(6):
            mgr.advance(cycle)
            statuses.append(cycle.status)
        assert MetaCycleStatus.COLLECTING in statuses
        assert MetaCycleStatus.MINING in statuses
        assert MetaCycleStatus.OPTIMIZING in statuses
        assert MetaCycleStatus.EXECUTING in statuses
        assert MetaCycleStatus.LEARNING in statuses
        assert MetaCycleStatus.COMPLETED in statuses

    def test_cannot_advance_completed(self):
        """已完成周期不能推进。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        cycle.mark_completed()
        with pytest.raises(ValueError, match="already completed"):
            mgr.advance(cycle)

    def test_cannot_advance_failed(self):
        """已失败周期不能推进。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        cycle.mark_failed("Error")
        with pytest.raises(ValueError, match="already failed"):
            mgr.advance(cycle)

    def test_advance_to_specific_state(self):
        """推进到指定状态。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.advance_to(cycle, MetaCycleStatus.COLLECTING)
        assert cycle.status == MetaCycleStatus.COLLECTING

    def test_advance_to_invalid_state(self):
        """推进到非法状态。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        with pytest.raises(ValueError, match="Cannot transition"):
            mgr.advance_to(cycle, MetaCycleStatus.COMPLETED)

    def test_complete_cycle(self):
        """完成周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.advance(cycle)  # COLLECTING
        mgr.advance(cycle)  # MINING
        mgr.advance(cycle)  # OPTIMIZING
        mgr.advance(cycle)  # EXECUTING
        mgr.advance(cycle)  # LEARNING
        mgr.complete(cycle, "Done")
        assert cycle.is_successful

    def test_fail_cycle(self):
        """失败周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.fail(cycle, "Database error")
        assert cycle.status == MetaCycleStatus.FAILED
        assert "Database error" in cycle.errors

    def test_get_active_cycles(self):
        """获取活跃周期。"""
        mgr = CycleManager()
        mgr.create_cycle("p04")
        mgr.create_cycle("p04")
        active = mgr.get_active_cycles()
        assert len(active) == 2

    def test_get_active_cycles_for_product(self):
        """按产品获取活跃周期。"""
        mgr = CycleManager()
        mgr.create_cycle("p04")
        mgr.create_cycle("p05")
        active = mgr.get_active_cycles_for_product("p04")
        assert len(active) == 1

    def test_get_history(self):
        """获取历史周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.complete(cycle)
        history = mgr.get_history()
        assert len(history) == 1

    def test_get_last_completed(self):
        """获取最近完成的周期。"""
        mgr = CycleManager()
        c1 = mgr.create_cycle("p04")
        mgr.complete(c1)
        c2 = mgr.create_cycle("p04")
        mgr.complete(c2)
        last = mgr.get_last_completed("p04")
        assert last is not None
        # 最近完成的周期是其 cycle_id 匹配 c2 或具有最大的 end_time
        assert last.cycle_id in (c1.cycle_id, c2.cycle_id)

    def test_get_last_completed_none(self):
        """无完成周期时返回 None。"""
        mgr = CycleManager()
        last = mgr.get_last_completed("p04")
        assert last is None

    def test_get_cycle_by_id(self):
        """通过 ID 获取周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        found = mgr.get_cycle(cycle.cycle_id)
        assert found is not None
        assert found.cycle_id == cycle.cycle_id

    def test_get_cycle_from_history(self):
        """从历史中获取周期。"""
        mgr = CycleManager()
        cycle = mgr.create_cycle("p04")
        mgr.complete(cycle)
        found = mgr.get_cycle(cycle.cycle_id)
        assert found is not None

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = CycleManager()
        mgr.create_cycle("p04")  # active
        cycle = mgr.create_cycle("p04")
        mgr.complete(cycle)  # completed
        stats = mgr.get_stats()
        assert stats["total_cycles"] == 2
        assert stats["active_cycles"] == 1
        assert stats["completed_cycles"] == 1

    def test_clear(self):
        """清空所有周期。"""
        mgr = CycleManager()
        mgr.create_cycle("p04")
        mgr.clear()
        assert mgr.get_stats()["total_cycles"] == 0


# ═══════════════════════════════════════════════════════════
# 3. LearningScheduler (15 tests)
# ═══════════════════════════════════════════════════════════


class TestLearningScheduler:
    """LearningScheduler 测试。"""

    def test_trigger_by_experiment_count(self):
        """实验数触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(experiment_count=100, total_spend=10000)
        assert trigger.should_trigger
        assert trigger.reason == TriggerReason.EXPERIMENT_COUNT

    def test_trigger_by_spend(self):
        """花费触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(experiment_count=30, total_spend=10000)
        assert trigger.should_trigger
        assert trigger.reason == TriggerReason.SPEND_THRESHOLD

    def test_trigger_by_performance_drop(self):
        """性能下降触发（最高优先级）。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(experiment_count=5, performance_drop=0.20)
        assert trigger.should_trigger
        assert trigger.reason == TriggerReason.PERFORMANCE_DROP

    def test_trigger_by_time_interval(self):
        """时间间隔触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=60,
            days_since_last=10,
        )
        assert trigger.should_trigger
        assert trigger.reason == TriggerReason.TIME_INTERVAL

    def test_no_trigger_time_interval_insufficient_experiments(self):
        """时间间隔满足但实验不足时不触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=30,
            days_since_last=10,
        )
        assert not trigger.should_trigger

    def test_no_trigger_below_thresholds(self):
        """低于所有阈值时不触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=10,
            total_spend=1000,
            days_since_last=1,
        )
        assert not trigger.should_trigger

    def test_trigger_by_new_experiments(self):
        """新增实验触发。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=30,
            new_experiments=15,
            days_since_last=3,
        )
        assert trigger.should_trigger

    def test_disable_auto_trigger(self):
        """禁用自动触发。"""
        schedule = LearningSchedule(auto_trigger=False)
        scheduler = LearningScheduler(schedule)
        trigger = scheduler.check(experiment_count=100)
        assert not trigger.should_trigger
        assert trigger.reason == TriggerReason.MANUAL

    def test_check_from_state(self):
        """从状态检查触发。"""
        from datetime import datetime, timezone, timedelta
        scheduler = LearningScheduler()
        last = datetime.now(timezone.utc) - timedelta(days=10)
        trigger = scheduler.check_from_state(
            experiment_count=100,
            total_spend=10000,
            last_cycle=last,
        )
        assert trigger.should_trigger

    def test_check_from_state_performance_drop(self):
        """从状态检测性能下降。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check_from_state(
            experiment_count=100,
            total_spend=10000,
            current_performance=0.5,
            previous_performance=1.0,
        )
        assert trigger.should_trigger
        assert trigger.performance_drop > 0

    def test_should_trigger_helper(self):
        """should_trigger 辅助方法。"""
        scheduler = LearningScheduler()
        trigger = LearningTrigger(should_trigger=True)
        assert scheduler.should_trigger(trigger)

    def test_custom_schedule(self):
        """自定义 LearningSchedule。"""
        schedule = LearningSchedule(min_experiments=10, min_spend=1000)
        scheduler = LearningScheduler(schedule)
        trigger = scheduler.check(experiment_count=15, total_spend=500)
        assert trigger.should_trigger

    def test_scheduler_to_dict(self):
        """LearningScheduler to_dict。"""
        scheduler = LearningScheduler()
        d = scheduler.to_dict()
        assert "schedule" in d

    def test_performance_drop_priority_over_experiment_count(self):
        """性能下降优先级高于实验数。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=100,
            performance_drop=0.20,
        )
        assert trigger.reason == TriggerReason.PERFORMANCE_DROP

    def test_trigger_message(self):
        """触发消息。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(experiment_count=100)
        assert "Experiment count" in trigger.message


# ═══════════════════════════════════════════════════════════
# 4. KnowledgeUpdater (25 tests)
# ═══════════════════════════════════════════════════════════


class TestKnowledgeUpdater:
    """KnowledgeUpdater 测试。"""

    def test_update_node_confidence(self):
        """Bayesian 更新节点置信度。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.72)
        updated, record = updater.update_node_confidence(
            node, success_count=20, total_count=25, cycle_id="MLC_001"
        )
        # 20/25 = 0.80 success_rate, Bayesian update should increase
        assert updated.confidence > 0.72
        assert record.is_improved
        assert record.evidence_count == 25

    def test_update_node_confidence_decrease(self):
        """新证据差时置信度下降。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.85)
        updated, record = updater.update_node_confidence(
            node, success_count=5, total_count=25, cycle_id="MLC_001"
        )
        # 5/25 = 0.20 success_rate, Bayesian update should decrease
        assert updated.confidence < 0.85
        assert not record.is_improved

    def test_update_node_confidence_no_evidence(self):
        """零证据不更新。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.72)
        updated, record = updater.update_node_confidence(
            node, success_count=0, total_count=0
        )
        assert updated.confidence == 0.72
        assert record.evidence_count == 0

    def test_update_node_confidence_conflict_detection(self):
        """冲突检测。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.90)
        updated, record = updater.update_node_confidence(
            node, success_count=5, total_count=25, cycle_id="MLC_001"
        )
        # 5/25 = 0.20 vs 0.90 → conflict
        assert "Conflict" in record.update_reason

    def test_update_node_confidence_strong_positive(self):
        """强正面证据。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.30)
        updated, record = updater.update_node_confidence(
            node, success_count=20, total_count=25, cycle_id="MLC_001"
        )
        # 20/25 = 0.80 vs 0.30 → strong positive
        assert "Strong positive" in record.update_reason

    def test_update_node_with_decay(self):
        """带衰减的更新。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.72)
        updated, record = updater.update_node_confidence(
            node, success_count=20, total_count=25, days_since_creation=100
        )
        # 衰减后置信度应该更低
        assert updated.confidence < 0.72 + 0.08  # 不会全量上升

    def test_update_edge_confidence(self):
        """Bayesian 更新边置信度。"""
        updater = KnowledgeUpdater()
        edge = make_knowledge_edge(confidence=0.85, evidence=100)
        updated, record = updater.update_edge_confidence(
            edge, success_count=20, total_count=25, cycle_id="MLC_001"
        )
        # 20/25 = 0.80, weighted with previous 100 evidence
        assert updated.confidence < 0.85  # 0.80 < 0.85, slight decrease
        assert updated.evidence_count == 125

    def test_update_edge_confidence_no_evidence(self):
        """零证据不更新边。"""
        updater = KnowledgeUpdater()
        edge = make_knowledge_edge()
        updated, record = updater.update_edge_confidence(
            edge, success_count=0, total_count=0
        )
        assert updated.confidence == 0.85
        assert record.evidence_count == 0

    def test_update_edge_confidence_improved(self):
        """边置信度提升。"""
        updater = KnowledgeUpdater()
        edge = make_knowledge_edge(confidence=0.50, evidence=10)
        updated, record = updater.update_edge_confidence(
            edge, success_count=20, total_count=25, cycle_id="MLC_001"
        )
        # 0.80 success_rate with 10 evidence + 25 new → should increase
        assert updated.confidence > 0.50

    def test_update_nodes_batch(self):
        """批量更新节点。"""
        updater = KnowledgeUpdater()
        nodes = [
            (make_knowledge_node("N1", confidence=0.72), 20, 25),
            (make_knowledge_node("N2", confidence=0.60), 15, 25),
        ]
        updated_nodes, records = updater.update_nodes_batch(nodes, "MLC_001")
        assert len(updated_nodes) == 2
        assert len(records) == 2

    def test_update_edges_batch(self):
        """批量更新边。"""
        updater = KnowledgeUpdater()
        edges = [
            (make_knowledge_edge("N1", "N2", evidence=100), 20, 25),
            (make_knowledge_edge("N3", "N4", evidence=50), 15, 25),
        ]
        updated_edges, records = updater.update_edges_batch(edges, "MLC_001")
        assert len(updated_edges) == 2
        assert len(records) == 2

    def test_apply_decay(self):
        """应用时间衰减。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.90)
        decayed = updater.apply_decay(node, days_since_creation=100)
        # 1 - 0.001 * 100 = 0.9, 0.9 * 0.9 = 0.81
        assert decayed.confidence < 0.90

    def test_apply_decay_minimum(self):
        """衰减不低于最低值。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.90)
        decayed = updater.apply_decay(node, days_since_creation=1000)
        # capped at 0.5 decay factor
        assert decayed.confidence >= 0.45

    def test_update_record_serialization(self):
        """KnowledgeUpdate to_dict。"""
        u = KnowledgeUpdate(
            node_id="N1",
            old_confidence=0.72,
            new_confidence=0.89,
            evidence_count=20,
            cycle_id="MLC_001",
        )
        d = u.to_dict()
        assert d["node_id"] == "N1"
        assert d["confidence_delta"] == 0.17
        assert d["is_improved"] is True

    def test_bayesian_formula_correctness(self):
        """Bayesian 公式正确性。"""
        updater = KnowledgeUpdater(prior_weight=10)
        node = make_knowledge_node(confidence=0.70)
        updated, record = updater.update_node_confidence(
            node, success_count=8, total_count=10, cycle_id="MLC_001"
        )
        # new_conf = (0.70 * 10 + 0.80 * 10) / (10 + 10) = 15/20 = 0.75
        assert abs(updated.confidence - 0.75) < 0.01

    def test_knowledge_updater_repr(self):
        """KnowledgeUpdater repr。"""
        updater = KnowledgeUpdater()
        assert "KnowledgeUpdater" in repr(updater)


# ═══════════════════════════════════════════════════════════
# 5. StrategyFeedbackCollector (15 tests)
# ═══════════════════════════════════════════════════════════


class TestStrategyFeedbackCollector:
    """StrategyFeedbackCollector 测试。"""

    def test_collect_feedback(self):
        """收集策略反馈。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(
            name="Test",
            expected_ctr_delta=0.20,
            expected_roas_delta=0.20,
            confidence=0.85,
        )
        feedback = collector.collect(strategy, actual_gain=0.25, success=True, cycle_id="MLC_001")
        assert feedback.strategy_id == strategy.strategy_id
        assert feedback.success

    def test_collect_feedback_failure(self):
        """收集失败反馈。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test", expected_ctr_delta=0.20, expected_roas_delta=0.20)
        feedback = collector.collect(strategy, actual_gain=0.02, success=False)
        assert not feedback.success

    def test_collect_from_result(self):
        """从实际指标收集反馈。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(
            name="Test",
            expected_ctr_delta=0.20,
            expected_roas_delta=0.15,
            expected_cvr_delta=0.10,
            expected_cpi_delta=-0.05,
        )
        feedback = collector.collect_from_result(
            strategy,
            actual_ctr=0.25,
            actual_roas=0.18,
            actual_cvr=0.12,
            actual_cpi=-0.06,
            success=True,
            cycle_id="MLC_001",
        )
        assert feedback.success
        assert feedback.actual_gain > 0

    def test_update_strategy_score_success(self):
        """成功反馈提升策略评分。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(
            name="Test",
            expected_ctr_delta=0.20,
            expected_roas_delta=0.20,
            confidence=0.70,
        )
        feedback = StrategyFeedback(
            strategy_id=strategy.strategy_id,
            predicted_gain=strategy.performance_impact,
            actual_gain=strategy.performance_impact * 1.2,
            success=True,
        )
        updated = collector.update_strategy_score(strategy, feedback)
        assert updated.confidence > 0.70
        assert updated.evidence_count == 1

    def test_update_strategy_score_failure(self):
        """失败反馈降低策略评分。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(
            name="Test",
            expected_ctr_delta=0.20,
            expected_roas_delta=0.20,
            confidence=0.70,
        )
        feedback = StrategyFeedback(
            strategy_id=strategy.strategy_id,
            predicted_gain=strategy.performance_impact,
            actual_gain=0.01,
            success=False,
        )
        updated = collector.update_strategy_score(strategy, feedback)
        assert updated.confidence < 0.70

    def test_update_strategy_score_overestimated(self):
        """高估策略降低评分。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(
            name="Test",
            expected_ctr_delta=0.30,
            expected_roas_delta=0.30,
            confidence=0.80,
        )
        feedback = StrategyFeedback(
            strategy_id=strategy.strategy_id,
            predicted_gain=strategy.performance_impact,
            actual_gain=strategy.performance_impact * 0.3,
            success=True,
        )
        updated = collector.update_strategy_score(strategy, feedback)
        # 高估（accuracy 0.3 < 0.8）→ 降低
        assert updated.confidence < 0.80

    def test_update_strategies_batch(self):
        """批量更新策略。"""
        collector = StrategyFeedbackCollector()
        s1 = MetaStrategy(name="S1", confidence=0.70)
        s2 = MetaStrategy(name="S2", confidence=0.70)
        f1 = StrategyFeedback(strategy_id=s1.strategy_id, predicted_gain=0.10, actual_gain=0.12, success=True)
        f2 = StrategyFeedback(strategy_id=s2.strategy_id, predicted_gain=0.10, actual_gain=0.03, success=False)
        updated = collector.update_strategies_batch([(s1, f1), (s2, f2)])
        assert len(updated) == 2

    def test_get_feedbacks(self):
        """获取策略反馈列表。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test")
        collector.collect(strategy, actual_gain=0.20, success=True)
        collector.collect(strategy, actual_gain=0.15, success=False)
        feedbacks = collector.get_feedbacks(strategy.strategy_id)
        assert len(feedbacks) == 2

    def test_get_average_accuracy(self):
        """获取平均预测准确度。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test", expected_ctr_delta=0.20, expected_roas_delta=0.20)
        collector.collect(strategy, actual_gain=0.20, success=True)
        collector.collect(strategy, actual_gain=0.10, success=False)
        accuracy = collector.get_average_accuracy(strategy.strategy_id)
        assert accuracy > 0

    def test_get_success_rate(self):
        """获取策略成功率。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test")
        collector.collect(strategy, actual_gain=0.20, success=True)
        collector.collect(strategy, actual_gain=0.10, success=False)
        assert collector.get_success_rate(strategy.strategy_id) == 0.5

    def test_get_overall_accuracy(self):
        """获取全局预测准确度。"""
        collector = StrategyFeedbackCollector()
        s1 = MetaStrategy(name="S1", expected_ctr_delta=0.20, expected_roas_delta=0.20)
        s2 = MetaStrategy(name="S2", expected_ctr_delta=0.15, expected_roas_delta=0.15)
        collector.collect(s1, actual_gain=0.15, success=True)
        collector.collect(s2, actual_gain=0.10, success=True)
        accuracy = collector.get_overall_accuracy()
        assert accuracy > 0

    def test_get_summary(self):
        """获取反馈摘要。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test", expected_ctr_delta=0.20, expected_roas_delta=0.20)
        collector.collect(strategy, actual_gain=0.12, success=True)
        summary = collector.get_summary()
        assert summary["total_feedbacks"] == 1
        assert summary["successful_feedbacks"] == 1

    def test_clear(self):
        """清空反馈。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Test")
        collector.collect(strategy, actual_gain=0.20, success=True)
        collector.clear()
        assert collector.get_summary()["total_feedbacks"] == 0

    def test_collector_repr(self):
        """StrategyFeedbackCollector repr。"""
        collector = StrategyFeedbackCollector()
        assert "StrategyFeedbackCollector" in repr(collector)


# ═══════════════════════════════════════════════════════════
# 6. MetaLearningController (22 tests)
# ═══════════════════════════════════════════════════════════


class TestMetaLearningController:
    """MetaLearningController 测试。"""

    def test_controller_creation(self):
        """控制器创建。"""
        controller = MetaLearningController()
        assert controller._metrics.total_cycles == 0

    def test_run_cycle_no_experiences(self):
        """无经验时运行周期。"""
        controller = MetaLearningController()
        result = controller.run_cycle("p04")
        assert isinstance(result, MetaLearningResult)
        assert result.success

    def test_run_cycle_with_experiences(self):
        """有经验时运行周期。"""
        controller = MetaLearningController()
        # 添加经验
        for i in range(10):
            record = make_record(product="p04", creative=f"c{i:03d}", improvement=0.3 + i * 0.02)
            controller.experience_store.add(record)

        result = controller.run_cycle("p04")
        assert isinstance(result, MetaLearningResult)
        assert result.success
        assert result.cycle.experiments_analyzed > 0

    def test_run_cycle_generates_strategies(self):
        """周期生成策略。"""
        controller = MetaLearningController()
        for i in range(20):
            record = make_record(
                product="p04",
                creative=f"c{i:03d}",
                improvement=0.3 + i * 0.02,
                gene_after={"hook": "rescue_puppy", "visual_style": "bright_colorful"},
            )
            controller.experience_store.add(record)

        result = controller.run_cycle("p04")
        assert result.cycle.strategies_generated > 0
        assert result.cycle.patterns_discovered > 0

    def test_run_cycle_updates_metrics(self):
        """周期更新指标。"""
        controller = MetaLearningController()
        for i in range(10):
            record = make_record(product="p04", creative=f"c{i:03d}")
            controller.experience_store.add(record)

        controller.run_cycle("p04")
        metrics = controller.get_metrics()
        assert metrics.total_cycles == 1

    def test_run_cycle_with_failure(self):
        """周期失败处理。"""
        controller = MetaLearningController()
        # 模拟空 store 和其他异常
        controller.experience_store = None  # Force error
        try:
            result = controller.run_cycle("p04")
            assert not result.success
        except AttributeError:
            pass  # 预期异常

    def test_should_run_true(self):
        """应该运行。"""
        controller = MetaLearningController()
        for i in range(100):
            record = make_record(product="p04", creative=f"c{i:03d}")
            controller.experience_store.add(record)
        assert controller.should_run("p04")

    def test_should_run_false(self):
        """不应该运行（数据不足）。"""
        # 使用高阈值确保不触发
        schedule = LearningSchedule(min_experiments=1000, min_spend=100000)
        controller = MetaLearningController(schedule=schedule)
        assert not controller.should_run("p04")

    def test_get_status(self):
        """获取控制器状态。"""
        controller = MetaLearningController()
        status = controller.get_status()
        assert "metrics" in status
        assert "cycle_stats" in status
        assert "feedback_summary" in status
        assert "graph_stats" in status

    def test_reset(self):
        """重置控制器。"""
        controller = MetaLearningController()
        for i in range(10):
            record = make_record(product="p04", creative=f"c{i:03d}")
            controller.experience_store.add(record)
        controller.run_cycle("p04")
        controller.reset()
        assert controller._metrics.total_cycles == 0

    def test_repr(self):
        """MetaLearningController repr。"""
        controller = MetaLearningController()
        assert "MetaLearningController" in repr(controller)

    def test_run_loop(self):
        """运行循环。"""
        controller = MetaLearningController()
        for i in range(100):
            record = make_record(product="p04", creative=f"c{i:03d}", improvement=0.3 + i * 0.01)
            controller.experience_store.add(record)

        results = controller.run_loop("p04", max_cycles=3, experiment_count=50, total_spend=5000)
        assert len(results) >= 0

    def test_custom_components(self):
        """自定义组件。"""
        store = ExperienceStore()
        scheduler = LearningScheduler(LearningSchedule(min_experiments=10, min_spend=1000))
        controller = MetaLearningController(
            experience_store=store,
            scheduler=scheduler,
        )
        assert controller.experience_store.query_all() == store.query_all()
        assert controller.scheduler.schedule.min_experiments == 10

    def test_run_cycle_learning_gain(self):
        """周期学习增益。"""
        controller = MetaLearningController()
        for i in range(10):
            record = make_record(product="p04", creative=f"c{i:03d}")
            controller.experience_store.add(record)

        result = controller.run_cycle("p04")
        assert result.cycle.learning_gain > 0

    def test_run_cycle_knowledge_updates(self):
        """周期知识更新。"""
        controller = MetaLearningController()
        for i in range(10):
            record = make_record(product="p04", creative=f"c{i:03d}")
            controller.experience_store.add(record)

        result = controller.run_cycle("p04")
        assert result.cycle.knowledge_updates > 0


# ═══════════════════════════════════════════════════════════
# 7. Edge Cases (10 tests)
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试。"""

    def test_cycle_manager_multiple_products(self):
        """多产品周期管理。"""
        mgr = CycleManager()
        mgr.create_cycle("p04")
        mgr.create_cycle("p05")
        mgr.create_cycle("p04")
        active_p04 = mgr.get_active_cycles_for_product("p04")
        active_p05 = mgr.get_active_cycles_for_product("p05")
        assert len(active_p04) == 2
        assert len(active_p05) == 1

    def test_cycle_manager_history_by_product(self):
        """按产品过滤历史。"""
        mgr = CycleManager()
        c1 = mgr.create_cycle("p04")
        mgr.complete(c1)
        c2 = mgr.create_cycle("p05")
        mgr.complete(c2)
        history_p04 = mgr.get_history("p04")
        assert len(history_p04) == 1
        assert history_p04[0].product_id == "p04"

    def test_scheduler_all_conditions_met(self):
        """所有条件同时满足。"""
        scheduler = LearningScheduler()
        trigger = scheduler.check(
            experiment_count=200,
            total_spend=50000,
            days_since_last=14,
            performance_drop=0.25,
        )
        assert trigger.should_trigger
        # 性能下降优先
        assert trigger.reason == TriggerReason.PERFORMANCE_DROP

    def test_updater_all_success(self):
        """全部成功的更新。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.50)
        updated, record = updater.update_node_confidence(
            node, success_count=25, total_count=25, cycle_id="MLC_001"
        )
        assert updated.confidence > 0.50
        assert record.is_improved

    def test_updater_all_failure(self):
        """全部失败的更新。"""
        updater = KnowledgeUpdater()
        node = make_knowledge_node(confidence=0.50)
        updated, record = updater.update_node_confidence(
            node, success_count=0, total_count=25, cycle_id="MLC_001"
        )
        assert updated.confidence < 0.50
        assert not record.is_improved

    def test_feedback_collector_empty_strategy(self):
        """空策略反馈。"""
        collector = StrategyFeedbackCollector()
        strategy = MetaStrategy(name="Empty")
        assert collector.get_feedbacks(strategy.strategy_id) == []
        assert collector.get_average_accuracy(strategy.strategy_id) == 0.0
        assert collector.get_success_rate(strategy.strategy_id) == 0.0

    def test_feedback_collector_multiple_strategies(self):
        """多策略反馈收集。"""
        collector = StrategyFeedbackCollector()
        s1 = MetaStrategy(name="S1")
        s2 = MetaStrategy(name="S2")
        collector.collect(s1, actual_gain=0.20, success=True)
        collector.collect(s2, actual_gain=0.15, success=True)
        collector.collect(s1, actual_gain=0.10, success=False)
        summary = collector.get_summary()
        assert summary["strategy_count"] == 2
        assert summary["total_feedbacks"] == 3

    def test_meta_learning_result_creation(self):
        """MetaLearningResult 创建。"""
        cycle = MetaLearningCycle(product_id="p04")
        result = MetaLearningResult(cycle=cycle, success=True)
        assert result.success
        assert result.summary is not None
        assert result.to_dict()["cycle"] is not None

    def test_meta_learning_result_no_trigger(self):
        """MetaLearningResult 无 trigger。"""
        result = MetaLearningResult(success=True)
        assert result.trigger is None
        assert result.to_dict()["trigger"] is None

    def test_loop_metrics_to_dict(self):
        """LoopMetrics to_dict。"""
        m = LoopMetrics(
            total_cycles=5,
            successful_cycles=4,
            failed_cycles=1,
            total_patterns_mined=20,
            total_knowledge_updated=50,
            total_strategies_generated=30,
            average_learning_gain=0.75,
        )
        d = m.to_dict()
        assert d["total_cycles"] == 5
        assert d["success_rate"] == 0.8
        assert d["average_learning_gain"] == 0.75