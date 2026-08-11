"""Creative Evolution Memory — 创意进化记忆"""
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from ...config import MEMORY_DIR


class CreativeEvolutionMemory:
    """记录赢家/输家模式，自动进化mutation权重"""

    def __init__(self, game_code: str = "P04"):
        self.game_code = game_code
        self.memory_file = MEMORY_DIR / "creative_evolution.json"
        self.winners: List[Dict] = []
        self.losers: List[Dict] = []
        self.mutation_weights: Dict[str, float] = {}
        self._load()

    def _load(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.winners = data.get("winners", [])
                self.losers = data.get("losers", [])
                self.mutation_weights = data.get("mutation_weights", {})
            except:
                pass

    def save(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump({
                "winners": self.winners,
                "losers": self.losers,
                "mutation_weights": self.mutation_weights,
                "last_update": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

    def record_winner(self, creative_id: str, dna: str, hook: str, roas: float,
                      mutation_types: List[str] = None):
        """记录赢家"""
        self.winners.append({
            "creative_id": creative_id,
            "dna": dna,
            "hook": hook,
            "roas": roas,
            "mutations": mutation_types or [],
            "timestamp": datetime.now().isoformat(),
        })

        # 更新mutation权重
        if mutation_types:
            for mt in mutation_types:
                self.mutation_weights[mt] = self.mutation_weights.get(mt, 1.0) * 1.2

        self.save()

    def record_loser(self, creative_id: str, dna: str, roas: float,
                     mutation_types: List[str] = None):
        """记录输家"""
        self.losers.append({
            "creative_id": creative_id,
            "dna": dna,
            "roas": roas,
            "mutations": mutation_types or [],
            "timestamp": datetime.now().isoformat(),
        })

        # 降低mutation权重
        if mutation_types:
            for mt in mutation_types:
                self.mutation_weights[mt] = self.mutation_weights.get(mt, 1.0) * 0.7

        self.save()

    def get_mutation_weight(self, mutation_type: str) -> float:
        """获取mutation权重"""
        return self.mutation_weights.get(mutation_type, 1.0)

    def get_top_patterns(self, n: int = 5) -> List[Dict]:
        """获取TOP N赢家模式"""
        sorted_winners = sorted(self.winners, key=lambda x: -x.get("roas", 0))
        return sorted_winners[:n]

    def get_evolution_report(self) -> Dict:
        """生成进化报告"""
        return {
            "total_winners": len(self.winners),
            "total_losers": len(self.losers),
            "avg_winner_roas": sum(w.get("roas", 0) for w in self.winners) / len(self.winners) if self.winners else 0,
            "avg_loser_roas": sum(l.get("roas", 0) for l in self.losers) / len(self.losers) if self.losers else 0,
            "top_mutation_weights": sorted(self.mutation_weights.items(), key=lambda x: -x[1])[:10],
            "top_patterns": self.get_top_patterns(3),
        }
