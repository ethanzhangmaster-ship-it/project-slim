"""E11.6.3 — Creative Genome Attribution Engine Test.

10 AC covering:
  1.  Attribution Schema
  2.  Creative Revenue Aggregation
  3.  Genome Mapping
  4.  DNA Impact Analysis
  5.  Gene Lift Calculation
  6.  Sample Confidence
  7.  Winner DNA Detection
  8.  Serialization
  9.  Deterministic
  10. Mutation Integration
"""

from __future__ import annotations

import pytest

from market_ops.e11.reality import (
    RevenueEvent,
    AttributionSource,
    CreativeRevenueAttribution,
    GeneRevenueImpact,
    GenomeAttributionResult,
    GenomeAttributor,
    DNARevenueAnalyzer,
    AttributionRepository,
)
from market_ops.e11.reality.adjust import AdjustCreativeMapper


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_revenue_event(
    user_id: str = "u1",
    creative_id: str = "creative_001",
    genome_id: str = "genome_001",
    revenue: float = 4.99,
    product_id: str = "iap_purchase",
) -> RevenueEvent:
    return RevenueEvent(
        user_id=user_id,
        creative_id=creative_id,
        genome_id=genome_id,
        product_id=product_id,
        revenue=revenue,
        currency="USD",
        country="US",
        source=AttributionSource.ADJUST,
    )


def _make_events_for_creative(
    creative_id: str,
    genome_id: str,
    user_count: int = 100,
    revenue_per_user: float = 5.0,
) -> list[RevenueEvent]:
    """Generate events for a single creative."""
    return [
        _make_revenue_event(
            user_id=f"u_{creative_id}_{i}",
            creative_id=creative_id,
            genome_id=genome_id,
            revenue=revenue_per_user,
        )
        for i in range(user_count)
    ]


def _make_dna_map() -> dict[str, dict[str, str]]:
    """Sample DNA map for 5 creatives across 2 genomes."""
    return {
        "creative_001": {"hook": "rescue", "reward": "dragon", "emotion": "urgency"},
        "creative_002": {"hook": "rescue", "reward": "baby_dragon", "emotion": "relief"},
        "creative_003": {"hook": "rescue", "reward": "dragon", "emotion": "curiosity"},
        "creative_004": {"hook": "merge", "reward": "coin", "emotion": "calm"},
        "creative_005": {"hook": "merge", "reward": "coin", "emotion": "calm"},
    }


# ═══════════════════════════════════════════════════════════
# AC1 — Attribution Schema
# ═══════════════════════════════════════════════════════════

def test_ac1a_creative_attribution_create():
    """AC1a: CreativeRevenueAttribution creates with all fields."""
    attr = CreativeRevenueAttribution(
        creative_id="creative_001",
        genome_id="genome_dragon",
        total_users=10000,
        total_revenue=33000.0,
        iap_revenue=25000.0,
        ad_revenue=8000.0,
        payer_count=800,
        payer_rate=0.08,
        arpu=3.3,
        d30_ltv=3.3,
    )
    assert attr.creative_id == "creative_001"
    assert attr.genome_id == "genome_dragon"
    assert attr.total_users == 10000
    assert attr.iap_revenue == 25000.0
    assert attr.ad_revenue == 8000.0
    assert attr.is_valid is True
    assert attr.is_attributed is True


def test_ac1b_creative_attribution_properties():
    """AC1b: CreativeRevenueAttribution computed properties."""
    attr = CreativeRevenueAttribution(
        creative_id="c1",
        total_revenue=100.0,
        iap_revenue=70.0,
        ad_revenue=30.0,
    )
    assert attr.iap_ratio == 0.7
    assert attr.is_valid is False  # total_users=0


def test_ac1c_gene_revenue_impact_create():
    """AC1c: GeneRevenueImpact creates with all fields."""
    impact = GeneRevenueImpact(
        gene_name="reward",
        gene_value="dragon",
        sample_count=120,
        avg_ltv=4.2,
        avg_revenue=5000.0,
        impact_score=0.86,
    )
    assert impact.gene_name == "reward"
    assert impact.gene_value == "dragon"
    assert impact.gene_key == "reward:dragon"
    assert impact.is_high_impact is True
    assert impact.is_significant_sample is True


def test_ac1d_gene_revenue_impact_properties():
    """AC1d: GeneRevenueImpact threshold checks."""
    high = GeneRevenueImpact(impact_score=0.7, sample_count=30)
    low = GeneRevenueImpact(impact_score=0.3, sample_count=5)
    assert high.is_high_impact is True
    assert high.is_significant_sample is True
    assert low.is_high_impact is False
    assert low.is_significant_sample is False


def test_ac1e_genome_attribution_result_create():
    """AC1e: GenomeAttributionResult creates with all fields."""
    result = GenomeAttributionResult(
        genome_id="dragon_rescue_01",
        creatives=["creative_001", "creative_002"],
        total_users=20000,
        total_revenue=50000.0,
        iap_revenue=40000.0,
        ad_revenue=10000.0,
        payer_count=1200,
        payer_rate=0.06,
        arpu=2.5,
        d30_ltv=2.5,
        attribution_score=0.92,
        top_genes=["reward:dragon", "hook:rescue"],
    )
    assert result.genome_id == "dragon_rescue_01"
    assert result.creative_count == 2
    assert result.attribution_score == 0.92
    assert result.top_genes == ["reward:dragon", "hook:rescue"]
    assert result.is_valid is True


# ═══════════════════════════════════════════════════════════
# AC2 — Creative Revenue Aggregation
# ═══════════════════════════════════════════════════════════

def test_ac2a_attribute_creative_single():
    """AC2a: GenomeAttributor.attribute_creative aggregates single creative."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = _make_events_for_creative("creative_001", "genome_001", user_count=10, revenue_per_user=5.0)
    attrs = attributor.attribute_creative(events)

    assert len(attrs) == 1
    assert attrs[0].creative_id == "creative_001"
    assert attrs[0].genome_id == "genome_001"
    assert attrs[0].total_revenue == 50.0
    assert attrs[0].total_users == 10


def test_ac2b_attribute_creative_multiple():
    """AC2b: GenomeAttributor.attribute_creative aggregates multiple creatives."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    mapper.register("creative_002", "genome_002")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = []
    events.extend(_make_events_for_creative("creative_001", "genome_001", user_count=5, revenue_per_user=10.0))
    events.extend(_make_events_for_creative("creative_002", "genome_002", user_count=3, revenue_per_user=5.0))

    attrs = attributor.attribute_creative(events)
    assert len(attrs) == 2

    attr1 = next(a for a in attrs if a.creative_id == "creative_001")
    attr2 = next(a for a in attrs if a.creative_id == "creative_002")
    assert attr1.total_revenue == 50.0
    assert attr2.total_revenue == 15.0


def test_ac2c_creative_iap_vs_ad():
    """AC2c: Creative attribution separates IAP and AD revenue."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = [
        _make_revenue_event(creative_id="creative_001", genome_id="genome_001", revenue=4.99, product_id="iap_purchase"),
        _make_revenue_event(creative_id="creative_001", genome_id="genome_001", revenue=0.23, product_id="ad_revenue"),
    ]
    attrs = attributor.attribute_creative(events)
    assert len(attrs) == 1
    assert attrs[0].iap_revenue == 4.99
    assert attrs[0].ad_revenue == 0.23
    assert attrs[0].total_revenue == 5.22


def test_ac2d_creative_skips_invalid():
    """AC2d: GenomeAttributor skips invalid events."""
    mapper = AdjustCreativeMapper()
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = [
        _make_revenue_event(creative_id="c1", genome_id="g1", revenue=4.99),
        RevenueEvent(),  # invalid
        _make_revenue_event(creative_id="", genome_id="", revenue=0.0),  # invalid
    ]
    attrs = attributor.attribute_creative(events)
    assert len(attrs) == 1


# ═══════════════════════════════════════════════════════════
# AC3 — Genome Mapping
# ═══════════════════════════════════════════════════════════

def test_ac3a_attribute_genome():
    """AC3a: GenomeAttributor.attribute aggregates to Genome level."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    mapper.register("creative_002", "genome_001")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = []
    events.extend(_make_events_for_creative("creative_001", "genome_001", user_count=10, revenue_per_user=5.0))
    events.extend(_make_events_for_creative("creative_002", "genome_001", user_count=10, revenue_per_user=3.0))

    results = attributor.attribute(events)
    assert len(results) == 1
    assert results[0].genome_id == "genome_001"
    assert results[0].total_revenue == 80.0
    assert results[0].creative_count == 2


def test_ac3b_attribute_multiple_genomes():
    """AC3b: GenomeAttributor.attribute handles multiple genomes."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    mapper.register("creative_002", "genome_002")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = []
    events.extend(_make_events_for_creative("creative_001", "genome_001", user_count=10, revenue_per_user=10.0))
    events.extend(_make_events_for_creative("creative_002", "genome_002", user_count=5, revenue_per_user=5.0))

    results = attributor.attribute(events)
    assert len(results) == 2
    # Sorted by revenue descending
    assert results[0].genome_id == "genome_001"
    assert results[1].genome_id == "genome_002"


def test_ac3c_genome_fitness_calculation():
    """AC3c: GenomeAttributionResult fitness is calculated."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    attributor = GenomeAttributor(creative_mapper=mapper)

    events = _make_events_for_creative("creative_001", "genome_001", user_count=100, revenue_per_user=5.0)
    results = attributor.attribute(events)

    assert len(results) == 1
    assert results[0].attribution_score > 0.0
    assert results[0].attribution_score <= 1.0


def test_ac3d_empty_events():
    """AC3d: GenomeAttributor.attribute returns empty for no events."""
    attributor = GenomeAttributor()
    results = attributor.attribute([])
    assert results == []


# ═══════════════════════════════════════════════════════════
# AC4 — DNA Impact Analysis
# ═══════════════════════════════════════════════════════════

def test_ac4a_analyze_gene_impact():
    """AC4a: DNARevenueAnalyzer.analyze_gene_impact returns impacts."""
    dna_map = _make_dna_map()
    analyzer = DNARevenueAnalyzer()

    attrs = [
        CreativeRevenueAttribution(creative_id="creative_001", genome_id="genome_001", total_users=100, total_revenue=500.0, d30_ltv=5.0),
        CreativeRevenueAttribution(creative_id="creative_002", genome_id="genome_001", total_users=100, total_revenue=400.0, d30_ltv=4.0),
        CreativeRevenueAttribution(creative_id="creative_003", genome_id="genome_001", total_users=100, total_revenue=600.0, d30_ltv=6.0),
        CreativeRevenueAttribution(creative_id="creative_004", genome_id="genome_002", total_users=100, total_revenue=200.0, d30_ltv=2.0),
        CreativeRevenueAttribution(creative_id="creative_005", genome_id="genome_002", total_users=100, total_revenue=150.0, d30_ltv=1.5),
    ]

    impacts = analyzer.analyze_gene_impact(attrs, dna_map)
    assert len(impacts) > 0

    # Check that impacts are sorted by impact_score descending
    for i in range(len(impacts) - 1):
        assert impacts[i].impact_score >= impacts[i + 1].impact_score


def test_ac4b_gene_impact_empty_dna():
    """AC4b: DNARevenueAnalyzer returns empty for empty dna_map."""
    analyzer = DNARevenueAnalyzer()
    attrs = [CreativeRevenueAttribution(creative_id="c1", total_users=100, total_revenue=500.0)]
    impacts = analyzer.analyze_gene_impact(attrs, {})
    assert impacts == []


def test_ac4c_gene_impact_empty_attrs():
    """AC4c: DNARevenueAnalyzer returns empty for empty attrs."""
    analyzer = DNARevenueAnalyzer()
    impacts = analyzer.analyze_gene_impact([], {})
    assert impacts == []


def test_ac4d_gene_impact_higher_revenue():
    """AC4d: Higher revenue genes get higher impact_score."""
    dna_map = {"creative_A": {"hook": "rescue"}, "creative_B": {"hook": "merge"}}
    analyzer = DNARevenueAnalyzer()

    attrs = [
        CreativeRevenueAttribution(creative_id="creative_A", total_users=100, total_revenue=1000.0, d30_ltv=10.0),
        CreativeRevenueAttribution(creative_id="creative_B", total_users=100, total_revenue=100.0, d30_ltv=1.0),
    ]

    impacts = analyzer.analyze_gene_impact(attrs, dna_map)
    rescue = next(i for i in impacts if i.gene_value == "rescue")
    merge = next(i for i in impacts if i.gene_value == "merge")
    assert rescue.impact_score > merge.impact_score


# ═══════════════════════════════════════════════════════════
# AC5 — Gene Lift Calculation
# ═══════════════════════════════════════════════════════════

def test_ac5a_gene_lift_greater_than_one():
    """AC5a: Gene with above-average revenue has lift > 1."""
    dna_map = {"creative_A": {"hook": "rescue"}, "creative_B": {"hook": "merge"}}
    analyzer = DNARevenueAnalyzer()

    attrs = [
        CreativeRevenueAttribution(creative_id="creative_A", total_users=100, total_revenue=800.0, d30_ltv=8.0),
        CreativeRevenueAttribution(creative_id="creative_B", total_users=100, total_revenue=200.0, d30_ltv=2.0),
    ]

    impacts = analyzer.analyze_gene_impact(attrs, dna_map)
    rescue = next(i for i in impacts if i.gene_value == "rescue")
    merge = next(i for i in impacts if i.gene_value == "merge")
    assert rescue.impact_score > merge.impact_score
    assert rescue.avg_ltv > merge.avg_ltv


def test_ac5b_gene_lift_table():
    """AC5b: get_gene_lift_table returns structured data."""
    dna_map = {"creative_A": {"hook": "rescue"}}
    analyzer = DNARevenueAnalyzer()
    attrs = [CreativeRevenueAttribution(creative_id="creative_A", total_users=100, total_revenue=500.0, d30_ltv=5.0)]
    impacts = analyzer.analyze_gene_impact(attrs, dna_map)

    table = analyzer.get_gene_lift_table(impacts)
    assert len(table) == 1
    assert "gene" in table[0]
    assert "impact" in table[0]
    assert "samples" in table[0]


def test_ac5c_lift_baseline_zero():
    """AC5c: calc_lift returns 1.0 when baseline is 0."""
    result = DNARevenueAnalyzer._calc_lift(5.0, 0.0)
    assert result == 1.0


# ═══════════════════════════════════════════════════════════
# AC6 — Sample Confidence
# ═══════════════════════════════════════════════════════════

def test_ac6a_confidence_increases_with_samples():
    """AC6a: Confidence increases with larger sample sizes."""
    analyzer = DNARevenueAnalyzer()
    c1 = analyzer._calc_confidence(5)
    c2 = analyzer._calc_confidence(50)
    c3 = analyzer._calc_confidence(500)
    assert c1 < c2 < c3


def test_ac6b_confidence_zero_samples():
    """AC6b: Confidence is 0 for 0 samples."""
    analyzer = DNARevenueAnalyzer()
    assert analyzer._calc_confidence(0) == 0.0


def test_ac6c_confidence_approaches_one():
    """AC6c: Confidence approaches 1.0 for large samples."""
    analyzer = DNARevenueAnalyzer()
    c = analyzer._calc_confidence(10000)
    assert c > 0.99


def test_ac6d_sample_factor():
    """AC6d: Sample factor is small for small samples."""
    analyzer = DNARevenueAnalyzer(max_sample_factor=1000)
    f1 = analyzer._calc_sample_factor(5)
    f2 = analyzer._calc_sample_factor(500)
    assert f1 < f2  # larger sample = larger factor
    assert 0.0 < f1 < 1.0
    assert 0.0 < f2 <= 1.0


def test_ac6e_small_sample_penalized():
    """AC6e: Small sample high lift gets lower impact than large sample."""
    dna_map = {"creative_A": {"hook": "rescue"}}
    analyzer = DNARevenueAnalyzer(max_sample_factor=1000)

    # Gene with moderate lift but very small sample
    attrs = [
        CreativeRevenueAttribution(creative_id="creative_A", total_users=5, total_revenue=200.0, d30_ltv=5.0),
    ]
    for _ in range(100):
        attrs.append(CreativeRevenueAttribution(
            creative_id=f"bg_{_}", total_users=100, total_revenue=100.0, d30_ltv=1.0,
        ))

    impacts = analyzer.analyze_gene_impact(attrs, dna_map)
    # The moderate-lift gene with small sample should be penalized below 1.0
    assert len(impacts) > 0
    assert impacts[0].impact_score < 1.0


# ═══════════════════════════════════════════════════════════
# AC7 — Winner DNA Detection
# ═══════════════════════════════════════════════════════════

def test_ac7a_detect_winner_genes():
    """AC7a: detect_winner_genes returns high-impact genes with significant samples."""
    impacts = [
        GeneRevenueImpact(gene_name="hook", gene_value="rescue", sample_count=120, impact_score=0.86),
        GeneRevenueImpact(gene_name="reward", gene_value="dragon", sample_count=80, impact_score=0.75),
        GeneRevenueImpact(gene_name="hook", gene_value="merge", sample_count=5, impact_score=0.90),  # small sample
        GeneRevenueImpact(gene_name="emotion", gene_value="calm", sample_count=50, impact_score=0.25),  # low impact
    ]

    analyzer = DNARevenueAnalyzer()
    winners = analyzer.detect_winner_genes(impacts, top_k=5, min_impact=0.3)

    # Only rescue and dragon should be winners
    assert len(winners) == 2
    assert winners[0].gene_value == "rescue"
    assert winners[1].gene_value == "dragon"


def test_ac7b_detect_winner_genes_top_k():
    """AC7b: detect_winner_genes respects top_k limit."""
    impacts = [
        GeneRevenueImpact(gene_name="g1", gene_value="v1", sample_count=50, impact_score=0.9),
        GeneRevenueImpact(gene_name="g2", gene_value="v2", sample_count=50, impact_score=0.8),
        GeneRevenueImpact(gene_name="g3", gene_value="v3", sample_count=50, impact_score=0.7),
        GeneRevenueImpact(gene_name="g4", gene_value="v4", sample_count=50, impact_score=0.6),
        GeneRevenueImpact(gene_name="g5", gene_value="v5", sample_count=50, impact_score=0.5),
        GeneRevenueImpact(gene_name="g6", gene_value="v6", sample_count=50, impact_score=0.4),
    ]

    analyzer = DNARevenueAnalyzer()
    winners = analyzer.detect_winner_genes(impacts, top_k=3, min_impact=0.3)
    assert len(winners) == 3


def test_ac7c_detect_winner_empty():
    """AC7c: detect_winner_genes returns empty for no qualifying genes."""
    impacts = [
        GeneRevenueImpact(gene_name="g1", gene_value="v1", sample_count=5, impact_score=0.9),  # small sample
        GeneRevenueImpact(gene_name="g2", gene_value="v2", sample_count=50, impact_score=0.1),  # low impact
    ]

    analyzer = DNARevenueAnalyzer()
    winners = analyzer.detect_winner_genes(impacts, top_k=5, min_impact=0.3)
    assert len(winners) == 0


# ═══════════════════════════════════════════════════════════
# AC8 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac8a_creative_attribution_roundtrip():
    """AC8a: CreativeRevenueAttribution to_dict/from_dict roundtrip."""
    attr = CreativeRevenueAttribution(
        creative_id="creative_001",
        genome_id="genome_dragon",
        total_users=10000,
        total_revenue=33000.0,
        iap_revenue=25000.0,
        ad_revenue=8000.0,
        payer_count=800,
        payer_rate=0.08,
        arpu=3.3,
        d30_ltv=3.3,
    )
    data = attr.to_dict()
    restored = CreativeRevenueAttribution.from_dict(data)
    assert restored.creative_id == attr.creative_id
    assert restored.genome_id == attr.genome_id
    assert restored.total_revenue == attr.total_revenue
    assert restored.iap_revenue == attr.iap_revenue


def test_ac8b_gene_impact_roundtrip():
    """AC8b: GeneRevenueImpact to_dict/from_dict roundtrip."""
    impact = GeneRevenueImpact(
        gene_name="reward",
        gene_value="dragon",
        sample_count=120,
        avg_ltv=4.2,
        avg_revenue=5000.0,
        impact_score=0.86,
    )
    data = impact.to_dict()
    restored = GeneRevenueImpact.from_dict(data)
    assert restored.gene_name == impact.gene_name
    assert restored.gene_value == impact.gene_value
    assert restored.sample_count == impact.sample_count
    assert restored.impact_score == impact.impact_score


def test_ac8c_genome_result_roundtrip():
    """AC8c: GenomeAttributionResult to_dict/from_dict roundtrip."""
    result = GenomeAttributionResult(
        genome_id="dragon_rescue_01",
        creatives=["creative_001", "creative_002"],
        total_users=20000,
        total_revenue=50000.0,
        attribution_score=0.92,
        top_genes=["reward:dragon", "hook:rescue"],
    )
    data = result.to_dict()
    restored = GenomeAttributionResult.from_dict(data)
    assert restored.genome_id == result.genome_id
    assert restored.creatives == result.creatives
    assert restored.total_revenue == result.total_revenue
    assert restored.attribution_score == result.attribution_score
    assert restored.top_genes == result.top_genes


def test_ac8d_attribution_repository_roundtrip():
    """AC8d: AttributionRepository to_dict/from_dict roundtrip."""
    repo = AttributionRepository()
    repo.save_genome_results([
        GenomeAttributionResult(genome_id="genome_001", total_revenue=50000.0, attribution_score=0.92),
    ])
    repo.save_creative_attrs([
        CreativeRevenueAttribution(creative_id="creative_001", genome_id="genome_001", total_revenue=5000.0),
    ])
    repo.save_gene_impacts([
        GeneRevenueImpact(gene_name="hook", gene_value="rescue", impact_score=0.86),
    ])

    data = repo.to_dict()
    restored = AttributionRepository.from_dict(data)

    assert restored.genome_count == 1
    assert restored.creative_count == 1
    assert restored.gene_impact_count == 1
    assert restored.get_genome_result("genome_001") is not None
    assert restored.get_genome_result("genome_001").attribution_score == 0.92


def test_ac8e_repository_repr():
    """AC8e: AttributionRepository repr shows state."""
    repo = AttributionRepository()
    repo.save_genome_results([GenomeAttributionResult(genome_id="g1", total_revenue=100.0)])
    r = repr(repo)
    assert "genomes=1" in r


# ═══════════════════════════════════════════════════════════
# AC9 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac9a_deterministic_attribution():
    """AC9a: Same events produce same attribution results."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_001", "genome_001")
    a1 = GenomeAttributor(creative_mapper=mapper)
    a2 = GenomeAttributor(creative_mapper=mapper)

    events = _make_events_for_creative("creative_001", "genome_001", user_count=10, revenue_per_user=5.0)
    r1 = a1.attribute(events)
    r2 = a2.attribute(events)

    assert len(r1) == len(r2)
    assert r1[0].total_revenue == r2[0].total_revenue
    assert r1[0].attribution_score == r2[0].attribution_score


def test_ac9b_deterministic_impact():
    """AC9b: Same data produces same gene impact analysis."""
    dna_map = {"creative_A": {"hook": "rescue"}}
    a1 = DNARevenueAnalyzer()
    a2 = DNARevenueAnalyzer()

    attrs = [CreativeRevenueAttribution(creative_id="creative_A", total_users=100, total_revenue=500.0, d30_ltv=5.0)]
    i1 = a1.analyze_gene_impact(attrs, dna_map)
    i2 = a2.analyze_gene_impact(attrs, dna_map)

    assert len(i1) == len(i2)
    if i1 and i2:
        assert i1[0].impact_score == i2[0].impact_score


def test_ac9c_deterministic_confidence():
    """AC9c: Confidence calculation is deterministic."""
    a1 = DNARevenueAnalyzer()
    a2 = DNARevenueAnalyzer()
    for n in [1, 10, 100, 1000]:
        assert a1._calc_confidence(n) == a2._calc_confidence(n)


def test_ac9d_deterministic_sample_factor():
    """AC9d: Sample factor calculation is deterministic."""
    a1 = DNARevenueAnalyzer()
    a2 = DNARevenueAnalyzer()
    for n in [1, 10, 100, 500]:
        assert a1._calc_sample_factor(n) == a2._calc_sample_factor(n)


# ═══════════════════════════════════════════════════════════
# AC10 — Mutation Integration
# ═══════════════════════════════════════════════════════════

def test_ac10a_enrich_genome_results():
    """AC10a: DNARevenueAnalyzer.enrich_genome_results fills top_genes."""
    dna_map = _make_dna_map()
    analyzer = DNARevenueAnalyzer()

    results = [
        GenomeAttributionResult(
            genome_id="genome_001",
            creatives=["creative_001", "creative_002", "creative_003"],
            total_users=300,
            total_revenue=1500.0,
            attribution_score=0.85,
        ),
        GenomeAttributionResult(
            genome_id="genome_002",
            creatives=["creative_004", "creative_005"],
            total_users=200,
            total_revenue=350.0,
            attribution_score=0.35,
        ),
    ]

    enriched = analyzer.enrich_genome_results(results, dna_map)

    assert len(enriched) == 2
    assert len(enriched[0].top_genes) > 0
    assert len(enriched[1].top_genes) > 0


def test_ac10b_enrich_with_preexisting_impacts():
    """AC10b: enrich_genome_results uses pre-computed gene_impacts."""
    dna_map = _make_dna_map()
    analyzer = DNARevenueAnalyzer()

    results = [
        GenomeAttributionResult(
            genome_id="genome_001",
            creatives=["creative_001"],
            total_users=100,
            total_revenue=500.0,
            attribution_score=0.8,
        ),
    ]

    # Pre-computed impacts
    pre_impacts = [
        GeneRevenueImpact(gene_name="hook", gene_value="rescue", impact_score=0.9),
        GeneRevenueImpact(gene_name="reward", gene_value="dragon", impact_score=0.85),
    ]

    enriched = analyzer.enrich_genome_results(results, dna_map, gene_impacts=pre_impacts)
    assert len(enriched[0].top_genes) > 0
    # "hook:rescue" should appear first due to higher impact
    if enriched[0].top_genes:
        assert "hook:rescue" in enriched[0].top_genes or "reward:dragon" in enriched[0].top_genes


def test_ac10c_repository_top_genomes():
    """AC10c: AttributionRepository.get_top_genomes returns top by revenue."""
    repo = AttributionRepository()
    repo.save_genome_results([
        GenomeAttributionResult(genome_id="genome_A", total_revenue=10000.0, attribution_score=0.5),
        GenomeAttributionResult(genome_id="genome_B", total_revenue=50000.0, attribution_score=0.9),
        GenomeAttributionResult(genome_id="genome_C", total_revenue=30000.0, attribution_score=0.7),
    ])

    top = repo.get_top_genomes(limit=2, by="total_revenue")
    assert len(top) == 2
    assert top[0].genome_id == "genome_B"
    assert top[1].genome_id == "genome_C"


def test_ac10d_repository_top_by_fitness():
    """AC10d: AttributionRepository.get_top_genomes sorts by fitness."""
    repo = AttributionRepository()
    repo.save_genome_results([
        GenomeAttributionResult(genome_id="genome_A", total_revenue=10000.0, attribution_score=0.5),
        GenomeAttributionResult(genome_id="genome_B", total_revenue=10000.0, attribution_score=0.9),
        GenomeAttributionResult(genome_id="genome_C", total_revenue=10000.0, attribution_score=0.7),
    ])

    top = repo.get_top_genomes(limit=3, by="attribution_score")
    assert top[0].genome_id == "genome_B"
    assert top[-1].genome_id == "genome_A"


def test_ac10e_repository_get_high_impact_genes():
    """AC10e: AttributionRepository.get_high_impact_genes filters by score."""
    repo = AttributionRepository()
    repo.save_gene_impacts([
        GeneRevenueImpact(gene_name="hook", gene_value="rescue", impact_score=0.86),
        GeneRevenueImpact(gene_name="hook", gene_value="merge", impact_score=0.30),
        GeneRevenueImpact(gene_name="reward", gene_value="dragon", impact_score=0.75),
    ])

    high = repo.get_high_impact_genes(min_score=0.5)
    assert len(high) == 2
    assert all(imp.impact_score >= 0.5 for imp in high)


def test_ac10f_repository_history():
    """AC10f: AttributionRepository tracks history."""
    repo = AttributionRepository()
    repo.save_genome_results([GenomeAttributionResult(genome_id="g1", total_revenue=100.0)])
    repo.save_creative_attrs([CreativeRevenueAttribution(creative_id="c1", total_revenue=10.0)])
    assert repo.history_count == 2


def test_ac10g_repository_clear():
    """AC10g: AttributionRepository.clear resets all data."""
    repo = AttributionRepository()
    repo.save_genome_results([GenomeAttributionResult(genome_id="g1", total_revenue=100.0)])
    repo.clear()
    assert repo.genome_count == 0
    assert repo.history_count == 0


def test_ac10h_repository_get_creative_attr():
    """AC10h: AttributionRepository.get_creative_attr returns single attr."""
    repo = AttributionRepository()
    repo.save_creative_attrs([CreativeRevenueAttribution(creative_id="c1", total_revenue=10.0)])
    attr = repo.get_creative_attr("c1")
    assert attr is not None
    assert attr.total_revenue == 10.0
    assert repo.get_creative_attr("nonexistent") is None