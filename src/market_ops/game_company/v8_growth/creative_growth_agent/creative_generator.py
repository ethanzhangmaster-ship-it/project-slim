from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import random


class CreativeType(Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    PLAYABLE = "playable"


class CreativeStatus(Enum):
    DRAFT = "draft"
    READY = "ready"
    TESTING = "testing"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class CreativeConcept:
    concept_id: str
    name: str
    description: str
    target_audience: str = ""
    key_message: str = ""
    emotional_hooks: List[str] = field(default_factory=list)
    creative_type: CreativeType = CreativeType.IMAGE
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "description": self.description,
            "target_audience": self.target_audience,
            "key_message": self.key_message,
            "emotional_hooks": self.emotional_hooks,
            "creative_type": self.creative_type.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CreativeTemplate:
    template_id: str
    name: str
    type: CreativeType
    elements: Dict[str, Any] = field(default_factory=dict)
    performance_history: List[float] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "type": self.type.value,
            "elements": self.elements,
            "performance_history": self.performance_history,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
        }


@dataclass
class GeneratedCreative:
    creative_id: str
    concept_id: str
    template_id: str
    name: str
    type: CreativeType
    elements: Dict[str, Any] = field(default_factory=dict)
    status: CreativeStatus = CreativeStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "concept_id": self.concept_id,
            "template_id": self.template_id,
            "name": self.name,
            "type": self.type.value,
            "elements": self.elements,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


class CreativeGenerator:
    def __init__(self):
        self._concepts: Dict[str, CreativeConcept] = {}
        self._templates: Dict[str, CreativeTemplate] = {}
        self._creatives: Dict[str, GeneratedCreative] = {}
        self._init_default_templates()

    def _init_default_templates(self):
        default_templates = [
            CreativeTemplate(
                template_id="tpl_001",
                name="Hero Image",
                type=CreativeType.IMAGE,
                elements={"headline": "top", "image": "center", "cta": "bottom"},
                success_rate=0.45,
            ),
            CreativeTemplate(
                template_id="tpl_002",
                name="Video Story",
                type=CreativeType.VIDEO,
                elements={"hook": "first_3s", "story": "middle", "cta": "end"},
                success_rate=0.52,
            ),
            CreativeTemplate(
                template_id="tpl_003",
                name="Feature Carousel",
                type=CreativeType.CAROUSEL,
                elements={"cards": 5, "flow": "left_to_right"},
                success_rate=0.48,
            ),
            CreativeTemplate(
                template_id="tpl_004",
                name="Playable Demo",
                type=CreativeType.PLAYABLE,
                elements={"duration": "15s", "interaction": "tap"},
                success_rate=0.55,
            ),
        ]
        for template in default_templates:
            self._templates[template.template_id] = template

    def generate_concepts(self, brief: Dict[str, Any], num_concepts: int = 5) -> List[CreativeConcept]:
        concepts = []
        target_audience = brief.get("target_audience", "general users")
        key_messages = brief.get("key_messages", ["discover", "play", "win"])
        emotional_hooks = brief.get("emotional_hooks", ["excitement", "achievement", "competition"])

        concept_names = [
            "Challenge Mode",
            "Victory Path",
            "Epic Journey",
            "Champion Rise",
            "Power Up",
            "Quest Begin",
            "Legend Awaits",
            "Glory Call",
            "Battle Ready",
            "Hero's Choice",
        ]

        for i in range(min(num_concepts, len(concept_names))):
            concept_id = f"concept_{datetime.now().strftime('%Y%m%d')}_{i+1}"
            concept = CreativeConcept(
                concept_id=concept_id,
                name=concept_names[i],
                description=f"Creative concept focusing on {key_messages[i % len(key_messages)]}",
                target_audience=target_audience,
                key_message=key_messages[i % len(key_messages)],
                emotional_hooks=[emotional_hooks[i % len(emotional_hooks)]],
                creative_type=random.choice(list(CreativeType)),
            )
            concepts.append(concept)
            self._concepts[concept_id] = concept

        return concepts

    def generate_creatives(
        self,
        concept_id: str,
        template_id: str = None,
        num_creatives: int = 3,
        variations: Dict[str, Any] = None
    ) -> List[GeneratedCreative]:
        concept = self._concepts.get(concept_id)
        if not concept:
            return []

        if template_id:
            template = self._templates.get(template_id)
            templates = [template] if template else []
        else:
            templates = list(self._templates.values())

        creatives = []
        for i, template in enumerate(templates[:num_creatives]):
            creative_id = f"creative_{concept_id}_{i+1}"
            elements = dict(template.elements)
            if variations:
                elements.update(variations)

            creative = GeneratedCreative(
                creative_id=creative_id,
                concept_id=concept_id,
                template_id=template.template_id,
                name=f"{concept.name} - Variation {i+1}",
                type=template.type,
                elements=elements,
                status=CreativeStatus.DRAFT,
            )
            creatives.append(creative)
            self._creatives[creative_id] = creative

        return creatives

    def get_templates(self, creative_type: CreativeType = None) -> List[CreativeTemplate]:
        templates = list(self._templates.values())
        if creative_type:
            templates = [t for t in templates if t.type == creative_type]
        return sorted(templates, key=lambda t: t.success_rate, reverse=True)

    def add_template(self, template: CreativeTemplate) -> CreativeTemplate:
        self._templates[template.template_id] = template
        return template

    def get_concept(self, concept_id: str) -> Optional[CreativeConcept]:
        return self._concepts.get(concept_id)

    def get_creative(self, creative_id: str) -> Optional[GeneratedCreative]:
        return self._creatives.get(creative_id)

    def get_all_concepts(self) -> List[CreativeConcept]:
        return list(self._concepts.values())

    def get_all_creatives(self) -> List[GeneratedCreative]:
        return list(self._creatives.values())

    def update_creative_status(self, creative_id: str, status: CreativeStatus) -> Optional[GeneratedCreative]:
        creative = self._creatives.get(creative_id)
        if creative:
            creative.status = status
        return creative

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_concepts": len(self._concepts),
            "total_templates": len(self._templates),
            "total_creatives": len(self._creatives),
            "creatives_by_status": {
                status.value: sum(1 for c in self._creatives.values() if c.status == status)
                for status in CreativeStatus
            },
            "creatives_by_type": {
                ctype.value: sum(1 for c in self._creatives.values() if c.type == ctype)
                for ctype in CreativeType
            },
        }