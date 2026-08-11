"""E5.1 Market Brain — Opportunity Generator.

Takes raw signals from TrendDetector + CompetitorTracker + CreativeSignalMiner
and synthesizes actionable Creative Opportunities with recommended genomes.

Output: Opportunity card with genome blueprint, ready for Creative Brain pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from market_ops.market_intelligence.trend_detector import TrendDetector, TrendSignal
from market_ops.market_intelligence.competitor_tracker import CompetitorTracker, CompetitorProfile
from market_ops.market_intelligence.creative_signal_miner import CreativeSignalMiner, CreativeSignal
from market_ops.market_intelligence.category_heatmap import CategoryHeatmapEngine


@dataclass
class CreativeOpportunity:
    """A synthesized market opportunity with recommended genome."""
    opportunity_id: str = ""
    name: str = ""
    category: str = ""
    score: float = 0.0              # 0-100
    # Component scores
    market_momentum: float = 0.0     # /30
    creative_potential: float = 0.0  # /25
    build_efficiency: float = 0.0    # /20
    monetization_fit: float = 0.0    # /15
    evolution_space: float = 0.0     # /10
    # Evidence
    supporting_trends: list[str] = field(default_factory=list)
    competitor_signals: list[str] = field(default_factory=list)
    creative_signals: list[str] = field(default_factory=list)
    # Action
    recommended_genome: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.5
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "name": self.name,
            "category": self.category,
            "score": round(self.score, 1),
            "components": {
                "market_momentum": round(self.market_momentum, 1),
                "creative_potential": round(self.creative_potential, 1),
                "build_efficiency": round(self.build_efficiency, 1),
                "monetization_fit": round(self.monetization_fit, 1),
                "evolution_space": round(self.evolution_space, 1),
            },
            "supporting_trends": self.supporting_trends,
            "competitor_signals": self.competitor_signals,
            "creative_signals": self.creative_signals,
            "recommended_genome": self.recommended_genome,
            "confidence": self.confidence,
        }


class OpportunityGenerator:
    """Generate creative opportunities from market intelligence.

    Flow:
        TrendDetector → CompetitorTracker → CreativeSignalMiner → Heatmap
                                                                    ↓
        OpportunityGenerator: synthesize → score → rank → recommend
    """

    def __init__(self) -> None:
        self._trend_detector = TrendDetector()
        self._competitor_tracker = CompetitorTracker()
        self._signal_miner = CreativeSignalMiner()
        self._heatmap = CategoryHeatmapEngine()

    def generate(self) -> list[CreativeOpportunity]:
        """Generate all opportunities from current market data."""
        trends = self._trend_detector.detect_from_mock_data()
        competitors = self._competitor_tracker.scan()
        signals = self._signal_miner.mine()
        heatmap = self._heatmap.generate()

        opportunities = []

        # Generate from trends
        for trend in trends[:5]:
            opp = self._synthesize_from_trend(trend, competitors, signals, heatmap)
            if opp:
                opportunities.append(opp)

        # Generate from competitor weaknesses
        for comp in competitors[:3]:
            opp = self._synthesize_from_competitor(comp, trends, signals)
            if opp:
                opportunities.append(opp)

        # Sort by score
        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities

    def get_top_opportunities(self, n: int = 5) -> list[CreativeOpportunity]:
        """Get top N opportunities."""
        return self.generate()[:n]

    # ── Synthesis ───────────────────────────────────────────

    def _synthesize_from_trend(
        self, trend: TrendSignal, competitors: list[CompetitorProfile],
        signals: list[CreativeSignal], heatmap: Any,
    ) -> CreativeOpportunity | None:
        """Synthesize an opportunity from a market trend."""
        cat_cell = next((c for c in heatmap.cells if c.category == trend.category), None)

        market = min(30, trend.velocity_score * 0.3 + (cat_cell.market_heat * 0.1 if cat_cell else 10))
        creative = min(25, 15 + len(trend.sources) * 2)
        build = min(20, 14 + (1 if trend.category in ["sort", "merge"] else 0))
        monet = min(15, 10 + (3 if trend.growth_pct > 100 else 1))
        evo = min(10, 6 + (2 if trend.direction.value in ["exploding", "rising"] else 1))

        score = market + creative + build + monet + evo

        genome = self._build_genome_from_signals(trend.category, signals)

        return CreativeOpportunity(
            opportunity_id=f"opp_market_{trend.category}_{datetime.now().strftime('%Y%m%d')}",
            name=f"{trend.category.capitalize()} + {trend.subcategory.replace('_', ' ').title()}",
            category=trend.category,
            score=score, market_momentum=market, creative_potential=creative,
            build_efficiency=build, monetization_fit=monet, evolution_space=evo,
            supporting_trends=trend.evidence,
            competitor_signals=[],
            creative_signals=[],
            recommended_genome=genome,
            confidence=0.7 if trend.confidence.value == "high" else 0.5,
        )

    def _synthesize_from_competitor(
        self, comp: CompetitorProfile, trends: list[TrendSignal],
        signals: list[CreativeSignal],
    ) -> CreativeOpportunity | None:
        """Synthesize an opportunity from competitor weaknesses."""
        if not comp.opportunities:
            return None

        market = min(30, 15 + comp.growth_30d * 0.15)
        creative = min(25, 15 + len(comp.creative_strategy) * 2)
        build = min(20, 12 + (2 if comp.category in ["sort", "merge"] else 0))
        monet = min(15, 8 + len(comp.weaknesses) * 1)
        evo = min(10, 5 + len(comp.opportunities))

        score = market + creative + build + monet + evo

        genome = dict(comp.key_genes)
        # Add opportunity-driven gene
        if "add" in comp.opportunities[0].lower() or "hybrid" in str(comp.opportunities).lower():
            for opp_text in comp.opportunities:
                if "rescue" in opp_text.lower():
                    genome["hook"] = "rescue"
                if "collection" in opp_text.lower():
                    genome["reward"] = "collection"
                if "evolution" in opp_text.lower():
                    genome["reward"] = "evolution"

        return CreativeOpportunity(
            opportunity_id=f"opp_comp_{comp.game_id}",
            name=f"Counter-{comp.name}: {comp.opportunities[0][:40]}",
            category=comp.category,
            score=score, market_momentum=market, creative_potential=creative,
            build_efficiency=build, monetization_fit=monet, evolution_space=evo,
            supporting_trends=[],
            competitor_signals=[f"{comp.name}: {w}" for w in comp.weaknesses[:2]],
            creative_signals=[],
            recommended_genome=genome,
            confidence=0.6,
        )

    @staticmethod
    def _build_genome_from_signals(category: str, signals: list[CreativeSignal]) -> dict[str, str]:
        """Build recommended genome from creative signals."""
        genome: dict[str, str] = {}

        # Best hook for category
        hooks = [s for s in signals if s.dimension == "hook" and s.ctr_prediction == "high"]
        if hooks:
            genome["hook"] = max(hooks, key=lambda s: s.prevalence).value

        # Best visual
        visuals = [s for s in signals if s.dimension == "visual" and s.growth_30d > 0]
        if visuals:
            genome["visual"] = max(visuals, key=lambda s: s.growth_30d).value

        # Best reward
        rewards = [s for s in signals if s.dimension == "reward"]
        if rewards:
            genome["reward"] = max(rewards, key=lambda s: s.prevalence).value

        genome["core_loop"] = category
        return genome
