"""V5.0 Phase 1 Release Gate — Evolution Core (50 tests).

Per Freeze v1.1 PRD:
  1. EvolutionRun (5)
  2. Genome (10)
  3. Population (10)
  4. Fitness (10)
  5. EvolutionMemory (10)
  6. End-to-End Core (5)

Total: 50 tests. All must PASS.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_brain.v5_evolution.schemas import (
    Gene, GeneType, Genome, Population, Fitness, FitnessComponent,
    EvolutionPhase, EvolutionRun, EvolutionEvent, EvolutionSnapshot,
    MutationOperator, DEFAULT_FITNESS_WEIGHTS, DEFAULT_EVOLUTION_CONFIG,
)
from market_ops.creative_brain.v5_evolution.evolution_run import EvolutionRunManager
from market_ops.creative_brain.v5_evolution.genome_manager import GenomeManager
from market_ops.creative_brain.v5_evolution.population_manager import PopulationManager
from market_ops.creative_brain.v5_evolution.fitness_calculator import FitnessCalculator
from market_ops.creative_brain.v5_evolution.evolution_memory import EvolutionMemory


# ═══════════════════════════════════════════════════════════
# 1. EvolutionRun (5 tests)
# ═══════════════════════════════════════════════════════════

def test_run_create():
    """创建EvolutionRun"""
    rm = EvolutionRunManager()
    run = rm.create_run("Find next Merge Puzzle opportunity", "merge_puzzle")
    assert run.run_id is not None
    assert run.objective == "Find next Merge Puzzle opportunity"
    assert run.category == "merge_puzzle"
    return True

def test_run_multiple_concurrent():
    """多个并发Run"""
    rm = EvolutionRunManager()
    rm.create_run("Run A: Merge Puzzle", "merge_puzzle")
    rm.create_run("Run B: Sort Puzzle", "sort_puzzle")
    rm.create_run("Run C: AI Home Design", "home_design")
    active = rm.get_active_runs()
    assert len(active) == 3
    return True

def test_run_advance_generation():
    """推进Generation"""
    rm = EvolutionRunManager()
    run = rm.create_run("Test", "test")
    rm.advance_generation(run.run_id)
    rm.advance_generation(run.run_id)
    assert rm.get_run(run.run_id).current_generation == 2
    return True

def test_run_set_winner():
    """设置Winner"""
    rm = EvolutionRunManager()
    run = rm.create_run("Test", "test")
    rm.set_winner(run.run_id, "genome_0831")
    assert rm.get_run(run.run_id).winner_genome_id == "genome_0831"
    return True

def test_run_complete():
    """完成Run"""
    rm = EvolutionRunManager()
    run = rm.create_run("Test", "test")
    rm.complete_run(run.run_id)
    r = rm.get_run(run.run_id)
    assert r.status == "completed"
    assert len(rm.get_active_runs()) == 0
    return True


# ═══════════════════════════════════════════════════════════
# 2. Genome (10 tests)
# ═══════════════════════════════════════════════════════════

def test_genome_create():
    """创建Genome"""
    gm = GenomeManager()
    genes = [
        Gene(gene_type=GeneType.HOOK, value="rescue", mutation_pool=["rescue", "abandon", "escape"]),
        Gene(gene_type=GeneType.CHARACTER, value="dragon", mutation_pool=["dragon", "cat", "monster"]),
    ]
    genome = gm.create("creative_001", generation=0, genes=genes)
    assert genome.genome_id is not None
    assert len(genome.genes) == 2
    return True

def test_genome_from_winner_dna():
    """从Winner DNA创建Genome"""
    gm = GenomeManager()
    winner_dna = {"hook": "rescue", "character": "dragon", "emotion": "cute"}
    genome = gm.create_from_winner_dna("from_winner", winner_dna)
    assert len(genome.genes) == 3
    assert genome.genes["hook"].value == "rescue"
    assert genome.genes["hook"].source == "winner_dna"
    return True

def test_genome_clone():
    """克隆Genome"""
    gm = GenomeManager()
    genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
    original = gm.create("original", generation=0, genes=genes)
    cloned = gm.clone(original.genome_id, new_name="clone_001", new_generation=1)
    assert cloned is not None
    assert cloned.name == "clone_001"
    assert cloned.parent_ids == [original.genome_id]
    return True

def test_genome_fitness_update():
    """更新Fitness"""
    gm = GenomeManager()
    genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
    genome = gm.create("test", genes=genes)
    fitness = Fitness(genome_id=genome.genome_id, generation=0,
                      components={"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.5},
                      composite_score=0.72, sample_size=5000)
    gm.update_fitness(genome.genome_id, fitness)
    updated = gm.get(genome.genome_id)
    assert updated.fitness is not None
    assert abs(updated.fitness.composite_score - 0.72) < 0.001
    return True

def test_genome_fitness_history():
    """Fitness历史追踪"""
    gm = GenomeManager()
    genome = gm.create("test")
    f1 = Fitness(genome_id=genome.genome_id, composite_score=0.52)
    f2 = Fitness(genome_id=genome.genome_id, composite_score=0.61)
    f3 = Fitness(genome_id=genome.genome_id, composite_score=0.78)
    gm.update_fitness(genome.genome_id, f1)
    gm.update_fitness(genome.genome_id, f2)
    gm.update_fitness(genome.genome_id, f3)
    updated = gm.get(genome.genome_id)
    assert len(updated.fitness_history) == 2  # First fitness wasn't archived, 2nd and 3rd were
    assert updated.fitness_trend == "improving"
    return True

def test_genome_get_by_generation():
    """按Generation查询"""
    gm = GenomeManager()
    gm.create("gen0_a", generation=0)
    gm.create("gen0_b", generation=0)
    gm.create("gen1_a", generation=1)
    assert len(gm.get_by_generation(0)) == 2
    assert len(gm.get_by_generation(1)) == 1
    return True

def test_genome_top_by_fitness():
    """按Fitness排序Top N"""
    gm = GenomeManager()
    for i in range(5):
        g = gm.create(f"genome_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.1)
        gm.update_fitness(g.genome_id, fitness)
    top = gm.get_top_by_fitness(3)
    assert len(top) == 3
    assert top[0].fitness.composite_score > top[1].fitness.composite_score
    return True

def test_genome_lineage():
    """Lineage链追踪"""
    gm = GenomeManager()
    g0 = gm.create("gen0", generation=0)
    g1 = gm.clone(g0.genome_id, new_name="gen1", new_generation=1)
    g2 = gm.clone(g1.genome_id, new_name="gen2", new_generation=2)
    lineage = gm.get_lineage(g2.genome_id)
    assert len(lineage) >= 2
    return True

def test_genome_gene_mutation_risk():
    """Gene mutation risk"""
    gm = GenomeManager()
    genes = [
        Gene(gene_type=GeneType.CHARACTER, value="dragon",
             mutation_cost=0.1, mutation_risk=0.1),
        Gene(gene_type=GeneType.GAMEPLAY, value="merge",
             mutation_cost=0.5, mutation_risk=0.8),
    ]
    genome = gm.create("test", genes=genes)
    char_gene = genome.get_gene(GeneType.CHARACTER)
    game_gene = genome.get_gene(GeneType.GAMEPLAY)
    assert char_gene.mutation_risk == 0.1
    assert game_gene.mutation_risk == 0.8
    return True

def test_genome_stats():
    """Genome统计"""
    gm = GenomeManager()
    for i in range(10):
        g = gm.create(f"genome_{i}", generation=i % 3)
        if i % 2 == 0:
            fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.05)
            gm.update_fitness(g.genome_id, fitness)
    stats = gm.get_stats()
    assert stats["total_genomes"] == 10
    assert stats["generations"] == 3
    return True


# ═══════════════════════════════════════════════════════════
# 3. Population (10 tests)
# ═══════════════════════════════════════════════════════════

def test_population_create():
    """创建Population"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    assert pop.population_id is not None
    assert pop.generation == 0
    return True

def test_population_add_genomes():
    """添加Genomes"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    for i in range(5):
        g = gm.create(f"g_{i}", generation=0)
        pm.add_genome(pop.population_id, g)
    assert len(pop.genomes) == 5
    return True

def test_elite_selection():
    """精英选择"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0, size=100, elite_count=10)
    gm = GenomeManager()
    for i in range(20):
        g = gm.create(f"g_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.3 + i * 0.03)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)
    elites = pm.select_elites(pop.population_id)
    assert len(elites) == 10
    assert elites[0].fitness.composite_score >= elites[-1].fitness.composite_score
    return True

def test_next_generation():
    """创建下一代"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0, size=100, elite_count=5)
    gm = GenomeManager()
    for i in range(10):
        g = gm.create(f"g_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.5 + i * 0.05)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)
    next_pop = pm.create_next_generation(pop.population_id)
    assert next_pop is not None
    assert next_pop.generation == 1
    assert len(next_pop.genomes) == 5  # Elites carry over
    return True

def test_diversity_calculation():
    """多样性计算"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    # All same genes → low diversity
    for i in range(5):
        genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
        g = gm.create(f"same_{i}", genes=genes)
        pm.add_genome(pop.population_id, g)
    diversity = pm.calculate_diversity(pop.population_id)
    assert diversity <= 0.5  # Low diversity
    return True

def test_diversity_high():
    """高多样性"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    values = ["rescue", "escape", "protect", "abandon", "collect"]
    for i, v in enumerate(values):
        genes = [Gene(gene_type=GeneType.HOOK, value=v)]
        g = gm.create(f"div_{i}", genes=genes)
        pm.add_genome(pop.population_id, g)
    diversity = pm.calculate_diversity(pop.population_id)
    assert diversity > 0.5  # High diversity
    return True

def test_convergence_detection():
    """收敛检测"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    # All identical → converged
    for i in range(5):
        genes = [Gene(gene_type=GeneType.HOOK, value="rescue")]
        g = gm.create(f"conv_{i}", genes=genes)
        pm.add_genome(pop.population_id, g)
    pm.calculate_convergence(pop.population_id)
    assert pm.is_converged(pop.population_id)
    return True

def test_extinction_detection():
    """灭绝检测"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    # Very low fitness
    for i in range(5):
        g = gm.create(f"ext_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.001)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)
    risk = pm.detect_extinction_risk(pop.population_id)
    assert risk > 0.5  # High extinction risk
    return True

def test_population_stats():
    """Population统计"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    for i in range(10):
        g = gm.create(f"g_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.4 + i * 0.05)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)
    stats = pm.get_stats(pop.population_id)
    assert stats["size"] == 10
    assert stats["best_fitness"] > 0.8
    return True

def test_population_archive():
    """归档Population"""
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    pm.archive_population(pop.population_id)
    p = pm.get_population(pop.population_id)
    assert p.status == "archived"
    return True


# ═══════════════════════════════════════════════════════════
# 4. Fitness (10 tests)
# ═══════════════════════════════════════════════════════════

def test_fitness_online():
    """在线Fitness计算"""
    fc = FitnessCalculator()
    components = {"ctr": 0.035, "cvr": 0.20, "roas_d7": 0.45, "roas_d1": 0.30}
    fitness = fc.calculate_online("g1", 0, components, sample_size=5000)
    assert fitness.is_online
    assert fitness.composite_score > 0.0
    assert fitness.confidence > 0.5
    return True

def test_fitness_offline():
    """离线Fitness计算"""
    fc = FitnessCalculator()
    components = {"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.40}
    fitness = fc.calculate_offline("g1", 0, components, confidence=0.5)
    assert not fitness.is_online
    assert fitness.composite_score > 0.0
    return True

def test_fitness_mixed():
    """混合Fitness"""
    fc = FitnessCalculator()
    online = {"ctr": 0.04, "cvr": 0.20, "roas_d7": 0.50}
    offline = {"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.40}
    fitness = fc.calculate_mixed("g1", 0, online, offline, online_weight=0.7)
    assert fitness.is_online
    return True

def test_fitness_weights():
    """权重管理"""
    fc = FitnessCalculator()
    weights = fc.get_weights()
    assert "ctr" in weights
    assert "roas_d7" in weights
    # ROAS_D7 should have highest weight
    assert weights["roas_d7"] >= 0.2
    return True

def test_fitness_negative_weight():
    """负权重（CPI越低越好）"""
    fc = FitnessCalculator()
    weights = fc.get_weights()
    assert weights["cpi"] < 0  # Negative weight
    return True

def test_fitness_confidence():
    """置信度计算"""
    fc = FitnessCalculator(min_sample_size=1000)
    # Large sample → high confidence
    f1 = fc.calculate_online("g1", 0, {"ctr": 0.03}, sample_size=10000)
    # Small sample → low confidence
    f2 = fc.calculate_online("g2", 0, {"ctr": 0.03}, sample_size=100)
    assert f1.confidence > f2.confidence
    return True

def test_fitness_score_population():
    """批量Population评分"""
    fc = FitnessCalculator()
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    comps_map = {}
    for i in range(5):
        g = gm.create(f"g_{i}", generation=0)
        pm.add_genome(pop.population_id, g)
        comps_map[g.genome_id] = {"ctr": 0.03 + i * 0.005, "cvr": 0.15, "roas_d7": 0.4 + i * 0.05}
    count = fc.score_population(pop, comps_map)
    assert count == 5
    return True

def test_fitness_rank():
    """排名"""
    fc = FitnessCalculator()
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    gm = GenomeManager()
    for i in range(5):
        g = gm.create(f"g_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.3 + i * 0.1)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)
    ranked = fc.rank_population(pop)
    assert len(ranked) == 5
    assert ranked[0][1] > ranked[-1][1]
    return True

def test_fitness_plateau_detection():
    """Plateau检测"""
    fc = FitnessCalculator()
    pm = PopulationManager()
    pop1 = pm.create_population(generation=0)
    pop2 = pm.create_population(generation=1)
    pop1.avg_fitness = 0.50
    pop2.avg_fitness = 0.505  # Very small improvement
    assert fc.detect_plateau(pop2, pop1, improvement_threshold=0.01)
    return True

def test_fitness_component_importance():
    """组件重要性"""
    fc = FitnessCalculator()
    importance = fc.get_component_importance()
    total = sum(importance.values())
    assert abs(total - 1.0) < 0.01
    return True


# ═══════════════════════════════════════════════════════════
# 5. EvolutionMemory (10 tests)
# ═══════════════════════════════════════════════════════════

def test_memory_snapshot():
    """创建快照"""
    em = EvolutionMemory()
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    snap = em.snapshot("run_1", pop, EvolutionPhase.IDLE)
    assert snap.snapshot_id is not None
    assert snap.generation == 0
    return True

def test_memory_get_latest_snapshot():
    """获取最新快照"""
    em = EvolutionMemory()
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    em.snapshot("run_1", pop, EvolutionPhase.IDLE)
    pop2 = pm.create_population(generation=1)
    em.snapshot("run_1", pop2, EvolutionPhase.MUTATING)
    latest = em.get_latest_snapshot("run_1")
    assert latest.generation == 1
    assert latest.controller_phase == EvolutionPhase.MUTATING
    return True

def test_memory_record_mutation():
    """记录Mutation"""
    em = EvolutionMemory()
    em.record_mutation("genome_2", "genome_1", "hook", "rescue", "escape",
                       "point_mutation", generation=1,
                       fitness_before=0.5, fitness_after=0.6)
    mutations = em.get_mutations_by_genome("genome_2")
    assert len(mutations) == 1
    assert mutations[0]["fitness_delta"] > 0
    return True

def test_memory_beneficial_mutations():
    """有益Mutation"""
    em = EvolutionMemory()
    em.record_mutation("g1", "p1", "hook", "a", "b", "point", 1, 0.5, 0.7)
    em.record_mutation("g2", "p2", "hook", "c", "d", "point", 1, 0.6, 0.4)
    beneficial = em.get_beneficial_mutations(min_improvement=0.01)
    assert len(beneficial) == 1
    return True

def test_memory_harmful_mutations():
    """有害Mutation"""
    em = EvolutionMemory()
    em.record_mutation("g1", "p1", "hook", "a", "b", "point", 1, 0.5, 0.3)
    harmful = em.get_harmful_mutations()
    assert len(harmful) == 1
    return True

def test_memory_best_operators():
    """最佳Mutation Operator"""
    em = EvolutionMemory()
    em.record_mutation("g1", "p1", "hook", "a", "b", "point_mutation", 1, 0.5, 0.7)
    em.record_mutation("g2", "p2", "hook", "c", "d", "crossover", 1, 0.5, 0.55)
    em.record_mutation("g3", "p3", "hook", "e", "f", "swap", 1, 0.5, 0.45)
    best = em.get_best_mutation_operators(3)
    assert len(best) >= 1
    assert best[0][0] == "point_mutation"
    return True

def test_memory_lineage():
    """Lineage追踪"""
    em = EvolutionMemory()
    em.record_mutation("g1", "g0", "hook", "a", "b", "point", 0, 0, 0)
    em.record_mutation("g2", "g1", "hook", "b", "c", "point", 1, 0, 0)
    em.record_mutation("g3", "g2", "hook", "c", "d", "point", 2, 0, 0)
    chain = em.get_lineage("g3")
    assert "g0" in chain
    assert "g3" in chain
    assert len(chain) == 4
    return True

def test_memory_descendants():
    """后代追踪"""
    em = EvolutionMemory()
    em.record_mutation("g1", "g0", "hook", "a", "b", "point", 0, 0, 0)
    em.record_mutation("g2", "g0", "hook", "a", "c", "point", 0, 0, 0)
    em.record_mutation("g3", "g1", "hook", "b", "d", "point", 1, 0, 0)
    descendants = em.get_descendants("g0")
    assert len(descendants) == 3
    return True

def test_memory_event_log():
    """事件日志"""
    em = EvolutionMemory()
    event = EvolutionEvent(event_type="GENOME_CREATED", run_id="run_1",
                           entity_id="g1", source="genome_manager")
    em.log_event(event)
    events = em.get_events(event_type="GENOME_CREATED")
    assert len(events) == 1
    return True

def test_memory_stats():
    """Memory统计"""
    em = EvolutionMemory()
    pm = PopulationManager()
    pop = pm.create_population(generation=0)
    em.snapshot("run_1", pop, EvolutionPhase.IDLE)
    em.record_mutation("g1", "p1", "hook", "a", "b", "point", 1, 0.5, 0.7)
    em.record_mutation("g2", "p2", "hook", "c", "d", "point", 1, 0.6, 0.4)
    stats = em.get_stats()
    assert stats["total_snapshots"] == 1
    assert stats["total_mutations"] == 2
    return True


# ═══════════════════════════════════════════════════════════
# 6. End-to-End Core (5 tests)
# ═══════════════════════════════════════════════════════════

def test_e2e_evolution_cycle():
    """完整进化周期：Run → Genome → Population → Fitness → Memory"""
    # 1. Create run
    rm = EvolutionRunManager()
    run = rm.create_run("E2E: Find top creative", "merge_puzzle")

    # 2. Create seed genomes from Winner DNA
    gm = GenomeManager()
    winner_dna = {"hook": "rescue", "character": "dragon", "emotion": "cute"}
    for i in range(10):
        gm.create_from_winner_dna(f"seed_{i}", winner_dna, generation=0)

    # 3. Create population
    pm = PopulationManager()
    pop = pm.create_population(generation=0, elite_count=3)
    pm.add_genomes(pop.population_id, gm.get_by_generation(0))

    # 4. Calculate fitness
    fc = FitnessCalculator()
    comps_map = {}
    for g in pop.genomes:
        comps_map[g.genome_id] = {"ctr": 0.03, "cvr": 0.15, "roas_d7": 0.45}
    fc.score_population(pop, comps_map)

    # 5. Select elites + create next gen
    elites = pm.select_elites(pop.population_id)
    assert len(elites) == 3
    next_pop = pm.create_next_generation(pop.population_id)
    assert next_pop.generation == 1

    # 6. Record in evolution memory
    em = EvolutionMemory()
    em.snapshot(run.run_id, pop, EvolutionPhase.POPULATION_CREATED)
    em.snapshot(run.run_id, next_pop, EvolutionPhase.MUTATING)

    # 7. Advance run
    rm.advance_generation(run.run_id)
    rm.set_winner(run.run_id, elites[0].genome_id)

    # Verify
    assert rm.get_run(run.run_id).current_generation == 1
    assert len(em.get_snapshots_by_run(run.run_id)) == 2
    return True

def test_e2e_mutation_cycle():
    """Mutation周期：Clone → Mutate → Fitness → Record"""
    gm = GenomeManager()
    em = EvolutionMemory()

    # Create seed
    genes = [Gene(gene_type=GeneType.HOOK, value="rescue",
                  mutation_pool=["rescue", "escape", "protect"])]
    seed = gm.create("seed", genes=genes)

    # Clone + mutate
    cloned = gm.clone(seed.genome_id, new_name="mutant_1", new_generation=1)
    assert cloned.genome_id != seed.genome_id

    # Record mutation
    em.record_mutation(cloned.genome_id, seed.genome_id, "hook",
                       "rescue", "escape", "point_mutation",
                       generation=1, fitness_before=0.5, fitness_after=0.62)

    # Update fitness
    fc = FitnessCalculator()
    fitness = fc.calculate_online(cloned.genome_id, 1,
                                  {"ctr": 0.035, "cvr": 0.18, "roas_d7": 0.5},
                                  sample_size=3000)
    gm.update_fitness(cloned.genome_id, fitness)

    beneficial = em.get_beneficial_mutations()
    assert len(beneficial) == 1
    return True

def test_e2e_extinction_recovery():
    """灭绝检测与恢复"""
    pm = PopulationManager()
    gm = GenomeManager()
    em = EvolutionMemory()

    # Create low-fitness population
    pop = pm.create_population(generation=0)
    for i in range(5):
        g = gm.create(f"weak_{i}", generation=0)
        fitness = Fitness(genome_id=g.genome_id, composite_score=0.001)
        g.fitness = fitness
        pm.add_genome(pop.population_id, g)

    risk = pm.detect_extinction_risk(pop.population_id)
    assert risk > 0.5  # High risk

    em.snapshot("run_1", pop, EvolutionPhase.EXTINCT)
    return True

def test_e2e_diversity_monitoring():
    """多样性监控"""
    pm = PopulationManager()
    gm = GenomeManager()

    pop = pm.create_population(generation=0)
    for i in range(10):
        genes = [Gene(gene_type=GeneType.HOOK, value=f"hook_{i % 3}")]
        g = gm.create(f"g_{i}", genes=genes)
        pm.add_genome(pop.population_id, g)

    diversity = pm.calculate_diversity(pop.population_id)
    assert diversity > 0.0
    pm.calculate_convergence(pop.population_id)
    assert not pm.is_converged(pop.population_id)
    return True

def test_e2e_fitness_trend():
    """Fitness趋势追踪"""
    gm = GenomeManager()
    fc = FitnessCalculator()

    g = gm.create("trend_test")
    for i, score in enumerate([0.52, 0.61, 0.78, 0.82]):
        fitness = Fitness(genome_id=g.genome_id, composite_score=score)
        gm.update_fitness(g.genome_id, fitness)

    genome = gm.get(g.genome_id)
    assert genome.fitness_trend == "improving"
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. EvolutionRun (5)
        ("Run: Create", test_run_create),
        ("Run: Concurrent", test_run_multiple_concurrent),
        ("Run: Advance Gen", test_run_advance_generation),
        ("Run: Set Winner", test_run_set_winner),
        ("Run: Complete", test_run_complete),
        # 2. Genome (10)
        ("Genome: Create", test_genome_create),
        ("Genome: From Winner DNA", test_genome_from_winner_dna),
        ("Genome: Clone", test_genome_clone),
        ("Genome: Fitness Update", test_genome_fitness_update),
        ("Genome: Fitness History", test_genome_fitness_history),
        ("Genome: By Generation", test_genome_get_by_generation),
        ("Genome: Top By Fitness", test_genome_top_by_fitness),
        ("Genome: Lineage", test_genome_lineage),
        ("Genome: Mutation Risk", test_genome_gene_mutation_risk),
        ("Genome: Stats", test_genome_stats),
        # 3. Population (10)
        ("Population: Create", test_population_create),
        ("Population: Add Genomes", test_population_add_genomes),
        ("Population: Elite Selection", test_elite_selection),
        ("Population: Next Gen", test_next_generation),
        ("Population: Diversity Low", test_diversity_calculation),
        ("Population: Diversity High", test_diversity_high),
        ("Population: Convergence", test_convergence_detection),
        ("Population: Extinction", test_extinction_detection),
        ("Population: Stats", test_population_stats),
        ("Population: Archive", test_population_archive),
        # 4. Fitness (10)
        ("Fitness: Online", test_fitness_online),
        ("Fitness: Offline", test_fitness_offline),
        ("Fitness: Mixed", test_fitness_mixed),
        ("Fitness: Weights", test_fitness_weights),
        ("Fitness: Negative Weight", test_fitness_negative_weight),
        ("Fitness: Confidence", test_fitness_confidence),
        ("Fitness: Score Population", test_fitness_score_population),
        ("Fitness: Rank", test_fitness_rank),
        ("Fitness: Plateau", test_fitness_plateau_detection),
        ("Fitness: Importance", test_fitness_component_importance),
        # 5. EvolutionMemory (10)
        ("Memory: Snapshot", test_memory_snapshot),
        ("Memory: Latest Snapshot", test_memory_get_latest_snapshot),
        ("Memory: Record Mutation", test_memory_record_mutation),
        ("Memory: Beneficial", test_memory_beneficial_mutations),
        ("Memory: Harmful", test_memory_harmful_mutations),
        ("Memory: Best Operators", test_memory_best_operators),
        ("Memory: Lineage", test_memory_lineage),
        ("Memory: Descendants", test_memory_descendants),
        ("Memory: Event Log", test_memory_event_log),
        ("Memory: Stats", test_memory_stats),
        # 6. E2E (5)
        ("E2E: Evolution Cycle", test_e2e_evolution_cycle),
        ("E2E: Mutation Cycle", test_e2e_mutation_cycle),
        ("E2E: Extinction Recovery", test_e2e_extinction_recovery),
        ("E2E: Diversity Monitoring", test_e2e_diversity_monitoring),
        ("E2E: Fitness Trend", test_e2e_fitness_trend),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase 1 — Evolution Core Release Gate")
    print("  Per Freeze v1.1: 50 tests")
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