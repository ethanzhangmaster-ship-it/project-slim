"""
E16.6.3 — ASO Creative DNA Builder.

Builds the categorical ``ASOCreativeDNA`` of a store asset, combining three
sources of truth (in priority order):

  1. explicit ``overrides`` (caller / human input)
  2. feature-derived signals (from the vision analyzer — character visibility,
     hook strength, reward visibility, gameplay clarity)
  3. genre ``category`` conventions (per-genre defaults)

It also aggregates a game's multiple asset DNAs into a single
``GameCreativeDNAProfile`` (icon = brand DNA, screenshots = aggregated DNA),
which the optimizer / pattern miner consume.

This is the bridge to E11 Creative Evolution Engine's "creative DNA" concept:
here the DNA is deterministic & categorical; a real E11 model would replace the
feature-derived step with learned embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.aso_intelligence.creative.models import (
    ASOCreativeDNA,
    AssetType,
    CreativeVisionFeature,
)
from src.aso_intelligence.creative.vision_analyzer import VisionResult


# Genre conventions: dominant_color / character_style / composition /
# message_type / emotional_trigger / gameplay_focus.
_CATEGORY_DEFAULTS: Dict[str, Dict[str, str]] = {
    "merge": {
        "dominant_color": "purple",
        "character_style": "cartoon_monster",
        "composition": "centered_focal",
        "message_type": "merge_progress",
        "emotional_trigger": "satisfaction",
        "gameplay_focus": "merge_two_objects",
    },
    "trivia": {
        "dominant_color": "blue",
        "character_style": "abstract",
        "composition": "centered_text",
        "message_type": "question_hook",
        "emotional_trigger": "curiosity",
        "gameplay_focus": "answer_question",
    },
    "cooking": {
        "dominant_color": "warm_orange",
        "character_style": "cartoon_chef",
        "composition": "centered_focal",
        "message_type": "cooking_moment",
        "emotional_trigger": "satisfaction",
        "gameplay_focus": "cook_dish",
    },
    "match3": {
        "dominant_color": "pink",
        "character_style": "abstract",
        "composition": "grid_focal",
        "message_type": "match_moment",
        "emotional_trigger": "satisfaction",
        "gameplay_focus": "match_three",
    },
    "rpg": {
        "dominant_color": "dark_blue",
        "character_style": "hero",
        "composition": "centered_focal",
        "message_type": "battle_moment",
        "emotional_trigger": "excitement",
        "gameplay_focus": "combat",
    },
    "hyper_casual": {
        "dominant_color": "bright_yellow",
        "character_style": "abstract",
        "composition": "scattered",
        "message_type": "action_moment",
        "emotional_trigger": "excitement",
        "gameplay_focus": "simple_action",
    },
}


def _empty_default() -> Dict[str, str]:
    return {
        "dominant_color": "unknown",
        "character_style": "unknown",
        "composition": "unknown",
        "message_type": "unknown",
        "emotional_trigger": "unknown",
        "gameplay_focus": "unknown",
    }


@dataclass
class GameCreativeDNAProfile:
    """A game-level aggregation of its assets' creative DNA."""

    game_id: str
    category: str
    icon_dna: Optional[ASOCreativeDNA] = None
    screenshot_dna: Optional[ASOCreativeDNA] = None
    avg_fitness: float = 0.0
    asset_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "category": self.category,
            "icon_dna": self.icon_dna.to_dict() if self.icon_dna else None,
            "screenshot_dna": self.screenshot_dna.to_dict()
            if self.screenshot_dna
            else None,
            "avg_fitness": round(self.avg_fitness, 4),
            "asset_count": self.asset_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameCreativeDNAProfile":
        return cls(
            game_id=d.get("game_id", ""),
            category=d.get("category", ""),
            icon_dna=ASOCreativeDNA.from_dict(d.get("icon_dna")),
            screenshot_dna=ASOCreativeDNA.from_dict(d.get("screenshot_dna")),
            avg_fitness=float(d.get("avg_fitness", 0.0)),
            asset_count=int(d.get("asset_count", 0)),
        )


class ASOCreativeDNABuilder:
    """Category-aware builder of ``ASOCreativeDNA``.

    Merge order for each DNA field: ``overrides`` → feature-derived →
    ``category`` default → ``unknown``.
    """

    def __init__(
        self, category_defaults: Optional[Dict[str, Dict[str, str]]] = None
    ):
        self._defaults = category_defaults or _CATEGORY_DEFAULTS

    # ------------------------------------------------------------------ #
    def _feature_derived(
        self, feature: CreativeVisionFeature
    ) -> Dict[str, str]:
        char = feature.character_visibility
        if char >= 0.6:
            character_style = "cartoon"
        elif char >= 0.3:
            character_style = "abstract"
        else:
            character_style = "unknown"

        is_strong_hook = feature.hook_score >= 0.6
        if is_strong_hook or char >= 0.5:
            composition = "centered_focal"
        else:
            composition = "scattered"

        if feature.gameplay_clarity >= 0.6:
            message_type = "gameplay_moment"
        else:
            message_type = "generic"

        if feature.reward_visibility >= 0.6:
            emotional_trigger = "satisfaction"
        elif feature.emotional_appeal >= 0.5:
            emotional_trigger = "curiosity"
        else:
            emotional_trigger = "unknown"

        return {
            "character_style": character_style,
            "composition": composition,
            "message_type": message_type,
            "emotional_trigger": emotional_trigger,
        }

    def build(
        self,
        asset_type: AssetType,
        feature: CreativeVisionFeature,
        *,
        category: Optional[str] = None,
        overrides: Optional[Dict[str, str]] = None,
    ) -> ASOCreativeDNA:
        default = dict(_empty_default())
        if category:
            cat = self._defaults.get(category)
            if cat:
                default.update(cat)

        derived = self._feature_derived(feature)
        overrides = overrides or {}

        def pick(field: str) -> str:
            if field in overrides and overrides[field]:
                return overrides[field]
            if field in derived and derived[field] != "unknown":
                return derived[field]
            return default.get(field, "unknown")

        return ASOCreativeDNA(
            asset_type=asset_type,
            dominant_color=pick("dominant_color"),
            character_style=pick("character_style"),
            composition=pick("composition"),
            message_type=pick("message_type"),
            emotional_trigger=pick("emotional_trigger"),
            gameplay_focus=pick("gameplay_focus"),
        )

    def build_from_result(
        self,
        result: VisionResult,
        *,
        category: Optional[str] = None,
        overrides: Optional[Dict[str, str]] = None,
    ) -> ASOCreativeDNA:
        return self.build(
            result.asset.asset_type,
            result.feature,
            category=category,
            overrides=overrides,
        )

    # ------------------------------------------------------------------ #
    def aggregate(
        self,
        game_id: str,
        category: str,
        results: List[VisionResult],
        *,
        overrides: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> GameCreativeDNAProfile:
        """Aggregate many asset VisionResults into one game-level profile.

        - ``icon_dna``     = DNA of the (first) ICON asset, if any.
        - ``screenshot_dna`` = DNA of the first SCREENSHOT asset, if any
          (screenshots share a visual language, so the lead one represents it).
        - ``avg_fitness``  = mean fitness across all assets.
        """
        overrides = overrides or {}
        icon_dna: Optional[ASOCreativeDNA] = None
        screenshot_dna: Optional[ASOCreativeDNA] = None
        total = 0.0
        count = 0

        for r in results:
            at = r.asset.asset_type
            ov = overrides.get(r.asset.url) or overrides.get(at.value)
            dna = self.build(
                at, r.feature, category=category, overrides=ov
            )
            if at == AssetType.ICON and icon_dna is None:
                icon_dna = dna
            elif at == AssetType.SCREENSHOT and screenshot_dna is None:
                screenshot_dna = dna
            total += r.feature.fitness()
            count += 1

        avg = round(total / count, 4) if count else 0.0
        return GameCreativeDNAProfile(
            game_id=game_id,
            category=category,
            icon_dna=icon_dna,
            screenshot_dna=screenshot_dna,
            avg_fitness=avg,
            asset_count=count,
        )


__all__ = [
    "ASOCreativeDNABuilder",
    "GameCreativeDNAProfile",
    "_CATEGORY_DEFAULTS",
]
