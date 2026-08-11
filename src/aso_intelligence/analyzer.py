"""
E16.6.1 — ASO Analyzers: the five Intelligence modules (deterministic).

Pure functions / stateless analyzers. No I/O, no randomness, no LLM. Each
analyzer turns ASO reality into a list of ``ASOInsight`` objects. The agent
(``agent.py``) aggregates and routes them.

Modules:
  * ``KeywordAnalyzer``     — intent coverage + review-term mining
  * ``ConversionAnalyzer`` — CVR drop detection (listing fatigue signal)
  * ``ListingAnalyzer``    — screenshot hook/clarity + icon focal strength
  * ``CompetitorAnalyzer`` — competitor surge / creative change detection

Every rule is explicit and threshold-driven so behavior is fully testable and
auditable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    ASOInsight,
    ASOInsightType,
    ASOSnapshot,
    CompetitorSnapshot,
)

# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
_STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "it", "this", "that", "i", "you", "we", "they",
    "my", "me", "so", "very", "really", "just", "too", "at", "be", "as", "by",
    "game", "games", "play", "playing", "played", "app", "apps", "free",
    "love", "good", "great", "fun", "nice", "best", "awesome", "amazing",
    "nice", "cool", "wow", "yes", "no", "not", "don't", "dont", "can", "will",
    "would", "could", "should", "have", "has", "had", "get", "got", "all",
    "out", "up", "down", "more", "much", "than", "then", "them", "their",
    "here", "there", "when", "what", "who", "how", "because", "from", "about",
    "into", "your", "our", "been", "some", "such", "only", "also", "still",
}


def _tokenize(text: str) -> List[str]:
    return [t.strip().lower() for t in text.replace(",", " ").replace(".", " ").split() if t.strip()]


def _covered_terms(snapshot: ASOSnapshot) -> Set[str]:
    """All listing terms (title + description + keywords) as a token set."""
    terms: Set[str] = set()
    terms.update(snapshot.title_tokens())
    terms.update(snapshot.description_tokens())
    terms.update(t.strip().lower() for t in snapshot.keywords)
    return terms


# --------------------------------------------------------------------------- #
# 1. Keyword Intelligence
# --------------------------------------------------------------------------- #
class KeywordAnalyzer:
    """Intent-coverage gaps + review-term mining.

    Two deterministic detectors:

    * ``analyze_intent_coverage`` — for each *planned intent* keyword not
      present in the listing → ``MISSING_KEYWORD``.
    * ``analyze_review_terms`` — mine frequent review terms not in the listing
      → ``REVIEW_KEYWORD_SIGNAL``. When a term is BOTH an intent gap and
      review-frequent it is promoted to ``KEYWORD_OPPORTUNITY`` (highest value).
    """

    def analyze(
        self,
        snapshot: ASOSnapshot,
        intent_keywords: List[str],
        reviews: Optional[List[str]] = None,
        review_min_count: int = 5,
    ) -> List[ASOInsight]:
        insights: List[ASOInsight] = []
        covered = _covered_terms(snapshot)
        intent_set = {k.strip().lower() for k in intent_keywords if k.strip()}

        # --- review-term frequency ---
        review_terms: Dict[str, int] = {}
        if reviews:
            for r in reviews:
                for tok in _tokenize(r):
                    if tok in _STOPWORDS or len(tok) < 3:
                        continue
                    review_terms[tok] = review_terms.get(tok, 0) + 1

        # --- classify each intent keyword ---
        for kw in sorted(intent_set):
            is_missing = kw not in covered
            is_review = review_terms.get(kw, 0) >= review_min_count
            if not is_missing:
                continue
            if is_review:
                insights.append(
                    self._insight(
                        snapshot,
                        ASOInsightType.KEYWORD_OPPORTUNITY,
                        keyword=kw,
                        confidence=0.9,
                        impact=70.0,
                        review_count=review_terms[kw],
                        note="intent gap + strong player language",
                    )
                )
            else:
                insights.append(
                    self._insight(
                        snapshot,
                        ASOInsightType.MISSING_KEYWORD,
                        keyword=kw,
                        confidence=0.8,
                        impact=55.0,
                        note="planned intent keyword not in listing",
                    )
                )

        # --- review terms not in intent set, not covered -> signal ---
        for term, cnt in sorted(
            review_terms.items(), key=lambda kv: kv[1], reverse=True
        ):
            if term in intent_set:
                continue  # already handled above
            if term in covered:
                continue
            if cnt < review_min_count:
                continue
            insights.append(
                self._insight(
                    snapshot,
                    ASOInsightType.REVIEW_KEYWORD_SIGNAL,
                    keyword=term,
                    confidence=round(min(0.9, 0.5 + 0.03 * cnt), 4),
                    impact=60.0,
                    review_count=cnt,
                    note="player language absent from listing",
                )
            )
        return insights

    # ------------------------------------------------------------------ #
    @staticmethod
    def _insight(
        snapshot: ASOSnapshot,
        itype: ASOInsightType,
        *,
        keyword: str,
        confidence: float,
        impact: float,
        review_count: int = 0,
        note: str = "",
    ) -> ASOInsight:
        verbs = {
            ASOInsightType.MISSING_KEYWORD: "Add the missing keyword",
            ASOInsightType.KEYWORD_OPPORTUNITY: "Add the high-value keyword",
            ASOInsightType.REVIEW_KEYWORD_SIGNAL: "Add the player-language keyword",
        }
        return ASOInsight(
            game_id=snapshot.game_id,
            insight_type=itype,
            description=f"'{keyword}' is not represented in the store listing.",
            recommendation=f"{verbs.get(itype, 'Add keyword')} '{keyword}' to title/keywords.",
            evidence={
                "keyword": keyword,
                "review_count": review_count,
                "note": note,
                "current_keywords": list(snapshot.keywords),
            },
            confidence=confidence,
            impact_score=impact,
        )


# --------------------------------------------------------------------------- #
# 2. Conversion Intelligence
# --------------------------------------------------------------------------- #
class ConversionAnalyzer:
    """CVR drop detection → listing fatigue signal.

    CVR = installs / store_visits. If CVR drops materially versus the previous
    period while store rating & category ranking stay healthy, the listing
    creative is the most likely culprit (fatigue) → recommend a screenshot
    refresh.
    """

    def __init__(
        self,
        strong_drop: float = 0.15,  # >15% drop -> CONVERSION_DROP
        mild_drop: float = 0.08,  # 8–15% drop -> FATIGUE
        healthy_rating: float = 4.0,
        ranking_slip_tolerance: int = 20,  # rank may worsen by this much
    ):
        self.strong_drop = strong_drop
        self.mild_drop = mild_drop
        self.healthy_rating = healthy_rating
        self.ranking_slip_tolerance = ranking_slip_tolerance

    def analyze(
        self, current: ASOSnapshot, previous: Optional[ASOSnapshot]
    ) -> List[ASOInsight]:
        if previous is None:
            return []
        cvr_cur = current.cvr()
        cvr_prev = previous.cvr()
        if cvr_prev <= 0:
            return []

        drop = (cvr_prev - cvr_cur) / cvr_prev
        if drop <= self.mild_drop:
            return []  # healthy

        rating_ok = current.rating >= self.healthy_rating
        ranking_ok = self._ranking_ok(current, previous)
        if not (rating_ok and ranking_ok):
            # CVR fell but store health also deteriorated -> not a listing
            # fatigue problem (likely a rating/review issue) -> no ASO insight.
            return []

        if drop > self.strong_drop:
            itype = ASOInsightType.LISTING_CONVERSION_DROP
            confidence = round(min(0.95, 0.7 + drop), 4)
            impact = 80.0
            rec = "Refresh store screenshots (hook + gameplay clarity)."
        else:
            itype = ASOInsightType.LISTING_FATIGUE
            confidence = round(min(0.8, 0.55 + drop), 4)
            impact = 55.0
            rec = "Monitor listing fatigue; plan a screenshot update."

        return [
            ASOInsight(
                game_id=current.game_id,
                insight_type=itype,
                description=(
                    f"Store CVR fell {drop:.1%} "
                    f"({cvr_prev:.1%} → {cvr_cur:.1%}) while rating & ranking "
                    f"stayed healthy — listing creative fatigue."
                ),
                recommendation=rec,
                evidence={
                    "cvr_current": round(cvr_cur, 4),
                    "cvr_previous": round(cvr_prev, 4),
                    "cvr_drop_pct": round(drop, 4),
                    "rating": current.rating,
                    "ranking": current.ranking,
                    "ranking_previous": previous.ranking,
                },
                confidence=confidence,
                impact_score=impact,
            )
        ]

    @staticmethod
    def _ranking_ok(current: ASOSnapshot, previous: ASOSnapshot) -> bool:
        if current.ranking is None or previous.ranking is None:
            return True  # no ranking data -> don't block on it
        # ranking worsens when the number grows; tolerate a small slip
        return current.ranking <= previous.ranking + 20


# --------------------------------------------------------------------------- #
# 3. Listing Intelligence (screenshots + icon)
# --------------------------------------------------------------------------- #
class ListingAnalyzer:
    """Screenshot hook/clarity + icon focal-strength diagnostics.

    Reuses the E11 Creative DNA vocabulary (hook / gameplay_clarity /
    value_proposition / visual_density) carried on each ``ScreenshotFeature``.
    """

    def __init__(
        self,
        screenshot_hook_min: float = 0.5,
        screenshot_clarity_min: float = 0.5,
        icon_focal_min: float = 0.5,
    ):
        self.screenshot_hook_min = screenshot_hook_min
        self.screenshot_clarity_min = screenshot_clarity_min
        self.icon_focal_min = icon_focal_min

    def analyze(self, snapshot: ASOSnapshot) -> List[ASOInsight]:
        insights: List[ASOInsight] = []

        # --- screenshots ---
        worst: Optional[Tuple[float, Any]] = None
        for s in snapshot.screenshots:
            score = min(s.hook_strength, s.gameplay_clarity)
            if score < min(self.screenshot_hook_min, self.screenshot_clarity_min):
                if worst is None or score < worst[0]:
                    worst = (score, s)
        if worst is not None:
            s = worst[1]
            insights.append(
                ASOInsight(
                    game_id=snapshot.game_id,
                    insight_type=ASOInsightType.SCREENSHOT_WEAK,
                    description=(
                        f"Screenshot '{s.asset_id}' is weak "
                        f"(hook {s.hook_strength:.0%}, clarity "
                        f"{s.gameplay_clarity:.0%}) — fails to stop the scroll "
                        f"or show the core loop."
                    ),
                    recommendation=(
                        "Re-shoot the first 2–3 screenshots with a stronger "
                        "hook frame and clearer gameplay."
                    ),
                    evidence={
                        "asset_id": s.asset_id,
                        "hook_strength": round(s.hook_strength, 4),
                        "gameplay_clarity": round(s.gameplay_clarity, 4),
                        "value_proposition": round(s.value_proposition, 4),
                    },
                    confidence=round(min(0.9, 0.5 + 0.4 * (1 - worst[0])), 4),
                    impact_score=75.0,
                )
            )

        # --- icon ---
        focal = float(snapshot.icon.get("focal_strength", 1.0))
        face_area = float(snapshot.icon.get("face_area_ratio", 0.5))
        if focal < self.icon_focal_min:
            insights.append(
                ASOInsight(
                    game_id=snapshot.game_id,
                    insight_type=ASOInsightType.ICON_OPTIMIZATION,
                    description=(
                        f"Icon focal strength is weak ({focal:.0%}); character "
                        f"face area ratio {face_area:.0%}."
                    ),
                    recommendation=(
                        "Increase the main character's face/figure area and "
                        "reduce background noise to lift icon tap-through."
                    ),
                    evidence={
                        "focal_strength": round(focal, 4),
                        "face_area_ratio": round(face_area, 4),
                    },
                    confidence=round(min(0.85, 0.5 + 0.4 * (1 - focal)), 4),
                    impact_score=65.0,
                )
            )
        return insights


# --------------------------------------------------------------------------- #
# 4. Competitor Intelligence
# --------------------------------------------------------------------------- #
class CompetitorAnalyzer:
    """Competitor surge / creative change detection.

    A competitor is "changed" when it (a) jumped up the category chart by
    ``surge_threshold`` positions, or (b) swapped its icon / screenshots —
    both are signals to run a store experiment of our own.
    """

    def __init__(self, surge_threshold: int = 50):
        self.surge_threshold = surge_threshold

    def analyze(
        self,
        game_id: str,
        current: List[CompetitorSnapshot],
        previous: Optional[List[CompetitorSnapshot]] = None,
    ) -> List[ASOInsight]:
        prev_by_id = {c.competitor_id: c for c in (previous or [])}
        insights: List[ASOInsight] = []

        for c in current:
            reasons: List[str] = []

            # material change flags
            if c.icon_changed:
                reasons.append("icon refreshed")
            if c.screenshot_changed:
                reasons.append("screenshots refreshed")

            # ranking surge (lower rank number = higher position)
            prev = prev_by_id.get(c.competitor_id)
            rank_before = c.previous_ranking
            if rank_before is None and prev is not None:
                rank_before = prev.ranking
            if (
                c.ranking is not None
                and rank_before is not None
                and rank_before - c.ranking >= self.surge_threshold
            ):
                reasons.append(
                    f"rank surged +{rank_before - c.ranking} positions"
                )

            if not reasons:
                continue
            insights.append(
                ASOInsight(
                    game_id=game_id,
                    insight_type=ASOInsightType.COMPETITOR_CHANGE,
                    description=(
                        f"Competitor '{c.competitor_id}' changed: "
                        f"{'; '.join(reasons)}."
                    ),
                    recommendation=(
                        "Launch a controlled store experiment (icon / screenshot "
                        "/ title variant) to defend conversion."
                    ),
                    evidence={
                        "competitor_id": c.competitor_id,
                        "reasons": reasons,
                        "ranking": c.ranking,
                        "previous_ranking": rank_before,
                        "icon_changed": c.icon_changed,
                        "screenshot_changed": c.screenshot_changed,
                    },
                    confidence=0.82,
                    impact_score=60.0,
                )
            )
        return insights


__all__ = [
    "KeywordAnalyzer",
    "ConversionAnalyzer",
    "ListingAnalyzer",
    "CompetitorAnalyzer",
]
