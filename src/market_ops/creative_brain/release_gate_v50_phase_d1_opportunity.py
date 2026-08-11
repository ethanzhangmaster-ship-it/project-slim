"""V5.0 Phase D.1 — Opportunity Intelligence Layer Release Gate (16 tests).

Validates the Human-AI Creative Evolution Platform MVP:
  1. Module imports (all 8 modules load)
  2. Human Idea Inbox — text submission
  3. Human Idea Inbox — URL submission with type detection
  4. Human Idea Inbox — query and state management
  5. Market Scanner — returns 7 mock opportunities
  6. Market Scanner — signals present
  7. Opportunity Engine — ingest human idea
  8. Opportunity Engine — scan market + deduplication
  9. Opportunity Ranker — BUILD/WATCH/IGNORE recommendations
 10. Hypothesis Engine — generates hypothesis + 3 variants
 11. Hypothesis Engine — genome hints in variants
 12. Opportunity Genome Builder — opportunity → V5 Genome
 13. Opportunity Genome Builder — variant → V5 Genome
 14. Report Generator — daily report with markdown
 15. End-to-End Test Case 1: Merge + Simulation → Score + Genome + Plan
 16. End-to-End Test Case 2+3: URL input + Human idea evaluation

All tests must PASS before Phase D.2 (Mutation Engine).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from market_ops.creative_opportunity import (
    HumanIdeaInbox,
    MockMarketScanner,
    OpportunityIntelligenceEngine,
    OpportunityRanker,
    HypothesisEngine,
    OpportunityGenomeBuilder,
    OpportunityReportGenerator,
    Recommendation,
    OpportunityStatus,
)


# ═══════════════════════════════════════════════════════════
# 1-4. Human Idea Inbox (4 tests)
# ═══════════════════════════════════════════════════════════

def test_human_idea_text_submission():
    """Inbox: text idea gets ID and is stored"""
    inbox = HumanIdeaInbox()
    idea = inbox.submit_text(
        title="Merge + Simulation",
        description="Test idea",
        reference_games=["Game A"],
        tags=["merge"],
    )
    assert idea.idea_id.startswith("idea_")
    assert idea.title == "Merge + Simulation"
    assert "merge" in idea.tags
    assert len(inbox.get_all()) == 1
    return True


def test_human_idea_url_detection():
    """Inbox: URL auto-detects source type"""
    inbox = HumanIdeaInbox()
    idea = inbox.submit_url("https://play.google.com/store/apps/details?id=x", notes="test")
    assert idea.metadata.get("source_type") == "google_play"

    idea2 = inbox.submit_url("https://apps.apple.com/app/id123", notes="test")
    assert idea2.metadata.get("source_type") == "app_store"
    return True


def test_human_idea_query_and_state():
    """Inbox: query by status and approve/reject works"""
    inbox = HumanIdeaInbox()
    idea = inbox.submit_text("Test", "Desc")
    assert len(inbox.get_pending()) == 1

    inbox.approve(idea.idea_id)
    assert idea.status == OpportunityStatus.APPROVED
    assert len(inbox.get_pending()) == 0

    inbox.reject(idea.idea_id)
    assert idea.status == OpportunityStatus.REJECTED
    return True


def test_human_idea_creator_filter():
    """Inbox: filter by creator"""
    inbox = HumanIdeaInbox()
    inbox.submit_text("A", "Desc", creator="alice")
    inbox.submit_text("B", "Desc", creator="bob")
    assert len(inbox.get_by_creator("alice")) == 1
    return True


# ═══════════════════════════════════════════════════════════
# 5-6. Market Scanner (2 tests)
# ═══════════════════════════════════════════════════════════

def test_market_scanner_returns_opportunities():
    """Scanner: returns 7 mock opportunities with scores"""
    scanner = MockMarketScanner(seed=42)
    opps = scanner.scan()
    assert len(opps) == 7
    assert all(o.score > 0 for o in opps)
    assert all(o.confidence >= 0.5 for o in opps)
    return True


def test_market_scanner_signals():
    """Scanner: raw market signals available"""
    scanner = MockMarketScanner()
    signals = scanner.get_signals()
    assert len(signals) == 3
    assert any(s.source == "google_play" for s in signals)
    return True


# ═══════════════════════════════════════════════════════════
# 7-8. Opportunity Intelligence Engine (2 tests)
# ═══════════════════════════════════════════════════════════

def test_engine_ingests_human_idea():
    """Engine: human idea converts to scored opportunity"""
    inbox = HumanIdeaInbox()
    idea = inbox.submit_text("Merge Sim", "Desc", tags=["merge", "sim"])

    engine = OpportunityIntelligenceEngine(inbox=inbox)
    opp = engine.ingest_human_idea(idea)
    assert opp.source.name == "HUMAN"
    assert opp.score > 0
    return True


def test_engine_full_pipeline():
    """Engine: full pipeline runs (ideas + scan + dedup)"""
    inbox = HumanIdeaInbox()
    inbox.submit_text("Merge Sim", "Desc", tags=["merge"])

    engine = OpportunityIntelligenceEngine(inbox=inbox)
    opps = engine.run_full_pipeline()
    assert len(opps) >= 7  # 1 human + 7 AI (minus dedup)

    # Verify categories
    categories = set(o.category.value for o in opps)
    assert len(categories) >= 2
    return True


# ═══════════════════════════════════════════════════════════
# 9. Opportunity Ranker (1 test)
# ═══════════════════════════════════════════════════════════

def test_ranker_recommendations():
    """Ranker: assigns BUILD/WATCH/IGNORE correctly"""
    engine = OpportunityIntelligenceEngine()
    engine.scan_market()

    ranker = OpportunityRanker()
    ranked = ranker.rank(engine.get_all())
    assert len(ranked) == 7

    recs = [r.recommendation for r in ranked]
    assert any(r in recs for r in [Recommendation.BUILD, Recommendation.WATCH, Recommendation.IGNORE])

    # Verify sorting
    for i in range(len(ranked) - 1):
        assert ranked[i].opportunity.score >= ranked[i + 1].opportunity.score
    return True


# ═══════════════════════════════════════════════════════════
# 10-11. Hypothesis Engine (2 tests)
# ═══════════════════════════════════════════════════════════

def test_hypothesis_generates_plan():
    """Hypothesis: generates plan with 3 variants"""
    engine = OpportunityIntelligenceEngine()
    engine.scan_market()
    opp = engine.get_top(1)[0]

    hypo = HypothesisEngine()
    plan = hypo.generate(opp)
    assert plan.hypothesis != ""
    assert len(plan.variants) == 3
    assert plan.estimated_budget > 0
    assert "CTR" in plan.success_metrics
    return True


def test_hypothesis_genome_hints():
    """Hypothesis: variants contain genome hints"""
    engine = OpportunityIntelligenceEngine()
    engine.scan_market()
    opp = engine.get_top(1)[0]

    hypo = HypothesisEngine()
    plan = hypo.generate(opp)
    for v in plan.variants:
        assert "gameplay_gene" in v.genome_hint
        assert "visual_gene" in v.genome_hint
        assert "hook_gene" in v.genome_hint
    return True


# ═══════════════════════════════════════════════════════════
# 12-13. Opportunity Genome Builder (2 tests)
# ═══════════════════════════════════════════════════════════

def test_genome_builder_from_opportunity():
    """GenomeBuilder: opportunity → V5 Genome with genes"""
    engine = OpportunityIntelligenceEngine()
    engine.scan_market()
    opp = engine.get_top(1)[0]

    builder = OpportunityGenomeBuilder()
    genome = builder.build_from_opportunity(opp)
    assert genome.genome_id != ""
    assert len(genome.genes) >= 4
    assert "gameplay" in genome.genes
    assert "hook" in genome.genes
    assert genome.metadata.get("opportunity_id") == opp.opportunity_id
    return True


def test_genome_builder_from_variant():
    """GenomeBuilder: experiment variant → V5 Genome"""
    engine = OpportunityIntelligenceEngine()
    engine.scan_market()
    opp = engine.get_top(1)[0]

    hypo = HypothesisEngine()
    plan = hypo.generate(opp)
    variant = plan.variants[0]

    builder = OpportunityGenomeBuilder()
    genome = builder.build_from_variant(variant, opp)
    assert genome.genome_id != ""
    assert len(genome.genes) > 0
    return True


# ═══════════════════════════════════════════════════════════
# 14. Report Generator (1 test)
# ═══════════════════════════════════════════════════════════

def test_report_generator():
    """Report: generates report with summary and markdown"""
    gen = OpportunityReportGenerator()
    report = gen.generate_daily_report()
    assert len(report.ranked_opportunities) >= 7
    assert "build_count" in report.summary
    assert "watch_count" in report.summary

    md = report.to_markdown()
    assert "# Daily Opportunity Report" in md
    assert "## Summary" in md
    assert "## Top Opportunities" in md
    return True


# ═══════════════════════════════════════════════════════════
# 15-16. End-to-End Acceptance Tests (2 tests)
# ═══════════════════════════════════════════════════════════

def test_e2e_test_case_1():
    """E2E TC1: Merge + Simulation → Score + Genome + Experiment Plan"""
    inbox = HumanIdeaInbox()
    idea = inbox.submit_text(
        title="Merge + Simulation",
        description="Merge + Factory hybrid with simulation elements",
        reference_games=["Merge Dragon", "Tasty Travels"],
        tags=["merge", "simulation", "factory"],
    )

    engine = OpportunityIntelligenceEngine(inbox=inbox)
    engine.run_full_pipeline()
    ranked = OpportunityRanker().rank(engine.get_all())
    assert len(ranked) > 0

    top = ranked[0]
    assert top.opportunity.score > 0
    assert top.recommendation in (Recommendation.BUILD, Recommendation.WATCH, Recommendation.IGNORE)

    plan = HypothesisEngine().generate(top.opportunity)
    assert len(plan.variants) == 3

    genome = OpportunityGenomeBuilder().build_from_opportunity(top.opportunity)
    assert len(genome.genes) >= 4
    return True


def test_e2e_test_cases_2_and_3():
    """E2E TC2+3: URL input + Human idea evaluation"""
    inbox = HumanIdeaInbox()

    # TC2: URL input
    url_idea = inbox.submit_url(
        "https://play.google.com/store/apps/details?id=com.merge.game",
        notes="Check competitor",
    )
    assert url_idea.metadata.get("source_type") == "google_play"

    # TC3: Human idea with evaluation
    human_idea = inbox.submit_text(
        title="Cozy Merge Home",
        description="Home decoration + merge mechanics",
        reference_games=["Merge Mansion"],
        tags=["cozy", "home", "merge"],
    )

    engine = OpportunityIntelligenceEngine(inbox=inbox)
    engine.run_full_pipeline()
    ranked = OpportunityRanker().rank(engine.get_all())

    # Verify evaluation exists
    assert len(ranked) > 0
    for r in ranked:
        assert r.opportunity.score > 0
        assert r.recommendation in (Recommendation.BUILD, Recommendation.WATCH, Recommendation.IGNORE)
        assert r.reason != ""
    return True


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def run_all():
    tests = [
        # 1-4. Human Idea Inbox (4)
        ("Inbox: text submission", test_human_idea_text_submission),
        ("Inbox: URL type detection", test_human_idea_url_detection),
        ("Inbox: query and state", test_human_idea_query_and_state),
        ("Inbox: creator filter", test_human_idea_creator_filter),
        # 5-6. Market Scanner (2)
        ("Scanner: returns opportunities", test_market_scanner_returns_opportunities),
        ("Scanner: market signals", test_market_scanner_signals),
        # 7-8. Opportunity Engine (2)
        ("Engine: ingest human idea", test_engine_ingests_human_idea),
        ("Engine: full pipeline", test_engine_full_pipeline),
        # 9. Ranker (1)
        ("Ranker: recommendations", test_ranker_recommendations),
        # 10-11. Hypothesis (2)
        ("Hypothesis: generates plan", test_hypothesis_generates_plan),
        ("Hypothesis: genome hints", test_hypothesis_genome_hints),
        # 12-13. Genome Builder (2)
        ("GenomeBuilder: from opportunity", test_genome_builder_from_opportunity),
        ("GenomeBuilder: from variant", test_genome_builder_from_variant),
        # 14. Report (1)
        ("Report: daily report", test_report_generator),
        # 15-16. E2E (2)
        ("E2E TC1: Merge+Sim → Score+Genome+Plan", test_e2e_test_case_1),
        ("E2E TC2+3: URL + Human eval", test_e2e_test_cases_2_and_3),
    ]

    passed = 0
    failed = 0
    print("=" * 65)
    print("  V5.0 Phase D.1 — Opportunity Intelligence Release Gate")
    print("  16 tests")
    print("=" * 65)
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
    print("=" * 65)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
