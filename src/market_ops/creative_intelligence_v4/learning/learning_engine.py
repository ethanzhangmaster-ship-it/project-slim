"""V4.0: Learning Engine — Facebook feedback loop.

Closed-loop learning:
  Facebook Performance → Winner Detection → DNA Extraction
  → Prompt Generation → Image/Video Generation → Review
  → Learning → Next Generation

The Learning Engine analyzes which DNAs work and why,
then feeds insights back to the Creative Intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..creative_repository.metadata import CreativeMetadata, CreativeStatus


@dataclass
class LearningInsight:
    """A single learning insight from performance data."""
    dimension: str = ""
    winning_value: str = ""
    losing_value: str = ""
    confidence: float = 0.0
    sample_count: int = 0
    source: str = ""  # "performance", "review", "mutation"
    created_at: str = ""


@dataclass
class LearningReport:
    """Complete learning report from a batch of creative performance."""
    insights: list[LearningInsight] = field(default_factory=list)
    total_creatives: int = 0
    winners: int = 0
    losers: int = 0
    top_dna: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""


class LearningEngine:
    """V4.0 Learning Engine — closed-loop optimization.

    Analyzes performance data to identify winning and losing patterns,
    then generates recommendations for the next generation.
    """

    def __init__(self) -> None:
        self._insights: list[LearningInsight] = []

    def analyze(self, repository) -> LearningReport:
        """Analyze all creatives in the repository and generate insights.

        Returns a LearningReport with winning patterns and recommendations.
        """
        all_creatives = repository.list_all()
        winners = [c for c in all_creatives if c.status == CreativeStatus.WINNER]
        losers = [c for c in all_creatives if c.status == CreativeStatus.LOSER]

        insights = []

        # 1. Performance-based insights
        if winners:
            insights.extend(self._analyze_winners(winners, repository))

        # 2. Review-based insights
        reviewed = [c for c in all_creatives if c.review_count > 0]
        if reviewed:
            insights.extend(self._analyze_reviews(reviewed, repository))

        # 3. Generate recommendations
        recommendations = self._generate_recommendations(insights, winners, losers)

        return LearningReport(
            insights=insights,
            total_creatives=len(all_creatives),
            winners=len(winners),
            losers=len(losers),
            top_dna=self._extract_top_dna(winners, repository),
            recommendations=recommendations,
            generated_at=datetime.now().isoformat(),
        )

    def _analyze_winners(
        self, winners: list[CreativeMetadata], repository,
    ) -> list[LearningInsight]:
        """Analyze winning creatives for common DNA patterns."""
        insights = []
        dna_list = []

        for w in winners:
            dna = repository.get_dna(w.creative_id)
            if dna:
                dna_list.append(dna)

        if not dna_list:
            return insights

        # Count common DNA values
        for dim in ["character", "reward", "camera", "lighting", "hook", "gameplay"]:
            values = {}
            for dna in dna_list:
                v = dna.get(dim, "")
                if v:
                    values[v] = values.get(v, 0) + 1

            top_value = max(values, key=values.get, default="")
            if top_value and values[top_value] >= 2:
                insights.append(LearningInsight(
                    dimension=dim,
                    winning_value=top_value,
                    confidence=values[top_value] / len(dna_list),
                    sample_count=len(dna_list),
                    source="performance",
                    created_at=datetime.now().isoformat(),
                ))

        return insights

    def _analyze_reviews(
        self, reviewed: list[CreativeMetadata], repository,
    ) -> list[LearningInsight]:
        """Analyze human review scores for patterns."""
        insights = []

        for r in reviewed:
            review = repository.get_review(r.creative_id)
            if not review:
                continue
            scores = review.get("scores", {})
            for dim, score in scores.items():
                if isinstance(score, (int, float)) and score >= 8:
                    dna = repository.get_dna(r.creative_id)
                    if dna:
                        dna_value = dna.get(dim, "")
                        if dna_value:
                            insights.append(LearningInsight(
                                dimension=dim,
                                winning_value=dna_value,
                                confidence=0.7,
                                sample_count=1,
                                source="review",
                                created_at=datetime.now().isoformat(),
                            ))

        return insights

    def _generate_recommendations(
        self, insights: list[LearningInsight],
        winners: list[CreativeMetadata],
        losers: list[CreativeMetadata],
    ) -> list[str]:
        recommendations = []

        for insight in insights:
            if insight.confidence >= 0.6:
                recommendations.append(
                    f"Use {insight.dimension}='{insight.winning_value}' "
                    f"(confidence: {insight.confidence:.0%}, n={insight.sample_count})"
                )

        if winners:
            avg_roas = sum(w.roas_d7 for w in winners if w.roas_d7 > 0) / max(len(winners), 1)
            recommendations.append(
                f"Average winner ROAS D7: {avg_roas:.2f} across {len(winners)} winners"
            )

        if losers:
            recommendations.append(
                f"Consider pausing {len(losers)} low-performing creatives"
            )

        return recommendations

    def _extract_top_dna(
        self, winners: list[CreativeMetadata], repository,
    ) -> dict[str, Any]:
        """Extract the best-performing DNA."""
        if not winners:
            return {}

        best = max(winners, key=lambda w: w.roas_d7 or 0)
        dna = repository.get_dna(best.creative_id)
        return dna or {}

    @property
    def insights(self) -> list[LearningInsight]:
        return self._insights