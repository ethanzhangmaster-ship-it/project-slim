"""Creative Memory — 创意记忆与学习"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from ...models import CreativeMemory, CreativeMemoryEntry, WinnerDNA
from ...config import MEMORY_DIR


class CreativeMemoryManager:
    """管理创意记忆和 Winner DNA 进化"""

    def __init__(self):
        self.memory_file = MEMORY_DIR / "creative_memory.json"
        self.winner_file = MEMORY_DIR / "winner_pattern.json"
        self.memory = self._load()

    def _load(self) -> CreativeMemory:
        """加载记忆"""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return CreativeMemory(
                    winners=[CreativeMemoryEntry(**w) for w in data.get("winners", [])],
                    losers=data.get("losers", []),
                    fatigue_map=data.get("fatigue_map", {}),
                    dna_evolution=data.get("dna_evolution", {}),
                )
            except:
                pass
        return CreativeMemory()

    def save(self):
        """保存记忆"""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "winners": [
                {
                    "dna_key": w.dna_key,
                    "performance": w.performance,
                    "weight": w.weight,
                    "used_count": w.used_count,
                    "last_used": w.last_used,
                }
                for w in self.memory.winners
            ],
            "losers": self.memory.losers,
            "fatigue_map": self.memory.fatigue_map,
            "dna_evolution": self.memory.dna_evolution,
        }
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_winner(self, dna_key: str, performance: Dict[str, float]):
        """记录赢家"""
        now = datetime.now().isoformat()

        # 查找已有条目
        for entry in self.memory.winners:
            if entry.dna_key == dna_key:
                entry.performance = performance
                entry.weight = min(entry.weight + 0.1, 2.0)
                entry.used_count += 1
                entry.last_used = now
                return

        # 新建条目
        self.memory.winners.append(CreativeMemoryEntry(
            dna_key=dna_key,
            performance=performance,
            weight=1.2,
            used_count=1,
            last_used=now,
        ))

        # 按权重排序
        self.memory.winners.sort(key=lambda x: -x.weight)

    def record_loser(self, dna_key: str):
        """记录输家"""
        if dna_key not in self.memory.losers:
            self.memory.losers.append(dna_key)

    def get_top_dna(self, n: int = 5) -> List[str]:
        """获取 TOP N Winner DNA"""
        return [w.dna_key for w in self.memory.winners[:n]]

    def get_dna_weight(self, dna_key: str) -> float:
        """获取 DNA 权重（用于增强下一轮生成）"""
        for entry in self.memory.winners:
            if entry.dna_key == dna_key:
                return entry.weight
        return 1.0

    def update_fatigue(self, v_num: str):
        """更新素材疲劳度"""
        self.memory.fatigue_map[v_num] = self.memory.fatigue_map.get(v_num, 0) + 1

    def get_fatigue(self, v_num: str) -> int:
        """获取素材疲劳度"""
        return self.memory.fatigue_map.get(v_num, 0)
