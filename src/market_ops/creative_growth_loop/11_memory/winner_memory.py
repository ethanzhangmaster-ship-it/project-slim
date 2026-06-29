"""Winner Memory - V15素材增长闭环"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List


@dataclass
class WinnerMemoryEntry:
    gene_type: str
    gene_value: str
    win_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gene_type": self.gene_type,
            "gene_value": self.gene_value,
            "win_count": self.win_count,
        }


class WinnerMemory:
    MEMORY_PATH = "memory/winner_memory.json"
    
    def __init__(self, memory_path: str = None):
        self.memory_path = Path(memory_path or self.MEMORY_PATH)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    def record_win(self, gene_type: str, gene_value: str) -> None:
        """记录赢家"""
        memory = self._load_memory()
        
        key = f"{gene_type}_{gene_value}"
        
        if key not in memory:
            memory[key] = {
                "gene_type": gene_type,
                "gene_value": gene_value,
                "win_count": 0,
            }
        
        memory[key]["win_count"] += 1
        
        self._save_memory(memory)
    
    def get_win_count(self, gene_type: str, gene_value: str) -> int:
        """获取胜次数"""
        memory = self._load_memory()
        key = f"{gene_type}_{gene_value}"
        
        return memory.get(key, {}).get("win_count", 0)
    
    def get_top_winners(self, gene_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """获取Top赢家"""
        memory = self._load_memory()
        
        entries = []
        for key, data in memory.items():
            if gene_type and data["gene_type"] != gene_type:
                continue
            entries.append(data)
        
        sorted_entries = sorted(entries, key=lambda x: x["win_count"], reverse=True)
        return sorted_entries[:limit]
    
    def get_winner_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取赢家模式"""
        hooks = self.get_top_winners("hook", 10)
        rewards = self.get_top_winners("reward", 10)
        emotions = self.get_top_winners("emotion", 10)
        overlays = self.get_top_winners("overlay", 10)
        
        return {
            "hooks": hooks,
            "rewards": rewards,
            "emotions": emotions,
            "overlays": overlays,
        }
    
    def _load_memory(self) -> Dict[str, Any]:
        """加载记忆"""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _save_memory(self, memory: Dict[str, Any]) -> None:
        """保存记忆"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)


class LoserMemory:
    MEMORY_PATH = "memory/loser_memory.json"
    
    def __init__(self, memory_path: str = None):
        self.memory_path = Path(memory_path or self.MEMORY_PATH)
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    def record_loss(self, gene_type: str, gene_value: str) -> None:
        """记录失败"""
        memory = self._load_memory()
        
        key = f"{gene_type}_{gene_value}"
        
        if key not in memory:
            memory[key] = {
                "gene_type": gene_type,
                "gene_value": gene_value,
                "lose_count": 0,
            }
        
        memory[key]["lose_count"] += 1
        
        self._save_memory(memory)
    
    def is_known_loser(self, gene_type: str, gene_value: str) -> bool:
        """检查是否已知失败"""
        memory = self._load_memory()
        key = f"{gene_type}_{gene_value}"
        
        return key in memory and memory[key]["lose_count"] >= 3
    
    def get_avoid_list(self) -> List[Dict[str, Any]]:
        """获取避免列表"""
        memory = self._load_memory()
        
        losers = []
        for key, data in memory.items():
            if data["lose_count"] >= 3:
                losers.append(data)
        
        return sorted(losers, key=lambda x: x["lose_count"], reverse=True)
    
    def _load_memory(self) -> Dict[str, Any]:
        """加载记忆"""
        if self.memory_path.exists():
            with open(self.memory_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _save_memory(self, memory: Dict[str, Any]) -> None:
        """保存记忆"""
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)


class FamilyTree:
    TREE_PATH = "memory/family_tree.json"
    
    def __init__(self, tree_path: str = None):
        self.tree_path = Path(tree_path or self.TREE_PATH)
        self.tree_path.parent.mkdir(parents=True, exist_ok=True)
    
    def add_family(self, parent_winner: str, family_id: str, 
                   top_variants: List[str], generation: int) -> None:
        """添加家族"""
        tree = self._load_tree()
        
        if parent_winner not in tree:
            tree[parent_winner] = {
                "winner_id": parent_winner,
                "families": [],
                "generation": 0,
            }
        
        tree[parent_winner]["families"].append({
            "family_id": family_id,
            "top_variants": top_variants,
            "generation": generation,
        })
        
        self._save_tree(tree)
    
    def get_winner_lineage(self, winner_id: str) -> Dict[str, Any]:
        """获取赢家谱系"""
        tree = self._load_tree()
        return tree.get(winner_id, {})
    
    def get_all_winners(self) -> List[str]:
        """获取所有赢家"""
        tree = self._load_tree()
        return list(tree.keys())
    
    def get_evolution_path(self, winner_id: str) -> List[Dict[str, Any]]:
        """获取进化路径"""
        tree = self._load_tree()
        
        path = []
        current = winner_id
        
        while current in tree:
            entry = tree[current]
            path.append({
                "winner_id": current,
                "generation": entry.get("generation", 0),
                "families": len(entry.get("families", [])),
            })
            
            families = entry.get("families", [])
            if families:
                current = families[-1].get("top_variants", [None])[0]
            else:
                break
        
        return path
    
    def _load_tree(self) -> Dict[str, Any]:
        """加载谱系"""
        if self.tree_path.exists():
            with open(self.tree_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _save_tree(self, tree: Dict[str, Any]) -> None:
        """保存谱系"""
        with open(self.tree_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, indent=2, ensure_ascii=False)