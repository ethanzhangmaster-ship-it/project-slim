from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List


@dataclass
class CreativePipeline:
    pipeline_id: str
    stage: str
    concepts: int
    in_production: int
    ready_for_test: int
    winners: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "stage": self.stage,
            "concepts": self.concepts,
            "in_production": self.in_production,
            "ready_for_test": self.ready_for_test,
            "winners": self.winners,
        }


@dataclass
class CreativeNeed:
    need_id: str
    channel: str
    format: str
    quantity: int
    deadline: datetime
    priority: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "need_id": self.need_id,
            "channel": self.channel,
            "format": self.format,
            "quantity": self.quantity,
            "deadline": self.deadline.isoformat(),
            "priority": self.priority,
        }


@dataclass
class CreativeBudget:
    period: str
    total_budget: float
    production_cost: float
    testing_cost: float
    influencer_cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "total_budget": self.total_budget,
            "production_cost": self.production_cost,
            "testing_cost": self.testing_cost,
            "influencer_cost": self.influencer_cost,
        }


class CreativeStrategy:
    def __init__(self):
        self._pipelines: Dict[str, CreativePipeline] = {}
        self._needs: Dict[str, CreativeNeed] = {}

    def plan_creative_pipeline(self) -> CreativePipeline:
        pipeline = CreativePipeline(
            pipeline_id="cp1",
            stage="active",
            concepts=12,
            in_production=5,
            ready_for_test=3,
            winners=2,
        )
        self._pipelines[pipeline.pipeline_id] = pipeline
        return pipeline

    def get_creative_needs(self) -> List[CreativeNeed]:
        now = datetime.now()
        return [
            CreativeNeed("n1", "meta_ads", "video_15s", 8, now + timedelta(days=7), "high"),
            CreativeNeed("n2", "tiktok_ads", "video_30s", 5, now + timedelta(days=10), "high"),
            CreativeNeed("n3", "google_ads", "playable", 3, now + timedelta(days=14), "medium"),
            CreativeNeed("n4", "asa", "screenshot_set", 4, now + timedelta(days=5), "critical"),
        ]

    def allocate_creative_budget(self) -> CreativeBudget:
        return CreativeBudget(
            period="monthly",
            total_budget=60000.0,
            production_cost=35000.0,
            testing_cost=15000.0,
            influencer_cost=10000.0,
        )

    def evaluate_creative_performance(self) -> List[Dict[str, Any]]:
        return [
            {"creative_id": "c1", "ctr": 0.035, "ipm": 4.5, "cost_per_install": 2.80, "status": "winner"},
            {"creative_id": "c2", "ctr": 0.028, "ipm": 3.8, "cost_per_install": 3.20, "status": "scale"},
            {"creative_id": "c3", "ctr": 0.015, "ipm": 1.5, "cost_per_install": 5.50, "status": "kill"},
        ]

    def get_creative_strategy(self) -> Dict[str, Any]:
        return {
            "theme_rotation_days": 14,
            "test_budget_per_creative": 500.0,
            "winning_threshold_ipm": 3.5,
            "production_capacity_per_week": 3,
            "preferred_formats": ["video_15s", "video_30s", "playable"],
        }

    def get_stats(self) -> Dict[str, Any]:
        pipelines = list(self._pipelines.values())
        needs = self.get_creative_needs()
        total_concepts = sum(p.concepts for p in pipelines)
        return {
            "active_pipelines": len(pipelines),
            "total_concepts": total_concepts,
            "in_production": sum(p.in_production for p in pipelines),
            "ready_for_test": sum(p.ready_for_test for p in pipelines),
            "winners": sum(p.winners for p in pipelines),
            "open_needs": len(needs),
        }