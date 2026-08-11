"""Creative Value Predictor — Buying Score 计算引擎

Buying Score = Hook×25% + Gameplay×25% + Reward×20% + Novelty×15% + Emotion×10% + CTA×5%

输出：predicted_ctr, predicted_cpi, predicted_roi
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional


class CreativeValuePredictor:
    """创意价值预测器"""

    # Buying Score 权重
    WEIGHTS = {
        "hook": 0.25,
        "gameplay": 0.25,
        "reward": 0.20,
        "novelty": 0.15,
        "emotion": 0.10,
        "cta": 0.05,
    }

    def __init__(self, ranking_db_path: Optional[Path] = None,
                 winner_db_path: Optional[Path] = None):
        if ranking_db_path is None:
            ranking_db_path = Path("d:/project_slim/project_slim/creative_remix_engine/storage/outputs/v36_1_ranking_db.json")
        self.ranking_data = {}
        self._load_ranking(ranking_db_path)

        # Winner 数据用于校准
        self.winner_patterns = {}
        if winner_db_path and winner_db_path.exists():
            try:
                with open(winner_db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for w in data.get("winners", []):
                    dna = w.get("dna", {})
                    for key in ["hook_type", "subject", "action", "emotion"]:
                        val = dna.get(key, "")
                        if val:
                            if key not in self.winner_patterns:
                                self.winner_patterns[key] = {}
                            if val not in self.winner_patterns[key]:
                                self.winner_patterns[key][val] = []
                            self.winner_patterns[key][val].append(w["metrics"]["ctr"])
            except Exception:
                pass

    def _load_ranking(self, path: Path):
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("shots", []):
                    self.ranking_data[item.get("video_name", "")] = item
            except Exception:
                pass

    def predict(self, video_name: str) -> Dict:
        """预测单个视频的 Buying Score 和买量指标"""
        rank = self.ranking_data.get(video_name, {})
        name = video_name.lower()

        # 基础分数
        hook = rank.get("hook_score_v2", 0)
        gameplay = rank.get("gameplay_clarity", 0)
        reward = rank.get("reward_score", 0)
        novelty = rank.get("hook_breakdown", {}).get("novelty", 20)
        emotion = rank.get("hook_breakdown", {}).get("emotion", 30)
        cta = max(hook, reward) * 0.6  # CTA 通常继承 hook/reward 的强度

        # Winner DNA 加成
        winner_bonus = self._calc_winner_bonus(name)

        # 计算 Buying Score
        buying_score = (
            hook * self.WEIGHTS["hook"] +
            gameplay * self.WEIGHTS["gameplay"] +
            reward * self.WEIGHTS["reward"] +
            novelty * self.WEIGHTS["novelty"] +
            emotion * self.WEIGHTS["emotion"] +
            cta * self.WEIGHTS["cta"] +
            winner_bonus
        )
        buying_score = min(100, max(0, buying_score))

        # 预测买量指标
        ctr, cpi, roi = self._predict_metrics(buying_score, hook, gameplay, name)

        return {
            "video_name": video_name,
            "buying_score": round(buying_score, 1),
            "breakdown": {
                "hook": round(hook * self.WEIGHTS["hook"], 1),
                "gameplay": round(gameplay * self.WEIGHTS["gameplay"], 1),
                "reward": round(reward * self.WEIGHTS["reward"], 1),
                "novelty": round(novelty * self.WEIGHTS["novelty"], 1),
                "emotion": round(emotion * self.WEIGHTS["emotion"], 1),
                "cta": round(cta * self.WEIGHTS["cta"], 1),
                "winner_bonus": round(winner_bonus, 1),
            },
            "predicted_ctr": ctr,
            "predicted_cpi": cpi,
            "predicted_d7_roi": roi,
        }

    def _calc_winner_bonus(self, name: str) -> float:
        """基于 Winner 模式的加成"""
        bonus = 0
        s = name.lower()

        # 检查是否匹配 Winner 模式
        for pattern_type, patterns in self.winner_patterns.items():
            for pattern_val, ctrs in patterns.items():
                if pattern_val in s:
                    avg_ctr = np.mean(ctrs) if ctrs else 2.0
                    # CTR > 3.0 的 pattern 给加分
                    if avg_ctr > 3.0:
                        bonus += 5
                    if avg_ctr > 4.0:
                        bonus += 5
        return min(20, bonus)

    def _predict_metrics(self, buying_score: float, hook: float, gameplay: float, name: str) -> tuple:
        """基于 Buying Score 预测 CTR/CPI/ROI"""
        # CTR: 非线性映射，高分段的边际收益递减
        if buying_score >= 80:
            ctr = 3.5 + (buying_score - 80) * 0.05
        elif buying_score >= 60:
            ctr = 2.0 + (buying_score - 60) * 0.075
        else:
            ctr = 0.5 + buying_score * 0.025
        ctr = min(6.0, max(0.3, ctr))

        # CPI: 与 Buying Score 负相关
        cpi = max(0.15, 1.2 - buying_score / 80)

        # ROI: 与 Hook 和 Gameplay 都相关
        roi = max(0.05, buying_score / 100 * 0.8 + hook / 100 * 0.1)

        return round(ctr, 2), round(cpi, 2), round(roi, 2)

    def predict_all(self, video_names: List[str]) -> List[dict]:
        """批量预测"""
        return [self.predict(name) for name in video_names]

    def get_top_buying_score(self, video_names: List[str], role: str = "overall", top_n: int = 20) -> List[dict]:
        """获取某角色的 Top Buying Score"""
        predictions = self.predict_all(video_names)
        predictions.sort(key=lambda x: -x["buying_score"])
        return predictions[:top_n]
