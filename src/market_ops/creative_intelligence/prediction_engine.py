"""M7: Creative Prediction

生成图片后,基于历史Feature数据预测CTR/CVR/CPI/ROAS。

复用现有:
- FeatureDatabase (M2) 提供历史数据
- CreativeKnowledgeBase (M5) 提供Feature效果规则

预测方法:
- 基于Feature匹配的历史均值
- 加权计算(显著Feature权重高)

Usage:
    from market_ops.creative_intelligence.prediction_engine import CreativePredictionEngine

    engine = CreativePredictionEngine()
    pred = engine.predict(features={"has_cta": True, "left_right_layout": True, "warm_cool": "warm"})
    print(f"预测CTR: {pred['predicted_ctr']}%")
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from market_ops.creative_intelligence.feature_db import FeatureDatabase
from market_ops.creative_intelligence.knowledge_base import CreativeKnowledgeBase

_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = _ROOT / "output" / "creative_intelligence" / "predictions"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class CreativePredictionEngine:
    """创意效果预测引擎

    基于历史Feature+性能数据,预测新创意的CTR/CVR/CPI/ROAS。
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db = FeatureDatabase(db_path)
        self._kb = CreativeKnowledgeBase()

    def predict(self, features: dict[str, Any], project: str = "") -> dict[str, Any]:
        """预测给定Feature组合的性能

        Args:
            features: {"has_cta": True, "left_right_layout": True, ...}
            project: 项目名(用于过滤历史数据)

        Returns:
            {
                "predicted_ctr": float,
                "predicted_cpi": float,
                "predicted_ipm": float,
                "confidence": float,
                "matched_samples": int,
                "contributing_rules": [...],
            }
        """
        # 1. 从知识库找到匹配的规则
        all_rules = self._kb._rules
        matched_rules = []
        for rule in all_rules:
            if rule["status"] != "active":
                continue
            if project and rule.get("project") and rule["project"] != project:
                continue
            pattern = rule["pattern"]
            if self._pattern_matches(pattern, features):
                matched_rules.append(rule)

        # 2. 基于历史数据计算基准值
        baseline = self._get_baseline(project)
        if not baseline:
            return {
                "predicted_ctr": 0,
                "confidence": 0,
                "matched_samples": 0,
                "error": "no_baseline_data",
            }

        # 3. 根据匹配规则调整预测值
        predicted_ctr = baseline["avg_ctr"]
        predicted_cpi = baseline["avg_cpi"]
        predicted_ipm = baseline["avg_ipm"]

        for rule in matched_rules:
            if rule["metric"] == "ctr":
                lift = rule["lift_pct"] / 100 * rule["confidence"]
                predicted_ctr *= (1 + lift)
            elif rule["effect"] == "positive" and rule["metric"] in ("winner_rate", "win_rate"):
                # 正向规则提升CTR
                lift = min(rule["lift_pct"] / 100, 0.3) * rule["confidence"]
                predicted_ctr *= (1 + lift)

        # 4. 置信度 = 匹配规则样本量的函数
        total_samples = sum(r["sample_count"] for r in matched_rules)
        confidence = min(1.0, total_samples / 50)

        # 5. 从历史数据找最相似的样本(简单版本:匹配feature最多的)
        similar = self._find_similar_samples(features, project, limit=5)

        result = {
            "predicted_ctr": round(predicted_ctr, 2),
            "predicted_cpi": round(predicted_cpi, 2),
            "predicted_ipm": round(predicted_ipm, 2),
            "confidence": round(confidence, 2),
            "matched_samples": total_samples,
            "baseline_ctr": baseline["avg_ctr"],
            "baseline_cpi": baseline["avg_cpi"],
            "contributing_rules": [{
                "pattern": r["pattern"],
                "effect": r["effect"],
                "lift_pct": r["lift_pct"],
                "confidence": r["confidence"],
            } for r in matched_rules],
            "similar_samples": [{
                "creative_id": s.get("creative_id", ""),
                "ctr": s.get("ctr", 0),
                "cpi": s.get("cpi", 0),
                "spend": s.get("spend", 0),
            } for s in similar],
            "predicted_at": datetime.now().isoformat(),
        }

        return result

    def predict_for_planner_output(self, prompts: list[dict]) -> list[dict[str, Any]]:
        """对M6 CreativePlanner的输出做预测

        Args:
            prompts: M6输出的prompt列表
        """
        results = []
        for p in prompts:
            # 从prompt的predicted_features提取feature dict
            features = {}
            for feat in p.get("predicted_features", []):
                if "=" in feat:
                    k, v = feat.split("=", 1)
                    features[k] = v == "True" if v in ("True", "False") else v
                else:
                    features[feat] = True

            pred = self.predict(features, project=p.get("project", ""))
            results.append({
                "prompt_id": p["prompt_id"],
                "type": p["type"],
                "prediction": pred,
            })

        # 保存预测报告
        report = {
            "predicted_at": datetime.now().isoformat(),
            "total_predictions": len(results),
            "predictions": results,
        }
        report_file = OUTPUT_DIR / f"predictions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        return results

    def _pattern_matches(self, pattern: str, features: dict) -> bool:
        """检查pattern是否匹配给定features"""
        if "=" in pattern:
            # 类别: feature=value
            feat, val = pattern.split("=", 1)
            feat = feat.strip()
            val = val.strip()
            actual = features.get(feat, features.get(feat.replace("has_", ""), ""))
            return str(actual) == val
        elif "+" in pattern:
            # 组合: feat1 + feat2
            feats = [f.strip() for f in pattern.split("+")]
            return all(features.get(f, False) for f in feats)
        else:
            # 布尔: feature
            return bool(features.get(pattern, False))

    def _get_baseline(self, project: str) -> dict[str, float] | None:
        """获取项目基准CTR/CPI/IPM"""
        rows = self._db.query_features_with_performance(
            project=project if project else None,
            min_spend=50,
            limit=10000,
        )
        if len(rows) < 5:
            return None

        ctrs = [r["ctr"] for r in rows if r.get("ctr")]
        cpis = [r["cpi"] for r in rows if r.get("cpi") and r["cpi"] > 0]
        ipms = [r["ipm"] for r in rows if r.get("ipm")]

        return {
            "avg_ctr": round(sum(ctrs) / len(ctrs), 2) if ctrs else 0,
            "avg_cpi": round(sum(cpis) / len(cpis), 2) if cpis else 0,
            "avg_ipm": round(sum(ipms) / len(ipms), 2) if ipms else 0,
            "sample_count": len(rows),
        }

    def _find_similar_samples(self, features: dict, project: str, limit: int = 5) -> list[dict]:
        """找最相似的历史样本(匹配feature最多)"""
        rows = self._db.query_features_with_performance(
            project=project if project else None,
            min_spend=50,
            limit=10000,
        )

        scored = []
        for r in rows:
            score = 0
            for feat, val in features.items():
                if str(r.get(feat, "")) == str(val):
                    score += 1
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def close(self) -> None:
        self._db.close()
