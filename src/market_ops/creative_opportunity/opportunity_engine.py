"""Opportunity Intelligence Engine — merge, deduplicate, and score opportunities.

Unifies Human Ideas + AI Market Scanner outputs into a single ranked pipeline.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from market_ops.creative_opportunity.schemas import (
    HumanIdea,
    Opportunity,
    OpportunityCategory,
    OpportunitySource,
    OpportunityStatus,
)
from market_ops.creative_opportunity.market_scanner import MarketScanner, MockMarketScanner
from market_ops.creative_opportunity.human_idea import HumanIdeaInbox


class OpportunityIntelligenceEngine:
    """Core engine: ingest ideas + scan market → deduplicated opportunities."""

    # Deduplication threshold (0-1)
    SIMILARITY_THRESHOLD = 0.65

    # Human idea → opportunity score boost
    HUMAN_BOOST = 5.0

    def __init__(
        self,
        scanner: MarketScanner | None = None,
        inbox: HumanIdeaInbox | None = None,
    ) -> None:
        self._scanner = scanner or MockMarketScanner()
        self._inbox = inbox or HumanIdeaInbox()
        self._opportunities: list[Opportunity] = []

    # ── Ingestion ───────────────────────────────────────────

    def ingest_human_idea(self, idea: HumanIdea) -> Opportunity:
        """Convert a human idea into an Opportunity and score it."""
        opp = self._idea_to_opportunity(idea)
        self._score_human_opportunity(opp, idea)
        self._opportunities.append(opp)
        return opp

    def ingest_all_human_ideas(self) -> list[Opportunity]:
        """Convert all pending human ideas to opportunities."""
        ideas = self._inbox.get_pending()
        results = []
        for idea in ideas:
            opp = self.ingest_human_idea(idea)
            results.append(opp)
            idea.status = OpportunityStatus.APPROVED  # Auto-approve for pipeline
        return results

    def scan_market(self) -> list[Opportunity]:
        """Run market scanner and ingest AI-discovered opportunities."""
        ai_opportunities = self._scanner.scan()
        self._opportunities.extend(ai_opportunities)
        return ai_opportunities

    def run_full_pipeline(self) -> list[Opportunity]:
        """Complete pipeline: human ideas + market scan + deduplication."""
        self._opportunities = []
        self.ingest_all_human_ideas()
        self.scan_market()
        self.deduplicate()
        return list(self._opportunities)

    # ── Deduplication ───────────────────────────────────────

    def deduplicate(self) -> list[Opportunity]:
        """Merge semantically similar opportunities.

        Uses name + description similarity. Higher-scoring opportunity survives.
        """
        if len(self._opportunities) <= 1:
            return self._opportunities

        kept: list[Opportunity] = []
        merged_ids: set[str] = set()

        # Sort by score descending so best opportunity survives
        sorted_opps = sorted(self._opportunities, key=lambda o: o.score, reverse=True)

        for i, opp in enumerate(sorted_opps):
            if opp.opportunity_id in merged_ids:
                continue

            for other in sorted_opps[i + 1 :]:
                if other.opportunity_id in merged_ids:
                    continue
                sim = self._similarity(opp, other)
                if sim >= self.SIMILARITY_THRESHOLD:
                    # Merge other into opp
                    self._merge_opportunities(opp, other)
                    merged_ids.add(other.opportunity_id)

            kept.append(opp)

        self._opportunities = kept
        return kept

    # ── Query ───────────────────────────────────────────────

    def get_all(self) -> list[Opportunity]:
        """Return all current opportunities."""
        return list(self._opportunities)

    def get_by_category(self, category: OpportunityCategory) -> list[Opportunity]:
        """Filter by category."""
        return [o for o in self._opportunities if o.category == category]

    def get_by_tag(self, tag: str) -> list[Opportunity]:
        """Filter by tag."""
        return [o for o in self._opportunities if tag.lower() in [t.lower() for t in o.tags]]

    def get_top(self, n: int = 10) -> list[Opportunity]:
        """Return top N by score."""
        return sorted(self._opportunities, key=lambda o: o.score, reverse=True)[:n]

    # ── Internal: Conversion ────────────────────────────────

    @staticmethod
    def _idea_to_opportunity(idea: HumanIdea) -> Opportunity:
        """Convert HumanIdea to Opportunity."""
        # Infer category from tags/description
        category = OpportunityIntelligenceEngine._infer_category(idea.description + " " + " ".join(idea.tags))

        return Opportunity(
            name=idea.title,
            description=idea.description,
            category=category,
            source=OpportunitySource.HUMAN,
            reference_games=idea.reference_games,
            tags=idea.tags,
            status=OpportunityStatus.PENDING,
            metadata={
                "idea_id": idea.idea_id,
                "creator": idea.creator,
                "source": "human_inbox",
            },
        )

    @staticmethod
    def _infer_category(text: str) -> OpportunityCategory:
        """Infer opportunity category from text."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["visual", "3d", "art", "style", "animation"]):
            return OpportunityCategory.VISUAL_TREND
        if any(w in text_lower for w in ["monetization", "battle pass", "iap", "revenue"]):
            return OpportunityCategory.MONETIZATION_TREND
        if any(w in text_lower for w in ["ua", "ads", "creative", "campaign", "tiktok"]):
            return OpportunityCategory.UA_OPPORTUNITY
        if any(w in text_lower for w in ["gap", "missing", "empty", "no one"]):
            return OpportunityCategory.MARKET_GAP
        return OpportunityCategory.GAMEPLAY_INNOVATION

    def _score_human_opportunity(self, opp: Opportunity, idea: HumanIdea) -> None:
        """Score a human-submitted opportunity.

        Human ideas get a baseline score + boost for detail.
        """
        # Base score
        opp.score = 50.0 + self.HUMAN_BOOST

        # Boost for reference games (more research = higher confidence)
        opp.confidence = 0.5 + min(len(idea.reference_games) * 0.05, 0.3)

        # Default component scores for human ideas
        opp.market_momentum = 60.0
        opp.competition_gap = 55.0
        opp.ua_potential = 60.0
        opp.production_cost = 50.0
        opp.creative_fit = 60.0
        opp.historical_success = 50.0

        # Recompute final score
        opp.score = self._compute_score_from_components(opp)

    @staticmethod
    def _compute_score_from_components(opp: Opportunity) -> float:
        """Recalculate score from component scores."""
        weights = {
            "market_momentum": 0.25,
            "competition_gap": 0.20,
            "ua_potential": 0.20,
            "production_cost": 0.15,
            "creative_fit": 0.10,
            "historical_success": 0.10,
        }
        score = 0.0
        for key, weight in weights.items():
            score += getattr(opp, key, 50) * weight
        return round(score, 1)

    # ── Internal: Deduplication Helpers ─────────────────────

    @staticmethod
    def _similarity(a: Opportunity, b: Opportunity) -> float:
        """Compute text similarity between two opportunities."""
        text_a = f"{a.name} {a.description}"
        text_b = f"{b.name} {b.description}"
        return SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()

    @staticmethod
    def _merge_opportunities(target: Opportunity, source: Opportunity) -> None:
        """Merge source opportunity into target."""
        # Combine reference games
        target.reference_games = list(
            set(target.reference_games + source.reference_games)
        )
        # Combine tags
        target.tags = list(set(target.tags + source.tags))
        # Boost confidence
        target.confidence = min(0.95, target.confidence + 0.05)
        # Average component scores
        for attr in ["market_momentum", "competition_gap", "ua_potential",
                     "production_cost", "creative_fit", "historical_success"]:
            val_a = getattr(target, attr, 0)
            val_b = getattr(source, attr, 0)
            setattr(target, attr, round((val_a + val_b) / 2, 1))
        # Recalculate score
        target.score = OpportunityIntelligenceEngine._compute_score_from_components(target)
        # Mark source as merged
        source.status = OpportunityStatus.REJECTED
        target.metadata["merged_from"] = target.metadata.get("merged_from", []) + [source.opportunity_id]
