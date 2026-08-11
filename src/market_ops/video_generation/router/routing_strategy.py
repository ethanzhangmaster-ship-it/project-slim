"""Routing Strategy"""
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class PlatformScore:
    platform: str = ""
    score: float = 0.0
    reason: str = ""
    factors: Dict[str, float] = field(default_factory=dict)


class RoutingStrategy:
    """路由策略基类"""

    def score(self, requirements: Dict[str, Any]) -> List[PlatformScore]:
        pass


class StyleBasedStrategy(RoutingStrategy):
    """基于风格的路由策略"""

    _style_mapping = {
        "cinematic": {"veo": 9, "runway": 8, "kling": 6},
        "realistic": {"veo": 10, "kling": 7, "runway": 6},
        "game": {"kling": 10, "veo": 5, "runway": 7},
        "cartoon": {"kling": 9, "runway": 8, "veo": 4},
        "abstract": {"runway": 9, "kling": 7, "veo": 5},
        "product": {"veo": 9, "kling": 8, "runway": 7},
    }

    def score(self, requirements: Dict[str, Any]) -> List[PlatformScore]:
        style = requirements.get("style", "cinematic").lower()
        scores = []

        for platform in ["veo", "kling", "runway", "comfyui"]:
            style_score = self._style_mapping.get(style, {}).get(platform, 5)
            score = PlatformScore(
                platform=platform,
                score=style_score,
                reason=f"Style '{style}' compatibility",
                factors={"style": style_score},
            )
            scores.append(score)

        return sorted(scores, key=lambda s: s.score, reverse=True)


class BudgetBasedStrategy(RoutingStrategy):
    """基于预算的路由策略"""

    _pricing = {
        "veo": {"price_per_second": 0.2, "base_price": 0.0},
        "kling": {"price_per_second": 0.15, "base_price": 0.0},
        "runway": {"price_per_second": 0.25, "base_price": 0.0},
        "comfyui": {"price_per_second": 0.05, "base_price": 0.0},
    }

    def score(self, requirements: Dict[str, Any]) -> List[PlatformScore]:
        duration = requirements.get("duration", 5)
        budget = requirements.get("budget", 100)

        scores = []
        for platform, pricing in self._pricing.items():
            cost = pricing["base_price"] + duration * pricing["price_per_second"]
            if cost <= budget:
                score = max(0, 10 - cost * 2)
            else:
                score = 0

            scores.append(PlatformScore(
                platform=platform,
                score=score,
                reason=f"Cost ${cost:.2f} within budget ${budget}",
                factors={"cost": cost, "score": score},
            ))

        return sorted(scores, key=lambda s: s.score, reverse=True)


class MotionBasedStrategy(RoutingStrategy):
    """基于动作复杂度的路由策略"""

    _motion_scores = {
        "simple": {"veo": 8, "kling": 9, "runway": 7},
        "medium": {"veo": 9, "kling": 8, "runway": 10},
        "complex": {"runway": 10, "veo": 7, "kling": 6},
    }

    def score(self, requirements: Dict[str, Any]) -> List[PlatformScore]:
        motion_complexity = requirements.get("motion", "simple").lower()
        scores = []

        for platform in ["veo", "kling", "runway", "comfyui"]:
            motion_score = self._motion_scores.get(motion_complexity, {}).get(platform, 5)
            scores.append(PlatformScore(
                platform=platform,
                score=motion_score,
                reason=f"Motion '{motion_complexity}' support",
                factors={"motion": motion_score},
            ))

        return sorted(scores, key=lambda s: s.score, reverse=True)
