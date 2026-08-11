"""Quality Scorer - 广告质量评分器

根据 Video Director 输出评分：
- Hook Score (0-3秒)
- Action Score
- Gameplay Score
- Visual Score
"""
from __future__ import annotations

from typing import Any

from ..video_director.models import VideoCreativePlan
from .models import VideoScore


class QualityScorer:
    """广告质量评分器"""

    # Hook 关键词
    HOOK_KEYWORDS: list[str] = [
        "transformation", "explosion", "attack", "flash", "burst",
        "magic", "power", "ultimate", "evolution", "merge",
    ]

    # Action 关键词
    ACTION_KEYWORDS: list[str] = [
        "casting", "merging", "transforming", "attacking", "upgrading",
        "evolving", "collecting", "fighting", "defending",
    ]

    # Gameplay 关键词
    GAMEPLAY_KEYWORDS: list[str] = [
        "merge", "upgrade", "reward", "level up", "collection",
        "puzzle", "match", "combo", "cascade", "evolution",
    ]

    # 视觉质量关键词
    VISUAL_KEYWORDS: list[str] = [
        "masterpiece", "best quality", "4K", "ultra detailed",
        "cinematic", "glowing", "particles", "radiant", "sparkling",
    ]

    def __init__(self):
        self._hook_kw = list(self.HOOK_KEYWORDS)
        self._action_kw = list(self.ACTION_KEYWORDS)
        self._gameplay_kw = list(self.GAMEPLAY_KEYWORDS)
        self._visual_kw = list(self.VISUAL_KEYWORDS)

    def score(self, plan: VideoCreativePlan) -> VideoScore:
        """对创意方案进行质量评分

        Returns:
            VideoScore
        """
        positive = plan.comfyui_workflow.positive.lower()
        storyboard = plan.storyboard

        hook_score = self._score_hook(plan, positive, storyboard)
        action_score = self._score_action(plan, positive, storyboard)
        gameplay_score = self._score_gameplay(plan, positive, storyboard)
        visual_score = self._score_visual(plan, positive)

        total = (hook_score * 0.3 + action_score * 0.25 +
                 gameplay_score * 0.25 + visual_score * 0.20)

        return VideoScore(
            hook_score=hook_score,
            action_score=action_score,
            gameplay_score=gameplay_score,
            visual_score=visual_score,
            total_score=total,
        )

    def _score_hook(self, plan: VideoCreativePlan, positive: str, storyboard: list[Any]) -> float:
        """Hook 评分（0-100）"""
        score = 50.0

        # 检查 prompt 中是否有 hook 关键词
        for kw in self._hook_kw:
            if kw in positive:
                score += 5

        # 检查前3秒是否有强动作
        if storyboard:
            first = storyboard[0]
            if any(kw in first.action.lower() for kw in self._hook_kw):
                score += 15
            if first.emotion in ("shock/awe", "tension/shock", "adorable/surprise"):
                score += 10

        # 检查 camera plan 前3秒强度
        if plan.camera_plan:
            intensity = plan.camera_plan[0].get("intensity", 0)
            score += intensity * 10

        return min(100.0, score)

    def _score_action(self, plan: VideoCreativePlan, positive: str, storyboard: list[Any]) -> float:
        """Action 评分（0-100）"""
        score = 50.0

        # 检查 action 关键词
        for kw in self._action_kw:
            if kw in positive:
                score += 5

        # 检查是否有禁止动作
        banned = ["standing still", "looking around", "idle"]
        for b in banned:
            if b in positive:
                score -= 20

        # 检查 storyboard 动作丰富度
        if storyboard:
            unique_actions = len(set(s.action for s in storyboard))
            score += unique_actions * 5

        # 检查 action plan
        if plan.action_plan:
            for act in plan.action_plan:
                action_text = act.get("action", "").lower()
                if any(kw in action_text for kw in self._action_kw):
                    score += 5

        return min(100.0, max(0.0, score))

    def _score_gameplay(self, plan: VideoCreativePlan, positive: str, storyboard: list[Any]) -> float:
        """Gameplay 评分（0-100）"""
        score = 40.0

        # 检查 gameplay 关键词
        for kw in self._gameplay_kw:
            if kw in positive:
                score += 5

        # 检查是否有奖励/升级场景
        if storyboard:
            for s in storyboard:
                if any(kw in s.scene.lower() for kw in ["reward", "upgrade", "evolution", "merge"]):
                    score += 10

        # 检查 metadata 内容类型
        content_type = plan.metadata.get("content_type", "")
        if content_type in ("juesezhanshi", "wanfashipin", "chongwuzhanshi"):
            score += 10

        return min(100.0, score)

    def _score_visual(self, plan: VideoCreativePlan, positive: str) -> float:
        """Visual 评分（0-100）"""
        score = 50.0

        # 检查质量关键词
        for kw in self._visual_kw:
            if kw in positive:
                score += 3

        # 检查是否有负面低价值关键词
        negative = plan.comfyui_workflow.negative.lower()
        if "dark forest" in positive or "landscape" in positive:
            score -= 30
        if "scenery only" in positive:
            score -= 20

        # 检查是否有高 ROAS 特效
        effects = ["particle", "glow", "flash", "sparkle", "radiant", "bloom"]
        for ef in effects:
            if ef in positive:
                score += 4

        # 检查负面 prompt 是否完善
        if "bad anatomy" in negative and "deformed" in negative:
            score += 5

        return min(100.0, max(0.0, score))
