"""Creative DNA V2 - Inference-centric Creative System

从 Image-centric learning → Inference-centric creative system

核心思想：
  系统目标不是 generate better images
  而是 generate creatives that maximize inference completion within 1 second
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


MECHANISM_TYPES = [
    "merge",
    "evolution",
    "collection",
    "progression_chain",
    "transformation",
    "comparison",
]

REWARD_TYPES = [
    "transformation",
    "collection",
    "unlock",
    "upgrade",
    "discovery",
    "power_up",
    "legendary_item",
]

HOOK_TYPES = [
    "collection",
    "transformation",
    "challenge",
    "secret",
    "curiosity",
    "progression",
    "achievement",
]

LAYOUT_TEMPLATES = [
    "merge_formula",
    "evolution_chain",
    "before_after_transformation",
]

VISUAL_LEVELS = ["level1", "level2", "level3", "level4"]

ATTENTION_GOALS = [
    "reward_first",
    "mechanism_first",
]

PSYCHOLOGY_DRIVES = [
    "collection_motivation",
    "completion_bias",
    "reward_anticipation",
    "curiosity_gap",
    "fantasy_appeal",
    "self_projection",
    "progress_satisfaction",
]


@dataclass
class VisualHierarchySpec:
    level1: str = ""
    level2: str = ""
    level3: str = ""
    level4: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "level1": self.level1,
            "level2": self.level2,
            "level3": self.level3,
            "level4": self.level4,
        }


@dataclass
class CreativeDNAV2:
    dna_id: str = ""
    
    mechanism_type: str = ""
    reward_type: str = ""
    hook_type: str = ""
    layout_template: str = ""
    
    visual_hierarchy: VisualHierarchySpec = field(default_factory=VisualHierarchySpec)
    
    attention_goal: str = "reward_first"
    psychology_drive: List[str] = field(default_factory=list)
    
    mechanism_visibility_score: float = 0.0
    reward_salience_score: float = 0.0
    identity_projection_score: float = 0.0
    visual_hierarchy_match: float = 0.0
    scroll_stop_score: float = 0.0
    
    total_score: float = 0.0
    
    is_rejected: bool = False
    reject_reasons: List[str] = field(default_factory=list)
    
    user_role_mapping: str = "player_who_merges"
    
    source_creative_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dna_id": self.dna_id,
            "mechanism_type": self.mechanism_type,
            "reward_type": self.reward_type,
            "hook_type": self.hook_type,
            "layout_template": self.layout_template,
            "visual_hierarchy": self.visual_hierarchy.to_dict(),
            "attention_goal": self.attention_goal,
            "psychology_drive": self.psychology_drive,
            "mechanism_visibility_score": self.mechanism_visibility_score,
            "reward_salience_score": self.reward_salience_score,
            "identity_projection_score": self.identity_projection_score,
            "visual_hierarchy_match": self.visual_hierarchy_match,
            "scroll_stop_score": self.scroll_stop_score,
            "total_score": self.total_score,
            "is_rejected": self.is_rejected,
            "reject_reasons": self.reject_reasons,
            "user_role_mapping": self.user_role_mapping,
            "source_creative_id": self.source_creative_id,
        }


class HierarchyRules:
    STANDARD_HIERARCHY = VisualHierarchySpec(
        level1="reward",
        level2="mechanism",
        level3="brand_character",
        level4="ui_cta",
    )
    
    @classmethod
    def validate(cls, hierarchy: VisualHierarchySpec) -> tuple[bool, List[str]]:
        reasons = []
        
        if hierarchy.level1 == "character" or hierarchy.level1 == "brand":
            reasons.append("Character must not be L1 visual hierarchy")
        
        if hierarchy.level1 != "reward" and hierarchy.level1 != "mechanism_result":
            reasons.append(f"Reward must be L1, got L1={hierarchy.level1}")
        
        if hierarchy.level2 not in ["mechanism", "merge_process", "evolution_path"]:
            reasons.append(f"Mechanism should be L2, got L2={hierarchy.level2}")
        
        passed = len(reasons) == 0
        return passed, reasons
