"""E11.3.3 — Selection Layer Test.

8 AC covering:
  1. Selection Schema (Mode / Policy / Result)
  2. Elite Selection (top_k)
  3. Threshold Selection (min_score)
  4. Diversity Selection (unique fingerprints)
  5. Selection Manager Dispatch (policy → strategy)
  6. Survivor Ranking (rank preserved)
  7. Serialization (to_dict / from_dict roundtrip)
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
    Survivor,
    SelectionResult,
    EliteSelection,
    ThresholdSelection,
    DiversitySelection,
    SelectionManager,
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


def _make_population(
    scores: dict[str, float],
    population_id: str = "pop_001",
) -> GenomePopulation:
    """创建带评分的种群。"""
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
# AC1 — Selection Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_selection_mode_enum():
    """AC1a: SelectionMode has ELITE, THRESHOLD, DIVERSITY."""
    assert SelectionMode.ELITE.value == "elite"
    assert SelectionMode.THRESHOLD.value == "threshold"
    assert SelectionMode.DIVERSITY.value == "diversity"
    assert len(SelectionMode) == 3


def test_ac1b_selection_policy_create():
    """AC1b: SelectionPolicy creates with all fields."""
    policy = SelectionPolicy(
        mode=SelectionMode.ELITE,
        top_k=5,
        min_score=0.75,
        diversity_limit=3,
    )
    assert policy.mode == SelectionMode.ELITE
    assert policy.top_k == 5
    assert policy.min_score == 0.75
    assert policy.diversity_limit == 3


def test_ac1c_selection_policy_defaults():
    """AC1c: SelectionPolicy defaults."""
    policy = SelectionPolicy()
    assert policy.mode == SelectionMode.ELITE
    assert policy.top_k == 5
    assert policy.min_score == 0.5
    assert policy.diversity_limit == 3


def test_ac1d_survivor_create():
    """AC1d: Survivor creates with all fields."""
    s = Survivor(genome_id="genome_001", score=0.91, rank=1, reason="elite_top_2")
    assert s.genome_id == "genome_001"
    assert s.score == 0.91
    assert s.rank == 1
    assert s.reason == "elite_top_2"


def test_ac1e_selection_result_create():
    """AC1e: SelectionResult creates with survivors and eliminated."""
    result = SelectionResult(
        population_id="pop_001",
        survivors=[
            Survivor("genome_A", 0.91, 1, "elite"),
            Survivor("genome_B", 0.85, 2, "elite"),
        ],
        eliminated=["genome_C"],
        generation=1,
    )

    assert result.population_id == "pop_001"
    assert result.survivor_count == 2
    assert result.eliminated_count == 1
    assert result.survival_rate == 0.6667
    assert result.survivor_ids == ["genome_A", "genome_B"]
    assert result.is_survivor("genome_A") is True
    assert result.is_survivor("genome_C") is False


def test_ac1f_selection_result_empty():
    """AC1f: Empty SelectionResult."""
    result = SelectionResult()
    assert result.survivor_count == 0
    assert result.eliminated_count == 0
    assert result.survival_rate == 0.0
    assert result.survivor_ids == []
    assert result.selection_id.startswith("sel_")


# ═══════════════════════════════════════════════════════════
# AC2 — Elite Selection
# ═══════════════════════════════════════════════════════════

def test_ac2_elite_selection():
    """AC2a: Elite top_k=2 selects top 2."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
        "genome_D": 0.40,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=2)

    assert result.survivor_count == 2
    assert result.eliminated_count == 2
    assert result.survivor_ids == ["genome_A", "genome_B"]
    assert "genome_C" in result.eliminated
    assert "genome_D" in result.eliminated


def test_ac2b_elite_top_k_larger_than_population():
    """AC2b: top_k > population size → all survive."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=10)

    assert result.survivor_count == 2
    assert result.eliminated_count == 0


def test_ac2c_elite_top_k_zero():
    """AC2c: top_k=0 → all eliminated."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=0)

    assert result.survivor_count == 0
    assert result.eliminated_count == 2


def test_ac2d_elite_survivor_ranks():
    """AC2d: Survivors have correct ranks."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=3)

    assert result.get_survivor("genome_A").rank == 1
    assert result.get_survivor("genome_B").rank == 2
    assert result.get_survivor("genome_C").rank == 3


def test_ac2e_elite_reason_field():
    """AC2e: Survivor reason includes top_k."""
    pop = _make_population({"genome_A": 0.91})
    strategy = EliteSelection()
    result = strategy.select(pop, top_k=3)

    assert "top_3" in result.survivors[0].reason


# ═══════════════════════════════════════════════════════════
# AC3 — Threshold Selection
# ═══════════════════════════════════════════════════════════

def test_ac3_threshold_selection():
    """AC3a: Threshold min_score=0.75 selects score >= 0.75."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.51,
        "genome_D": 0.40,
    })

    strategy = ThresholdSelection()
    result = strategy.select(pop, min_score=0.75)

    assert result.survivor_count == 2
    assert result.survivor_ids == ["genome_A", "genome_B"]
    assert "genome_C" in result.eliminated
    assert "genome_D" in result.eliminated


def test_ac3b_threshold_all_pass():
    """AC3b: min_score=0.0 → all pass."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.30,
    })

    strategy = ThresholdSelection()
    result = strategy.select(pop, min_score=0.0)

    assert result.survivor_count == 2
    assert result.eliminated_count == 0


def test_ac3c_threshold_all_fail():
    """AC3c: min_score=1.0 → all fail."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
    })

    strategy = ThresholdSelection()
    result = strategy.select(pop, min_score=1.0)

    assert result.survivor_count == 0
    assert result.eliminated_count == 2


def test_ac3d_threshold_exact_boundary():
    """AC3d: Score exactly at threshold survives."""
    pop = _make_population({
        "genome_A": 0.50,
        "genome_B": 0.49,
    })

    strategy = ThresholdSelection()
    result = strategy.select(pop, min_score=0.50)

    assert result.survivor_count == 1
    assert result.survivor_ids == ["genome_A"]


def test_ac3e_threshold_reason_field():
    """AC3e: Survivor reason includes threshold value."""
    pop = _make_population({"genome_A": 0.80})
    strategy = ThresholdSelection()
    result = strategy.select(pop, min_score=0.75)

    assert "0.75" in result.survivors[0].reason


# ═══════════════════════════════════════════════════════════
# AC4 — Diversity Selection
# ═══════════════════════════════════════════════════════════

def test_ac4_diversity_selection():
    """AC4a: Diversity selection keeps unique genomes."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
        "genome_D": 0.40,
    })

    strategy = DiversitySelection()
    result = strategy.select(pop, diversity_limit=3)

    # 所有 ID 不同 → 全部存活
    assert result.survivor_count == 4
    assert result.eliminated_count == 0


def test_ac4b_diversity_limit_one():
    """AC4b: diversity_limit=1 → 每个指纹最多保留 1 个."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
    })

    strategy = DiversitySelection()
    result = strategy.select(pop, diversity_limit=1)

    # 每个 ID 指纹不同 → 全部存活
    assert result.survivor_count == 3


def test_ac4c_diversity_result_fields():
    """AC4c: Diversity result has correct policy."""
    pop = _make_population({"genome_A": 0.91})
    strategy = DiversitySelection()
    result = strategy.select(pop, diversity_limit=2)

    assert result.policy is not None
    assert result.policy.mode == SelectionMode.DIVERSITY
    assert result.policy.diversity_limit == 2


# ═══════════════════════════════════════════════════════════
# AC5 — Selection Manager Dispatch
# ═══════════════════════════════════════════════════════════

def test_ac5_manager_dispatch_elite():
    """AC5a: Manager dispatches ELITE policy correctly."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
    })

    mgr = SelectionManager()
    policy = SelectionPolicy(mode=SelectionMode.ELITE, top_k=2)
    result = mgr.select(pop, policy)

    assert result.survivor_count == 2
    assert result.survivor_ids == ["genome_A", "genome_B"]


def test_ac5b_manager_dispatch_threshold():
    """AC5b: Manager dispatches THRESHOLD policy correctly."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.40,
    })

    mgr = SelectionManager()
    policy = SelectionPolicy(mode=SelectionMode.THRESHOLD, min_score=0.5)
    result = mgr.select(pop, policy)

    assert result.survivor_count == 1
    assert result.survivor_ids == ["genome_A"]


def test_ac5c_manager_dispatch_diversity():
    """AC5c: Manager dispatches DIVERSITY policy correctly."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
    })

    mgr = SelectionManager()
    policy = SelectionPolicy(mode=SelectionMode.DIVERSITY, diversity_limit=1)
    result = mgr.select(pop, policy)

    assert result.survivor_count == 2


def test_ac5d_manager_shortcut_methods():
    """AC5d: Manager shortcut methods work."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
    })

    mgr = SelectionManager()

    r1 = mgr.select_elite(pop, top_k=2)
    assert r1.survivor_count == 2

    r2 = mgr.select_threshold(pop, min_score=0.8)
    assert r2.survivor_count == 2

    r3 = mgr.select_diversity(pop, diversity_limit=2)
    assert r3.survivor_count == 3


def test_ac5e_manager_selection_count():
    """AC5e: selection_count increments."""
    pop = _make_population({"genome_A": 0.91})
    mgr = SelectionManager()

    assert mgr.selection_count == 0
    mgr.select_elite(pop, top_k=1)
    assert mgr.selection_count == 1
    mgr.select_threshold(pop, min_score=0.5)
    assert mgr.selection_count == 2


# ═══════════════════════════════════════════════════════════
# AC6 — Survivor Ranking
# ═══════════════════════════════════════════════════════════

def test_ac6_survivor_ranking_order():
    """AC6a: Survivors are ordered by score descending."""
    pop = _make_population({
        "genome_A": 0.70,
        "genome_B": 0.91,
        "genome_C": 0.85,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=3)

    # 应按评分降序: B(0.91), C(0.85), A(0.70)
    assert result.survivors[0].genome_id == "genome_B"
    assert result.survivors[1].genome_id == "genome_C"
    assert result.survivors[2].genome_id == "genome_A"


def test_ac6b_survivor_rank_sequence():
    """AC6b: Survivor ranks are 1, 2, 3, ..."""
    pop = _make_population({
        "genome_A": 0.91,
        "genome_B": 0.85,
        "genome_C": 0.70,
    })

    strategy = EliteSelection()
    result = strategy.select(pop, top_k=3)

    for i, s in enumerate(result.survivors):
        assert s.rank == i + 1


# ═══════════════════════════════════════════════════════════
# AC7 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac7_policy_serialization():
    """AC7a: SelectionPolicy to_dict / from_dict roundtrip."""
    policy = SelectionPolicy(
        mode=SelectionMode.ELITE,
        top_k=3,
        min_score=0.6,
        diversity_limit=2,
    )

    d = policy.to_dict()
    assert d["mode"] == "elite"
    assert d["top_k"] == 3

    restored = SelectionPolicy.from_dict(d)
    assert restored.mode == policy.mode
    assert restored.top_k == policy.top_k
    assert restored.min_score == policy.min_score
    assert restored.diversity_limit == policy.diversity_limit


def test_ac7b_survivor_serialization():
    """AC7b: Survivor to_dict / from_dict roundtrip."""
    s = Survivor(genome_id="genome_001", score=0.91, rank=1, reason="elite")

    d = s.to_dict()
    assert d["genome_id"] == "genome_001"

    restored = Survivor.from_dict(d)
    assert restored.genome_id == s.genome_id
    assert restored.score == s.score
    assert restored.rank == s.rank
    assert restored.reason == s.reason


def test_ac7c_selection_result_serialization():
    """AC7c: SelectionResult to_dict / from_dict roundtrip."""
    result = SelectionResult(
        population_id="pop_001",
        survivors=[
            Survivor("genome_A", 0.91, 1, "elite_top_2"),
            Survivor("genome_B", 0.85, 2, "elite_top_2"),
        ],
        eliminated=["genome_C"],
        generation=2,
        policy=SelectionPolicy(mode=SelectionMode.ELITE, top_k=2),
    )

    d = result.to_dict()
    assert d["population_id"] == "pop_001"
    assert d["generation"] == 2
    assert len(d["survivors"]) == 2
    assert len(d["eliminated"]) == 1
    assert d["policy"] is not None

    restored = SelectionResult.from_dict(d)
    assert restored.population_id == result.population_id
    assert restored.generation == result.generation
    assert restored.survivor_count == result.survivor_count
    assert restored.eliminated_count == result.eliminated_count
    assert restored.survivor_ids == result.survivor_ids


# ═══════════════════════════════════════════════════════════
# AC8 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac8_deterministic_elite():
    """AC8a: Same population + policy → same elite result."""
    scores = {"A": 0.91, "B": 0.85, "C": 0.70}

    pop1 = _make_population(scores)
    pop2 = _make_population(scores)

    strategy = EliteSelection()
    r1 = strategy.select(pop1, top_k=2)
    r2 = strategy.select(pop2, top_k=2)

    assert r1.survivor_ids == r2.survivor_ids
    assert r1.eliminated == r2.eliminated


def test_ac8b_deterministic_threshold():
    """AC8b: Same population + policy → same threshold result."""
    scores = {"A": 0.91, "B": 0.85, "C": 0.40}

    pop1 = _make_population(scores)
    pop2 = _make_population(scores)

    strategy = ThresholdSelection()
    r1 = strategy.select(pop1, min_score=0.5)
    r2 = strategy.select(pop2, min_score=0.5)

    assert r1.survivor_ids == r2.survivor_ids
    assert r1.eliminated == r2.eliminated


def test_ac8c_deterministic_manager():
    """AC8c: Same population + policy → manager produces same result."""
    scores = {"A": 0.91, "B": 0.85, "C": 0.70, "D": 0.40}

    pop1 = _make_population(scores)
    pop2 = _make_population(scores)

    mgr = SelectionManager()
    policy = SelectionPolicy(mode=SelectionMode.ELITE, top_k=3)

    r1 = mgr.select(pop1, policy)
    r2 = mgr.select(pop2, policy)

    assert r1.survivor_ids == r2.survivor_ids
    assert r1.survival_rate == r2.survival_rate