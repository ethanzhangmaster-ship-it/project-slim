"""Gene Extractor - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from market_ops.clients.lovart import LovartClient


@dataclass
class CreativeGene:
    creative_id: str
    subject: str
    style: str
    hook: str
    reward: str
    emotion: str
    progress: str
    overlay: str
    composition: str
    camera: str
    background: str
    palette: str
    character_pose: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "subject": self.subject,
            "style": self.style,
            "hook": self.hook,
            "reward": self.reward,
            "emotion": self.emotion,
            "progress": self.progress,
            "overlay": self.overlay,
            "composition": self.composition,
            "camera": self.camera,
            "background": self.background,
            "palette": self.palette,
            "character_pose": self.character_pose,
        }


class GeneExtractor:
    HOOK_TYPES = [
        "secret", "challenge", "warning", "wrong_choice", "before_after",
        "reward", "curiosity", "urgency", "social", "achievement"
    ]
    
    REWARD_TYPES = [
        "gold_dragon", "castle", "treasure", "diamond", "phoenix",
        "unicorn", "golden_tree", "magic_item", "legendary", "rare"
    ]
    
    EMOTION_TYPES = [
        "surprise", "panic", "happy", "wow", "cry", "angry",
        "excited", "curious", "proud", "mysterious"
    ]
    
    PROGRESS_TYPES = [
        "lv10", "lv50", "lv100", "ultimate", "secret",
        "final", "evolution", "max", "legendary"
    ]
    
    OVERLAY_TYPES = [
        "arrow", "circle", "glow", "text", "+999",
        "NEW", "SECRET", "LEVEL100", "question_mark"
    ]
    
    def __init__(self, output_dir: str = "memory"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lovart_client = LovartClient()
    
    def extract_gene(self, image_path: str, creative_id: str = None) -> CreativeGene:
        """从图片提取基因"""
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        creative_id = creative_id or image_path.stem
        
        try:
            visual_dna = self.lovart_client.describe_image(str(image_path))
            gene = self._parse_visual_dna(visual_dna, creative_id)
        except Exception:
            gene = self._fallback_gene(creative_id)
        
        self._save_gene(gene)
        return gene
    
    def _parse_visual_dna(self, visual_dna: Dict[str, Any], creative_id: str) -> CreativeGene:
        """解析视觉DNA"""
        dna = visual_dna.get("visual_dna", visual_dna)
        
        hook = self._classify_hook(dna)
        reward = self._classify_reward(dna)
        emotion = self._classify_emotion(dna)
        progress = self._classify_progress(dna)
        overlay = self._classify_overlay(dna)
        
        return CreativeGene(
            creative_id=creative_id,
            subject=dna.get("subject", "unknown"),
            style=dna.get("style", "3D cartoon"),
            hook=hook,
            reward=reward,
            emotion=emotion,
            progress=progress,
            overlay=overlay,
            composition=dna.get("composition", "centered"),
            camera=dna.get("camera", "portrait"),
            background=dna.get("background", "fantasy"),
            palette=dna.get("palette", ""),
            character_pose=dna.get("character_pose", ""),
        )
    
    def _classify_hook(self, dna: Dict[str, Any]) -> str:
        """分类Hook类型"""
        overlay_text = dna.get("overlay_text", "").lower()
        mood = dna.get("mood", "").lower()
        hook_type = dna.get("hook_type", "").lower()
        
        if "secret" in overlay_text or "secret" in hook_type:
            return "secret"
        if "challenge" in overlay_text or "can you" in overlay_text:
            return "challenge"
        if "warning" in overlay_text or "don't" in overlay_text:
            return "warning"
        if "before" in overlay_text or "after" in overlay_text:
            return "before_after"
        if "reward" in mood or "gold" in overlay_text:
            return "reward"
        if "curiosity" in mood or "?" in overlay_text:
            return "curiosity"
        
        return hook_type or "unknown"
    
    def _classify_reward(self, dna: Dict[str, Any]) -> str:
        """分类Reward类型"""
        subject = dna.get("subject", "").lower()
        standout = dna.get("standout_features", [])
        
        for reward in self.REWARD_TYPES:
            if reward.replace("_", " ") in subject:
                return reward
            for feature in standout:
                if reward.replace("_", " ") in str(feature).lower():
                    return reward
        
        return "unknown"
    
    def _classify_emotion(self, dna: Dict[str, Any]) -> str:
        """分类Emotion类型"""
        mood = dna.get("mood", "").lower()
        
        for emotion in self.EMOTION_TYPES:
            if emotion in mood:
                return emotion
        
        return "neutral"
    
    def _classify_progress(self, dna: Dict[str, Any]) -> str:
        """分类Progress类型"""
        overlay_text = dna.get("overlay_text", "").lower()
        
        for progress in self.PROGRESS_TYPES:
            if progress.lower() in overlay_text:
                return progress
        
        if "lv" in overlay_text:
            return "level"
        
        return "unknown"
    
    def _classify_overlay(self, dna: Dict[str, Any]) -> str:
        """分类Overlay类型"""
        ui_elements = dna.get("ui_elements", [])
        overlay_text = dna.get("overlay_text", "").lower()
        
        for overlay in self.OVERLAY_TYPES:
            if overlay.lower() in overlay_text:
                return overlay
            for element in ui_elements:
                if overlay.lower() in str(element).lower():
                    return overlay
        
        return "none"
    
    def _fallback_gene(self, creative_id: str) -> CreativeGene:
        """备用基因"""
        return CreativeGene(
            creative_id=creative_id,
            subject="fantasy creature",
            style="3D cartoon",
            hook="unknown",
            reward="unknown",
            emotion="neutral",
            progress="unknown",
            overlay="none",
            composition="centered",
            camera="portrait",
            background="fantasy world",
            palette="purple, gold",
            character_pose="standing",
        )
    
    def _save_gene(self, gene: CreativeGene) -> Path:
        """保存基因"""
        output_path = self.output_dir / f"{gene.creative_id}_gene.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(gene.to_dict(), f, indent=2, ensure_ascii=False)
        
        return output_path
    
    def load_gene(self, creative_id: str) -> Optional[CreativeGene]:
        """加载基因"""
        gene_path = self.output_dir / f"{creative_id}_gene.json"
        
        if gene_path.exists():
            with open(gene_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return CreativeGene(
                    creative_id=data["creative_id"],
                    subject=data["subject"],
                    style=data["style"],
                    hook=data["hook"],
                    reward=data["reward"],
                    emotion=data["emotion"],
                    progress=data["progress"],
                    overlay=data["overlay"],
                    composition=data["composition"],
                    camera=data["camera"],
                    background=data["background"],
                    palette=data["palette"],
                    character_pose=data["character_pose"],
                )
        
        return None
    
    def extract_batch(self, winner_paths: List[str]) -> List[CreativeGene]:
        """批量提取基因"""
        genes = []
        
        for path in winner_paths:
            try:
                gene = self.extract_gene(path)
                genes.append(gene)
            except Exception as e:
                print(f"Failed to extract gene from {path}: {e}")
        
        return genes