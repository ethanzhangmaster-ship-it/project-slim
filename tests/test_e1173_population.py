"""E11.7.3 — Population Evolution Manager 测试。

测试范围：
  - Models: GenomeIndividual, GenomeStatus, PopulationSnapshot, PopulationDecision, PopulationSummary
  - PopulationEvaluator: evaluate, rank, top_n, bottom_n, middle, summary, snapshots
  - PopulationSelector: select (elite/mutate/retire), explore trigger, ratios, batch
  - DiversityEngine: calculate, Jaccard distance, is_diverse, needs_exploration, stagnant
  - PopulationEvolutionManager: register, create_population, evolve, evolve_multiple, queries, stats
  - Scheduler Integration: submit_population_decision
  - Controller Integration: manage_population, manage_population_and_tick, register_genome
  - Full Pipeline: Population → Evaluator → Diversity → Selector → Decision → Scheduler
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population.models import (
    GenomeIndividual,
    GenomeStatus,
    PopulationSnapshot,
    PopulationDecision,
    PopulationSummary,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population.evaluator import (
    PopulationEvaluator,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population.selector import (
    PopulationSelector,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population.diversity import (
    DiversityEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population.population_manager import (
    PopulationEvolutionManager,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.population import (
    GenomeIndividual as ExportedGenomeIndividual,
    GenomeStatus as ExportedGenomeStatus,
    PopulationSnapshot as ExportedPopulationSnapshot,
    PopulationDecision as ExportedPopulationDecision,
    PopulationSummary as ExportedPopulationSummary,
    PopulationEvaluator as ExportedPopulationEvaluator,
    PopulationSelector as ExportedPopulationSelector,
    DiversityEngine as ExportedDiversityEngine,
    PopulationEvolutionManager as ExportedPopulationEvolutionManager,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.scheduler.scheduler import (
    EvolutionScheduler,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.budget_manager import (
    EvolutionBudgetManager,
)
from market_ops.creative_vision_runtime.autonomous_controller.orchestrator.budget.models import (
    BudgetLevel,
)
from market_ops.creative_vision_runtime.autonomous_controller.controller import (
    AutonomousCreativeController,
)
from market_ops.creative_vision_runtime.intelligence.engine import (
    VisionIntelligenceEngine,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_individual(
    genome_id: str = "g001",
    fitness_score: float = 50.0,
    generation: int = 0,
    status: GenomeStatus = GenomeStatus.ACTIVE,
    mutation_count: int = 0,
    parent_id: str | None = None,
    features: dict | None = None,
    metadata: dict | None = None,
) -> GenomeIndividual:
    return GenomeIndividual(
        genome_id=genome_id,
        fitness_score=fitness_score,
        generation=generation,
        status=status,
        mutation_count=mutation_count,
        parent_id=parent_id,
        features=features or {},
        metadata=metadata or {},
    )


def _make_population(
    size: int = 10,
    base_fitness: float = 50.0,
    step: float = 10.0,
) -> list[GenomeIndividual]:
    """创建按 fitness 递减的种群。"""
    individuals = []
    for i in range(size):
        genome_id = f"g{i + 1:03d}"
        fitness = base_fitness + (size - i) * step
        individuals.append(_make_individual(
            genome_id=genome_id,
            fitness_score=fitness,
            features={"hook": f"hook_{i % 3}", "color": f"color_{i % 2}"},
        ))
    return individuals


def _make_genome_specs(
    size: int = 10,
    base_fitness: float = 50.0,
    step: float = 10.0,
) -> list[dict]:
    """创建基因组规格列表（用于 register_batch）。"""
    specs = []
    for i in range(size):
        genome_id = f"g{i + 1:03d}"
        fitness = base_fitness + (size - i) * step
        specs.append({
            "genome_id": genome_id,
            "fitness_score": fitness,
            "features": {"hook": f"hook_{i % 3}", "color": f"color_{i % 2}"},
        })
    return specs


# ═══════════════════════════════════════════════════════════
# 1. Models — 15 tests
# ═══════════════════════════════════════════════════════════

class TestGenomeStatus:
    """GenomeStatus 枚举测试。"""

    def test_status_values(self):
        assert GenomeStatus.ACTIVE.value == "active"
        assert GenomeStatus.ELITE.value == "elite"
        assert GenomeStatus.MUTATING.value == "mutating"
        assert GenomeStatus.RETIRED.value == "retired"
        assert GenomeStatus.FAILED.value == "failed"

    def test_status_count(self):
        assert len(GenomeStatus) == 5


class TestGenomeIndividual:
    """GenomeIndividual 测试。"""

    def test_create_default(self):
        ind = GenomeIndividual()
        assert ind.genome_id == ""
        assert ind.fitness_score == 0.0
        assert ind.generation == 0
        assert ind.status == GenomeStatus.ACTIVE
        assert ind.mutation_count == 0
        assert ind.parent_id is None
        assert ind.features == {}
        assert ind.metadata == {}

    def test_create_full(self):
        ind = _make_individual(
            genome_id="g001",
            fitness_score=85.5,
            generation=3,
            status=GenomeStatus.ELITE,
            mutation_count=2,
            parent_id="g000",
            features={"hook": "rescue", "color": "bright"},
            metadata={"source": "evolution"},
        )
        assert ind.genome_id == "g001"
        assert ind.fitness_score == 85.5
        assert ind.generation == 3
        assert ind.status == GenomeStatus.ELITE
        assert ind.mutation_count == 2
        assert ind.parent_id == "g000"
        assert ind.features == {"hook": "rescue", "color": "bright"}
        assert ind.metadata == {"source": "evolution"}

    def test_is_elite(self):
        assert _make_individual(status=GenomeStatus.ELITE).is_elite is True
        assert _make_individual(status=GenomeStatus.ACTIVE).is_elite is False

    def test_is_retired(self):
        assert _make_individual(status=GenomeStatus.RETIRED).is_retired is True
        assert _make_individual(status=GenomeStatus.ACTIVE).is_retired is False

    def test_is_active(self):
        assert _make_individual(status=GenomeStatus.ACTIVE).is_active is True
        assert _make_individual(status=GenomeStatus.ELITE).is_active is True
        assert _make_individual(status=GenomeStatus.MUTATING).is_active is True
        assert _make_individual(status=GenomeStatus.RETIRED).is_active is False
        assert _make_individual(status=GenomeStatus.FAILED).is_active is False

    def test_to_dict(self):
        ind = _make_individual(genome_id="g001", fitness_score=90.0, generation=1)
        d = ind.to_dict()
        assert d["genome_id"] == "g001"
        assert d["fitness_score"] == 90.0
        assert d["generation"] == 1
        assert d["status"] == "active"

    def test_repr(self):
        ind = _make_individual(genome_id="g001", fitness_score=90.0, generation=1)
        r = repr(ind)
        assert "g001" in r
        assert "90.0" in r


class TestPopulationSnapshot:
    """PopulationSnapshot 测试。"""

    def test_create_empty(self):
        snap = PopulationSnapshot()
        assert snap.population_id != ""
        assert snap.population_id.startswith("pop_")
        assert snap.generation == 0
        assert snap.individuals == []
        assert snap.avg_fitness == 0.0
        assert snap.total_count == 0
        assert snap.created_at != ""

    def test_create_with_individuals(self):
        inds = [_make_individual("g001", 90.0), _make_individual("g002", 70.0)]
        snap = PopulationSnapshot(
            generation=1,
            individuals=inds,
            avg_fitness=80.0,
            min_fitness=70.0,
            max_fitness=90.0,
            diversity_score=0.5,
            elite_count=1,
        )
        assert snap.generation == 1
        assert snap.total_count == 2
        assert snap.avg_fitness == 80.0
        assert snap.min_fitness == 70.0
        assert snap.max_fitness == 90.0
        assert snap.diversity_score == 0.5
        assert snap.elite_count == 1

    def test_to_dict(self):
        snap = PopulationSnapshot(generation=1, avg_fitness=80.0)
        d = snap.to_dict()
        assert d["generation"] == 1
        assert d["avg_fitness"] == 80.0
        assert "population_id" in d
        assert "created_at" in d

    def test_repr(self):
        snap = PopulationSnapshot(generation=1, total_count=10, avg_fitness=75.0, diversity_score=0.5)
        r = repr(snap)
        assert "gen=1" in r
        assert "size=10" in r


class TestPopulationDecision:
    """PopulationDecision 测试。"""

    def test_create_default(self):
        d = PopulationDecision()
        assert d.decision_id != ""
        assert d.decision_id.startswith("pd_")
        assert d.generation == 0
        assert d.elite == []
        assert d.mutate == []
        assert d.retire == []
        assert d.explore == []
        assert d.diversity_score == 0.0
        assert d.needs_exploration is False

    def test_create_full(self):
        d = PopulationDecision(
            generation=2,
            elite=["g001", "g002"],
            mutate=["g003", "g004", "g005"],
            retire=["g008", "g009", "g010"],
            explore=["g003"],
            diversity_score=0.15,
            needs_exploration=True,
            summary="Gen 2: 2 elite, 3 mutate, 3 retire, 1 explore",
        )
        assert d.generation == 2
        assert len(d.elite) == 2
        assert len(d.mutate) == 3
        assert len(d.retire) == 3
        assert len(d.explore) == 1
        assert d.needs_exploration is True

    def test_total_actions(self):
        d = PopulationDecision(
            elite=["g001"], mutate=["g003", "g004"], retire=["g008"], explore=["g003"]
        )
        # elite(1) + mutate(2) + retire(1) + explore(1) = 5
        assert d.total_actions == 5

    def test_mutation_count(self):
        d = PopulationDecision(mutate=["g003", "g004"], explore=["g005"])
        assert d.mutation_count == 3

    def test_to_dict(self):
        d = PopulationDecision(generation=1, elite=["g001"], mutate=["g003"])
        dd = d.to_dict()
        assert dd["generation"] == 1
        assert dd["elite"] == ["g001"]
        assert dd["mutate"] == ["g003"]

    def test_repr(self):
        d = PopulationDecision(
            generation=1, elite=["g001"], mutate=["g003", "g004"], retire=["g008"]
        )
        r = repr(d)
        assert "elite=1" in r
        assert "mutate=2" in r
        assert "retire=1" in r


class TestPopulationSummary:
    """PopulationSummary 测试。"""

    def test_create_default(self):
        s = PopulationSummary()
        assert s.total_individuals == 0
        assert s.active_count == 0
        assert s.elite_count == 0
        assert s.retired_count == 0
        assert s.avg_fitness == 0.0
        assert s.best_fitness == 0.0
        assert s.diversity_score == 0.0
        assert s.total_generations == 0

    def test_create_full(self):
        s = PopulationSummary(
            total_individuals=10,
            active_count=7,
            elite_count=2,
            retired_count=3,
            avg_fitness=75.0,
            best_fitness=95.0,
            diversity_score=0.45,
            total_generations=3,
        )
        assert s.total_individuals == 10
        assert s.active_count == 7
        assert s.elite_count == 2
        assert s.retired_count == 3
        assert s.avg_fitness == 75.0
        assert s.best_fitness == 95.0
        assert s.diversity_score == 0.45
        assert s.total_generations == 3

    def test_to_dict(self):
        s = PopulationSummary(total_individuals=10, avg_fitness=75.0)
        d = s.to_dict()
        assert d["total_individuals"] == 10
        assert d["avg_fitness"] == 75.0


# ═══════════════════════════════════════════════════════════
# 2. PopulationEvaluator — 15 tests
# ═══════════════════════════════════════════════════════════

class TestPopulationEvaluator:
    """PopulationEvaluator 测试。"""

    def test_evaluate_empty(self):
        evaluator = PopulationEvaluator()
        snap = evaluator.evaluate([], generation=0)
        assert snap.total_count == 0
        assert snap.avg_fitness == 0.0
        assert evaluator.evaluate_count == 1

    def test_evaluate_single(self):
        evaluator = PopulationEvaluator()
        ind = _make_individual("g001", 90.0)
        snap = evaluator.evaluate([ind], generation=0)
        assert snap.total_count == 1
        assert snap.avg_fitness == 90.0
        assert snap.min_fitness == 90.0
        assert snap.max_fitness == 90.0

    def test_evaluate_multiple(self):
        evaluator = PopulationEvaluator()
        inds = [_make_individual("g001", 90.0), _make_individual("g002", 70.0), _make_individual("g003", 50.0)]
        snap = evaluator.evaluate(inds, generation=1)
        assert snap.total_count == 3
        assert snap.avg_fitness == 70.0
        assert snap.min_fitness == 50.0
        assert snap.max_fitness == 90.0
        assert snap.generation == 1

    def test_evaluate_counts_elite(self):
        evaluator = PopulationEvaluator()
        inds = [
            _make_individual("g001", 90.0, status=GenomeStatus.ELITE),
            _make_individual("g002", 70.0, status=GenomeStatus.ELITE),
            _make_individual("g003", 50.0),
        ]
        snap = evaluator.evaluate(inds)
        assert snap.elite_count == 2

    def test_evaluate_increments_count(self):
        evaluator = PopulationEvaluator()
        evaluator.evaluate([_make_individual("g001", 50.0)])
        evaluator.evaluate([_make_individual("g002", 60.0)])
        assert evaluator.evaluate_count == 2

    def test_rank_descending(self):
        inds = [_make_individual("g001", 50.0), _make_individual("g002", 90.0), _make_individual("g003", 70.0)]
        ranked = PopulationEvaluator.rank(inds)
        assert ranked[0].genome_id == "g002"
        assert ranked[0].fitness_score == 90.0
        assert ranked[1].genome_id == "g003"
        assert ranked[2].genome_id == "g001"

    def test_rank_sets_metadata(self):
        inds = [_make_individual("g001", 90.0), _make_individual("g002", 50.0)]
        ranked = PopulationEvaluator.rank(inds)
        assert ranked[0].metadata["rank"] == 1
        assert ranked[1].metadata["rank"] == 2

    def test_get_top_n(self):
        inds = [_make_individual(f"g{i:03d}", i * 10.0) for i in range(10)]
        top = PopulationEvaluator.get_top_n(inds, 3)
        assert len(top) == 3
        assert top[0].fitness_score == 90.0
        assert top[1].fitness_score == 80.0

    def test_get_top_n_returns_all_if_n_exceeds_size(self):
        inds = [_make_individual("g001", 50.0)]
        top = PopulationEvaluator.get_top_n(inds, 5)
        assert len(top) == 1

    def test_get_bottom_n(self):
        inds = [_make_individual(f"g{i:03d}", i * 10.0) for i in range(10)]
        bottom = PopulationEvaluator.get_bottom_n(inds, 3)
        assert len(bottom) == 3
        assert bottom[0].fitness_score == 0.0

    def test_get_middle(self):
        inds = [_make_individual(f"g{i:03d}", i * 10.0) for i in range(10)]  # 0~90
        middle = PopulationEvaluator.get_middle(inds, top_ratio=0.2, bottom_ratio=0.3)
        # top 2 (g009 90, g008 80), bottom 3 (g002 20, g001 10, g000 0), middle = 5
        assert len(middle) == 5

    def test_summary(self):
        inds = [
            _make_individual("g001", 90.0, status=GenomeStatus.ELITE),
            _make_individual("g002", 70.0),
            _make_individual("g003", 50.0, status=GenomeStatus.RETIRED),
        ]
        s = PopulationEvaluator.summary(inds, diversity_score=0.5)
        assert s.total_individuals == 3
        assert s.active_count == 2
        assert s.elite_count == 1
        assert s.retired_count == 1
        assert s.avg_fitness == 70.0
        assert s.best_fitness == 90.0
        assert s.diversity_score == 0.5

    def test_summary_empty(self):
        s = PopulationEvaluator.summary([])
        assert s.total_individuals == 0
        assert s.avg_fitness == 0.0

    def test_snapshots_accumulate(self):
        evaluator = PopulationEvaluator()
        evaluator.evaluate([_make_individual("g001", 50.0)], generation=0)
        evaluator.evaluate([_make_individual("g002", 60.0)], generation=1)
        assert len(evaluator.get_snapshots()) == 2

    def test_get_snapshot_by_generation(self):
        evaluator = PopulationEvaluator()
        evaluator.evaluate([_make_individual("g001", 50.0)], generation=0)
        evaluator.evaluate([_make_individual("g002", 60.0)], generation=1)
        snap = evaluator.get_snapshot_by_generation(1)
        assert snap is not None
        assert snap.generation == 1

    def test_get_snapshot_by_generation_not_found(self):
        evaluator = PopulationEvaluator()
        assert evaluator.get_snapshot_by_generation(99) is None

    def test_reset(self):
        evaluator = PopulationEvaluator()
        evaluator.evaluate([_make_individual("g001", 50.0)])
        evaluator.reset()
        assert evaluator.evaluate_count == 0
        assert len(evaluator.get_snapshots()) == 0

    def test_get_stats(self):
        evaluator = PopulationEvaluator()
        evaluator.evaluate([_make_individual("g001", 50.0)])
        stats = evaluator.get_stats()
        assert stats["evaluate_count"] == 1
        assert stats["snapshots_count"] == 1


# ═══════════════════════════════════════════════════════════
# 3. PopulationSelector — 20 tests
# ═══════════════════════════════════════════════════════════

class TestPopulationSelector:
    """PopulationSelector 测试。"""

    def test_create_default_ratios(self):
        selector = PopulationSelector()
        assert selector.elite_ratio == 0.2
        assert selector.mutate_ratio == 0.5
        assert selector.retire_ratio == 0.3

    def test_create_custom_ratios(self):
        selector = PopulationSelector(elite_ratio=0.1, mutate_ratio=0.6, retire_ratio=0.3)
        assert selector.elite_ratio == 0.1
        assert selector.mutate_ratio == 0.6

    def test_ratios_must_sum_to_one(self):
        with pytest.raises(ValueError, match="must equal 1.0"):
            PopulationSelector(elite_ratio=0.5, mutate_ratio=0.5, retire_ratio=0.5)

    def test_select_empty_population(self):
        selector = PopulationSelector()
        decision = selector.select([], generation=0)
        assert decision.elite == []
        assert decision.mutate == []
        assert decision.retire == []
        assert decision.summary == "Empty population"

    def test_select_10_population(self):
        """10 个个体：2 elite, 5 mutate, 3 retire。"""
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0, diversity_score=0.5)
        assert len(decision.elite) == 2
        assert len(decision.mutate) == 5
        assert len(decision.retire) == 3
        assert len(decision.explore) == 0
        assert decision.needs_exploration is False

    def test_select_elite_are_top_fitness(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0)
        # elite 应该是前2名
        assert decision.elite[0] == "g001"  # highest fitness
        assert decision.elite[1] == "g002"

    def test_select_retire_are_bottom_fitness(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0)
        # retire 应该是最后3名
        assert "g008" in decision.retire
        assert "g009" in decision.retire
        assert "g010" in decision.retire

    def test_select_sets_status_elite(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        selector.select(inds, generation=0)
        for ind in inds[:2]:
            assert ind.status == GenomeStatus.ELITE

    def test_select_sets_status_mutating(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        selector.select(inds, generation=0)
        mutating = [ind for ind in inds if ind.status == GenomeStatus.MUTATING]
        assert len(mutating) == 5

    def test_select_sets_status_retired(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        selector.select(inds, generation=0)
        retired = [ind for ind in inds if ind.status == GenomeStatus.RETIRED]
        assert len(retired) == 3

    def test_select_min_population_no_retire(self):
        """种群 <= min_population 时不退役。"""
        selector = PopulationSelector(min_population=5)
        inds = _make_population(4)  # 4 < 5
        decision = selector.select(inds, generation=0)
        assert len(decision.retire) == 0

    def test_select_above_min_population_retires(self):
        selector = PopulationSelector(min_population=5)
        inds = _make_population(6)  # 6 > 5
        decision = selector.select(inds, generation=0)
        assert len(decision.retire) > 0

    def test_select_triggers_explore_on_low_diversity(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0, diversity_score=0.1)
        assert decision.needs_exploration is True
        assert len(decision.explore) > 0

    def test_select_no_explore_on_high_diversity(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0, diversity_score=0.8)
        assert decision.needs_exploration is False
        assert len(decision.explore) == 0

    def test_select_explore_from_mutate_pool(self):
        """探索个体从突变池中取。"""
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=0, diversity_score=0.1)
        for explore_id in decision.explore:
            assert explore_id in decision.mutate

    def test_select_increments_count(self):
        selector = PopulationSelector()
        selector.select(_make_population(10))
        selector.select(_make_population(10))
        assert selector.select_count == 2

    def test_set_ratios(self):
        selector = PopulationSelector()
        selector.set_ratios(elite_ratio=0.3, mutate_ratio=0.4, retire_ratio=0.3)
        assert selector.elite_ratio == 0.3
        assert selector.mutate_ratio == 0.4
        assert selector.retire_ratio == 0.3

    def test_set_ratios_partial(self):
        selector = PopulationSelector()
        selector.set_ratios(elite_ratio=0.3)
        assert selector.elite_ratio == 0.3
        assert selector.mutate_ratio == 0.5  # unchanged

    def test_select_batch(self):
        selector = PopulationSelector()
        snapshots = [(_make_population(5), 0, 0.5), (_make_population(5), 1, 0.4)]
        decisions = selector.select_batch(snapshots)
        assert len(decisions) == 2
        assert decisions[0].generation == 0
        assert decisions[1].generation == 1

    def test_select_summary_contains_counts(self):
        selector = PopulationSelector()
        inds = _make_population(10)
        decision = selector.select(inds, generation=2, diversity_score=0.5)
        assert "Gen 2" in decision.summary
        assert "elite" in decision.summary
        assert "mutate" in decision.summary
        assert "retire" in decision.summary

    def test_get_stats(self):
        selector = PopulationSelector()
        selector.select(_make_population(10))
        stats = selector.get_stats()
        assert stats["select_count"] == 1
        assert stats["elite_ratio"] == 0.2

    def test_reset(self):
        selector = PopulationSelector()
        selector.select(_make_population(10))
        selector.reset()
        assert selector.select_count == 0


# ═══════════════════════════════════════════════════════════
# 4. DiversityEngine — 15 tests
# ═══════════════════════════════════════════════════════════

class TestDiversityEngine:
    """DiversityEngine 测试。"""

    def test_calculate_empty(self):
        engine = DiversityEngine()
        assert engine.calculate([]) == 0.0

    def test_calculate_single_individual(self):
        engine = DiversityEngine()
        inds = [_make_individual("g001", features={"hook": "rescue"})]
        assert engine.calculate(inds) == 0.0

    def test_calculate_identical(self):
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={"hook": "rescue", "color": "bright"}),
            _make_individual("g002", features={"hook": "rescue", "color": "bright"}),
        ]
        # identical features → Jaccard distance = 0
        assert engine.calculate(inds) == 0.0

    def test_calculate_completely_different(self):
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={"hook": "rescue", "color": "bright"}),
            _make_individual("g002", features={"hook": "challenge", "color": "dark"}),
        ]
        # 4 unique features, 0 shared → Jaccard = 1 - 0/4 = 1.0
        assert engine.calculate(inds) == 1.0

    def test_calculate_partial_overlap(self):
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={"hook": "rescue", "color": "bright"}),
            _make_individual("g002", features={"hook": "rescue", "color": "dark"}),
        ]
        # features: hook:rescue, color:bright, color:dark → 3 total, 1 shared
        # Jaccard = 1 - 1/3 = 0.6667
        score = engine.calculate(inds)
        assert 0.6 < score < 0.7

    def test_calculate_multiple_individuals(self):
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={"hook": "rescue", "color": "bright"}),
            _make_individual("g002", features={"hook": "challenge", "color": "dark"}),
            _make_individual("g003", features={"hook": "rescue", "color": "dark"}),
        ]
        score = engine.calculate(inds)
        assert 0.0 <= score <= 1.0

    def test_calculate_with_list_features(self):
        """列表类型特征值展开为多个 key:value 对。"""
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={"tags": ["a", "b"]}),
            _make_individual("g002", features={"tags": ["c", "d"]}),
        ]
        # tags:a, tags:b vs tags:c, tags:d → 4 unique, 0 shared → 1.0
        assert engine.calculate(inds) == 1.0

    def test_calculate_no_features_uses_genome_id(self):
        """无特征时使用 genome_id 作为最小特征。"""
        engine = DiversityEngine()
        inds = [
            _make_individual("g001", features={}),
            _make_individual("g002", features={}),
        ]
        # id:g001 vs id:g002 → 2 unique, 0 shared → 1.0
        assert engine.calculate(inds) == 1.0

    def test_is_diverse_below_threshold(self):
        engine = DiversityEngine(diversity_threshold=0.2)
        inds = [
            _make_individual("g001", features={"hook": "rescue"}),
            _make_individual("g002", features={"hook": "rescue"}),
        ]
        assert engine.is_diverse(inds) is False

    def test_is_diverse_above_threshold(self):
        engine = DiversityEngine(diversity_threshold=0.2)
        inds = [
            _make_individual("g001", features={"hook": "rescue"}),
            _make_individual("g002", features={"hook": "challenge"}),
        ]
        assert engine.is_diverse(inds) is True

    def test_needs_exploration(self):
        engine = DiversityEngine(diversity_threshold=0.2)
        inds = [
            _make_individual("g001", features={"hook": "rescue"}),
            _make_individual("g002", features={"hook": "rescue"}),
        ]
        assert engine.needs_exploration(inds) is True

    def test_is_stagnant_false_with_insufficient_history(self):
        engine = DiversityEngine()
        assert engine.is_stagnant(window=3) is False

    def test_is_stagnant_true(self):
        engine = DiversityEngine()
        engine._history = [0.5, 0.51, 0.50]  # max-min = 0.01 < 0.05
        assert engine.is_stagnant(window=3) is True

    def test_is_stagnant_false_with_variation(self):
        engine = DiversityEngine()
        engine._history = [0.1, 0.5, 0.9]  # max-min = 0.8 > 0.05
        assert engine.is_stagnant(window=3) is False

    def test_calculate_batch(self):
        engine = DiversityEngine()
        pops = [
            [_make_individual("g001", features={"hook": "a"}), _make_individual("g002", features={"hook": "b"})],
            [_make_individual("g003", features={"hook": "a"}), _make_individual("g004", features={"hook": "a"})],
        ]
        scores = engine.calculate_batch(pops)
        assert len(scores) == 2
        assert scores[0] == 1.0  # completely different
        assert scores[1] == 0.0  # identical

    def test_get_history(self):
        engine = DiversityEngine()
        engine.calculate([_make_individual("g001", features={"hook": "a"}), _make_individual("g002", features={"hook": "b"})])
        h = engine.get_history()
        assert len(h) == 1
        assert h[0] == 1.0

    def test_get_average_diversity(self):
        engine = DiversityEngine()
        engine._history = [0.2, 0.4, 0.6]
        assert engine.get_average_diversity() == 0.4

    def test_reset(self):
        engine = DiversityEngine()
        engine.calculate([_make_individual("g001", features={"hook": "a"}), _make_individual("g002", features={"hook": "b"})])
        engine.reset()
        assert engine.calculate_count == 0
        assert engine.get_history() == []


# ═══════════════════════════════════════════════════════════
# 5. PopulationEvolutionManager — 25 tests
# ═══════════════════════════════════════════════════════════

class TestPopulationEvolutionManager:
    """PopulationEvolutionManager 测试。"""

    # ── 注册 ──

    def test_register_single(self):
        manager = PopulationEvolutionManager()
        ind = manager.register(genome_id="g001", fitness_score=85.0)
        assert ind.genome_id == "g001"
        assert ind.fitness_score == 85.0
        assert manager.population_size == 1

    def test_register_with_features(self):
        manager = PopulationEvolutionManager()
        ind = manager.register(
            genome_id="g001",
            fitness_score=90.0,
            features={"hook": "rescue", "color": "bright"},
            parent_id="g000",
            metadata={"source": "mutation"},
        )
        assert ind.features == {"hook": "rescue", "color": "bright"}
        assert ind.parent_id == "g000"
        assert ind.metadata == {"source": "mutation"}

    def test_register_batch(self):
        manager = PopulationEvolutionManager()
        specs = _make_genome_specs(10)
        inds = manager.register_batch(specs)
        assert len(inds) == 10
        assert manager.population_size == 10

    def test_create_population(self):
        manager = PopulationEvolutionManager()
        specs = _make_genome_specs(5)
        inds = manager.create_population(specs)
        assert len(inds) == 5
        assert manager.generation == 0
        assert manager.population_size == 5

    def test_create_population_resets(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(3))
        manager.evolve()  # generation → 1
        # 重新创建应重置
        manager.create_population(_make_genome_specs(5))
        assert manager.generation == 0
        assert manager.population_size == 5

    # ── evolve ──

    def test_evolve_returns_decision(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        decision = manager.evolve()
        assert isinstance(decision, PopulationDecision)
        assert decision.generation == 0
        assert len(decision.elite) > 0
        assert len(decision.mutate) > 0

    def test_evolve_increments_generation(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        assert manager.generation == 0
        manager.evolve()
        assert manager.generation == 1
        manager.evolve()
        assert manager.generation == 2

    def test_evolve_10_population_ratios(self):
        """10 个体：2 elite, 5 mutate, 3 retire。"""
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        decision = manager.evolve()
        assert len(decision.elite) == 2
        assert len(decision.mutate) == 5
        assert len(decision.retire) == 3

    def test_evolve_20_population_ratios(self):
        """20 个体：4 elite, 10 mutate, 6 retire。"""
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(20))
        decision = manager.evolve()
        assert len(decision.elite) == 4
        assert len(decision.mutate) == 10
        assert len(decision.retire) == 6

    def test_evolve_updates_individual_status(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        elite = manager.get_elite()
        retired = manager.get_retired()
        assert len(elite) == 2
        assert len(retired) == 3

    def test_evolve_with_low_diversity_triggers_explore(self):
        manager = PopulationEvolutionManager()
        # 所有个体特征相同 → diversity = 0
        specs = [
            {"genome_id": f"g{i:03d}", "fitness_score": 50.0 + i * 10, "features": {"hook": "same"}}
            for i in range(10)
        ]
        manager.create_population(specs)
        decision = manager.evolve()
        assert decision.needs_exploration is True
        assert len(decision.explore) > 0

    def test_evolve_high_diversity_no_explore(self):
        manager = PopulationEvolutionManager()
        # 所有个体特征不同 → diversity = 1.0
        specs = [
            {"genome_id": f"g{i:03d}", "fitness_score": 50.0 + i * 10, "features": {"hook": f"unique_{i}"}}
            for i in range(10)
        ]
        manager.create_population(specs)
        decision = manager.evolve()
        assert decision.needs_exploration is False
        assert len(decision.explore) == 0

    def test_evolve_multiple(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        decisions = manager.evolve_multiple(3)
        assert len(decisions) == 3
        assert manager.generation == 3

    def test_evolve_stores_decisions(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        manager.evolve()
        assert len(manager.get_decisions()) == 2

    def test_evolve_empty_population(self):
        manager = PopulationEvolutionManager()
        manager.create_population([])
        decision = manager.evolve()
        assert decision.elite == []
        assert decision.mutate == []
        assert decision.retire == []

    # ── 查询 ──

    def test_get_individual(self):
        manager = PopulationEvolutionManager()
        manager.register("g001", 90.0)
        ind = manager.get_individual("g001")
        assert ind is not None
        assert ind.genome_id == "g001"

    def test_get_individual_not_found(self):
        manager = PopulationEvolutionManager()
        assert manager.get_individual("nonexistent") is None

    def test_get_active_individuals(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()  # 2 elite, 5 mutate, 3 retire
        active = manager.get_active_individuals()
        assert len(active) == 7  # 2 elite + 5 mutate

    def test_get_elite(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        assert len(manager.get_elite()) == 2

    def test_get_retired(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        assert len(manager.get_retired()) == 3

    def test_get_by_status(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        mutating = manager.get_by_status(GenomeStatus.MUTATING)
        assert len(mutating) == 5

    def test_get_individuals_by_generation(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(3))
        gen0 = manager.get_individuals_by_generation(0)
        assert len(gen0) == 3

    def test_get_population_snapshot(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        snap = manager.get_population_snapshot()
        assert isinstance(snap, PopulationSnapshot)
        assert snap.total_count == 10

    def test_get_summary(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        summary = manager.get_summary()
        assert isinstance(summary, PopulationSummary)
        assert summary.total_individuals == 10

    def test_get_latest_decision(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        d = manager.get_latest_decision()
        assert d is not None
        assert d.generation == 0

    # ── 属性 ──

    def test_properties(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        assert manager.population_size == 10
        assert manager.active_count == 7
        assert manager.elite_count == 2
        assert manager.retired_count == 3

    def test_get_stats(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        stats = manager.get_stats()
        assert stats["generation"] == 1
        assert stats["population_size"] == 10
        assert "summary" in stats
        assert "evaluator" in stats
        assert "selector" in stats
        assert "diversity" in stats
        assert "decisions_count" in stats

    def test_reset(self):
        manager = PopulationEvolutionManager()
        manager.create_population(_make_genome_specs(10))
        manager.evolve()
        manager.reset()
        assert manager.population_size == 0
        assert manager.generation == 0
        assert manager.get_latest_decision() is None


# ═══════════════════════════════════════════════════════════
# 6. Scheduler Integration — 10 tests
# ═══════════════════════════════════════════════════════════

class TestSchedulerPopulationIntegration:
    """Scheduler + PopulationDecision 集成测试。"""

    def test_submit_population_decision(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=1,
            elite=["g001", "g002"],
            mutate=["g003", "g004", "g005"],
            retire=["g008", "g009", "g010"],
            diversity_score=0.5,
        )
        result = scheduler.submit_population_decision(decision)
        assert result["total_tasks"] == 8  # 2 + 3 + 3
        assert len(result["elite_tasks"]) == 2
        assert len(result["mutate_tasks"]) == 3
        assert len(result["retire_tasks"]) == 3
        assert len(result["explore_tasks"]) == 0
        assert result["rejected_count"] == 0

    def test_submit_population_decision_with_explore(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=1,
            elite=["g001"],
            mutate=["g003", "g004", "g005"],
            explore=["g003"],
            retire=["g008"],
            needs_exploration=True,
        )
        result = scheduler.submit_population_decision(decision)
        # elite(1) + mutate(3) + retire(1) + explore(1) = 6
        assert result["total_tasks"] == 6
        assert len(result["explore_tasks"]) == 1

    def test_submit_population_decision_empty(self):
        scheduler = EvolutionScheduler()
        decision = PopulationDecision(generation=0)
        result = scheduler.submit_population_decision(decision)
        assert result["total_tasks"] == 0

    def test_submit_population_decision_tasks_have_metadata(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=2,
            elite=["g001"],
            mutate=["g003"],
            retire=["g008"],
        )
        result = scheduler.submit_population_decision(decision)
        # 检查任务携带了正确的 metadata
        elite_task = scheduler.get_task(result["elite_tasks"][0])
        assert elite_task is not None
        assert elite_task.metadata["decision_id"] == decision.decision_id
        assert elite_task.metadata["generation"] == 2
        assert elite_task.metadata["source"] == "population_decision"

    def test_submit_population_decision_task_actions(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=1,
            elite=["g001"],
            mutate=["g003"],
            retire=["g008"],
        )
        result = scheduler.submit_population_decision(decision)
        elite_task = scheduler.get_task(result["elite_tasks"][0])
        mutate_task = scheduler.get_task(result["mutate_tasks"][0])
        retire_task = scheduler.get_task(result["retire_tasks"][0])
        assert elite_task.action == "keep"
        assert mutate_task.action == "mutate"
        assert retire_task.action == "retire"

    def test_submit_population_decision_task_priorities(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=1,
            elite=["g001"],
            mutate=["g003"],
            retire=["g008"],
        )
        result = scheduler.submit_population_decision(decision)
        elite_task = scheduler.get_task(result["elite_tasks"][0])
        mutate_task = scheduler.get_task(result["mutate_tasks"][0])
        retire_task = scheduler.get_task(result["retire_tasks"][0])
        assert elite_task.priority == 10
        assert mutate_task.priority == 60
        assert retire_task.priority == 100

    def test_submit_population_decision_with_budget_rejection(self):
        """预算锁定时应拒绝所有任务。"""
        budget = EvolutionBudgetManager()
        budget.lock()
        scheduler = EvolutionScheduler(max_parallel=10, budget_manager=budget)
        decision = PopulationDecision(
            generation=1,
            elite=["g001"],
            mutate=["g003"],
        )
        result = scheduler.submit_population_decision(decision)
        assert result["total_tasks"] == 0
        assert result["rejected_count"] == 2

    def test_submit_population_decision_respects_budget_limit(self):
        """保守预算限制任务数量。"""
        budget = EvolutionBudgetManager()
        budget.set_level(BudgetLevel.CONSERVATIVE)  # 20 tasks max
        scheduler = EvolutionScheduler(max_parallel=50, budget_manager=budget)
        # 创建 30 个 mutate 任务
        decision = PopulationDecision(
            generation=1,
            mutate=[f"g{i:03d}" for i in range(30)],
        )
        result = scheduler.submit_population_decision(decision)
        # 预算限制下应有部分被拒绝
        assert result["rejected_count"] > 0

    def test_submit_population_decision_with_tick(self):
        scheduler = EvolutionScheduler(max_parallel=10)
        decision = PopulationDecision(
            generation=1,
            mutate=["g001", "g002", "g003"],
        )
        result = scheduler.submit_population_decision(decision)
        assert result["total_tasks"] == 3
        # tick 执行
        started = scheduler.tick()
        assert len(started) == 3

    def test_scheduler_population_manager_property(self):
        pop_mgr = PopulationEvolutionManager()
        scheduler = EvolutionScheduler(population_manager=pop_mgr)
        assert scheduler.population_manager is pop_mgr


# ═══════════════════════════════════════════════════════════
# 7. Controller Integration — 10 tests
# ═══════════════════════════════════════════════════════════

class TestControllerPopulationIntegration:
    """Controller + Population Manager 集成测试。"""

    @pytest.fixture
    def controller(self):
        """创建带有 mock intelligence engine 的 controller。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        return AutonomousCreativeController(intelligence_engine=mock_intel)

    def test_manage_population(self, controller):
        specs = _make_genome_specs(10)
        fitness_map = {"g001": 95.0, "g002": 85.0}
        result = controller.manage_population(specs, fitness_map)

        assert "decision" in result
        assert "snapshot" in result
        assert "summary" in result
        assert "scheduler_result" in result
        assert "started_tasks" in result

        decision = result["decision"]
        assert isinstance(decision, PopulationDecision)
        assert decision.generation == 0

    def test_manage_population_elite_from_fitness_map(self, controller):
        specs = _make_genome_specs(10)  # g001=150, g002=140, g003=130, ...
        # fitness_map 必须高于初始值才能让 g001, g002 成为精英
        fitness_map = {"g001": 200.0, "g002": 190.0}
        result = controller.manage_population(specs, fitness_map)
        decision = result["decision"]
        assert "g001" in decision.elite
        assert "g002" in decision.elite

    def test_manage_population_with_tick(self, controller):
        specs = _make_genome_specs(10)
        result = controller.manage_population(specs, tick=True)
        assert result["started_tasks"] is not None
        assert len(result["started_tasks"]) > 0

    def test_manage_population_and_tick(self, controller):
        specs = _make_genome_specs(10)
        result = controller.manage_population_and_tick(specs)
        assert result["started_tasks"] is not None
        assert len(result["started_tasks"]) > 0

    def test_manage_population_empty(self, controller):
        result = controller.manage_population([])
        decision = result["decision"]
        assert decision.elite == []
        assert decision.mutate == []
        assert decision.retire == []

    def test_register_genome(self, controller):
        ind = controller.register_genome(
            genome_id="g001",
            fitness_score=90.0,
            features={"hook": "rescue"},
        )
        assert ind.genome_id == "g001"
        assert ind.fitness_score == 90.0
        assert ind.features == {"hook": "rescue"}

    def test_get_population_summary(self, controller):
        controller.register_genome("g001", 90.0, features={"hook": "rescue"})
        controller.register_genome("g002", 70.0)
        controller.register_genome("g003", 50.0)
        summary = controller.get_population_summary()
        assert summary.total_individuals == 3
        assert summary.avg_fitness > 0

    def test_population_manager_property(self, controller):
        pm = controller.population_manager
        assert isinstance(pm, PopulationEvolutionManager)

    def test_manage_population_with_budget_manager(self, controller):
        """Controller 的 budget manager 应在 scheduler 中生效。"""
        # 先锁定预算
        controller.budget_manager.lock()
        specs = _make_genome_specs(10)
        result = controller.manage_population(specs)
        # 所有任务被预算拒绝
        assert result["scheduler_result"]["total_tasks"] == 0

    def test_manage_population_multiple_generations(self, controller):
        """多次调用 manage_population 应逐代进化。"""
        specs = _make_genome_specs(10)
        r1 = controller.manage_population(specs)
        assert r1["decision"].generation == 0

        r2 = controller.manage_population(specs)
        assert r2["decision"].generation == 0  # create_population 重置了


# ═══════════════════════════════════════════════════════════
# 8. Full Pipeline — 10 tests
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路测试：Population → Evolution → Scheduler。"""

    def test_pipeline_population_to_scheduler(self):
        """完整链路：Population → Evaluator → Diversity → Selector → Decision → Scheduler。"""
        # 创建管理器
        manager = PopulationEvolutionManager()
        scheduler = EvolutionScheduler(max_parallel=10, population_manager=manager)

        # 注册种群
        manager.create_population(_make_genome_specs(10))

        # 进化
        decision = manager.evolve()

        # 提交到 Scheduler
        result = scheduler.submit_population_decision(decision)
        assert result["total_tasks"] > 0

        # 执行
        started = scheduler.tick()
        assert len(started) == result["total_tasks"]

    def test_pipeline_multi_generation(self):
        """多代进化管道。"""
        manager = PopulationEvolutionManager()
        scheduler = EvolutionScheduler(max_parallel=20, population_manager=manager)

        manager.create_population(_make_genome_specs(10))

        for gen in range(3):
            decision = manager.evolve()
            assert decision.generation == gen
            result = scheduler.submit_population_decision(decision)
            assert result["total_tasks"] > 0

        assert manager.generation == 3

    def test_pipeline_explore_on_low_diversity(self):
        """低多样性 → 触发探索 → 探索任务提交。"""
        manager = PopulationEvolutionManager()
        scheduler = EvolutionScheduler(max_parallel=10, population_manager=manager)

        # 所有个体特征相同
        specs = [
            {"genome_id": f"g{i:03d}", "fitness_score": 50.0 + i * 10, "features": {"hook": "same"}}
            for i in range(10)
        ]
        manager.create_population(specs)
        decision = manager.evolve()
        assert decision.needs_exploration is True
        assert len(decision.explore) > 0

        result = scheduler.submit_population_decision(decision)
        assert len(result["explore_tasks"]) > 0

    def test_pipeline_with_controller(self):
        """完整链路：Controller → Population → Scheduler → Tick。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        controller = AutonomousCreativeController(intelligence_engine=mock_intel)

        specs = _make_genome_specs(10)  # g001=150, g002=140, ...
        fitness_map = {"g001": 200.0, "g002": 190.0, "g003": 180.0}

        result = controller.manage_population_and_tick(specs, fitness_map)

        decision = result["decision"]
        assert isinstance(decision, PopulationDecision)
        assert "g001" in decision.elite
        assert result["scheduler_result"]["total_tasks"] > 0
        assert len(result["started_tasks"]) > 0

    def test_pipeline_controller_with_budget(self):
        """Controller + Budget + Population 完整链路。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        budget = EvolutionBudgetManager()
        budget.set_level(BudgetLevel.LIBERAL)  # 200 tasks
        controller = AutonomousCreativeController(
            intelligence_engine=mock_intel,
            budget_manager=budget,
        )

        specs = _make_genome_specs(10)
        result = controller.manage_population(specs)

        assert result["scheduler_result"]["total_tasks"] > 0
        assert result["scheduler_result"]["rejected_count"] == 0

    def test_pipeline_controller_budget_locked(self):
        """预算锁定 → 所有任务被拒绝。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        budget = EvolutionBudgetManager()
        budget.lock()
        controller = AutonomousCreativeController(
            intelligence_engine=mock_intel,
            budget_manager=budget,
        )

        specs = _make_genome_specs(10)
        result = controller.manage_population(specs)

        assert result["scheduler_result"]["total_tasks"] == 0
        assert result["scheduler_result"]["rejected_count"] > 0

    def test_pipeline_controller_can_evolve(self):
        """can_evolve() 检查预算。"""
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        budget = EvolutionBudgetManager()
        budget.set_level(BudgetLevel.LIBERAL)
        controller = AutonomousCreativeController(
            intelligence_engine=mock_intel,
            budget_manager=budget,
        )
        assert controller.can_evolve() is True

    def test_pipeline_controller_cannot_evolve_when_locked(self):
        mock_intel = MagicMock(spec=VisionIntelligenceEngine)
        budget = EvolutionBudgetManager()
        budget.lock()
        controller = AutonomousCreativeController(
            intelligence_engine=mock_intel,
            budget_manager=budget,
        )
        assert controller.can_evolve() is False

    def test_pipeline_diversity_evolution_loop(self):
        """多样性在进化过程中被跟踪。"""
        manager = PopulationEvolutionManager()
        # 高多样性初始种群
        specs = [
            {"genome_id": f"g{i:03d}", "fitness_score": 50.0 + i * 10, "features": {"hook": f"unique_{i}"}}
            for i in range(10)
        ]
        manager.create_population(specs)
        decision = manager.evolve()
        # 高多样性 → 不触发探索
        assert decision.needs_exploration is False
        assert decision.diversity_score > 0.5

    def test_pipeline_retirement_preserves_min_population(self):
        """小种群时不退役。"""
        manager = PopulationEvolutionManager()
        specs = _make_genome_specs(3)
        manager.create_population(specs)
        decision = manager.evolve()
        # 3 < min_population(5) → 0 retire
        assert len(decision.retire) == 0


# ═══════════════════════════════════════════════════════════
# 9. Package Exports — 5 tests
# ═══════════════════════════════════════════════════════════

class TestPackageExports:
    """__init__.py 导出测试。"""

    def test_exports_models(self):
        assert ExportedGenomeIndividual is GenomeIndividual
        assert ExportedGenomeStatus is GenomeStatus
        assert ExportedPopulationSnapshot is PopulationSnapshot
        assert ExportedPopulationDecision is PopulationDecision
        assert ExportedPopulationSummary is PopulationSummary

    def test_exports_evaluator(self):
        assert ExportedPopulationEvaluator is PopulationEvaluator

    def test_exports_selector(self):
        assert ExportedPopulationSelector is PopulationSelector

    def test_exports_diversity(self):
        assert ExportedDiversityEngine is DiversityEngine

    def test_exports_manager(self):
        assert ExportedPopulationEvolutionManager is PopulationEvolutionManager