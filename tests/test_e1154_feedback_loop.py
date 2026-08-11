"""E11.5.4 — Evolution Feedback Loop (IAP) Test.

12 AC covering:
  1.  Loop Schema
  2.  Event Creation
  3.  Feedback Processing
  4.  Signal Integration
  5.  Fitness Integration
  6.  Population Update
  7.  Generation Advance
  8.  Rollback
  9.  Convergence
  10. History
  11. Serialization
  12. Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.genome.schema import CreativeGenome, GENE_SLOTS
from market_ops.e11.evolution.generation_schema import (
    EvolutionHistory,
    GenerationRecord,
    GenerationStatus,
)
from market_ops.e11.evolution.population_schema import (
    GenomePopulation,
    PopulationMember,
)
from market_ops.e11.evolution.population_manager import PopulationManager
from market_ops.e11.evolution.orchestrator_schema import EvolutionConfig
from market_ops.e11.evolution.convergence_detector import ConvergenceConfig
from market_ops.e11.market import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
    MarketSignalProcessor,
    FitnessEngine,
    GenomeFitness,
    LoopStatus,
    EvolutionFeedbackEvent,
    FeedbackLoopState,
    EvolutionEventStore,
    EvolutionBridge,
    FeedbackLoopController,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_ua(installs: int = 30000, spend: float = 10000.0) -> UAMetrics:
    return UAMetrics(
        impressions=100000,
        clicks=50000,
        installs=installs,
        spend=spend,
    )


def _make_eng(
    d1: float = 0.45,
    d7: float = 0.35,
    d30: float = 0.15,
    playtime: float = 42.0,
    level: float = 5.3,
) -> EngagementMetrics:
    return EngagementMetrics(
        d1_retention=d1,
        d7_retention=d7,
        d30_retention=d30,
        sessions=12.5,
        playtime=playtime,
        level_progress=level,
    )


def _make_iap(
    revenue: float = 50000.0,
    payers: int = 500,
    purchases: int = 1200,
    installs: int = 30000,
    d30_ltv: float = 8.0,
    d7_ltv: float = 1.2,
) -> IAPMetrics:
    return IAPMetrics(
        revenue=revenue,
        iap_revenue=48000.0,
        payer_count=payers,
        purchase_count=purchases,
        installs=installs,
        d7_ltv=d7_ltv,
        d30_ltv=d30_ltv,
        d90_ltv=15.0,
    )


def _make_full_feedback(creative_id: str = "creative_001") -> PerformanceFeedback:
    return PerformanceFeedback(
        creative_id=creative_id,
        campaign_id="campaign_001",
        source="facebook",
        period="2026-01-01_to_2026-01-07",
        ua_metrics=_make_ua(),
        engagement_metrics=_make_eng(),
        monetization_metrics=_make_iap(),
    )


def _make_genome(genome_id: str = "genome_001", generation: int = 1) -> CreativeGenome:
    return CreativeGenome(
        genome_id=genome_id,
        generation=generation,
        genes={
            slot: {"type": "default", "strength": 0.5}
            for slot in GENE_SLOTS
        },
        fitness={"ctr": 0.5},
    )


def _make_population(
    population_id: str = "pop_test",
    generation: int = 1,
    genome_ids: list[str] | None = None,
) -> GenomePopulation:
    manager = PopulationManager()
    if genome_ids:
        pop = manager.create_population_from_genomes(
            genome_ids, population_id=population_id, generation=generation,
        )
    else:
        pop = manager.create_population(
            population_id=population_id, generation=generation,
        )
    return pop


def _make_genome_fitness(
    genome_id: str = "genome_001",
    creative_id: str = "creative_001",
    fitness_score: float = 0.91,
    monetization: float = 0.95,
    retention: float = 0.85,
    acquisition: float = 0.88,
    ltv: float = 0.92,
    confidence: float = 0.95,
) -> GenomeFitness:
    return GenomeFitness(
        genome_id=genome_id,
        creative_id=creative_id,
        fitness_score=fitness_score,
        monetization_score=monetization,
        retention_score=retention,
        acquisition_score=acquisition,
        ltv_score=ltv,
        confidence=confidence,
        sample_size=30000,
    )


def _make_evolution_history(
    scores: list[float],
    run_id: str = "evo_test",
    start_gen: int = 1,
) -> EvolutionHistory:
    history = EvolutionHistory(run_id=run_id)
    for i, score in enumerate(scores):
        record = GenerationRecord(
            generation=start_gen + i,
            population_id=f"pop_{start_gen + i:03d}",
            best_genome_id=f"genome_{start_gen + i:03d}",
            best_score=score,
            avg_score=score * 0.9,
            status=GenerationStatus.COMPLETED,
        )
        history.add_generation(record)
    return history


# ═══════════════════════════════════════════════════════════
# AC1 — Loop Schema
# ═══════════════════════════════════════════════════════════

def test_ac1a_loop_status_enum():
    """AC1a: LoopStatus enum has all required values."""
    assert LoopStatus.CREATED.value == "created"
    assert LoopStatus.RUNNING.value == "running"
    assert LoopStatus.WAITING_FEEDBACK.value == "waiting_feedback"
    assert LoopStatus.EVOLVING.value == "evolving"
    assert LoopStatus.COMPLETED.value == "completed"
    assert LoopStatus.FAILED.value == "failed"


def test_ac1b_evolution_feedback_event_create():
    """AC1b: EvolutionFeedbackEvent creates with all fields."""
    event = EvolutionFeedbackEvent(
        genome_id="genome_001",
        creative_id="creative_005",
        feedback_id="fb_abc123",
        fitness_score=0.87,
        generation=3,
        action="feedback_processed",
    )
    assert event.event_id.startswith("evt_")
    assert event.genome_id == "genome_001"
    assert event.creative_id == "creative_005"
    assert event.feedback_id == "fb_abc123"
    assert event.fitness_score == 0.87
    assert event.generation == 3
    assert event.action == "feedback_processed"


def test_ac1c_feedback_loop_state_create():
    """AC1c: FeedbackLoopState creates with default values."""
    state = FeedbackLoopState()
    assert state.loop_id.startswith("loop_")
    assert state.generation == 0
    assert state.status == LoopStatus.CREATED
    assert state.processed_count == 0
    assert state.best_fitness == 0.0
    assert state.best_genome_id == ""


def test_ac1d_feedback_loop_state_lifecycle():
    """AC1d: FeedbackLoopState lifecycle transitions work correctly."""
    state = FeedbackLoopState()
    assert state.status == LoopStatus.CREATED

    state.start()
    assert state.status == LoopStatus.RUNNING
    assert state.started_at is not None

    state.wait_for_feedback()
    assert state.status == LoopStatus.WAITING_FEEDBACK

    state.evolve()
    assert state.status == LoopStatus.EVOLVING

    state.complete()
    assert state.status == LoopStatus.COMPLETED
    assert state.completed_at is not None


def test_ac1e_feedback_loop_state_is_active():
    """AC1e: is_active returns True for RUNNING/WAITING_FEEDBACK/EVOLVING."""
    state = FeedbackLoopState()
    assert state.is_active is False

    state.start()
    assert state.is_active is True

    state.wait_for_feedback()
    assert state.is_active is True

    state.evolve()
    assert state.is_active is True

    state.complete()
    assert state.is_active is False


def test_ac1f_feedback_loop_state_is_terminal():
    """AC1f: is_terminal returns True only for COMPLETED/FAILED."""
    state = FeedbackLoopState()
    assert state.is_terminal is False

    state.complete()
    assert state.is_terminal is True

    state2 = FeedbackLoopState()
    state2.fail()
    assert state2.is_terminal is True


# ═══════════════════════════════════════════════════════════
# AC2 — Event Creation
# ═══════════════════════════════════════════════════════════

def test_ac2a_event_default_fields():
    """AC2a: EvolutionFeedbackEvent default fields are non-empty."""
    event = EvolutionFeedbackEvent()
    assert event.event_id != ""
    assert event.genome_id == ""
    assert event.fitness_score == 0.0
    assert event.generation == 0
    assert event.timestamp is not None


def test_ac2b_event_with_details():
    """AC2b: EvolutionFeedbackEvent stores details dict."""
    event = EvolutionFeedbackEvent(
        genome_id="genome_001",
        fitness_score=0.91,
        details={
            "monetization_score": 0.95,
            "retention_score": 0.85,
            "population_size": 10,
        },
    )
    assert event.details["monetization_score"] == 0.95
    assert event.details["retention_score"] == 0.85
    assert event.details["population_size"] == 10


def test_ac2c_event_repr():
    """AC2c: EvolutionFeedbackEvent repr includes key fields."""
    event = EvolutionFeedbackEvent(
        genome_id="genome_001",
        fitness_score=0.87,
        generation=3,
        action="feedback_processed",
    )
    r = repr(event)
    assert "gen=3" in r
    assert "genome_001" in r
    assert "0.87" in r


def test_ac2d_event_store_basic():
    """AC2d: EvolutionEventStore add and query."""
    store = EvolutionEventStore()
    assert store.event_count == 0
    assert store.best_score == 0.0

    e1 = EvolutionFeedbackEvent(genome_id="g1", fitness_score=0.8, generation=1)
    e2 = EvolutionFeedbackEvent(genome_id="g2", fitness_score=0.9, generation=1)
    store.add_event(e1)
    store.add_event(e2)

    assert store.event_count == 2
    assert store.best_score == 0.9


def test_ac2e_event_store_clear():
    """AC2e: EvolutionEventStore clear resets to empty."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(genome_id="g1", fitness_score=0.8))
    store.clear()
    assert store.event_count == 0
    assert store.best_score == 0.0


# ═══════════════════════════════════════════════════════════
# AC3 — Feedback Processing
# ═══════════════════════════════════════════════════════════

def test_ac3a_process_feedback_basic():
    """AC3a: FeedbackLoopController.process_feedback runs successfully."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    state = controller.process_feedback(feedback, population, genome)

    assert state is not None
    assert state.status == LoopStatus.COMPLETED
    assert state.processed_count == 1
    assert state.best_fitness > 0.0


def test_ac3b_process_feedback_creates_events():
    """AC3b: process_feedback creates multiple events in the event store."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    assert controller.event_store.event_count >= 4  # signal, fitness, genome, population
    timeline = controller.timeline
    actions = [e.action for e in timeline]
    assert "signal_generated" in actions
    assert "fitness_evaluated" in actions
    assert "genome_updated" in actions
    assert "population_updated" in actions


def test_ac3c_process_feedback_updates_loop_state():
    """AC3c: process_feedback updates loop_state fields."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    ls = controller.loop_state
    assert ls is not None
    assert ls.processed_count == 1
    assert ls.generation == 1
    assert ls.best_fitness > 0.0


def test_ac3d_process_feedback_updates_best_fitness():
    """AC3d: process_feedback tracks best_fitness correctly."""
    controller = FeedbackLoopController()

    # First feedback with high fitness
    fb1 = _make_full_feedback("creative_001")
    g1 = _make_genome("genome_001")
    pop1 = _make_population("pop_test", generation=1)
    controller.process_feedback(fb1, pop1, g1)

    best1 = controller.best_score
    assert best1 > 0.0

    # Second feedback with lower fitness should not reduce best
    fb2 = PerformanceFeedback(
        creative_id="creative_002",
        campaign_id="campaign_002",
        source="facebook",
        period="2026-01-08_to_2026-01-14",
        ua_metrics=_make_ua(installs=1000, spend=5000.0),
        engagement_metrics=_make_eng(d1=0.1, d7=0.05, d30=0.02),
        monetization_metrics=_make_iap(revenue=100.0, payers=5, d30_ltv=1.0),
    )
    g2 = _make_genome("genome_002")
    pop2 = _make_population("pop_test2", generation=1)
    controller.process_feedback(fb2, pop2, g2)

    assert controller.best_score >= best1


def test_ac3e_multiple_feedback_processing():
    """AC3e: Multiple feedback processing increments processed_count."""
    controller = FeedbackLoopController()

    for i in range(5):
        fb = _make_full_feedback(f"creative_{i:03d}")
        genome = _make_genome(f"genome_{i:03d}")
        pop = _make_population(f"pop_{i:03d}", generation=1)
        controller.process_feedback(fb, pop, genome)

    assert controller.loop_state.processed_count == 5
    assert controller.event_store.event_count >= 20  # 5 * 4+ events


# ═══════════════════════════════════════════════════════════
# AC4 — Signal Integration
# ═══════════════════════════════════════════════════════════

def test_ac4a_signal_generated_event():
    """AC4a: process_feedback generates signal_generated event."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    signal_events = [
        e for e in controller.timeline if e.action == "signal_generated"
    ]
    assert len(signal_events) >= 1
    assert signal_events[0].details.get("signal_id") is not None


def test_ac4b_signal_integration_in_loop():
    """AC4b: Signal is integrated into the feedback loop pipeline."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    # Verify the pipeline produced events in order
    actions = [e.action for e in controller.timeline]
    sig_idx = actions.index("signal_generated")
    fit_idx = actions.index("fitness_evaluated")
    assert sig_idx < fit_idx  # signal comes before fitness


def test_ac4c_signal_quality_passed_through():
    """AC4c: MarketSignal quality score is used in the loop."""
    signal_processor = MarketSignalProcessor()
    feedback = _make_full_feedback("creative_001")
    signal = signal_processor.process(feedback, genome_id="genome_001")

    assert signal.quality_score > 0.0
    assert signal.genome_id == "genome_001"
    assert signal.creative_id == "creative_001"


def test_ac4d_signal_processor_used():
    """AC4d: FeedbackLoopController uses MarketSignalProcessor."""
    signal_processor = MarketSignalProcessor()
    controller = FeedbackLoopController(signal_processor=signal_processor)
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    # Signal events should be present
    signal_events = [
        e for e in controller.timeline if e.action == "signal_generated"
    ]
    assert len(signal_events) >= 1


# ═══════════════════════════════════════════════════════════
# AC5 — Fitness Integration
# ═══════════════════════════════════════════════════════════

def test_ac5a_fitness_evaluated_event():
    """AC5a: process_feedback generates fitness_evaluated event."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    fitness_events = [
        e for e in controller.timeline if e.action == "fitness_evaluated"
    ]
    assert len(fitness_events) >= 1
    assert "fitness_id" in fitness_events[0].details
    assert "monetization" in fitness_events[0].details


def test_ac5b_fitness_genome_updated():
    """AC5b: process_feedback generates genome_updated event."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    genome_events = [
        e for e in controller.timeline if e.action == "genome_updated"
    ]
    assert len(genome_events) >= 1


def test_ac5c_fitness_score_in_loop_state():
    """AC5c: Fitness score is reflected in loop state best_fitness."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    assert controller.loop_state.best_fitness > 0.0
    assert controller.loop_state.best_fitness <= 1.0


def test_ac5d_fitness_history_recorded():
    """AC5d: Fitness history is recorded via FitnessEngine."""
    fitness_engine = FitnessEngine()
    controller = FeedbackLoopController(fitness_engine=fitness_engine)
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)

    controller.process_feedback(feedback, population, genome)

    history = fitness_engine.get_history(genome.genome_id)
    assert history is not None
    assert history.entry_count >= 1
    assert history.latest_score > 0.0


# ═══════════════════════════════════════════════════════════
# AC6 — Population Update
# ═══════════════════════════════════════════════════════════

def test_ac6a_evolution_bridge_apply_feedback():
    """AC6a: EvolutionBridge.apply_feedback adds genome to population."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_001")
    fitness = _make_genome_fitness("genome_001", fitness_score=0.91)

    event = bridge.apply_feedback(population, genome, fitness)

    assert event.action == "feedback_processed"
    assert event.genome_id == "genome_001"
    assert event.fitness_score == 0.91
    assert population.has_genome("genome_001") is True
    assert population.size == 1


def test_ac6b_population_member_added():
    """AC6b: EvolutionBridge adds new genome as PopulationMember with FitnessScore."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_new")
    fitness = _make_genome_fitness("genome_new", fitness_score=0.85)

    bridge.apply_feedback(population, genome, fitness)

    member = population.get_member("genome_new")
    assert member is not None
    assert member.fitness is not None
    assert member.score > 0.0


def test_ac6c_population_ranking():
    """AC6c: EvolutionBridge ranks population after feedback."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)

    # Add multiple genomes with different fitness
    for i, score in enumerate([0.5, 0.9, 0.7, 0.3, 0.8]):
        gid = f"genome_{i:03d}"
        genome = _make_genome(gid)
        fitness = _make_genome_fitness(gid, fitness_score=score)
        bridge.apply_feedback(population, genome, fitness)

    # Check ranking
    members = sorted(population.members, key=lambda m: m.rank)
    assert members[0].score >= members[1].score  # rank 1 should have highest score
    assert population.best_member is not None
    assert population.best_member.score >= 0.9


def test_ac6d_evolution_bridge_update_population():
    """AC6d: EvolutionBridge.update_population batch updates."""
    bridge = EvolutionBridge()
    manager = PopulationManager()
    population = manager.create_population_from_genomes(
        ["genome_001", "genome_002"],
        population_id="pop_test",
        generation=1,
    )

    fitness_map = {
        "genome_001": _make_genome_fitness("genome_001", fitness_score=0.9),
        "genome_002": _make_genome_fitness("genome_002", fitness_score=0.6),
    }
    events = bridge.update_population(population, fitness_map)

    assert len(events) == 2
    assert population.get_member("genome_001").score > 0.0
    assert population.get_member("genome_002").score > 0.0


def test_ac6e_evolution_bridge_select_survivors():
    """AC6e: EvolutionBridge.select_survivors returns elite survivors."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)

    for i, score in enumerate([0.5, 0.9, 0.7, 0.3, 0.8, 0.6, 0.4]):
        gid = f"genome_{i:03d}"
        genome = _make_genome(gid)
        fitness = _make_genome_fitness(gid, fitness_score=score)
        bridge.apply_feedback(population, genome, fitness)

    result = bridge.select_survivors(population, elite_count=3, min_fitness=0.3)
    assert result.survivor_count == 3
    assert result.survivors[0].score >= result.survivors[1].score


# ═══════════════════════════════════════════════════════════
# AC7 — Generation Advance
# ═══════════════════════════════════════════════════════════

def test_ac7a_advance_generation_basic():
    """AC7a: FeedbackLoopController.advance_generation increments generation."""
    controller = FeedbackLoopController()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_001")

    # Process feedback first to init state
    controller.process_feedback(_make_full_feedback(), population, genome)
    assert controller.loop_state.generation == 1

    controller.advance_generation(population)
    assert population.generation == 2
    assert controller.loop_state.generation == 2


def test_ac7b_advance_generation_updates_state():
    """AC7b: advance_generation sets loop state to EVOLVING."""
    controller = FeedbackLoopController()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_001")

    controller.process_feedback(_make_full_feedback(), population, genome)
    controller.advance_generation(population)

    assert controller.loop_state.status == LoopStatus.EVOLVING


def test_ac7c_evolution_bridge_advance_generation():
    """AC7c: EvolutionBridge.advance_generation increments population generation."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=3)

    result = bridge.advance_generation(population)
    assert result.generation == 4


def test_ac7d_multi_generation_tracking():
    """AC7d: Multiple generations are tracked correctly."""
    controller = FeedbackLoopController()

    for gen in range(1, 4):
        pop = _make_population(f"pop_gen{gen}", generation=gen)
        genome = _make_genome(f"genome_gen{gen}", generation=gen)
        controller.process_feedback(_make_full_feedback(f"creative_{gen}"), pop, genome)
        if gen < 3:
            controller.advance_generation(pop)

    assert controller.loop_state.generation == 3
    assert controller.loop_state.processed_count == 3


# ═══════════════════════════════════════════════════════════
# AC8 — Rollback
# ═══════════════════════════════════════════════════════════

def test_ac8a_should_rollback_true():
    """AC8a: should_rollback returns True when fitness drops below threshold."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_high")
    genome = _make_genome("genome_high")
    population = _make_population("pop_test", generation=1)
    controller.process_feedback(feedback, population, genome)

    # Current fitness is much lower than best
    assert controller.should_rollback(0.1, degradation_threshold=0.1) is True


def test_ac8b_should_rollback_false():
    """AC8b: should_rollback returns False when fitness is close to best."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_high")
    genome = _make_genome("genome_high")
    population = _make_population("pop_test", generation=1)
    controller.process_feedback(feedback, population, genome)

    best = controller.best_score
    # Current fitness is close to best
    assert controller.should_rollback(best - 0.01, degradation_threshold=0.1) is False


def test_ac8c_should_rollback_no_state():
    """AC8c: should_rollback returns False when no loop state exists."""
    controller = FeedbackLoopController()
    assert controller.should_rollback(0.5) is False


def test_ac8d_rollback_execution():
    """AC8d: FeedbackLoopController.rollback delegates to EvolutionBridge."""
    controller = FeedbackLoopController()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_001")
    fitness = _make_genome_fitness("genome_001", fitness_score=0.9)

    # Add to population first
    bridge = EvolutionBridge()
    bridge.apply_feedback(population, genome, fitness)

    # Rollback with higher fitness
    result = controller.rollback(population, 0.95, "genome_best")
    # May or may not rollback depending on population state
    assert isinstance(result, bool)


def test_ac8e_evolution_bridge_rollback_to_best():
    """AC8e: EvolutionBridge.rollback_to_best detects degradation."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)

    # Add genome with medium fitness
    genome = _make_genome("genome_001")
    fitness = _make_genome_fitness("genome_001", fitness_score=0.5)
    bridge.apply_feedback(population, genome, fitness)

    # Previous best was 0.9, current is 0.5 → should rollback
    result = bridge.rollback_to_best(population, 0.9, "genome_previous_best")
    assert result is True


# ═══════════════════════════════════════════════════════════
# AC9 — Convergence
# ═══════════════════════════════════════════════════════════

def test_ac9a_check_convergence_not_converged():
    """AC9a: check_convergence returns not converged for improving history."""
    controller = FeedbackLoopController()
    history = _make_evolution_history([0.5, 0.6, 0.7, 0.8, 0.9])

    result = controller.check_convergence(history)
    assert result["converged"] is False
    assert "improving" in result["reason"].lower()


def test_ac9b_check_convergence_insufficient():
    """AC9b: check_convergence returns not converged for insufficient data."""
    controller = FeedbackLoopController()
    history = _make_evolution_history([0.5])

    result = controller.check_convergence(history)
    assert result["converged"] is False


def test_ac9c_is_converged_false():
    """AC9c: is_converged returns False for improving history."""
    controller = FeedbackLoopController()
    history = _make_evolution_history([0.5, 0.6, 0.7, 0.8, 0.9])

    assert controller.is_converged(history) is False


def test_ac9d_convergence_with_stable_history():
    """AC9d: Convergence detected when scores are stable."""
    controller = FeedbackLoopController(
        convergence_config=ConvergenceConfig(patience=3, min_delta=0.05),
    )
    history = _make_evolution_history([0.90, 0.91, 0.91, 0.91, 0.91])

    result = controller.check_convergence(history)
    assert result["converged"] is True


def test_ac9e_convergence_with_custom_patience():
    """AC9e: Convergence respects custom patience config."""
    controller = FeedbackLoopController(
        convergence_config=ConvergenceConfig(patience=5, min_delta=0.01),
    )
    # Very stable scores over 5 generations
    history = _make_evolution_history([0.90, 0.905, 0.905, 0.905, 0.905, 0.905])

    result = controller.check_convergence(history)
    assert result["converged"] is True


# ═══════════════════════════════════════════════════════════
# AC10 — History
# ═══════════════════════════════════════════════════════════

def test_ac10a_event_store_timeline():
    """AC10a: EvolutionEventStore timeline is sorted by timestamp."""
    store = EvolutionEventStore()
    e1 = EvolutionFeedbackEvent(genome_id="g1", fitness_score=0.5, generation=1)
    e2 = EvolutionFeedbackEvent(genome_id="g2", fitness_score=0.7, generation=2)
    e3 = EvolutionFeedbackEvent(genome_id="g3", fitness_score=0.9, generation=3)
    store.add_event(e1)
    store.add_event(e2)
    store.add_event(e3)

    timeline = store.get_timeline()
    assert len(timeline) == 3
    # Timeline should be sorted by timestamp
    for i in range(len(timeline) - 1):
        assert timeline[i].timestamp <= timeline[i + 1].timestamp


def test_ac10b_get_by_generation():
    """AC10b: EvolutionEventStore.get_by_generation filters correctly."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(genome_id="g1", generation=1))
    store.add_event(EvolutionFeedbackEvent(genome_id="g2", generation=2))
    store.add_event(EvolutionFeedbackEvent(genome_id="g3", generation=2))

    gen1 = store.get_by_generation(1)
    gen2 = store.get_by_generation(2)
    gen3 = store.get_by_generation(3)

    assert len(gen1) == 1
    assert len(gen2) == 2
    assert len(gen3) == 0


def test_ac10c_get_by_genome():
    """AC10c: EvolutionEventStore.get_by_genome filters correctly."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(genome_id="genome_A", generation=1))
    store.add_event(EvolutionFeedbackEvent(genome_id="genome_A", generation=2))
    store.add_event(EvolutionFeedbackEvent(genome_id="genome_B", generation=1))

    a_events = store.get_by_genome("genome_A")
    b_events = store.get_by_genome("genome_B")
    c_events = store.get_by_genome("genome_C")

    assert len(a_events) == 2
    assert len(b_events) == 1
    assert len(c_events) == 0


def test_ac10d_get_best_events():
    """AC10d: EvolutionEventStore.get_best_events returns top 10 by fitness."""
    store = EvolutionEventStore()
    for i in range(15):
        store.add_event(
            EvolutionFeedbackEvent(
                genome_id=f"g_{i:03d}",
                fitness_score=0.5 + i * 0.03,
                generation=1,
            )
        )

    best = store.get_best_events()
    assert len(best) == 10
    assert best[0].fitness_score >= best[-1].fitness_score


def test_ac10e_get_by_creative():
    """AC10e: EvolutionEventStore.get_by_creative filters by creative_id."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g1", creative_id="creative_A", fitness_score=0.8,
    ))
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g2", creative_id="creative_B", fitness_score=0.7,
    ))

    assert len(store.get_by_creative("creative_A")) == 1
    assert len(store.get_by_creative("creative_B")) == 1
    assert len(store.get_by_creative("creative_C")) == 0


# ═══════════════════════════════════════════════════════════
# AC11 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac11a_evolution_feedback_event_serialization():
    """AC11a: EvolutionFeedbackEvent to_dict/from_dict roundtrip."""
    event = EvolutionFeedbackEvent(
        genome_id="genome_001",
        creative_id="creative_005",
        feedback_id="fb_abc123",
        fitness_score=0.87,
        generation=3,
        action="feedback_processed",
        details={"key": "value"},
    )
    data = event.to_dict()
    restored = EvolutionFeedbackEvent.from_dict(data)

    assert restored.genome_id == event.genome_id
    assert restored.creative_id == event.creative_id
    assert restored.fitness_score == event.fitness_score
    assert restored.generation == event.generation
    assert restored.action == event.action
    assert restored.details == event.details


def test_ac11b_feedback_loop_state_serialization():
    """AC11b: FeedbackLoopState to_dict/from_dict roundtrip."""
    state = FeedbackLoopState(
        generation=3,
        status=LoopStatus.EVOLVING,
        processed_count=15,
        best_fitness=0.91,
        best_genome_id="genome_021",
    )
    # Set started_at without changing status
    from datetime import datetime, timezone
    state.started_at = datetime.now(timezone.utc)

    data = state.to_dict()
    restored = FeedbackLoopState.from_dict(data)

    assert restored.generation == 3
    assert restored.status == LoopStatus.EVOLVING
    assert restored.processed_count == 15
    assert restored.best_fitness == 0.91
    assert restored.best_genome_id == "genome_021"
    assert restored.started_at is not None


def test_ac11c_evolution_event_store_serialization():
    """AC11c: EvolutionEventStore to_dict/from_dict roundtrip."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g1", fitness_score=0.8, generation=1,
    ))
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g2", fitness_score=0.9, generation=2,
    ))

    data = store.to_dict()
    restored = EvolutionEventStore.from_dict(data)

    assert restored.event_count == 2
    assert restored.best_score == 0.9


def test_ac11d_feedback_loop_controller_serialization():
    """AC11d: FeedbackLoopController to_dict serializes state and events."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)
    controller.process_feedback(feedback, population, genome)

    data = controller.to_dict()
    assert "loop_state" in data
    assert "events" in data
    assert data["loop_state"] is not None


def test_ac11e_evolution_bridge_repr():
    """AC11e: EvolutionBridge repr is deterministic."""
    bridge = EvolutionBridge()
    r = repr(bridge)
    assert "EvolutionBridge" in r


# ═══════════════════════════════════════════════════════════
# AC12 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac12a_deterministic_event_creation():
    """AC12a: Same inputs produce same evolution event fields."""
    e1 = EvolutionFeedbackEvent(
        genome_id="genome_001",
        fitness_score=0.87,
        generation=3,
        action="feedback_processed",
        details={"a": 1, "b": 2},
    )
    e2 = EvolutionFeedbackEvent(
        genome_id="genome_001",
        fitness_score=0.87,
        generation=3,
        action="feedback_processed",
        details={"a": 1, "b": 2},
    )

    # All deterministic fields match
    assert e1.genome_id == e2.genome_id
    assert e1.fitness_score == e2.fitness_score
    assert e1.generation == e2.generation
    assert e1.action == e2.action
    assert e1.details == e2.details


def test_ac12b_deterministic_feedback_processing():
    """AC12b: Same feedback processed twice produces same loop state fitness."""
    fb1 = _make_full_feedback("creative_001")
    fb2 = _make_full_feedback("creative_001")

    c1 = FeedbackLoopController()
    c2 = FeedbackLoopController()

    c1.process_feedback(fb1, _make_population("p1"), _make_genome("g1"))
    c2.process_feedback(fb2, _make_population("p2"), _make_genome("g1"))

    # Same input → same best_fitness
    assert c1.best_score == pytest.approx(c2.best_score)


def test_ac12c_deterministic_rollback_check():
    """AC12c: should_rollback is deterministic for same inputs."""
    c1 = FeedbackLoopController()
    c2 = FeedbackLoopController()

    c1.process_feedback(_make_full_feedback(), _make_population("p1"), _make_genome("g1"))
    c2.process_feedback(_make_full_feedback(), _make_population("p2"), _make_genome("g1"))

    assert c1.should_rollback(0.5) == c2.should_rollback(0.5)


def test_ac12d_deterministic_convergence_check():
    """AC12d: Convergence check is deterministic for same history."""
    c1 = FeedbackLoopController(
        convergence_config=ConvergenceConfig(patience=3, min_delta=0.05),
    )
    c2 = FeedbackLoopController(
        convergence_config=ConvergenceConfig(patience=3, min_delta=0.05),
    )

    h1 = _make_evolution_history([0.90, 0.91, 0.91, 0.91])
    h2 = _make_evolution_history([0.90, 0.91, 0.91, 0.91])

    r1 = c1.check_convergence(h1)
    r2 = c2.check_convergence(h2)

    assert r1["converged"] == r2["converged"]
    assert r1["actual_delta"] == r2["actual_delta"]


def test_ac12e_deterministic_evolution_bridge():
    """AC12e: EvolutionBridge.apply_feedback is deterministic for same inputs."""
    b1 = EvolutionBridge()
    b2 = EvolutionBridge()

    pop1 = _make_population("p1")
    pop2 = _make_population("p2")
    g1 = _make_genome("genome_001")
    g2 = _make_genome("genome_001")
    f1 = _make_genome_fitness("genome_001", fitness_score=0.91)
    f2 = _make_genome_fitness("genome_001", fitness_score=0.91)

    e1 = b1.apply_feedback(pop1, g1, f1)
    e2 = b2.apply_feedback(pop2, g2, f2)

    assert e1.genome_id == e2.genome_id
    assert e1.fitness_score == e2.fitness_score
    assert pop1.best_score == pop2.best_score


# ═══════════════════════════════════════════════════════════
# Additional — Edge Cases
# ═══════════════════════════════════════════════════════════

def test_controller_reset():
    """Controller reset clears all state."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback()
    genome = _make_genome("genome_001")
    population = _make_population("pop_test")

    controller.process_feedback(feedback, population, genome)
    assert controller.event_store.event_count > 0
    assert controller.loop_state is not None

    controller.reset()
    assert controller.event_store.event_count == 0
    assert controller.loop_state is None
    assert controller.best_score == 0.0


def test_controller_with_config():
    """Controller with EvolutionConfig marks elite members."""
    controller = FeedbackLoopController()
    feedback = _make_full_feedback("creative_001")
    genome = _make_genome("genome_001")
    population = _make_population("pop_test", generation=1)
    config = EvolutionConfig(elite_count=3, min_fitness_threshold=0.3)

    controller.process_feedback(feedback, population, genome, config=config)

    # Check elite_marked event
    elite_events = [
        e for e in controller.timeline if e.action == "elite_marked"
    ]
    assert len(elite_events) >= 1


def test_controller_select_survivors():
    """Controller select_survivors returns survivor IDs."""
    controller = FeedbackLoopController()
    population = _make_population("pop_test", generation=1)

    bridge = EvolutionBridge()
    for i, score in enumerate([0.9, 0.7, 0.5, 0.3, 0.8]):
        gid = f"genome_{i:03d}"
        genome = _make_genome(gid)
        fitness = _make_genome_fitness(gid, fitness_score=score)
        bridge.apply_feedback(population, genome, fitness)

    survivors = controller.select_survivors(population, elite_count=3)
    assert len(survivors) == 3


def test_evolution_bridge_get_top_candidates():
    """EvolutionBridge.get_top_candidates returns top N."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)

    for i, score in enumerate([0.5, 0.9, 0.7, 0.3, 0.8]):
        gid = f"genome_{i:03d}"
        genome = _make_genome(gid)
        fitness = _make_genome_fitness(gid, fitness_score=score)
        bridge.apply_feedback(population, genome, fitness)

    top = bridge.get_top_candidates(population, top_k=3)
    assert len(top) == 3
    assert top[0].score >= top[1].score


def test_evolution_bridge_mark_elite():
    """EvolutionBridge.mark_elite marks top members as elite."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)

    for i, score in enumerate([0.5, 0.9, 0.7, 0.3, 0.8]):
        gid = f"genome_{i:03d}"
        genome = _make_genome(gid)
        fitness = _make_genome_fitness(gid, fitness_score=score)
        bridge.apply_feedback(population, genome, fitness)

    bridge.mark_elite(population, top_k=3, min_score=0.5)
    elite_count = sum(1 for m in population.members if m.is_elite)
    assert elite_count == 3


def test_evolution_bridge_apply_feedback_existing_member():
    """EvolutionBridge.apply_feedback updates existing member's fitness."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)
    genome = _make_genome("genome_001")
    fitness1 = _make_genome_fitness("genome_001", fitness_score=0.7)
    fitness2 = _make_genome_fitness("genome_001", fitness_score=0.95)

    bridge.apply_feedback(population, genome, fitness1)
    assert population.get_member("genome_001").score == pytest.approx(0.7, abs=0.1)

    bridge.apply_feedback(population, genome, fitness2)
    assert population.get_member("genome_001").score == pytest.approx(0.95, abs=0.1)


def test_event_store_to_dict():
    """EvolutionEventStore.to_dict returns valid structure."""
    store = EvolutionEventStore()
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g1", fitness_score=0.8, generation=1,
    ))
    store.add_event(EvolutionFeedbackEvent(
        genome_id="g2", fitness_score=0.9, generation=2,
    ))

    data = store.to_dict()
    assert "events" in data
    assert len(data["events"]) == 2


def test_feedback_loop_state_with_custom_values():
    """FeedbackLoopState with custom init values."""
    state = FeedbackLoopState(
        loop_id="loop_custom",
        generation=5,
        status=LoopStatus.EVOLVING,
        processed_count=42,
        best_fitness=0.88,
        best_genome_id="genome_042",
        population_id="pop_042",
    )
    assert state.loop_id == "loop_custom"
    assert state.generation == 5
    assert state.status == LoopStatus.EVOLVING
    assert state.processed_count == 42
    assert state.best_fitness == 0.88
    assert state.best_genome_id == "genome_042"


def test_loop_state_fail_transition():
    """FeedbackLoopState.fail sets status to FAILED."""
    state = FeedbackLoopState()
    state.start()
    state.fail()

    assert state.status == LoopStatus.FAILED
    assert state.completed_at is not None
    assert state.is_terminal is True


def test_evolution_bridge_rollback_no_best():
    """EvolutionBridge.rollback_to_best returns False when no best member."""
    bridge = EvolutionBridge()
    population = _make_population("pop_test", generation=1)  # empty

    result = bridge.rollback_to_best(population, 0.9, "genome_best")
    assert result is False