"""
E16.6.3 — ASO Creative Optimization Engine.

Turns vision-analyzed assets into *non-image* optimization actions (the
"what to change" — not the pixels). This is the layer that connects E16.6.3
back into the shared Growth Decision Layer: every ``OptimizationAction`` can be
emitted as a standard ``GrowthAction`` (via ``ASOAction``) and routed through
E16.1's Decision Validator / E13.3 Growth Executor.

Pipeline:
    VisionResult(s)  →  AssetAnalysis (fitness vs benchmark, weak dims)
                     →  OptimizationAction(s)  →  GrowthAction
                     →  (after launch) ASOCreativeExperience (closed loop)

Deterministic: benchmarks come from competitor patterns (E16.6.2) or a default;
no LLM, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.aso_intelligence.creative.models import (
    ASOCreativeDNA,
    ASOCreativeExperience,
    AssetType,
    CreativeVisionFeature,
    OptimizationAction,
    StoreCreativeAsset,
)
from src.aso_intelligence.creative.vision_analyzer import VisionResult
from src.aso_intelligence.models import ASOAction
from src.revenue_intelligence.models import GrowthAction


# A vision dim below this is considered "weak".
WEAK_THRESHOLD = 0.50
# Fitness below this → high-priority action.
HIGH_PRIORITY_FITNESS = 0.40
# Default category benchmark when no competitor data is available.
DEFAULT_BENCHMARK = 0.60

# Which dims are "primary" (must be strong) per asset type.
_PRIMARY_DIMS: Dict[AssetType, List[str]] = {
    AssetType.ICON: ["hook_score", "character_visibility"],
    AssetType.SCREENSHOT: ["hook_score", "gameplay_clarity"],
    AssetType.VIDEO: ["hook_score", "gameplay_clarity"],
}

_DIM_LABELS = {
    "hook_score": "hook",
    "gameplay_clarity": "gameplay clarity",
    "emotional_appeal": "emotional appeal",
    "character_visibility": "character visibility",
    "text_readability": "text readability",
    "reward_visibility": "reward visibility",
    "visual_density": "visual density",
}

# Deterministic suggestion copy per (asset_type, weak dim).
_SUGGESTIONS: Dict[AssetType, Dict[str, str]] = {
    AssetType.ICON: {
        "hook_score": "Use a bold, high-contrast silhouette that reads at 0.5s thumbnail size.",
        "character_visibility": "Add a centered cartoon character occupying >=40% of the icon area (ICON_FOCUS_WEAK).",
        "emotional_appeal": "Inject a clear emotional cue (excited face / reward glow).",
        "text_readability": "Avoid small text on the icon; rely on shape + color for recognition.",
        "reward_visibility": "Show the core reward/payoff object prominently in the icon.",
    },
    AssetType.SCREENSHOT: {
        "hook_score": "Replace with a high-contrast 'gameplay moment' screenshot that stops the scroll.",
        "gameplay_clarity": "Show the core loop in the first frame (merge / action in progress).",
        "emotional_appeal": "Capture a moment of progress/reward to trigger emotional pull.",
        "text_readability": "Use short, large overlay copy (<6 words) legible at thumbnail size.",
        "reward_visibility": "Make the reward (coins/level-up) visible in the screenshot.",
    },
    AssetType.VIDEO: {
        "hook_score": "Open the preview video with the strongest gameplay beat (first 2s).",
        "gameplay_clarity": "Keep the core loop legible; avoid intro fluff in the first 3s.",
        "emotional_appeal": "End on a satisfying payoff moment.",
        "reward_visibility": "Show the reward loop explicitly in the preview.",
    },
}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


# --------------------------------------------------------------------------- #
# Analysis result
# --------------------------------------------------------------------------- #
@dataclass
class AssetAnalysis:
    """Per-asset verdict: fitness vs benchmark + which dims are weak."""

    asset: StoreCreativeAsset
    feature: CreativeVisionFeature
    fitness: float
    benchmark: float
    weak_dims: List[str] = field(default_factory=list)
    verdict: str = "ok"  # "weak" | "ok" | "strong"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset.to_dict(),
            "feature": self.feature.to_dict(),
            "fitness": round(self.fitness, 4),
            "benchmark": round(self.benchmark, 4),
            "weak_dims": list(self.weak_dims),
            "verdict": self.verdict,
        }


# --------------------------------------------------------------------------- #
# Optimization result
# --------------------------------------------------------------------------- #
@dataclass
class AssetOptimizationResult:
    """One asset's analysis + its optimization actions."""

    analysis: AssetAnalysis
    actions: List[OptimizationAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis": self.analysis.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
        }


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
@dataclass
class ASOCreativeOptimizationReport:
    """Unified output of one optimization run for a game."""

    game_id: str
    category: str
    overall_fitness: float = 0.0
    benchmark: float = DEFAULT_BENCHMARK
    analyses: List[AssetAnalysis] = field(default_factory=list)
    actions: List[OptimizationAction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "category": self.category,
            "overall_fitness": round(self.overall_fitness, 4),
            "benchmark": round(self.benchmark, 4),
            "analyses": [a.to_dict() for a in self.analyses],
            "actions": [a.to_dict() for a in self.actions],
        }


# --------------------------------------------------------------------------- #
# Optimizer
# --------------------------------------------------------------------------- #
class ASOCreativeOptimizer:
    """Analyzes vision results and emits optimization actions + GrowthActions."""

    def __init__(
        self,
        weak_threshold: float = WEAK_THRESHOLD,
        high_priority_fitness: float = HIGH_PRIORITY_FITNESS,
        default_benchmark: float = DEFAULT_BENCHMARK,
    ):
        self.weak_threshold = weak_threshold
        self.high_priority_fitness = high_priority_fitness
        self.default_benchmark = default_benchmark

    # ------------------------------------------------------------------ #
    def _benchmark_for(
        self,
        asset_type: AssetType,
        benchmark: Optional[float],
        competitor_patterns: Optional[List[Any]] = None,
    ) -> float:
        if benchmark is not None:
            return float(benchmark)
        # prefer the best competitor pattern that matches this asset type
        if competitor_patterns:
            best = None
            for p in competitor_patterns:
                if getattr(p, "asset", None) == asset_type.value and p.success is not None:
                    if best is None or p.success > best:
                        best = p.success
            if best is not None:
                return float(best)
        return self.default_benchmark

    def _target_for(self, asset: StoreCreativeAsset) -> str:
        if asset.asset_type == AssetType.ICON:
            return "icon"
        order = (asset.extra or {}).get("order", 0)
        if asset.asset_type == AssetType.VIDEO:
            return f"video_{order}"
        return f"screenshot_{order}"

    def analyze_asset(
        self,
        asset: StoreCreativeAsset,
        feature: CreativeVisionFeature,
        benchmark: float,
    ) -> AssetAnalysis:
        fitness = feature.fitness()
        primary = _PRIMARY_DIMS.get(asset.asset_type, ["hook_score"])
        weak = [
            d
            for d in primary
            if getattr(feature, d, 0.0) < self.weak_threshold
        ]
        if fitness < self.high_priority_fitness:
            verdict = "weak"
        elif weak or fitness < benchmark:
            verdict = "weak"
        elif fitness >= benchmark + 0.1:
            verdict = "strong"
        else:
            verdict = "ok"
        return AssetAnalysis(
            asset=asset,
            feature=feature,
            fitness=fitness,
            benchmark=benchmark,
            weak_dims=weak,
            verdict=verdict,
        )

    def optimize(self, analysis: AssetAnalysis) -> List[OptimizationAction]:
        """Produce one ``OptimizationAction`` per weak primary dim."""
        if analysis.verdict != "weak":
            return []
        actions: List[OptimizationAction] = None  # type: ignore
        actions = []
        asset = analysis.asset
        target = self._target_for(asset)
        gap = analysis.benchmark - analysis.fitness
        expected = f"fitness:{analysis.fitness:.2f}->{analysis.benchmark:.2f}"
        priority = "high" if analysis.fitness < self.high_priority_fitness else "medium"

        for dim in analysis.weak_dims:
            label = _DIM_LABELS.get(dim, dim)
            val = getattr(analysis.feature, dim, 0.0)
            reason = (
                f"{label.capitalize()} score {val:.2f} below weak threshold "
                f"{self.weak_threshold:.2f} (benchmark {analysis.benchmark:.2f})."
            )
            suggestion = _SUGGESTIONS.get(asset.asset_type, {}).get(
                dim,
                f"Improve {label} (currently {val:.2f}, weak threshold "
                f"{self.weak_threshold:.2f}).",
            )
            actions.append(
                OptimizationAction(
                    game_id=asset.game_id,
                    asset_type=asset.asset_type,
                    target=target,
                    priority=priority,
                    reason=reason,
                    suggestion=suggestion,
                    expected_metric=expected,
                )
            )
        return actions

    # ------------------------------------------------------------------ #
    def to_growth_action(
        self,
        opt: OptimizationAction,
        *,
        confidence: Optional[float] = None,
        impact_score: Optional[float] = None,
        source: str = "aso_creative_optimizer",
    ) -> GrowthAction:
        """Map an ``OptimizationAction`` to a standard ``GrowthAction``.

        asset_type → ``ASOAction``:
          ICON       → UPDATE_ICON
          SCREENSHOT → UPDATE_SCREENSHOT
          VIDEO      → CREATE_EXPERIMENT
        """
        action_map = {
            AssetType.ICON: ASOAction.UPDATE_ICON,
            AssetType.SCREENSHOT: ASOAction.UPDATE_SCREENSHOT,
            AssetType.VIDEO: ASOAction.CREATE_EXPERIMENT,
        }
        aso_action = action_map.get(opt.asset_type, ASOAction.UPDATE_SCREENSHOT)

        # derive confidence / impact from the fitness gap if not given
        gap = 0.0
        try:
            before, after = opt.expected_metric.split(":")[1].split("->")
            gap = max(0.0, float(after) - float(before))
        except Exception:
            gap = 0.0
        conf = confidence if confidence is not None else _clamp(0.5 + gap, 0.1, 0.95)
        impact = (
            impact_score
            if impact_score is not None
            else round(min(100.0, 40.0 + gap * 100.0), 2)
        )

        return GrowthAction(
            game_id=opt.game_id,
            action=aso_action,
            title=f"Optimize {opt.asset_type.value} ({opt.target})",
            rationale=f"{opt.reason} {opt.suggestion}",
            evidence={
                "target": opt.target,
                "priority": opt.priority,
                "expected_metric": opt.expected_metric,
            },
            confidence=round(conf, 4),
            impact_score=impact,
            source=source,
        )

    # ------------------------------------------------------------------ #
    def record_experiment(
        self,
        game_id: str,
        opt_action: OptimizationAction,
        cvr_before: float,
        cvr_after: float,
        pattern: str = "",
        confidence: float = 0.0,
    ) -> ASOCreativeExperience:
        """Build a closed-loop experience record from an executed change.

        (Persisting it is the memory module's job — pass ``memory`` to also
        append it there.)
        """
        return ASOCreativeExperience(
            game_id=game_id,
            asset_type=opt_action.asset_type,
            change=opt_action.suggestion,
            cvr_before=cvr_before,
            cvr_after=cvr_after,
            pattern=pattern,
            confidence=confidence,
        )

    # ------------------------------------------------------------------ #
    def run(
        self,
        game_id: str,
        category: str,
        results: List[VisionResult],
        *,
        benchmark: Optional[float] = None,
        competitor_patterns: Optional[List[Any]] = None,
    ) -> ASOCreativeOptimizationReport:
        analyses: List[AssetAnalysis] = []
        actions: List[OptimizationAction] = []
        total = 0.0
        for r in results:
            bench = self._benchmark_for(
                r.asset.asset_type, benchmark, competitor_patterns
            )
            analysis = self.analyze_asset(r.asset, r.feature, bench)
            analyses.append(analysis)
            opt_actions = self.optimize(analysis)
            actions.extend(opt_actions)
            total += analysis.fitness

        overall = round(total / len(results), 4) if results else 0.0
        resolved_bench = self._benchmark_for(
            AssetType.SCREENSHOT, benchmark, competitor_patterns
        )
        return ASOCreativeOptimizationReport(
            game_id=game_id,
            category=category,
            overall_fitness=overall,
            benchmark=resolved_bench,
            analyses=analyses,
            actions=actions,
        )


__all__ = [
    "ASOCreativeOptimizer",
    "AssetAnalysis",
    "AssetOptimizationResult",
    "ASOCreativeOptimizationReport",
    "WEAK_THRESHOLD",
    "HIGH_PRIORITY_FITNESS",
    "DEFAULT_BENCHMARK",
]
