"""Product management module for autonomous product studio."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import random
import uuid


@dataclass
class Milestone:
    """Project milestone."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    duration_weeks: int = 0
    dependencies: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)


@dataclass
class ProductPackage:
    """Complete product package for development handoff."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    opportunity_id: str = ""
    idea_summary: str = ""
    design_summary: str = ""
    economy_summary: str = ""
    level_plan: str = ""
    prototype_features: List[str] = field(default_factory=list)
    playtest_results: str = ""
    timeline_weeks: int = 0
    team_roles: List[str] = field(default_factory=list)
    budget_estimate_usd: float = 0.0


class ProductManager:
    """Manages product packaging and timeline estimation."""

    def __init__(self):
        self._package: ProductPackage | None = None
        self._milestones: List[Milestone] = []

    def create_product_package(self, opportunity: Any) -> ProductPackage:
        """Create a complete product package from an opportunity."""
        opp_id = getattr(opportunity, "id", "unknown")
        segment = getattr(opportunity, "market_segment", "general")
        self._package = ProductPackage(
            opportunity_id=opp_id,
            idea_summary=f"Game idea targeting {segment} segment.",
            design_summary="Core loop and mechanics defined in GDD v1.",
            economy_summary="Dual-currency economy with daily reward loops.",
            level_plan="30 handcrafted levels across 6 themes.",
            prototype_features=[
                "core_movement",
                "basic_combat",
                "ui_framework",
                "inventory_system",
                "save_load",
            ],
            playtest_results="Simulated 50 sessions; NPS pending.",
            timeline_weeks=random.randint(12, 36),
            team_roles=["game_designer", "programmer", "artist", "sound_designer", "qa"],
            budget_estimate_usd=round(random.uniform(50_000, 500_000), 2),
        )
        return self._package

    def get_package(self) -> ProductPackage:
        """Return the current product package."""
        if self._package is None:
            self._package = ProductPackage()
        return self._package

    def estimate_timeline(self) -> Dict[str, Any]:
        """Estimate development timeline with milestones."""
        if self._package is None:
            self.create_product_package(None)
        total_weeks = self._package.timeline_weeks
        self._milestones = [
            Milestone(
                name="Pre-Production",
                duration_weeks=max(1, int(total_weeks * 0.15)),
                deliverables=["GDD v1", "art_bible", "tech_spec"],
            ),
            Milestone(
                name="Vertical Slice",
                duration_weeks=max(1, int(total_weeks * 0.25)),
                dependencies=["Pre-Production"],
                deliverables=["playable_slice", "core_loop_validated"],
            ),
            Milestone(
                name="Alpha",
                duration_weeks=max(1, int(total_weeks * 0.30)),
                dependencies=["Vertical Slice"],
                deliverables=["feature_complete", "first_pass_content"],
            ),
            Milestone(
                name="Beta",
                duration_weeks=max(1, int(total_weeks * 0.20)),
                dependencies=["Alpha"],
                deliverables=["content_complete", "soft_launch_ready"],
            ),
            Milestone(
                name="Launch",
                duration_weeks=max(1, int(total_weeks * 0.10)),
                dependencies=["Beta"],
                deliverables=["global_launch", "live_ops_plan"],
            ),
        ]
        return {
            "total_weeks": total_weeks,
            "milestones": [
                {
                    "name": m.name,
                    "duration_weeks": m.duration_weeks,
                    "deliverables": m.deliverables,
                }
                for m in self._milestones
            ],
            "critical_path": [m.name for m in self._milestones],
        }
