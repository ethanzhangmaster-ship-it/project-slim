from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class MilestoneStatus(Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


@dataclass
class Milestone:
    milestone_id: str
    title: str
    target_date: datetime
    status: MilestoneStatus
    deliverables: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "title": self.title,
            "target_date": self.target_date.isoformat(),
            "status": self.status.value,
            "deliverables": self.deliverables,
        }


@dataclass
class Timeline:
    start_date: datetime
    end_date: datetime
    milestones: List[Milestone] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "milestones": [m.to_dict() for m in self.milestones],
        }


@dataclass
class Roadmap:
    product_id: str
    version: str
    timeline: Timeline
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "version": self.version,
            "timeline": self.timeline.to_dict(),
            "created_at": self.created_at.isoformat(),
        }


class RoadmapEngine:
    def __init__(self):
        self._roadmaps: Dict[str, Roadmap] = {}
        self._milestones: Dict[str, Milestone] = {}

    def create_roadmap(self, product_id: str) -> Roadmap:
        start = datetime.now()
        end = start + timedelta(days=180)
        timeline = Timeline(
            start_date=start,
            end_date=end,
            milestones=[
                Milestone(
                    "m1",
                    "Alpha Build",
                    start + timedelta(days=30),
                    MilestoneStatus.COMPLETED,
                    ["core loop", "basic UI"],
                ),
                Milestone(
                    "m2",
                    "Beta Launch",
                    start + timedelta(days=90),
                    MilestoneStatus.IN_PROGRESS,
                    ["monetization", "social features"],
                ),
                Milestone(
                    "m3",
                    "Global Release",
                    start + timedelta(days=180),
                    MilestoneStatus.PLANNED,
                    ["localization", "paid UA"],
                ),
            ],
        )
        roadmap = Roadmap(product_id, "v1.0", timeline)
        self._roadmaps[product_id] = roadmap
        return roadmap

    def get_roadmap(self, product_id: str) -> Optional[Roadmap]:
        if product_id in self._roadmaps:
            return self._roadmaps[product_id]
        return self.create_roadmap(product_id)

    def add_milestone(self, milestone: Milestone) -> str:
        self._milestones[milestone.milestone_id] = milestone
        return milestone.milestone_id

    def update_milestone(self, milestone_id: str) -> Optional[Milestone]:
        if milestone_id in self._milestones:
            self._milestones[milestone_id].status = MilestoneStatus.COMPLETED
            return self._milestones[milestone_id]
        return None

    def get_timeline(self) -> Timeline:
        return self.create_roadmap("default").timeline

    def get_stats(self) -> Dict[str, Any]:
        milestones = list(self._milestones.values())
        status_counts = {
            "planned": 0,
            "in_progress": 0,
            "completed": 0,
            "delayed": 0,
        }
        for m in milestones:
            status_counts[m.status.value] += 1
        return {
            "total_roadmaps": len(self._roadmaps),
            "total_milestones": len(milestones),
            "status_distribution": status_counts,
        }