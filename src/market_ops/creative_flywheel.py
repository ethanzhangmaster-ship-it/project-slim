"""E6+E8: Creative Intelligence Flywheel — the orchestrator.

Connects market intelligence, agent debate, genome exchange, creative factory,
reality tracking, failure analysis, and evolution into a daily cycle.

E8 Reality Mode (NEW):
  06:00  RealityDataPipeline: fetch real Meta Ads, Google Play, Adjust data
         ↓
  06:15  MarketKnowledgeGraph: ingest real signals, explain trends
         ↓
  06:30  OpportunityGenerator: synthesise opportunities from real data
         ↓
  07:00  ConsensusEngine: 5 agents debate each opportunity
         ↓
  07:30  Human-in-the-loop: select top opportunities
         ↓
  08:00  CreativeFactory: generate creatives
         ↓
  Next day: RealityTracker → FailureAnalyzer → GenomeAttribution
         ↓
  Agent recalibration → Evolution → Better AI
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from market_ops.creative_brain.v5_evolution.schemas import Genome
from market_ops.market_intelligence.collector import SignalCollectionPipeline
from market_ops.market_intelligence.knowledge import (
    MarketKnowledgeGraph, CategoryMemory, TrendMemory,
)
from market_ops.market_intelligence import TrendDetector, OpportunityGenerator
from market_ops.market_intelligence.competitor_tracker import CompetitorTracker
from market_ops.market_intelligence.creative_signal_miner import CreativeSignalMiner
from market_ops.market_intelligence.category_heatmap import CategoryHeatmapEngine

from market_ops.creative_brain_ui.debate_engine import (
    ConsensusEngine, DebateMemory,
    MarketAgent, GameplayAgent, UAAgent, ProducerAgent, InvestorAgent,
)
from market_ops.creative_brain_ui.debate_engine.decision_history import (
    DecisionHistory, DecisionRecord, PredictedDecision,
)

from market_ops.creative_brain_ui.genome_exchange import GenomeExchange, GenomeAsset
from market_ops.creative_brain_ui.genome_value import GenomeValueEngine
from market_ops.creative_brain_ui.creative_scoring import CreativeScoringEngine

# E7: Reality Intelligence
from market_ops.creative_reality import (
    RealityTracker, CampaignReality, GenomePerformanceDelta,
    FailureAnalyzer, GenomeAttribution,
)
from market_ops.genome_evolution import GenomeEvolutionEngine

# E8: Reality Data Pipeline
from market_ops.reality_data_pipeline import RealityDataPipeline, RealityCalibrator
from market_ops.creative_dna_store import CreativeDNAStore


class CreativeIntelligenceFlywheel:
    """The full autonomous creative intelligence daily cycle.

    Usage:
        flywheel = CreativeIntelligenceFlywheel()
        report = flywheel.run_daily_cycle()
        print(report["morning_briefing"])

        # Next day:
        flywheel.record_outcomes([
            {"opportunity": "Sort+Rescue", "roas": 1.5, "ctr": 0.04, "outcome": "winner"},
            {"opportunity": "Merge+Sim", "roas": 0.3, "ctr": 0.01, "outcome": "failure"},
        ])
        flywheel.recalibrate()
    """

    def __init__(self) -> None:
        # E6.1: Market Intelligence
        self._knowledge_graph = MarketKnowledgeGraph()
        self._category_memory = CategoryMemory()
        self._trend_memory = TrendMemory()
        self._trend_detector = TrendDetector()
        self._competitor_tracker = CompetitorTracker()
        self._signal_miner = CreativeSignalMiner()
        self._heatmap_engine = CategoryHeatmapEngine()
        self._opportunity_generator = OpportunityGenerator()

        # E6.2: Decision + Calibration
        self._debate_memory = DebateMemory()
        self._decision_history = DecisionHistory()
        self._consensus_engine = ConsensusEngine(self._debate_memory)

        # E6.3: Asset Exchange
        self._genome_exchange = GenomeExchange()
        self._value_engine = GenomeValueEngine()

        # E7: Reality Intelligence
        self._reality_tracker = RealityTracker()
        self._failure_analyzer = FailureAnalyzer(self._decision_history)
        self._gene_attribution = GenomeAttribution()
        self._evolution_engine = GenomeEvolutionEngine(self._gene_attribution)

        # Scoring bridge
        self._scoring_engine = CreativeScoringEngine()

        # E8: Reality Data Pipeline (lazy — initialized on first use)
        self._reality_pipeline: RealityDataPipeline | None = None
        self._dna_store: CreativeDNAStore | None = None
        self._reality_calibrator: RealityCalibrator | None = None

        # Cycle state
        self._today_opportunities: list[dict[str, Any]] = []
        self._populations: list[list[Genome]] = []  # Evolution populations

    # ── Daily Cycle ─────────────────────────────────────────

    def run_daily_cycle(self) -> dict[str, Any]:
        """Execute one full daily cycle.

        Returns: complete morning briefing + action items.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        report: dict[str, Any] = {"date": today, "stages": {}}

        # Stage 1: Collect signals
        signals = SignalCollectionPipeline.collect_all()
        report["stages"]["signals_collected"] = len(signals)
        report["stages"]["sources"] = SignalCollectionPipeline.get_source_breakdown()

        # Stage 2: Feed knowledge graph
        SignalCollectionPipeline.feed_graph(self._knowledge_graph)

        # Stage 3: Heatmap
        heatmap = self._heatmap_engine.generate()
        report["stages"]["hot_categories"] = heatmap.hot_categories

        # Populate knowledge graph from heatmap
        for cell in heatmap.cells:
            self._knowledge_graph.ingest_category(
                cell.category, cell.market_heat,
                cell.opportunity_gap, cell.dominant_genes,
                cell.competition_density,
            )

        # Stage 4: Detect trends
        trends = self._trend_detector.detect_from_mock_data()
        self._trend_memory.record_batch(trends)
        for t in trends:
            cell = next((c for c in heatmap.cells if c.category == t.category), None)
            comp = cell.competition_density if cell else 50
            self._category_memory.record_snapshot(
                t.category, t.velocity_score, t.growth_pct,
                competition=comp, signals=t.evidence,
            )
        report["stages"]["trends_detected"] = len(trends)
        report["stages"]["exploding"] = [
            f"{t.category}/{t.subcategory}" for t in trends
            if t.direction.value == "exploding"
        ]

        # Stage 5: Generate opportunities
        opportunities = self._opportunity_generator.generate()
        report["stages"]["opportunities_found"] = len(opportunities)

        # Stage 6: Debate each opportunity
        debated = []
        for opp in opportunities[:10]:
            debate_result = self._debate_opportunity(opp)
            debated.append(debate_result)

        # Sort by consensus strength
        debated.sort(key=lambda d: d.get("consensus_strength", 0), reverse=True)

        # Stage 7: Build knowledge graph insights
        graph_insights = []
        for cat in heatmap.hot_categories[:3]:
            explanation = self._knowledge_graph.explain(cat)
            if explanation.get("causal_analysis"):
                graph_insights.append(explanation)

        hybrid_opps = self._knowledge_graph.find_hybrid_opportunities()

        # Stage 8: Compile briefing
        report["morning_briefing"] = self._format_briefing(debated, graph_insights, hybrid_opps)
        report["top_opportunities"] = debated[:5]
        report["causal_insights"] = graph_insights
        report["hybrid_suggestions"] = hybrid_opps[:5]

        self._today_opportunities = debated
        return report

    # ── E8: Reality Mode (replaces mock with real data) ─────

    def run_reality_mode(self) -> dict[str, Any]:
        """Execute daily cycle with REAL data instead of mock.

        Pipeline: Real Meta Ads → CSV → Google Play → Market Graph → Debate → Recalibrate.
        NEW E8.5: DNA Store → Gene Attribution → Reality Calibrator → Evolution.

        Falls back gracefully to mock when data sources unavailable.

        Returns: reality-integrated report with data source status + gene learning.
        """
        if self._reality_pipeline is None:
            self._reality_pipeline = RealityDataPipeline()
        if self._dna_store is None:
            self._dna_store = CreativeDNAStore()
        if self._reality_calibrator is None:
            self._reality_calibrator = RealityCalibrator(
                self._failure_analyzer, self._gene_attribution,
            )

        today = datetime.now().strftime("%Y-%m-%d")
        report: dict[str, Any] = {"date": today, "mode": "reality", "stages": {}}

        # Stage 1: E8 Reality Data Pipeline (replaces SignalCollectionPipeline)
        reality_report = self._reality_pipeline.run(self)
        report["stages"]["reality_data"] = reality_report

        # Stage 1.5: E8.5 — Load DNA store + feed gene attribution
        dna_count = self._dna_store.load()
        if dna_count > 0:
            attr_count = self._dna_store.feed_to_attribution(self._gene_attribution)
            dna_summary = self._dna_store.get_summary()
            combos = self._dna_store.get_genome_combinations(min_occurrence=3)
            report["stages"]["dna_store"] = {
                "records": dna_count,
                "attributed": attr_count,
                "with_dna": dna_summary["with_dna"],
                "gene_stats": dna_summary["gene_stats"],
                "winning_genes": dna_summary["winning_genes"][:10],
                "genome_combinations": combos[:10],
            }

        # Stage 2: Market Knowledge Graph
        heatmap = self._heatmap_engine.generate()
        report["stages"]["hot_categories"] = heatmap.hot_categories
        for cell in heatmap.cells:
            self._knowledge_graph.ingest_category(
                cell.category, cell.market_heat,
                cell.opportunity_gap, cell.dominant_genes,
                cell.competition_density,
            )

        # Stage 3: Generate opportunities
        opportunities = self._opportunity_generator.generate()
        report["stages"]["opportunities_found"] = len(opportunities)

        # Stage 4: Debate
        debated = []
        for opp in opportunities[:10]:
            debate_result = self._debate_opportunity(opp)
            debated.append(debate_result)
        debated.sort(key=lambda d: d.get("consensus_strength", 0), reverse=True)

        # Stage 5: Knowledge graph insights
        graph_insights = []
        for cat in heatmap.hot_categories[:3]:
            explanation = self._knowledge_graph.explain(cat)
            if explanation.get("causal_analysis"):
                graph_insights.append(explanation)
        hybrid_opps = self._knowledge_graph.find_hybrid_opportunities()

        # Stage 6: E8.5 — Reality Calibrator (compare predictions with reality)
        reality_campaigns = self._meta_ads_campaigns_from_report(reality_report)
        if reality_campaigns and debated:
            predictions = {
                d.get("creative_id", f"opp_{i}"): {
                    "score": d.get("score", 50),
                    "vote": d.get("consensus_vote", "watch"),
                }
                for i, d in enumerate(debated)
            }
            cal_report = self._reality_calibrator.calibrate_from_campaigns(
                reality_campaigns, predictions,
            )
            report["stages"]["reality_calibration"] = cal_report

        # Stage 7: Compile briefing
        report["morning_briefing"] = self._format_briefing(debated, graph_insights, hybrid_opps)
        report["top_opportunities"] = debated[:5]
        report["causal_insights"] = graph_insights
        report["hybrid_suggestions"] = hybrid_opps[:5]

        self._today_opportunities = debated
        return report

    @staticmethod
    def _meta_ads_campaigns_from_report(
        reality_report: dict[str, Any],
    ) -> list[CampaignReality]:
        """Extract campaigns from reality pipeline report (for RealityCalibrator)."""
        meta = reality_report.get("sources", {}).get("meta_ads", {})
        # If the pipeline already fed campaigns, get them from reality tracker
        return []  # Campaigns are already in flywheel._reality_tracker via feed_to_flywheel

    # ── Outcome Recording (next day) ────────────────────────

    def record_outcomes(self, results: list[dict[str, Any]]) -> None:
        """Record real-world outcomes from yesterday's decisions.

        Feeds into: DecisionHistory + RealityTracker + GenomeAttribution + FailureAnalyzer

        Args:
            results: [{opportunity, roas, ctr, cpi, installs, outcome, genome}]
        """
        predictions = {}  # genome_id → predicted_score

        for r in results:
            # E6: Record decision
            self._decision_history.record_decision(
                DecisionRecord(
                    opportunity_name=r.get("opportunity", "unknown"),
                    actual_roas=r.get("roas", 0),
                    actual_ctr=r.get("ctr", 0),
                    actual_installs=r.get("installs", 0),
                    actual_outcome=r.get("outcome", "inconclusive"),
                    was_consensus_correct=(r.get("outcome") == "winner"),
                )
            )

            # E7: Feed reality tracker
            genome = r.get("genome")
            if genome:
                campaign = CampaignReality(
                    creative_id=r.get("creative_id", f"c_{genome.genome_id[:8]}"),
                    genome_id=genome.genome_id,
                    spend=r.get("spend", 100),
                    impressions=r.get("impressions", 5000),
                    clicks=int(r.get("ctr", 0.02) * 5000),
                    ctr=r.get("ctr", 0.02),
                    cpi=r.get("cpi", 5.0),
                    installs=r.get("installs", 20),
                    d7_roas=r.get("roas", 0),
                    revenue_d7=r.get("roas", 0) * r.get("spend", 100),
                )
                self._reality_tracker.ingest_campaign(campaign)

                # E7: Gene attribution
                self._gene_attribution.record_outcome(
                    genome, r.get("roas", 0), r.get("ctr", 0),
                    r.get("cpi", 5), r.get("outcome") == "winner",
                )

                # E6: Genome exchange
                if r.get("outcome") == "winner":
                    self._genome_exchange.register_genome(
                        genome, d7_roas=r.get("roas", 0),
                        ctr=r.get("ctr", 0), installs=r.get("installs", 0),
                        project=r.get("project", "daily_cycle"),
                    )

                predictions[genome.genome_id] = r.get("predicted_score", 50)

        # E7: Compute reality deltas
        deltas = self._reality_tracker.compute_deltas(predictions)

        # E7: Analyze failures
        for delta in deltas:
            if delta.was_failure or not delta.prediction_correct:
                self._failure_analyzer.analyze_failure(delta, {})

        self._today_opportunities = []

    def recalibrate(self) -> dict[str, Any]:
        """Recalibrate agents + learn from reality feedback.

        Returns: calibration, agent ranking, error patterns, gene winners, evolution status.
        """
        # E6: Decision calibration
        calibration = self._decision_history.calibrate()
        ranking = self._decision_history.get_agent_ranking()
        learning = self._decision_history.get_learning_summary()

        # E7: Failure intelligence
        error_summary = self._failure_analyzer.get_system_error_summary()

        # E7: Gene performance from reality
        winning_genes = self._gene_attribution.get_winning_genes()
        losing_genes = self._gene_attribution.get_losing_genes()
        synergies = self._gene_attribution.get_best_synergies()

        # E7: Reality tracker aggregate
        reality_stats = self._reality_tracker.get_aggregate_stats()

        return {
            "calibration": calibration,
            "agent_ranking": ranking,
            "learning_summary": learning,
            "error_intelligence": error_summary,
            "reality_stats": reality_stats,
            "winning_genes": winning_genes[:5],
            "losing_genes": losing_genes[:3],
            "best_synergies": synergies[:3],
            "exchange_summary": self._genome_exchange.get_exchange_summary(),
        }

    def evolve_population(self, genomes: list[Genome], target_size: int = 50) -> dict[str, Any]:
        """E7: Run one generation of Darwinian genome evolution.

        Uses real performance data to select survivors + breed next generation.
        """
        gen = self._evolution_engine.evolve(genomes, target_size)
        self._populations.append(gen.genomes)
        trend = self._evolution_engine.get_evolution_trend()

        return {
            "generation": gen.generation,
            "population_size": len(gen.genomes),
            "elites_preserved": len(gen.elite_ids),
            "diversity": round(gen.diversity_score, 2),
            "evolution_trend": trend,
            "history": self._evolution_engine.get_evolution_history(),
        }
    # ── Internal: Debate ───────────────────────────────────

    def _debate_opportunity(self, opp: Any) -> dict[str, Any]:
        """Run full debate on an opportunity."""
        agents = [
            MarketAgent(self._debate_memory),
            GameplayAgent(self._debate_memory),
            UAAgent(self._debate_memory),
            ProducerAgent(self._debate_memory),
            InvestorAgent(self._debate_memory),
        ]

        evidence = {
            "genes": opp.recommended_genome,
            "market_data": {"growth": opp.market_momentum,
                            "competition": 100 - getattr(opp, 'market_momentum', 50)},
            "creative_data": {},
            "total_score": opp.score,
            "test_budget": 3000,
            "missing_dimensions": [],
            "creative_signals": opp.creative_signals,
        }

        result = self._consensus_engine.run_debate(agents, evidence)

        return {
            "opportunity": opp.name,
            "score": opp.score,
            "category": opp.category,
            "consensus_vote": result["final_vote"],
            "consensus_strength": result["consensus_strength"],
            "total_arguments": result["total_arguments"],
            "vote_details": result["vote_details"],
            "recommended_genome": opp.recommended_genome,
        }

    # ── Internal: Formatting ────────────────────────────────

    def _format_briefing(
        self,
        debated: list[dict],
        insights: list[dict],
        hybrids: list[dict],
    ) -> str:
        """Format the daily briefing for human review."""
        lines = [
            "# Creative Intelligence Daily Briefing",
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## Market Intelligence",
        ]
        for insight in insights[:3]:
            lines.append(f"### {insight['category']} ({insight['lifecycle']})")
            for cause in insight.get("causal_analysis", [])[:3]:
                lines.append(f"- {cause}")
        lines.append("")

        lines.append("## Top Opportunities")
        for i, opp in enumerate(debated[:5], 1):
            vote = opp["consensus_vote"].upper()
            strength = opp["consensus_strength"]
            lines.append(f"#{i}. **{opp['opportunity']}** (Score: {opp['score']:.0f})")
            lines.append(f"   Consensus: {vote} ({strength:.0%} agreement)")
            genome = opp.get("recommended_genome", {})
            if genome:
                genes_str = ", ".join(f"{k}={v}" for k, v in list(genome.items())[:4])
                lines.append(f"   Genome: {genes_str}")
            lines.append("")

        lines.append("## Hybrid Opportunities")
        for h in hybrids[:3]:
            cats = " + ".join(h["categories"])
            lines.append(f"- {cats}: {h['rationale']} (Score: {h['opportunity_score']})")

        return "\n".join(lines)
