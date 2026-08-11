"""
E16.6.8 — ASO Creative Generator: data models.

Bridges ASO Intelligence (E16.6.1–7) with creative generation (E11).
Transforms "screenshot weak" → structured creative brief → generated
candidate → vision-scored → experiment-ready.

Key concepts:
  * ``ASOCreativeBrief`` — structured creative requirement from ASO insight
  * ``ASOCreativeGenome`` — creative DNA for store assets (hook/composition/text/emotion)
  * ``CreativeScore`` — multi-dimension evaluation (vision + compliance + pattern + revenue)
  * ``CreativeCandidate`` — one generated asset with scores
  * ``ASOCreativeReport`` — daily output with ranking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# 1. Asset types for store creative
# --------------------------------------------------------------------------- #
class StoreAssetType(str, Enum):
    """Types of store creative that can be generated."""
    ICON = "ICON"
    SCREENSHOT = "SCREENSHOT"
    FEATURE_GRAPHIC = "FEATURE_GRAPHIC"
    PREVIEW_VIDEO = "PREVIEW_VIDEO"


class BriefObjective(str, Enum):
    """What the creative aims to improve."""
    INCREASE_CVR = "INCREASE_CVR"
    IMPROVE_FIRST_IMPRESSION = "IMPROVE_FIRST_IMPRESSION"
    CLARIFY_GAMEPLAY = "CLARIFY_GAMEPLAY"
    SHOW_REWARD = "SHOW_REWARD"
    BUILD_BRAND = "BUILD_BRAND"
    TARGET_KEYWORD = "TARGET_KEYWORD"


# --------------------------------------------------------------------------- #
# 2. Creative brief
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeBrief:
    """Structured creative requirement derived from an ASO insight."""

    game_id: str
    asset_type: StoreAssetType
    objective: BriefObjective
    audience: str = ""
    country: str = ""
    key_message: str = ""
    visual_direction: str = ""
    source_insight: str = ""  # e.g. "screenshot_clarity_weak" or "cvr_drop"
    source_data: Dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "objective": self.objective.value,
            "audience": self.audience,
            "country": self.country,
            "key_message": self.key_message,
            "visual_direction": self.visual_direction,
            "source_insight": self.source_insight,
            "source_data": self.source_data,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOCreativeBrief":
        return cls(
            game_id=d.get("game_id", ""),
            asset_type=StoreAssetType(d.get("asset_type", "SCREENSHOT")),
            objective=BriefObjective(d.get("objective", "INCREASE_CVR")),
            audience=d.get("audience", ""),
            country=d.get("country", ""),
            key_message=d.get("key_message", ""),
            visual_direction=d.get("visual_direction", ""),
            source_insight=d.get("source_insight", ""),
            source_data=d.get("source_data", {}),
            created_at=d.get("created_at", ""),
        )


# --------------------------------------------------------------------------- #
# 3. ASO Creative Genome (store-specific DNA)
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeGenome:
    """Creative DNA specifically adapted for store listing assets.

    Mirrors E11 CreativeDNA concepts but tuned for store conversion.
    """

    # Hook strategy
    hook_character: str = ""  # "hero_face" / "monster" / "none"
    hook_reward: str = ""     # "coins" / "gems" / "unlock" / "none"
    hook_transformation: str = ""  # "merge_before_after" / "upgrade" / "none"

    # Composition
    comp_focus: str = "centered"  # "centered" / "character_focused" / "scene"
    comp_hierarchy: str = "clear"  # "clear" / "cluttered"
    comp_contrast: str = "high"  # "high" / "medium" / "low"

    # Text
    text_headline: str = ""
    text_benefit: str = ""

    # Emotion
    emotion_curiosity: float = 0.0
    emotion_achievement: float = 0.0
    emotion_collection: float = 0.0

    # Meta
    category: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_character": self.hook_character,
            "hook_reward": self.hook_reward,
            "hook_transformation": self.hook_transformation,
            "comp_focus": self.comp_focus,
            "comp_hierarchy": self.comp_hierarchy,
            "comp_contrast": self.comp_contrast,
            "text_headline": self.text_headline,
            "text_benefit": self.text_benefit,
            "emotion_curiosity": round(self.emotion_curiosity, 4),
            "emotion_achievement": round(self.emotion_achievement, 4),
            "emotion_collection": round(self.emotion_collection, 4),
            "category": self.category,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOCreativeGenome":
        return cls(
            hook_character=d.get("hook_character", ""),
            hook_reward=d.get("hook_reward", ""),
            hook_transformation=d.get("hook_transformation", ""),
            comp_focus=d.get("comp_focus", "centered"),
            comp_hierarchy=d.get("comp_hierarchy", "clear"),
            comp_contrast=d.get("comp_contrast", "high"),
            text_headline=d.get("text_headline", ""),
            text_benefit=d.get("text_benefit", ""),
            emotion_curiosity=float(d.get("emotion_curiosity", 0.0)),
            emotion_achievement=float(d.get("emotion_achievement", 0.0)),
            emotion_collection=float(d.get("emotion_collection", 0.0)),
            category=d.get("category", ""),
            created_at=d.get("created_at", ""),
        )

    @classmethod
    def merge_genome_default(cls, category: str = "merge_game") -> "ASOCreativeGenome":
        """Default genome for merge games (per spec: character focus + before/after + coins)."""
        if "merge" in category:
            return cls(
                hook_character="hero_face",
                hook_reward="coins",
                hook_transformation="merge_before_after",
                comp_focus="character_focused",
                comp_hierarchy="clear",
                comp_contrast="high",
                text_headline="Merge & Evolve!",
                text_benefit="Discover epic upgrades",
                emotion_curiosity=0.7,
                emotion_achievement=0.8,
                emotion_collection=0.6,
                category=category,
            )
        # Default generic
        return cls(
            hook_character="none",
            hook_reward="none",
            hook_transformation="none",
            category=category,
        )


# --------------------------------------------------------------------------- #
# 4. Creative score (multi-dimension evaluation)
# --------------------------------------------------------------------------- #
@dataclass
class CreativeScore:
    """Full evaluation of one creative candidate.

    ``final_score = hook_weight × hook_score + clarity_weight × clarity_score
        + emotional_weight × emotional_score + brand_weight × brand_score
        - compliance_penalty``

    ``store_compliance`` defaults to 1.0 (pass). Penalised for misleading claims,
    excessive marketing language, or suspected policy violations.
    """

    hook_score: float = 0.0
    clarity_score: float = 0.0
    emotional_score: float = 0.0
    brand_score: float = 0.0
    conversion_prediction: float = 0.0  # estimated CVR uplift
    store_compliance: float = 1.0  # 0–1, 1 = fully compliant

    # Weights
    hook_weight: float = 0.30
    clarity_weight: float = 0.30
    emotional_weight: float = 0.20
    brand_weight: float = 0.20

    # Historical pattern boost (set externally by ranking engine)
    pattern_boost: float = 1.0
    revenue_quality: float = 1.0  # from E16.6.6 revenue feedback

    def compute_final(self) -> float:
        """Final = weighted vision - compliance penalty, then * pattern * revenue."""
        base = (
            self.hook_weight * self.hook_score
            + self.clarity_weight * self.clarity_score
            + self.emotional_weight * self.emotional_score
            + self.brand_weight * self.brand_score
        )
        compliance_factor = max(0.0, self.store_compliance)
        final = base * compliance_factor * self.pattern_boost * self.revenue_quality
        return round(final, 4)

    def is_high_quality(self, threshold: float = 0.7) -> bool:
        return self.compute_final() >= threshold

    def has_compliance_risk(self) -> bool:
        return self.store_compliance < 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_score": round(self.hook_score, 4),
            "clarity_score": round(self.clarity_score, 4),
            "emotional_score": round(self.emotional_score, 4),
            "brand_score": round(self.brand_score, 4),
            "conversion_prediction": round(self.conversion_prediction, 4),
            "store_compliance": round(self.store_compliance, 4),
            "pattern_boost": round(self.pattern_boost, 4),
            "revenue_quality": round(self.revenue_quality, 4),
            "final_score": self.compute_final(),
        }


# --------------------------------------------------------------------------- #
# 5. One creative candidate
# --------------------------------------------------------------------------- #
@dataclass
class CreativeCandidate:
    """One generated store asset with full evaluation."""

    candidate_id: str
    game_id: str
    asset_type: StoreAssetType
    variant_label: str  # e.g. "Variant A", "Variant #7"
    prompt_used: str = ""
    genome: Optional[ASOCreativeGenome] = None
    score: Optional[CreativeScore] = None
    source: str = "generated"  # "generated" or "dryrun"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "variant_label": self.variant_label,
            "prompt_used": self.prompt_used,
            "genome": self.genome.to_dict() if self.genome else None,
            "score": self.score.to_dict() if self.score else None,
            "source": self.source,
            "created_at": self.created_at,
        }


# --------------------------------------------------------------------------- #
# 6. Daily ASO creative report
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeReport:
    """Output of the creative generator agent's daily run."""

    game_id: str
    date: str
    brief: Optional[ASOCreativeBrief] = None
    candidates: List[CreativeCandidate] = field(default_factory=list)
    top_candidate: Optional[CreativeCandidate] = None
    experiments_created: int = 0
    patterns_learned: int = 0
    created_at: str = field(default_factory=_now_iso)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# ASO Creative Report")
        lines.append(f"")
        lines.append(f"**Game:** {self.game_id}")
        lines.append(f"**Date:** {self.date}")
        lines.append(f"")

        if self.brief:
            lines.append(f"## Creative Brief")
            lines.append(f"")
            lines.append(f"- **Asset Type:** {self.brief.asset_type.value}")
            lines.append(f"- **Objective:** {self.brief.objective.value}")
            lines.append(f"- **Key Message:** {self.brief.key_message}")
            lines.append(f"- **Visual Direction:** {self.brief.visual_direction}")
            lines.append(f"- **Source:** {self.brief.source_insight}")
            lines.append(f"")

        lines.append(f"## Generated Candidates ({len(self.candidates)})")
        if self.top_candidate:
            tc = self.top_candidate
            lines.append(f"")
            lines.append(f"### Top Candidate: {tc.variant_label}")
            lines.append(f"")
            if tc.score:
                fs = tc.score.compute_final()
                lines.append(f"- **Final Score:** {fs:.2f}")
                lines.append(f"- **Hook:** {tc.score.hook_score:.2f}")
                lines.append(f"- **Clarity:** {tc.score.clarity_score:.2f}")
                lines.append(f"- **Emotion:** {tc.score.emotional_score:.2f}")
                lines.append(f"- **Store Compliance:** {tc.score.store_compliance:.2f}")
            if tc.genome:
                lines.append(f"- **Genome:** character={tc.genome.hook_character}, "
                             f"reward={tc.genome.hook_reward}")
            lines.append(f"- **Status:** Ready for experiment")
            lines.append(f"")

        if self.experiments_created > 0:
            lines.append(f"**Experiments created:** {self.experiments_created}")
        if self.patterns_learned > 0:
            lines.append(f"**Patterns learned:** {self.patterns_learned}")

        return "\n".join(lines)


__all__ = [
    "StoreAssetType",
    "BriefObjective",
    "ASOCreativeBrief",
    "ASOCreativeGenome",
    "CreativeScore",
    "CreativeCandidate",
    "ASOCreativeReport",
]
