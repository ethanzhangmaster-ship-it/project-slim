"""E11.4.2 — Multi Generation Evolution Loop Test.

10 AC covering:
  1. Generation Schema (Status / Record / History)
  2. Generation Manager (create / next / complete / fail)
  3. History Recording (add / latest / best / score_progression)
  4. Best Generation (best score tracking)
  5. Convergence Detection (patience / min_delta / converged / not converged)
  6. Checkpoint Save/Load (save / load / restore / delete)
  7. Multi Generation Loop (orchestrator multi-gen)
  8. Early Stop (convergence stopping)
  9. Serialization (to_dict / from_dict roundtrip)
  10. Deterministic (same input → same result)
"""

from __future__ import annotations

from market_ops.e11.evolution import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
    PopulationManager,
    SelectionMode,
    SelectionPolicy,
    SelectionManager,
    EvolutionStatus,
    EvolutionConfig,
    EvolutionRun,
    GenerationResult,
    EvolutionResult,
    EvolutionOrchestrator,
    GenerationStatus,
    GenerationRecord,
    EvolutionHistory,
    GenerationManager,
    EvolutionHistoryRecorder,
    ConvergenceConfig,
    ConvergenceDetector,
    CheckpointRecord,
    CheckpointManager,
)
from market_ops.e11.evolution.population_schema import GenomePopulation


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_fitness(genome_id: str, score_value: float) -> FitnessScore:
    return FitnessScore(
        genome_id=genome_id,
        metrics=[
            FitnessMetric(name="roas_d7", value=score_value, weight=1.0,
                         direction=FitnessDirection.MAXIMIZE),
        ],
    )


def _make_population_with_scores(
    scores: dict[str, float],
    population_id: str = "pop_001",
) -> GenomePopulation:
    mgr = PopulationManager()
    pop = mgr.create_population_from_genomes(
        list(scores.keys()),
        population_id=population_id,
    )
    mgr.update_fitness_batch(pop, {
        gid: _make_fitness(gid, score)
        for gid, score in scores.items()
    })
    mgr.rank_members(pop)
    return pop


# ═══════════════════════════════════════════════════════════
# AC1 — Generation Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_generation_status_enum():
    """AC1a: GenerationStatus has 4 values."""
    assert GenerationStatus.CREATED.value == "created"
    assert GenerationStatus.RUNNING.value == "running"
    assert GenerationStatus.COMPLETED.value == "completed"
    assert GenerationStatus.FAILED.value == "failed"
    assert len(GenerationStatus) == 4


def test_ac1b_generation_record_create():
    """AC1b: GenerationRecord creates with all fields."""
    record = GenerationRecord(
        generation=3,
        population_id="pop_003",
        best_genome_id="genome_021",
        best_score=0.91,
        avg_score=0.75,
        mutation_count=10,
        survivor_count=8,
    )

    assert record.generation == 3
    assert record.population_id == "pop_003"
    assert record.best_genome_id == "genome_021"
    assert record.best_score == 0.91
    assert record.avg_score == 0.75
    assert record.mutation_count == 10
    assert record.survivor_count == 8
    assert record.status == GenerationStatus.CREATED
    assert record.created_at is not None


def test_ac1c_generation_record_lifecycle():
    """AC1c: GenerationRecord lifecycle transitions."""
    record = GenerationRecord(generation=1)

    assert record.status == GenerationStatus.CREATED

    record.start()
    assert record.status == GenerationStatus.RUNNING

    record.complete()
    assert record.status == GenerationStatus.COMPLETED
    assert record.completed_at is not None


def test_ac1d_generation_record_fail():
    """AC1d: GenerationRecord.fail() sets FAILED status."""
    record = GenerationRecord(generation=1)
    record.start()
    record.fail()

    assert record.status == GenerationStatus.FAILED
    assert record.completed_at is not None


def test_ac1e_evolution_history_create():
    """AC1e: EvolutionHistory creates empty."""
    history = EvolutionHistory(run_id="evo_001")
    assert history.run_id == "evo_001"
    assert history.generation_count == 0
    assert history.highest_score() == 0.0
    assert history.latest() is None
    assert history.best() is None


def test_ac1f_evolution_history_add():
    """AC1f: EvolutionHistory.add_generation() stores records."""
    history = EvolutionHistory(run_id="evo_001")
    r1 = GenerationRecord(generation=1, best_score=0.72)
    r2 = GenerationRecord(generation=2, best_score=0.81)

    history.add_generation(r1)
    assert history.generation_count == 1

    history.add_generation(r2)
    assert history.generation_count == 2
    assert history.score_progression == [0.72, 0.81]


# ═══════════════════════════════════════════════════════════
# AC2 — Generation Manager
# ═══════════════════════════════════════════════════════════

def test_ac2_create_generation():
    """AC2a: GenerationManager.create_generation() creates a record."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    mgr = GenerationManager()

    record = mgr.create_generation(pop, generation=1)
    assert record.generation == 1
    assert record.population_id == pop.population_id
    assert record.status == GenerationStatus.CREATED
    assert mgr.generation_count == 1


def test_ac2b_create_generation_default_gen():
    """AC2b: create_generation() uses population.generation as default."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    mgr = GenerationManager()

    record = mgr.create_generation(pop)
    assert record.generation == pop.generation


def test_ac2c_next_generation():
    """AC2c: next_generation() creates next generation record."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    mgr = GenerationManager()

    record = mgr.next_generation(pop, generation=2)
    assert record.generation == 2
    assert record.status == GenerationStatus.CREATED


def test_ac2d_next_generation_auto_increment():
    """AC2d: next_generation() auto-increments from survivors."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    mgr = GenerationManager()

    record = mgr.next_generation(pop)
    assert record.generation == pop.generation + 1


def test_ac2e_complete_generation():
    """AC2e: complete_generation() fills stats from population."""
    pop = _make_population_with_scores({"genome_A": 0.90})
    mgr = GenerationManager()
    record = mgr.create_generation(pop, generation=1)

    mgr.complete_generation(record, pop)
    assert record.status == GenerationStatus.COMPLETED
    assert record.best_score == 0.90
    assert record.best_genome_id == "genome_A"
    assert record.survivor_count == 1


def test_ac2f_fail_generation():
    """AC2f: fail_generation() marks as FAILED."""
    mgr = GenerationManager()
    record = GenerationRecord(generation=1)

    mgr.fail_generation(record)
    assert record.status == GenerationStatus.FAILED


def test_ac2g_reset_counter():
    """AC2g: reset() resets generation counter."""
    mgr = GenerationManager()
    pop = _make_population_with_scores({"genome_A": 0.80})
    mgr.create_generation(pop)
    mgr.create_generation(pop)
    assert mgr.generation_count == 2

    mgr.reset()
    assert mgr.generation_count == 0


# ═══════════════════════════════════════════════════════════
# AC3 — History Recording
# ═══════════════════════════════════════════════════════════

def test_ac3_history_recorder_record():
    """AC3a: EvolutionHistoryRecorder.record() stores generation."""
    recorder = EvolutionHistoryRecorder(run_id="evo_001")
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    recorder.record(r1)

    assert recorder.generation_count == 1
    assert recorder.latest().best_score == 0.65


def test_ac3b_history_recorder_latest():
    """AC3b: latest() returns most recent generation."""
    recorder = EvolutionHistoryRecorder()
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    r2 = GenerationRecord(generation=2, best_score=0.73)
    r2.complete()
    recorder.record(r1)
    recorder.record(r2)

    assert recorder.latest().best_score == 0.73
    assert recorder.latest().generation == 2


def test_ac3c_history_recorder_best():
    """AC3c: best() returns highest score generation."""
    recorder = EvolutionHistoryRecorder()
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    r2 = GenerationRecord(generation=2, best_score=0.73)
    r2.complete()
    r3 = GenerationRecord(generation=3, best_score=0.88)
    r3.complete()
    recorder.record(r1)
    recorder.record(r2)
    recorder.record(r3)

    best = recorder.best()
    assert best.generation == 3
    assert best.best_score == 0.88


def test_ac3d_history_recorder_score_progression():
    """AC3d: score_progression returns list of best scores."""
    recorder = EvolutionHistoryRecorder()
    for i, score in enumerate([0.65, 0.73, 0.88], start=1):
        r = GenerationRecord(generation=i, best_score=score)
        r.complete()
        recorder.record(r)

    assert recorder.score_progression == [0.65, 0.73, 0.88]


def test_ac3e_history_recorder_get_completed():
    """AC3e: get_completed() filters by COMPLETED status."""
    recorder = EvolutionHistoryRecorder()
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    r2 = GenerationRecord(generation=2, best_score=0.73)
    r2.fail()
    recorder.record(r1)
    recorder.record(r2)

    completed = recorder.get_completed()
    assert len(completed) == 1
    assert completed[0].generation == 1


def test_ac3f_history_recorder_get_failed():
    """AC3f: get_failed() filters by FAILED status."""
    recorder = EvolutionHistoryRecorder()
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    r2 = GenerationRecord(generation=2, best_score=0.73)
    r2.fail()
    recorder.record(r1)
    recorder.record(r2)

    failed = recorder.get_failed()
    assert len(failed) == 1
    assert failed[0].generation == 2


def test_ac3g_history_recorder_clear():
    """AC3g: clear() empties all records."""
    recorder = EvolutionHistoryRecorder()
    r1 = GenerationRecord(generation=1, best_score=0.65)
    r1.complete()
    recorder.record(r1)
    recorder.clear()

    assert recorder.generation_count == 0


# ═══════════════════════════════════════════════════════════
# AC4 — Best Generation
# ═══════════════════════════════════════════════════════════

def test_ac4_history_highest_score():
    """AC4a: highest_score() returns max across all generations."""
    history = EvolutionHistory()
    history.add_generation(GenerationRecord(generation=1, best_score=0.50))
    history.add_generation(GenerationRecord(generation=2, best_score=0.91))
    history.add_generation(GenerationRecord(generation=3, best_score=0.72))

    assert history.highest_score() == 0.91


def test_ac4b_history_best_none_empty():
    """AC4b: best() returns None for empty history."""
    history = EvolutionHistory()
    assert history.best() is None


def test_ac4c_history_get_generation():
    """AC4c: get_generation() finds by generation number."""
    history = EvolutionHistory()
    history.add_generation(GenerationRecord(generation=1, best_score=0.50))
    history.add_generation(GenerationRecord(generation=2, best_score=0.91))

    g = history.get_generation(2)
    assert g is not None
    assert g.best_score == 0.91

    assert history.get_generation(99) is None


# ═══════════════════════════════════════════════════════════
# AC5 — Convergence Detection
# ═══════════════════════════════════════════════════════════

def test_ac5_convergence_config_create():
    """AC5a: ConvergenceConfig creates with defaults."""
    config = ConvergenceConfig()
    assert config.patience == 5
    assert config.min_delta == 0.01


def test_ac5b_convergence_config_custom():
    """AC5b: ConvergenceConfig with custom values."""
    config = ConvergenceConfig(patience=3, min_delta=0.05)
    assert config.patience == 3
    assert config.min_delta == 0.05


def test_ac5c_converged_detected():
    """AC5c: detect() returns converged=True when stable."""
    history = EvolutionHistory()
    for i, score in enumerate([0.80, 0.805, 0.805, 0.807, 0.807], start=1):
        history.add_generation(GenerationRecord(generation=i, best_score=score))

    detector = ConvergenceDetector(ConvergenceConfig(patience=5, min_delta=0.01))
    result = detector.detect(history)

    assert result["converged"] is True
    assert result["actual_delta"] < 0.01


def test_ac5d_not_converged():
    """AC5d: detect() returns converged=False when improving."""
    history = EvolutionHistory()
    for i, score in enumerate([0.65, 0.73, 0.88], start=1):
        history.add_generation(GenerationRecord(generation=i, best_score=score))

    detector = ConvergenceDetector(ConvergenceConfig(patience=3, min_delta=0.01))
    result = detector.detect(history)

    assert result["converged"] is False


def test_ac5e_insufficient_generations():
    """AC5e: detect() returns not converged for < 2 generations."""
    history = EvolutionHistory()
    history.add_generation(GenerationRecord(generation=1, best_score=0.80))

    detector = ConvergenceDetector()
    result = detector.detect(history)

    assert result["converged"] is False
    assert "Insufficient" in result["reason"]


def test_ac5f_convergence_exact_boundary():
    """AC5f: Exact delta == min_delta should NOT converge."""
    history = EvolutionHistory()
    for i, score in enumerate([0.80, 0.81], start=1):
        history.add_generation(GenerationRecord(generation=i, best_score=score))

    detector = ConvergenceDetector(ConvergenceConfig(patience=2, min_delta=0.01))
    result = detector.detect(history)

    assert result["converged"] is False


def test_ac5g_is_converged_shortcut():
    """AC5g: is_converged() returns boolean."""
    history = EvolutionHistory()
    for i, score in enumerate([0.80, 0.80, 0.80, 0.80, 0.80], start=1):
        history.add_generation(GenerationRecord(generation=i, best_score=score))

    detector = ConvergenceDetector(ConvergenceConfig(patience=5, min_delta=0.01))
    assert detector.is_converged(history) is True


def test_ac5h_convergence_large_patience():
    """AC5h: Larger patience window still detects convergence."""
    history = EvolutionHistory()
    for i in range(1, 11):
        history.add_generation(GenerationRecord(generation=i, best_score=0.90))

    detector = ConvergenceDetector(ConvergenceConfig(patience=10, min_delta=0.01))
    result = detector.detect(history)

    assert result["converged"] is True
    assert result["actual_delta"] == 0.0


# ═══════════════════════════════════════════════════════════
# AC6 — Checkpoint Save/Load
# ═══════════════════════════════════════════════════════════

def test_ac6_checkpoint_record_create():
    """AC6a: CheckpointRecord creates with auto ID."""
    record = CheckpointRecord(
        run_id="evo_001",
        generation=5,
    )
    assert record.checkpoint_id.startswith("ckpt_")
    assert record.run_id == "evo_001"
    assert record.generation == 5


def test_ac6b_checkpoint_save():
    """AC6b: CheckpointManager.save() stores checkpoint."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    history = EvolutionHistory()
    config = EvolutionConfig()

    ckpt_mgr = CheckpointManager()
    record = ckpt_mgr.save(run, pop, history, config)

    assert record.checkpoint_id.startswith("ckpt_")
    assert ckpt_mgr.checkpoint_count == 1


def test_ac6c_checkpoint_load():
    """AC6c: CheckpointManager.load() returns checkpoint."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    history = EvolutionHistory()
    config = EvolutionConfig()

    ckpt_mgr = CheckpointManager()
    saved = ckpt_mgr.save(run, pop, history, config, checkpoint_id="my_ckpt")

    loaded = ckpt_mgr.load("my_ckpt")
    assert loaded is not None
    assert loaded.checkpoint_id == "my_ckpt"
    assert loaded.generation == 1


def test_ac6d_checkpoint_restore():
    """AC6d: CheckpointManager.restore() returns (pop, history, config)."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    history = EvolutionHistory()
    history.add_generation(GenerationRecord(generation=1, best_score=0.80))
    config = EvolutionConfig(population_size=30, max_generations=5)

    ckpt_mgr = CheckpointManager()
    ckpt_mgr.save(run, pop, history, config, checkpoint_id="ckpt_restore")

    restored_pop, restored_history, restored_config = ckpt_mgr.restore("ckpt_restore")
    assert restored_pop is not None
    assert restored_history is not None
    assert restored_config is not None
    assert restored_pop.population_id == pop.population_id
    assert restored_history.generation_count == 1
    assert restored_config.population_size == 30


def test_ac6e_checkpoint_delete():
    """AC6e: CheckpointManager.delete() removes checkpoint."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    ckpt_mgr = CheckpointManager()
    ckpt_mgr.save(run, pop, EvolutionHistory(), EvolutionConfig(), checkpoint_id="to_delete")

    assert ckpt_mgr.checkpoint_count == 1
    ckpt_mgr.delete("to_delete")
    assert ckpt_mgr.checkpoint_count == 0


def test_ac6f_checkpoint_list_all():
    """AC6f: list_all() returns all checkpoints."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    ckpt_mgr = CheckpointManager()
    ckpt_mgr.save(run, pop, EvolutionHistory(), EvolutionConfig())
    ckpt_mgr.save(run, pop, EvolutionHistory(), EvolutionConfig())

    assert len(ckpt_mgr.list_all()) == 2


def test_ac6g_checkpoint_restore_not_found():
    """AC6g: restore() returns (None, None, None) for missing checkpoint."""
    ckpt_mgr = CheckpointManager()
    pop, hist, cfg = ckpt_mgr.restore("nonexistent")
    assert pop is None
    assert hist is None
    assert cfg is None


def test_ac6h_checkpoint_clear():
    """AC6h: clear() removes all checkpoints."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    run = EvolutionRun(population_id=pop.population_id, generation=1)
    ckpt_mgr = CheckpointManager()
    ckpt_mgr.save(run, pop, EvolutionHistory(), EvolutionConfig())
    ckpt_mgr.save(run, pop, EvolutionHistory(), EvolutionConfig())

    ckpt_mgr.clear()
    assert ckpt_mgr.checkpoint_count == 0


# ═══════════════════════════════════════════════════════════
# AC7 — Multi Generation Loop
# ═══════════════════════════════════════════════════════════

def test_ac7_multi_generation_loop():
    """AC7a: Orchestrator runs multiple generations."""
    pop = _make_population_with_scores({
        "genome_A": 0.80,
        "genome_B": 0.70,
    })
    config = EvolutionConfig(
        population_size=3,
        max_generations=3,
        elite_count=2,
        min_fitness_threshold=0.3,
    )

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    assert result.generation_count >= 1
    assert result.total_generations >= 1
    assert result.total_children > 0


def test_ac7b_multi_gen_result_has_generations():
    """AC7b: Multi-gen result contains multiple GenerationResults."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=2, max_generations=3)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    assert len(result.generations) >= 1
    for gen in result.generations:
        assert gen.generation >= 1
        assert gen.children_created >= 0


def test_ac7c_multi_gen_population_grows():
    """AC7c: Population grows across multiple generations."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    initial_size = pop.size
    config = EvolutionConfig(population_size=3, max_generations=3)

    orchestrator = EvolutionOrchestrator()
    orchestrator.run(pop, config)

    assert pop.size > initial_size


def test_ac7d_multi_gen_backward_compat():
    """AC7d: max_generations=1 still works (E11.4.1 backward compat)."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=3, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    assert result.generation_count == 1
    assert result.total_children > 0


# ═══════════════════════════════════════════════════════════
# AC8 — Early Stop
# ═══════════════════════════════════════════════════════════

def test_ac8_early_stop_on_convergence():
    """AC8a: Orchestrator stops early when convergence detected."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=2, max_generations=10)
    # Low patience so convergence triggers quickly
    conv_config = ConvergenceConfig(patience=2, min_delta=0.01)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config, convergence_config=conv_config)

    assert result.success is True
    # Should stop before max_generations=10
    assert result.generation_count < 10


def test_ac8b_early_stop_max_generations():
    """AC8b: Without convergence, runs all max_generations."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=2, max_generations=3)
    # High patience, won't converge in 3 gens
    conv_config = ConvergenceConfig(patience=10, min_delta=0.01)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config, convergence_config=conv_config)

    assert result.success is True
    assert result.generation_count == 3


def test_ac8c_checkpoint_interval():
    """AC8c: Checkpoint saves at configured interval."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=2, max_generations=5)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config, checkpoint_interval=2)

    assert result.success is True
    # 5 gens, interval=2 → saves at gen 2, 4 → at least 2 checkpoints
    assert orchestrator._checkpoint_manager.checkpoint_count >= 2


# ═══════════════════════════════════════════════════════════
# AC9 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac9_generation_record_serialization():
    """AC9a: GenerationRecord to_dict/from_dict roundtrip."""
    record = GenerationRecord(
        generation=3,
        population_id="pop_003",
        best_genome_id="genome_021",
        best_score=0.91,
        avg_score=0.75,
        mutation_count=10,
        survivor_count=8,
    )
    record.complete()

    d = record.to_dict()
    restored = GenerationRecord.from_dict(d)

    assert restored.generation == record.generation
    assert restored.population_id == record.population_id
    assert restored.best_genome_id == record.best_genome_id
    assert restored.best_score == record.best_score
    assert restored.avg_score == record.avg_score
    assert restored.mutation_count == record.mutation_count
    assert restored.survivor_count == record.survivor_count
    assert restored.status == record.status


def test_ac9b_evolution_history_serialization():
    """AC9b: EvolutionHistory to_dict/from_dict roundtrip."""
    history = EvolutionHistory(run_id="evo_001")
    history.add_generation(GenerationRecord(generation=1, best_score=0.72))
    history.add_generation(GenerationRecord(generation=2, best_score=0.81))

    d = history.to_dict()
    restored = EvolutionHistory.from_dict(d)

    assert restored.run_id == "evo_001"
    assert restored.generation_count == 2
    assert restored.score_progression == [0.72, 0.81]


def test_ac9c_history_recorder_serialization():
    """AC9c: EvolutionHistoryRecorder to_dict/from_dict roundtrip."""
    recorder = EvolutionHistoryRecorder(run_id="evo_001")
    r = GenerationRecord(generation=1, best_score=0.72)
    r.complete()
    recorder.record(r)

    d = recorder.to_dict()
    restored = EvolutionHistoryRecorder.from_dict(d)

    assert restored.run_id == "evo_001"
    assert restored.generation_count == 1


def test_ac9d_convergence_config_serialization():
    """AC9d: ConvergenceConfig to_dict/from_dict roundtrip."""
    config = ConvergenceConfig(patience=3, min_delta=0.05)

    d = config.to_dict()
    restored = ConvergenceConfig.from_dict(d)

    assert restored.patience == 3
    assert restored.min_delta == 0.05


def test_ac9e_checkpoint_serialization():
    """AC9e: CheckpointRecord and CheckpointManager serialization."""
    record = CheckpointRecord(
        run_id="evo_001",
        generation=5,
        population={"id": "pop_001"},
        history={"run_id": "evo_001"},
        config={"population_size": 50},
    )

    d = record.to_dict()
    restored = CheckpointRecord.from_dict(d)

    assert restored.checkpoint_id == record.checkpoint_id
    assert restored.run_id == "evo_001"
    assert restored.generation == 5


def test_ac9f_convergence_result_structure():
    """AC9f: Convergence detect() result has all required fields."""
    history = EvolutionHistory()
    history.add_generation(GenerationRecord(generation=1, best_score=0.80))
    history.add_generation(GenerationRecord(generation=2, best_score=0.80))

    detector = ConvergenceDetector()
    result = detector.detect(history)

    assert "converged" in result
    assert "reason" in result
    assert "patience" in result
    assert "min_delta" in result
    assert "actual_delta" in result


# ═══════════════════════════════════════════════════════════
# AC10 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac10_deterministic_multi_gen():
    """AC10a: Same population + config → same result (multi-gen)."""
    pop1 = _make_population_with_scores({"genome_A": 0.80, "genome_B": 0.70})
    pop2 = _make_population_with_scores({"genome_A": 0.80, "genome_B": 0.70})

    config = EvolutionConfig(population_size=3, max_generations=3, elite_count=2)
    orchestrator = EvolutionOrchestrator()

    r1 = orchestrator.run(pop1, config)
    r2 = orchestrator.run(pop2, config)

    assert r1.success == r2.success
    assert r1.generation_count == r2.generation_count
    assert r1.total_children == r2.total_children


def test_ac10b_deterministic_convergence():
    """AC10b: Convergence detection is deterministic."""
    history1 = EvolutionHistory()
    history2 = EvolutionHistory()
    for i, score in enumerate([0.80, 0.80, 0.80, 0.80, 0.80], start=1):
        history1.add_generation(GenerationRecord(generation=i, best_score=score))
        history2.add_generation(GenerationRecord(generation=i, best_score=score))

    detector = ConvergenceDetector()
    r1 = detector.detect(history1)
    r2 = detector.detect(history2)

    assert r1["converged"] == r2["converged"]
    assert r1["actual_delta"] == r2["actual_delta"]


def test_ac10c_deterministic_generation_manager():
    """AC10c: GenerationManager produces deterministic results."""
    pop1 = _make_population_with_scores({"genome_A": 0.80})
    pop2 = _make_population_with_scores({"genome_A": 0.80})

    mgr1 = GenerationManager()
    mgr2 = GenerationManager()

    r1 = mgr1.create_generation(pop1, generation=1)
    r2 = mgr2.create_generation(pop2, generation=1)
    mgr1.complete_generation(r1, pop1)
    mgr2.complete_generation(r2, pop2)

    assert r1.best_score == r2.best_score
    assert r1.best_genome_id == r2.best_genome_id
    assert r1.status == r2.status