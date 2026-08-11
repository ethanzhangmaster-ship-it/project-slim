"""Cost Predictor"""
from typing import Dict, Any
from dataclasses import dataclass


class CostPredictor:
    """成本预测器"""

    _platform_pricing = {
        "veo": {"price_per_second": 0.2, "base_price": 0.0},
        "kling": {"price_per_second": 0.15, "base_price": 0.0},
        "runway": {"price_per_second": 0.25, "base_price": 0.0},
        "pika": {"price_per_second": 0.1, "base_price": 0.0},
        "luma": {"price_per_second": 0.3, "base_price": 0.0},
        "hailuo": {"price_per_second": 0.12, "base_price": 0.0},
        "comfyui": {"price_per_second": 0.05, "base_price": 0.0},
    }

    _resolution_multiplier = {
        "720p": 0.8,
        "1080p": 1.0,
        "2k": 1.5,
        "4k": 2.5,
    }

    @classmethod
    def predict(
        cls,
        platform: str,
        duration: float,
        resolution: str = "1080p",
        style: str = "standard",
    ) -> Dict[str, Any]:
        pricing = cls._platform_pricing.get(platform, {"price_per_second": 0.1, "base_price": 0.0})
        multiplier = cls._resolution_multiplier.get(resolution, 1.0)

        base_cost = pricing["base_price"] + duration * pricing["price_per_second"]
        estimated_cost = base_cost * multiplier

        return {
            "platform": platform,
            "duration": duration,
            "resolution": resolution,
            "base_cost": round(base_cost, 2),
            "estimated_cost": round(estimated_cost, 2),
            "gpu_required": cls._get_gpu(platform),
            "estimated_time_seconds": int(duration * 2),
        }

    @classmethod
    def _get_gpu(cls, platform: str) -> str:
        gpu_map = {
            "veo": "A100",
            "kling": "RTX 4090",
            "runway": "H100",
            "pika": "A100",
            "luma": "H100",
            "hailuo": "RTX 4090",
            "comfyui": "RTX 4090",
        }
        return gpu_map.get(platform, "A100")

    @classmethod
    def compare_platforms(cls, duration: float, resolution: str = "1080p") -> Dict[str, Dict[str, Any]]:
        results = {}
        for platform in cls._platform_pricing:
            results[platform] = cls.predict(platform, duration, resolution)
        return results
