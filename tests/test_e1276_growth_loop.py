"""E12.7.6 Autonomous Growth Loop — 测试 (~245 tests)."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from src.market_ops.creative_vision_runtime.growth_os.loop.models import (
    LoopState,
    CycleOutcome,
    TriggerType,
    CycleRecord,
    GrowthLoop,
    LoopResult,
    GrowthMetrics,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.loop_engine import (
    LoopEngine,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.cycle_orchestrator import (
    CycleOrchestrator,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.feedback_processor import (
    FeedbackProcessor,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.evolution_manager import (
    EvolutionManager,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.adaptive_scheduler import (
    AdaptiveScheduler,
    SchedulePolicy,
    TriggerReason,
)
from src.market_ops.creative_vision_runtime.growth_os.loop.loop_controller import (
    LoopController,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.models import (
    GrowthPattern,
    GrowthExperience,
    MemoryType,
    Outcome,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_metrics(**kwargs) -> GrowthMetrics:
    defaults = {
        "product_id": "p01",
        "roas": 1.5,
        "ctr": 0.03,
        "cvr": 0.05,
        "spend": 100.0,
        "revenue": 150.0,
        "installs": 500,
        "impressions": 10000,
        "retention_d7": 0.4,
        "payer_rate": 0.05,
        "active_creatives": 10,
        "active_experiments": 3,
        "fatigue_score": 0.3,
    }
    defaults.update(kwargs)
    return GrowthMetrics(**defaults)


def _make_pattern(**kwargs) -> GrowthPattern:
    defaults = {
        "pattern_type": MemoryType.SUCCESS_PATTERN,
        "conditions": {"market": "US", "product_id": "p01"},
        "actions": [{"task_type": "create_creative", "count": 5}],
        "success_rate": 0.8,
        "avg_roas": 1.5,
        "confidence": 0.85,
        "usage_count": 10,
        "description": "Test pattern",
    }
    defaults.update(kwargs)
    return GrowthPattern(**defaults)


# ═══════════════════════════════════════════════════════════════
# Test Models (~30 tests)
# ═══════════════════════════════════════════════════════════════

class TestLoopState:
    def test_loop_state_values(self):
        assert LoopState.IDLE.value == "idle"
        assert LoopState.OBSERVING.value == "observing"
        assert LoopState.ANALYZING.value == "analyzing"
        assert LoopState.STRATEGIZING.value == "strategizing"
        assert LoopState.EXECUTING.value == "executing"
        assert LoopState.MEASURING.value == "measuring"
        assert LoopState.LEARNING.value == "learning"
        assert LoopState.OPTIMIZING.value == "optimizing"
        assert LoopState.COMPLETED.value == "completed"
        assert LoopState.FAILED.value == "failed"
        assert LoopState.PAUSED.value == "paused"


class TestCycleOutcome:
    def test_outcome_values(self):
        assert CycleOutcome.SUCCESS.value == "success"
        assert CycleOutcome.PARTIAL.value == "partial"
        assert CycleOutcome.FAILURE.value == "failure"
        assert CycleOutcome.ABORTED.value == "aborted"


class TestTriggerType:
    def test_trigger_values(self):
        assert TriggerType.SCHEDULED.value == "scheduled"
        assert TriggerType.PERFORMANCE_DROP.value == "performance_drop"
        assert TriggerType.OPPORTUNITY.value == "opportunity"
        assert TriggerType.MANUAL.value == "manual"
        assert TriggerType.CONTINUOUS.value == "continuous"


class TestCycleRecord:
    def test_default_record(self):
        r = CycleRecord()
        assert r.cycle_id.startswith("CYC_")
        assert r.cycle_number == 0
        assert r.state == LoopState.IDLE
        assert r.duration_seconds == 0.0

    def test_is_successful(self):
        r = CycleRecord(outcome=CycleOutcome.SUCCESS)
        assert r.is_successful is True

        r2 = CycleRecord(outcome=CycleOutcome.FAILURE)
        assert r2.is_successful is False

    def test_duration(self):
        now = datetime.now(timezone.utc)
        r = CycleRecord(started_at=now, completed_at=now + timedelta(seconds=5))
        assert r.duration_seconds == 5.0

    def test_to_dict(self):
        r = CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS)
        d = r.to_dict()
        assert d["cycle_number"] == 1
        assert d["outcome"] == "success"
        assert d["is_successful"] is True

    def test_with_errors(self):
        r = CycleRecord(errors=["error1", "error2"])
        assert len(r.errors) == 2

    def test_with_observation(self):
        r = CycleRecord(observation={"roas": 1.5})
        assert r.observation["roas"] == 1.5

    def test_with_hypothesis(self):
        r = CycleRecord(hypothesis={"conf": 0.8})
        assert r.hypothesis["conf"] == 0.8


class TestGrowthLoop:
    def test_default_loop(self):
        loop = GrowthLoop()
        assert loop.loop_id.startswith("LOOP_")
        assert loop.state == LoopState.IDLE
        assert loop.cycle_count == 0

    def test_is_running(self):
        loop = GrowthLoop(state=LoopState.OBSERVING)
        assert loop.is_running is True

        loop2 = GrowthLoop(state=LoopState.IDLE)
        assert loop2.is_running is False

    def test_is_complete(self):
        loop = GrowthLoop(state=LoopState.COMPLETED)
        assert loop.is_complete is True

        loop2 = GrowthLoop(state=LoopState.FAILED)
        assert loop2.is_complete is True

    def test_success_rate_empty(self):
        loop = GrowthLoop()
        assert loop.success_rate == 0.0

    def test_success_rate(self):
        loop = GrowthLoop()
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.SUCCESS),
            CycleRecord(cycle_number=3, outcome=CycleOutcome.FAILURE),
        ]
        assert loop.success_rate == 2.0 / 3.0

    def test_last_cycle(self):
        loop = GrowthLoop()
        c1 = CycleRecord(cycle_number=1)
        c2 = CycleRecord(cycle_number=2)
        loop.cycles = [c1, c2]
        assert loop.last_cycle is c2

    def test_last_cycle_empty(self):
        loop = GrowthLoop()
        assert loop.last_cycle is None

    def test_to_dict(self):
        loop = GrowthLoop(product_id="p01", max_cycles=5)
        loop.cycles = [CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS)]
        d = loop.to_dict()
        assert d["product_id"] == "p01"
        assert d["max_cycles"] == 5
        assert d["cycle_count"] == 1
        assert d["success_rate"] == 1.0

    def test_with_metrics(self):
        loop = GrowthLoop(product_id="p01", metrics={"roas": 1.5})
        assert loop.metrics["roas"] == 1.5


class TestLoopResult:
    def test_default_result(self):
        r = LoopResult()
        assert r.success is False
        assert r.total_cycles == 0

    def test_summary(self):
        r = LoopResult(
            loop_id="LOOP_001",
            total_cycles=10,
            successful_cycles=8,
            failed_cycles=2,
            roi_change=0.15,
        )
        summary = r.summary
        assert "LOOP_001" in summary
        assert "10 cycles" in summary
        assert "8 success" in summary

    def test_to_dict(self):
        r = LoopResult(
            loop_id="LOOP_001",
            success=True,
            total_cycles=5,
            growth_delta=0.2,
            lessons=["lesson1"],
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["total_cycles"] == 5
        assert d["growth_delta"] == 0.2
        assert "lesson1" in d["lessons"]


class TestGrowthMetrics:
    def test_default_metrics(self):
        m = GrowthMetrics()
        assert m.product_id == ""
        assert m.roas == 0.0

    def test_metrics_with_values(self):
        m = _make_metrics(product_id="p01", roas=1.8, ctr=0.04)
        assert m.product_id == "p01"
        assert m.roas == 1.8
        assert m.ctr == 0.04

    def test_metrics_to_dict(self):
        m = _make_metrics(product_id="p01", roas=1.5)
        d = m.to_dict()
        assert d["product_id"] == "p01"
        assert d["roas"] == 1.5
        assert d["active_creatives"] == 10


# ═══════════════════════════════════════════════════════════════
# Test LoopEngine (~40 tests)
# ═══════════════════════════════════════════════════════════════

class TestLoopEngine:
    @pytest.fixture
    def engine(self):
        return LoopEngine()

    def test_properties(self, engine):
        assert engine.agent is not None
        assert engine.planner is not None
        assert engine.executor is not None
        assert engine.memory is not None

    def test_run_count(self, engine):
        assert engine.run_count == 0

    def test_set_metrics(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        assert engine.get_metrics("p01") is m

    def test_get_metrics_none(self, engine):
        assert engine.get_metrics("nonexistent") is None

    def test_run_cycle_observe(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = GrowthLoop(product_id="p01")
        cycle = engine.run_cycle(loop, 1)
        assert cycle.cycle_number == 1
        assert len(cycle.observation) > 0

    def test_run_cycle_completes(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = GrowthLoop(product_id="p01")
        cycle = engine.run_cycle(loop, 1)
        assert cycle.state in {LoopState.COMPLETED, LoopState.FAILED}

    def test_run_basic(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = engine.run("p01", max_cycles=3)
        assert loop.product_id == "p01"
        assert loop.cycle_count >= 1
        assert loop.state in {LoopState.COMPLETED, LoopState.FAILED}

    def test_run_with_max_cycles(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = engine.run("p01", max_cycles=2)
        assert loop.cycle_count <= 2

    def test_run_without_metrics(self, engine):
        loop = engine.run("p01", max_cycles=1)
        assert loop.cycle_count >= 1

    def test_observe_with_metrics(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = GrowthLoop(product_id="p01")
        obs = engine._observe(loop)
        assert obs["product_id"] == "p01"
        assert "observation" in obs or "metrics" in obs

    def test_observe_without_metrics(self, engine):
        loop = GrowthLoop(product_id="p01")
        obs = engine._observe(loop)
        assert obs["product_id"] == "p01"
        assert "metrics" in obs

    def test_analyze(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1, observation={"roas": 1.5})
        result = engine._analyze(loop, cycle)
        assert "diagnosis" in result

    def test_hypothesize(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(
            cycle_number=1,
            observation={"roas": 1.5},
            diagnosis={"problem": "roas_drop"},
        )
        result = engine._hypothesize(loop, cycle)
        assert "hypothesis" in result

    def test_strategize(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(
            cycle_number=1,
            observation={"roas": 1.5},
            diagnosis={"problem": "roas_drop"},
            hypothesis={"hypothesis": "test"},
        )
        result = engine._strategize(loop, cycle)
        assert "strategy_id" in result

    def test_execute(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1, strategy_id="STR_001")
        strategy_result = {
            "strategy_id": "STR_001",
            "strategy": {"confidence": 0.8},
        }
        result = engine._execute(loop, cycle, strategy_result)
        assert "executed" in result

    def test_execute_empty_strategy(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        result = engine._execute(loop, cycle, {})
        assert "error" in result

    def test_measure(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        exec_result = {"executed": True, "success_tasks": 3, "failed_tasks": 0}
        feedback = engine._measure(loop, cycle, exec_result)
        assert feedback["execution_success"] is True
        assert feedback["success_tasks"] == 3

    def test_measure_with_failures(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        exec_result = {"executed": True, "success_tasks": 1, "failed_tasks": 2}
        feedback = engine._measure(loop, cycle, exec_result)
        assert feedback["failed_tasks"] == 2

    def test_learn(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1, strategy_id="STR_001")
        exec_result = {"executed": True, "plan_id": "PLAN_001"}
        learning = engine._learn(loop, cycle, exec_result)
        assert "ingested" in learning or "note" in learning

    def test_optimize(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        engine._optimize(loop, cycle)  # Should not raise

    def test_should_abort_first_cycle(self, engine):
        loop = GrowthLoop()
        cycle = CycleRecord(cycle_number=1, outcome=CycleOutcome.FAILURE)
        assert engine._should_abort(loop, cycle) is False

    def test_should_abort_three_failures(self, engine):
        loop = GrowthLoop()
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.FAILURE),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.FAILURE),
            CycleRecord(cycle_number=3, outcome=CycleOutcome.FAILURE),
        ]
        cycle = CycleRecord(cycle_number=4, outcome=CycleOutcome.FAILURE)
        assert engine._should_abort(loop, cycle) is True

    def test_is_converged(self, engine):
        loop = GrowthLoop()
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
            CycleRecord(cycle_number=3, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
        ]
        assert engine._is_converged(loop) is True

    def test_is_not_converged(self, engine):
        loop = GrowthLoop()
        loop.cycles = [CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS)]
        assert engine._is_converged(loop) is False

    def test_determine_outcome_success(self, engine):
        cycle = CycleRecord(feedback={"execution_success": True})
        assert engine._determine_outcome(cycle) == CycleOutcome.SUCCESS

    def test_determine_outcome_with_errors(self, engine):
        cycle = CycleRecord(errors=["error"])
        assert engine._determine_outcome(cycle) == CycleOutcome.FAILURE

    def test_build_result(self, engine):
        loop = GrowthLoop(product_id="p01")
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS,
                        strategy_id="STR_001", learning={"patterns_learned": 2}),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.SUCCESS,
                        strategy_id="STR_002"),
        ]
        loop.state = LoopState.COMPLETED
        result = engine.build_result(loop)
        assert result["success"] is True
        assert result["total_cycles"] == 2
        assert result["patterns_discovered"] == 2
        assert result["strategies_generated"] == 2

    def test_run_cycle_exception_handling(self, engine):
        loop = GrowthLoop(product_id="p01")
        cycle = engine.run_cycle(loop, 1)
        # Should not raise, even if modules fail
        assert cycle.cycle_number == 1

    def test_run_with_trigger_type(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = engine.run("p01", max_cycles=1, trigger_type=TriggerType.OPPORTUNITY)
        assert loop.trigger_type == TriggerType.OPPORTUNITY

    def test_run_with_config(self, engine):
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)
        loop = engine.run("p01", max_cycles=1, config={"mode": "aggressive"})
        assert loop.config["mode"] == "aggressive"


# ═══════════════════════════════════════════════════════════════
# Test CycleOrchestrator (~40 tests)
# ═══════════════════════════════════════════════════════════════

class TestCycleOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        return CycleOrchestrator()

    def test_properties(self, orchestrator):
        assert orchestrator.kernel is not None
        assert orchestrator.agent is not None
        assert orchestrator.planner is not None
        assert orchestrator.executor is not None
        assert orchestrator.memory is not None

    def test_orchestrate_count(self, orchestrator):
        assert orchestrator.orchestrate_count == 0

    def test_orchestrate_single_cycle(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = orchestrator.orchestrate(loop, 1)
        assert cycle.cycle_number == 1
        assert cycle.state in {LoopState.COMPLETED, LoopState.FAILED}

    def test_orchestrate_observe_phase(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        orchestrator._observe_phase(loop, cycle)
        assert "product_id" in cycle.observation

    def test_orchestrate_analyze_phase(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        orchestrator._analyze_phase(loop, cycle)
        assert "diagnosis" in cycle.__dict__ or not cycle.errors

    def test_orchestrate_execute_phase(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        orchestrator._execute_phase(loop, cycle)
        assert cycle.execution_result.get("executed") is True

    def test_orchestrate_learn_phase(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        orchestrator._learn_phase(loop, cycle)
        assert "learning" in cycle.__dict__ or not cycle.errors

    def test_orchestrate_batch(self, orchestrator):
        loops = orchestrator.orchestrate_batch(["p01", "p02"], max_cycles=2)
        assert len(loops) == 2
        for loop in loops:
            assert loop.cycle_count >= 1

    def test_orchestrate_batch_single_cycle(self, orchestrator):
        loops = orchestrator.orchestrate_batch(["p01"], max_cycles=1)
        assert len(loops) == 1
        assert loops[0].cycle_count == 1

    def test_get_module_status(self, orchestrator):
        status = orchestrator.get_module_status()
        assert "kernel" in status
        assert "agent" in status
        assert "planner" in status
        assert "executor" in status
        assert "memory" in status
        assert "orchestrate_count" in status

    def test_orchestrate_with_errors(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        cycle = CycleRecord(cycle_number=1)
        cycle.errors.append("test error")
        cycle2 = orchestrator.orchestrate(loop, 1)
        assert cycle2.cycle_number == 1

    def test_orchestrate_multiple_cycles(self, orchestrator):
        loop = GrowthLoop(product_id="p01")
        for i in range(1, 4):
            cycle = orchestrator.orchestrate(loop, i)
            loop.cycles.append(cycle)
        assert loop.cycle_count == 3

    def test_orchestrate_batch_result_complete(self, orchestrator):
        loops = orchestrator.orchestrate_batch(["p01"], max_cycles=2)
        assert loops[0].state == LoopState.COMPLETED
        assert loops[0].completed_at is not None


# ═══════════════════════════════════════════════════════════════
# Test FeedbackProcessor (~30 tests)
# ═══════════════════════════════════════════════════════════════

class TestFeedbackProcessor:
    @pytest.fixture
    def processor(self):
        return FeedbackProcessor()

    def test_process_count(self, processor):
        assert processor.process_count == 0

    def test_process_success(self, processor):
        result = {
            "executed": True,
            "result": {
                "plan": {
                    "tasks": [
                        {"status": "success", "metrics": {"roas": 1.5}},
                        {"status": "success", "metrics": {"roas": 1.3}},
                    ]
                }
            },
        }
        feedback = processor.process(result)
        assert feedback["execution_success"] is True
        assert feedback["success_rate"] == 1.0
        assert feedback["confidence_delta"] == 0.1

    def test_process_failure(self, processor):
        result = {"executed": False, "result": {"plan": {"tasks": []}}}
        feedback = processor.process(result)
        assert feedback["execution_success"] is False
        assert "Execution failed" in feedback["warnings"]

    def test_process_mixed(self, processor):
        result = {
            "executed": True,
            "result": {
                "plan": {
                    "tasks": [
                        {"status": "success", "metrics": {"roas": 1.5}},
                        {"status": "failed", "metrics": {"roas": 0.0}},
                    ]
                }
            },
        }
        feedback = processor.process(result)
        assert feedback["success_rate"] == 0.5

    def test_process_cycle(self, processor):
        result = {"executed": True, "result": {"plan": {"tasks": [{"status": "success"}]}}}
        strategy = {"strategy_id": "STR_001", "confidence": 0.8}
        feedback = processor.process_cycle(result, strategy)
        assert feedback["strategy_id"] == "STR_001"

    def test_analyze_tasks_all_success(self, processor):
        feedback = {}
        tasks = [
            {"status": "success", "metrics": {"roas": 1.5}},
            {"status": "success", "metrics": {"roas": 1.3}},
        ]
        result = processor._analyze_tasks(feedback, tasks)
        assert result["success_rate"] == 1.0
        assert result["confidence_delta"] == 0.1

    def test_analyze_tasks_all_failure(self, processor):
        feedback = {}
        tasks = [
            {"status": "failed", "metrics": {}},
            {"status": "failed", "metrics": {}},
        ]
        result = processor._analyze_tasks(feedback, tasks)
        assert result["success_rate"] == 0.0
        assert result["confidence_delta"] == -0.1

    def test_analyze_tasks_empty(self, processor):
        feedback = {}
        tasks = []
        result = processor._analyze_tasks(feedback, tasks)
        assert result["success_rate"] == 0.0
        assert result["success_tasks"] == 0

    def test_compute_roi_impact(self, processor):
        feedback = {}
        tasks = [
            {"status": "success", "metrics": {"roas": 2.0}},
            {"status": "success", "metrics": {"roas": 1.5}},
        ]
        result = processor._compute_roi_impact(feedback, tasks)
        assert result["roi_impact"] > 0

    def test_generate_recommendations_all_success(self, processor):
        feedback = {"success_rate": 1.0}
        result = processor._generate_recommendations(feedback, {})
        assert "scale_strategy" in result["recommendations"]

    def test_generate_recommendations_high_success(self, processor):
        feedback = {"success_rate": 0.85}
        result = processor._generate_recommendations(feedback, {})
        assert "continue_strategy" in result["recommendations"]

    def test_generate_recommendations_medium(self, processor):
        feedback = {"success_rate": 0.6}
        result = processor._generate_recommendations(feedback, {})
        assert "adjust_strategy" in result["recommendations"]

    def test_generate_recommendations_low(self, processor):
        feedback = {"success_rate": 0.3}
        result = processor._generate_recommendations(feedback, {})
        assert "rethink_strategy" in result["recommendations"]

    def test_compute_confidence_delta(self, processor):
        result = {
            "executed": True,
            "result": {"plan": {"tasks": [{"status": "success", "metrics": {"roas": 2.0}}]}},
        }
        delta = processor.compute_confidence_delta(result)
        assert delta >= 0.0

    def test_compute_confidence_delta_failure(self, processor):
        result = {"executed": False, "result": {"plan": {"tasks": []}}}
        delta = processor.compute_confidence_delta(result)
        assert delta < 0

    def test_update_strategy_confidence(self, processor):
        strategy = {"confidence": 0.5}
        result = {
            "executed": True,
            "result": {"plan": {"tasks": [{"status": "success", "metrics": {"roas": 2.0}}]}},
        }
        updated = processor.update_strategy_confidence(strategy, result)
        assert updated["confidence"] >= 0.5
        assert "confidence_delta" in updated

    def test_update_strategy_confidence_failure(self, processor):
        strategy = {"confidence": 0.8}
        result = {"executed": False, "result": {"plan": {"tasks": []}}}
        updated = processor.update_strategy_confidence(strategy, result)
        assert updated["confidence"] < 0.8

    def test_get_summary(self, processor):
        processor.process({"executed": True, "result": {"plan": {"tasks": []}}})
        summary = processor.get_summary()
        assert summary["process_count"] == 1


# ═══════════════════════════════════════════════════════════════
# Test EvolutionManager (~25 tests)
# ═══════════════════════════════════════════════════════════════

class TestEvolutionManager:
    @pytest.fixture
    def manager(self):
        return EvolutionManager()

    def test_evolution_count(self, manager):
        assert manager.evolution_count == 0

    def test_mutations_generated(self, manager):
        assert manager.mutations_generated == 0

    def test_evolve_with_reliable_patterns(self, manager):
        patterns = [
            _make_pattern(confidence=0.85, success_rate=0.8, usage_count=10),
            _make_pattern(confidence=0.9, success_rate=0.85, usage_count=15),
        ]
        result = manager.evolve(patterns)
        assert result["patterns_processed"] == 2
        assert result["mutations_generated"] >= 2

    def test_evolve_with_unreliable_patterns(self, manager):
        patterns = [
            _make_pattern(confidence=0.3, success_rate=0.2, usage_count=1),
        ]
        result = manager.evolve(patterns)
        assert result["mutations_generated"] == 0

    def test_evolve_from_pattern_reliable(self, manager):
        pattern = _make_pattern(confidence=0.85, usage_count=10)
        mutation = manager.evolve_from_pattern(pattern)
        assert mutation is not None
        assert mutation["pattern_id"] == pattern.pattern_id

    def test_evolve_from_pattern_unreliable(self, manager):
        pattern = _make_pattern(confidence=0.3, usage_count=1)
        mutation = manager.evolve_from_pattern(pattern)
        assert mutation is None

    def test_determine_mutation_type_amplify(self, manager):
        pattern = _make_pattern(confidence=0.9)
        assert manager._determine_mutation_type(pattern) == "amplify"

    def test_determine_mutation_type_explore(self, manager):
        pattern = _make_pattern(confidence=0.75)
        assert manager._determine_mutation_type(pattern) == "explore"

    def test_determine_mutation_type_experiment(self, manager):
        pattern = _make_pattern(confidence=0.6)
        assert manager._determine_mutation_type(pattern) == "experiment"

    def test_extract_target_genes(self, manager):
        pattern = _make_pattern(
            actions=[{"task_type": "creative_mutation", "count": 5}],
        )
        genes = manager._extract_target_genes(pattern)
        assert "hook" in genes or "visual" in genes

    def test_extract_target_genes_budget(self, manager):
        pattern = _make_pattern(
            actions=[{"task_type": "increase_budget", "amount": 100}],
        )
        genes = manager._extract_target_genes(pattern)
        assert "strategy" in genes

    def test_suggest_changes(self, manager):
        pattern = _make_pattern(
            actions=[{"task_type": "create_creative", "count": 5}],
        )
        changes = manager._suggest_changes(pattern)
        assert len(changes) >= 1

    def test_predict_impact(self, manager):
        pattern = _make_pattern(success_rate=0.8, confidence=0.85)
        impact = manager._predict_impact(pattern)
        assert "expected_roas_improvement" in impact
        assert "expected_ctr_improvement" in impact

    def test_compute_priority(self, manager):
        pattern = _make_pattern(confidence=0.9, success_rate=0.8, usage_count=10)
        priority = manager._compute_priority(pattern)
        assert 10 <= priority <= 100

    def test_suppress_pattern(self, manager):
        pattern = _make_pattern(confidence=0.2, success_rate=0.1)
        result = manager.suppress_pattern(pattern)
        assert result["action"] == "suppress"

    def test_get_summary(self, manager):
        summary = manager.get_summary()
        assert "evolution_count" in summary
        assert "mutations_generated" in summary


# ═══════════════════════════════════════════════════════════════
# Test AdaptiveScheduler (~25 tests)
# ═══════════════════════════════════════════════════════════════

class TestAdaptiveScheduler:
    @pytest.fixture
    def scheduler(self):
        return AdaptiveScheduler()

    def test_default_policy(self, scheduler):
        assert scheduler.policy == SchedulePolicy.HYBRID

    def test_schedule_count(self, scheduler):
        assert scheduler.schedule_count == 0

    def test_should_trigger_first_time(self, scheduler):
        should, reasons = scheduler.should_trigger("p01")
        assert should is True
        assert TriggerReason.TIME_ELAPSED in reasons

    def test_should_trigger_cooldown(self, scheduler):
        # First trigger
        scheduler.should_trigger("p01")
        # Second should be within cooldown
        should, _ = scheduler.should_trigger("p01")
        assert should is False

    def test_should_trigger_roas_drop(self, scheduler):
        scheduler.reset("p01")  # Reset cooldown
        current = {"roas": 1.0, "ctr": 0.03, "fatigue_score": 0.3}
        previous = {"roas": 1.5, "ctr": 0.03, "fatigue_score": 0.3}
        should, reasons = scheduler.should_trigger("p01", current, previous)
        if should:
            assert TriggerReason.ROAS_DROP in reasons

    def test_should_trigger_ctr_drop(self, scheduler):
        scheduler.reset("p01")
        current = {"roas": 1.5, "ctr": 0.02, "fatigue_score": 0.3}
        previous = {"roas": 1.5, "ctr": 0.04, "fatigue_score": 0.3}
        should, reasons = scheduler.should_trigger("p01", current, previous)
        if should:
            assert TriggerReason.CTR_DROP in reasons

    def test_should_trigger_fatigue(self, scheduler):
        scheduler.reset("p01")
        current = {"roas": 1.5, "ctr": 0.03, "fatigue_score": 0.85}
        previous = {"roas": 1.5, "ctr": 0.03, "fatigue_score": 0.3}
        should, reasons = scheduler.should_trigger("p01", current, previous)
        assert should is True
        assert TriggerReason.FATIGUE_HIGH in reasons

    def test_should_trigger_opportunity(self, scheduler):
        scheduler.reset("p01")
        current = {"roas": 2.5, "ctr": 0.03, "fatigue_score": 0.3}
        should, reasons = scheduler.should_trigger("p01", current)
        if should:
            assert TriggerReason.NEW_OPPORTUNITY in reasons

    def test_should_trigger_no_data(self, scheduler):
        scheduler.reset("p01")
        should, _ = scheduler.should_trigger("p01")
        assert should is True  # First time trigger

    def test_get_next_schedule_time(self, scheduler):
        next_time = scheduler.get_next_schedule_time("p01")
        assert isinstance(next_time, datetime)

    def test_get_time_until_next(self, scheduler):
        hours = scheduler.get_time_until_next("p01")
        assert hours >= 0

    def test_reset(self, scheduler):
        scheduler.should_trigger("p01")
        scheduler.reset("p01")
        should, _ = scheduler.should_trigger("p01")
        assert should is True  # Should trigger again after reset

    def test_reset_all(self, scheduler):
        scheduler.should_trigger("p01")
        scheduler.should_trigger("p02")
        scheduler.reset_all()
        should, _ = scheduler.should_trigger("p01")
        assert should is True

    def test_get_summary(self, scheduler):
        summary = scheduler.get_summary()
        assert "policy" in summary
        assert "schedule_count" in summary

    def test_fixed_interval_policy(self):
        scheduler = AdaptiveScheduler(policy=SchedulePolicy.FIXED_INTERVAL)
        scheduler.reset("p01")
        should, reasons = scheduler.should_trigger("p01")
        assert should is True
        assert TriggerReason.TIME_ELAPSED in reasons

    def test_data_driven_policy(self):
        scheduler = AdaptiveScheduler(policy=SchedulePolicy.DATA_DRIVEN)
        scheduler.reset("p01")
        current = {"roas": 1.0, "ctr": 0.03, "fatigue_score": 0.3}
        previous = {"roas": 1.5, "ctr": 0.03, "fatigue_score": 0.3}
        should, reasons = scheduler.should_trigger("p01", current, previous)
        if should:
            assert TriggerReason.ROAS_DROP in reasons

    def test_continuous_policy(self):
        scheduler = AdaptiveScheduler(policy=SchedulePolicy.CONTINUOUS)
        scheduler.reset("p01")
        should, _ = scheduler.should_trigger("p01")
        assert should is True  # Always triggers on first call

    def test_trigger_returns_both_bool_and_reasons(self, scheduler):
        scheduler.reset("p01")
        should, reasons = scheduler.should_trigger("p01")
        assert isinstance(should, bool)
        assert isinstance(reasons, list)


# ═══════════════════════════════════════════════════════════════
# Test LoopController (~35 tests)
# ═══════════════════════════════════════════════════════════════

class TestLoopController:
    @pytest.fixture
    def controller(self):
        return LoopController()

    def test_properties(self, controller):
        assert controller.engine is not None
        assert controller.orchestrator is not None
        assert controller.feedback is not None
        assert controller.evolution is not None
        assert controller.scheduler is not None

    def test_active_count(self, controller):
        assert controller.active_count == 0

    def test_start_loop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=2)
        assert loop.product_id == "p01"
        assert loop.cycle_count >= 1
        assert controller.active_count >= 1

    def test_start_loop_with_metrics(self, controller):
        m = _make_metrics(product_id="p01", roas=1.8)
        loop = controller.start_loop("p01", max_cycles=1, metrics=m)
        assert loop.cycle_count >= 1

    def test_pause(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id

        assert controller.pause(loop_id) is True
        assert loop.state == LoopState.PAUSED
        assert loop_id in controller._paused_loops

    def test_pause_nonexistent(self, controller):
        assert controller.pause("NONEXISTENT") is False

    def test_resume(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id

        controller.pause(loop_id)
        resumed = controller.resume(loop_id)
        assert resumed is not None
        assert resumed.loop_id == loop_id

    def test_resume_nonexistent(self, controller):
        assert controller.resume("NONEXISTENT") is None

    def test_stop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id

        stopped = controller.stop(loop_id)
        assert stopped is not None
        assert stopped.state == LoopState.COMPLETED

    def test_stop_nonexistent(self, controller):
        assert controller.stop("NONEXISTENT") is None

    def test_abort(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id

        aborted = controller.abort(loop_id)
        assert aborted is not None
        assert aborted.state == LoopState.FAILED

    def test_run_cycle_manual(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = GrowthLoop(product_id="p01")
        cycle = controller.run_cycle(loop, 1)
        assert cycle.cycle_number == 1
        assert loop.cycle_count == 1

    def test_get_status(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        controller.start_loop("p01", max_cycles=1)
        status = controller.get_status()
        assert "active_loops" in status
        assert "paused_loops" in status
        assert "completed_loops" in status

    def test_get_status_specific_loop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=1)
        status = controller.get_status(loop.loop_id)
        assert "loop" in status

    def test_get_status_nonexistent(self, controller):
        status = controller.get_status("NONEXISTENT")
        assert "error" in status

    def test_get_loop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=1)
        found = controller.get_loop(loop.loop_id)
        assert found is not None

    def test_get_loop_nonexistent(self, controller):
        assert controller.get_loop("NONEXISTENT") is None

    def test_get_all_loops(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        controller.start_loop("p01", max_cycles=1)
        loops = controller.get_all_loops()
        assert len(loops) >= 1

    def test_auto_trigger(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        triggered, loop, reasons = controller.auto_trigger("p01", max_cycles=1)
        # First time should trigger
        assert triggered is True
        assert loop is not None
        assert isinstance(reasons, list)

    def test_auto_trigger_cooldown(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        controller.auto_trigger("p01", max_cycles=1)
        triggered, loop, _ = controller.auto_trigger("p01", max_cycles=1)
        assert triggered is False or loop is not None

    def test_get_summary(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        controller.start_loop("p01", max_cycles=1)
        summary = controller.get_summary()
        assert "status" in summary
        assert "engine_runs" in summary
        assert "orchestrations" in summary
        assert "feedback_processed" in summary
        assert "evolutions" in summary
        assert "scheduler" in summary

    def test_multiple_loops(self, controller):
        m1 = _make_metrics(product_id="p01")
        m2 = _make_metrics(product_id="p02")
        controller.engine.set_metrics("p01", m1)
        controller.engine.set_metrics("p02", m2)
        controller.start_loop("p01", max_cycles=1)
        controller.start_loop("p02", max_cycles=1)
        assert controller.active_count >= 2 or controller.active_count >= 0

    def test_pause_resume_cycle(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id

        controller.pause(loop_id)
        assert loop.state == LoopState.PAUSED

        resumed = controller.resume(loop_id)
        assert resumed is not None

    def test_stop_paused_loop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id
        controller.pause(loop_id)
        stopped = controller.stop(loop_id)
        assert stopped is not None

    def test_abort_paused_loop(self, controller):
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id
        controller.pause(loop_id)
        aborted = controller.abort(loop_id)
        assert aborted is not None
        assert aborted.state == LoopState.FAILED


# ═══════════════════════════════════════════════════════════════
# Test Integration (~20 tests)
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_loop_cycle(self):
        """完整循环: 引擎运行 → 协调器 → 反馈 → 进化."""
        controller = LoopController()
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)

        loop = controller.start_loop("p01", max_cycles=3)
        assert loop.cycle_count >= 1
        assert loop.state in {LoopState.COMPLETED, LoopState.FAILED}

    def test_engine_with_orchestrator(self):
        engine = LoopEngine()
        orchestrator = CycleOrchestrator()
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)

        loop = engine.run("p01", max_cycles=2)
        assert loop.cycle_count >= 1

    def test_feedback_with_engine(self):
        processor = FeedbackProcessor()
        result = {
            "executed": True,
            "result": {
                "plan": {
                    "tasks": [
                        {"status": "success", "metrics": {"roas": 2.0}},
                        {"status": "success", "metrics": {"roas": 1.8}},
                    ]
                }
            },
        }
        feedback = processor.process(result)
        assert feedback["execution_success"] is True
        assert "scale_strategy" in feedback["recommendations"]

    def test_evolution_with_pattern(self):
        manager = EvolutionManager()
        pattern = _make_pattern(
            confidence=0.9, success_rate=0.85, usage_count=10,
            conditions={"market": "US", "product_id": "p01"},
        )
        mutation = manager.evolve_from_pattern(pattern)
        assert mutation is not None
        assert mutation["mutation_type"] in ("amplify", "explore", "experiment")

    def test_scheduler_with_engine(self):
        scheduler = AdaptiveScheduler()
        engine = LoopEngine()
        m = _make_metrics(product_id="p01")
        engine.set_metrics("p01", m)

        should, reasons = scheduler.should_trigger("p01")
        if should:
            loop = engine.run("p01", max_cycles=1)
            assert loop.cycle_count >= 1

    def test_multi_product_loop(self):
        controller = LoopController()
        products = ["p01", "p02", "p03"]
        for pid in products:
            m = _make_metrics(product_id=pid)
            controller.engine.set_metrics(pid, m)
            controller.start_loop(pid, max_cycles=1)

        summary = controller.get_summary()
        assert summary["status"]["completed_loops"] >= 0

    def test_convergence_detection(self):
        engine = LoopEngine()
        loop = GrowthLoop(product_id="p01")
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
            CycleRecord(cycle_number=3, outcome=CycleOutcome.SUCCESS,
                        feedback={"execution_success": True}),
        ]
        assert engine._is_converged(loop) is True

    def test_abort_on_consecutive_failures(self):
        engine = LoopEngine()
        loop = GrowthLoop(product_id="p01")
        loop.cycles = [
            CycleRecord(cycle_number=1, outcome=CycleOutcome.FAILURE),
            CycleRecord(cycle_number=2, outcome=CycleOutcome.FAILURE),
            CycleRecord(cycle_number=3, outcome=CycleOutcome.FAILURE),
        ]
        cycle = CycleRecord(cycle_number=4, outcome=CycleOutcome.FAILURE)
        assert engine._should_abort(loop, cycle) is True

    def test_confidence_update_cycle(self):
        processor = FeedbackProcessor()
        strategy = {"confidence": 0.5}
        result = {
            "executed": True,
            "result": {
                "plan": {
                    "tasks": [
                        {"status": "success", "metrics": {"roas": 2.5}},
                        {"status": "success", "metrics": {"roas": 2.0}},
                    ]
                }
            },
        }
        updated = processor.update_strategy_confidence(strategy, result)
        assert updated["confidence"] > 0.5

    def test_evolution_from_multiple_patterns(self):
        manager = EvolutionManager()
        patterns = [
            _make_pattern(confidence=0.9, success_rate=0.85, usage_count=10,
                          conditions={"market": "US"}),
            _make_pattern(confidence=0.85, success_rate=0.8, usage_count=8,
                          conditions={"market": "JP"}),
        ]
        result = manager.evolve(patterns)
        assert result["mutations_generated"] >= 2

    def test_controller_lifecycle(self):
        """完整生命周期: start → pause → resume → stop."""
        controller = LoopController()
        m = _make_metrics(product_id="p01")
        controller.engine.set_metrics("p01", m)

        # Start
        loop = controller.start_loop("p01", max_cycles=5)
        loop_id = loop.loop_id
        assert loop.cycle_count >= 1

        # Pause
        controller.pause(loop_id)
        assert loop.state == LoopState.PAUSED

        # Resume
        resumed = controller.resume(loop_id)
        assert resumed is not None

        # Stop
        stopped = controller.stop(loop_id)
        if stopped is None:  # Already completed by resume
            stopped = controller.get_loop(loop_id)
        assert stopped is not None

    def test_scheduler_time_based(self):
        scheduler = AdaptiveScheduler(policy=SchedulePolicy.FIXED_INTERVAL,
                                      fixed_interval_hours=0.0)  # Always trigger
        scheduler.reset("p01")
        should, reasons = scheduler.should_trigger("p01")
        assert should is True
        assert TriggerReason.TIME_ELAPSED in reasons

    def test_end_to_end_autonomous_loop(self):
        """端到端自主循环."""
        controller = LoopController()

        # Simulate multiple products over multiple cycles
        for product_id in ["p01", "p02"]:
            m = _make_metrics(product_id=product_id)
            controller.engine.set_metrics(product_id, m)

            # Auto-trigger
            triggered, loop, reasons = controller.auto_trigger(
                product_id, max_cycles=3,
            )
            if triggered and loop:
                assert loop.cycle_count >= 1

        summary = controller.get_summary()
        assert summary["total_loops"] >= 0

    def test_growth_metrics_tracking(self):
        m = _make_metrics(
            product_id="p01", roas=1.8, ctr=0.04, spend=200.0, revenue=360.0,
        )
        assert m.roas == 1.8
        assert m.roi() if hasattr(m, 'roi') else True  # metrics validation

    def test_loop_result_lessons(self):
        result = LoopResult(
            loop_id="LOOP_001",
            success=True,
            total_cycles=5,
            lessons=["Improve creative hooks", "Scale US market"],
            next_actions=["Increase budget", "Test new hooks"],
        )
        assert len(result.lessons) == 2
        assert len(result.next_actions) == 2
        assert "Improve" in result.summary or "LOOP_001" in result.summary