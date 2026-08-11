"""
E16.6.3 — Creative Vision Analyzer.

Turns a raw ``StoreCreativeAsset`` (plus optional low-level ``signals`` — the
kind a real vision model / E11 Creative Evolution Engine would emit) into:

  * a ``CreativeVisionFeature`` (the 7-dim scoring), and
  * an ``ASOCreativeDNA`` (the extracted categorical identity).

This layer is *deterministic heuristic*: no CLIP, no LLM, no network. The
``VisionAnalyzer`` Protocol is the seam an E11 visual model plugs into — swap
``HeuristicVisionAnalyzer`` for a real model without touching the optimizer.

A ``StaticVisionAnalyzer`` test double is provided so the optimizer / generator
bridge can be exercised without heuristic behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from src.aso_intelligence.creative.models import (
    ASOCreativeDNA,
    AssetType,
    CreativeVisionFeature,
    StoreCreativeAsset,
)


# The 7 feature dims, in canonical order.
_DIMS = [
    "hook_score",
    "gameplay_clarity",
    "emotional_appeal",
    "character_visibility",
    "text_readability",
    "reward_visibility",
    "visual_density",
]


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


# Per-asset-type neutral baselines (used when no raw signals are supplied).
_BASELINES: Dict[AssetType, Dict[str, float]] = {
    AssetType.ICON: {
        "hook_score": 0.60,
        "gameplay_clarity": 0.40,
        "emotional_appeal": 0.50,
        "character_visibility": 0.55,
        "text_readability": 0.70,
        "reward_visibility": 0.40,
        "visual_density": 0.45,
    },
    AssetType.SCREENSHOT: {
        "hook_score": 0.50,
        "gameplay_clarity": 0.50,
        "emotional_appeal": 0.50,
        "character_visibility": 0.50,
        "text_readability": 0.50,
        "reward_visibility": 0.50,
        "visual_density": 0.50,
    },
    AssetType.VIDEO: {
        "hook_score": 0.55,
        "gameplay_clarity": 0.50,
        "emotional_appeal": 0.55,
        "character_visibility": 0.55,
        "text_readability": 0.45,
        "reward_visibility": 0.55,
        "visual_density": 0.60,
    },
}


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class VisionResult:
    """One asset's vision analysis output."""

    asset: StoreCreativeAsset
    feature: CreativeVisionFeature
    dna: ASOCreativeDNA
    raw_signals: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset.to_dict(),
            "feature": self.feature.to_dict(),
            "dna": self.dna.to_dict(),
            "raw_signals": {k: round(v, 4) for k, v in self.raw_signals.items()},
        }


# --------------------------------------------------------------------------- #
# Protocol seam (E11 visual model plugs here)
# --------------------------------------------------------------------------- #
@runtime_checkable
class VisionAnalyzer(Protocol):
    """Converts a store asset (+ optional raw vision signals) into a VisionResult."""

    def analyze(
        self,
        asset: StoreCreativeAsset,
        signals: Optional[Dict[str, float]] = None,
    ) -> VisionResult:
        ...


# --------------------------------------------------------------------------- #
# Deterministic heuristic implementation
# --------------------------------------------------------------------------- #
class HeuristicVisionAnalyzer:
    """Deterministic heuristic vision analyzer.

    ``signals`` may carry any of the 7 dims directly (the output of a vision
    model). Missing dims fall back to the asset-type baseline. DNA is inferred
    from the feature + asset metadata (``extra``).
    """

    def __init__(self, baselines: Optional[Dict[AssetType, Dict[str, float]]] = None):
        self._baselines = baselines or _BASELINES

    def _baseline(self, at: AssetType) -> Dict[str, float]:
        return dict(self._baselines.get(at, _BASELINES[AssetType.SCREENSHOT]))

    def _build_feature(
        self, asset: StoreCreativeAsset, signals: Optional[Dict[str, float]]
    ) -> CreativeVisionFeature:
        base = self._baseline(asset.asset_type)
        feats: Dict[str, float] = {}
        for dim in _DIMS:
            if signals and dim in signals and signals[dim] is not None:
                feats[dim] = _clamp(signals[dim])
            else:
                feats[dim] = base[dim]
        return CreativeVisionFeature(**feats)

    def _infer_dna(
        self, asset: StoreCreativeAsset, feature: CreativeVisionFeature
    ) -> ASOCreativeDNA:
        extra = asset.extra or {}
        char = feature.character_visibility
        if char >= 0.6:
            character_style = "cartoon"
        elif char >= 0.3:
            character_style = "abstract"
        else:
            character_style = "unknown"

        is_icon = asset.asset_type == AssetType.ICON
        if is_icon or feature.character_visibility >= 0.5 or feature.hook_score >= 0.6:
            composition = "centered_focal"
        else:
            composition = "scattered"

        if feature.gameplay_clarity >= 0.6:
            message_type = extra.get("message_type", "gameplay_moment")
        else:
            message_type = extra.get("message_type", "generic")

        if feature.reward_visibility >= 0.6:
            emotional_trigger = "satisfaction"
        elif feature.emotional_appeal >= 0.5:
            emotional_trigger = "curiosity"
        else:
            emotional_trigger = "neutral"

        return ASOCreativeDNA(
            asset_type=asset.asset_type,
            dominant_color=extra.get("dominant_color", "unknown"),
            character_style=character_style,
            composition=composition,
            message_type=message_type,
            emotional_trigger=emotional_trigger,
            gameplay_focus=extra.get("gameplay_focus", "unknown"),
        )

    def analyze(
        self,
        asset: StoreCreativeAsset,
        signals: Optional[Dict[str, float]] = None,
    ) -> VisionResult:
        feature = self._build_feature(asset, signals)
        dna = self._infer_dna(asset, feature)
        return VisionResult(
            asset=asset,
            feature=feature,
            dna=dna,
            raw_signals={k: _clamp(v) for k, v in (signals or {}).items()},
        )


# --------------------------------------------------------------------------- #
# Static test double — returns a fixed result regardless of input
# --------------------------------------------------------------------------- #
class StaticVisionAnalyzer:
    """Deterministic test double: always returns the same VisionResult.

    Useful for exercising the optimizer / generator bridge without heuristic
    variance. Accepts a fixed ``feature`` and ``dna`` (or callables).
    """

    def __init__(
        self,
        feature: Optional[CreativeVisionFeature] = None,
        dna: Optional[ASOCreativeDNA] = None,
    ):
        self._feature = feature or CreativeVisionFeature(
            hook_score=0.5,
            gameplay_clarity=0.5,
            emotional_appeal=0.5,
            character_visibility=0.5,
            text_readability=0.5,
            reward_visibility=0.5,
            visual_density=0.5,
        )
        self._dna = dna or ASOCreativeDNA(asset_type=AssetType.SCREENSHOT)

    def analyze(
        self,
        asset: StoreCreativeAsset,
        signals: Optional[Dict[str, float]] = None,
    ) -> VisionResult:
        # clone the fixed feature but keep the asset's type in the DNA
        feat = CreativeVisionFeature(
            hook_score=self._feature.hook_score,
            gameplay_clarity=self._feature.gameplay_clarity,
            emotional_appeal=self._feature.emotional_appeal,
            character_visibility=self._feature.character_visibility,
            text_readability=self._feature.text_readability,
            reward_visibility=self._feature.reward_visibility,
            visual_density=self._feature.visual_density,
        )
        dna = ASOCreativeDNA(
            asset_type=asset.asset_type,
            dominant_color=self._dna.dominant_color,
            character_style=self._dna.character_style,
            composition=self._dna.composition,
            message_type=self._dna.message_type,
            emotional_trigger=self._dna.emotional_trigger,
            gameplay_focus=self._dna.gameplay_focus,
        )
        return VisionResult(asset=asset, feature=feat, dna=dna, raw_signals=signals or {})


__all__ = [
    "VisionResult",
    "VisionAnalyzer",
    "HeuristicVisionAnalyzer",
    "StaticVisionAnalyzer",
    "_DIMS",
]
