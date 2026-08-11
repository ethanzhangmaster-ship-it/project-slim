"""Template System - 强约束布局模板系统

禁止自由生成布局。所有 creative 必须绑定 template_id。

Template Types:
  1. Merge Formula Template: A + B = C
  2. Evolution Chain Template: 1 → 2 → 3 → MAX
  3. Before/After Transformation Template
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .creative_dna_v2 import VisualHierarchySpec


@dataclass
class LayoutRegion:
    name: str
    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float
    visual_weight: float
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "x_ratio": self.x_ratio,
            "y_ratio": self.y_ratio,
            "width_ratio": self.width_ratio,
            "height_ratio": self.height_ratio,
            "visual_weight": self.visual_weight,
            "description": self.description,
        }


@dataclass
class AdTemplate:
    template_id: str
    template_name: str
    mechanism_type: str
    attention_goal: str
    
    regions: List[LayoutRegion] = field(default_factory=list)
    visual_hierarchy: VisualHierarchySpec = field(default_factory=VisualHierarchySpec)
    
    psychology_drives: List[str] = field(default_factory=list)
    
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "mechanism_type": self.mechanism_type,
            "attention_goal": self.attention_goal,
            "regions": [r.to_dict() for r in self.regions],
            "visual_hierarchy": self.visual_hierarchy.to_dict(),
            "psychology_drives": self.psychology_drives,
            "prompt_prefix": self.prompt_prefix,
            "prompt_suffix": self.prompt_suffix,
        }


class TemplateLibrary:
    _templates: Dict[str, AdTemplate] = {}
    
    @classmethod
    def get_all(cls) -> List[AdTemplate]:
        if not cls._templates:
            cls._init_templates()
        return list(cls._templates.values())
    
    @classmethod
    def get(cls, template_id: str) -> Optional[AdTemplate]:
        if not cls._templates:
            cls._init_templates()
        return cls._templates.get(template_id)
    
    @classmethod
    def get_by_mechanism(cls, mechanism_type: str) -> List[AdTemplate]:
        if not cls._templates:
            cls._init_templates()
        return [t for t in cls._templates.values() if t.mechanism_type == mechanism_type]
    
    @classmethod
    def _init_templates(cls):
        cls._templates = {}
        
        cls._templates["merge_formula"] = AdTemplate(
            template_id="merge_formula",
            template_name="Merge Formula (A + B = C)",
            mechanism_type="merge",
            attention_goal="reward_first",
            regions=[
                LayoutRegion(
                    name="logo",
                    x_ratio=0.5, y_ratio=0.08,
                    width_ratio=0.35, height_ratio=0.08,
                    visual_weight=0.08,
                    description="Game logo at top center",
                ),
                LayoutRegion(
                    name="result_c",
                    x_ratio=0.5, y_ratio=0.45,
                    width_ratio=0.45, height_ratio=0.4,
                    visual_weight=0.45,
                    description="Merge result C - glowing, L1 visual focus",
                ),
                LayoutRegion(
                    name="item_a",
                    x_ratio=0.22, y_ratio=0.45,
                    width_ratio=0.22, height_ratio=0.3,
                    visual_weight=0.2,
                    description="Item A - left side",
                ),
                LayoutRegion(
                    name="item_b",
                    x_ratio=0.78, y_ratio=0.45,
                    width_ratio=0.22, height_ratio=0.3,
                    visual_weight=0.2,
                    description="Item B - right side",
                ),
                LayoutRegion(
                    name="plus_sign",
                    x_ratio=0.38, y_ratio=0.42,
                    width_ratio=0.05, height_ratio=0.08,
                    visual_weight=0.07,
                    description="Plus sign between A and B",
                ),
                LayoutRegion(
                    name="equals_sign",
                    x_ratio=0.5, y_ratio=0.32,
                    width_ratio=0.06, height_ratio=0.05,
                    visual_weight=0.05,
                    description="Equals sign pointing to result",
                ),
                LayoutRegion(
                    name="character_hands",
                    x_ratio=0.12, y_ratio=0.55,
                    width_ratio=0.76, height_ratio=0.25,
                    visual_weight=0.1,
                    description="Witch character hands reaching in from sides",
                ),
                LayoutRegion(
                    name="cta_banner",
                    x_ratio=0.5, y_ratio=0.90,
                    width_ratio=0.7, height_ratio=0.1,
                    visual_weight=0.07,
                    description="Decorative text banner at bottom",
                ),
            ],
            visual_hierarchy=VisualHierarchySpec(
                level1="result_c",
                level2="merge_process",
                level3="character_hands",
                level4="cta_banner",
            ),
            psychology_drives=[
                "reward_anticipation",
                "completion_bias",
                "collection_motivation",
                "fantasy_appeal",
            ],
            prompt_prefix=(
                "merge game screenshot, A + B = C formula layout, "
                "glowing merge result in center as main focus, "
                "two items on left and right with plus sign, "
                "witch character hands reaching in from sides, "
            ),
            prompt_suffix=(
                "dark purple background, magical glow effects, "
                "9:16 vertical, high contrast, reward-first visual hierarchy"
            ),
        )
        
        cls._templates["evolution_chain"] = AdTemplate(
            template_id="evolution_chain",
            template_name="Evolution Chain (1 → 2 → 3 → MAX)",
            mechanism_type="evolution",
            attention_goal="reward_first",
            regions=[
                LayoutRegion(
                    name="logo",
                    x_ratio=0.5, y_ratio=0.07,
                    width_ratio=0.3, height_ratio=0.07,
                    visual_weight=0.07,
                    description="Game logo at top",
                ),
                LayoutRegion(
                    name="final_form",
                    x_ratio=0.75, y_ratio=0.45,
                    width_ratio=0.35, height_ratio=0.5,
                    visual_weight=0.4,
                    description="Final/M MAX evolution form - largest, L1 focus",
                ),
                LayoutRegion(
                    name="stage1",
                    x_ratio=0.15, y_ratio=0.65,
                    width_ratio=0.15, height_ratio=0.2,
                    visual_weight=0.08,
                    description="Stage 1 - smallest, starting point",
                ),
                LayoutRegion(
                    name="stage2",
                    x_ratio=0.32, y_ratio=0.58,
                    width_ratio=0.18, height_ratio=0.28,
                    visual_weight=0.15,
                    description="Stage 2 - medium size",
                ),
                LayoutRegion(
                    name="stage3",
                    x_ratio=0.52, y_ratio=0.5,
                    width_ratio=0.22, height_ratio=0.38,
                    visual_weight=0.25,
                    description="Stage 3 - larger",
                ),
                LayoutRegion(
                    name="arrows",
                    x_ratio=0.35, y_ratio=0.55,
                    width_ratio=0.3, height_ratio=0.05,
                    visual_weight=0.05,
                    description="Evolution arrows between stages",
                ),
                LayoutRegion(
                    name="character",
                    x_ratio=0.12, y_ratio=0.35,
                    width_ratio=0.2, height_ratio=0.35,
                    visual_weight=0.12,
                    description="Witch character at left side, observing evolution",
                ),
                LayoutRegion(
                    name="cta_banner",
                    x_ratio=0.5, y_ratio=0.92,
                    width_ratio=0.7, height_ratio=0.08,
                    visual_weight=0.06,
                    description="Text banner at bottom",
                ),
            ],
            visual_hierarchy=VisualHierarchySpec(
                level1="final_form",
                level2="evolution_path",
                level3="character",
                level4="cta_banner",
            ),
            psychology_drives=[
                "collection_motivation",
                "progression_satisfaction",
                "reward_anticipation",
                "completion_bias",
            ],
            prompt_prefix=(
                "evolution chain game illustration, bottom-up progression, "
                "small form on left growing to giant final form on right, "
                "final evolved creature as main focus glowing brightly, "
                "numbered stages with arrows showing progression, "
                "witch character watching from side, "
            ),
            prompt_suffix=(
                "fantasy magic style, purple and gold palette, "
                "9:16 vertical, collection-driven visual hierarchy"
            ),
        )
        
        cls._templates["before_after"] = AdTemplate(
            template_id="before_after",
            template_name="Before/After Transformation",
            mechanism_type="transformation",
            attention_goal="reward_first",
            regions=[
                LayoutRegion(
                    name="logo",
                    x_ratio=0.5, y_ratio=0.06,
                    width_ratio=0.3, height_ratio=0.06,
                    visual_weight=0.06,
                    description="Logo at top",
                ),
                LayoutRegion(
                    name="after_side",
                    x_ratio=0.72, y_ratio=0.48,
                    width_ratio=0.45, height_ratio=0.6,
                    visual_weight=0.42,
                    description="After/reward side - right, brighter, L1 focus",
                ),
                LayoutRegion(
                    name="before_side",
                    x_ratio=0.28, y_ratio=0.52,
                    width_ratio=0.45, height_ratio=0.5,
                    visual_weight=0.28,
                    description="Before/low state - left, dimmer",
                ),
                LayoutRegion(
                    name="divider",
                    x_ratio=0.5, y_ratio=0.5,
                    width_ratio=0.03, height_ratio=0.7,
                    visual_weight=0.08,
                    description="Vertical divider with arrow pointing right",
                ),
                LayoutRegion(
                    name="character",
                    x_ratio=0.15, y_ratio=0.5,
                    width_ratio=0.18, height_ratio=0.3,
                    visual_weight=0.1,
                    description="Character shown in both states or in middle",
                ),
                LayoutRegion(
                    name="cta_banner",
                    x_ratio=0.5, y_ratio=0.92,
                    width_ratio=0.7, height_ratio=0.08,
                    visual_weight=0.06,
                    description="Bottom text banner",
                ),
            ],
            visual_hierarchy=VisualHierarchySpec(
                level1="after_side",
                level2="transformation",
                level3="character",
                level4="cta_banner",
            ),
            psychology_drives=[
                "reward_anticipation",
                "progress_satisfaction",
                "self_projection",
                "curiosity_gap",
            ],
            prompt_prefix=(
                "before and after transformation split-screen, "
                "left side messy/low state, right side clean/rewarded state, "
                "right side brighter and more detailed as L1 focus, "
                "vertical divider with arrow pointing right, "
                "transformation clearly visible, "
            ),
            prompt_suffix=(
                "merge game art style, magical transformation glow, "
                "9:16 vertical, reward-first visual hierarchy"
            ),
        )
    
    @classmethod
    def validate_template_id(cls, template_id: str) -> bool:
        if not cls._templates:
            cls._init_templates()
        return template_id in cls._templates
    
    @classmethod
    def list_template_ids(cls) -> List[str]:
        if not cls._templates:
            cls._init_templates()
        return list(cls._templates.keys())
