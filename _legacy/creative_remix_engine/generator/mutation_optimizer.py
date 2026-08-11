"""Mutation Optimizer — 基于历史赢家自动优化变异"""
import json
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from ..config import MEMORY_DIR


class MutationOptimizer:
    """根据历史 ROI 自动调整 mutation 权重"""

    def __init__(self):
        self.weights_file = MEMORY_DIR / "mutation_weights.json"
        self.weights: Dict[str, float] = {}
        self.performance_log: Dict[str, List[float]] = defaultdict(list)
        self._load()

    def _load(self):
        if self.weights_file.exists():
            try:
                with open(self.weights_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.weights = data.get("weights", {})
                self.performance_log = defaultdict(list, data.get("log", {}))
            except:
                pass

    def save(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.weights_file, "w", encoding="utf-8") as f:
            json.dump({
                "weights": self.weights,
                "log": dict(self.performance_log),
            }, f, ensure_ascii=False, indent=2)

    def record_performance(self, mutation_type: str, roas: float):
        """记录某个 mutation 类型的表现"""
        self.performance_log[mutation_type].append(roas)
        self._recalculate_weights()

    def _recalculate_weights(self):
        """重新计算权重"""
        for mutation_type, roas_list in self.performance_log.items():
            if len(roas_list) >= 3:
                avg_roas = sum(roas_list) / len(roas_list)
                # 基础权重 1.0，ROAS > 1.0 增加权重
                self.weights[mutation_type] = round(1.0 + (avg_roas - 1.0) * 0.3, 3)

    def get_weight(self, mutation_type: str) -> float:
        """获取 mutation 权重"""
        return self.weights.get(mutation_type, 1.0)

    def get_top_mutations(self, category: str = "hook", top_n: int = 3) -> List[str]:
        """获取某类最优 mutation"""
        prefix = f"{category}_"
        candidates = [(k, v) for k, v in self.weights.items() if k.startswith(prefix)]
        candidates.sort(key=lambda x: -x[1])
        return [k for k, _ in candidates[:top_n]]

    def apply_weights_to_candidates(self, candidates: List[str], category: str) -> List[str]:
        """根据权重排序 candidates"""
        scored = [(c, self.get_weight(f"{category}_{c}")) for c in candidates]
        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored]
