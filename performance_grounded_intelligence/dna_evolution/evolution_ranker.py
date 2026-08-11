"""Evolution Ranker — 演化排名

对通过 Quality Gate 的 variants 按 evolution_score 降序排列,
输出 evolution_ranking.json。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import DNA_EVOLUTION_DIR, FB_TEST_BATCH_SIZE, ensure_dirs


class EvolutionRanker:
    """演化变体排名器"""

    def __init__(self):
        self.variants: List[dict] = []
        self.ranked: List[dict] = []

    def rank(self, variants: List[dict]) -> List[dict]:
        """按 evolution_score 降序排列

        Args:
            variants: 通过 Quality Gate 的 variant 列表

        Returns:
            排序后的变体列表
        """
        self.variants = variants

        # 按 evolution_score 降序, 同分按 diversity 降序
        self.ranked = sorted(
            variants,
            key=lambda v: (
                v.get("_evolution_score", 0),
                v.get("_diversity", 0),
            ),
            reverse=True,
        )

        print(f"\n[EvolutionRanker] 排名完成: {len(self.ranked)} variants")
        if self.ranked:
            top = self.ranked[0]
            print(f"  Top 1: {top.get('creative_id', '?')} "
                  f"score={top.get('_evolution_score', 0):.4f}")

        return self.ranked

    def get_top_n(self, n: Optional[int] = None) -> List[dict]:
        """获取 Top N variants

        Args:
            n: 返回前 N 个, 默认 FB_TEST_BATCH_SIZE

        Returns:
            Top N variants
        """
        n = n or FB_TEST_BATCH_SIZE
        return self.ranked[:min(n, len(self.ranked))]

    def save(self, output_path: Optional[Path] = None):
        """保存排名结果到 evolution_ranking.json"""
        ensure_dirs()
        output_path = output_path or (DNA_EVOLUTION_DIR / "evolution_ranking.json")

        ranking_data = []
        for rank_idx, v in enumerate(self.ranked, 1):
            entry = {
                "rank": rank_idx,
                "creative_id": v.get("creative_id", "unknown"),
                "strategy": v.get("strategy", ""),
                "strategy_label": v.get("strategy_label", ""),
                "winner_source": v.get("winner_source", {}).get("asset_id", ""),
                "winner_similarity": v.get("_similarity", 0),
                "diversity": v.get("_diversity", 0),
                "gameplay_preserve": v.get("_gameplay_preserve", 0),
                "reward_visibility": v.get("_reward_visibility", 0),
                "evolution_score": v.get("_evolution_score", 0),
            }
            ranking_data.append(entry)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": "2.1.8-evo",
                "total": len(ranking_data),
                "ranking": ranking_data,
            }, f, ensure_ascii=False, indent=2)

        print(f"[EvolutionRanker] 排名已保存: {output_path}")
        return output_path
