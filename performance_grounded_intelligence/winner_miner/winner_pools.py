"""Winner Pools — 三池输出

根据不同目的筛选 Winner:
1. Scale Winners: 可放量素材 (spend > $5000, ROAS > 0.3)
2. Efficiency Winners: 高质量用户 (spend > $500, ROAS > 0.8)
3. Creative Pattern Winners: 学习视觉 (Top 10% WinnerScore)
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

from ..config import POOL_SCALE, POOL_EFFICIENCY, POOL_PATTERN, WINNERS_DIR, ensure_dirs
from .winner_score import calculate_winner_score_from_record, get_score_breakdown
from .confidence_model import calculate_confidence_from_record


class WinnerPools:
    """Winner 三池管理器"""

    def __init__(self):
        self.scale_winners: List[dict] = []
        self.efficiency_winners: List[dict] = []
        self.pattern_winners: List[dict] = []

    def mine(self, assets: List[dict]) -> Dict[str, List[dict]]:
        """从 visual_assets 挖掘三池 Winner

        Args:
            assets: visual_assets.json 的 assets 列表

        Returns:
            {"scale": [...], "efficiency": [...], "pattern": [...]}
        """
        # 计算所有 asset 的 winner_score
        scored = []
        for asset in assets:
            if asset.get("installs", 0) == 0:
                continue
            score = calculate_winner_score_from_record(asset)
            confidence = calculate_confidence_from_record(asset)
            scored.append({
                **asset,
                "winner_score": score,
                "confidence": confidence,
            })

        print(f"[WinnerPools] 有效素材: {len(scored)} (有安装数据)")

        # Pool 1: Scale Winners
        self.scale_winners = [
            a for a in scored
            if a["spend"] >= POOL_SCALE["min_spend"]
            and a["iap_roas"] >= POOL_SCALE["min_roas"]
        ]
        self.scale_winners.sort(key=lambda x: x["all_revenue"], reverse=True)

        # Pool 2: Efficiency Winners
        self.efficiency_winners = [
            a for a in scored
            if a["spend"] >= POOL_EFFICIENCY["min_spend"]
            and a["iap_roas"] >= POOL_EFFICIENCY["min_roas"]
        ]
        self.efficiency_winners.sort(key=lambda x: x["iap_roas"], reverse=True)

        # Pool 3: Creative Pattern Winners (Top 10% by winner_score)
        scored_sorted = sorted(scored, key=lambda x: x["winner_score"], reverse=True)
        top_n = max(1, int(len(scored_sorted) * POOL_PATTERN["top_percentile"]))
        self.pattern_winners = scored_sorted[:top_n]

        print(f"[WinnerPools] Scale Winners: {len(self.scale_winners)}")
        print(f"[WinnerPools] Efficiency Winners: {len(self.efficiency_winners)}")
        print(f"[WinnerPools] Pattern Winners: {len(self.pattern_winners)} (Top {top_n})")

        return {
            "scale": self.scale_winners,
            "efficiency": self.efficiency_winners,
            "pattern": self.pattern_winners,
        }

    def save(self, output_dir: Optional[Path] = None):
        """保存三池到文件"""
        ensure_dirs()
        out = output_dir or WINNERS_DIR

        for pool_name, pool_data in [
            ("scale_winners", self.scale_winners),
            ("efficiency_winners", self.efficiency_winners),
            ("creative_pattern_winners", self.pattern_winners),
        ]:
            path = out / f"{pool_name}.json"
            # 清理不可序列化的字段
            clean_data = []
            for item in pool_data[:20]:  # 只保存 Top 20
                clean = {k: v for k, v in item.items()
                         if not isinstance(v, (set, bytes))}
                clean["score_breakdown"] = get_score_breakdown(item)
                clean_data.append(clean)

            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "pool": pool_name,
                    "total": len(pool_data),
                    "top_20": clean_data,
                }, f, ensure_ascii=False, indent=2)

        print(f"[WinnerPools] 已保存到 {out}")

    def print_summary(self):
        """打印三池 Top 5 摘要"""
        print(f"\n{'='*80}")
        print("=== Scale Winners (可放量) Top 5 ===")
        for i, w in enumerate(self.scale_winners[:5], 1):
            print(f"  {i}. {w.get('sample_names', ['?'])[0][:40]} | "
                  f"${w['spend']:,.0f} | ROAS {w['iap_roas']:.0%} | "
                  f"收入 ${w['all_revenue']:,.0f}")

        print(f"\n=== Efficiency Winners (高效率) Top 5 ===")
        for i, w in enumerate(self.efficiency_winners[:5], 1):
            print(f"  {i}. {w.get('sample_names', ['?'])[0][:40]} | "
                  f"${w['spend']:,.0f} | ROAS {w['iap_roas']:.0%} | "
                  f"CPI ${w['cpi']:.1f}")

        print(f"\n=== Pattern Winners (学习视觉) Top 5 ===")
        for i, w in enumerate(self.pattern_winners[:5], 1):
            print(f"  {i}. {w.get('sample_names', ['?'])[0][:40]} | "
                  f"Score {w['winner_score']:.3f} | "
                  f"ROAS {w['iap_roas']:.0%} | ${w['spend']:,.0f}")
