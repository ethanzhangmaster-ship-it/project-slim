"""Prompt Builder - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from ..03_gene.gene_extractor import CreativeGene
from ..03_gene.gene_memory import GeneLock
from ..04_mutation.hook_mutator import HookMutation


@dataclass
class VariantPrompt:
    prompt_id: str
    prompt_text: str
    hook: str
    reward: str
    emotion: str
    progress: str
    overlay: str
    mutation_type: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "hook": self.hook,
            "reward": self.reward,
            "emotion": self.emotion,
            "progress": self.progress,
            "overlay": self.overlay,
            "mutation_type": self.mutation_type,
        }


class PromptBuilder:
    STYLE_TEMPLATES = {
        "3D cartoon": "3D Pixar style, cute character design",
        "dark fantasy": "dark fantasy art, atmospheric lighting",
        "anime": "anime style, vibrant colors",
        "realistic": "photorealistic, high detail",
    }
    
    EMOTION_EXPRESSIONS = {
        "surprise": "surprised expression, wide eyes, shocked face",
        "panic": "panic expression, worried face, dramatic",
        "happy": "happy expression, smiling, joyful",
        "wow": "amazed expression, wow face, impressed",
        "cry": "sad expression, crying, emotional",
        "angry": "angry expression, fierce, intense",
        "excited": "excited expression, thrilled, energetic",
        "curious": "curious expression, wondering, intrigued",
        "mysterious": "mysterious expression, enigmatic, secretive",
    }
    
    def __init__(self, output_dir: str = "output/creative_growth_loop/prompts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.gene_lock = GeneLock()
    
    def build_prompts(self, gene: CreativeGene, mutations: List[Dict[str, Any]], 
                      count: int = 20) -> List[VariantPrompt]:
        """构建变体提示词"""
        prompts = []
        
        self.gene_lock.lock_from_winner(gene)
        
        for i, mutation in enumerate(mutations[:count]):
            prompt = self._build_single_prompt(gene, mutation, i)
            prompts.append(prompt)
        
        self._save_prompts(prompts)
        return prompts
    
    def _build_single_prompt(self, gene: CreativeGene, mutation: Dict[str, Any], 
                             idx: int) -> VariantPrompt:
        """构建单个提示词"""
        prompt_parts = []
        
        style = gene.style
        style_template = self.STYLE_TEMPLATES.get(style, style)
        prompt_parts.append(style_template)
        
        subject = gene.subject
        if "subject_value" in mutation:
            subject = mutation["subject_value"]
        prompt_parts.append(subject)
        
        hook = mutation.get("hook_text", gene.hook)
        hook_type = mutation.get("hook_type", "unknown")
        
        reward = gene.reward
        if "reward_value" in mutation:
            reward = mutation["reward_value"]
        if reward and reward != "unknown":
            prompt_parts.append(f"holding {reward}")
        
        emotion = gene.emotion
        if "emotion_value" in mutation:
            emotion = mutation["emotion_value"]
        emotion_expr = self.EMOTION_EXPRESSIONS.get(emotion, "")
        if emotion_expr:
            prompt_parts.append(emotion_expr)
        
        progress = gene.progress
        if "progress_value" in mutation:
            progress = mutation["progress_value"]
        
        overlay = gene.overlay
        if "overlay_value" in mutation:
            overlay = mutation["overlay_value"]
        
        prompt_parts.append(f"set in {gene.background}")
        
        locked_genes = self.gene_lock.get_locked_genes()
        if "composition" in locked_genes:
            prompt_parts.append(f"{locked_genes['composition']} composition")
        
        if "camera" in locked_genes:
            prompt_parts.append(f"{locked_genes['camera']} angle")
        
        prompt_parts.extend([
            "high quality",
            "professional advertising",
            "mobile game ad",
            "9:16 aspect ratio",
        ])
        
        prompt_text = ", ".join(prompt_parts)
        
        mutation_type = mutation.get("hook_type", mutation.get("reward_type", 
                             mutation.get("emotion_type", "unknown")))
        
        return VariantPrompt(
            prompt_id=f"prompt_{idx:03d}",
            prompt_text=prompt_text,
            hook=hook,
            reward=reward,
            emotion=emotion,
            progress=progress,
            overlay=overlay,
            mutation_type=mutation_type,
        )
    
    def _save_prompts(self, prompts: List[VariantPrompt]) -> Path:
        """保存提示词"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"prompts_{timestamp}.json"
        output_path = self.output_dir / filename
        
        data = [p.to_dict() for p in prompts]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def build_overlay_prompt(self, base_prompt: str, overlay_type: str) -> str:
        """构建Overlay提示词"""
        overlay_descriptions = {
            "Arrow": "with red arrow pointing at main subject",
            "Circle": "with glowing circle highlighting reward",
            "Glow": "with magical glow effect around character",
            "Text": "with bold text overlay",
            "+999": "with +999 score badge",
            "NEW": "with NEW badge",
            "SECRET": "with SECRET badge",
            "LEVEL100": "with LEVEL 100 badge",
            "Question Mark": "with question mark overlay",
        }
        
        overlay_desc = overlay_descriptions.get(overlay_type, "")
        if overlay_desc:
            return f"{base_prompt}, {overlay_desc}"
        
        return base_prompt