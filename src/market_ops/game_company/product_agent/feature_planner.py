from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class FeaturePlan:
    plan_id: str
    features: List[Dict[str, Any]] = field(default_factory=list)
    phases: Dict[str, List[str]] = field(default_factory=dict)
    timeline: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)


class FeaturePlanner:
    def __init__(self):
        self.plans: Dict[str, FeaturePlan] = {}

    def plan(self, genre: str, focus_areas: List[str] = None) -> FeaturePlan:
        if focus_areas is None:
            focus_areas = ["core"]
        
        features = self._generate_features(genre)
        
        if "retention" in focus_areas:
            features.append({"id": "retention_features", "name": "Retention Features", "priority": 2, "effort": 2})
        if "monetization" in focus_areas:
            features.append({"id": "monetization_advanced", "name": "Advanced Monetization", "priority": 2, "effort": 2})
        if "social" in focus_areas:
            features.append({"id": "social_advanced", "name": "Advanced Social", "priority": 3, "effort": 3})
        
        phases = self._generate_phases(features)
        timeline = self._generate_timeline()
        dependencies = self._generate_dependencies(features)

        plan = FeaturePlan(
            plan_id=f"plan_{hash(genre) % 10000:04d}",
            features=features,
            phases=phases,
            timeline=timeline,
            dependencies=dependencies,
        )

        self.plans[plan.plan_id] = plan
        return plan

    def _generate_features(self, genre: str) -> List[Dict[str, Any]]:
        base_features = [
            {"id": "core_gameplay", "name": "Core Gameplay", "priority": 1, "effort": 3},
            {"id": "ui", "name": "UI/UX", "priority": 1, "effort": 2},
            {"id": "economy", "name": "Economy System", "priority": 2, "effort": 3},
            {"id": "monetization", "name": "Monetization", "priority": 2, "effort": 2},
            {"id": "social", "name": "Social Features", "priority": 3, "effort": 2},
            {"id": "events", "name": "Events System", "priority": 3, "effort": 1},
            {"id": "analytics", "name": "Analytics", "priority": 2, "effort": 1},
        ]

        if "Merge" in genre:
            base_features.append({"id": "merge_system", "name": "Merge System", "priority": 1, "effort": 3})
        
        if "Decoration" in genre:
            base_features.append({"id": "decoration", "name": "Decoration Mode", "priority": 2, "effort": 2})

        return base_features

    def _generate_phases(self, features: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        phases = {
            "Phase 1 (MVP)": [],
            "Phase 2 (Beta)": [],
            "Phase 3 (Launch)": [],
            "Phase 4 (Post-Launch)": [],
        }

        for feature in features:
            priority = feature["priority"]
            if priority == 1:
                phases["Phase 1 (MVP)"].append(feature["id"])
            elif priority == 2:
                phases["Phase 2 (Beta)"].append(feature["id"])
            else:
                phases["Phase 3 (Launch)"].append(feature["id"])

        return phases

    def _generate_timeline(self) -> Dict[str, str]:
        return {
            "Phase 1": "Weeks 1-4",
            "Phase 2": "Weeks 5-8",
            "Phase 3": "Weeks 9-12",
            "Phase 4": "Weeks 13+",
        }

    def _generate_dependencies(self, features: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        return {
            "economy": ["core_gameplay"],
            "monetization": ["economy"],
            "social": ["core_gameplay"],
            "events": ["economy"],
        }

    def plan_demo(self) -> FeaturePlan:
        return self.plan("Merge + Decoration")
