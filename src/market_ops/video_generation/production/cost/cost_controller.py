"""Cost Controller - 成本控制器"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class CostEstimate:
    estimated_cost: float = 0.0
    recommended_platform: str = ""
    recommended_resolution: str = ""
    estimated_duration: float = 0.0
    gpu_required: str = ""


class CostController:
    """成本智能控制器"""

    _platform_pricing = {
        "veo": {"price_per_second": 0.20, "quality": "high", "supported_resolutions": ["1080p", "4k"]},
        "kling": {"price_per_second": 0.15, "quality": "medium", "supported_resolutions": ["720p", "1080p"]},
        "runway": {"price_per_second": 0.25, "quality": "high", "supported_resolutions": ["1080p", "2k"]},
        "comfyui": {"price_per_second": 0.05, "quality": "low", "supported_resolutions": ["720p", "1080p"]},
    }

    _resolution_multipliers = {
        "720p": 0.8,
        "1080p": 1.0,
        "2k": 1.5,
        "4k": 2.5,
    }

    _quality_thresholds = {
        "high": 80,
        "medium": 60,
        "low": 40,
    }

    def estimate(self, blueprint: Dict[str, Any], platform: str = "", creative_score: int = 70) -> CostEstimate:
        duration = blueprint.get("duration", 8)
        requested_resolution = blueprint.get("resolution", "1080p")
        requested_platform = platform or blueprint.get("platform", "kling")

        quality_level = self._determine_quality(creative_score)

        if quality_level == "high":
            recommended_platforms = ["veo", "runway"]
            recommended_resolution = "1080p"
        elif quality_level == "medium":
            recommended_platforms = ["kling", "veo"]
            recommended_resolution = "1080p"
        else:
            recommended_platforms = ["comfyui", "kling"]
            recommended_resolution = "720p"

        recommended_platform = requested_platform if requested_platform in recommended_platforms else recommended_platforms[0]

        pricing = self._platform_pricing.get(recommended_platform, {"price_per_second": 0.1})
        multiplier = self._resolution_multipliers.get(recommended_resolution, 1.0)

        estimated_cost = duration * pricing["price_per_second"] * multiplier

        return CostEstimate(
            estimated_cost=round(estimated_cost, 2),
            recommended_platform=recommended_platform,
            recommended_resolution=recommended_resolution,
            estimated_duration=duration,
            gpu_required="A100",
        )

    def _determine_quality(self, creative_score: int) -> str:
        if creative_score >= self._quality_thresholds["high"]:
            return "high"
        elif creative_score >= self._quality_thresholds["medium"]:
            return "medium"
        else:
            return "low"

    def compare_platforms(self, duration: float, resolution: str) -> List[Dict[str, Any]]:
        results = []
        for platform, pricing in self._platform_pricing.items():
            multiplier = self._resolution_multipliers.get(resolution, 1.0)
            cost = duration * pricing["price_per_second"] * multiplier
            results.append({
                "platform": platform,
                "estimated_cost": round(cost, 2),
                "quality": pricing["quality"],
            })
        return sorted(results, key=lambda r: r["estimated_cost"])

    def get_cheapest_platform(self, duration: float, min_quality: str = "low") -> str:
        candidates = [
            p for p, pricing in self._platform_pricing.items()
            if self._quality_level_value(pricing["quality"]) >= self._quality_level_value(min_quality)
        ]
        if not candidates:
            return "kling"
        return min(candidates, key=lambda p: self._platform_pricing[p]["price_per_second"])

    def _quality_level_value(self, quality: str) -> int:
        mapping = {"high": 3, "medium": 2, "low": 1}
        return mapping.get(quality, 2)