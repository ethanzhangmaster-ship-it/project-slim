"""Platform Router - 智能平台选择"""
from typing import Dict, Any, List
from dataclasses import dataclass, field

from .routing_strategy import RoutingStrategy, StyleBasedStrategy, BudgetBasedStrategy, MotionBasedStrategy


@dataclass
class RoutingDecision:
    platform: str = ""
    score: float = 0.0
    reason: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


class PlatformRouter:
    """智能平台路由器"""

    def __init__(self):
        self._strategies: List[RoutingStrategy] = [
            StyleBasedStrategy(),
            MotionBasedStrategy(),
            BudgetBasedStrategy(),
        ]

    def route(self, requirements: Dict[str, Any]) -> RoutingDecision:
        all_scores = {}

        for strategy in self._strategies:
            scores = strategy.score(requirements)
            for score in scores:
                if score.platform not in all_scores:
                    all_scores[score.platform] = []
                all_scores[score.platform].append(score.score)

        platform_scores = []
        for platform, scores in all_scores.items():
            avg_score = sum(scores) / len(scores)
            platform_scores.append({"platform": platform, "score": avg_score})

        platform_scores.sort(key=lambda x: x["score"], reverse=True)

        best = platform_scores[0]
        alternatives = platform_scores[1:]

        reasons = []
        style = requirements.get("style", "cinematic")
        budget = requirements.get("budget", 100)
        motion = requirements.get("motion", "simple")

        if best["platform"] == "veo":
            reasons.append(f"Best for {style} style")
        elif best["platform"] == "kling":
            reasons.append(f"Best value under ${budget} budget")
        elif best["platform"] == "runway":
            reasons.append(f"Best for {motion} motion")
        elif best["platform"] == "comfyui":
            reasons.append("Best for local batch generation")

        return RoutingDecision(
            platform=best["platform"],
            score=round(best["score"], 2),
            reason="; ".join(reasons),
            alternatives=alternatives,
        )

    def suggest_platform(self, blueprint: Dict[str, Any]) -> RoutingDecision:
        requirements = {
            "style": blueprint.get("style", "cinematic"),
            "duration": blueprint.get("duration", 8),
            "budget": blueprint.get("budget", 100),
            "motion": blueprint.get("motion", "simple"),
        }
        return self.route(requirements)
