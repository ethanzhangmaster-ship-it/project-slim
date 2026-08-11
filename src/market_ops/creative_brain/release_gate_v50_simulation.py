"""V5.0 Evolution Simulation Gate — Mock Mutation Pipeline (38 tests).

Per Architecture Review v1.2 → v1.3 → v1.4 (Final Freeze):
  Final schema freeze before Phase 2 Mutation Engine.
  This ensures:
    - Genome lifecycle + schema_version tracking
    - Population lifecycle (novelty, survival, convergence, species)
    - Fitness update + category scores + explanation
    - Memory lineage + event logging + replay fields
    - Event order + replay (generation, actor, version, random_seed)
    - Rollback/recovery
    - Species classification + split/merge tracking
    - Cross-over + structural mutation contract
    - Mutation API v1.4 interface contract
    - mutation_hash determinism (SHA256, key order, float precision)
    - correlation_id lifecycle (auto-generated per EvolutionRun)

Tests:
  1. Genome Lifecycle (4)
  2. Population Lifecycle (4)
  3. Fitness Update (3)
  4. Memory Lineage (3)
  5. Event Order (3)
  6. Rollback (2)
  7. E2E Mock Mutation (1)
  8. Species (3)
  9. Event Replay (3)
 10. Cross-over (2)
 11. Schema v1.3 (4)
 12. Freeze Final (2)
 13. Hash Determinism + Correlation (4)    ← NEW

Total: 38 tests. All must PASS.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.v5_evolution.schemas import (
    Gene, GeneType, Genome, Species, Population, Fitness, FitnessComponent,
    EvolutionPhase, EvolutionRun, EvolutionEvent, EvolutionSnapshot,
    MutationOperator, MutationRequest, MutationResult, MutationReport,
    MutationStrategyType, DEFAULT_FITNESS_WEIGHTS, DEFAULT_FITNESS_CATEGORIES,
    compute_mutation_hash,
)
from market_ops.creative_brain.v5_evolution.evolution_run import EvolutionRunManager
from market_ops.creative_brain.v5_evolution.genome_manager import GenomeManager
from market_ops.creative_brain.v5_evolution.population_manager import PopulationManager
from market_ops.creative_brain.v5_evolution.fitness_calculator import FitnessCalculator
from market_ops.creative_brain.v5_evolution.evolution_memory import EvolutionMemory


# ═══════════════════════════════════════════════════════════
# Helpers: Mock Mutation Engine
# ═══════════════════════════════════════════════════════════

def mock_mutate_genome(gm: GenomeManager, genome_id: str, gene_type: str,
                       new_value: str, generation: int) -> tuple[Genome, Genome]:
    """Mock a single-gene mutation: clone genome → change gene value.

    Returns (original, mutated).
    """
    original = gm.get(genome_id)
    mutated = gm.clone(genome_id, new_name=f"{original.name}_mut", new_generation=generation)
    # Apply mutation
    gene = mutated.genes.get(gene_type)
    if gene:
        gene.value = new_value
        gene.mutation_history.append(new_value)
    return original, mutated


def mock_mutate_population(gm: GenomeManager, genomes: list[Genome],
                           generation: int, mutation_rate: float = 0.3) -> list[Genome]:
    """Mock multi-gene mutation on a population.

    Returns list of mutated genomes (original + mutated).
    """
    mutations = []
    mutation_pool = {
        "hook": ["rescue", "escape", "protect", "abandon"],
        "character": ["dragon", "cat", "monster", "hero"],
        "emotion": ["cute", "fear", "curiosity", "excitement"],
        "gameplay": ["merge", "puzzle", "sort", "match"],
    }

    for genome in genomes:
        original, mutated = genome, genome
        for gene_type, gene in list(genome.genes.items()):
            # Random mutation decision
            if gene_type in mutation_pool:
                # Simple deterministic: if gene value is the first in pool, mutate to second
                pool = mutation_pool[gene_type]
                if gene.value in pool:
                    idx = pool.index(gene.value)
                    new_val = pool[(idx + 1) % len(pool)]  # Cycle to next
                    if new_val != gene.value:
                        original, mutated = mock_mutate_genome(
                            gm, original.genome_id, gene_type, new_val, generation
                        )
                        mutations.append(mutated)
        if mutated == genome:
            mutations.append(genome)
    return mutations


# ═══════════════════════════════════════════════════════════
# 1. Genome Lifecycle (4 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_genome_create_mutate_fitness():
    """Genome create → mutate → fitness update"""
    gm = GenomeManager()
    fc = FitnessCalculator()

    # Create seed
    genes = [
        Gene(gene_type=GeneType.HOOK, value="rescue",
             mutation_pool=["rescue", "escape", "protect"]),
        Gene(gene_type=GeneType.CHARACTER, value="dragon",
             mutation_pool=["dragon", "cat", "monster"]),
    ]
    seed = gm.create("seed", generation=0, genes=genes)

    # Mock mutate
    original, mutated = mock_mutate_genome(gm, seed.genome_id, "hook", "escape", generation=1)
    assert mutated.genome_id != seed.genome_id
    assert mutated.genes["hook"].value == "escape"

    # Fitness update
    fitness = fc.calculate_online(mutated.genome_id, 1,
                                  {"ctr": 0.04, "cvr": 0.18, "roas_d7": 0.55},
                                  sample_size=5000)
    gm.update_fitness(mutated.genome_id, fitness)
    assert gm.get(mutated.genome_id).fitness is not None
    return True


def test_sim_genome_lineage_across_gens():
    """Genome lineage across 3 generations"""
    gm = GenomeManager()

    g0 = gm.create("g0", generation=0,
                   genes=[Gene(gene_type=GeneType.HOOK, value="rescue")])
    original, g1 = mock_mutate_genome(gm, g0.genome_id, "hook", "escape", 1)
    original, g2 = mock_mutate_genome(gm, g1.genome_id, "hook", "protect", 2)

    lineage = gm.get_lineage(g2.genome_id)
    assert len(lineage) == 3  # g0 → g1 → g2
    assert lineage[0].genome_id == g0.genome_id
    assert lineage[-1].genome_id == g2.genome_id
    return True


def test_sim_fitness_history_accumulation():
    """Fitness history accumulates across updates"""
    gm = GenomeManager()
    fc = FitnessCalculator()

    g = gm.create("test", generation=0,
                  genes=[Gene(gene_type=GeneType.HOOK, value="rescue")])

    for i, score in enumerate([0.52, 0.61, 0.78, 0.82]):
        fitness = Fitness(genome_id=g.genome_id, composite_score=score)
        gm.update_fitness(g.genome_id, fitness)

    genome = gm.get(g.genome_id)
    assert len(genome.fitness_history) == 3  # First archived, rest in history
    assert genome.fitness_trend == "improving"
    return True


def test_sim_fitness_trend_detection():
    """Fitness trend: improving / declining / stable"""
    gm = GenomeManager()

    # Improving
    g1 = gm.create("improving", generation=0)
    for score in [0.5, 0.6, 0.8]:
        gm.update_fitness(g1.genome_id, Fitness(genome_id=g1.genome_id, composite_score=score))
    assert gm.get(g1.genome_id).fitness_trend == "improving"

    # Declining
    g2 = gm.create("declining", generation=0)
    for score in [0.8, 0.6, 0.5]:
        gm.update_fitness(g2.genome_id, Fitness(genome_id=g2.genome_id, composite_score=score))
    assert gm.get(g2.genome_id).fitness_trend == "declining"

    # Stable
    g3 = gm.create("stable", generation=0)
    for score in [0.5, 0.5, 0.51]:
        gm.update_fitness(g3.genome_id, Fitness(genome_id=g3.genome_id, composite_score=score))
    assert gm.get(g3.genome_id).fitness_trend == "stable"
    return True


# ═══════════════════════════════════════════════════════════
# 2. Population Lifecycle (4 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_population_create_to_next_gen():
    """Population: create → add genomes → select elites → next gen"""
    gm = GenomeManager()
    pm = PopulationManager()

    # Gen 0
    pop0 = pm.create_population(generation=0, elite_count=3)
    for i in range(10):
        genes = [Gene(gene_type=GeneType.HOOK, value=f"hook_{i % 3}")]
        g = gm.create(f"g0_{i}", generation=0, genes=genes)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.05)
        g.fitness = fitness
        pm.add_genome(pop0.population_id, g)

    # Select elites
    elites = pm.select_elites(pop0.population_id)
    assert len(elites) == 3

    # Gen 1
    pop1 = pm.create_next_generation(pop0.population_id)
    assert pop1.generation == 1
    assert len(pop1.genomes) == 3  # Elites carried over
    return True


def test_sim_novelty_calculation():
    """Novelty: new gen should show novelty vs prev gen"""
    gm = GenomeManager()
    pm = PopulationManager()

    # Gen 0: all same hook values
    pop0 = pm.create_population(generation=0)
    for i in range(5):
        genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
        g = gm.create(f"g0_{i}", generation=0, genes=genes)
        pm.add_genome(pop0.population_id, g)

    # Gen 1: all different hook values
    pop1 = pm.create_population(generation=1)
    values = ["escape", "protect", "abandon", "collect", "rescue"]
    for i, v in enumerate(values):
        genes = [Gene(gene_type=GeneType.HOOK, value=v)]
        g = gm.create(f"g1_{i}", generation=1, genes=genes)
        pm.add_genome(pop1.population_id, g)

    novelty = pm.calculate_novelty(pop1.population_id)
    assert novelty > 0.5  # Most values are new
    return True


def test_sim_survival_rate():
    """Survival rate: tracks how many genomes survived from prev gen"""
    gm = GenomeManager()
    pm = PopulationManager()

    # Gen 0
    pop0 = pm.create_population(generation=0)
    genome_ids = []
    for i in range(5):
        genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
        g = gm.create(f"g0_{i}", generation=0, genes=genes)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5)
        g.fitness = fitness
        pm.add_genome(pop0.population_id, g)
        genome_ids.append(g.genome_id)

    # Gen 1: clone 3 of 5 from gen 0
    pop1 = pm.create_population(generation=1)
    for i in range(3):
        cloned = gm.clone(genome_ids[i], new_name=f"g1_{i}", new_generation=1)
        pm.add_genome(pop1.population_id, cloned)

    survival = pm.calculate_survival_rate(pop1.population_id)
    assert survival > 0.0
    assert survival <= 1.0
    return True


def test_sim_population_combined_metrics():
    """Population: diversity + convergence + novelty + survival combined"""
    gm = GenomeManager()
    pm = PopulationManager()

    pop = pm.create_population(generation=0)
    hook_values = ["rescue", "escape", "protect", "abandon", "collect"]
    for i, v in enumerate(hook_values):
        genes = [Gene(gene_type=GeneType.HOOK, value=v)]
        g = gm.create(f"g_{i}", generation=0, genes=genes)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.1)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)

    diversity = pm.calculate_diversity(pop.population_id)
    convergence = pm.calculate_convergence(pop.population_id)
    novelty = pm.calculate_novelty(pop.population_id)
    survival = pm.calculate_survival_rate(pop.population_id)

    assert diversity > 0.5  # All different values
    assert convergence < 0.5  # Not converged
    assert novelty == 1.0  # First generation
    assert survival == 1.0  # First generation
    return True


# ═══════════════════════════════════════════════════════════
# 3. Fitness Update (3 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_fitness_category_scores():
    """Fitness: category scores (creative, business, user, long_term)"""
    fc = FitnessCalculator()

    components = {
        "ctr": 0.04, "cvr": 0.18, "roas_d1": 0.35,
        "roas_d7": 0.55, "roas_d30": 0.40,
        "retention_d1": 0.35, "retention_d7": 0.25,
        "cpi": 0.50, "ltv": 0.60,
    }
    fitness = fc.calculate_online("g1", 1, components, sample_size=5000)

    assert "creative" in fitness.category_scores
    assert "business" in fitness.category_scores
    assert "user" in fitness.category_scores
    assert "long_term" in fitness.category_scores
    # All category scores should be between 0 and 1
    for cat, score in fitness.category_scores.items():
        assert 0.0 <= score <= 1.0, f"{cat}: {score}"
    return True


def test_sim_fitness_batch_population():
    """Fitness: batch population scoring with category scores"""
    fc = FitnessCalculator()
    pm = PopulationManager()
    gm = GenomeManager()

    pop = pm.create_population(generation=0)
    comps_map = {}
    for i in range(5):
        g = gm.create(f"g_{i}", generation=0)
        pm.add_genome(pop.population_id, g)
        comps_map[g.genome_id] = {
            "ctr": 0.03 + i * 0.005, "cvr": 0.15 + i * 0.01,
            "roas_d7": 0.4 + i * 0.05, "retention_d7": 0.2 + i * 0.02,
        }

    count = fc.score_population(pop, comps_map)
    assert count == 5

    # Verify each genome has category scores
    for g in pop.genomes:
        assert g.fitness is not None
        assert "creative" in g.fitness.category_scores
    return True


def test_sim_fitness_mixed_online_offline():
    """Fitness: mixed online + offline scoring"""
    fc = FitnessCalculator()

    online = {"ctr": 0.04, "cvr": 0.20, "roas_d7": 0.50}
    offline = {"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.40}

    fitness = fc.calculate_mixed("g1", 1, online, offline, online_weight=0.7, sample_size=3000)
    assert fitness.is_online
    assert fitness.composite_score > 0.0
    assert len(fitness.category_scores) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 4. Memory Lineage (3 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_memory_snapshot_chain():
    """Memory: snapshot chain across generations"""
    em = EvolutionMemory()
    pm = PopulationManager()
    gm = GenomeManager()

    run_id = "sim_run_1"

    for gen in range(3):
        pop = pm.create_population(generation=gen)
        for i in range(5):
            g = gm.create(f"g{gen}_{i}", generation=gen)
            fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + gen * 0.1 + i * 0.02)
            g.fitness = fitness
            pm.add_genome(pop.population_id, g)

        phase = EvolutionPhase.MUTATING
        if gen == 2:
            phase = EvolutionPhase.CONVERGING
        em.snapshot(run_id, pop, phase)

    snapshots = em.get_snapshots_by_run(run_id)
    assert len(snapshots) == 3
    assert snapshots[0].generation == 0
    assert snapshots[2].generation == 2
    assert snapshots[2].controller_phase == EvolutionPhase.CONVERGING
    return True


def test_sim_memory_mutation_beneficial():
    """Memory: mutation records with beneficial/harmful detection"""
    em = EvolutionMemory()

    # Beneficial mutations
    em.record_mutation("g1", "p1", "hook", "rescue", "escape", "point_mutation",
                       1, fitness_before=0.5, fitness_after=0.7)
    em.record_mutation("g2", "p2", "character", "dragon", "cat", "swap",
                       1, fitness_before=0.6, fitness_after=0.85)

    # Harmful mutation
    em.record_mutation("g3", "p3", "gameplay", "merge", "shooter", "point_mutation",
                       1, fitness_before=0.6, fitness_after=0.45)

    beneficial = em.get_beneficial_mutations()
    harmful = em.get_harmful_mutations()

    assert len(beneficial) == 2
    assert len(harmful) == 1
    return True


def test_sim_memory_operator_effectiveness():
    """Memory: best mutation operators by avg improvement"""
    em = EvolutionMemory()

    em.record_mutation("g1", "p1", "hook", "a", "b", "point_mutation", 1, 0.5, 0.7)
    em.record_mutation("g2", "p2", "hook", "c", "d", "point_mutation", 1, 0.5, 0.65)
    em.record_mutation("g3", "p3", "hook", "e", "f", "crossover", 1, 0.5, 0.55)
    em.record_mutation("g4", "p4", "hook", "g", "h", "swap", 1, 0.5, 0.4)

    best = em.get_best_mutation_operators(3)
    assert len(best) >= 1
    assert best[0][0] == "point_mutation"  # Highest avg improvement
    return True


# ═══════════════════════════════════════════════════════════
# 5. Event Order (3 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_event_sequence():
    """Event: correct sequence in evolution pipeline"""
    em = EvolutionMemory()
    run_id = "sim_event_run"

    # Simulate full event sequence
    events = [
        ("GENOME_CREATED", "g_seed"),
        ("POPULATION_CREATED", "pop_0"),
        ("MUTATION_APPLIED", "g_mut_1"),
        ("FITNESS_UPDATED", "g_mut_1"),
        ("ELITE_SELECTED", "pop_0"),
        ("GENERATION_FINISHED", "pop_0"),
    ]

    for event_type, entity_id in events:
        evt = EvolutionEvent(event_type=event_type, run_id=run_id,
                             entity_id=entity_id, source="simulation")
        em.log_event(evt)

    all_events = em.get_events()
    assert len(all_events) == 6

    # Verify order
    assert all_events[0].event_type == "GENOME_CREATED"
    assert all_events[-1].event_type == "GENERATION_FINISHED"
    return True


def test_sim_event_filter():
    """Event: filtering by type and run_id"""
    em = EvolutionMemory()

    # Events from run A
    for i in range(3):
        em.log_event(EvolutionEvent(event_type="GENOME_CREATED", run_id="run_A",
                                    entity_id=f"g_{i}", source="test"))
    # Events from run B
    for i in range(2):
        em.log_event(EvolutionEvent(event_type="FITNESS_UPDATED", run_id="run_B",
                                    entity_id=f"g_{i}", source="test"))

    by_type = em.get_events(event_type="GENOME_CREATED")
    assert len(by_type) == 3

    by_run = em.get_events(run_id="run_B")
    assert len(by_run) == 2
    return True


def test_sim_event_source_tracking():
    """Event: source module tracking"""
    em = EvolutionMemory()

    em.log_event(EvolutionEvent(event_type="GENOME_CREATED", run_id="r1",
                                entity_id="g1", source="genome_manager"))
    em.log_event(EvolutionEvent(event_type="FITNESS_UPDATED", run_id="r1",
                                entity_id="g1", source="fitness_calculator"))
    em.log_event(EvolutionEvent(event_type="MUTATION_APPLIED", run_id="r1",
                                entity_id="g1", source="mutation_engine"))

    all_events = em.get_events()
    sources = {e.source for e in all_events}
    assert "genome_manager" in sources
    assert "fitness_calculator" in sources
    assert "mutation_engine" in sources
    return True


# ═══════════════════════════════════════════════════════════
# 6. Rollback (2 tests)
# ═══════════════════════════════════════════════════════════

def test_sim_rollback_snapshot():
    """Rollback: snapshot creation + retrieval for rollback"""
    em = EvolutionMemory()
    pm = PopulationManager()
    gm = GenomeManager()

    run_id = "sim_rollback"

    # Gen 0: good population
    pop0 = pm.create_population(generation=0)
    for i in range(5):
        g = gm.create(f"g0_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.7 + i * 0.05)
        g.fitness = fitness
        pm.add_genome(pop0.population_id, g)
    snap0 = em.snapshot(run_id, pop0, EvolutionPhase.POPULATION_CREATED)

    # Gen 1: bad population (simulated)
    pop1 = pm.create_population(generation=1)
    for i in range(5):
        g = gm.create(f"g1_{i}", generation=1)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.1)
        g.fitness = fitness
        pm.add_genome(pop1.population_id, g)
    snap1 = em.snapshot(run_id, pop1, EvolutionPhase.MUTATING)

    # Verify snapshots
    assert em.get_snapshot(snap0.snapshot_id).avg_fitness > 0.5
    assert em.get_snapshot(snap1.snapshot_id).avg_fitness < 0.5

    # Latest snapshot is gen 1
    latest = em.get_latest_snapshot(run_id)
    assert latest.generation == 1

    # Rollback to gen 0 (by snapshot)
    rollback_snap = em.get_snapshots_by_run(run_id)[0]
    assert rollback_snap.generation == 0
    assert rollback_snap.avg_fitness > 0.5
    return True


def test_sim_rollback_multi_gen():
    """Rollback: multiple generations → rollback to specific gen"""
    em = EvolutionMemory()
    pm = PopulationManager()
    gm = GenomeManager()

    run_id = "sim_multi_gen"

    for gen in range(5):
        pop = pm.create_population(generation=gen)
        for i in range(3):
            g = gm.create(f"g{gen}_{i}", generation=gen)
            fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + gen * 0.1)
            g.fitness = fitness
            pm.add_genome(pop.population_id, g)
        em.snapshot(run_id, pop, EvolutionPhase.MUTATING)

    snapshots = em.get_snapshots_by_run(run_id)
    assert len(snapshots) == 5

    # Rollback to gen 2
    gen2_snaps = em.get_snapshots_by_generation(2)
    assert len(gen2_snaps) == 1
    assert gen2_snaps[0].generation == 2
    return True


# ═══════════════════════════════════════════════════════════
# 7. E2E Mock Mutation (1 test)
# ═══════════════════════════════════════════════════════════

def test_sim_e2e_mock_mutation_pipeline():
    """E2E: full evolution pipeline with mock mutation

    Seed → Clone → Mock Mutate → Fitness → Elite → Next Gen → Memory → Verify
    """
    rm = EvolutionRunManager()
    gm = GenomeManager()
    pm = PopulationManager()
    fc = FitnessCalculator()
    em = EvolutionMemory()

    # 1. Create run
    run = rm.create_run("Mock Evolution: Find best creative", "merge_puzzle")

    # 2. Create seed genomes
    seed_genes = [
        Gene(gene_type=GeneType.HOOK, value="rescue",
             mutation_pool=["rescue", "escape", "protect"]),
        Gene(gene_type=GeneType.CHARACTER, value="dragon",
             mutation_pool=["dragon", "cat", "monster"]),
        Gene(gene_type=GeneType.EMOTION, value="cute",
             mutation_pool=["cute", "fear", "curiosity"]),
    ]
    for i in range(6):
        gm.create(f"seed_{i}", generation=0, genes=seed_genes)

    # 3. Create population gen 0
    pop0 = pm.create_population(generation=0, elite_count=3)
    pm.add_genomes(pop0.population_id, gm.get_by_generation(0))

    # 4. Fitness gen 0
    comps_map = {}
    for g in pop0.genomes:
        comps_map[g.genome_id] = {"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.45}
    fc.score_population(pop0, comps_map)
    em.snapshot(run.run_id, pop0, EvolutionPhase.POPULATION_CREATED)

    # 5. Mock mutation → gen 1
    elites = pm.select_elites(pop0.population_id)
    mutated = mock_mutate_population(gm, elites, generation=1)

    pop1 = pm.create_population(generation=1, elite_count=3)
    pm.add_genomes(pop1.population_id, mutated)

    # 6. Fitness gen 1 (improved)
    comps_map1 = {}
    for g in pop1.genomes:
        comps_map1[g.genome_id] = {"ctr": 0.035, "cvr": 0.18, "roas_d7": 0.52}
    fc.score_population(pop1, comps_map1)
    em.snapshot(run.run_id, pop1, EvolutionPhase.MUTATING)

    # 7. Record mutations in memory
    for g in pop1.genomes:
        if g.parent_ids:
            em.record_mutation(
                g.genome_id, g.parent_ids[0],
                "hook", "rescue", g.genes.get("hook", Gene()).value,
                "point_mutation", generation=1,
                fitness_before=0.5, fitness_after=0.62
            )
    em.log_event(EvolutionEvent(
        event_type="MUTATION_APPLIED", run_id=run.run_id,
        entity_id=pop1.population_id, source="mutation_engine"
    ))

    # 8. Next gen + elite
    elites1 = pm.select_elites(pop1.population_id)
    pop2 = pm.create_next_generation(pop1.population_id)
    em.snapshot(run.run_id, pop2, EvolutionPhase.CONVERGING)

    # 9. Advance run
    rm.advance_generation(run.run_id)
    rm.advance_generation(run.run_id)
    assert rm.get_run(run.run_id).current_generation == 2

    # 10. Verify end-to-end
    # Population lifecycle
    assert len(pop0.genomes) == 6  # Gen 0: 6 seeds
    assert len(elites) == 3        # Elite selection
    assert pop1.generation == 1    # Gen 1
    assert pop2.generation == 2    # Gen 2

    # Fitness improvement
    assert pop1.avg_fitness > pop0.avg_fitness

    # Memory lineage
    snapshots = em.get_snapshots_by_run(run.run_id)
    assert len(snapshots) == 3  # Gen 0, 1, 2

    # Events logged
    events = em.get_events()
    mutation_events = em.get_events(event_type="MUTATION_APPLIED")
    assert len(mutation_events) >= 1

    # Mutation records
    beneficial = em.get_beneficial_mutations()
    assert len(beneficial) > 0

    # Novelty: gen 1 should have novelty vs gen 0
    pm.calculate_novelty(pop1.population_id)
    assert pop1.novelty_score > 0.0

    # Survival rate
    pm.calculate_survival_rate(pop1.population_id)
    assert pop1.survival_rate > 0.0

    # Set winner
    best = pop1.get_best()
    if best:
        rm.set_winner(run.run_id, best.genome_id)
        assert rm.get_run(run.run_id).winner_genome_id == best.genome_id

    return True


# ═══════════════════════════════════════════════════════════
# 8. Species (3 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_species_create_and_classify():
    """Species: create and classify genomes into species by gameplay"""
    gm = GenomeManager()
    pm = PopulationManager()

    pop = pm.create_population(generation=0)
    gameplays = ["merge", "merge", "sort", "sort", "simulation"]
    for i, gp in enumerate(gameplays):
        genes = [
            Gene(gene_type=GeneType.HOOK, value="rescue"),
            Gene(gene_type=GeneType.GAMEPLAY, value=gp),
        ]
        g = gm.create(f"g_{i}", generation=0, genes=genes)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.05)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)

    species_map = pm.classify_into_species(pop.population_id, species_key="gameplay")
    assert len(species_map) == 3  # merge, sort, simulation

    for s in species_map.values():
        assert s.size > 0
        assert s.avg_fitness > 0.0
        assert s.diversity_score >= 0.0

    return True


def test_sim_species_separate_evolution():
    """Species: separate evolution tracks with different fitness"""
    gm = GenomeManager()
    pm = PopulationManager()

    pop = pm.create_population(generation=0)

    # Create merge species (high fitness)
    merge_species = pm.create_species(pop.population_id, "merge_0", "merge")
    for i in range(3):
        g = gm.create(f"merge_{i}", generation=0,
                      genes=[Gene(gene_type=GeneType.GAMEPLAY, value="merge")])
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.8)
        g.fitness = fitness
        pm.add_to_species(pop.population_id, merge_species.species_id, g)

    # Create sort species (low fitness)
    sort_species = pm.create_species(pop.population_id, "sort_0", "sort")
    for i in range(3):
        g = gm.create(f"sort_{i}", generation=0,
                      genes=[Gene(gene_type=GeneType.GAMEPLAY, value="sort")])
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.4)
        g.fitness = fitness
        pm.add_to_species(pop.population_id, sort_species.species_id, g)

    # Verify species stats
    merge = pm.get_species(pop.population_id, merge_species.species_id)
    sort = pm.get_species(pop.population_id, sort_species.species_id)

    assert merge.avg_fitness > sort.avg_fitness
    assert merge.size == 3
    assert sort.size == 3

    all_species = pm.get_all_species(pop.population_id)
    assert len(all_species) == 2

    return True


def test_sim_species_cross_breeding_readiness():
    """Species: cross-breeding fields (centroid, source_genomes) exist"""
    gm = GenomeManager()
    pm = PopulationManager()

    pop = pm.create_population(generation=0)

    species_a = pm.create_species(pop.population_id, "merge_0", "merge")
    species_b = pm.create_species(pop.population_id, "sort_0", "sort")

    # Verify species have centroid_genome_id field
    assert hasattr(species_a, "centroid_genome_id")
    assert hasattr(species_b, "centroid_genome_id")

    # Verify MutationRequest supports source_genomes for cross-over
    req = MutationRequest(
        genome_id="g1",
        source_genomes=["g2", "g3"],
        operators=[MutationOperator.CROSSOVER],
        strategy=MutationStrategyType.HYBRID,
    )
    assert "g2" in req.source_genomes
    assert "g3" in req.source_genomes
    assert req.to_dict()["source_genomes"] == ["g2", "g3"]

    return True


# ═══════════════════════════════════════════════════════════
# 9. Event Replay (3 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_event_generation_tracking():
    """Event Replay: generation field is set correctly"""
    em = EvolutionMemory()

    for gen in range(3):
        em.log_event(EvolutionEvent(
            event_type="GENOME_CREATED", run_id="replay_r1",
            entity_id=f"g_{gen}", generation=gen,
            source="genome_manager", actor="seed",
        ))

    events = em.get_events()
    assert len(events) == 3
    assert events[0].generation == 0
    assert events[1].generation == 1
    assert events[2].generation == 2

    # Filter by generation (simulate replay)
    gen1_events = [e for e in events if e.generation == 1]
    assert len(gen1_events) == 1

    return True


def test_sim_event_actor_tracking():
    """Event Replay: actor field identifies who triggered the event"""
    em = EvolutionMemory()

    em.log_event(EvolutionEvent(
        event_type="MUTATION_APPLIED", run_id="r1", entity_id="g1",
        generation=1, source="mutation_engine",
        actor="guided_mutation",
    ))
    em.log_event(EvolutionEvent(
        event_type="MUTATION_APPLIED", run_id="r1", entity_id="g2",
        generation=1, source="mutation_engine",
        actor="random_mutation",
    ))
    em.log_event(EvolutionEvent(
        event_type="FITNESS_UPDATED", run_id="r1", entity_id="g1",
        generation=1, source="fitness_calculator",
        actor="online_evaluator",
    ))

    events = em.get_events()
    actors = {e.actor for e in events}
    assert "guided_mutation" in actors
    assert "random_mutation" in actors
    assert "online_evaluator" in actors

    return True


def test_sim_event_version_tracking():
    """Event Replay: version field enables schema compatibility"""
    em = EvolutionMemory()

    em.log_event(EvolutionEvent(
        event_type="GENOME_CREATED", run_id="r1", entity_id="g1",
        version="1.0", source="test",
    ))
    em.log_event(EvolutionEvent(
        event_type="GENOME_CREATED", run_id="r1", entity_id="g2",
        version="1.1", source="test",
    ))

    events = em.get_events()
    versions = {e.version for e in events}
    assert "1.0" in versions
    assert "1.1" in versions

    # Verify version is in to_dict
    d = events[0].to_dict()
    assert d["version"] == "1.0"

    return True


# ═══════════════════════════════════════════════════════════
# 10. Cross-over Mutation (2 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_crossover_source_genomes():
    """Cross-over: MutationRequest supports multiple parent genomes"""
    req = MutationRequest(
        genome_id="parent_a",
        source_genomes=["parent_b"],
        operators=[MutationOperator.CROSSOVER],
        strategy=MutationStrategyType.HYBRID,
        context={"crossover_method": "uniform"},
    )
    assert req.genome_id == "parent_a"
    assert len(req.source_genomes) == 1
    assert req.source_genomes[0] == "parent_b"
    assert MutationOperator.CROSSOVER in req.operators
    return True


def test_sim_structural_mutation_new_genes():
    """Structural Mutation: MutationRequest supports adding new genes"""
    req = MutationRequest(
        genome_id="g1",
        operators=[MutationOperator.INSERTION],
        new_genes=[
            {"gene_type": "reward", "value": "coin_collect", "mutation_pool": ["coin", "gem", "star"]},
        ],
        strategy=MutationStrategyType.REWARD,
    )
    assert len(req.new_genes) == 1
    assert req.new_genes[0]["gene_type"] == "reward"
    assert req.new_genes[0]["value"] == "coin_collect"
    return True


# ═══════════════════════════════════════════════════════════
# 11. Schema v1.3 (4 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_genome_schema_version():
    """Schema v1.3: Genome.schema_version for forward compatibility"""
    gm = GenomeManager()
    g = gm.create("test", generation=0)
    assert hasattr(g, "schema_version")
    assert g.schema_version == "1.3"
    assert "schema_version" in g.to_dict()
    return True


def test_sim_fitness_explanation():
    """Schema v1.3: Fitness.explanation for model interpretability"""
    fc = FitnessCalculator()
    fitness = fc.calculate_online("g1", 1,
                                  {"ctr": 0.04, "cvr": 0.18, "roas_d7": 0.55},
                                  sample_size=5000)
    assert hasattr(fitness, "explanation")
    assert isinstance(fitness.explanation, list)
    # Explanation can be empty initially, filled by evaluator
    assert "explanation" in fitness.to_dict()
    return True


def test_sim_event_random_seed():
    """Schema v1.3: EvolutionEvent.random_seed for deterministic replay"""
    em = EvolutionMemory()

    evt = EvolutionEvent(
        event_type="MUTATION_APPLIED", run_id="r1", entity_id="g1",
        generation=1, source="mutation_engine", actor="random_mutation",
        random_seed=42,
    )
    em.log_event(evt)

    events = em.get_events()
    assert events[0].random_seed == 42
    d = events[0].to_dict()
    assert d["random_seed"] == 42
    return True


def test_sim_species_split_merge_tracking():
    """Schema v1.3: Species parent/children/merge_history for split/merge"""
    gm = GenomeManager()
    pm = PopulationManager()

    pop = pm.create_population(generation=0)

    # Create parent species
    parent = pm.create_species(pop.population_id, "merge_sort_0", "merge_sort")
    for i in range(3):
        g = gm.create(f"g_{i}", generation=0)
        pm.add_to_species(pop.population_id, parent.species_id, g)

    # Verify split/merge fields exist
    assert hasattr(parent, "parent_species_id")
    assert hasattr(parent, "children_species_ids")
    assert hasattr(parent, "merge_history")
    assert parent.parent_species_id == ""
    assert parent.children_species_ids == []
    assert parent.merge_history == []

    return True


# ═══════════════════════════════════════════════════════════
# 12. Freeze Final (2 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_mutation_hash_field():
    """Freeze Final: MutationResult.mutation_hash for dedup/replay/cache"""
    result = MutationResult(
        original_genome_id="g1",
        operators_used=["point_mutation"],
        mutation_hash="abc123",
    )
    assert hasattr(result, "mutation_hash")
    assert result.mutation_hash == "abc123"
    assert "mutation_hash" in result.to_dict()
    return True


def test_sim_event_correlation_id():
    """Freeze Final: EvolutionEvent.correlation_id links pipeline events"""
    import uuid
    corr_id = str(uuid.uuid4())[:8]

    em = EvolutionMemory()
    em.log_event(EvolutionEvent(
        event_type="GENOME_CREATED", run_id="r1", entity_id="g1",
        correlation_id=corr_id, source="genome_manager",
    ))
    em.log_event(EvolutionEvent(
        event_type="MUTATION_APPLIED", run_id="r1", entity_id="g1",
        correlation_id=corr_id, source="mutation_engine",
    ))
    em.log_event(EvolutionEvent(
        event_type="FITNESS_UPDATED", run_id="r1", entity_id="g1",
        correlation_id=corr_id, source="fitness_calculator",
    ))

    events = em.get_events()
    # All 3 events share the same correlation_id
    assert len(events) == 3
    assert all(e.correlation_id == corr_id for e in events)

    d = events[0].to_dict()
    assert d["correlation_id"] == corr_id

    return True


# ═══════════════════════════════════════════════════════════
# 13. Hash Determinism + Correlation Lifecycle (3 tests) — NEW
# ═══════════════════════════════════════════════════════════

def test_sim_hash_determinism_same_input():
    """Hash Determinism: same input → same hash (cache key stability)"""
    h1 = compute_mutation_hash("g1", "point_mutation",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "escape"})
    h2 = compute_mutation_hash("g1", "point_mutation",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "escape"})
    assert h1 == h2
    assert len(h1) == 16  # hex digest, 16 chars
    return True


def test_sim_hash_determinism_different_input():
    """Hash Determinism: different input → different hash"""
    h1 = compute_mutation_hash("g1", "point_mutation",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "escape"})
    h2 = compute_mutation_hash("g1", "point_mutation",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "protect"})
    h3 = compute_mutation_hash("g2", "point_mutation",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "escape"})
    h4 = compute_mutation_hash("g1", "crossover",
                               {"gene_type": "hook", "old_value": "rescue", "new_value": "escape"})
    assert h1 != h2  # different value
    assert h1 != h3  # different parent
    assert h1 != h4  # different operator
    return True


def test_sim_hash_determinism_key_order_and_float():
    """Hash Determinism: key order + float precision don't affect hash"""
    h1 = compute_mutation_hash("g1", "point_mutation",
                               {"b": 0.1234561, "a": 1.0})
    h2 = compute_mutation_hash("g1", "point_mutation",
                               {"a": 1.0, "b": 0.1234561})  # different key order
    h3 = compute_mutation_hash("g1", "point_mutation",
                               {"a": 1.0000001, "b": 0.1234564})  # same after rounding (6dp)
    assert h1 == h2  # key order normalized
    assert h1 == h3  # float precision normalized (both round to same values)
    return True


def test_sim_correlation_id_lifecycle():
    """Correlation Lifecycle: EvolutionRun auto-generates correlation_id"""
    rm = EvolutionRunManager()

    run = rm.create_run("Test correlation lifecycle", "merge_puzzle")
    assert hasattr(run, "correlation_id")
    assert run.correlation_id != ""
    assert len(run.correlation_id) == 36  # UUID format

    # correlation_id persists in to_dict
    d = run.to_dict()
    assert d["correlation_id"] == run.correlation_id

    # Multiple runs get different correlation_ids
    run2 = rm.create_run("Another run", "sort_puzzle")
    assert run2.correlation_id != run.correlation_id

    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Genome Lifecycle (4)
        ("Sim: Genome Create→Mutate→Fitness", test_sim_genome_create_mutate_fitness),
        ("Sim: Genome Lineage 3 Gens", test_sim_genome_lineage_across_gens),
        ("Sim: Fitness History Accumulation", test_sim_fitness_history_accumulation),
        ("Sim: Fitness Trend Detection", test_sim_fitness_trend_detection),
        # 2. Population Lifecycle (4)
        ("Sim: Population Create→Next Gen", test_sim_population_create_to_next_gen),
        ("Sim: Novelty Calculation", test_sim_novelty_calculation),
        ("Sim: Survival Rate", test_sim_survival_rate),
        ("Sim: Population Combined Metrics", test_sim_population_combined_metrics),
        # 3. Fitness Update (3)
        ("Sim: Fitness Category Scores", test_sim_fitness_category_scores),
        ("Sim: Fitness Batch Population", test_sim_fitness_batch_population),
        ("Sim: Fitness Mixed Online/Offline", test_sim_fitness_mixed_online_offline),
        # 4. Memory Lineage (3)
        ("Sim: Memory Snapshot Chain", test_sim_memory_snapshot_chain),
        ("Sim: Memory Mutation Beneficial", test_sim_memory_mutation_beneficial),
        ("Sim: Memory Operator Effectiveness", test_sim_memory_operator_effectiveness),
        # 5. Event Order (3)
        ("Sim: Event Sequence", test_sim_event_sequence),
        ("Sim: Event Filter", test_sim_event_filter),
        ("Sim: Event Source Tracking", test_sim_event_source_tracking),
        # 6. Rollback (2)
        ("Sim: Rollback Snapshot", test_sim_rollback_snapshot),
        ("Sim: Rollback Multi Gen", test_sim_rollback_multi_gen),
        # 7. E2E Mock Mutation (1)
        ("Sim: E2E Mock Mutation Pipeline", test_sim_e2e_mock_mutation_pipeline),
        # 8. Species (3) — NEW
        ("Sim: Species Create+Classify", test_sim_species_create_and_classify),
        ("Sim: Species Separate Evolution", test_sim_species_separate_evolution),
        ("Sim: Species Cross-Breeding Ready", test_sim_species_cross_breeding_readiness),
        # 9. Event Replay (3) — NEW
        ("Sim: Event Generation Tracking", test_sim_event_generation_tracking),
        ("Sim: Event Actor Tracking", test_sim_event_actor_tracking),
        ("Sim: Event Version Tracking", test_sim_event_version_tracking),
        # 10. Cross-over (2)
        ("Sim: Crossover Source Genomes", test_sim_crossover_source_genomes),
        ("Sim: Structural Mutation New Genes", test_sim_structural_mutation_new_genes),
        # 11. Schema v1.3 (4) — NEW
        ("Sim: Genome Schema Version", test_sim_genome_schema_version),
        ("Sim: Fitness Explanation", test_sim_fitness_explanation),
        ("Sim: Event Random Seed", test_sim_event_random_seed),
        ("Sim: Species Split/Merge Tracking", test_sim_species_split_merge_tracking),
        # 12. Freeze Final (2) — NEW
        ("Sim: Mutation Hash Field", test_sim_mutation_hash_field),
        ("Sim: Event Correlation ID", test_sim_event_correlation_id),
        # 13. Hash Determinism + Correlation Lifecycle (4) — NEW
        ("Sim: Hash Determinism Same Input", test_sim_hash_determinism_same_input),
        ("Sim: Hash Determinism Different Input", test_sim_hash_determinism_different_input),
        ("Sim: Hash Determinism Key Order+Float", test_sim_hash_determinism_key_order_and_float),
        ("Sim: Correlation ID Lifecycle", test_sim_correlation_id_lifecycle),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Evolution Simulation Gate")
    print("  Mock Mutation Pipeline: 38 tests")
    print("=" * 60)
    print()

    for name, fn in tests:
        try:
            result = fn()
            if result:
                passed += 1
                print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")

    print()
    print(f"  Results: {passed}/{passed + failed} PASS")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)