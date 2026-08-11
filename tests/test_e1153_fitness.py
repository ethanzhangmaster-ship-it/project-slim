"""E11.5.3 — Real-world Fitness Engine (IAP) Test.

12 AC covering:
  1.  Fitness Schema
  2.  IAP Weight Calculation
  3.  Retention Score
  4.  Acquisition Score
  5.  LTV Normalization
  6.  Confidence Score
  7.  Full Fitness Calculation
  8.  Genome Update
  9.  Ranking
  10. History
  11. Serialization
  12. Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.genome.schema import CreativeGenome, GENE_SLOTS
from market_ops.e11.market import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
    PerformanceFeedback,
    MarketSignal,
    MarketSignalProcessor,
    GenomeFitness,
    FitnessHistory,
    FitnessHistoryEntry,
    FitnessCalculator,
    FitnessEngine,
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


def _make_signal(creative_id: str = "creative_001", genome_id: str = "genome_001") -> MarketSignal:
    processor = MarketSignalProcessor()
    return processor.process(_make_full_feedback(creative_id), genome_id=genome_id)


def _make_genome(genome_id: str = "genome_001") -> CreativeGenome:
    return CreativeGenome(
        genome_id=genome_id,
        generation=1,
        genes={
            slot: {"type": "default", "strength": 0.5}
            for slot in GENE_SLOTS
        },
        fitness={"ctr": 0.5},
    )


def _make_calculator() -> FitnessCalculator:
    return FitnessCalculator()


def _make_engine() -> FitnessEngine:
    return FitnessEngine()


# ═══════════════════════════════════════════════════════════
# AC1 — Fitness Schema
# ═══════════════════════════════════════════════════════════

def test_ac1_genome_fitness_create():
    """AC1a: GenomeFitness creates with all fields."""
    fitness = GenomeFitness(
        genome_id="genome_001",
        creative_id="creative_001",
        fitness_score=0.91,
        monetization_score=0.95,
        retention_score=0.85,
        acquisition_score=0.88,
        ltv_score=0.92,
        confidence=0.95,
        sample_size=30000,
    )

    assert fitness.fitness_id.startswith("fit_")
    assert fitness.genome_id == "genome_001"
    assert fitness.fitness_score == 0.91
    assert fitness.monetization_score == 0.95
    assert fitness.confidence == 0.95


def test_ac1b_fitness_is_elite():
    """AC1b: is_elite=True when fitness >= 0.85."""
    assert GenomeFitness(fitness_score=0.85).is_elite is True
    assert GenomeFitness(fitness_score=0.84).is_elite is False


def test_ac1c_fitness_is_strong():
    """AC1c: is_strong=True when fitness >= 0.70."""
    assert GenomeFitness(fitness_score=0.70).is_strong is True
    assert GenomeFitness(fitness_score=0.69).is_strong is False


def test_ac1d_fitness_is_weak():
    """AC1d: is_weak=True when fitness < 0.40."""
    assert GenomeFitness(fitness_score=0.39).is_weak is True
    assert GenomeFitness(fitness_score=0.40).is_weak is False


def test_ac1e_fitness_dominant_dimension():
    """AC1e: dominant_dimension returns highest scoring dimension."""
    fitness = GenomeFitness(
        monetization_score=0.95,
        retention_score=0.85,
        acquisition_score=0.70,
        ltv_score=0.80,
    )
    assert fitness.dominant_dimension() == "monetization"


# ═══════════════════════════════════════════════════════════
# AC2 — IAP Weight Calculation
# ═══════════════════════════════════════════════════════════

def test_ac2_default_weights():
    """AC2a: Default weights sum to 1.0."""
    calc = _make_calculator()
    weights = calc.weights
    total = sum(weights.values())
    assert total == pytest.approx(1.0)


def test_ac2b_weights_monetization():
    """AC2b: Monetization weight is 0.40."""
    calc = _make_calculator()
    assert calc.weights["monetization"] == 0.40


def test_ac2c_weights_retention():
    """AC2c: Retention weight is 0.30."""
    calc = _make_calculator()
    assert calc.weights["retention"] == 0.30


def test_ac2d_weights_acquisition():
    """AC2d: Acquisition weight is 0.20."""
    calc = _make_calculator()
    assert calc.weights["acquisition"] == 0.20


def test_ac2e_weights_confidence():
    """AC2e: Confidence weight is 0.10."""
    calc = _make_calculator()
    assert calc.weights["confidence"] == 0.10


def test_ac2f_custom_weights():
    """AC2f: Custom weights override defaults."""
    calc = FitnessCalculator(weights={
        "monetization": 0.50,
        "retention": 0.30,
        "acquisition": 0.15,
        "confidence": 0.05,
    })
    assert calc.weights["monetization"] == 0.50


# ═══════════════════════════════════════════════════════════
# AC3 — Retention Score
# ═══════════════════════════════════════════════════════════

def test_ac3_retention_score_in_fitness():
    """AC3a: Fitness includes retention_score."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.retention_score > 0.0
    assert fitness.retention_score <= 1.0


def test_ac3b_high_retention_high_score():
    """AC3b: High retention → high retention_score."""
    fb = _make_full_feedback()
    fb.engagement_metrics = _make_eng(d7=0.55, d30=0.35, playtime=55.0, level=8.0)
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.retention_score > 0.5


def test_ac3c_low_retention_low_score():
    """AC3c: Low retention → low retention_score."""
    fb = _make_full_feedback()
    fb.engagement_metrics = _make_eng(d7=0.10, d30=0.03, playtime=5.0, level=1.0)
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.retention_score < 0.4


# ═══════════════════════════════════════════════════════════
# AC4 — Acquisition Score
# ═══════════════════════════════════════════════════════════

def test_ac4_acquisition_score_in_fitness():
    """AC4a: Fitness includes acquisition_score."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.acquisition_score > 0.0
    assert fitness.acquisition_score <= 1.0


def test_ac4b_good_ua_high_acquisition():
    """AC4b: Good UA metrics → high acquisition."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=30000, spend=15000.0)  # CPI=0.5
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.acquisition_score > 0.5


def test_ac4c_poor_ua_low_acquisition():
    """AC4c: Poor UA metrics → low acquisition."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=1000, spend=15000.0)  # CPI=15
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.acquisition_score < 0.4


# ═══════════════════════════════════════════════════════════
# AC5 — LTV Normalization
# ═══════════════════════════════════════════════════════════

def test_ac5_ltv_score_in_fitness():
    """AC5a: Fitness includes ltv_score."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.ltv_score > 0.0
    assert fitness.ltv_score <= 1.0


def test_ac5b_high_ltv_reflected():
    """AC5b: High LTV + high pay_rate → high monetization score."""
    fb = _make_full_feedback()
    fb.monetization_metrics = _make_iap(
        revenue=100000, payers=5000, installs=30000,
        d30_ltv=12.0, d7_ltv=4.0,
    )  # high pay_rate + high LTV
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.monetization_score > 0.6


# ═══════════════════════════════════════════════════════════
# AC6 — Confidence Score
# ═══════════════════════════════════════════════════════════

def test_ac6_confidence_in_fitness():
    """AC6a: Fitness includes confidence score."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.confidence > 0.0
    assert fitness.confidence <= 1.0


def test_ac6b_large_sample_high_confidence():
    """AC6b: Large sample → high confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=50000)
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.confidence > 0.8


def test_ac6c_small_sample_low_confidence():
    """AC6c: Small sample → low confidence."""
    fb = _make_full_feedback()
    fb.ua_metrics = _make_ua(installs=100)
    signal = MarketSignalProcessor().process(fb)
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.confidence < 0.5


# ═══════════════════════════════════════════════════════════
# AC7 — Full Fitness Calculation
# ═══════════════════════════════════════════════════════════

def test_ac7_full_fitness_calculation():
    """AC7a: calculate() returns complete GenomeFitness."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert fitness.fitness_score > 0.0
    assert fitness.monetization_score > 0.0
    assert fitness.retention_score > 0.0
    assert fitness.acquisition_score > 0.0
    assert fitness.ltv_score > 0.0
    assert fitness.confidence > 0.0
    assert fitness.sample_size > 0
    assert fitness.weight_breakdown


def test_ac7b_fitness_score_in_range():
    """AC7b: fitness_score is always in [0, 1]."""
    signal = _make_signal()
    calc = _make_calculator()
    fitness = calc.calculate(signal)

    assert 0.0 <= fitness.fitness_score <= 1.0


def test_ac7c_calculate_batch():
    """AC7c: calculate_batch returns list of GenomeFitness."""
    signals = [_make_signal(f"c_{i}") for i in range(3)]
    calc = _make_calculator()
    results = calc.calculate_batch(signals)

    assert len(results) == 3
    for r in results:
        assert isinstance(r, GenomeFitness)


def test_ac7d_weight_breakdown_recorded():
    """AC7d: weight_breakdown matches calculator weights."""
    calc = _make_calculator()
    signal = _make_signal()
    fitness = calc.calculate(signal)

    assert fitness.weight_breakdown["monetization"] == calc.weights["monetization"]
    assert fitness.weight_breakdown["retention"] == calc.weights["retention"]
    assert fitness.weight_breakdown["acquisition"] == calc.weights["acquisition"]
    assert fitness.weight_breakdown["confidence"] == calc.weights["confidence"]


# ═══════════════════════════════════════════════════════════
# AC8 — Genome Update
# ═══════════════════════════════════════════════════════════

def test_ac8_engine_evaluate():
    """AC8a: Engine.evaluate() returns GenomeFitness."""
    engine = _make_engine()
    signal = _make_signal()
    fitness = engine.evaluate(signal)

    assert isinstance(fitness, GenomeFitness)
    assert fitness.fitness_score > 0.0


def test_ac8b_engine_update_genome():
    """AC8b: update_genome() sets real market fitness."""
    engine = _make_engine()
    genome = _make_genome()
    signal = _make_signal()
    fitness = engine.evaluate(signal)

    updated = engine.update_genome(genome, fitness)

    assert isinstance(updated.fitness, dict)
    assert updated.fitness.get("fitness_score") == fitness.fitness_score
    assert updated.fitness.get("source") == "real_market"


def test_ac8c_update_genome_gene_strengths():
    """AC8c: update_genome() updates gene strengths."""
    engine = _make_engine()
    genome = _make_genome()
    signal = _make_signal()
    fitness = engine.evaluate(signal)

    updated = engine.update_genome(genome, fitness)

    # Check hook gene is updated
    hook = updated.genes.get("hook", {})
    assert isinstance(hook, dict)
    assert "strength" in hook
    assert hook.get("fitness_source") == "real_market"


def test_ac8d_update_genome_preserves_other_genes():
    """AC8d: update_genome() preserves genes not in mapping."""
    engine = _make_engine()
    genome = _make_genome()
    genome.genes["custom_slot"] = {"type": "custom", "strength": 0.5}
    signal = _make_signal()
    fitness = engine.evaluate(signal)

    updated = engine.update_genome(genome, fitness)

    assert "custom_slot" in updated.genes


# ═══════════════════════════════════════════════════════════
# AC9 — Ranking
# ═══════════════════════════════════════════════════════════

def test_ac9_rank_genomes():
    """AC9a: rank_genomes() sorts by fitness descending."""
    engine = _make_engine()

    g1 = _make_genome("genome_A")
    engine.update_genome(g1, GenomeFitness(genome_id="genome_A", fitness_score=0.7))
    g2 = _make_genome("genome_B")
    engine.update_genome(g2, GenomeFitness(genome_id="genome_B", fitness_score=0.9))
    g3 = _make_genome("genome_C")
    engine.update_genome(g3, GenomeFitness(genome_id="genome_C", fitness_score=0.5))

    ranked = engine.rank_genomes([g1, g2, g3])
    assert ranked[0].genome_id == "genome_B"
    assert ranked[1].genome_id == "genome_A"
    assert ranked[2].genome_id == "genome_C"


def test_ac9b_get_top_genomes():
    """AC9b: get_top_genomes() returns top N."""
    engine = _make_engine()

    genomes = []
    for i in range(10):
        g = _make_genome(f"genome_{i}")
        engine.update_genome(g, GenomeFitness(genome_id=f"genome_{i}", fitness_score=0.5 + i * 0.05))
        genomes.append(g)

    top = engine.get_top_genomes(genomes, top_n=3)
    assert len(top) == 3
    assert top[0].genome_id == "genome_9"


def test_ac9c_rank_empty_list():
    """AC9c: rank_genomes() handles empty list."""
    engine = _make_engine()
    assert engine.rank_genomes([]) == []


def test_ac9d_extract_fitness_score():
    """AC9d: _extract_fitness_score handles dict and non-dict."""
    engine = _make_engine()

    g = _make_genome()
    engine.update_genome(g, GenomeFitness(fitness_score=0.85))
    assert engine._extract_fitness_score(g) == 0.85

    g.fitness = 0.5
    assert engine._extract_fitness_score(g) == 0.0  # non-dict returns 0.0


# ═══════════════════════════════════════════════════════════
# AC10 — History
# ═══════════════════════════════════════════════════════════

def test_ac10_record_fitness():
    """AC10a: record_fitness() creates history entry."""
    engine = _make_engine()
    genome = _make_genome()
    signal = _make_signal()
    fitness = engine.evaluate(signal)

    history = engine.record_fitness(genome, fitness, date="2026-07")
    assert history.entry_count == 1
    assert history.entries[0].date == "2026-07"


def test_ac10b_get_history():
    """AC10b: get_history() retrieves history."""
    engine = _make_engine()
    genome = _make_genome()
    fitness = engine.evaluate(_make_signal())
    engine.record_fitness(genome, fitness, date="2026-07")

    history = engine.get_history(genome.genome_id)
    assert history is not None
    assert history.genome_id == genome.genome_id


def test_ac10c_history_trend_improving():
    """AC10c: History trend is improving when scores rise."""
    engine = _make_engine()
    genome = _make_genome()

    engine.record_fitness(genome, GenomeFitness(fitness_score=0.5), date="2026-06")
    engine.record_fitness(genome, GenomeFitness(fitness_score=0.7), date="2026-07")
    engine.record_fitness(genome, GenomeFitness(fitness_score=0.9), date="2026-08")

    history = engine.get_history(genome.genome_id)
    assert history.trend == "improving"


def test_ac10d_history_trend_declining():
    """AC10d: History trend is declining when scores drop."""
    engine = _make_engine()
    genome = _make_genome()

    engine.record_fitness(genome, GenomeFitness(fitness_score=0.9), date="2026-06")
    engine.record_fitness(genome, GenomeFitness(fitness_score=0.7), date="2026-07")
    engine.record_fitness(genome, GenomeFitness(fitness_score=0.5), date="2026-08")

    history = engine.get_history(genome.genome_id)
    assert history.trend == "declining"


def test_ac10e_history_trend_stable():
    """AC10e: History trend is stable when scores don't change much."""
    engine = _make_engine()
    genome = _make_genome()

    engine.record_fitness(genome, GenomeFitness(fitness_score=0.80), date="2026-06")
    engine.record_fitness(genome, GenomeFitness(fitness_score=0.82), date="2026-07")

    history = engine.get_history(genome.genome_id)
    assert history.trend == "stable"


def test_ac10f_history_trend_insufficient():
    """AC10f: Insufficient entries → insufficient trend."""
    history = FitnessHistory(genome_id="g1")
    assert history.trend == "insufficient"


def test_ac10g_get_declining_genomes():
    """AC10g: get_declining_genomes() returns declining IDs."""
    engine = _make_engine()

    g1 = _make_genome("genome_A")
    engine.record_fitness(g1, GenomeFitness(fitness_score=0.9), date="2026-06")
    engine.record_fitness(g1, GenomeFitness(fitness_score=0.5), date="2026-07")

    g2 = _make_genome("genome_B")
    engine.record_fitness(g2, GenomeFitness(fitness_score=0.5), date="2026-06")
    engine.record_fitness(g2, GenomeFitness(fitness_score=0.9), date="2026-07")

    declining = engine.get_declining_genomes()
    assert "genome_A" in declining
    assert "genome_B" not in declining


def test_ac10h_get_improving_genomes():
    """AC10h: get_improving_genomes() returns improving IDs."""
    engine = _make_engine()

    g1 = _make_genome("genome_A")
    engine.record_fitness(g1, GenomeFitness(fitness_score=0.5), date="2026-06")
    engine.record_fitness(g1, GenomeFitness(fitness_score=0.9), date="2026-07")

    g2 = _make_genome("genome_B")
    engine.record_fitness(g2, GenomeFitness(fitness_score=0.9), date="2026-06")
    engine.record_fitness(g2, GenomeFitness(fitness_score=0.5), date="2026-07")

    improving = engine.get_improving_genomes()
    assert "genome_A" in improving
    assert "genome_B" not in improving


# ═══════════════════════════════════════════════════════════
# AC11 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac11_genome_fitness_serialization():
    """AC11a: GenomeFitness to_dict/from_dict roundtrip."""
    fitness = GenomeFitness(
        genome_id="genome_001",
        fitness_score=0.91,
        monetization_score=0.95,
        retention_score=0.85,
        acquisition_score=0.88,
        ltv_score=0.92,
        confidence=0.95,
        sample_size=30000,
        weight_breakdown={"monetization": 0.40},
    )

    d = fitness.to_dict()
    restored = GenomeFitness.from_dict(d)

    assert restored.fitness_id == fitness.fitness_id
    assert restored.fitness_score == fitness.fitness_score
    assert restored.monetization_score == fitness.monetization_score
    assert restored.weight_breakdown == fitness.weight_breakdown


def test_ac11b_fitness_history_entry_serialization():
    """AC11b: FitnessHistoryEntry to_dict/from_dict roundtrip."""
    entry = FitnessHistoryEntry(
        date="2026-07",
        fitness_score=0.85,
        monetization_score=0.90,
        retention_score=0.80,
        acquisition_score=0.85,
        ltv_score=0.88,
        sample_size=30000,
    )

    d = entry.to_dict()
    restored = FitnessHistoryEntry.from_dict(d)

    assert restored.date == "2026-07"
    assert restored.fitness_score == 0.85


def test_ac11c_fitness_history_serialization():
    """AC11c: FitnessHistory to_dict/from_dict roundtrip."""
    history = FitnessHistory(genome_id="genome_001")
    history.add_entry(FitnessHistoryEntry(date="2026-07", fitness_score=0.72))
    history.add_entry(FitnessHistoryEntry(date="2026-08", fitness_score=0.89))

    d = history.to_dict()
    restored = FitnessHistory.from_dict(d)

    assert restored.history_id == history.history_id
    assert restored.entry_count == 2
    assert restored.trend == history.trend


def test_ac11d_fitness_engine_serialization():
    """AC11d: FitnessEngine to_dict/from_dict roundtrip."""
    engine = _make_engine()
    genome = _make_genome()
    fitness = engine.evaluate(_make_signal())
    engine.record_fitness(genome, fitness, date="2026-07")

    d = engine.to_dict()
    restored = FitnessEngine.from_dict(d)

    restored_history = restored.get_history(genome.genome_id)
    assert restored_history is not None
    assert restored_history.entry_count == 1


# ═══════════════════════════════════════════════════════════
# AC12 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac12_deterministic_calculator():
    """AC12a: Same signal → same fitness."""
    signal1 = _make_signal()
    signal2 = _make_signal()

    calc1 = _make_calculator()
    calc2 = _make_calculator()

    f1 = calc1.calculate(signal1)
    f2 = calc2.calculate(signal2)

    assert f1.fitness_score == f2.fitness_score
    assert f1.monetization_score == f2.monetization_score
    assert f1.retention_score == f2.retention_score
    assert f1.acquisition_score == f2.acquisition_score


def test_ac12b_deterministic_engine_rank():
    """AC12b: Same genomes → same ranking."""
    engine1 = _make_engine()
    engine2 = _make_engine()

    g1 = _make_genome("A")
    g2 = _make_genome("B")
    engine1.update_genome(g1, GenomeFitness(fitness_score=0.7))
    engine1.update_genome(g2, GenomeFitness(fitness_score=0.9))
    engine2.update_genome(_make_genome("A"), GenomeFitness(fitness_score=0.7))
    engine2.update_genome(_make_genome("B"), GenomeFitness(fitness_score=0.9))

    r1 = engine1.rank_genomes([g1, g2])
    r2 = engine2.rank_genomes([g2, g1])  # different input order

    assert r1[0].genome_id == r2[0].genome_id
    assert r1[1].genome_id == r2[1].genome_id


def test_ac12c_deterministic_weighted_score():
    """AC12c: Weighted score calculation is deterministic."""
    calc = _make_calculator()
    signal = _make_signal()

    f1 = calc.calculate(signal)
    f2 = calc.calculate(signal)

    assert f1.fitness_score == f2.fitness_score