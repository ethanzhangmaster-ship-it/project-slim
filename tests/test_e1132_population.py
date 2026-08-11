"""E11.3.2 — Population Manager Test.

8 AC covering:
  1. Population Schema (create / status)
  2. Add Genome (empty → add → count)
  3. Remove Genome (remove → not exists)
  4. Fitness Update (member updated)
  5. Ranking (ordered by score)
  6. Elite Query (top_k candidates)
  7. Serialization (to_dict / from_dict roundtrip)
  8. Deterministic (same input → same result)
"""

from __future__ import annotations

from market_ops.e11.evolution import (
    FitnessDirection,
    FitnessMetric,
    FitnessScore,
    PopulationStatus,
    GenomePopulation,
    PopulationMember,
)
from market_ops.e11.evolution.population_manager import PopulationManager


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
    genome_ids: list[str] | None = None,
    population_id: str = "",
    manager: PopulationManager | None = None,
) -> GenomePopulation:
    mgr = manager or PopulationManager()
    if genome_ids:
        return mgr.create_population_from_genomes(genome_ids, population_id)
    return mgr.create_population(population_id)


# ═══════════════════════════════════════════════════════════
# AC1 — Population Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_population_create():
    """AC1a: GenomePopulation creates with defaults."""
    pop = GenomePopulation()

    assert pop.population_id.startswith("pop_")
    assert pop.generation == 1
    assert pop.size == 0
    assert pop.status == PopulationStatus.CREATED
    assert pop.avg_score == 0.0
    assert pop.best_score == 0.0


def test_ac1b_population_status_enum():
    """AC1b: PopulationStatus has 4 values."""
    assert PopulationStatus.CREATED.value == "created"
    assert PopulationStatus.ACTIVE.value == "active"
    assert PopulationStatus.EVALUATED.value == "evaluated"
    assert PopulationStatus.ARCHIVED.value == "archived"
    assert len(PopulationStatus) == 4


def test_ac1c_population_with_members():
    """AC1c: GenomePopulation with pre-populated members."""
    member = PopulationMember(
        genome_id="genome_001",
        fitness=_make_fitness("genome_001", 0.82),
        rank=1,
        is_elite=True,
    )

    pop = GenomePopulation(
        population_id="pop_001",
        generation=2,
        members=[member],
        status=PopulationStatus.ACTIVE,
    )

    assert pop.population_id == "pop_001"
    assert pop.generation == 2
    assert pop.size == 1
    assert pop.genome_ids == ["genome_001"]
    assert pop.avg_score == 0.82
    assert pop.best_score == 0.82
    assert pop.elite_count == 1


def test_ac1d_population_member_fields():
    """AC1d: PopulationMember has all fields."""
    fitness = _make_fitness("genome_001", 0.75)
    member = PopulationMember(
        genome_id="genome_001",
        fitness=fitness,
        rank=2,
        is_elite=True,
    )

    assert member.genome_id == "genome_001"
    assert member.score == 0.75
    assert member.is_healthy is True
    assert member.rank == 2
    assert member.is_elite is True


def test_ac1e_member_no_fitness():
    """AC1e: PopulationMember without fitness defaults score=0."""
    member = PopulationMember(genome_id="genome_001")
    assert member.score == 0.0
    assert member.is_healthy is False
    assert member.fitness is None


# ═══════════════════════════════════════════════════════════
# AC2 — Add Genome
# ═══════════════════════════════════════════════════════════

def test_ac2_add_genome():
    """AC2a: Add genome to empty population."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    assert pop.size == 0

    member = manager.add_genome(pop, "genome_001")
    assert pop.size == 1
    assert member.genome_id == "genome_001"
    assert pop.has_genome("genome_001")


def test_ac2b_add_genome_with_fitness():
    """AC2b: Add genome with initial fitness."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    fitness = _make_fitness("genome_001", 0.82)
    member = manager.add_genome(pop, "genome_001", fitness=fitness)

    assert member.score == 0.82
    assert pop.avg_score == 0.82


def test_ac2c_add_duplicate_raises():
    """AC2c: Adding duplicate genome_id raises ValueError."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    manager.add_genome(pop, "genome_001")

    try:
        manager.add_genome(pop, "genome_001")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_ac2d_add_multiple_genomes():
    """AC2d: Add multiple genomes."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    manager.add_genome(pop, "genome_001")
    manager.add_genome(pop, "genome_002")
    manager.add_genome(pop, "genome_003")

    assert pop.size == 3
    assert pop.genome_ids == ["genome_001", "genome_002", "genome_003"]


def test_ac2e_create_from_genomes():
    """AC2e: create_population_from_genomes."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_001", "genome_002", "genome_003"],
        population_id="pop_test",
    )

    assert pop.population_id == "pop_test"
    assert pop.size == 3
    assert pop.status == PopulationStatus.ACTIVE


# ═══════════════════════════════════════════════════════════
# AC3 — Remove Genome
# ═══════════════════════════════════════════════════════════

def test_ac3_remove_genome():
    """AC3a: Remove genome from population."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_001", "genome_002", "genome_003"],
    )

    assert pop.size == 3

    manager.remove_genome(pop, "genome_002")

    assert pop.size == 2
    assert not pop.has_genome("genome_002")
    assert pop.genome_ids == ["genome_001", "genome_003"]


def test_ac3b_remove_not_found_raises():
    """AC3b: Removing non-existent genome raises ValueError."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    try:
        manager.remove_genome(pop, "nonexistent")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_ac3c_remove_last_genome():
    """AC3c: Remove the last genome → empty population."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(["genome_001"])

    manager.remove_genome(pop, "genome_001")

    assert pop.size == 0
    assert pop.avg_score == 0.0


# ═══════════════════════════════════════════════════════════
# AC4 — Fitness Update
# ═══════════════════════════════════════════════════════════

def test_ac4_update_fitness():
    """AC4a: Update fitness for a member."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(["genome_001"])

    fitness = _make_fitness("genome_001", 0.82)
    updated = manager.update_fitness(pop, "genome_001", fitness)

    assert updated.score == 0.82
    assert pop.get_member("genome_001").score == 0.82


def test_ac4b_update_fitness_not_found():
    """AC4b: Update fitness for non-existent genome raises ValueError."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    try:
        manager.update_fitness(pop, "nonexistent", _make_fitness("x", 0.5))
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_ac4c_update_fitness_batch():
    """AC4c: Batch update fitness for multiple members."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_001", "genome_002", "genome_003"],
    )

    manager.update_fitness_batch(pop, {
        "genome_001": _make_fitness("genome_001", 0.90),
        "genome_002": _make_fitness("genome_002", 0.60),
        "genome_003": _make_fitness("genome_003", 0.75),
    })

    assert pop.get_member("genome_001").score == 0.90
    assert pop.get_member("genome_002").score == 0.60
    assert pop.get_member("genome_003").score == 0.75


# ═══════════════════════════════════════════════════════════
# AC5 — Ranking
# ═══════════════════════════════════════════════════════════

def test_ac5_ranking():
    """AC5a: Rank members by score descending."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.60),
        "genome_C": _make_fitness("genome_C", 0.90),
    })

    manager.rank_members(pop)

    assert pop.get_member("genome_C").rank == 1  # 0.90
    assert pop.get_member("genome_A").rank == 2  # 0.80
    assert pop.get_member("genome_B").rank == 3  # 0.60


def test_ac5b_ranking_ties():
    """AC5b: Ranking with tied scores."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.80),
    })

    manager.rank_members(pop)

    # 相同分数，排名不同但顺序取决于排序稳定性
    ranks = {m.genome_id: m.rank for m in pop.members}
    assert set(ranks.values()) == {1, 2}


def test_ac5c_ranking_best_member():
    """AC5c: best_member after ranking."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.60),
        "genome_C": _make_fitness("genome_C", 0.90),
    })

    assert pop.best_member.genome_id == "genome_C"
    assert pop.best_score == 0.90


# ═══════════════════════════════════════════════════════════
# AC6 — Elite Query
# ═══════════════════════════════════════════════════════════

def test_ac6_top_candidates():
    """AC6a: get_top_candidates returns top_k."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C", "genome_D", "genome_E"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.60),
        "genome_C": _make_fitness("genome_C", 0.90),
        "genome_D": _make_fitness("genome_D", 0.70),
        "genome_E": _make_fitness("genome_E", 0.50),
    })

    top3 = manager.get_top_candidates(pop, top_k=3)

    assert len(top3) == 3
    assert top3[0].genome_id == "genome_C"  # 0.90
    assert top3[1].genome_id == "genome_A"  # 0.80
    assert top3[2].genome_id == "genome_D"  # 0.70


def test_ac6b_top_candidates_min_score():
    """AC6b: get_top_candidates with min_score filter."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.90),
        "genome_B": _make_fitness("genome_B", 0.40),
        "genome_C": _make_fitness("genome_C", 0.80),
    })

    top = manager.get_top_candidates(pop, top_k=5, min_score=0.5)

    assert len(top) == 2
    assert top[0].genome_id == "genome_A"
    assert top[1].genome_id == "genome_C"


def test_ac6c_mark_elite():
    """AC6c: mark_elite marks top performers."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C", "genome_D"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.90),
        "genome_B": _make_fitness("genome_B", 0.40),
        "genome_C": _make_fitness("genome_C", 0.80),
        "genome_D": _make_fitness("genome_D", 0.70),
    })

    manager.mark_elite(pop, top_k=2, min_score=0.5)

    assert pop.get_member("genome_A").is_elite is True
    assert pop.get_member("genome_C").is_elite is True
    assert pop.get_member("genome_D").is_elite is False  # rank 3
    assert pop.get_member("genome_B").is_elite is False  # score < 0.5
    assert pop.elite_count == 2


def test_ac6d_elite_below_threshold():
    """AC6d: Low-scoring candidate not elite even if top_k."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.30),
        "genome_B": _make_fitness("genome_B", 0.20),
    })

    manager.mark_elite(pop, top_k=2, min_score=0.5)

    # 分数都低于 0.5，无人成为精英
    assert pop.elite_count == 0


def test_ac6e_healthy_candidates():
    """AC6e: get_healthy_candidates returns score >= 0.5."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C"],
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.30),
        "genome_C": _make_fitness("genome_C", 0.60),
    })

    healthy = manager.get_healthy_candidates(pop)

    assert len(healthy) == 2
    ids = {m.genome_id for m in healthy}
    assert ids == {"genome_A", "genome_C"}


# ═══════════════════════════════════════════════════════════
# AC7 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac7_population_member_serialization():
    """AC7a: PopulationMember to_dict / from_dict roundtrip."""
    fitness = _make_fitness("genome_001", 0.82)
    member = PopulationMember(
        genome_id="genome_001",
        fitness=fitness,
        rank=1,
        is_elite=True,
    )

    d = member.to_dict()
    assert d["genome_id"] == "genome_001"
    assert d["rank"] == 1
    assert d["is_elite"] is True

    restored = PopulationMember.from_dict(d)
    assert restored.genome_id == member.genome_id
    assert restored.score == member.score
    assert restored.rank == member.rank
    assert restored.is_elite == member.is_elite


def test_ac7b_population_serialization():
    """AC7b: GenomePopulation to_dict / from_dict roundtrip."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B"],
        population_id="pop_001",
        generation=2,
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.80),
        "genome_B": _make_fitness("genome_B", 0.60),
    })
    manager.rank_members(pop)
    manager.mark_elite(pop, top_k=1)
    manager.mark_evaluated(pop)

    d = pop.to_dict()
    assert d["population_id"] == "pop_001"
    assert d["generation"] == 2
    assert len(d["members"]) == 2
    assert d["status"] == "evaluated"

    restored = GenomePopulation.from_dict(d)
    assert restored.population_id == pop.population_id
    assert restored.generation == pop.generation
    assert restored.size == pop.size
    assert restored.status == pop.status
    assert restored.avg_score == pop.avg_score
    assert restored.best_score == pop.best_score


def test_ac7c_population_stats():
    """AC7c: get_population_stats returns correct dict."""
    manager = PopulationManager()
    pop = manager.create_population_from_genomes(
        ["genome_A", "genome_B", "genome_C"],
        population_id="pop_001",
    )
    manager.update_fitness_batch(pop, {
        "genome_A": _make_fitness("genome_A", 0.90),
        "genome_B": _make_fitness("genome_B", 0.40),
        "genome_C": _make_fitness("genome_C", 0.70),
    })
    manager.mark_elite(pop, top_k=2)

    stats = manager.get_population_stats(pop)

    assert stats["population_id"] == "pop_001"
    assert stats["size"] == 3
    assert stats["best_genome"] == "genome_A"
    assert stats["elite_count"] == 2
    assert stats["healthy_count"] == 2


# ═══════════════════════════════════════════════════════════
# AC8 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac8_deterministic_population():
    """AC8a: Same genomes → same population stats."""
    def build():
        manager = PopulationManager()
        pop = manager.create_population_from_genomes(
            ["genome_A", "genome_B"],
        )
        manager.update_fitness_batch(pop, {
            "genome_A": _make_fitness("genome_A", 0.80),
            "genome_B": _make_fitness("genome_B", 0.60),
        })
        manager.rank_members(pop)
        return pop

    pop1 = build()
    pop2 = build()

    assert pop1.avg_score == pop2.avg_score
    assert pop1.best_score == pop2.best_score
    assert pop1.get_top_candidates(2)[0].genome_id == pop2.get_top_candidates(2)[0].genome_id


def test_ac8b_deterministic_ranking():
    """AC8b: Same scores → same ranking."""
    manager = PopulationManager()
    pop1 = manager.create_population_from_genomes(["genome_A", "genome_B", "genome_C"])
    pop2 = manager.create_population_from_genomes(["genome_A", "genome_B", "genome_C"])

    for pop in [pop1, pop2]:
        manager.update_fitness_batch(pop, {
            "genome_A": _make_fitness("genome_A", 0.90),
            "genome_B": _make_fitness("genome_B", 0.60),
            "genome_C": _make_fitness("genome_C", 0.75),
        })
        manager.rank_members(pop)

    assert pop1.get_member("genome_A").rank == pop2.get_member("genome_A").rank
    assert pop1.get_member("genome_B").rank == pop2.get_member("genome_B").rank
    assert pop1.get_member("genome_C").rank == pop2.get_member("genome_C").rank


def test_ac8c_status_transitions():
    """AC8c: Status transitions are deterministic."""
    manager = PopulationManager()
    pop = _make_population(manager=manager)

    assert pop.status == PopulationStatus.CREATED
    manager.activate(pop)
    assert pop.status == PopulationStatus.ACTIVE
    manager.mark_evaluated(pop)
    assert pop.status == PopulationStatus.EVALUATED
    manager.archive(pop)
    assert pop.status == PopulationStatus.ARCHIVED