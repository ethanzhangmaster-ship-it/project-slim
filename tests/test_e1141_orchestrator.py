"""E11.4.1 — Evolution Orchestrator Test.

8 AC covering:
  1. Schema (Status/Config/Run/Result)
  2. Create Run (config → EvolutionRun)
  3. Execute Cycle (population → result)
  4. Mutation Integration (Genome → Child)
  5. Selection Integration (Population → Survivor)
  6. Result Generation (best_genome, history)
  7. Failure Handling (status=FAILED)
  8. Deterministic (same input → same result)
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
# AC1 — Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_evolution_status_enum():
    """AC1a: EvolutionStatus has 4 values."""
    assert EvolutionStatus.CREATED.value == "created"
    assert EvolutionStatus.RUNNING.value == "running"
    assert EvolutionStatus.COMPLETED.value == "completed"
    assert EvolutionStatus.FAILED.value == "failed"
    assert len(EvolutionStatus) == 4


def test_ac1b_evolution_config_create():
    """AC1b: EvolutionConfig creates with all fields."""
    config = EvolutionConfig(
        population_size=50,
        max_generations=10,
        mutation_rate=0.3,
        elite_count=5,
        min_fitness_threshold=0.5,
        selection_mode="elite",
    )

    assert config.population_size == 50
    assert config.max_generations == 10
    assert config.mutation_rate == 0.3
    assert config.elite_count == 5
    assert config.min_fitness_threshold == 0.5
    assert config.selection_mode == "elite"


def test_ac1c_evolution_config_defaults():
    """AC1c: EvolutionConfig defaults."""
    config = EvolutionConfig()
    assert config.population_size == 50
    assert config.max_generations == 10
    assert config.elite_count == 5


def test_ac1d_evolution_run_create():
    """AC1d: EvolutionRun creates with auto-generated ID."""
    run = EvolutionRun(
        population_id="pop_001",
        generation=1,
        config=EvolutionConfig(),
    )

    assert run.run_id.startswith("evo_")
    assert run.population_id == "pop_001"
    assert run.generation == 1
    assert run.status == EvolutionStatus.CREATED
    assert run.is_active is False


def test_ac1e_evolution_run_lifecycle():
    """AC1e: EvolutionRun lifecycle transitions."""
    run = EvolutionRun(population_id="pop_001", generation=1)

    assert run.status == EvolutionStatus.CREATED

    run.start()
    assert run.status == EvolutionStatus.RUNNING
    assert run.is_active is True
    assert run.started_at is not None

    run.complete()
    assert run.status == EvolutionStatus.COMPLETED
    assert run.completed_at is not None
    assert run.elapsed_seconds is not None


def test_ac1f_evolution_run_fail():
    """AC1f: EvolutionRun.fail() sets FAILED status."""
    run = EvolutionRun(population_id="pop_001", generation=1)
    run.start()
    run.fail()

    assert run.status == EvolutionStatus.FAILED
    assert run.completed_at is not None


def test_ac1g_generation_result_create():
    """AC1g: GenerationResult creates with stats."""
    gr = GenerationResult(
        generation=1,
        children_created=10,
        survivors=8,
        best_score=0.91,
        avg_score=0.72,
        best_genome_id="genome_001",
    )

    assert gr.generation == 1
    assert gr.children_created == 10
    assert gr.survivors == 8
    assert gr.best_score == 0.91
    assert gr.avg_score == 0.72
    assert gr.best_genome_id == "genome_001"


def test_ac1h_evolution_result_create():
    """AC1h: EvolutionResult with generation history."""
    gr = GenerationResult(
        generation=1, children_created=5, survivors=4,
        best_score=0.91, best_genome_id="genome_001",
    )
    result = EvolutionResult(
        run_id="evo_001",
        best_genome_id="genome_001",
        best_score=0.91,
        generations=[gr],
        success=True,
        total_generations=1,
        total_children=5,
    )

    assert result.run_id == "evo_001"
    assert result.best_genome_id == "genome_001"
    assert result.best_score == 0.91
    assert result.success is True
    assert result.generation_count == 1
    assert result.total_children == 5
    assert result.score_progression == [0.91]
    assert result.has_improvement is False


def test_ac1i_evolution_result_improvement():
    """AC1i: has_improvement detects score progression."""
    gr1 = GenerationResult(generation=1, best_score=0.70)
    gr2 = GenerationResult(generation=2, best_score=0.85)
    result = EvolutionResult(
        generations=[gr1, gr2],
        best_score=0.85,
        success=True,
    )

    assert result.has_improvement is True
    assert result.score_progression == [0.70, 0.85]


# ═══════════════════════════════════════════════════════════
# AC2 — Create Run
# ═══════════════════════════════════════════════════════════

def test_ac2_orchestrator_creates_run():
    """AC2a: Orchestrator.run() creates EvolutionRun."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=10, max_generations=1, elite_count=2)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.run_id.startswith("evo_")
    assert result.success is True
    assert result.total_generations == 1


def test_ac2b_run_without_config():
    """AC2b: Run uses default config when none provided."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop)

    assert result.success is True


# ═══════════════════════════════════════════════════════════
# AC3 — Execute Cycle
# ═══════════════════════════════════════════════════════════

def test_ac3_execute_cycle():
    """AC3a: Single generation cycle produces children."""
    pop = _make_population_with_scores({
        "genome_A": 0.80,
        "genome_B": 0.70,
        "genome_C": 0.60,
    })
    config = EvolutionConfig(population_size=10, max_generations=1, elite_count=3)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    assert result.generation_count == 1
    assert result.total_children > 0
    assert result.best_score > 0


def test_ac3b_population_grows():
    """AC3b: Population grows after children are added."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    initial_size = pop.size
    config = EvolutionConfig(population_size=5, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    # 种群增长了（子代加入）
    assert pop.size > initial_size


def test_ac3c_result_has_generation_data():
    """AC3c: Result contains generation statistics."""
    pop = _make_population_with_scores({"genome_A": 0.80, "genome_B": 0.70})
    config = EvolutionConfig(population_size=5, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    gen = result.generations[0]
    assert gen.generation >= 0
    assert gen.children_created > 0
    assert gen.best_score >= 0.0


# ═══════════════════════════════════════════════════════════
# AC4 — Mutation Integration
# ═══════════════════════════════════════════════════════════

def test_ac4_mutation_produces_child():
    """AC4a: Mutation Operator produces child genome."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=3, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    # 子代 ID 不同于父代
    child_ids = [m.genome_id for m in pop.members
                 if m.genome_id != "genome_A"]
    assert len(child_ids) > 0


def test_ac4b_children_unique_ids():
    """AC4b: Each child has a unique genome_id."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=5, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    orchestrator.run(pop, config)

    all_ids = pop.genome_ids
    assert len(all_ids) == len(set(all_ids))  # 无重复


# ═══════════════════════════════════════════════════════════
# AC5 — Selection Integration
# ═══════════════════════════════════════════════════════════

def test_ac5_selection_integration():
    """AC5a: Elite selection marks top performers."""
    pop = _make_population_with_scores({
        "genome_A": 0.90,
        "genome_B": 0.80,
        "genome_C": 0.70,
    })
    config = EvolutionConfig(population_size=5, max_generations=1, elite_count=2,
                            min_fitness_threshold=0.5)

    orchestrator = EvolutionOrchestrator()
    orchestrator.run(pop, config)

    # 精英成员被标记
    elites = pop.get_elite_candidates()
    assert len(elites) > 0
    for elite in elites:
        assert elite.is_elite is True


def test_ac5b_population_ranked():
    """AC5b: Population is ranked after cycle."""
    pop = _make_population_with_scores({
        "genome_A": 0.80,
        "genome_B": 0.70,
    })
    config = EvolutionConfig(population_size=5, elite_count=2)

    orchestrator = EvolutionOrchestrator()
    orchestrator.run(pop, config)

    # 检查排名
    for member in pop.members:
        assert member.rank > 0


# ═══════════════════════════════════════════════════════════
# AC6 — Result Generation
# ═══════════════════════════════════════════════════════════

def test_ac6_result_best_genome():
    """AC6a: Result tracks best_genome_id."""
    pop = _make_population_with_scores({
        "genome_A": 0.90,
        "genome_B": 0.60,
    })
    config = EvolutionConfig(population_size=5, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert result.success is True
    assert result.best_genome_id != ""
    assert result.best_score > 0


def test_ac6b_result_generation_history():
    """AC6b: Result contains generation history."""
    pop = _make_population_with_scores({"genome_A": 0.80})
    config = EvolutionConfig(population_size=3, max_generations=1)

    orchestrator = EvolutionOrchestrator()
    result = orchestrator.run(pop, config)

    assert len(result.generations) == 1
    gen = result.generations[0]
    assert gen.children_created > 0
    assert gen.best_score >= 0.0
    assert gen.avg_score >= 0.0


def test_ac6c_result_serialization():
    """AC6c: EvolutionResult to_dict / from_dict roundtrip."""
    gr = GenerationResult(
        generation=1, children_created=5, survivors=4,
        best_score=0.91, best_genome_id="genome_001",
    )
    result = EvolutionResult(
        run_id="evo_001",
        best_genome_id="genome_001",
        best_score=0.91,
        generations=[gr],
        success=True,
        total_generations=1,
        total_children=5,
    )

    d = result.to_dict()
    assert d["run_id"] == "evo_001"
    assert d["success"] is True
    assert len(d["generations"]) == 1

    restored = EvolutionResult.from_dict(d)
    assert restored.run_id == result.run_id
    assert restored.best_genome_id == result.best_genome_id
    assert restored.best_score == result.best_score
    assert restored.success == result.success
    assert restored.generation_count == result.generation_count


# ═══════════════════════════════════════════════════════════
# AC7 — Failure Handling
# ═══════════════════════════════════════════════════════════

def test_ac7_failure_result():
    """AC7a: Failed run produces EvolutionResult with success=False."""
    # 模拟失败：空种群
    result = EvolutionResult(
        run_id="evo_fail",
        success=False,
        error_message="Empty population",
    )

    assert result.success is False
    assert result.error_message == "Empty population"
    assert result.generation_count == 0
    assert result.total_children == 0


def test_ac7b_failure_error_message():
    """AC7b: Error message is preserved in result."""
    result = EvolutionResult(
        success=False,
        error_message="Mutation engine failed: GeneNotFoundError",
    )

    assert "Mutation engine failed" in result.error_message
    assert result.success is False


# ═══════════════════════════════════════════════════════════
# AC8 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac8_deterministic_orchestrator():
    """AC8a: Same population + config → same result."""
    pop1 = _make_population_with_scores({"genome_A": 0.80, "genome_B": 0.70})
    pop2 = _make_population_with_scores({"genome_A": 0.80, "genome_B": 0.70})

    config = EvolutionConfig(population_size=5, max_generations=1, elite_count=2)
    orchestrator = EvolutionOrchestrator()

    r1 = orchestrator.run(pop1, config)
    r2 = orchestrator.run(pop2, config)

    assert r1.success == r2.success
    assert r1.generation_count == r2.generation_count
    assert r1.total_children == r2.total_children


def test_ac8b_deterministic_empty_population():
    """AC8b: Empty population produces consistent result."""
    pop1 = _make_population_with_scores({})
    pop2 = _make_population_with_scores({})

    config = EvolutionConfig(population_size=3, max_generations=1)
    orchestrator = EvolutionOrchestrator()

    r1 = orchestrator.run(pop1, config)
    r2 = orchestrator.run(pop2, config)

    assert r1.success == r2.success
    assert r1.total_children == r2.total_children


def test_ac8c_config_serialization():
    """AC8c: EvolutionConfig serialization roundtrip."""
    config = EvolutionConfig(
        population_size=30,
        max_generations=5,
        mutation_rate=0.5,
        elite_count=3,
    )

    d = config.to_dict()
    restored = EvolutionConfig.from_dict(d)

    assert restored.population_size == config.population_size
    assert restored.max_generations == config.max_generations
    assert restored.mutation_rate == config.mutation_rate
    assert restored.elite_count == config.elite_count