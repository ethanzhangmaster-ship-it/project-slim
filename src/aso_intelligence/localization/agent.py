"""
E16.6.9 — ASO Localization Agent.

Main pipeline: market analysis → keyword adaptation → copy generation →
creative adaptation → evaluation → learning.

This is how a single game becomes n versions for different markets —
each version culturally optimised for local players.

Pipeline:
    Reality
        → Market Profile
            → Keyword Adaptation (E16.6.7 bridge)
                → Copy Generation (re-expression)
                    → Creative Adaptation (E16.6.8 bridge)
                        → Quality Evaluation
                            → Experiment → Memory
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.localization.models import (
    MarketProfile,
    LocalizedKeyword,
    LocalizedCreativeBrief,
    LocalizationScore,
    LocalizationReport,
)
from src.aso_intelligence.localization.market_profile import (
    MarketProfileRepository,
)
from src.aso_intelligence.localization.keyword_adapter import KeywordAdapter
from src.aso_intelligence.localization.copy_generator import CopyGenerator
from src.aso_intelligence.localization.creative_adapter import CreativeAdapter
from src.aso_intelligence.localization.evaluator import LocalizationEvaluator
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)
from src.aso_intelligence.experiment_memory.experiment_models import (
    ASOPattern,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class ASOLocalizationAgent:
    """AI ASO Localization Manager — make the same game appeal to
    players in every market.

    Typical usage:

        agent = ASOLocalizationAgent.build(store)
        report = agent.run(
            game_id="merge_witch",
            country="JP",
            source_title="Merge Witch",
            genre="merge",
            copy_params={
                "noun": "Witch",
                "goal": "Kingdom",
                "verb": "Collect",
                "theme": "Magic",
                "adj": "Cute",
            },
        )
        print(report.to_markdown())
    """

    def __init__(
        self,
        profiles: Optional[MarketProfileRepository] = None,
        keywords: Optional[KeywordAdapter] = None,
        copy_gen: Optional[CopyGenerator] = None,
        creative: Optional[CreativeAdapter] = None,
        evaluator: Optional[LocalizationEvaluator] = None,
        store: Optional[ASOExperimentStore] = None,
    ):
        self.profiles = profiles or MarketProfileRepository()
        self.keywords = keywords or KeywordAdapter()
        self.copy_gen = copy_gen or CopyGenerator()
        self.creative = creative or CreativeAdapter()
        self.evaluator = evaluator or LocalizationEvaluator()
        self.store = store

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOLocalizationAgent":
        return cls(store=store)

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        country: str,
        source_title: str,
        *,
        source_short_desc: str = "",
        genre: str = "merge",
        copy_params: dict = None,
        # Optional revenue feedback (from E16.6.6)
        market_cvr: Dict[str, float] = None,
        market_ltv: Dict[str, float] = None,
        # Optional keywords to localise
        keywords_to_localize: List[str] = None,
    ) -> LocalizationReport:
        """Run the full localisation pipeline for one game × one market.

        1. Get market profile
        2. Localise keywords (E16.6.7 bridge)
        3. Generate localised copy
        4. Adapt creative direction (E16.6.8 bridge)
        5. Evaluate quality
        6. Learn from revenue feedback → pattern
        """
        # Step 1: Market profile
        profile = self.profiles.get(country)
        if profile is None:
            return LocalizationReport(
                game_id=game_id, country=country, date=_today_iso(),
            )

        # Step 2: Keyword localisation
        localized_keywords: List[LocalizedKeyword] = []
        if keywords_to_localize:
            localized_keywords = self.keywords.localize_batch(
                keywords_to_localize, country
            )
        if not localized_keywords:
            localized_keywords = self.keywords.suggest_keywords(country, genre)

        # Step 3: Copy generation (re-expression, not translation)
        copy_result = self.copy_gen.adapt_all(
            en_title=source_title,
            en_short_desc=source_short_desc or f"Welcome to {source_title}!",
            profile=profile,
            genre=genre,
            params=copy_params,
        )

        # Step 4: Creative adaptation
        creative_brief = self.creative.adapt_brief(
            original_brief_text="", profile=profile,
        )

        # Step 5: Evaluate quality
        score = self.evaluator.evaluate_default(profile)

        # Step 6: Revenue feedback
        opportunities_found = 0
        if market_ltv and market_cvr:
            weights = self.evaluator.revenue_feedback(market_cvr, market_ltv)
            mkt_weight = weights.get(country, 1.0)
            score.revenue_history = mkt_weight
            if mkt_weight > 1.0:
                opportunities_found = 1

        # Step 7: Learn pattern (if store available and quality is high)
        patterns_learned = 0
        if self.store and score.is_high_quality():
            pattern = ASOPattern(
                category=genre,
                condition=f"localization:{country}:{source_title}",
                action=copy_result.get("title", ""),
                result=(
                    f"{country} localization: motivation={profile.motivation}, "
                    f"tone={profile.tone}"
                ),
                confidence=score.compute(),
                sample_size=1,
                success_rate=1.0,
                reward=score.revenue_history,
                pattern_id=f"loc:{country}:{genre}:{profile.motivation}",
            )
            self.store.record_pattern(pattern)
            patterns_learned = 1

        # Report
        report = LocalizationReport(
            game_id=game_id,
            country=country,
            date=_today_iso(),
            market_profile=profile,
            localized_keywords=localized_keywords,
            localized_title=copy_result.get("title", ""),
            localized_short_desc=copy_result.get("short_description", ""),
            localized_full_desc=copy_result.get("full_description", ""),
            creative_brief=creative_brief,
            score=score,
            patterns_learned=patterns_learned,
            opportunities_found=opportunities_found,
        )
        return report

    # ------------------------------------------------------------------ #
    def run_multi_market(
        self,
        game_id: str,
        source_title: str,
        countries: List[str],
        genre: str = "merge",
        copy_params: dict = None,
        market_cvr: Dict[str, float] = None,
        market_ltv: Dict[str, float] = None,
    ) -> Dict[str, LocalizationReport]:
        """Run localisation for multiple markets at once.

        Returns dict of country → report.
        """
        return {
            c: self.run(
                game_id, c, source_title,
                genre=genre, copy_params=copy_params,
                market_cvr=market_cvr, market_ltv=market_ltv,
            )
            for c in countries
        }


__all__ = ["ASOLocalizationAgent"]
