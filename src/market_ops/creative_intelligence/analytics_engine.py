"""M3: Feature Analytics Engine

自动统计每一个 Feature 的 CTR/CVR/CPI/ROAS,支持显著性检验和多维过滤。

复用现有:
- FeatureDatabase (M2) 提供数据
- creative_performance 表的性能指标

输出:
- Top Feature / Worst Feature
- Feature Ranking
- Feature Correlation

Usage:
    from market_ops.creative_intelligence.analytics_engine import FeatureAnalyticsEngine

    engine = FeatureAnalyticsEngine()
    report = engine.analyze(project="P04", min_spend=100)
    print(report["top_features"])
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.feature_db import FeatureDatabase

_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = _ROOT / "output" / "creative_intelligence" / "analytics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class FeatureAnalyticsEngine:
    """Feature 效果分析引擎

    对每个特征维度(如 has_coins=True vs False),
    计算带该特征vs不带该特征的CTR/CVR/CPI/ROAS差异和显著性。
    """

    # 需要分析的布尔特征列
    BOOLEAN_FEATURES = [
        "has_female", "has_monster", "has_ui", "has_reward",
        "has_coins", "has_chest", "has_arrow", "has_before_after",
        "has_explosion", "has_highlight", "has_finger_guide",
        "has_number", "has_text", "has_cta",
        "symmetry", "center_layout", "left_right_layout",
        "game_has_merge", "game_has_level", "game_has_progress",
        "game_has_collection", "game_has_reward",
        "emotion_surprise", "emotion_reward", "emotion_tension",
    ]

    # 需要分析的类别特征列
    CATEGORICAL_FEATURES = [
        "subject_type", "primary_color", "warm_cool",
        "hook_type", "mood", "focus_grid",
    ]

    # 性能指标
    METRICS = ["ctr", "ipm", "cpi", "roas_d7", "spend", "install"]

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db = FeatureDatabase(db_path)

    def analyze(
        self,
        project: str | None = None,
        min_spend: float = 50,
        min_impressions: int = 1000,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """执行完整分析

        Args:
            min_spend: 最低花费门槛(过滤噪音)
            min_impressions: 最低展示门槛
        """
        print(f"[Analytics] 开始分析 project={project} min_spend={min_spend}")

        # 1. 拉取Feature+Performance关联数据
        rows = self._db.query_features_with_performance(
            project=project,
            min_spend=min_spend,
            min_impressions=min_impressions,
            date_from=date_from,
            date_to=date_to,
            limit=10000,
        )
        print(f"[Analytics] 关联数据: {len(rows)} 条")

        if len(rows) < 5:
            print(f"[Analytics] 数据不足(<5条),跳过分析")
            return {"error": "insufficient_data", "count": len(rows)}

        # 2. 布尔特征分析 (A/B对比)
        bool_results = self._analyze_boolean_features(rows)

        # 3. 类别特征分析 (分组对比)
        cat_results = self._analyze_categorical_features(rows)

        # 4. 汇总 Top/Worst Features
        all_effects = bool_results + cat_results
        top_features = sorted([r for r in all_effects if r.get("lift_pct", 0) > 0],
                              key=lambda x: x["lift_pct"], reverse=True)[:20]
        worst_features = sorted([r for r in all_effects if r.get("lift_pct", 0) < 0],
                                key=lambda x: x["lift_pct"])[:20]

        # 5. Feature Correlation (共现分析)
        correlations = self._analyze_correlations(rows)

        report = {
            "analyzed_at": datetime.now().isoformat(),
            "filters": {
                "project": project,
                "min_spend": min_spend,
                "min_impressions": min_impressions,
            },
            "sample_count": len(rows),
            "total_spend": round(sum(r.get("spend", 0) or 0 for r in rows), 2),
            "total_installs": sum(r.get("install", 0) or 0 for r in rows),
            "top_features": top_features,
            "worst_features": worst_features,
            "boolean_feature_analysis": bool_results,
            "categorical_feature_analysis": cat_results,
            "correlations": correlations,
        }

        # 保存报告
        report_file = OUTPUT_DIR / f"analytics_{project or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"[Analytics] 报告已保存: {report_file}")

        return report

    def _analyze_boolean_features(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """布尔特征A/B分析: has_X=True vs has_X=False"""
        results = []

        for feat in self.BOOLEAN_FEATURES:
            with_feat = [r for r in rows if r.get(feat) and r.get("ctr") is not None]
            without_feat = [r for r in rows if not r.get(feat) and r.get("ctr") is not None]

            if len(with_feat) < 3 or len(without_feat) < 3:
                continue

            for metric in ["ctr", "ipm", "cpi", "roas_d7"]:
                with_vals = [float(r[metric]) for r in with_feat if r.get(metric) is not None]
                without_vals = [float(r[metric]) for r in without_feat if r.get(metric) is not None]

                if len(with_vals) < 3 or len(without_vals) < 3:
                    continue

                with_mean = sum(with_vals) / len(with_vals)
                without_mean = sum(without_vals) / len(without_vals)

                if without_mean == 0:
                    continue

                # CPI越低越好,其他越高越好
                if metric == "cpi":
                    lift_pct = round((without_mean - with_mean) / without_mean * 100, 1)
                else:
                    lift_pct = round((with_mean - without_mean) / without_mean * 100, 1)

                # 显著性检验 (简化版Z-test)
                significant = self._is_significant(with_vals, without_vals)

                results.append({
                    "feature": feat,
                    "metric": metric,
                    "with_count": len(with_vals),
                    "without_count": len(without_vals),
                    "with_mean": round(with_mean, 3),
                    "without_mean": round(without_mean, 3),
                    "lift_pct": lift_pct,
                    "significant": significant,
                })

        return results

    def _analyze_categorical_features(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """类别特征分组分析: 每个类别值vs其余"""
        results = []

        for feat in self.CATEGORICAL_FEATURES:
            # 按特征值分组
            groups: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                val = r.get(feat)
                if val and r.get("ctr") is not None:
                    groups[str(val)].append(r)

            if len(groups) < 2:
                continue

            for val, group_rows in groups.items():
                if len(group_rows) < 3:
                    continue

                other_rows = [r for r in rows if str(r.get(feat, "")) != val and r.get("ctr") is not None]
                if len(other_rows) < 3:
                    continue

                for metric in ["ctr", "ipm", "cpi"]:
                    with_vals = [float(r[metric]) for r in group_rows if r.get(metric) is not None]
                    without_vals = [float(r[metric]) for r in other_rows if r.get(metric) is not None]

                    if len(with_vals) < 3 or len(without_vals) < 3:
                        continue

                    with_mean = sum(with_vals) / len(with_vals)
                    without_mean = sum(without_vals) / len(without_vals)
                    if without_mean == 0:
                        continue

                    if metric == "cpi":
                        lift_pct = round((without_mean - with_mean) / without_mean * 100, 1)
                    else:
                        lift_pct = round((with_mean - without_mean) / without_mean * 100, 1)

                    results.append({
                        "feature": feat,
                        "value": val,
                        "metric": metric,
                        "with_count": len(with_vals),
                        "without_count": len(without_vals),
                        "with_mean": round(with_mean, 3),
                        "without_mean": round(without_mean, 3),
                        "lift_pct": lift_pct,
                        "significant": self._is_significant(with_vals, without_vals),
                    })

        return results

    def _analyze_correlations(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """特征共现分析 (如 has_coins + has_chest 常一起出现)"""
        correlations = []
        bool_feats = [f for f in self.BOOLEAN_FEATURES
                      if any(r.get(f) for r in rows)]

        for i, f1 in enumerate(bool_feats):
            for f2 in bool_feats[i+1:]:
                both = sum(1 for r in rows if r.get(f1) and r.get(f2))
                if both < 3:
                    continue
                total = len(rows)
                p1 = sum(1 for r in rows if r.get(f1)) / total
                p2 = sum(1 for r in rows if r.get(f2)) / total
                expected = p1 * p2 * total
                if expected < 1:
                    continue
                lift = both / expected
                if lift > 1.5 or lift < 0.67:
                    correlations.append({
                        "feature1": f1,
                        "feature2": f2,
                        "co_occurrence": both,
                        "lift": round(lift, 2),
                        "relation": "positive" if lift > 1 else "negative",
                    })

        return sorted(correlations, key=lambda x: abs(x["lift"] - 1), reverse=True)[:20]

    def _is_significant(self, group_a: list[float], group_b: list[float]) -> bool:
        """简化的显著性检验 (基于效应量和样本量)"""
        n1, n2 = len(group_a), len(group_b)
        if n1 < 3 or n2 < 3:
            return False

        mean1 = sum(group_a) / n1
        mean2 = sum(group_b) / n2

        # 简化标准差
        var1 = sum((x - mean1) ** 2 for x in group_a) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in group_b) / (n2 - 1) if n2 > 1 else 0
        se = math.sqrt(var1 / n1 + var2 / n2)

        if se == 0:
            return False

        z = abs(mean1 - mean2) / se
        return z > 1.96  # p < 0.05 近似

    def close(self) -> None:
        self._db.close()
