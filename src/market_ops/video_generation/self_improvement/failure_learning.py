from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class FailureLesson:
    lesson_id: str
    failure_type: str
    creative_id: Optional[str] = None
    audience_id: Optional[str] = None
    platform_id: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    root_cause: str = ""
    prevention: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class FailureLearning:
    def __init__(self):
        self.lessons: List[FailureLesson] = []

    def record_failure(self, failure_data: Dict[str, Any]) -> FailureLesson:
        symptoms = []
        if failure_data.get("ctr_ok"):
            symptoms.append("CTR OK")
        if failure_data.get("purchase_low"):
            symptoms.append("Purchase LOW")
        if failure_data.get("roas_drop"):
            symptoms.append("ROAS Drop")
        if failure_data.get("cpi_increase"):
            symptoms.append("CPI Increase")

        root_cause = self._analyze_root_cause(failure_data)
        prevention = self._generate_prevention(root_cause)

        lesson = FailureLesson(
            lesson_id=f"fail_{hash(str(failure_data)) % 10000:04d}",
            failure_type=failure_data.get("failure_type", "unknown"),
            creative_id=failure_data.get("creative_id"),
            audience_id=failure_data.get("audience_id"),
            platform_id=failure_data.get("platform_id"),
            symptoms=symptoms,
            root_cause=root_cause,
            prevention=prevention,
        )

        self.lessons.append(lesson)
        return lesson

    def _analyze_root_cause(self, data: Dict[str, Any]) -> str:
        if data.get("ctr_ok") and data.get("purchase_low"):
            return "wrong_audience"
        if data.get("roas_drop") and data.get("cpi_increase"):
            return "market_competition"
        if data.get("ctr_low") and data.get("purchase_low"):
            return "creative_fatigue"
        return "unknown"

    def _generate_prevention(self, root_cause: str) -> List[str]:
        prevention_map = {
            "wrong_audience": [
                "Audience segmentation before launch",
                "A/B test with different audiences",
                "Check audience compatibility in knowledge graph",
            ],
            "market_competition": [
                "Monitor competitor activity",
                "Adjust bidding strategy",
                "Increase creative refresh rate",
            ],
            "creative_fatigue": [
                "Creative rotation every 7 days",
                "Creative mutation based on winner DNA",
                "Expand creative variants",
            ],
        }
        return prevention_map.get(root_cause, ["Monitor and adjust"])

    def get_lessons_by_type(self, failure_type: str) -> List[FailureLesson]:
        return [l for l in self.lessons if l.failure_type == failure_type]

    def should_avoid(self, creative_id: str = None, audience_id: str = None, platform_id: str = None) -> bool:
        for lesson in self.lessons:
            if (creative_id and lesson.creative_id == creative_id) or \
               (audience_id and lesson.audience_id == audience_id) or \
               (platform_id and lesson.platform_id == platform_id):
                if lesson.root_cause == "wrong_audience":
                    return True
        return False

    def record_demo(self) -> FailureLesson:
        failure_data = {
            "failure_type": "conversion_drop",
            "creative_id": "creative_X",
            "audience_id": "audience_Wrong",
            "ctr_ok": True,
            "purchase_low": True,
        }
        return self.record_failure(failure_data)
