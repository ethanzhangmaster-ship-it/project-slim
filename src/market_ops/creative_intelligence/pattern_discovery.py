"""M4: Winner Pattern Discovery

自动发现赢家规律组合 - 不只是单个Feature分析,而是发现Feature组合模式。

例如发现:
  美国 + Merge + 紫色 + 女性角色 → CTR 2.8%, ROAS 35%

复用现有:
- FeatureDatabase (M2) 的 JOIN 查询
- FeatureAnalyticsEngine (M3) 的单Feature分析

输出:
- Winner Pattern (Feature组合 + 性能指标 + 样本数 + 置信度)
- Loser Pattern (失败规律)

Usage:
    from market_ops.creative_intelligence.pattern_discovery import WinnerPatternDiscovery

    discovery = WinnerPatternDiscovery()
    patterns = discovery.discover(project="P04", min_spend=100)
    for p in patterns["winners"]:
        print(f"{p['pattern']} → CTR {p['ctr']}% (n={p['sample_count']})")
"""
from __future__ import annotations

import json
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.feature_db import FeatureDatabase

_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = _ROOT / "output" / "creative_intelligence" / "patterns"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class WinnerPatternDiscovery:
    """赢家规律发现引擎

    策略:
    1. 单Feature扫描 (复用M3的思路,但聚焦Top/Bottom performers)
    2. Feature组合挖掘 (2-3个Feature组合,找出高CTR的规律)
    3. 对比Winner vs Loser的Feature差异
    """

    # 用于组合挖掘的特征(布尔型,适合组合)
    COMBO_FEATURES = [
        "has_female", "has_monster", "has_ui", "has_coins",
        "has_chest", "has_cta", "has_arrow", "has_highlight",
        "symmetry", "center_layout", "left_right_layout",
        "game_has_merge", "game_has_level", "game_has_progress",
        "game_has_collection",
    ]

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db = FeatureDatabase(db_path)

    def discover(
        self,
        project: str | None = None,
        min_spend: float = 100,
        min_impressions: int = 5000,
        top_pct: float = 0.2,  # Top 20% = Winner
        bottom_pct: float = 0.2,  # Bottom 20% = Loser
    ) -> dict[str, Any]:
        """发现赢家/输家规律

        Args:
            top_pct: Top N% 定义为winner
            bottom_pct: Bottom N% 定义为loser
        """
        print(f"[PatternDiscovery] 开始 project={project} min_spend={min_spend}")

        # 1. 拉取数据
        rows = self._db.query_features_with_performance(
            project=project,
            min_spend=min_spend,
            min_impressions=min_impressions,
            limit=10000,
        )
        print(f"[PatternDiscovery] 数据: {len(rows)} 条")

        if len(rows) < 10:
            return {"error": "insufficient_data", "count": len(rows)}

        # 2. 定义Winner/Loser
        sorted_by_ctr = sorted([r for r in rows if r.get("ctr")], key=lambda x: x["ctr"], reverse=True)
        n = len(sorted_by_ctr)
        top_n = max(3, int(n * top_pct))
        bottom_n = max(3, int(n * bottom_pct))

        winners = sorted_by_ctr[:top_n]
        losers = sorted_by_ctr[-bottom_n:]

        winner_avg_ctr = sum(r["ctr"] for r in winners) / len(winners)
        loser_avg_ctr = sum(r["ctr"] for r in losers) / len(losers)
        overall_avg_ctr = sum(r["ctr"] for r in sorted_by_ctr) / n

        print(f"[PatternDiscovery] Winners: {len(winners)} (avg CTR {winner_avg_ctr:.2f}%)")
        print(f"[PatternDiscovery] Losers: {len(losers)} (avg CTR {loser_avg_ctr:.2f}%)")
        print(f"[PatternDiscovery] Overall: avg CTR {overall_avg_ctr:.2f}%")

        # 3. 单Feature规律
        single_patterns = self._find_single_feature_patterns(winners, losers, rows)

        # 4. Feature组合规律 (2-3个Feature)
        combo_patterns = self._find_combo_patterns(rows, min_samples=3)

        # 5. Winner vs Loser 对比
        comparison = self._compare_winner_loser(winners, losers)

        report = {
            "analyzed_at": datetime.now().isoformat(),
            "filters": {"project": project, "min_spend": min_spend},
            "sample_count": n,
            "winner_count": len(winners),
            "loser_count": len(losers),
            "winner_avg_ctr": round(winner_avg_ctr, 2),
            "loser_avg_ctr": round(loser_avg_ctr, 2),
            "overall_avg_ctr": round(overall_avg_ctr, 2),
            "single_feature_patterns": single_patterns,
            "combo_patterns": combo_patterns[:20],  # Top 20组合
            "winner_loser_comparison": comparison,
            "winners": self._format_samples(winners[:10]),
            "losers": self._format_samples(losers[:10]),
        }

        # 保存
        report_file = OUTPUT_DIR / f"patterns_{project or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"[PatternDiscovery] 报告: {report_file}")

        return report

    def _find_single_feature_patterns(
        self, winners: list[dict], losers: list[dict], all_rows: list[dict]
    ) -> list[dict[str, Any]]:
        """单Feature规律 - Winner中高频 vs Loser中高频"""
        patterns = []

        for feat in self.COMBO_FEATURES + ["primary_color", "warm_cool", "hook_type"]:
            if feat in ["primary_color", "warm_cool", "hook_type"]:
                # 类别特征
                win_dist = self._value_distribution(winners, feat)
                lose_dist = self._value_distribution(losers, feat)
                all_dist = self._value_distribution(all_rows, feat)

                for val, win_pct in win_dist.items():
                    lose_pct = lose_dist.get(val, 0)
                    all_pct = all_dist.get(val, 0)
                    if win_pct > all_pct * 1.3 and win_pct > 20:
                        patterns.append({
                            "type": "single",
                            "feature": feat,
                            "value": val,
                            "winner_pct": round(win_pct, 1),
                            "loser_pct": round(lose_pct, 1),
                            "overall_pct": round(all_pct, 1),
                            "pattern": f"{feat}={val}",
                            "insight": f"Winner中{win_pct:.0f}%有{feat}={val},Loser中仅{lose_pct:.0f}%",
                        })
            else:
                # 布尔特征
                win_pct = sum(1 for r in winners if r.get(feat)) / len(winners) * 100
                lose_pct = sum(1 for r in losers if r.get(feat)) / len(losers) * 100
                all_pct = sum(1 for r in all_rows if r.get(feat)) / len(all_rows) * 100

                if win_pct > all_pct * 1.3 and win_pct > 20:
                    patterns.append({
                        "type": "single",
                        "feature": feat,
                        "value": True,
                        "winner_pct": round(win_pct, 1),
                        "loser_pct": round(lose_pct, 1),
                        "overall_pct": round(all_pct, 1),
                        "pattern": feat,
                        "insight": f"Winner中{win_pct:.0f}%有{feat},Loser中仅{lose_pct:.0f}%",
                    })

        return sorted(patterns, key=lambda x: x["winner_pct"] - x["loser_pct"], reverse=True)

    def _find_combo_patterns(self, rows: list[dict], min_samples: int = 3) -> list[dict[str, Any]]:
        """Feature组合挖掘 - 找出高CTR的2-3 Feature组合"""
        combo_results = []

        # 2-Feature组合
        for f1, f2 in combinations(self.COMBO_FEATURES, 2):
            with_both = [r for r in rows if r.get(f1) and r.get(f2) and r.get("ctr")]
            if len(with_both) < min_samples:
                continue

            without_both = [r for r in rows if r.get("ctr") and not (r.get(f1) and r.get(f2))]
            if len(without_both) < min_samples:
                continue

            with_ctr = sum(r["ctr"] for r in with_both) / len(with_both)
            without_ctr = sum(r["ctr"] for r in without_both) / len(without_both)
            if without_ctr == 0:
                continue

            lift = (with_ctr - without_ctr) / without_ctr * 100
            if lift > 20:  # 只保留显著正向组合
                combo_results.append({
                    "type": "combo2",
                    "features": [f1, f2],
                    "pattern": f"{f1} + {f2}",
                    "sample_count": len(with_both),
                    "avg_ctr": round(with_ctr, 2),
                    "baseline_ctr": round(without_ctr, 2),
                    "lift_pct": round(lift, 1),
                })

        return sorted(combo_results, key=lambda x: x["lift_pct"], reverse=True)

    def _compare_winner_loser(self, winners: list[dict], losers: list[dict]) -> dict[str, Any]:
        """Winner vs Loser 关键差异"""
        diffs = []
        for feat in self.COMBO_FEATURES:
            win_pct = sum(1 for r in winners if r.get(feat)) / len(winners) * 100
            lose_pct = sum(1 for r in losers if r.get(feat)) / len(losers) * 100
            gap = win_pct - lose_pct
            if abs(gap) > 15:
                diffs.append({
                    "feature": feat,
                    "winner_pct": round(win_pct, 1),
                    "loser_pct": round(lose_pct, 1),
                    "gap": round(gap, 1),
                    "direction": "winner_dominant" if gap > 0 else "loser_dominant",
                })

        return {
            "key_differences": sorted(diffs, key=lambda x: abs(x["gap"]), reverse=True),
            "summary": f"Winner和Loser在{len(diffs)}个特征上有显著差异(>15%)",
        }

    def _value_distribution(self, rows: list[dict], field: str) -> dict[str, float]:
        """计算类别值分布百分比"""
        from collections import Counter
        values = [str(r.get(field, "")) for r in rows if r.get(field)]
        if not values:
            return {}
        counter = Counter(values)
        total = len(values)
        return {k: v / total * 100 for k, v in counter.items()}

    def _format_samples(self, rows: list[dict]) -> list[dict[str, Any]]:
        """格式化样本展示"""
        return [{
            "creative_id": r.get("creative_id", ""),
            "project": r.get("project", ""),
            "ctr": r.get("ctr", 0),
            "spend": r.get("spend", 0),
            "ipm": r.get("ipm", 0),
            "cpi": r.get("cpi", 0),
            "primary_color": r.get("primary_color", ""),
            "hook_type": r.get("hook_type", ""),
            "has_female": r.get("has_female", False),
            "has_cta": r.get("has_cta", False),
            "game_has_merge": r.get("game_has_merge", False),
        } for r in rows]

    def close(self) -> None:
        self._db.close()
