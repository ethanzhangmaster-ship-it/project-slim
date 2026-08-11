"""
E16.6.9 — ASO Localization Agent: data models.

Transforms a single game into market-specific versions that local players
are more likely to download and pay for. This is NOT machine translation
— it's cultural re-expression.

Key concepts:
  * ``MarketProfile`` — what motivates players in each country
  * ``LocalizedKeyword`` — market-specific keyword targeting
  * ``LocalizedCreativeBrief`` — country-specific visual direction
  * ``LocalizationScore`` — Language × Keyword Fit × Cultural Fit × Revenue
  * ``LocalizationReport`` — daily output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Market profile — player behavior in each country
# --------------------------------------------------------------------------- #
@dataclass
class MarketProfile:
    """Cultural profile for a single market.

    ``motivation`` — primary player drive (achievement / collection / progression / social)
    ``preferred_words`` — keywords that resonate positively
    ``avoided_words`` — keywords that turn players off
    ``monetization_traits`` — how this market pays (e.g. "high_iap", "reward_ad_heavy")
    ``tone`` — communication style (exciting / emotional / professional / playful)
    """

    country: str
    language: str
    motivation: str = "achievement"
    preferred_words: List[str] = field(default_factory=list)
    avoided_words: List[str] = field(default_factory=list)
    monetization_traits: List[str] = field(default_factory=list)
    tone: str = "exciting"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "language": self.language,
            "motivation": self.motivation,
            "preferred_words": self.preferred_words,
            "avoided_words": self.avoided_words,
            "monetization_traits": self.monetization_traits,
            "tone": self.tone,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MarketProfile":
        return cls(
            country=d.get("country", ""),
            language=d.get("language", ""),
            motivation=d.get("motivation", "achievement"),
            preferred_words=list(d.get("preferred_words", [])),
            avoided_words=list(d.get("avoided_words", [])),
            monetization_traits=list(d.get("monetization_traits", [])),
            tone=d.get("tone", "exciting"),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 2. Localized keyword
# --------------------------------------------------------------------------- #
@dataclass
class LocalizedKeyword:
    """A keyword adapted for a specific market."""

    original_keyword: str
    market: str
    translated_keyword: str
    search_volume: int = 0
    difficulty: float = 0.5
    revenue_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_keyword": self.original_keyword,
            "market": self.market,
            "translated_keyword": self.translated_keyword,
            "search_volume": self.search_volume,
            "difficulty": round(self.difficulty, 4),
            "revenue_score": round(self.revenue_score, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LocalizedKeyword":
        return cls(
            original_keyword=d.get("original_keyword", ""),
            market=d.get("market", ""),
            translated_keyword=d.get("translated_keyword", ""),
            search_volume=int(d.get("search_volume", 0)),
            difficulty=float(d.get("difficulty", 0.5)),
            revenue_score=float(d.get("revenue_score", 0.0)),
        )


# --------------------------------------------------------------------------- #
# 3. Localized creative brief
# --------------------------------------------------------------------------- #
@dataclass
class LocalizedCreativeBrief:
    """Creative direction adapted for a specific market."""

    country: str
    visual_direction: str = ""
    copy_style: str = ""
    emotional_trigger: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country": self.country,
            "visual_direction": self.visual_direction,
            "copy_style": self.copy_style,
            "emotional_trigger": self.emotional_trigger,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LocalizedCreativeBrief":
        return cls(
            country=d.get("country", ""),
            visual_direction=d.get("visual_direction", ""),
            copy_style=d.get("copy_style", ""),
            emotional_trigger=d.get("emotional_trigger", ""),
            notes=d.get("notes", ""),
        )


# --------------------------------------------------------------------------- #
# 4. Localization quality score
# --------------------------------------------------------------------------- #
@dataclass
class LocalizationScore:
    """Overall quality of a localisation effort.

    ``score = language_quality × keyword_fit × cultural_fit × revenue_history``
    """

    language_quality: float = 1.0
    keyword_fit: float = 1.0
    cultural_fit: float = 1.0
    revenue_history: float = 1.0  # from E16.6.6 — high LTV markets get a boost

    def compute(self) -> float:
        return round(
            self.language_quality * self.keyword_fit * self.cultural_fit * self.revenue_history,
            4,
        )

    def is_high_quality(self, threshold: float = 0.7) -> bool:
        return self.compute() >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language_quality": round(self.language_quality, 4),
            "keyword_fit": round(self.keyword_fit, 4),
            "cultural_fit": round(self.cultural_fit, 4),
            "revenue_history": round(self.revenue_history, 4),
            "score": self.compute(),
        }


# --------------------------------------------------------------------------- #
# 5. Localization report
# --------------------------------------------------------------------------- #
@dataclass
class LocalizationReport:
    """Daily ASO localisation report for one game × one market."""

    game_id: str
    country: str
    date: str
    market_profile: Optional[MarketProfile] = None
    localized_keywords: List[LocalizedKeyword] = field(default_factory=list)
    localized_title: str = ""
    localized_short_desc: str = ""
    localized_full_desc: str = ""
    creative_brief: Optional[LocalizedCreativeBrief] = None
    score: Optional[LocalizationScore] = None
    patterns_learned: int = 0
    opportunities_found: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Localization Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Market:** {self.country}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"")

        if self.market_profile:
            mp = self.market_profile
            lines.append(f"## Market Profile: {self.country}")
            lines.append(f"- **Language:** {mp.language}")
            lines.append(f"- **Motivation:** {mp.motivation}")
            lines.append(f"- **Tone:** {mp.tone}")
            lines.append(f"- **Preferred Words:** {', '.join(mp.preferred_words[:5])}")
            lines.append(f"")

        if self.score:
            lines.append(f"## Localization Score")
            lines.append(f"- **Overall:** {self.score.compute():.2f}")
            lines.append(f"- **Language Quality:** {self.score.language_quality:.2f}")
            lines.append(f"- **Keyword Fit:** {self.score.keyword_fit:.2f}")
            lines.append(f"- **Cultural Fit:** {self.score.cultural_fit:.2f}")
            lines.append(f"- **Revenue History:** {self.score.revenue_history:.2f}")
            lines.append(f"")

        if self.localized_keywords:
            lines.append(f"## Localized Keywords")
            for kw in self.localized_keywords:
                lines.append(
                    f"- **{kw.original_keyword}** → {kw.translated_keyword} "
                    f"(vol:{kw.search_volume}, score:{kw.revenue_score:.1f})"
                )
            lines.append(f"")

        lines.append(f"## Store Copy")
        lines.append(f"- **Title:** {self.localized_title}")
        lines.append(f"- **Short Description:** {self.localized_short_desc[:80]}...")
        if self.localized_full_desc:
            lines.append(f"- **Full Description:** {self.localized_full_desc[:100]}...")
        lines.append(f"")

        if self.creative_brief:
            cb = self.creative_brief
            lines.append(f"## Creative Direction")
            lines.append(f"- **Visual:** {cb.visual_direction}")
            lines.append(f"- **Copy Style:** {cb.copy_style}")
            lines.append(f"- **Emotional Trigger:** {cb.emotional_trigger}")

        if self.patterns_learned:
            lines.append(f"\n**Patterns learned:** {self.patterns_learned}")
        if self.opportunities_found:
            lines.append(f"**Opportunities found:** {self.opportunities_found}")

        return "\n".join(lines)


__all__ = [
    "MarketProfile",
    "LocalizedKeyword",
    "LocalizedCreativeBrief",
    "LocalizationScore",
    "LocalizationReport",
]
