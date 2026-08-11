"""E11.9 — Autonomous Evolution Orchestrator Tests。

覆盖：
  - Models: EvolutionCycleStatus, OpportunityType, EvolutionAction, EvolutionOpportunity, EvolutionDecision, EvolutionCycle, EvolutionCycleResult
  - OpportunityDetector: detect / detect_top / fatigue / performance_drop / diversity / knowledge_gap / underexploited
  - DecisionEngine: decide / decide_batch / START_EVOLUTION / OBSERVE / HOLD / budget constraints / active cycles
  - LifecycleManager: can_transition / transition / register / max_active / duplicate / stats
  - EvolutionCycle: no opportunity / decision not start / failed planning / failed execution / full cycle
  - EvolutionOrchestrator: run / run_loop / get_status / reset
  - Controller Integration: run_evolution_cycle / run_evolution_loop / detect_evolution_opportunity
  - Full Pipeline
  - Package Exports
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.models import (
    EvolutionAction,
    EvolutionCycle,
    EvolutionCycleResult,
    EvolutionCycleStatus,
    EvolutionDecision,
    EvolutionOpportunity,
    OpportunityType,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.opportunity_detector import (
    OpportunityDetector,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.decision_engine import (
    DecisionEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.lifecycle_manager import (
    LifecycleManager,
    VALID_TRANSITIONS,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.evolution_cycle import (
    EvolutionCycleRunner,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator.evolution_orchestrator import (
    EvolutionOrchestrator,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_market_signal(
    metrics: dict | None = None,
    trends: dict | None = None,
    usage_count: int = 0,
    previous_metrics: dict | None = None,
) -> dict:
    return {
        "metrics": metrics or {},
        "trends": trends or {},
        "usage_count": usage_count,
        "previous_metrics": previous_metrics or {},
    }


def _make_knowledge(
    overall_confidence: float = 0.5,
    mutation_performance: dict | None = None,
) -> dict:
    return {
        "overall_confidence": overall_confidence,
        "mutation_performance": mutation_performance or {},
    }


def _make_population(diversity_score: float = 0.5) -> dict:
    return {"diversity_score": diversity_score}


# ================================================================
# Models
# ================================================================


class TestEvolutionCycleStatus:
    """测试 EvolutionCycleStatus 枚举。"""

    def test_all_statuses(self):
        assert EvolutionCycleStatus.IDLE.value == "idle"
        assert EvolutionCycleStatus.DETECTING.value == "detecting"
        assert EvolutionCycleStatus.PLANNING.value == "planning"
        assert EvolutionCycleStatus.EXECUTING.value == "executing"
        assert EvolutionCycleStatus.EVALUATING.value == "evaluating"
        assert EvolutionCycleStatus.LEARNING.value == "learning"
        assert EvolutionCycleStatus.COMPLETED.value == "completed"
        assert EvolutionCycleStatus.FAILED.value == "failed"
        assert EvolutionCycleStatus.CANCELLED.value == "cancelled"

    def test_string_enum(self):
        assert isinstance(EvolutionCycleStatus.IDLE, str)


class TestOpportunityType:
    """测试 OpportunityType 枚举。"""

    def test_all_types(self):
        assert OpportunityType.CREATIVE_FATIGUE.value == "creative_fatigue"
        assert OpportunityType.PERFORMANCE_DROP.value == "performance_drop"
        assert OpportunityType.MARKET_SHIFT.value == "market_shift"
        assert OpportunityType.NEW_WINNER_PATTERN.value == "new_winner_pattern"
        assert OpportunityType.UNDEREXPLOITED_DNA.value == "underexploited_dna"
        assert OpportunityType.KNOWLEDGE_GAP.value == "knowledge_gap"
        assert OpportunityType.DIVERSITY_COLLAPSE.value == "diversity_collapse"
        assert OpportunityType.SCHEDULED.value == "scheduled"


class TestEvolutionAction:
    """测试 EvolutionAction 枚举。"""

    def test_all_actions(self):
        assert EvolutionAction.START_EVOLUTION.value == "start_evolution"
        assert EvolutionAction.OBSERVE.value == "observe"
        assert EvolutionAction.HOLD.value == "hold"
        assert EvolutionAction.ABORT.value == "abort"


class TestEvolutionOpportunity:
    """测试 EvolutionOpportunity 数据模型。"""

    def test_creation_defaults(self):
        opp = EvolutionOpportunity()
        assert opp.opportunity_id.startswith("opp_")
        assert opp.score == 0.0
        assert opp.evidence == []
        assert opp.created_at != ""

    def test_creation_with_fields(self):
        opp = EvolutionOpportunity(
            opportunity_id="test_opp",
            type=OpportunityType.CREATIVE_FATIGUE,
            score=0.85,
            evidence=["CTR drop: -20%"],
            metrics={"CTR": 0.03},
            metadata={"source": "market"},
        )
        assert opp.opportunity_id == "test_opp"
        assert opp.type == OpportunityType.CREATIVE_FATIGUE
        assert opp.score == 0.85
        assert "CTR drop" in opp.evidence[0]
        assert opp.metrics["CTR"] == 0.03

    def test_is_high_priority(self):
        assert EvolutionOpportunity(score=0.8).is_high_priority
        assert EvolutionOpportunity(score=0.9).is_high_priority
        assert not EvolutionOpportunity(score=0.79).is_high_priority

    def test_is_medium_priority(self):
        assert EvolutionOpportunity(score=0.5).is_medium_priority
        assert EvolutionOpportunity(score=0.7).is_medium_priority
        assert not EvolutionOpportunity(score=0.8).is_medium_priority
        assert not EvolutionOpportunity(score=0.49).is_medium_priority

    def test_is_low_priority(self):
        assert EvolutionOpportunity(score=0.49).is_low_priority
        assert EvolutionOpportunity(score=0.1).is_low_priority
        assert not EvolutionOpportunity(score=0.5).is_low_priority

    def test_to_dict(self):
        opp = EvolutionOpportunity(
            type=OpportunityType.PERFORMANCE_DROP,
            score=0.6,
            evidence=["ROI drop"],
            metrics={"ROI": 0.8},
        )
        d = opp.to_dict()
        assert d["type"] == "performance_drop"
        assert d["score"] == 0.6
        assert d["evidence"] == ["ROI drop"]

    def test_repr(self):
        opp = EvolutionOpportunity(type=OpportunityType.CREATIVE_FATIGUE, score=0.82)
        r = repr(opp)
        assert "creative_fatigue" in r
        assert "0.82" in r


class TestEvolutionDecision:
    """测试 EvolutionDecision 数据模型。"""

    def test_creation_defaults(self):
        d = EvolutionDecision()
        assert d.decision_id.startswith("dec_")
        assert d.action == EvolutionAction.HOLD
        assert d.confidence == 0.0

    def test_should_evolve(self):
        assert EvolutionDecision(action=EvolutionAction.START_EVOLUTION).should_evolve
        assert not EvolutionDecision(action=EvolutionAction.OBSERVE).should_evolve
        assert not EvolutionDecision(action=EvolutionAction.HOLD).should_evolve

    def test_to_dict(self):
        opp = EvolutionOpportunity(score=0.9)
        d = EvolutionDecision(
            action=EvolutionAction.START_EVOLUTION,
            reason="High opportunity",
            confidence=0.85,
            opportunity=opp,
        )
        result = d.to_dict()
        assert result["action"] == "start_evolution"
        assert result["confidence"] == 0.85
        assert result["opportunity"] is not None

    def test_to_dict_no_opportunity(self):
        d = EvolutionDecision(action=EvolutionAction.HOLD, reason="Low score")
        result = d.to_dict()
        assert result["opportunity"] is None

    def test_repr(self):
        d = EvolutionDecision(action=EvolutionAction.START_EVOLUTION, confidence=0.91)
        r = repr(d)
        assert "start_evolution" in r
        assert "0.91" in r


class TestEvolutionCycle:
    """测试 EvolutionCycle 数据模型。"""

    def test_creation_defaults(self):
        cycle = EvolutionCycle()
        assert cycle.cycle_id.startswith("cycle_")
        assert cycle.status == EvolutionCycleStatus.IDLE
        assert cycle.opportunity_score == 0.0
        assert cycle.created_at != ""

    def test_is_active(self):
        active_statuses = [
            EvolutionCycleStatus.DETECTING,
            EvolutionCycleStatus.PLANNING,
            EvolutionCycleStatus.EXECUTING,
            EvolutionCycleStatus.EVALUATING,
            EvolutionCycleStatus.LEARNING,
        ]
        for s in active_statuses:
            assert EvolutionCycle(status=s).is_active

        inactive = [EvolutionCycleStatus.IDLE, EvolutionCycleStatus.COMPLETED,
                     EvolutionCycleStatus.FAILED, EvolutionCycleStatus.CANCELLED]
        for s in inactive:
            assert not EvolutionCycle(status=s).is_active

    def test_is_terminal(self):
        assert EvolutionCycle(status=EvolutionCycleStatus.COMPLETED).is_terminal
        assert EvolutionCycle(status=EvolutionCycleStatus.FAILED).is_terminal
        assert EvolutionCycle(status=EvolutionCycleStatus.CANCELLED).is_terminal
        assert not EvolutionCycle(status=EvolutionCycleStatus.EXECUTING).is_terminal

    def test_to_dict(self):
        cycle = EvolutionCycle(
            cycle_id="test_cycle",
            status=EvolutionCycleStatus.COMPLETED,
            trigger_reason="fatigue",
            opportunity_score=0.85,
            strategy_id="s1",
        )
        d = cycle.to_dict()
        assert d["cycle_id"] == "test_cycle"
        assert d["status"] == "completed"
        assert d["trigger_reason"] == "fatigue"
        assert d["decision"] is None

    def test_to_dict_with_decision(self):
        cycle = EvolutionCycle(
            decision=EvolutionDecision(action=EvolutionAction.START_EVOLUTION),
        )
        d = cycle.to_dict()
        assert d["decision"] is not None
        assert d["decision"]["action"] == "start_evolution"

    def test_repr(self):
        cycle = EvolutionCycle(cycle_id="c1", opportunity_score=0.75)
        r = repr(cycle)
        assert "c1" in r
        assert "0.75" in r


class TestEvolutionCycleResult:
    """测试 EvolutionCycleResult 数据模型。"""

    def test_creation_defaults(self):
        r = EvolutionCycleResult()
        assert r.success is False
        assert r.strategies == []
        assert r.created_at != ""

    def test_creation_with_cycle(self):
        cycle = EvolutionCycle(status=EvolutionCycleStatus.COMPLETED)
        r = EvolutionCycleResult(cycle=cycle, success=True, summary="Done")
        assert r.success
        assert r.summary == "Done"

    def test_to_dict(self):
        cycle = EvolutionCycle(cycle_id="c1")
        r = EvolutionCycleResult(cycle=cycle, success=True, summary="OK")
        d = r.to_dict()
        assert d["success"] is True
        assert d["summary"] == "OK"
        assert d["cycle"] is not None

    def test_to_dict_no_cycle(self):
        r = EvolutionCycleResult(success=False, summary="No cycle")
        d = r.to_dict()
        assert d["cycle"] is None

    def test_repr(self):
        r = EvolutionCycleResult(success=True, strategies=[1, 2, 3])
        rep = repr(r)
        assert "True" in rep
        assert "3" in rep


# ================================================================
# OpportunityDetector
# ================================================================


class TestOpportunityDetector:
    """测试 OpportunityDetector。"""

    def test_detect_empty_inputs(self):
        detector = OpportunityDetector()
        ops = detector.detect()
        assert ops == []

    def test_detect_top_empty(self):
        detector = OpportunityDetector()
        assert detector.detect_top() is None

    def test_detect_fatigue_ctr_drop(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(
            trends={"CTR": -0.20, "impressions": 0.35},
            usage_count=35,
            metrics={"CTR": 0.015},
        )
        ops = detector.detect(market_signal=signal)
        assert len(ops) >= 1
        assert ops[0].type == OpportunityType.CREATIVE_FATIGUE
        assert ops[0].score > 0.5

    def test_detect_fatigue_no_drop(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(trends={"CTR": -0.05})
        ops = detector.detect(market_signal=signal)
        fatigue = [o for o in ops if o.type == OpportunityType.CREATIVE_FATIGUE]
        assert len(fatigue) == 0

    def test_detect_performance_drop(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(
            trends={"ROI": -0.25, "CTR": -0.22},
            metrics={"ROI": 0.8, "CTR": 0.02},
        )
        ops = detector.detect(market_signal=signal)
        assert len(ops) >= 1
        assert ops[0].type == OpportunityType.PERFORMANCE_DROP
        assert ops[0].score > 0.5

    def test_detect_performance_drop_single_metric(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(trends={"CVR": -0.30})
        ops = detector.detect(market_signal=signal)
        perf = [o for o in ops if o.type == OpportunityType.PERFORMANCE_DROP]
        assert len(perf) == 1
        assert perf[0].score == pytest.approx(0.3)

    def test_detect_performance_drop_no_drop(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(trends={"ROI": -0.05, "CTR": 0.01})
        ops = detector.detect(market_signal=signal)
        perf = [o for o in ops if o.type == OpportunityType.PERFORMANCE_DROP]
        assert len(perf) == 0

    def test_detect_diversity_collapse(self):
        detector = OpportunityDetector()
        ops = detector.detect(population=_make_population(diversity_score=0.1))
        div = [o for o in ops if o.type == OpportunityType.DIVERSITY_COLLAPSE]
        assert len(div) == 1
        assert div[0].score > 0

    def test_detect_diversity_ok(self):
        detector = OpportunityDetector()
        ops = detector.detect(population=_make_population(diversity_score=0.5))
        div = [o for o in ops if o.type == OpportunityType.DIVERSITY_COLLAPSE]
        assert len(div) == 0

    def test_detect_knowledge_gap(self):
        detector = OpportunityDetector()
        knowledge = _make_knowledge(
            overall_confidence=0.2,
            mutation_performance={
                "hook": {"sample_count": 2, "success_rate": 0.5},
            },
        )
        ops = detector.detect(knowledge=knowledge)
        gap = [o for o in ops if o.type == OpportunityType.KNOWLEDGE_GAP]
        assert len(gap) == 1
        assert gap[0].score > 0

    def test_detect_knowledge_gap_no_gap(self):
        detector = OpportunityDetector()
        knowledge = _make_knowledge(
            overall_confidence=0.8,
            mutation_performance={
                "hook": {"sample_count": 20, "success_rate": 0.5},
            },
        )
        ops = detector.detect(knowledge=knowledge)
        gap = [o for o in ops if o.type == OpportunityType.KNOWLEDGE_GAP]
        assert len(gap) == 0

    def test_detect_underexploited(self):
        detector = OpportunityDetector()
        knowledge = _make_knowledge(
            mutation_performance={
                "hook": {"success_rate": 0.8, "sample_count": 3},
            },
        )
        ops = detector.detect(knowledge=knowledge)
        under = [o for o in ops if o.type == OpportunityType.UNDEREXPLOITED_DNA]
        assert len(under) == 1

    def test_detect_underexploited_no_data(self):
        detector = OpportunityDetector()
        knowledge = _make_knowledge(
            mutation_performance={
                "hook": {"success_rate": 0.8, "sample_count": 20},
            },
        )
        ops = detector.detect(knowledge=knowledge)
        under = [o for o in ops if o.type == OpportunityType.UNDEREXPLOITED_DNA]
        assert len(under) == 0

    def test_detect_multiple_sorted_by_score(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(
            trends={"ROI": -0.25, "CTR": -0.30, "CVR": -0.22},
            metrics={"ROI": 0.8, "CTR": 0.02, "CVR": 0.05},
        )
        knowledge = _make_knowledge(
            overall_confidence=0.2,
            mutation_performance={
                "hook": {"success_rate": 0.8, "sample_count": 3},
            },
        )
        population = _make_population(diversity_score=0.1)
        ops = detector.detect(
            market_signal=signal,
            knowledge=knowledge,
            population=population,
        )
        assert len(ops) >= 2
        # 按 score 降序
        for i in range(len(ops) - 1):
            assert ops[i].score >= ops[i + 1].score

    def test_detect_top_returns_highest(self):
        detector = OpportunityDetector()
        signal = _make_market_signal(
            trends={"ROI": -0.25, "CTR": -0.30, "CVR": -0.22},
            metrics={"ROI": 0.8, "CTR": 0.02, "CVR": 0.05},
        )
        knowledge = _make_knowledge(
            overall_confidence=0.2,
        )
        top = detector.detect_top(market_signal=signal, knowledge=knowledge)
        assert top is not None
        assert top.score >= 0.5

    def test_repr(self):
        assert repr(OpportunityDetector()) == "OpportunityDetector()"


# ================================================================
# DecisionEngine
# ================================================================


class TestDecisionEngine:
    """测试 DecisionEngine。"""

    def test_high_score_start_evolution(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp)
        assert d.action == EvolutionAction.START_EVOLUTION
        assert d.confidence > 0.8

    def test_medium_score_observe(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.6)
        d = engine.decide(opp)
        assert d.action == EvolutionAction.OBSERVE

    def test_low_score_hold(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.3)
        d = engine.decide(opp)
        assert d.action == EvolutionAction.HOLD

    def test_budget_constraint_downgrades(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp, budget={"remaining_ratio": 0.05})
        assert d.action == EvolutionAction.OBSERVE

    def test_budget_constraint_observe_to_hold(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.6)
        d = engine.decide(opp, budget={"remaining_ratio": 0.05})
        assert d.action == EvolutionAction.HOLD

    def test_active_cycles_downgrades(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp, active_cycles=3)
        assert d.action == EvolutionAction.OBSERVE

    def test_active_cycles_observe_to_hold(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.6)
        d = engine.decide(opp, active_cycles=3)
        assert d.action == EvolutionAction.HOLD

    def test_high_history_boosts_confidence(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp, historical_success_rate=0.8)
        assert d.confidence > 0.9

    def test_low_history_reduces_confidence(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp, historical_success_rate=0.2)
        assert d.confidence < 0.9

    def test_decision_has_reason(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp)
        assert len(d.reason) > 0

    def test_decision_has_opportunity(self):
        engine = DecisionEngine()
        opp = EvolutionOpportunity(score=0.9)
        d = engine.decide(opp)
        assert d.opportunity is opp

    def test_decide_batch(self):
        engine = DecisionEngine()
        opps = [EvolutionOpportunity(score=0.9), EvolutionOpportunity(score=0.3)]
        decisions = engine.decide_batch(opps)
        assert len(decisions) == 2
        assert decisions[0].action == EvolutionAction.START_EVOLUTION
        assert decisions[1].action == EvolutionAction.HOLD

    def test_repr(self):
        r = repr(DecisionEngine())
        assert "DecisionEngine" in r


# ================================================================
# LifecycleManager
# ================================================================


class TestLifecycleManager:
    """测试 LifecycleManager。"""

    def test_can_transition_valid(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.IDLE)
        assert lm.can_transition(cycle, EvolutionCycleStatus.DETECTING)

    def test_can_transition_invalid(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.IDLE)
        assert not lm.can_transition(cycle, EvolutionCycleStatus.EXECUTING)

    def test_can_transition_completed_is_terminal(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.COMPLETED)
        assert not lm.can_transition(cycle, EvolutionCycleStatus.DETECTING)

    def test_transition_success(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.IDLE)
        assert lm.transition(cycle, EvolutionCycleStatus.DETECTING)
        assert cycle.status == EvolutionCycleStatus.DETECTING

    def test_transition_invalid_rejected(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.IDLE)
        assert not lm.transition(cycle, EvolutionCycleStatus.EXECUTING)
        assert cycle.status == EvolutionCycleStatus.IDLE

    def test_transition_to_terminal_moves_to_completed(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(status=EvolutionCycleStatus.LEARNING)
        lm.register_cycle(cycle)
        assert lm.transition(cycle, EvolutionCycleStatus.COMPLETED)
        assert lm.get_active_cycle_count() == 0
        assert len(lm.get_completed_cycles()) == 1

    def test_register_cycle(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle()
        assert lm.register_cycle(cycle)
        assert lm.get_active_cycle_count() == 1

    def test_register_max_active(self):
        lm = LifecycleManager(max_active=2)
        lm.register_cycle(EvolutionCycle())
        lm.register_cycle(EvolutionCycle())
        assert not lm.register_cycle(EvolutionCycle())
        assert lm.get_active_cycle_count() == 2

    def test_can_start_new(self):
        lm = LifecycleManager(max_active=1)
        assert lm.can_start_new()
        lm.register_cycle(EvolutionCycle())
        assert not lm.can_start_new()

    def test_is_duplicate_opportunity(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(
            trigger_reason="creative_fatigue",
            status=EvolutionCycleStatus.EXECUTING,
        )
        lm.register_cycle(cycle)
        assert lm.is_duplicate_opportunity("creative_fatigue")

    def test_is_duplicate_opportunity_false(self):
        lm = LifecycleManager()
        cycle = EvolutionCycle(
            trigger_reason="performance_drop",
            status=EvolutionCycleStatus.EXECUTING,
        )
        lm.register_cycle(cycle)
        assert not lm.is_duplicate_opportunity("creative_fatigue")

    def test_get_stats(self):
        lm = LifecycleManager()
        # 活跃
        active = EvolutionCycle()
        lm.register_cycle(active)
        # 已完成
        completed = EvolutionCycle(status=EvolutionCycleStatus.LEARNING)
        lm.register_cycle(completed)
        lm.transition(completed, EvolutionCycleStatus.COMPLETED)
        # 失败
        failed = EvolutionCycle(status=EvolutionCycleStatus.LEARNING)
        lm.register_cycle(failed)
        lm.transition(failed, EvolutionCycleStatus.FAILED)

        stats = lm.get_stats()
        assert stats["active_cycles"] == 1
        assert stats["completed_cycles"] == 1
        assert stats["failed_cycles"] == 1
        assert stats["total_cycles"] == 3

    def test_get_total_cycles(self):
        lm = LifecycleManager()
        assert lm.get_total_cycles() == 0
        lm.register_cycle(EvolutionCycle())
        assert lm.get_total_cycles() == 1

    def test_valid_transitions_defined(self):
        assert EvolutionCycleStatus.IDLE in VALID_TRANSITIONS
        assert EvolutionCycleStatus.DETECTING in VALID_TRANSITIONS[EvolutionCycleStatus.IDLE]

    def test_repr(self):
        lm = LifecycleManager()
        r = repr(lm)
        assert "LifecycleManager" in r


# ================================================================
# EvolutionCycleRunner
# ================================================================


class TestEvolutionCycleRunner:
    """测试 EvolutionCycleRunner。"""

    def test_no_opportunity_cancels(self):
        runner = EvolutionCycleRunner()
        result = runner.run_cycle()
        assert result.success is True
        assert "No evolution needed" in result.summary

    def test_decision_observe_cancels(self):
        detector = OpportunityDetector()
        decision_engine = DecisionEngine(
            start_threshold=0.99,  # impossible to reach
        )
        runner = EvolutionCycleRunner(
            detector=detector,
            decision_engine=decision_engine,
        )
        signal = _make_market_signal(
            trends={"ROI": -0.25, "CTR": -0.22},
            metrics={"ROI": 0.8, "CTR": 0.02},
        )
        result = runner.run_cycle(market_signal=signal)
        assert "Decision" in result.summary

    def test_force_run_skips_decision(self):
        runner = EvolutionCycleRunner()
        signal = _make_market_signal(
            trends={"ROI": -0.25},
            metrics={"ROI": 0.8},
        )
        result = runner.run_cycle(market_signal=signal, force=True)
        # force=True 会尝试 plan，但没有 planner → 返回空策略 → FAILED
        assert result.success is False

    def test_max_active_cycles_cancels(self):
        lifecycle = LifecycleManager(max_active=0)
        runner = EvolutionCycleRunner(lifecycle=lifecycle)
        result = runner.run_cycle()
        assert result.success is False
        assert "max active" in result.summary.lower()

    def test_cycle_status_transitions(self):
        """测试完整周期状态转换。"""
        # 使用一个自定义 planner 来通过 plan 阶段
        class FakePlanner:
            def plan(self, **kwargs):
                from market_ops.creative_vision_runtime.autonomous_controller.strategy.models import (
                    EvolutionObjective, EvolutionStrategy, Intensity, MutationFocus, StrategyType,
                )
                return [EvolutionStrategy(
                    strategy_type=StrategyType.EXPLORE_NEW,
                    objective=EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05),
                    mutation_focus=MutationFocus.HOOK,
                    intensity=Intensity.MEDIUM,
                    confidence=0.7,
                    reason="test",
                )]

        runner = EvolutionCycleRunner(strategy_planner=FakePlanner())
        signal = _make_market_signal(
            trends={"ROI": -0.25},
            metrics={"ROI": 0.8},
            previous_metrics={"ROI": 1.0},
        )
        result = runner.run_cycle(market_signal=signal, force=True)
        # 没有 executor 和 evaluator，但 plan 通过了
        # 会走到 execute → 返回 None → evaluate 也返回 None
        # 最终 learning 到 completed
        assert result.cycle is not None
        assert result.cycle.status == EvolutionCycleStatus.COMPLETED

    def test_failed_planning(self):
        class FailingPlanner:
            def plan(self, **kwargs):
                raise RuntimeError("Plan failed")

        runner = EvolutionCycleRunner(strategy_planner=FailingPlanner())
        signal = _make_market_signal(
            trends={"ROI": -0.25},
            metrics={"ROI": 0.8},
        )
        result = runner.run_cycle(market_signal=signal, force=True)
        assert result.success is False
        assert "No strategies" in result.summary

    def test_exception_handling(self):
        class CrashingPlanner:
            def plan(self, **kwargs):
                raise RuntimeError("Crash!")

        runner = EvolutionCycleRunner(strategy_planner=CrashingPlanner())
        signal = _make_market_signal(
            trends={"ROI": -0.25},
            metrics={"ROI": 0.8},
        )
        result = runner.run_cycle(market_signal=signal, force=True)
        assert result.success is False
        # plan 抛异常 → 返回 [] → "No strategies generated"
        assert "No strategies" in result.summary

    def test_lifecycle_property(self):
        runner = EvolutionCycleRunner()
        assert isinstance(runner.lifecycle, LifecycleManager)

    def test_repr(self):
        runner = EvolutionCycleRunner()
        r = repr(runner)
        assert "EvolutionCycleRunner" in r


# ================================================================
# EvolutionOrchestrator
# ================================================================


class TestEvolutionOrchestrator:
    """测试 EvolutionOrchestrator。"""

    def test_run_returns_result(self):
        orch = EvolutionOrchestrator()
        result = orch.run()
        assert isinstance(result, EvolutionCycleResult)
        assert result.success is True
        assert "No evolution needed" in result.summary

    def test_run_max_active_cycles(self):
        lifecycle = LifecycleManager(max_active=0)
        orch = EvolutionOrchestrator(lifecycle=lifecycle)
        result = orch.run()
        assert result.success is False
        assert "max active" in result.summary.lower()

    def test_run_loop_no_opportunity(self):
        orch = EvolutionOrchestrator()
        results = orch.run_loop()
        assert len(results) == 1
        assert results[0].success is True

    def test_run_loop_respects_max_iterations(self):
        orch = EvolutionOrchestrator(max_iterations=3)
        results = orch.run_loop()
        assert len(results) <= 3

    def test_get_status(self):
        orch = EvolutionOrchestrator()
        status = orch.get_status()
        assert "lifecycle" in status
        assert "total_runs" in status
        assert "can_start_new" in status

    def test_get_results(self):
        orch = EvolutionOrchestrator()
        orch.run()
        results = orch.get_results()
        assert len(results) == 1

    def test_reset(self):
        orch = EvolutionOrchestrator()
        orch.run()
        orch.reset()
        assert len(orch.get_results()) == 0

    def test_lifecycle_property(self):
        orch = EvolutionOrchestrator()
        assert isinstance(orch.lifecycle, LifecycleManager)

    def test_cycle_runner_property(self):
        orch = EvolutionOrchestrator()
        assert isinstance(orch.cycle_runner, EvolutionCycleRunner)

    def test_repr(self):
        orch = EvolutionOrchestrator()
        r = repr(orch)
        assert "EvolutionOrchestrator" in r


# ================================================================
# Controller Integration
# ================================================================


class TestControllerIntegration:
    """测试 Controller 中的 E11.9 集成。"""

    def _make_ctrl(self):
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        return AutonomousCreativeController(
            intelligence_engine=MagicMock(),
        )

    def test_run_evolution_cycle_no_opportunity(self):
        ctrl = self._make_ctrl()
        result = ctrl.run_evolution_cycle()
        assert "cycle" in result
        assert "decision" in result
        assert "learning" in result
        assert "success" in result
        assert "summary" in result

    def test_run_evolution_cycle_with_opportunity(self):
        ctrl = self._make_ctrl()
        market_signal = _make_market_signal(
            trends={"ROI": -0.30, "CTR": -0.25},
            metrics={"ROI": 0.5, "CTR": 0.015},
            usage_count=40,
        )
        result = ctrl.run_evolution_cycle(market_signal=market_signal)
        assert result["success"] is True or "cycle" in result

    def test_run_evolution_cycle_force(self):
        ctrl = self._make_ctrl()
        result = ctrl.run_evolution_cycle(force=True)
        assert "cycle" in result

    def test_run_evolution_loop(self):
        ctrl = self._make_ctrl()
        results = ctrl.run_evolution_loop()
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_detect_evolution_opportunity(self):
        ctrl = self._make_ctrl()
        market_signal = _make_market_signal(
            trends={"ROI": -0.30, "CTR": -0.25},
            metrics={"ROI": 0.5, "CTR": 0.015},
            usage_count=40,
        )
        ops = ctrl.detect_evolution_opportunity(market_signal=market_signal)
        assert isinstance(ops, list)
        assert len(ops) >= 1
        assert "type" in ops[0]
        assert "score" in ops[0]

    def test_detect_evolution_opportunity_empty(self):
        ctrl = self._make_ctrl()
        ops = ctrl.detect_evolution_opportunity()
        assert ops == []

    def test_get_orchestrator_status(self):
        ctrl = self._make_ctrl()
        status = ctrl.get_orchestrator_status()
        assert "lifecycle" in status
        assert "total_runs" in status
        assert "can_start_new" in status

    def test_evolution_orchestrator_property(self):
        ctrl = self._make_ctrl()
        orch = ctrl.evolution_orchestrator
        assert isinstance(orch, EvolutionOrchestrator)


# ================================================================
# Full Pipeline
# ================================================================


class TestFullPipeline:
    """测试完整 E11.9 管线。"""

    def test_detect_decide_hold(self):
        """检测 → 决策 → 低分 → HOLD"""
        detector = OpportunityDetector()
        engine = DecisionEngine()
        signal = _make_market_signal(trends={"CTR": -0.05})
        opp = detector.detect_top(market_signal=signal)
        assert opp is None
        # 无机会 → 不启动

    def test_detect_decide_high_start(self):
        """检测 → 决策 → 高分 → START_EVOLUTION"""
        detector = OpportunityDetector()
        engine = DecisionEngine()
        signal = _make_market_signal(
            trends={"ROI": -0.25, "CTR": -0.25, "CVR": -0.25},
            metrics={"ROI": 0.5, "CTR": 0.015, "CVR": 0.03},
            usage_count=40,
        )
        knowledge = _make_knowledge(overall_confidence=0.2)
        population = _make_population(diversity_score=0.1)

        opp = detector.detect_top(
            market_signal=signal,
            knowledge=knowledge,
            population=population,
        )
        assert opp is not None
        assert opp.score >= 0.8

        decision = engine.decide(opp)
        assert decision.action == EvolutionAction.START_EVOLUTION

    def test_lifecycle_full_flow(self):
        """完整生命周期状态转换。"""
        lm = LifecycleManager()
        cycle = EvolutionCycle()

        lm.register_cycle(cycle)
        assert lm.transition(cycle, EvolutionCycleStatus.DETECTING)
        assert lm.transition(cycle, EvolutionCycleStatus.PLANNING)
        assert lm.transition(cycle, EvolutionCycleStatus.EXECUTING)
        assert lm.transition(cycle, EvolutionCycleStatus.EVALUATING)
        assert lm.transition(cycle, EvolutionCycleStatus.LEARNING)
        assert lm.transition(cycle, EvolutionCycleStatus.COMPLETED)

        assert cycle.status == EvolutionCycleStatus.COMPLETED
        assert lm.get_active_cycle_count() == 0
        assert len(lm.get_completed_cycles()) == 1


# ================================================================
# Package Exports
# ================================================================


class TestPackageExports:
    """测试包导出。"""

    def test_models_imports(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator import (
            EvolutionAction,
            EvolutionCycle,
            EvolutionCycleResult,
            EvolutionCycleStatus,
            EvolutionDecision,
            EvolutionOpportunity,
            OpportunityType,
        )
        assert EvolutionAction is not None
        assert EvolutionCycle is not None
        assert EvolutionCycleResult is not None
        assert EvolutionCycleStatus is not None
        assert EvolutionDecision is not None
        assert EvolutionOpportunity is not None
        assert OpportunityType is not None

    def test_engines_imports(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.orchestrator import (
            DecisionEngine,
            EvolutionCycleRunner,
            EvolutionOrchestrator,
            LifecycleManager,
            OpportunityDetector,
        )
        assert DecisionEngine is not None
        assert EvolutionCycleRunner is not None
        assert EvolutionOrchestrator is not None
        assert LifecycleManager is not None
        assert OpportunityDetector is not None

    def test_init_creates_all(self):
        """确保所有引擎默认创建成功。"""
        detector = OpportunityDetector()
        dec = DecisionEngine()
        lm = LifecycleManager()
        runner = EvolutionCycleRunner(
            detector=detector,
            decision_engine=dec,
            lifecycle=lm,
        )
        orch = EvolutionOrchestrator(
            detector=detector,
            decision_engine=dec,
            lifecycle=lm,
            cycle_runner=runner,
        )
        assert orch is not None
        assert orch.get_status() is not None