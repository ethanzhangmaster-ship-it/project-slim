"""V5.0 Phase D.1 — Genome Integration Release Gate (14 tests).

Validates CreativeGenomeBuilder:
  1. Module imports correctly (no cv2 / external deps)
  2. Single genome build from CreativePerformance
  3. Genome structure: genes, fitness, metadata
  4. Gene mutation pools populated
  5. DNA inference from creative_name
  6. Fitness calculation with available metrics
  7. Seed population builds from CSV (1292+ creatives)
  8. Population structure: generation, genomes, stats
  9. Winners correctly tagged
  10. GenomeManager registration
  11. Elite genomes have fitness
  12. Platform / audience genes from performance
  13. Summary statistics
  14. Persistence to disk

All tests must PASS before Phase D.2 (Mutation Engine Integration).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_performance_builder import (
    CreativePerformanceBuilder,
    CreativePerformance,
)
from market_ops.creative_genome_builder import (
    CreativeGenomeBuilder,
    SEED_FITNESS_WEIGHTS,
    DEFAULT_MUTATION_POOLS,
)
from market_ops.creative_brain.v5_evolution.schemas import Genome, GeneType, Fitness
from market_ops.creative_brain.v5_evolution.genome_manager import GenomeManager
from market_ops.creative_brain.v5_evolution.population_manager import PopulationManager


# ═══════════════════════════════════════════════════════════
# 1. Module & Import (2 tests)
# ═══════════════════════════════════════════════════════════

def test_module_imports_without_cv2():
    """Import: module loads without opencv/cv2 dependency"""
    # If we got here, import already succeeded
    assert CreativeGenomeBuilder is not None
    assert SEED_FITNESS_WEIGHTS is not None
    assert "roas_d7" in SEED_FITNESS_WEIGHTS
    return True


def test_seed_fitness_weights_structure():
    """Import: seed fitness weights are well-formed"""
    assert isinstance(SEED_FITNESS_WEIGHTS, dict)
    assert len(SEED_FITNESS_WEIGHTS) >= 4
    total = sum(abs(v) for v in SEED_FITNESS_WEIGHTS.values())
    assert 0.9 <= total <= 1.1, f"Weights sum to {total}, expected ~1.0"
    return True


# ═══════════════════════════════════════════════════════════
# 2. Single Genome Build (4 tests)
# ═══════════════════════════════════════════════════════════

def test_build_genome_from_performance():
    """Genome: builds from a single CreativePerformance"""
    perf_builder = CreativePerformanceBuilder()
    all_perf = perf_builder.load()
    assert len(all_perf) > 0, "No performances loaded"

    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    genome = gb.build_genome(all_perf[0])

    assert isinstance(genome, Genome)
    assert genome.genome_id != ""
    assert genome.generation == 0
    return True


def test_genome_has_expected_genes():
    """Genome: contains all expected gene types"""
    perf_builder = CreativePerformanceBuilder()
    all_perf = perf_builder.load()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    genome = gb.build_genome(all_perf[0])

    expected_types = {"hook", "emotion", "pacing", "gameplay", "story", "visual", "platform", "audience"}
    actual_types = set(genome.genes.keys())
    assert expected_types.issubset(actual_types), f"Missing genes: {expected_types - actual_types}"
    return True


def test_genome_fitness_calculated():
    """Genome: fitness object with composite_score"""
    perf_builder = CreativePerformanceBuilder()
    all_perf = perf_builder.load()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)

    # Pick a performance with some metrics
    perf = next((p for p in all_perf if p.roas > 0 or p.ctr > 0), all_perf[0])
    genome = gb.build_genome(perf)

    assert genome.fitness is not None, "Fitness not assigned"
    assert isinstance(genome.fitness, Fitness)
    assert genome.fitness.composite_score >= 0.0
    assert genome.fitness.genome_id == genome.genome_id
    return True


def test_genome_metadata_complete():
    """Genome: metadata contains creative context"""
    perf_builder = CreativePerformanceBuilder()
    all_perf = perf_builder.load()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    genome = gb.build_genome(all_perf[0])

    assert genome.metadata.get("creative_id") == all_perf[0].creative_id
    assert "platform" in genome.metadata
    assert "decision" in genome.metadata
    assert "source" in genome.metadata
    return True


# ═══════════════════════════════════════════════════════════
# 3. DNA Inference & Gene Quality (3 tests)
# ═══════════════════════════════════════════════════════════

def test_dna_inference_from_name():
    """DNA: _infer_dna extracts labels from creative name"""
    gb = CreativeGenomeBuilder()
    labels = gb._infer_dna("Merge Dragon Rescue - Fast Cut - iOS")

    assert isinstance(labels, dict)
    assert labels.get("hook_type") == "crisis"  # "rescue" maps to crisis
    assert labels.get("ui_type") == "merge"
    assert labels.get("pace") == "fast"
    return True


def test_mutation_pools_populated():
    """Gene: mutation pools contain multiple values"""
    gb = CreativeGenomeBuilder()
    labels = gb._infer_dna("Merge Dragon - iOS")
    genes, _ = gb._build_genes(labels, CreativePerformance(creative_id="test", platform="ios"))

    for gene in genes:
        assert len(gene.mutation_pool) >= 1, f"Gene {gene.gene_type.value} has empty pool"
        assert gene.value in gene.mutation_pool, f"Current value not in pool for {gene.gene_type.value}"
    return True


def test_platform_and_audience_genes():
    """Gene: platform/audience derived from performance"""
    perf = CreativePerformance(creative_id="test", platform="ios", country="US")
    gb = CreativeGenomeBuilder()
    labels = gb._infer_dna("test creative")
    genes, _ = gb._build_genes(labels, perf)

    gene_map = {g.gene_type.value: g for g in genes}
    assert "platform" in gene_map
    assert "audience" in gene_map
    assert gene_map["platform"].value == "ios"
    assert gene_map["audience"].value == "us"
    return True


# ═══════════════════════════════════════════════════════════
# 4. Seed Population (4 tests)
# ═══════════════════════════════════════════════════════════

def test_seed_population_builds_all_creatives():
    """Population: builds genomes for all 1292+ creatives"""
    perf_builder = CreativePerformanceBuilder()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    population = gb.build_seed_population()

    assert population.generation == 0
    assert len(population.genomes) >= 1200, f"Expected >=1200 genomes, got {len(population.genomes)}"
    return True


def test_seed_population_has_winners():
    """Population: winners are tagged and have fitness"""
    perf_builder = CreativePerformanceBuilder()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    population = gb.build_seed_population()

    winners = [g for g in population.genomes if g.metadata.get("is_winner")]
    assert len(winners) >= 10, f"Expected >=10 winners, got {len(winners)}"

    for w in winners:
        assert w.fitness is not None, f"Winner {w.genome_id} missing fitness"
    return True


def test_seed_population_stats_calculated():
    """Population: best/avg/median fitness computed"""
    perf_builder = CreativePerformanceBuilder()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    population = gb.build_seed_population()

    assert population.best_fitness >= 0.0
    assert population.avg_fitness >= 0.0
    assert population.median_fitness >= 0.0
    assert population.best_fitness >= population.avg_fitness
    return True


def test_genome_manager_registration():
    """GenomeManager: all seed genomes registered"""
    perf_builder = CreativePerformanceBuilder()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    population = gb.build_seed_population()

    total_in_mgr = gb._genome_manager.get_count()
    assert total_in_mgr == len(population.genomes), (
        f"Manager has {total_in_mgr} genomes, population has {len(population.genomes)}"
    )

    gen0 = gb._genome_manager.get_by_generation(0)
    assert len(gen0) == len(population.genomes)
    return True


# ═══════════════════════════════════════════════════════════
# 5. Persistence & Summary (1 test)
# ═══════════════════════════════════════════════════════════

def test_save_and_summary():
    """Persistence: save outputs JSON, summary is accurate"""
    perf_builder = CreativePerformanceBuilder()
    gb = CreativeGenomeBuilder(performance_builder=perf_builder)
    gb.build_seed_population()

    with tempfile.TemporaryDirectory() as tmpdir:
        saved = gb.save(output_dir=Path(tmpdir))
        assert saved["genomes"].exists(), "Genomes JSON not saved"
        assert saved["stats"].exists(), "Stats JSON not saved"

        import json
        data = json.loads(saved["genomes"].read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == gb._genome_manager.get_count()

    summary = gb.get_summary()
    assert summary["total_genomes"] == gb._genome_manager.get_count()
    assert summary["winners"] >= 10
    assert summary["with_fitness"] == summary["total_genomes"]
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1. Module & Import (2)
        ("Import: no cv2 dependency", test_module_imports_without_cv2),
        ("Import: seed weights well-formed", test_seed_fitness_weights_structure),
        # 2. Single Genome Build (4)
        ("Genome: build from performance", test_build_genome_from_performance),
        ("Genome: expected gene types", test_genome_has_expected_genes),
        ("Genome: fitness calculated", test_genome_fitness_calculated),
        ("Genome: metadata complete", test_genome_metadata_complete),
        # 3. DNA Inference & Gene Quality (3)
        ("DNA: inference from name", test_dna_inference_from_name),
        ("Gene: mutation pools populated", test_mutation_pools_populated),
        ("Gene: platform/audience derived", test_platform_and_audience_genes),
        # 4. Seed Population (4)
        ("Population: builds all creatives", test_seed_population_builds_all_creatives),
        ("Population: winners tagged", test_seed_population_has_winners),
        ("Population: stats computed", test_seed_population_stats_calculated),
        ("GenomeManager: registration", test_genome_manager_registration),
        # 5. Persistence & Summary (1)
        ("Persistence: save + summary", test_save_and_summary),
    ]

    passed = 0
    failed = 0
    print("=" * 60)
    print("  V5.0 Phase D.1 — Genome Integration Release Gate")
    print("  14 tests")
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
