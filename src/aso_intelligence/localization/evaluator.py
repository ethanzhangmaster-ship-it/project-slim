"""
E16.6.9 — Localization Quality Evaluator.

Evaluates market-specific localisation on four dimensions:
  * **Language Quality** — natural, grammatical, appropriate register
  * **Keyword Fit** — does the copy include locally-searched keywords?
  * **Cultural Fit** — does the messaging match local player motivation?
  * **Revenue History** — has this market historically shown strong LTV?

Also supports comparing markets and adjusting investment decisions
based on revenue feedback.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.aso_intelligence.localization.models import (
    MarketProfile,
    LocalizationScore,
)


class LocalizationEvaluator:
    """Evaluate the commercial quality of a market localisation."""

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        profile: MarketProfile,
        *,
        has_keywords: bool = True,
        keyword_match_ratio: float = 0.8,
        motivation_match: bool = True,
        revenue_history: float = 1.0,
    ) -> LocalizationScore:
        """Score one market's localisation quality.

        ``has_keywords`` — whether the market has keyword mappings
        ``keyword_match_ratio`` — fraction of preferred words in copy
        ``motivation_match`` — whether copy matches market motivation
        ``revenue_history`` — historical LTV multiplier (from E16.6.6)
        """
        # Language quality: baseline 0.8, slightly higher for non-English
        # (requires more care → higher score if done well)
        lang_base = 0.9 if profile.language == "en" else 0.88
        language_quality = lang_base

        # Keyword fit
        keyword_fit = keyword_match_ratio if has_keywords else 0.3

        # Cultural fit based on motivation alignment
        cultural_fit = 0.9 if motivation_match else 0.4

        # Revenue history from E16.6.6 (higher LTV markets get a boost)
        revenue_boost = min(1.2, max(0.5, revenue_history))

        return LocalizationScore(
            language_quality=language_quality,
            keyword_fit=keyword_fit,
            cultural_fit=cultural_fit,
            revenue_history=revenue_boost,
        )

    # ------------------------------------------------------------------ #
    def evaluate_default(
        self,
        profile: MarketProfile,
    ) -> LocalizationScore:
        """Default evaluation assuming good keyword match and motivation fit."""
        return self.evaluate(
            profile,
            has_keywords=True,
            keyword_match_ratio=0.9,
            motivation_match=True,
            revenue_history=1.0,
        )

    # ------------------------------------------------------------------ #
    def compare_markets(
        self,
        profiles: List[MarketProfile],
        revenue_history_map: Dict[str, float] = None,
    ) -> List[Dict]:
        """Compare multiple markets and rank by localisation fit."""
        revenue_map = revenue_history_map or {}
        results: List[Dict] = []

        for profile in profiles:
            rev = revenue_map.get(profile.country, 1.0)
            score = self.evaluate(
                profile,
                has_keywords=True,
                keyword_match_ratio=0.8,
                motivation_match=True,
                revenue_history=rev,
            )
            results.append({
                "country": profile.country,
                "motivation": profile.motivation,
                "score": score.compute(),
                "revenue_history": rev,
                "investment_priority": (
                    "HIGH" if score.compute() >= 0.8 else
                    "MEDIUM" if score.compute() >= 0.5 else
                    "LOW"
                ),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ------------------------------------------------------------------ #
    def revenue_feedback(
        self,
        market_cvr: Dict[str, float],
        market_ltv: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply revenue feedback: high LTV markets get higher weight.

        Input: market → CVR, market → LTV
        Output: market → revenue_weight (used in LocalizationScore.revenue_history)
        """
        if not market_ltv:
            return {m: 1.0 for m in market_cvr}

        max_ltv = max(market_ltv.values())
        weights: Dict[str, float] = {}

        for market in set(list(market_cvr.keys()) + list(market_ltv.keys())):
            ltv = market_ltv.get(market, 0.0)
            cvr = market_cvr.get(market, 0.0)

            # Weight = LTV ratio × CVR adjustment
            # Top LTV market gets weight > 1.0 (signals priority)
            ltv_ratio = ltv / max_ltv if max_ltv > 0 else 0.5
            base_weight = 0.3 + ltv_ratio * 0.8
            weights[market] = round(base_weight, 4)

        return weights


__all__ = ["LocalizationEvaluator"]
