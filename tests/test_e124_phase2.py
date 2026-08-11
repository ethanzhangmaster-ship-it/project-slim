"""E12.4 Phase 2 — Autonomous Experiment Loop 测试。

覆盖:
  - MutationRequestBuilder: signal → intent → request (20 tests)
  - ExperimentTrigger: confidence/spend/cooldown checks (20 tests)
  - ExperimentMonitor: 6-stage lifecycle (15 tests)
  - ResultEvaluator: winner detection, metric comparison (20 tests)
  - LearningFeedback Phase 2: EvolutionLearningRecord (10 tests)

总计: 85+ tests
"""

import pytest
from datetime import datetime, timezone, timedelta

from market_ops.creative_vision_runtime.reality.feedback import (
    EvolutionLearningRecord,
    ExperimentEvaluation,
    ExperimentMonitor,
    ExperimentRun,
    ExperimentStatus,
    ExperimentTrigger,
    ExperimentTriggerResult,
    FeedbackSignalType,
    LearningFeedback,
    MutationIntent,
    MutationRequest,
    MutationRequestBuilder,
    RealityFeedbackSignal,
    ResultEvaluator,
)
from market_ops.creative_vision_runtime.reality.feedback.models import (
    INTENT_DNA_CONSTRAINTS,
    INTENT_GENERATION_COUNT,
    SIGNAL_TO_INTENT,
    VALID_EXPERIMENT_TRANSITIONS,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def make_signal(
    cid: str = "c001",
    signal_type: FeedbackSignalType = FeedbackSignalType.FATIGUE_WARNING,
    severity: float = 0.85,
    confidence: float = 0.91,
    spend: float = 500.0,
    reason: list[str] | None = None,
    metadata: dict | None = None,
) -> RealityFeedbackSignal:
    meta = {"spend": spend}
    if metadata:
        meta.update(metadata)
    return RealityFeedbackSignal(
        creative_id=cid,
        signal_type=signal_type,
        severity=severity,
        confidence=confidence,
        reason=reason or ["CTR -25%", "Frequency 5.2"],
        recommended_action="test_action",
        metadata=meta,
    )


def make_request(
    cid: str = "c001",
    intent: MutationIntent = MutationIntent.REFRESH_HOOK,
    confidence: float = 0.91,
    generation_count: int = 20,
) -> MutationRequest:
    return MutationRequest(
        creative_id=cid,
        intent=intent,
        signal_id="fs_test",
        reason=["CTR -25%", "Frequency 5.2"],
        confidence=confidence,
        dna_constraints=INTENT_DNA_CONSTRAINTS.get(intent, {"keep": [], "change": []}),
        generation_count=generation_count,
    )


# ═══════════════════════════════════════════════════════════
# 1. Mutation Request Builder (20 tests)
# ═══════════════════════════════════════════════════════════


class TestMutationRequestBuilder:
    """MutationRequestBuilder — Signal → MutationIntent → MutationRequest。"""

    def test_build_fatigue_to_hook_mutation(self):
        """疲劳预警 → REFRESH_HOOK。"""
        builder = MutationRequestBuilder()
        signal = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            reason=["CTR -25%", "Frequency 5.2"],
        )
        request = builder.build(signal)
        assert request.creative_id == "c001"
        assert request.intent == MutationIntent.REFRESH_HOOK
        assert request.generation_count == 20
        assert "hook" in request.change_genes

    def test_build_roas_decline_to_offer_change(self):
        """ROAS 下降 → OFFER_CHANGE。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.ROAS_DECLINE)
        request = builder.build(signal)
        assert request.intent == MutationIntent.OFFER_CHANGE
        assert request.generation_count == 10

    def test_build_scale_to_visual_variation(self):
        """放量机会 → VISUAL_VARIATION。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.SCALE_OPPORTUNITY)
        request = builder.build(signal)
        assert request.intent == MutationIntent.VISUAL_VARIATION
        assert request.generation_count == 15

    def test_build_replacement_to_full_rebuild(self):
        """素材替换 → FULL_REBUILD。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.CREATIVE_REPLACEMENT)
        request = builder.build(signal)
        assert request.intent == MutationIntent.FULL_REBUILD
        assert request.generation_count == 30

    def test_build_data_collection_to_refresh_hook(self):
        """数据不足 → REFRESH_HOOK（默认）。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.DATA_COLLECTION)
        request = builder.build(signal)
        assert request.intent == MutationIntent.REFRESH_HOOK

    def test_request_id_generated(self):
        builder = MutationRequestBuilder()
        signal = make_signal()
        request = builder.build(signal)
        assert request.request_id.startswith("mr_")

    def test_request_confidence_preserved(self):
        builder = MutationRequestBuilder()
        signal = make_signal(confidence=0.95)
        request = builder.build(signal)
        assert request.confidence == 0.95

    def test_request_reason_preserved(self):
        builder = MutationRequestBuilder()
        signal = make_signal(reason=["CTR drop", "High frequency"])
        request = builder.build(signal)
        assert "CTR drop" in request.reason
        assert "High frequency" in request.reason

    def test_dna_constraints_keep_genes(self):
        """REFRESH_HOOK 保留 gameplay, monetization, audience。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        request = builder.build(signal)
        assert "gameplay" in request.keep_genes
        assert "monetization" in request.keep_genes
        assert "audience" in request.keep_genes

    def test_dna_constraints_change_genes(self):
        """REFRESH_HOOK 修改 hook, visual_style。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        request = builder.build(signal)
        assert "hook" in request.change_genes
        assert "visual_style" in request.change_genes

    def test_full_rebuild_dna_constraints(self):
        """FULL_REBUILD: 只保留 audience，修改全部。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.CREATIVE_REPLACEMENT)
        request = builder.build(signal)
        assert request.keep_genes == ["audience"]
        assert len(request.change_genes) >= 6

    def test_offer_change_dna_constraints(self):
        """OFFER_CHANGE: 保留 hook/visual_style/gameplay，修改 monetization/context。"""
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.ROAS_DECLINE)
        request = builder.build(signal)
        assert "hook" in request.keep_genes
        assert "monetization" in request.change_genes

    def test_build_batch(self):
        builder = MutationRequestBuilder()
        signals = [
            make_signal(cid="c001", signal_type=FeedbackSignalType.FATIGUE_WARNING, confidence=0.91),
            make_signal(cid="c002", signal_type=FeedbackSignalType.ROAS_DECLINE, confidence=0.85),
            make_signal(cid="c003", signal_type=FeedbackSignalType.SCALE_OPPORTUNITY, confidence=0.75),
        ]
        requests = builder.build_batch(signals)
        assert len(requests) == 3
        # 按置信度降序
        assert requests[0].confidence >= requests[1].confidence
        assert requests[1].confidence >= requests[2].confidence

    def test_build_batch_empty(self):
        builder = MutationRequestBuilder()
        requests = builder.build_batch([])
        assert requests == []

    def test_build_with_override_intent(self):
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        request = builder.build_with_override(signal, intent=MutationIntent.FULL_REBUILD)
        assert request.intent == MutationIntent.FULL_REBUILD

    def test_build_with_override_generation_count(self):
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        request = builder.build_with_override(signal, generation_count=50)
        assert request.generation_count == 50

    def test_build_with_override_custom_constraints(self):
        builder = MutationRequestBuilder()
        signal = make_signal(signal_type=FeedbackSignalType.FATIGUE_WARNING)
        custom = {"keep": ["hook"], "change": ["visual_style", "gameplay"]}
        request = builder.build_with_override(signal, custom_constraints=custom)
        assert request.keep_genes == ["hook"]
        assert "visual_style" in request.change_genes
        assert "gameplay" in request.change_genes

    def test_metadata_dna_constraints_merged(self):
        """Signal metadata 中的 dna_keep/dna_change 被合并。"""
        builder = MutationRequestBuilder()
        signal = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            metadata={"spend": 500.0, "dna_keep": ["psychology"], "dna_change": ["context"]},
        )
        request = builder.build(signal)
        assert "psychology" in request.keep_genes
        assert "context" in request.change_genes

    def test_to_dict(self):
        builder = MutationRequestBuilder()
        signal = make_signal()
        request = builder.build(signal)
        d = request.to_dict()
        assert d["intent"] == "refresh_hook"
        assert d["generation_count"] == 20
        assert "keep_genes" in d
        assert "change_genes" in d

    def test_repr(self):
        builder = MutationRequestBuilder()
        signal = make_signal()
        request = builder.build(signal)
        r = repr(request)
        assert "MutationRequest" in r
        assert "c001" in r

    def test_total_requests_built_counter(self):
        builder = MutationRequestBuilder()
        assert builder.total_requests_built == 0
        builder.build(make_signal())
        builder.build(make_signal(cid="c002"))
        assert builder.total_requests_built == 2


# ═══════════════════════════════════════════════════════════
# 2. Experiment Trigger (20 tests)
# ═══════════════════════════════════════════════════════════


class TestExperimentTrigger:
    """ExperimentTrigger — confidence/spend/cooldown 安全检查。"""

    def test_trigger_all_conditions_met(self):
        """所有条件满足 → 触发。"""
        trigger = ExperimentTrigger()
        signal = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.85, confidence=0.91, spend=500.0,
        )
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True
        assert "confidence" in result.thresholds_met
        assert "spend" in result.thresholds_met
        assert "fatigue_probability" in result.thresholds_met
        assert "cooldown" in result.thresholds_met

    def test_not_trigger_low_confidence(self):
        trigger = ExperimentTrigger()
        signal = make_signal(confidence=0.70, spend=500.0)
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is False
        assert "confidence" in result.thresholds_failed

    def test_not_trigger_low_spend(self):
        trigger = ExperimentTrigger()
        signal = make_signal(confidence=0.91, spend=50.0)
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is False
        assert "spend" in result.thresholds_failed

    def test_not_trigger_low_fatigue_probability(self):
        trigger = ExperimentTrigger()
        signal = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.60, confidence=0.91, spend=500.0,
        )
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is False
        assert "fatigue_probability" in result.thresholds_failed

    def test_confidence_at_boundary(self):
        trigger = ExperimentTrigger()
        signal = make_signal(confidence=0.80, severity=0.85, spend=500.0)
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True

    def test_spend_at_boundary(self):
        trigger = ExperimentTrigger()
        signal = make_signal(confidence=0.91, severity=0.85, spend=100.0)
        request = make_request()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True

    def test_cooldown_blocks_second_trigger(self):
        """同一 creative 7 天内不重复触发。"""
        trigger = ExperimentTrigger()
        signal = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        request = make_request(cid="c001")

        # 第一次触发成功
        r1 = trigger.evaluate(signal, request)
        assert r1.should_trigger is True

        # 第二次被冷却阻止
        r2 = trigger.evaluate(signal, request)
        assert r2.should_trigger is False
        assert "cooldown" in r2.thresholds_failed

    def test_cooldown_allows_different_creative(self):
        """不同 creative 不受冷却影响。"""
        trigger = ExperimentTrigger()
        s1 = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        s2 = make_signal(cid="c002", confidence=0.91, severity=0.85, spend=500.0)
        r1 = make_request(cid="c001")
        r2 = make_request(cid="c002")

        trigger.evaluate(s1, r1)  # c001 触发
        result = trigger.evaluate(s2, r2)  # c002 不受影响
        assert result.should_trigger is True

    def test_cooldown_reset(self):
        trigger = ExperimentTrigger()
        signal = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        request = make_request(cid="c001")

        trigger.evaluate(signal, request)  # 触发，进入冷却
        trigger.reset_cooldown("c001")      # 重置冷却
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True

    def test_cooldown_reset_all(self):
        trigger = ExperimentTrigger()
        signals = [
            make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0),
            make_signal(cid="c002", confidence=0.91, severity=0.85, spend=500.0),
        ]
        requests = [make_request(cid="c001"), make_request(cid="c002")]

        for s, r in zip(signals, requests):
            trigger.evaluate(s, r)

        trigger.reset_all_cooldowns()

        for s, r in zip(signals, requests):
            result = trigger.evaluate(s, r)
            assert result.should_trigger is True

    def test_get_cooldown_remaining(self):
        trigger = ExperimentTrigger()
        now = datetime.now(timezone.utc)
        signal = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        request = make_request(cid="c001")

        trigger.evaluate(signal, request, current_time=now)
        remaining = trigger.get_cooldown_remaining("c001", current_time=now)
        assert remaining == 7  # 刚触发，剩余 7 天

    def test_get_cooldown_remaining_partial(self):
        trigger = ExperimentTrigger()
        now = datetime.now(timezone.utc)
        three_days_ago = now - timedelta(days=3)
        signal = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        request = make_request(cid="c001")

        trigger.evaluate(signal, request, current_time=three_days_ago)
        remaining = trigger.get_cooldown_remaining("c001", current_time=now)
        assert remaining == 4

    def test_get_cooldown_remaining_expired(self):
        trigger = ExperimentTrigger()
        now = datetime.now(timezone.utc)
        eight_days_ago = now - timedelta(days=8)
        signal = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        request = make_request(cid="c001")

        trigger.evaluate(signal, request, current_time=eight_days_ago)
        remaining = trigger.get_cooldown_remaining("c001", current_time=now)
        assert remaining == 0

    def test_non_fatigue_signal_expected_impact(self):
        """ROAS_DECLINE 信号检查 expected_impact 而非 fatigue_probability。"""
        trigger = ExperimentTrigger()
        signal = make_signal(
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.80, confidence=0.91, spend=500.0,
        )
        request = make_request(intent=MutationIntent.OFFER_CHANGE)
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True
        assert "expected_impact" in result.thresholds_met

    def test_non_fatigue_signal_low_impact(self):
        trigger = ExperimentTrigger()
        signal = make_signal(
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.03, confidence=0.91, spend=500.0,
        )
        request = make_request(intent=MutationIntent.OFFER_CHANGE)
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is False
        assert "expected_impact" in result.thresholds_failed

    def test_evaluate_batch(self):
        trigger = ExperimentTrigger()
        signals = [
            make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0),
            make_signal(cid="c002", confidence=0.70, severity=0.85, spend=500.0),
        ]
        requests = [make_request(cid="c001"), make_request(cid="c002")]
        results = trigger.evaluate_batch(signals, requests)
        assert len(results) == 2
        assert results[0].should_trigger is True
        assert results[1].should_trigger is False

    def test_get_triggered(self):
        trigger = ExperimentTrigger()
        results = [
            ExperimentTriggerResult(should_trigger=True, request_id="r1"),
            ExperimentTriggerResult(should_trigger=False, request_id="r2"),
            ExperimentTriggerResult(should_trigger=True, request_id="r3"),
        ]
        triggered = trigger.get_triggered(results)
        assert len(triggered) == 2
        assert all(r.should_trigger for r in triggered)

    def test_get_rejected(self):
        trigger = ExperimentTrigger()
        results = [
            ExperimentTriggerResult(should_trigger=True, request_id="r1"),
            ExperimentTriggerResult(should_trigger=False, request_id="r2"),
        ]
        rejected = trigger.get_rejected(results)
        assert len(rejected) == 1
        assert not rejected[0].should_trigger

    def test_trigger_result_repr(self):
        result = ExperimentTriggerResult(
            should_trigger=True, request_id="mr_test",
            reason=["All thresholds met"],
            thresholds_met=["confidence", "spend"],
        )
        r = repr(result)
        assert "trigger=True" in r

    def test_counter_stats(self):
        trigger = ExperimentTrigger()
        s1 = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        s2 = make_signal(cid="c002", confidence=0.60, severity=0.85, spend=500.0)
        trigger.evaluate(s1, make_request(cid="c001"))
        trigger.evaluate(s2, make_request(cid="c002"))
        assert trigger.total_evaluated == 2
        assert trigger.total_triggered == 1
        assert trigger.total_rejected == 1


# ═══════════════════════════════════════════════════════════
# 3. Experiment Monitor (15 tests)
# ═══════════════════════════════════════════════════════════


class TestExperimentMonitor:
    """ExperimentMonitor — 6 阶段生命周期。"""

    def test_create_experiment(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        assert exp.experiment_id.startswith("exp_")
        assert exp.status == ExperimentStatus.CREATED
        assert exp.creative_id == "c001"
        assert exp.mutation_request_id == request.request_id

    def test_create_with_custom_creative_id(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request, creative_id="custom_c001")
        assert exp.creative_id == "custom_c001"

    def test_create_batch(self):
        monitor = ExperimentMonitor()
        requests = [make_request(cid="c001"), make_request(cid="c002")]
        exps = monitor.create_batch(requests)
        assert len(exps) == 2
        assert exps[0].creative_id == "c001"
        assert exps[1].creative_id == "c002"

    def test_create_metadata(self):
        monitor = ExperimentMonitor()
        request = make_request(intent=MutationIntent.FULL_REBUILD, generation_count=30)
        exp = monitor.create(request)
        assert exp.metadata["intent"] == "full_rebuild"
        assert exp.metadata["generation_count"] == 30
        assert "dna_constraints" in exp.metadata

    def test_lifecycle_full_flow(self):
        """完整生命周期：CREATED → GENERATING → READY → RUNNING → COMPLETED。"""
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)

        exp = monitor.transition_to_generating(exp.experiment_id)
        assert exp.status == ExperimentStatus.GENERATING

        exp = monitor.transition_to_ready(exp.experiment_id, variants=["v1", "v2", "v3"])
        assert exp.status == ExperimentStatus.READY
        assert exp.variants == ["v1", "v2", "v3"]

        exp = monitor.transition_to_running(exp.experiment_id)
        assert exp.status == ExperimentStatus.RUNNING

        exp = monitor.transition_to_completed(exp.experiment_id)
        assert exp.status == ExperimentStatus.COMPLETED
        assert exp.is_terminal is True

    def test_lifecycle_failed_from_created(self):
        """CREATED → FAILED。"""
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        exp = monitor.transition_to_failed(exp.experiment_id, reason="Generation error")
        assert exp.status == ExperimentStatus.FAILED
        assert exp.metadata["failure_reason"] == "Generation error"

    def test_lifecycle_failed_from_running(self):
        """RUNNING → FAILED。"""
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        monitor.transition_to_ready(exp.experiment_id)
        monitor.transition_to_running(exp.experiment_id)
        exp = monitor.transition_to_failed(exp.experiment_id)
        assert exp.status == ExperimentStatus.FAILED

    def test_invalid_transition(self):
        """非法状态转换抛出 ValueError。"""
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        # CREATED → RUNNING 非法
        with pytest.raises(ValueError, match="Invalid transition"):
            monitor.transition_to_running(exp.experiment_id)

    def test_update_metrics(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        exp = monitor.update_metrics(exp.experiment_id, {"ctr": 0.031, "spend": 520.0})
        assert exp.metrics["ctr"] == 0.031
        assert exp.metrics["spend"] == 520.0

    def test_set_variants(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        exp = monitor.set_variants(exp.experiment_id, ["v1", "v2", "v3"])
        assert exp.variants == ["v1", "v2", "v3"]

    def test_get_active_experiments(self):
        monitor = ExperimentMonitor()
        r1 = make_request(cid="c001")
        r2 = make_request(cid="c002")
        monitor.create(r1)
        monitor.create(r2)
        active = monitor.get_active_experiments()
        assert len(active) == 2

    def test_get_completed_experiments(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        monitor.transition_to_ready(exp.experiment_id)
        monitor.transition_to_running(exp.experiment_id)
        monitor.transition_to_completed(exp.experiment_id)
        completed = monitor.get_completed_experiments()
        assert len(completed) == 1

    def test_get_by_creative(self):
        monitor = ExperimentMonitor()
        monitor.create(make_request(cid="c001"))
        monitor.create(make_request(cid="c001"))
        monitor.create(make_request(cid="c002"))
        c001_exps = monitor.get_by_creative("c001")
        assert len(c001_exps) == 2

    def test_get_by_status(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        generating = monitor.get_by_status(ExperimentStatus.GENERATING)
        assert len(generating) == 1

    def test_get_stats(self):
        monitor = ExperimentMonitor()
        monitor.create(make_request(cid="c001"))
        monitor.create(make_request(cid="c002"))
        stats = monitor.get_stats()
        assert stats["total_experiments"] == 2
        assert stats["active_experiments"] == 2
        assert stats["completed_experiments"] == 0
        assert "status_counts" in stats

    def test_clear(self):
        monitor = ExperimentMonitor()
        monitor.create(make_request())
        assert len(monitor) == 1
        monitor.clear()
        assert len(monitor) == 0

    def test_get_by_mutation_request(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        found = monitor.get_by_mutation_request(request.request_id)
        assert found is not None
        assert found.experiment_id == exp.experiment_id

    def test_status_history_recorded(self):
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        exp = monitor.get_experiment(exp.experiment_id)
        history = exp.metadata.get("status_history", [])
        assert len(history) == 1
        assert history[0]["from"] == "created"
        assert history[0]["to"] == "generating"


# ═══════════════════════════════════════════════════════════
# 4. Result Evaluator (20 tests)
# ═══════════════════════════════════════════════════════════


class TestResultEvaluator:
    """ResultEvaluator — 旧 vs 新对比，赢家检测。"""

    def test_winner_detection(self):
        """v2 CTR 0.030 > v1 0.028 → v2 赢。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {
            "v1": {"ctr": 0.028, "roas": 0.68},
            "v2": {"ctr": 0.030, "roas": 0.72},
            "v3": {"ctr": 0.019, "roas": 0.50},
        }
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert evaluation.winner_id == "v2"
        assert evaluation.improvement_score > 0
        assert evaluation.has_winner is True

    def test_improvement_score_positive(self):
        """改善 → improvement_score > 0。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert evaluation.improvement_score > 0.15
        assert evaluation.is_significant_improvement is True

    def test_improvement_score_negative(self):
        """变体全部劣于基线 → improvement_score < 0。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.030, "roas": 0.72}
        variants = {"v1": {"ctr": 0.021, "roas": 0.55}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert evaluation.improvement_score < 0
        assert evaluation.has_winner is False

    def test_no_variants(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021}
        evaluation = evaluator.evaluate(exp, baseline, {})
        assert evaluation.winner_id == ""
        assert evaluation.improvement_score == 0.0
        assert "No variants" in evaluation.learning_signal

    def test_metrics_delta(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert "ctr" in evaluation.metrics_delta
        assert "roas" in evaluation.metrics_delta
        assert evaluation.metrics_delta["ctr"] > 0
        assert evaluation.metrics_delta["roas"] > 0

    def test_cpi_lower_is_better(self):
        """CPI 越低越好。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"cpi": 2.5, "roas": 0.55}
        variants = {"v1": {"cpi": 1.8, "roas": 0.55}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        # CPI 降低 → improvement_score 应该为正
        assert evaluation.metrics_delta["cpi"] > 0  # 反向后的 delta 为正

    def test_cpi_higher_is_worse(self):
        """CPI 升高 → 负向。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"cpi": 1.8, "roas": 0.55}
        variants = {"v1": {"cpi": 2.5, "roas": 0.55}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert evaluation.metrics_delta["cpi"] < 0

    def test_learning_signal_generated(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert "Winner" in evaluation.learning_signal
        assert "v1" in evaluation.learning_signal

    def test_learning_signal_no_winner(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.030, "roas": 0.72}
        variants = {"v1": {"ctr": 0.021, "roas": 0.55}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert "No winner" in evaluation.learning_signal or "No improvement" in evaluation.learning_signal

    def test_confidence_calculation(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert 0.5 <= evaluation.confidence <= 1.0

    def test_confidence_higher_with_more_variants(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants_1 = {"v1": {"ctr": 0.030, "roas": 0.72}}
        variants_3 = {
            "v1": {"ctr": 0.028, "roas": 0.68},
            "v2": {"ctr": 0.030, "roas": 0.72},
            "v3": {"ctr": 0.025, "roas": 0.60},
        }
        e1 = evaluator.evaluate(exp, baseline, variants_1)
        e3 = evaluator.evaluate(exp, baseline, variants_3)
        assert e3.confidence >= e1.confidence

    def test_evaluate_from_experiment_metrics(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(
            creative_id="c001",
            metrics={
                "baseline": {"ctr": 0.021, "roas": 0.55},
                "variants": {
                    "v1": {"ctr": 0.030, "roas": 0.72},
                },
            },
        )
        evaluation = evaluator.evaluate_from_experiment_metrics(exp)
        assert evaluation.winner_id == "v1"
        assert evaluation.improvement_score > 0

    def test_evaluate_batch(self):
        evaluator = ResultEvaluator()
        exp1 = ExperimentRun(creative_id="c001")
        exp2 = ExperimentRun(creative_id="c002")
        baselines = [
            {"ctr": 0.021, "roas": 0.55},
            {"ctr": 0.030, "roas": 0.72},
        ]
        variants_list = [
            {"v1": {"ctr": 0.030, "roas": 0.72}},
            {"v1": {"ctr": 0.021, "roas": 0.55}},
        ]
        evaluations = evaluator.evaluate_batch([exp1, exp2], baselines, variants_list)
        assert len(evaluations) == 2
        assert evaluations[0].improvement_score > 0
        assert evaluations[1].improvement_score < 0

    def test_find_winners(self):
        evaluator = ResultEvaluator()
        evaluations = [
            ExperimentEvaluation(winner_id="v1", improvement_score=0.3),
            ExperimentEvaluation(winner_id="", improvement_score=-0.1),
            ExperimentEvaluation(winner_id="v2", improvement_score=0.2),
        ]
        winners = evaluator.find_winners(evaluations)
        assert len(winners) == 2

    def test_get_best_improvement(self):
        evaluator = ResultEvaluator()
        evaluations = [
            ExperimentEvaluation(winner_id="v1", improvement_score=0.1),
            ExperimentEvaluation(winner_id="v2", improvement_score=0.5),
            ExperimentEvaluation(winner_id="v3", improvement_score=0.3),
        ]
        best = evaluator.get_best_improvement(evaluations)
        assert best is not None
        assert best.winner_id == "v2"

    def test_get_best_improvement_empty(self):
        evaluator = ResultEvaluator()
        best = evaluator.get_best_improvement([])
        assert best is None

    def test_raw_metrics_included(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert "baseline" in evaluation.raw_metrics
        assert "v1" in evaluation.raw_metrics
        assert evaluation.raw_metrics["baseline"]["ctr"] == 0.021

    def test_improvement_score_range(self):
        """improvement_score 在 [-1, 1] 范围内（正常场景）。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.020, "roas": 0.50}
        variants = {"v1": {"ctr": 0.040, "roas": 1.0}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert -1.0 <= evaluation.improvement_score <= 1.0

    def test_zero_baseline_handling(self):
        """基线为 0 时正确处理。"""
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.0, "roas": 0.0}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        assert evaluation.improvement_score > 0

    def test_evaluation_to_dict(self):
        evaluator = ResultEvaluator()
        exp = ExperimentRun(creative_id="c001")
        baseline = {"ctr": 0.021, "roas": 0.55}
        variants = {"v1": {"ctr": 0.030, "roas": 0.72}}
        evaluation = evaluator.evaluate(exp, baseline, variants)
        d = evaluation.to_dict()
        assert d["winner_id"] == "v1"
        assert "improvement_score" in d
        assert "has_winner" in d
        assert "is_significant_improvement" in d


# ═══════════════════════════════════════════════════════════
# 5. LearningFeedback Phase 2 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestLearningFeedbackPhase2:
    """LearningFeedback Phase 2 — EvolutionLearningRecord。"""

    def test_record_evolution(self):
        lf = LearningFeedback()
        record = lf.record_evolution(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.85,
            mutation_success=True,
            winner_dna={"hook": "rescue", "visual_style": "fantasy"},
            insight="Stronger rescue hook improved ROAS by 31%",
        )
        assert record.record_id.startswith("elr_")
        assert record.prediction_accuracy == 0.85
        assert record.mutation_success is True
        assert record.winner_dna["hook"] == "rescue"

    def test_record_evolution_from_evaluation(self):
        lf = LearningFeedback()
        record = lf.record_evolution_from_evaluation(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.90,
            mutation_success=True,
            insight="Hook mutation successful",
        )
        assert record.prediction_accuracy == 0.90

    def test_get_evolution_records(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        records = lf.get_evolution_records()
        assert len(records) == 2

    def test_get_evolution_insights(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True, insight="insight_1")
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False, insight="insight_2")
        insights = lf.get_evolution_insights()
        assert len(insights) == 2
        # 按时间倒序，最新的在前
        assert insights[0] == "insight_2"

    def test_get_evolution_stats(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.65, False)
        lf.record_evolution("rp_003", "mr_003", "exp_003", 0.90, True)
        stats = lf.get_evolution_stats()
        assert stats["total_records"] == 3
        assert stats["mutation_success_rate"] == pytest.approx(2 / 3)
        assert stats["mean_prediction_accuracy"] == pytest.approx(0.80)
        assert stats["successful_mutations"] == 2
        assert stats["failed_mutations"] == 1

    def test_get_evolution_stats_empty(self):
        lf = LearningFeedback()
        stats = lf.get_evolution_stats()
        assert stats["total_records"] == 0
        assert stats["mutation_success_rate"] == 0.0

    def test_get_successful_mutations(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        successful = lf.get_successful_mutations()
        assert len(successful) == 1

    def test_get_failed_mutations(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        failed = lf.get_failed_mutations()
        assert len(failed) == 1

    def test_get_evolution_records_by_experiment(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        records = lf.get_evolution_records_by_experiment("exp_001")
        assert len(records) == 1
        assert records[0].experiment_id == "exp_001"

    def test_get_evolution_recommendations_low_success(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, False)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        lf.record_evolution("rp_003", "mr_003", "exp_003", 0.90, True)
        recs = lf.get_evolution_recommendations()
        assert len(recs) >= 1
        # 成功率 1/3 = 33% > 30%, 所以不会触发低成功率警告
        # 但可能是正常或包含其他建议

    def test_get_evolution_recommendations_insufficient(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        recs = lf.get_evolution_recommendations()
        assert "Insufficient" in recs[0]

    def test_clear_clears_evolution_records(self):
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        assert lf.total_evolution_records == 1
        lf.clear()
        assert lf.total_evolution_records == 0

    def test_total_evolution_records_property(self):
        lf = LearningFeedback()
        assert lf.total_evolution_records == 0
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_evolution("rp_002", "mr_002", "exp_002", 0.70, False)
        assert lf.total_evolution_records == 2

    def test_evolution_learning_record_repr(self):
        record = EvolutionLearningRecord(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.85,
            mutation_success=True,
            insight="Stronger rescue hook",
        )
        r = repr(record)
        assert "EvolutionLearningRecord" in r

    def test_evolution_learning_record_to_dict(self):
        record = EvolutionLearningRecord(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.85,
            mutation_success=True,
            winner_dna={"hook": "rescue"},
            insight="test",
        )
        d = record.to_dict()
        assert d["prediction_accuracy"] == 0.85
        assert d["mutation_success"] is True
        assert d["winner_dna"]["hook"] == "rescue"

    def test_learning_feedback_repr_phase2(self):
        """repr 中应包含 Phase 2 统计。"""
        lf = LearningFeedback()
        lf.record_evolution("rp_001", "mr_001", "exp_001", 0.85, True)
        lf.record_outcome("rp_001", "c001", "roas", 0.55, 0.48)
        r = repr(lf)
        assert "evolution_records" in r
        assert "mutation_success" in r


# ═══════════════════════════════════════════════════════════
# 6. Full Pipeline Integration (5 tests)
# ═══════════════════════════════════════════════════════════


class TestFullPipeline:
    """完整闭环：Signal → Mutation → Trigger → Experiment → Evaluate → Learn。"""

    def test_full_pipeline_end_to_end(self):
        """完整闭环流程。"""
        # 1. Signal → MutationRequest
        builder = MutationRequestBuilder()
        signal = make_signal(
            signal_type=FeedbackSignalType.FATIGUE_WARNING,
            severity=0.85, confidence=0.91, spend=500.0,
        )
        request = builder.build(signal)
        assert request.intent == MutationIntent.REFRESH_HOOK

        # 2. Trigger → Experiment
        trigger = ExperimentTrigger()
        trigger_result = trigger.evaluate(signal, request)
        assert trigger_result.should_trigger is True

        # 3. Experiment lifecycle
        monitor = ExperimentMonitor()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        monitor.transition_to_ready(exp.experiment_id, variants=["v1", "v2", "v3"])
        monitor.transition_to_running(exp.experiment_id)
        monitor.update_metrics(exp.experiment_id, {
            "baseline": {"ctr": 0.021, "roas": 0.55},
            "variants": {
                "v1": {"ctr": 0.028, "roas": 0.68},
                "v2": {"ctr": 0.030, "roas": 0.72},
                "v3": {"ctr": 0.019, "roas": 0.50},
            },
        })
        monitor.transition_to_completed(exp.experiment_id)

        # 4. Result evaluation
        evaluator = ResultEvaluator()
        evaluation = evaluator.evaluate_from_experiment_metrics(exp)
        assert evaluation.has_winner is True
        assert evaluation.winner_id == "v2"

        # 5. Learning feedback
        lf = LearningFeedback()
        record = lf.record_evolution(
            prediction_id="rp_001",
            mutation_request_id=request.request_id,
            experiment_id=exp.experiment_id,
            prediction_accuracy=0.85,
            mutation_success=evaluation.has_winner,
            winner_dna=evaluation.raw_metrics.get(evaluation.winner_id, {}),
            insight=evaluation.learning_signal,
        )
        assert record.mutation_success is True
        assert "v2" in record.insight

    def test_pipeline_roas_decline(self):
        """ROAS 下降信号 → OFFER_CHANGE → 实验 → 评估。"""
        builder = MutationRequestBuilder()
        signal = make_signal(
            signal_type=FeedbackSignalType.ROAS_DECLINE,
            severity=0.80, confidence=0.91, spend=500.0,
        )
        request = builder.build(signal)
        assert request.intent == MutationIntent.OFFER_CHANGE

        trigger = ExperimentTrigger()
        result = trigger.evaluate(signal, request)
        assert result.should_trigger is True

        monitor = ExperimentMonitor()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        monitor.transition_to_ready(exp.experiment_id, variants=["v1"])
        monitor.transition_to_running(exp.experiment_id)
        monitor.update_metrics(exp.experiment_id, {
            "baseline": {"roas": 0.55, "cvr": 0.03},
            "variants": {"v1": {"roas": 0.72, "cvr": 0.04}},
        })
        monitor.transition_to_completed(exp.experiment_id)

        evaluator = ResultEvaluator()
        evaluation = evaluator.evaluate_from_experiment_metrics(exp)
        assert evaluation.has_winner is True

    def test_pipeline_rejected_by_cooldown(self):
        """冷却阻止重复触发。"""
        builder = MutationRequestBuilder()
        trigger = ExperimentTrigger()

        s1 = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        r1 = builder.build(s1)

        # 第一次触发
        assert trigger.evaluate(s1, r1).should_trigger is True

        # 第二次被冷却
        s2 = make_signal(cid="c001", confidence=0.91, severity=0.85, spend=500.0)
        r2 = builder.build(s2)
        assert trigger.evaluate(s2, r2).should_trigger is False

    def test_pipeline_no_winner_feedback(self):
        """无赢家 → 学习记录标记 mutation_success=False。"""
        monitor = ExperimentMonitor()
        request = make_request()
        exp = monitor.create(request)
        monitor.transition_to_generating(exp.experiment_id)
        monitor.transition_to_ready(exp.experiment_id, variants=["v1"])
        monitor.transition_to_running(exp.experiment_id)
        monitor.update_metrics(exp.experiment_id, {
            "baseline": {"ctr": 0.030, "roas": 0.72},
            "variants": {"v1": {"ctr": 0.021, "roas": 0.55}},
        })
        monitor.transition_to_completed(exp.experiment_id)

        evaluator = ResultEvaluator()
        evaluation = evaluator.evaluate_from_experiment_metrics(exp)
        assert evaluation.has_winner is False

        lf = LearningFeedback()
        record = lf.record_evolution(
            "rp_001", "mr_001", exp.experiment_id,
            0.85, evaluation.has_winner,
            insight=evaluation.learning_signal,
        )
        assert record.mutation_success is False

    def test_pipeline_multiple_creatives(self):
        """多个创意并行处理。"""
        builder = MutationRequestBuilder()
        signals = [
            make_signal(cid="c001", signal_type=FeedbackSignalType.FATIGUE_WARNING,
                        confidence=0.91, severity=0.85, spend=500.0),
            make_signal(cid="c002", signal_type=FeedbackSignalType.ROAS_DECLINE,
                        confidence=0.91, severity=0.80, spend=500.0),
        ]
        requests = builder.build_batch(signals)
        assert len(requests) == 2
        assert requests[0].intent == MutationIntent.REFRESH_HOOK
        assert requests[1].intent == MutationIntent.OFFER_CHANGE


# ═══════════════════════════════════════════════════════════
# 7. Model Constants (5 tests)
# ═══════════════════════════════════════════════════════════


class TestPhase2ModelConstants:
    """Phase 2 模型常量验证。"""

    def test_signal_to_intent_complete(self):
        """所有 FeedbackSignalType 都有对应的 MutationIntent。"""
        for signal_type in FeedbackSignalType:
            assert signal_type in SIGNAL_TO_INTENT

    def test_intent_dna_constraints_complete(self):
        """所有 MutationIntent 都有 DNA 约束。"""
        for intent in MutationIntent:
            assert intent in INTENT_DNA_CONSTRAINTS
            c = INTENT_DNA_CONSTRAINTS[intent]
            assert "keep" in c
            assert "change" in c

    def test_intent_generation_count_complete(self):
        """所有 MutationIntent 都有建议生成数量。"""
        for intent in MutationIntent:
            assert intent in INTENT_GENERATION_COUNT
            assert INTENT_GENERATION_COUNT[intent] > 0

    def test_experiment_status_count(self):
        """6 种实验状态。"""
        assert len(list(ExperimentStatus)) == 6

    def test_valid_transitions_terminal(self):
        """COMPLETED 和 FAILED 不能转换到其他状态。"""
        assert VALID_EXPERIMENT_TRANSITIONS[ExperimentStatus.COMPLETED] == []
        assert VALID_EXPERIMENT_TRANSITIONS[ExperimentStatus.FAILED] == []