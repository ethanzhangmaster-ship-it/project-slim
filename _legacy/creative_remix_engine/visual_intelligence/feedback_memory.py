"""Feedback Memory — 人工评分反馈循环

保存人工评分，用于调整 ranking_weight。
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class FeedbackMemory:
    """反馈记忆系统"""

    DEFAULT_WEIGHTS = {
        "hook": {"impact": 0.30, "motion": 0.25, "subject": 0.20, "novelty": 0.15, "emotion": 0.10},
        "gameplay": {"gameplay": 0.50, "motion": 0.20, "impact": 0.20, "reward": 0.10},
        "reward": {"reward": 0.50, "impact": 0.30, "motion": 0.20},
        "cta": {"hook": 0.30, "impact": 0.30, "reward": 0.20, "motion": 0.20},
    }

    def __init__(self, memory_path: Path):
        self.memory_path = memory_path
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.feedbacks: List[dict] = []
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self._load()

    def _load(self):
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.feedbacks = data.get("feedbacks", [])
                self.weights = data.get("weights", self.DEFAULT_WEIGHTS)
            except Exception:
                pass

    def save(self):
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump({
                "feedbacks": self.feedbacks,
                "weights": self.weights,
                "updated_at": datetime.now().isoformat(),
                "total": len(self.feedbacks),
            }, f, ensure_ascii=False, indent=2)

    def add_feedback(self, video_name: str,
                     hook_human: float, gameplay_human: float,
                     reward_human: float, overall_human: float,
                     hook_ai: float, gameplay_ai: float,
                     reward_ai: float, overall_ai: float):
        """添加人工评分"""
        self.feedbacks.append({
            "video_name": video_name,
            "human": {"hook": hook_human, "gameplay": gameplay_human,
                      "reward": reward_human, "overall": overall_human},
            "ai": {"hook": hook_ai, "gameplay": gameplay_ai,
                   "reward": reward_ai, "overall": overall_ai},
            "delta": {
                "hook": round(hook_human - hook_ai, 1),
                "gameplay": round(gameplay_human - gameplay_ai, 1),
                "reward": round(reward_human - reward_ai, 1),
                "overall": round(overall_human - overall_ai, 1),
            },
            "timestamp": datetime.now().isoformat(),
        })
        self._auto_adjust_weights()
        self.save()

    def _auto_adjust_weights(self):
        """基于反馈自动微调权重（简单平均偏移）"""
        if len(self.feedbacks) < 3:
            return

        # 分析最近 10 条反馈的偏差方向
        recent = self.feedbacks[-10:]
        for role in ["hook", "gameplay", "reward"]:
            deltas = [f["delta"].get(role, 0) for f in recent]
            avg_delta = sum(deltas) / len(deltas)
            # 如果 AI 持续高估，降低相关维度权重
            if avg_delta < -2:
                self._nudge_weights(role, -0.02)
            elif avg_delta > 2:
                self._nudge_weights(role, 0.02)

    def _nudge_weights(self, role: str, delta: float):
        """微调权重"""
        w = self.weights.get(role, {})
        if not w:
            return
        # 找到最大权重项，微调它
        max_key = max(w, key=w.get)
        w[max_key] = round(max(0.05, min(0.8, w[max_key] + delta)), 3)
        # 归一化
        total = sum(w.values())
        for k in w:
            w[k] = round(w[k] / total, 3)

    def get_weights(self, role: str) -> Dict[str, float]:
        return self.weights.get(role, self.DEFAULT_WEIGHTS.get(role, {}))
