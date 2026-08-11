"""
E16.6.3 — ASO Creative Optimization: data models & integration seams.

The "store visual growth" layer of the ASO Agent. It turns raw store creative
(icon / screenshots / preview video) into a structured, machine-readable
understanding and, from that, into optimizer-ready actions.

This module is the contract layer (pure data, no I/O, no side effects):

* ``StoreCreativeAsset``   — one raw store asset (URL + type + version)
* ``CreativeVisionFeature``— the 7-dim "vision" scoring of one asset
* ``ASOCreativeDNA``       — the extracted creative DNA of one asset
* ``ASOCreativePattern``   — a mined cross-game visual pattern (cf. E13.4)
* ``CompetitorCreative``   — a competitor's asset + its vision feature / DNA
* ``OptimizationAction``   — a non-image optimizer suggestion (→ ``GrowthAction``)
* ``ASOCreativeExperience``— a closed-loop learning record (CVR before/after)

E16.6.3 depends ONE-WAY on:
  - ``src.aso_intelligence.reality`` (``ASORealitySnapshot`` / ``Platform``)
    for the raw asset capture it builds ``StoreCreativeAsset`` from.
  - ``src.aso_intelligence.models`` (``ASOAction``) and
    ``src.revenue_intelligence.models`` (``GrowthAction``) for emitting
    optimizer moves into the shared Growth Decision Layer (E16.1 / E13.3).

Vision analysis is *deterministic heuristic* here (no CLIP / no LLM / no
network) — the same seam an E11 Creative Evolution Engine would plug into.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.aso_intelligence.reality.models import ASORealitySnapshot, Platform


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# 1. Asset type
# --------------------------------------------------------------------------- #
class AssetType(str, Enum):
    """The kind of store creative asset."""

    ICON = "icon"
    SCREENSHOT = "screenshot"
    VIDEO = "video"


# --------------------------------------------------------------------------- #
# 2. Store creative asset (raw capture)
# --------------------------------------------------------------------------- #
@dataclass
class StoreCreativeAsset:
    """One raw store creative asset.

    Built from ``ASORealitySnapshot`` (icon_url + screenshots URLs). ``url`` is
    the store CDN URL; ``version`` lets the optimizer track asset rotations.
    """

    game_id: str
    asset_type: AssetType
    url: str
    version: str = "v1"
    created_at: datetime = field(default_factory=_now)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "url": self.url,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoreCreativeAsset":
        ts = d.get("created_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = _now()
        else:
            ts = _now()
        try:
            at = AssetType(d.get("asset_type", "screenshot"))
        except ValueError:
            at = AssetType.SCREENSHOT
        return cls(
            game_id=d.get("game_id", ""),
            asset_type=at,
            url=d.get("url", ""),
            version=d.get("version", "v1"),
            created_at=ts,
            extra=d.get("extra") or {},
        )

    @classmethod
    def assets_from_reality(
        cls,
        game_id: str,
        platform: Platform,
        reality: ASORealitySnapshot,
        version: str = "v1",
    ) -> List["StoreCreativeAsset"]:
        """Bridge a raw ``ASORealitySnapshot`` into a list of assets.

        - ``reality.icon_url``           → one ``ICON`` asset
        - ``reality.screenshots`` (urls) → one ``SCREENSHOT`` asset per URL
        - ``reality.extra["preview_video"]`` (if present) → one ``VIDEO`` asset

        Assets with empty URLs are skipped. ``platform`` is recorded in
        ``extra["platform"]`` for provenance.
        """
        assets: List["StoreCreativeAsset"] = []
        plat = platform.value if isinstance(platform, Platform) else str(platform)

        if reality.icon_url:
            assets.append(
                cls(
                    game_id=game_id,
                    asset_type=AssetType.ICON,
                    url=reality.icon_url,
                    version=version,
                    extra={"platform": plat},
                )
            )

        for idx, url in enumerate(reality.screenshots or []):
            if not url:
                continue
            assets.append(
                cls(
                    game_id=game_id,
                    asset_type=AssetType.SCREENSHOT,
                    url=url,
                    version=version,
                    extra={"platform": plat, "order": idx},
                )
            )

        video = (reality.extra or {}).get("preview_video")
        if video:
            assets.append(
                cls(
                    game_id=game_id,
                    asset_type=AssetType.VIDEO,
                    url=video,
                    version=version,
                    extra={"platform": plat},
                )
            )

        return assets


# --------------------------------------------------------------------------- #
# 3. Creative vision feature (7-dim scoring, 0.0–1.0)
# --------------------------------------------------------------------------- #
@dataclass
class CreativeVisionFeature:
    """Deterministic "vision" scoring of one store creative asset.

    Reuses the E11 Creative DNA vocabulary. All 7 dims are 0.0–1.0:

    * ``hook_score``         — does it stop the scroll?
    * ``gameplay_clarity``   — is the core loop obvious?
    * ``emotional_appeal``   — does it make the player *feel* something?
    * ``character_visibility``— are the characters / mascots visible?
    * ``text_readability``   — is overlay copy legible at thumbnail size?
    * ``reward_visibility``  — is the reward / payoff visible?
    * ``visual_density``     — too busy / too empty (→ closer to 0.5 is better,
                               but here it is a raw 0–1 "amount of content" score)

    Two derived aggregates power the Fitness Score:
    * ``value_score``  = mean(reward_visibility, text_readability)
    * ``emotion_score``= mean(emotional_appeal, character_visibility)
    """

    hook_score: float = 0.0
    gameplay_clarity: float = 0.0
    emotional_appeal: float = 0.0
    character_visibility: float = 0.0
    text_readability: float = 0.0
    reward_visibility: float = 0.0
    visual_density: float = 0.0

    def _clamp(self, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @property
    def value_score(self) -> float:
        """Aggregate 'value proposition' signal (reward + text)."""
        return self._clamp(
            (self.reward_visibility + self.text_readability) / 2.0
        )

    @property
    def emotion_score(self) -> float:
        """Aggregate 'emotional trigger' signal (appeal + character)."""
        return self._clamp(
            (self.emotional_appeal + self.character_visibility) / 2.0
        )

    def fitness(self) -> float:
        """ASO Creative Fitness Score.

        ASO Fitness = Hook×0.3 + Clarity×0.3 + Value×0.2 + Emotion×0.2
        (Value and Emotion are the aggregates above). Returns 0.0–1.0.
        """
        score = (
            self.hook_score * 0.3
            + self.gameplay_clarity * 0.3
            + self.value_score * 0.2
            + self.emotion_score * 0.2
        )
        return round(self._clamp(score), 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_score": round(self.hook_score, 4),
            "gameplay_clarity": round(self.gameplay_clarity, 4),
            "emotional_appeal": round(self.emotional_appeal, 4),
            "character_visibility": round(self.character_visibility, 4),
            "text_readability": round(self.text_readability, 4),
            "reward_visibility": round(self.reward_visibility, 4),
            "visual_density": round(self.visual_density, 4),
            "value_score": round(self.value_score, 4),
            "emotion_score": round(self.emotion_score, 4),
            "fitness": self.fitness(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CreativeVisionFeature":
        if d is None:
            return cls()
        return cls(
            hook_score=float(d.get("hook_score", 0.0)),
            gameplay_clarity=float(d.get("gameplay_clarity", 0.0)),
            emotional_appeal=float(d.get("emotional_appeal", 0.0)),
            character_visibility=float(d.get("character_visibility", 0.0)),
            text_readability=float(d.get("text_readability", 0.0)),
            reward_visibility=float(d.get("reward_visibility", 0.0)),
            visual_density=float(d.get("visual_density", 0.0)),
        )


# --------------------------------------------------------------------------- #
# 4. ASO Creative DNA
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeDNA:
    """The extracted "creative DNA" of one asset.

    Categorical metadata describing the visual identity. Example for a Merge
    game's icon::

        ASOCreativeDNA(
            asset_type=AssetType.ICON,
            dominant_color="purple",
            character_style="cartoon_monster",
            composition="centered_focal",
            message_type="merge_progress",
            emotional_trigger="satisfaction",
            gameplay_focus="merge_two_objects",
        )
    """

    asset_type: AssetType = AssetType.SCREENSHOT
    dominant_color: str = "unknown"
    character_style: str = "unknown"
    composition: str = "unknown"
    message_type: str = "unknown"
    emotional_trigger: str = "unknown"
    gameplay_focus: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_type": self.asset_type.value,
            "dominant_color": self.dominant_color,
            "character_style": self.character_style,
            "composition": self.composition,
            "message_type": self.message_type,
            "emotional_trigger": self.emotional_trigger,
            "gameplay_focus": self.gameplay_focus,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOCreativeDNA":
        if d is None:
            return cls()
        try:
            at = AssetType(d.get("asset_type", "screenshot"))
        except ValueError:
            at = AssetType.SCREENSHOT
        return cls(
            asset_type=at,
            dominant_color=d.get("dominant_color", "unknown"),
            character_style=d.get("character_style", "unknown"),
            composition=d.get("composition", "unknown"),
            message_type=d.get("message_type", "unknown"),
            emotional_trigger=d.get("emotional_trigger", "unknown"),
            gameplay_focus=d.get("gameplay_focus", "unknown"),
        )


# --------------------------------------------------------------------------- #
# 5. ASO Creative Pattern (cf. E13.4 Pattern Memory)
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativePattern:
    """A mined cross-game visual pattern.

    e.g. category="merge", asset="icon", pattern="centered_cartoon_character",
    success=0.82, sample_size=10 — meaning: across 10 merge games, icons with a
    centered cartoon character averaged a 0.82 creative fitness.
    """

    category: str
    asset: str  # "icon" | "screenshot" | "video"
    pattern: str
    success: float = 0.0  # mean fitness / CVR lift of assets matching the pattern
    sample_size: int = 0
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "asset": self.asset,
            "pattern": self.pattern,
            "success": round(self.success, 4),
            "sample_size": self.sample_size,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOCreativePattern":
        return cls(
            category=d.get("category", ""),
            asset=d.get("asset", ""),
            pattern=d.get("pattern", ""),
            success=float(d.get("success", 0.0)),
            sample_size=int(d.get("sample_size", 0)),
            note=d.get("note", ""),
        )


# --------------------------------------------------------------------------- #
# 6. Competitor creative
# --------------------------------------------------------------------------- #
@dataclass
class CompetitorCreative:
    """A competitor's store asset + its extracted vision feature / DNA."""

    competitor_id: str
    game_id: str
    asset_type: AssetType = AssetType.SCREENSHOT
    feature: Optional[CreativeVisionFeature] = None
    dna: Optional[ASOCreativeDNA] = None
    url: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "competitor_id": self.competitor_id,
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "url": self.url,
            "feature": self.feature.to_dict() if self.feature else None,
            "dna": self.dna.to_dict() if self.dna else None,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompetitorCreative":
        try:
            at = AssetType(d.get("asset_type", "screenshot"))
        except ValueError:
            at = AssetType.SCREENSHOT
        return cls(
            competitor_id=d.get("competitor_id", ""),
            game_id=d.get("game_id", ""),
            asset_type=at,
            url=d.get("url", ""),
            feature=CreativeVisionFeature.from_dict(d.get("feature")),
            dna=ASOCreativeDNA.from_dict(d.get("dna")),
            extra=d.get("extra") or {},
        )


# --------------------------------------------------------------------------- #
# 7. Optimization action (non-image suggestion)
# --------------------------------------------------------------------------- #
@dataclass
class OptimizationAction:
    """A non-image optimizer suggestion for one asset.

    e.g. ``OptimizationAction(game_id, SCREENSHOT, "screenshot_1", "high",
    "Hook score 0.32 below category benchmark 0.61",
    "Replace first screenshot with a high-contrast 'merge in progress' moment",
    "+18% CVR")``
    """

    game_id: str
    asset_type: AssetType
    target: str  # e.g. "icon" / "screenshot_1" / "video_0"
    priority: str  # "high" | "medium" | "low"
    reason: str
    suggestion: str
    expected_metric: str = ""  # e.g. "cvr:+18%" / "fitness:0.58->0.82"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "target": self.target,
            "priority": self.priority,
            "reason": self.reason,
            "suggestion": self.suggestion,
            "expected_metric": self.expected_metric,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OptimizationAction":
        try:
            at = AssetType(d.get("asset_type", "screenshot"))
        except ValueError:
            at = AssetType.SCREENSHOT
        return cls(
            game_id=d.get("game_id", ""),
            asset_type=at,
            target=d.get("target", ""),
            priority=d.get("priority", "medium"),
            reason=d.get("reason", ""),
            suggestion=d.get("suggestion", ""),
            expected_metric=d.get("expected_metric", ""),
        )


# --------------------------------------------------------------------------- #
# 8. Closed-loop experience record (CVR before / after)
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeExperience:
    """A closed-loop learning record: an asset change and its CVR outcome.

    e.g. ``ASOCreativeExperience(game_id, ICON, "replaced flat icon with
    centered monster", 0.42, 0.50, "centered_cartoon_character", 0.9)`` —
    a +18% relative CVR lift, recorded for cross-game reuse.
    """

    game_id: str
    asset_type: AssetType
    change: str
    cvr_before: float
    cvr_after: float
    pattern: str = ""  # the pattern this change matched / established
    confidence: float = 0.0
    created_at: datetime = field(default_factory=_now)

    def cvr_lift(self) -> float:
        """Relative CVR lift (0.0 if before <= 0)."""
        if self.cvr_before <= 0:
            return 0.0
        return round((self.cvr_after - self.cvr_before) / self.cvr_before, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "asset_type": self.asset_type.value,
            "change": self.change,
            "cvr_before": round(self.cvr_before, 4),
            "cvr_after": round(self.cvr_after, 4),
            "cvr_lift": self.cvr_lift(),
            "pattern": self.pattern,
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ASOCreativeExperience":
        ts = d.get("created_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = _now()
        else:
            ts = _now()
        try:
            at = AssetType(d.get("asset_type", "screenshot"))
        except ValueError:
            at = AssetType.SCREENSHOT
        return cls(
            game_id=d.get("game_id", ""),
            asset_type=at,
            change=d.get("change", ""),
            cvr_before=float(d.get("cvr_before", 0.0)),
            cvr_after=float(d.get("cvr_after", 0.0)),
            pattern=d.get("pattern", ""),
            confidence=float(d.get("confidence", 0.0)),
            created_at=ts,
        )


__all__ = [
    "AssetType",
    "StoreCreativeAsset",
    "CreativeVisionFeature",
    "ASOCreativeDNA",
    "ASOCreativePattern",
    "CompetitorCreative",
    "OptimizationAction",
    "ASOCreativeExperience",
]
