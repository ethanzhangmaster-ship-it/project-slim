"""Prompt Builder - 将ImagePattern+ Mutation组合为VariantPrompt (DEPRECATED)
Use market_ops.creative_growth_loop.05_prompt.prompt_builder instead.
"""
from __future__ import annotations

from market_ops.deprecated import module_deprecated
module_deprecated(since="2026-06", use_instead="market_ops.creative_growth_loop.05_prompt.prompt_builder")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from .pattern_engine import ImagePattern
from .mutation_engine import Mutation, MutationType


@dataclass
class VariantPrompt:
    prompt_text: str
    mutation: Mutation
    mutation_axis: str
    hook_type: str
    reference_image_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_text": self.prompt_text,
            "mutation_type": self.mutation.mutation_type.value,
            "mutation_axis": self.mutation_axis,
            "hook_type": self.hook_type,
            "reference_image_url": self.reference_image_url,
            "mutation_description": self.mutation.description,
        }


class PromptBuilder:
    STYLE_TEMPLATES = {
        "3D cartoon": "3D Pixar style",
        "dark fantasy": "dark fantasy art style",
        "cinematic": "cinematic 3D rendering",
        "anime": "anime style",
        "pixel art": "pixel art style",
        "watercolor": "watercolor painting",
        "photorealistic": "photorealistic",
        "hand drawn": "hand drawn illustration",
    }

    HOOK_TEMPLATES = {
        "collection": "collectible, cute, appealing for collection",
        "transformation": "transformation, evolution, progression",
        "gameplay": "gameplay demonstration, action, fun",
        "narrative": "storytelling, mysterious, intriguing",
        "social": "friends, community, together",
        "achievement": "achievement, reward, victory",
    }

    def __init__(self, output_dir: str = "output/creative_loop_v2/prompts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_prompts(self, pattern: ImagePattern, mutations: List[Mutation]) -> List[VariantPrompt]:
        prompts: List[VariantPrompt] = []
        
        for mutation in mutations:
            prompt = self._build_single_prompt(pattern, mutation)
            if prompt:
                prompts.append(prompt)
        
        self._save_prompts(prompts)
        return prompts

    def _build_single_prompt(self, pattern: ImagePattern, mutation: Mutation) -> VariantPrompt:
        style = self.STYLE_TEMPLATES.get(pattern.style, pattern.style)
        hook_desc = self.HOOK_TEMPLATES.get(pattern.hook, pattern.hook)
        
        subject = self._apply_subject_mutation(pattern.subject, mutation)
        background = self._apply_background_mutation(pattern.background, mutation)
        lighting = self._apply_lighting_mutation(pattern.lighting, mutation)
        emotion = self._apply_emotion_mutation(pattern.emotion, mutation)
        pose = self._apply_pose_mutation(pattern.character_pose, mutation)
        palette = self._apply_color_mutation(pattern.palette, mutation)
        costume = self._apply_costume_mutation(mutation)
        
        prompt_parts = [
            f"{style} {subject}",
        ]
        
        if costume:
            prompt_parts.append(f"{costume} outfit")
        if pose:
            prompt_parts.append(f"{pose} pose")
        if emotion:
            prompt_parts.append(f"{emotion} expression")
        if background:
            prompt_parts.append(f"set in {background}")
        if palette:
            prompt_parts.append(f"color palette: {palette}")
        if lighting:
            prompt_parts.append(f"{lighting} lighting")
        if hook_desc:
            prompt_parts.append(hook_desc)
        
        prompt_parts.extend([
            "high detail",
            "professional advertising quality",
            "mobile ad format",
            "9:16 aspect ratio",
        ])
        
        prompt_text = ",\n".join(prompt_parts)
        
        return VariantPrompt(
            prompt_text=prompt_text,
            mutation=mutation,
            mutation_axis=mutation.mutation_type.value,
            hook_type=pattern.hook,
        )

    def _apply_subject_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.SUBJECT_SWAP:
            return mutation.new_value
        return original

    def _apply_background_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.BACKGROUND_SWAP:
            return mutation.new_value
        return original

    def _apply_lighting_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.LIGHTING_SWAP:
            return mutation.new_value
        return original

    def _apply_emotion_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.EMOTION_SWAP:
            return mutation.new_value
        return original

    def _apply_pose_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.POSE_SWAP:
            return mutation.new_value
        return original

    def _apply_color_mutation(self, original: str, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.COLOR_SWAP:
            return mutation.new_value
        return original

    def _apply_costume_mutation(self, mutation: Mutation) -> str:
        if mutation.mutation_type == MutationType.COSTUME_SWAP:
            return mutation.new_value
        return ""

    def _save_prompts(self, prompts: List[VariantPrompt]) -> Path:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prompts_{timestamp}.json"
        output_path = self.output_dir / filename
        
        data = [p.to_dict() for p in prompts]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path