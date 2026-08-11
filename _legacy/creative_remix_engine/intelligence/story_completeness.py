"""Story Completeness Predictor V1

判断单个视频是否包含完整的故事弧：
  Hook → Action → Transformation → Reward

输入：role_scores dict
输出：story_score (0-100) + 各阶段布尔判断
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class StoryCompletenessResult:
    has_hook: bool
    has_action: bool
    has_transformation: bool
    has_reward: bool
    story_score: float
    completeness_pct: float
    arc_quality: str  # full / partial / weak


class StoryCompletenessPredictor:
    """评估视频的故事完整性。"""

    # 阈值：角色分数超过此值认为存在该阶段
    THRESHOLDS = {
        "hook": 45.0,
        "action": 40.0,
        "transformation": 35.0,
        "reward": 40.0,
    }

    # 权重：各阶段对故事分的贡献
    WEIGHTS = {
        "hook": 0.30,
        "action": 0.25,
        "transformation": 0.25,
        "reward": 0.20,
    }

    def predict(self, role_scores: Dict[str, float]) -> StoryCompletenessResult:
        """基于角色分数预测故事完整性。"""

        # 映射 role_scores 到故事阶段
        hook_score = self._extract_stage_score(role_scores, "hook")
        action_score = self._extract_stage_score(role_scores, ["gameplay", "problem"])
        transformation_score = self._extract_stage_score(role_scores, ["gameplay", "scene"])
        reward_score = self._extract_stage_score(role_scores, ["reward", "character"])

        # 布尔判断
        has_hook = hook_score >= self.THRESHOLDS["hook"]
        has_action = action_score >= self.THRESHOLDS["action"]
        has_transformation = transformation_score >= self.THRESHOLDS["transformation"]
        has_reward = reward_score >= self.THRESHOLDS["reward"]

        # 计算故事分数 (0-100)
        stages = {
            "hook": hook_score,
            "action": action_score,
            "transformation": transformation_score,
            "reward": reward_score,
        }

        story_score = sum(
            min(score, 100) * self.WEIGHTS[stage]
            for stage, score in stages.items()
        )

        # 完整性百分比
        completed = sum([has_hook, has_action, has_transformation, has_reward])
        completeness_pct = (completed / 4) * 100

        # 弧线质量评级
        if completed == 4 and story_score >= 70:
            arc_quality = "full"
        elif completed >= 3 and story_score >= 55:
            arc_quality = "partial"
        elif completed >= 2 and story_score >= 40:
            arc_quality = "weak"
        else:
            arc_quality = "fragment"

        return StoryCompletenessResult(
            has_hook=has_hook,
            has_action=has_action,
            has_transformation=has_transformation,
            has_reward=has_reward,
            story_score=round(story_score, 2),
            completeness_pct=round(completeness_pct, 2),
            arc_quality=arc_quality,
        )

    def predict_batch(
        self, items: list[Dict[str, float]]
    ) -> list[StoryCompletenessResult]:
        """批量预测。"""
        return [self.predict(item) for item in items]

    def _extract_stage_score(
        self, role_scores: Dict[str, float], roles: str | list[str]
    ) -> float:
        """从 role_scores 中提取指定角色的最高分数。"""
        if isinstance(roles, str):
            roles = [roles]
        scores = [role_scores.get(r, 0) for r in roles]
        return max(scores) if scores else 0.0
