"""
E16.6.7 — ASO Keyword Intelligence Agent.

Main pipeline:
    collect_reality → score → classify → opportunities → report

Connects to E16.6.4 Memory for experiment learning and to E16.6.6 for
revenue attribution data.

Integrates with aso-mcp via an injectable keyword researcher:
  * When no researcher is available, collect_reality is a pure pass-through.
  * When ASOKeywordResearcher is injected, collect_reality enriches every
    incoming keyword with Apple Search Ads popularity/difficulty/brand data
    and appends any newly suggested keywords.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.aso_intelligence.keyword.models import (
    KeywordReality,
    KeywordValueScore,
    KeywordPortfolioEntry,
    KeywordOpportunity,
    KeywordPattern,
    ASOKeywordReport,
)
from src.aso_intelligence.keyword.scoring import KeywordValueScoringEngine
from src.aso_intelligence.keyword.portfolio import KeywordPortfolioManager
from src.aso_intelligence.keyword.opportunity import KeywordOpportunityEngine
from src.aso_intelligence.experiment_memory.experiment_store import (
    ASOExperimentStore,
)

logger = logging.getLogger(__name__)

# Map aso-mcp popularity (0–100) to KeywordReality.search_volume
_POPULARITY_TO_VOLUME = 1_000  # linear scale: popularity 100 = 100,000 vol

# Map aso-mcp difficultyScore (0–100) to KeywordReality.competition (0–1)
_DIFFICULTY_TO_COMPETITION = 100.0


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Module-level helpers (shared with tests)
# --------------------------------------------------------------------------- #

def enrich_reality(reality: KeywordReality, metric) -> None:
    """Update a KeywordReality in-place with an aso-mcp KeywordMetric.

    Only fills fields that are currently empty/unset; preserves any data the
    caller has already sourced from the store.
    """
    popularity = int(getattr(metric, "popularity", 0) or 0)
    difficulty = float(getattr(metric, "difficulty_score", 0.0)
                       or getattr(metric, "difficultyScore", 0.0) or 0.0)

    # search_volume — only overwrite if empty
    if reality.search_volume <= 0 and popularity > 0:
        reality.search_volume = popularity * _POPULARITY_TO_VOLUME

    # competition (0–1)
    if reality.competition in (0, 0.5) and difficulty > 0:
        reality.competition = round(difficulty / _DIFFICULTY_TO_COMPETITION, 4)

    # category classification
    if getattr(metric, "is_brand_keyword", False) and not reality.category:
        reality.category = "brand"


def build_new_reality(metric, *, country: str, date: str) -> KeywordReality:
    """Create a new KeywordReality from a researcher KeywordMetric."""
    popularity = int(getattr(metric, "popularity", 0) or 0)
    difficulty = float(
        getattr(metric, "difficulty_score", 0.0)
        or getattr(metric, "difficultyScore", 0.0)
        or 0.0
    )
    category = "brand" if getattr(metric, "is_brand_keyword", False) else ""

    return KeywordReality(
        keyword=metric.keyword,
        country=country,
        category=category,
        search_volume=popularity * _POPULARITY_TO_VOLUME if popularity > 0 else 0,
        competition=(
            round(difficulty / _DIFFICULTY_TO_COMPETITION, 4)
            if difficulty > 0
            else 0.5
        ),
        date=date,
    )


# --------------------------------------------------------------------------- #
# Agent class
# --------------------------------------------------------------------------- #

class ASOKeywordAgent:
    """Keyword intelligence agent — the "keyword growth strategist".

    Typical usage:

        agent = ASOKeywordAgent.build(store)
        report = agent.run(
            game_id="merge_witch",
            realities=[...keyword performance data...],
            competitor_keywords={...},
        )
        print(report.to_markdown())

    aso-mcp integration:

        from src.market_ops.workspace.aso_keyword_researcher import (
            ASOKeywordResearcher,
        )
        agent = ASOKeywordAgent.build(store)
        agent.set_keyword_researcher(ASOKeywordResearcher())
        # collect_reality will now enrich with ASA data
    """

    def __init__(
        self,
        scoring: Optional[KeywordValueScoringEngine] = None,
        portfolio: Optional[KeywordPortfolioManager] = None,
        opportunity: Optional[KeywordOpportunityEngine] = None,
        store: Optional[ASOExperimentStore] = None,
        keyword_researcher=None,
        default_country: str = "US",
        enrich_with_asa: bool = True,
    ):
        self.scoring = scoring or KeywordValueScoringEngine()
        self.portfolio = portfolio or KeywordPortfolioManager()
        self.opportunity = opportunity or KeywordOpportunityEngine()
        self.store = store
        self._keyword_researcher = keyword_researcher
        self._default_country = default_country
        self._enrich_with_asa = enrich_with_asa

    @classmethod
    def build(
        cls, store: Optional[ASOExperimentStore] = None
    ) -> "ASOKeywordAgent":
        return cls(store=store)

    # ------------------------------------------------------------------ #
    # aso-mcp integration helpers
    # ------------------------------------------------------------------ #
    def set_keyword_researcher(self, researcher) -> None:
        """Inject the Apple Search Ads keyword researcher (aso-mcp bridge)."""
        self._keyword_researcher = researcher

    def has_keyword_researcher(self) -> bool:
        return self._keyword_researcher is not None

    def _get_researcher(self):
        """Lazy-load ASOKeywordResearcher when available but not injected.

        Ensures graceful degradation: when aso-mcp is not installed the
        import may succeed but check_status() will later report "not ready".
        """
        if self._keyword_researcher is not None:
            return self._keyword_researcher
        try:
            from src.market_ops.workspace.aso_keyword_researcher import (
                get_aso_keyword_researcher,
            )

            researcher = get_aso_keyword_researcher()
            status = researcher.check_status()
            if status["status"] == "ready":
                self._keyword_researcher = researcher
                return researcher
        except Exception as exc:
            logger.debug("aso keyword researcher not available: %s", exc)
        return None

    # ------------------------------------------------------------------ #
    def collect_reality(
        self, realities: List[KeywordReality]
    ) -> List[KeywordReality]:
        """Step 1: Collect + enrich keyword reality data.

        **With aso-mcp integration (default when available):**

            For every incoming keyword reality we look up the Apple Search Ads
            popularity/difficulty/brand flag and update:

              - search_volume  ← popularity × _POPULARITY_TO_VOLUME
              - competition    ← difficultyScore / _DIFFICULTY_TO_COMPETITION
              - category       ← "brand" (from isBrandKeyword) or keep existing

            Additionally, any **new** keywords discovered by the researcher that
            are not already in the input list are appended at the end as new
            KeywordReality entries, so downstream scoring finds them.

        **Without aso-mcp (aso-mcp not installed/not authenticated):**

            Pure pass-through (identical behaviour to the previous
            implementation). No keyword is lost.
        """
        if not realities:
            return realities

        if not self._enrich_with_asa:
            return realities

        researcher = self._get_researcher()
        if researcher is None:
            return realities

        reality_by_keyword: Dict[str, KeywordReality] = {}
        for r in realities:
            reality_by_keyword.setdefault(r.keyword, r)

        keywords_to_research = list(reality_by_keyword.keys())
        if not keywords_to_research:
            return realities

        try:
            research_result = researcher.research_keywords(keywords_to_research)
        except Exception as exc:
            logger.warning(
                "ASOKeywordAgent research call failed, falling back to original realities: %s",
                exc,
                exc_info=True,
            )
            return realities

        if not research_result.success:
            logger.info(
                "ASOKeywordAgent researcher returned error, skipping enrichment: %s",
                research_result.error,
            )
            return realities

        for metric in research_result.items:
            reality = reality_by_keyword.get(metric.keyword)
            if reality is not None:
                enrich_reality(reality, metric)

        enriched_list: List[KeywordReality] = list(realities)
        existing_keywords = set(reality_by_keyword.keys())
        country_default = (
            realities[0].country if realities else self._default_country
        )
        date_default = realities[0].date if realities else _today_iso()

        for metric in research_result.items:
            if metric.keyword in existing_keywords:
                continue
            new_reality = build_new_reality(
                metric,
                country=country_default,
                date=date_default,
            )
            enriched_list.append(new_reality)

        return enriched_list

    # ------------------------------------------------------------------ #
    def score_keywords(
        self, realities: List[KeywordReality]
    ) -> List[KeywordValueScore]:
        """Step 2: Score all keywords."""
        scores = [self.scoring.compute(r) for r in realities]
        return self.scoring.rank(scores)

    # ------------------------------------------------------------------ #
    def classify_portfolio(
        self,
        scores: List[KeywordValueScore],
        realities: Dict[str, KeywordReality],
    ) -> List[KeywordPortfolioEntry]:
        """Step 3: Build keyword portfolio."""
        return self.portfolio.build_portfolio(scores, realities)

    # ------------------------------------------------------------------ #
    def find_opportunities(
        self,
        scores: List[KeywordValueScore],
        portfolio: List[KeywordPortfolioEntry],
        competitor_keywords: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[KeywordOpportunity]:
        """Step 4: Find keyword opportunities."""
        return self.opportunity.analyze_all(
            scores, portfolio, competitor_keywords
        )

    # ------------------------------------------------------------------ #
    def learn_from_experiment(
        self,
        category: str,
        keyword: str,
        cvr_uplift: float,
        ltv_uplift: float,
    ) -> Optional[KeywordPattern]:
        """Step 5 (optional): Learn a keyword pattern from an experiment.

        Writes to E16.6.4 store if available.
        """
        tokens = [t.lower() for t in keyword.split()
                  if len(t) > 2]
        if not tokens:
            return None

        pattern = KeywordPattern(
            category=category,
            keyword_tokens=tokens,
            avg_cvr_uplift=cvr_uplift,
            avg_ltv_uplift=ltv_uplift,
            sample_size=1,
            confidence=min(1.0, max(0.0, (cvr_uplift + ltv_uplift) / 0.5)),
            pattern_id=f"{category}:{'|'.join(tokens)}",
        )

        if self.store:
            from src.aso_intelligence.experiment_memory.experiment_models import (
                ASOPattern,
            )
            store_pattern = ASOPattern(
                category=category,
                condition=f"keyword:{keyword}",
                action="ADD_KEYWORD",
                result=(
                    f"CVR +{cvr_uplift:.1%}, LTV +{ltv_uplift:.1%} "
                    f"(keyword pattern)"
                ),
                confidence=pattern.confidence,
                sample_size=1,
                success_rate=1.0,
                reward=cvr_uplift * ltv_uplift,
                pattern_id=pattern.pattern_id,
            )
            self.store.record_pattern(store_pattern)

        return pattern

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        realities: List[KeywordReality],
        competitor_keywords: Optional[Dict[str, Dict[str, Any]]] = None,
        experiment_keyword: str = "",
        experiment_cvr_uplift: float = 0.0,
        experiment_ltv_uplift: float = 0.0,
    ) -> ASOKeywordReport:
        """Run the full keyword intelligence pipeline.

        1. Collect reality data
        2. Score all keywords
        3. Classify into portfolio
        4. Find opportunities
        5. (Optional) Learn from experiment
        6. Generate report
        """
        realities = self.collect_reality(realities)
        scores = self.score_keywords(realities)

        reality_map: Dict[str, KeywordReality] = {
            r.keyword: r for r in realities
        }

        portfolio = self.classify_portfolio(scores, reality_map)
        opportunities = self.find_opportunities(
            scores, portfolio, competitor_keywords
        )

        patterns: List[KeywordPattern] = []
        if experiment_keyword and experiment_cvr_uplift:
            pattern = self.learn_from_experiment(
                category=game_id.split("_")[0] if "_" in game_id else "unknown",
                keyword=experiment_keyword,
                cvr_uplift=experiment_cvr_uplift,
                ltv_uplift=experiment_ltv_uplift,
            )
            if pattern:
                patterns.append(pattern)

        report = ASOKeywordReport(
            game_id=game_id,
            date=_today_iso(),
            keyword_scores=scores,
            portfolio=portfolio,
            opportunities=opportunities,
            patterns=patterns,
        )
        return report


__all__ = [
    "ASOKeywordAgent",
    "enrich_reality",
    "build_new_reality",
]
