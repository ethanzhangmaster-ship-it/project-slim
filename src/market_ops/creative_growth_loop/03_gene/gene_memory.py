"""Gene Memory - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List

from ..03_gene.gene_extractor import CreativeGene


class GeneMemory:
    MEMORY_PATH = "memory/gene_memory.json"
    
    def __init__(self, memory_path: str = None):
        self.memory_path = Path(memory_path or self.MEMORY_PATH)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    def record_win(self, gene: CreativeGene) -> None:
        """记录赢家基因"""
        memory = self._load_memory()
        
        hook = gene.hook
        reward = gene.reward
        emotion = gene.emotion
        progress = gene.progress
        overlay = gene.overlay
        
        if hook and hook != "unknown":
            memory["hooks"][hook] = memory["hooks"].get(hook, 0) + 1
        
        if reward and reward != "unknown":
            memory["rewards"][reward] = memory["rewards"].get(reward, 0) + 1
        
        if emotion and emotion != "neutral":
            memory["emotions"][emotion] = memory["emotions"].get(emotion, 0) + 1
        
        if progress and progress != "unknown":
            memory["progress"][progress] = memory["progress"].get(progress, 0) + 1
        
        if overlay and overlay != "none":
            memory["overlays"][overlay] = memory["overlays"].get(overlay, 0) + 1
        
        self._save_memory(memory)
    
    def get_top_hooks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取Top Hooks"""
        memory = self._load_memory()
        hooks = memory.get("hooks", {})
        
        sorted_hooks = sorted(hooks.items(), key=lambda x: x[1], reverse=True)
        return [{"hook": h, "wins": w} for h, w in sorted_hooks[:limit]]
    
    def get_top_rewards(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取Top Rewards"""
        memory = self._load_memory()
        rewards = memory.get("rewards", {})
        
        sorted_rewards = sorted(rewards.items(), key=lambda x: x[1], reverse=True)
        return [{"reward": r, "wins": w} for r, w in sorted_rewards[:limit]]
    
    def get_top_emotions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取Top Emotions"""
        memory = self._load_memory()
        emotions = memory.get("emotions", {})
        
        sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)
        return [{"emotion": e, "wins": w} for e, w in sorted_emotions[:limit]]
    
    def get_top_overlays(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取Top Overlays"""
        memory = self._load_memory()
        overlays = memory.get("overlays", {})
        
        sorted_overlays = sorted(overlays.items(), key=lambda x: x[1], reverse=True)
        return [{"overlay": o, "wins": w} for o, w in sorted_overlays[:limit]]
    
    def get_gene_success_rate(self, gene_type: str, gene_value: str) -> float:
        """获取基因成功率"""
        memory = self._load_memory()
        
        total_wins = sum(memory.get(gene_type, {}).values())
        if total_wins == 0:
            return 0.0
        
        wins = memory.get(gene_type, {}).get(gene_value, 0)
        return wins / total_wins
    
    def get_best_combination(self) -> Dict[str, str]:
        """获取最佳组合"""
        top_hooks = self.get_top_hooks(1)
        top_rewards = self.get_top_rewards(1)
        top_emotions = self.get_top_emotions(1)
        top_overlays = self.get_top_overlays(1)
        
        return {
            "hook": top_hooks[0]["hook"] if top_hooks else "secret",
            "reward": top_rewards[0]["reward"] if top_rewards else "gold_dragon",
            "emotion": top_emotions[0]["emotion"] if top_emotions else "surprise",
            "overlay": top_overlays[0]["overlay"] if top_overlays else "arrow",
        }
    
    def _load_memory(self) -> Dict[str, Any]:
        """加载记忆"""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        
        return {
            "hooks": {},
            "rewards": {},
            "emotions": {},
            "progress": {},
            "overlays": {},
        }
    
    def _save_memory(self, memory: Dict[str, Any]) -> None:
        """保存记忆"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)


class GeneLock:
    """基因锁定 - 保持爆款基因"""
    
    LOCKED_GENES = ["style", "camera", "composition", "subject"]
    CLIP_RANGE = (0.7, 0.9)
    
    def __init__(self):
        self.locked_values: Dict[str, str] = {}
    
    def lock_from_winner(self, gene: CreativeGene) -> None:
        """从赢家锁定基因"""
        for locked_gene in self.LOCKED_GENES:
            value = getattr(gene, locked_gene, "")
            if value:
                self.locked_values[locked_gene] = value
    
    def get_locked_genes(self) -> Dict[str, str]:
        """获取锁定基因"""
        return self.locked_values
    
    def is_gene_locked(self, gene_type: str) -> bool:
        """检查基因是否锁定"""
        return gene_type in self.LOCKED_GENES
    
    def validate_clip_range(self, clip_score: float) -> bool:
        """验证CLIP范围"""
        return self.CLIP_RANGE[0] <= clip_score <= self.CLIP_RANGE[1]
    
    def apply_lock_to_prompt(self, prompt_parts: List[str]) -> List[str]:
        """将锁定基因应用到提示词"""
        if "style" in self.locked_values:
            prompt_parts.insert(0, f"{self.locked_values['style']} style")
        
        if "camera" in self.locked_values:
            prompt_parts.append(f"{self.locked_values['camera']} angle")
        
        if "composition" in self.locked_values:
            prompt_parts.append(f"{self.locked_values['composition']} composition")
        
        return prompt_parts