"""Opportunity Report Generator — produce daily human-readable reports."""

from __future__ import annotations

from typing import Any

from market_ops.creative_opportunity.schemas import (
    OpportunityReport,
    RankedOpportunity,
    Recommendation,
)
from market_ops.creative_opportunity.opportunity_ranker import OpportunityRanker
from market_ops.creative_opportunity.opportunity_engine import OpportunityIntelligenceEngine


class OpportunityReportGenerator:
    """Generate daily opportunity reports from the intelligence pipeline."""

    def __init__(
        self,
        engine: OpportunityIntelligenceEngine | None = None,
        ranker: OpportunityRanker | None = None,
    ) -> None:
        self._engine = engine or OpportunityIntelligenceEngine()
        self._ranker = ranker or OpportunityRanker()

    def generate_daily_report(self) -> OpportunityReport:
        """Run full pipeline and generate today's opportunity report.

        Flow:
            Market Scan → Human Ideas → Deduplicate → Rank → Report
        """
        opportunities = self._engine.run_full_pipeline()
        ranked = self._ranker.rank(opportunities)

        build_count = sum(1 for r in ranked if r.recommendation == Recommendation.BUILD)
        watch_count = sum(1 for r in ranked if r.recommendation == Recommendation.WATCH)
        ignore_count = sum(1 for r in ranked if r.recommendation == Recommendation.IGNORE)

        summary = {
            "total_opportunities": len(ranked),
            "build_count": build_count,
            "watch_count": watch_count,
            "ignore_count": ignore_count,
            "avg_score": round(
                sum(r.opportunity.score for r in ranked) / max(1, len(ranked)), 1
            ),
            "top_opportunity": ranked[0].opportunity.name if ranked else None,
            "source_breakdown": self._source_breakdown(ranked),
            "category_breakdown": self._category_breakdown(ranked),
        }

        return OpportunityReport(
            ranked_opportunities=ranked,
            summary=summary,
        )

    def generate_for_approved(self) -> OpportunityReport:
        """Generate report for only approved (human-approved) opportunities."""
        all_opps = self._engine.get_all()
        approved = [o for o in all_opps if o.status.value == "approved"]
        ranked = self._ranker.rank(approved)

        return OpportunityReport(
            ranked_opportunities=ranked,
            summary={
                "total_approved": len(ranked),
                "top_score": ranked[0].opportunity.score if ranked else 0,
            },
        )

    @staticmethod
    def _source_breakdown(ranked: list[RankedOpportunity]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in ranked:
            src = r.opportunity.source.name.lower()
            counts[src] = counts.get(src, 0) + 1
        return counts

    @staticmethod
    def _category_breakdown(ranked: list[RankedOpportunity]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in ranked:
            cat = r.opportunity.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts
