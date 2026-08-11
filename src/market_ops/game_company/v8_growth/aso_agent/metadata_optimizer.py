from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class MetadataType(Enum):
    TITLE = "title"
    DESCRIPTION = "description"
    SHORT_DESCRIPTION = "short_description"
    ICON = "icon"
    SCREENSHOTS = "screenshots"
    VIDEO = "video"
    PROMO_GRAPHIC = "promo_graphic"


class OptimizationStatus(Enum):
    DRAFT = "draft"
    TESTING = "testing"
    LIVE = "live"
    ARCHIVED = "archived"


@dataclass
class MetadataElement:
    element_id: str
    type: MetadataType
    content: str
    version: int = 1
    status: OptimizationStatus = OptimizationStatus.LIVE
    performance_score: float = 0.0
    impressions: int = 0
    conversions: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "type": self.type.value,
            "content": self.content,
            "version": self.version,
            "status": self.status.value,
            "performance_score": self.performance_score,
            "impressions": self.impressions,
            "conversions": self.conversions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class MetadataVersion:
    version_id: str
    elements: Dict[MetadataType, MetadataElement] = field(default_factory=dict)
    overall_score: float = 0.0
    conversion_rate: float = 0.0
    is_current: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "elements": {k.value: v.to_dict() for k, v in self.elements.items()},
            "overall_score": self.overall_score,
            "conversion_rate": self.conversion_rate,
            "is_current": self.is_current,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MetadataRecommendation:
    element_type: MetadataType
    current_content: str
    suggested_content: str
    reason: str = ""
    expected_impact: float = 0.0
    confidence: float = 0.0
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_type": self.element_type.value,
            "current_content": self.current_content,
            "suggested_content": self.suggested_content,
            "reason": self.reason,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "priority": self.priority,
        }


class MetadataOptimizer:
    def __init__(self):
        self._elements: Dict[str, MetadataElement] = {}
        self._versions: Dict[str, MetadataVersion] = {}
        self._recommendations: List[MetadataRecommendation] = []
        self._current_version: Optional[str] = None
        self._character_limits = {
            MetadataType.TITLE: 30,
            MetadataType.SHORT_DESCRIPTION: 80,
            MetadataType.DESCRIPTION: 4000,
        }

    def set_metadata(self, type: MetadataType, content: str) -> MetadataElement:
        element_id = f"meta_{type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        element = MetadataElement(
            element_id=element_id,
            type=type,
            content=content,
            status=OptimizationStatus.LIVE,
            performance_score=random.uniform(0.5, 0.9),
        )
        self._elements[element_id] = element
        return element

    def analyze_metadata(self) -> Dict[str, Any]:
        analysis = {
            "total_elements": len(self._elements),
            "elements_by_type": {},
            "performance_summary": {},
            "issues": [],
            "strengths": [],
        }

        for meta_type in MetadataType:
            type_elements = [e for e in self._elements.values() if e.type == meta_type]
            analysis["elements_by_type"][meta_type.value] = len(type_elements)

            if type_elements:
                avg_score = sum(e.performance_score for e in type_elements) / len(type_elements)
                analysis["performance_summary"][meta_type.value] = {
                    "avg_score": avg_score,
                    "best_score": max(e.performance_score for e in type_elements),
                    "conversion_rate": sum(e.conversions for e in type_elements) / max(1, sum(e.impressions for e in type_elements)),
                }

        for element in self._elements.values():
            char_limit = self._character_limits.get(element.type)
            if char_limit and len(element.content) > char_limit:
                analysis["issues"].append(f"{element.type.value} exceeds character limit ({len(element.content)}/{char_limit})")
            if element.performance_score < 0.6:
                analysis["issues"].append(f"{element.type.value} has low performance score ({element.performance_score:.2f})")
            if element.performance_score > 0.85:
                analysis["strengths"].append(f"{element.type.value} performs well ({element.performance_score:.2f})")

        return analysis

    def optimize_metadata(self) -> List[MetadataRecommendation]:
        recommendations = []
        for element in self._elements.values():
            if element.type == MetadataType.TITLE:
                if len(element.content) < 20:
                    rec = MetadataRecommendation(
                        element_type=element.type,
                        current_content=element.content,
                        suggested_content=f"{element.content} - Best Game App",
                        reason="Title could be longer to include more keywords",
                        expected_impact=0.15,
                        confidence=0.8,
                        priority=1,
                    )
                    recommendations.append(rec)

            elif element.type == MetadataType.DESCRIPTION:
                if "download" not in element.content.lower() and "free" not in element.content.lower():
                    rec = MetadataRecommendation(
                        element_type=element.type,
                        current_content=element.content,
                        suggested_content=f"{element.content[:100]}... Download now for free!",
                        reason="Description lacks key conversion triggers",
                        expected_impact=0.2,
                        confidence=0.75,
                        priority=2,
                    )
                    recommendations.append(rec)

            elif element.type == MetadataType.SHORT_DESCRIPTION:
                if element.conversions / max(1, element.impressions) < 0.03:
                    rec = MetadataRecommendation(
                        element_type=element.type,
                        current_content=element.content,
                        suggested_content="Play now! Free mobile game",
                        reason="Short description conversion rate is low",
                        expected_impact=0.25,
                        confidence=0.85,
                        priority=1,
                    )
                    recommendations.append(rec)

        self._recommendations.extend(recommendations)
        return recommendations

    def generate_optimized_content(self, type: MetadataType, keywords: List[str] = None) -> str:
        templates = {
            MetadataType.TITLE: "Best {category} Game - Play Free",
            MetadataType.SHORT_DESCRIPTION: "The ultimate {category} experience. Download free now!",
            MetadataType.DESCRIPTION: """
Join millions of players in the most exciting {category} game!
- Easy to play, hard to master
- Beautiful graphics and smooth gameplay
- Regular updates with new content
- Compete with friends worldwide

Download now and start your adventure!
""".strip(),
        }

        template = templates.get(type, "")
        keywords = keywords or ["mobile", "game", "adventure"]
        category = keywords[0] if keywords else "game"

        content = template.replace("{category}", category)
        char_limit = self._character_limits.get(type)
        if char_limit:
            content = content[:char_limit]

        return content

    def create_version(self, elements: Dict[MetadataType, MetadataElement]) -> MetadataVersion:
        version_id = f"version_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        version = MetadataVersion(
            version_id=version_id,
            elements=elements,
            overall_score=random.uniform(0.6, 0.9),
            conversion_rate=random.uniform(0.02, 0.08),
            is_current=True,
        )

        if self._current_version:
            old_version = self._versions.get(self._current_version)
            if old_version:
                old_version.is_current = False

        self._versions[version_id] = version
        self._current_version = version_id
        return version

    def get_current_version(self) -> Optional[MetadataVersion]:
        if self._current_version:
            return self._versions.get(self._current_version)
        return None

    def get_element(self, element_id: str) -> Optional[MetadataElement]:
        return self._elements.get(element_id)

    def get_elements_by_type(self, type: MetadataType) -> List[MetadataElement]:
        return [e for e in self._elements.values() if e.type == type]

    def get_all_versions(self) -> List[MetadataVersion]:
        return list(self._versions.values())

    def get_recommendations(self) -> List[MetadataRecommendation]:
        return list(self._recommendations)

    def get_stats(self) -> Dict[str, Any]:
        elements = list(self._elements.values())
        return {
            "total_elements": len(elements),
            "elements_by_type": {
                t.value: sum(1 for e in elements if e.type == t)
                for t in MetadataType
            },
            "total_versions": len(self._versions),
            "current_version": self._current_version,
            "total_recommendations": len(self._recommendations),
            "average_performance": sum(e.performance_score for e in elements) / len(elements) if elements else 0,
        }