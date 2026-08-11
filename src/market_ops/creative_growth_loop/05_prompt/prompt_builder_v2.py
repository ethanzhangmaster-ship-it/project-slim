"""Prompt Builder V2 - Template-driven Constraint Prompt Generation

从"自由生成布局"改为"模板强约束生成"。

所有 creative 必须绑定 template_id，不允许 template-free generation。

Prompt 结构：
  [Template Prefix] + [Mechanism Description] + [Reward Description] 
  + [Visual Hierarchy Cues] + [Style Constraints] + [Template Suffix]
"""
from __future__ import annotations

import importlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

_PKG = "market_ops.creative_growth_loop"

_dna_module = importlib.import_module(f"{_PKG}.03_gene.creative_dna_v2")
CreativeDNAV2 = _dna_module.CreativeDNAV2

_template_module = importlib.import_module(f"{_PKG}.03_gene.template_library")
TemplateLibrary = _template_module.TemplateLibrary
AdTemplate = _template_module.AdTemplate
LayoutRegion = _template_module.LayoutRegion


MERGE_ITEMS = [
    "cute witch hat",
    "magic cauldron",
    "crystal ball",
    "flying broom",
    "spell book",
    "magic potion",
    "star wand",
    "moon lantern",
    "mushroom house",
    "dragon egg",
]

EVOLUTION_FORMS = [
    "tiny forest spirit",
    "small magical creature",
    "medium fantasy beast",
    "large mythical guardian",
    "ancient legendary titan",
]

REWARD_VARIANTS = {
    "transformation": [
        "complete transformation reveal",
        "full evolution final form",
        "ultimate merged creature",
    ],
    "collection": [
        "complete collection showcase",
        "full set of magical items",
        "all creatures gathered together",
    ],
    "unlock": [
        "secret legendary item revealed",
        "hidden power unlocked",
        "mystery treasure discovered",
    ],
    "upgrade": [
        "powerful upgraded form",
        "enhanced magical ability",
        "boosted legendary creature",
    ],
    "legendary_item": [
        "glowing legendary item",
        "mythic golden artifact",
        "ancient magical relic",
    ],
}

HOOK_VARIANTS = {
    "collection": [
        "collect them all",
        "complete the set",
        "gather every creature",
    ],
    "transformation": [
        "watch the transformation",
        "see the epic change",
        "amazing evolution reveal",
    ],
    "challenge": [
        "can you merge this",
        "test your merging skills",
        "try to create this",
    ],
    "secret": [
        "unlock the secret",
        "discover what's hidden",
        "find the mystery creature",
    ],
    "curiosity": [
        "what happens when you merge",
        "guess the result",
        "can you figure it out",
    ],
    "progression": [
        "level up your creatures",
        "evolve to the max",
        "grow your power",
    ],
}


@dataclass
class TemplatePrompt:
    prompt_id: str
    prompt_text: str
    template_id: str
    mechanism_type: str
    reward_type: str
    hook_type: str
    visual_hierarchy: Dict[str, str]
    dna_reference: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "template_id": self.template_id,
            "mechanism_type": self.mechanism_type,
            "reward_type": self.reward_type,
            "hook_type": self.hook_type,
            "visual_hierarchy": self.visual_hierarchy,
            "dna_reference": self.dna_reference,
        }


class PromptBuilderV2:
    STYLE_BASE = (
        "3D cartoon style, Pixar quality, mobile game advertising, "
        "9:16 vertical aspect ratio, high contrast, vibrant colors"
    )
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/prompts_v2"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def build_prompts_from_dna(self, dna: CreativeDNAV2, 
                                count: int = 5) -> List[TemplatePrompt]:
        if not dna.layout_template or not TemplateLibrary.validate_template_id(dna.layout_template):
            raise ValueError(f"DNA must have valid template_id, got: {dna.layout_template}")
        
        template = TemplateLibrary.get(dna.layout_template)
        prompts = []
        
        for i in range(count):
            prompt = self._build_single_prompt(dna, template, i)
            prompts.append(prompt)
        
        self._save_prompts(prompts, dna.dna_id)
        return prompts
    
    def build_prompts_for_template(self, template_id: str, 
                                    mechanism_type: str = None,
                                    reward_type: str = None,
                                    hook_type: str = None,
                                    count: int = 5) -> List[TemplatePrompt]:
        if not TemplateLibrary.validate_template_id(template_id):
            raise ValueError(f"Invalid template_id: {template_id}")
        
        template = TemplateLibrary.get(template_id)
        
        dna = CreativeDNAV2(
            dna_id=f"dna_v2_gen_{uuid.uuid4().hex[:8]}",
            mechanism_type=mechanism_type or template.mechanism_type,
            reward_type=reward_type or "transformation",
            hook_type=hook_type or "curiosity",
            layout_template=template_id,
            attention_goal=template.attention_goal,
            psychology_drive=template.psychology_drives.copy(),
            visual_hierarchy=template.visual_hierarchy,
        )
        
        return self.build_prompts_from_dna(dna, count)
    
    def _build_single_prompt(self, dna: CreativeDNAV2, template: AdTemplate,
                             idx: int) -> TemplatePrompt:
        parts = []
        
        parts.append(template.prompt_prefix)
        
        mechanism_desc = self._build_mechanism_description(dna, template, idx)
        if mechanism_desc:
            parts.append(mechanism_desc)
        
        reward_desc = self._build_reward_description(dna, idx)
        if reward_desc:
            parts.append(reward_desc)
        
        hierarchy_cues = self._build_hierarchy_cues(dna, template)
        if hierarchy_cues:
            parts.append(hierarchy_cues)
        
        hook_desc = self._build_hook_description(dna, idx)
        if hook_desc:
            parts.append(hook_desc)
        
        parts.append(self.STYLE_BASE)
        
        if template.prompt_suffix:
            parts.append(template.prompt_suffix)
        
        final_prompt = ", ".join([p for p in parts if p])
        
        return TemplatePrompt(
            prompt_id=f"prompt_v2_{dna.dna_id}_{idx:03d}",
            prompt_text=final_prompt,
            template_id=template.template_id,
            mechanism_type=dna.mechanism_type,
            reward_type=dna.reward_type,
            hook_type=dna.hook_type,
            visual_hierarchy=template.visual_hierarchy.to_dict(),
            dna_reference=dna.dna_id,
        )
    
    def _build_mechanism_description(self, dna: CreativeDNAV2, 
                                      template: AdTemplate, idx: int) -> str:
        if template.template_id == "merge_formula":
            item_a = MERGE_ITEMS[idx % len(MERGE_ITEMS)]
            item_b = MERGE_ITEMS[(idx + 3) % len(MERGE_ITEMS)]
            return (
                f"merging {item_a} and {item_b}, "
                f"magical fusion process with sparkles and glow, "
                f"two items floating with plus sign between them"
            )
        
        elif template.template_id == "evolution_chain":
            forms = EVOLUTION_FORMS
            return (
                f"evolution chain showing progression from {forms[0]} to {forms[-1]}, "
                f"four stages of growth, getting larger and more powerful, "
                f"arrows showing evolution direction"
            )
        
        elif template.template_id == "before_after":
            return (
                f"before and after transformation comparison, "
                f"left side small and basic form, right side powerful evolved form, "
                f"vertical split screen with transformation arrow"
            )
        
        return ""
    
    def _build_reward_description(self, dna: CreativeDNAV2, idx: int) -> str:
        variants = REWARD_VARIANTS.get(dna.reward_type, REWARD_VARIANTS["transformation"])
        reward_desc = variants[idx % len(variants)]
        
        visual_cues = (
            f"{reward_desc}, "
            f"glowing brightly as main focal point, "
            f"largest element in the composition, "
            f"magical aura and sparkles around it, "
            f"positioned prominently as L1 visual"
        )
        
        return visual_cues
    
    def _build_hierarchy_cues(self, dna: CreativeDNAV2, template: AdTemplate) -> str:
        cues = []
        
        l1 = template.visual_hierarchy.level1
        if l1:
            cues.append(f"{l1} is largest and brightest element")
        
        l2 = template.visual_hierarchy.level2
        if l2:
            cues.append(f"{l2} is secondary focus")
        
        cues.append("character never in center foreground")
        cues.append("reward always most visually prominent")
        
        return "; ".join(cues)
    
    def _build_hook_description(self, dna: CreativeDNAV2, idx: int) -> str:
        variants = HOOK_VARIANTS.get(dna.hook_type, HOOK_VARIANTS["curiosity"])
        hook_text = variants[idx % len(variants)]
        return f"hook: {hook_text}"
    
    def _save_prompts(self, prompts: List[TemplatePrompt], dna_id: str) -> Path:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prompts_v2_{dna_id}_{timestamp}.json"
        output_path = self.output_dir / filename
        
        data = [p.to_dict() for p in prompts]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def generate_batch(self, template_ids: List[str] = None,
                       count_per_template: int = 3) -> List[TemplatePrompt]:
        if template_ids is None:
            template_ids = TemplateLibrary.list_template_ids()
        
        all_prompts = []
        
        for template_id in template_ids:
            try:
                prompts = self.build_prompts_for_template(
                    template_id=template_id,
                    count=count_per_template,
                )
                all_prompts.extend(prompts)
            except Exception as e:
                print(f"Failed to generate prompts for template {template_id}: {e}")
        
        return all_prompts
