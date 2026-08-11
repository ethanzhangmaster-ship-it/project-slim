"""Cost Model"""
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class CostModel:
    platform: str = ""
    price_per_second: float = 0.0
    base_price: float = 0.0
    gpu_required: str = ""

    def calculate(self, duration: float, resolution: str = "1080p") -> Dict[str, Any]:
        resolution_multiplier = {
            "720p": 0.8,
            "1080p": 1.0,
            "2k": 1.5,
            "4k": 2.5
        }.get(resolution, 1.0)

        estimated_cost = (self.base_price + duration * self.price_per_second) * resolution_multiplier
        estimated_time = duration * 2

        return {
            "platform": self.platform,
            "estimated_cost": round(estimated_cost, 2),
            "duration": duration,
            "resolution": resolution,
            "estimated_time_seconds": int(estimated_time),
            "gpu_required": self.gpu_required
        }


class CostModelManager:
    _instance = None
    _models: Dict[str, CostModel] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self):
        from .capability import capability_manager
        for platform in capability_manager.list_platforms():
            cap = capability_manager.get_capability(platform)
            pricing = cap.get("pricing", {})
            self._models[platform] = CostModel(
                platform=platform,
                price_per_second=pricing.get("price_per_second", 0.1),
                base_price=pricing.get("base_price", 0.0),
                gpu_required=pricing.get("gpu_required", "A100")
            )

    def get_cost(self, platform: str, duration: float, resolution: str = "1080p") -> Dict[str, Any]:
        model = self._models.get(platform)
        if model:
            return model.calculate(duration, resolution)
        return {
            "platform": platform,
            "estimated_cost": 0.0,
            "duration": duration,
            "resolution": resolution,
            "estimated_time_seconds": 0,
            "gpu_required": "unknown"
        }


cost_model_manager = CostModelManager()
