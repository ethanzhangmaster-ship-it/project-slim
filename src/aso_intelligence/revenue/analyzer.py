"""
E16.6.6 — ASO Revenue Analyzer.

The analysis engine that computes:
  1. Keyword Revenue Intelligence — ``KeywordValueScore`` per keyword
  2. Country Revenue Attribution — ``CountryRevenueAttribution`` per country
  3. Listing Experiment Revenue Evaluation — winner/loser with revenue impact
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.aso_intelligence.revenue.models import (
    ASOAcquisitionEvent,
    ASORevenueAttribution,
    ASOActionReward,
    KeywordValueScore,
    CountryRevenueAttribution,
    ASORevenueReport,
)
from src.aso_intelligence.revenue.attribution import ASORevenueAttributor
from src.aso_intelligence.revenue.quality import ASOUserQualityAnalyzer


@dataclass
class ExperimentRevenueVerdict:
    """Revenue outcome for one listing experiment."""

    experiment_id: str
    action: str
    cvr_change: float
    revenue_change: float
    payer_change: float
    verdict: str  # WINNER / LOSER / NEUTRAL
    reason: str


class ASORevenueAnalyzer:
    """Analyse ASO revenue data: keywords, countries, experiments."""

    def __init__(
        self,
        attributor: Optional[ASORevenueAttributor] = None,
        quality: Optional[ASOUserQualityAnalyzer] = None,
    ):
        self.attributor = attributor or ASORevenueAttributor()
        self.quality = quality or ASOUserQualityAnalyzer()

    # ------------------------------------------------------------------ #
    # 1. Keyword Revenue Intelligence
    # ------------------------------------------------------------------ #
    def analyze_keywords(
        self,
        game_id: str,
        keyword_data: List[Dict[str, Any]],
    ) -> List[KeywordValueScore]:
        """Compute ``KeywordValueScore`` for a set of keywords.

        Each dict expects:
          keyword, search_volume, install_rate, payer_rate, ltv, competition
        """
        scores: List[KeywordValueScore] = []
        for kd in keyword_data:
            kws = KeywordValueScore(
                keyword=kd.get("keyword", ""),
                game_id=game_id,
                search_volume=int(kd.get("search_volume", 0)),
                install_rate=float(kd.get("install_rate", 0.0)),
                payer_rate=float(kd.get("payer_rate", 0.0)),
                ltv=float(kd.get("ltv", 0.0)),
                competition=float(kd.get("competition", 0.5)),
            )
            kws.compute()
            scores.append(kws)

        # Sort by score descending
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    def top_keywords(
        self, scores: List[KeywordValueScore], k: int = 10
    ) -> List[KeywordValueScore]:
        return scores[:k]

    def high_value_keywords(
        self, scores: List[KeywordValueScore]
    ) -> List[KeywordValueScore]:
        return [s for s in scores if s.is_high_value()]

    # ------------------------------------------------------------------ #
    # 2. Country Revenue Attribution
    # ------------------------------------------------------------------ #
    def analyze_countries(
        self,
        game_id: str,
        events: List[ASOAcquisitionEvent],
        revenue_map: Dict[str, float],
        payer_map: Dict[str, int],
        dau_map: Optional[Dict[str, int]] = None,
    ) -> List[CountryRevenueAttribution]:
        """Compute country-level revenue attribution."""
        raw = self.attributor.attribute_by_country(
            events, revenue_map, payer_map, dau_map
        )

        countries: List[CountryRevenueAttribution] = []
        for r in raw:
            # Parse country from source_key "country:US"
            country_code = r.source_key.replace("country:", "")
            countries.append(
                CountryRevenueAttribution(
                    country=country_code,
                    game_id=game_id,
                    installs=r.installs,
                    revenue=r.revenue,
                    payer_count=r.payer_count,
                    dau=r.dau,
                )
            )

        # Sort by revenue descending
        countries.sort(key=lambda c: c.revenue, reverse=True)
        return countries

    # ------------------------------------------------------------------ #
    # 3. Listing Experiment Revenue Evaluation
    # ------------------------------------------------------------------ #

    def evaluate_experiment_revenue(
        self,
        experiment_id: str,
        action: str,
        attribution_before: ASORevenueAttribution,
        attribution_after: ASORevenueAttribution,
    ) -> ExperimentRevenueVerdict:
        """Evaluate whether a listing experiment was a revenue success."""
        cvr_proxy = (
            (attribution_after.installs - attribution_before.installs)
            / max(attribution_before.installs, 1)
        )
        revenue_change = (
            (attribution_after.revenue - attribution_before.revenue)
            / max(attribution_before.revenue, 0.01)
        )
        payer_change = (
            (attribution_after.payer_count - attribution_before.payer_count)
            / max(attribution_before.payer_count, 1)
        )

        if revenue_change > 0.05 and payer_change > -0.05:
            verdict = "WINNER"
            reason = f"D30 revenue +{revenue_change:.0%}, payers {payer_change:+.0%}"
        elif revenue_change > 0.05 and payer_change <= -0.05:
            verdict = "NEUTRAL"
            reason = (
                f"Revenue +{revenue_change:.0%} but payers {payer_change:.0%} — "
                f"quality concern"
            )
        elif revenue_change <= 0 and cvr_proxy > 0.1:
            verdict = "LOSER"
            reason = (
                f"CVR +{cvr_proxy:.0%} but revenue {revenue_change:.0%} — "
                f"user quality dropped significantly"
            )
        else:
            verdict = "NEUTRAL"
            reason = f"Revenue {revenue_change:+.0%} — insufficient impact"

        return ExperimentRevenueVerdict(
            experiment_id=experiment_id,
            action=action,
            cvr_change=round(cvr_proxy, 4),
            revenue_change=round(revenue_change, 4),
            payer_change=round(payer_change, 4),
            verdict=verdict,
            reason=reason,
        )

    # ------------------------------------------------------------------ #
    # 4. Generate full report
    # ------------------------------------------------------------------ #
    def generate_report(
        self,
        game_id: str,
        date: str,
        keyword_scores: List[KeywordValueScore],
        country_attributions: List[CountryRevenueAttribution],
        action_rewards: Optional[List[ASOActionReward]] = None,
    ) -> ASORevenueReport:
        """Assemble a complete revenue attribution report."""
        report = ASORevenueReport(
            game_id=game_id,
            date=date,
            keyword_scores=keyword_scores,
            country_attributions=country_attributions,
            action_rewards=action_rewards or [],
            total_aso_revenue=sum(c.revenue for c in country_attributions),
            total_payers=sum(c.payer_count for c in country_attributions),
            total_installs=sum(c.installs for c in country_attributions),
        )
        return report


__all__ = ["ASORevenueAnalyzer"]
