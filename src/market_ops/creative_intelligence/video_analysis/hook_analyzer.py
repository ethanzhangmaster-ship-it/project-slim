"""Hook Analyzer - Hook 分析器

重点分析视频前3秒：
- 第一帧吸引力（主体大小、对比度、动作）
- 冲突检测
- 动态变化检测
"""
from __future__ import annotations

from typing import Any

from .models import HookAnalysis


class HookAnalyzer:
    """Hook 分析器"""

    # 强冲突关键词
    CONFLICT_KEYWORDS: list[str] = [
        "attack", "danger", "challenge", "failure", "fight",
        "battle", "crash", "explosion", "destroy", "rescue",
    ]

    # 动态变化关键词
    TRANSFORMATION_KEYWORDS: list[str] = [
        "transformation", "transform", "evolution", "morph",
        "change", "upgrade", "evolve", "flash", "burst",
    ]

    # 强动作关键词
    MOTION_KEYWORDS: list[str] = [
        "attack", "casting", "merge", "explosion", "burst",
        "charge", "dash", "strike", "spell", "magic",
    ]

    def __init__(self):
        self._conflict_kw = list(self.CONFLICT_KEYWORDS)
        self._trans_kw = list(self.TRANSFORMATION_KEYWORDS)
        self._motion_kw = list(self.MOTION_KEYWORDS)

    def analyze(
        self,
        prompt_text: str,
        first_frame_description: str = "",
    ) -> HookAnalysis:
        """分析 Hook（前3秒）

        Args:
            prompt_text: 视频生成 prompt
            first_frame_description: 第一帧描述（预留）

        Returns:
            HookAnalysis
        """
        text = prompt_text.lower()
        result = HookAnalysis()

        # 检测冲突
        result.has_conflict = any(kw in text for kw in self._conflict_kw)
        if result.has_conflict:
            result.reasons.append("检测到冲突元素")

        # 检测动态变化
        result.has_transformation = any(kw in text for kw in self._trans_kw)
        if result.has_transformation:
            result.reasons.append("检测到变身/升级动画")

        # 检测动作
        result.has_motion = any(kw in text for kw in self._motion_kw)
        if result.has_motion:
            result.reasons.append("检测到动态动作")

        # 主体大小判断（基于 prompt 关键词）
        if "close-up" in text or "closeup" in text or "特写" in text:
            result.subject_size = "large"
            result.reasons.append("主体占画面较大（特写）")
        elif "medium shot" in text or "medium" in text:
            result.subject_size = "medium"
        elif "wide shot" in text or "landscape" in text or "scenery" in text:
            result.subject_size = "small"
            result.reasons.append("主体过小（风景为主）")
        else:
            result.subject_size = "medium"

        # 对比度判断
        if "high contrast" in text or "dramatic lighting" in text:
            result.contrast_level = "high"
            result.reasons.append("高对比度画面")
        elif "warm" in text or "soft" in text:
            result.contrast_level = "medium"
        else:
            result.contrast_level = "medium"

        # 计算分数
        result.score = self._calculate_score(result, text)
        return result

    def _calculate_score(self, result: HookAnalysis, text: str) -> float:
        """计算 Hook 分数（0-100）"""
        score = 40.0

        # 冲突加分
        if result.has_conflict:
            score += 20

        # 变身加分
        if result.has_transformation:
            score += 20

        # 动作加分
        if result.has_motion:
            score += 15

        # 主体大小
        if result.subject_size == "large":
            score += 10
        elif result.subject_size == "small":
            score -= 15

        # 对比度
        if result.contrast_level == "high":
            score += 5

        # 前3秒直接开始（无预热）
        if any(kw in text for kw in ["instant", "immediate", "sudden", "flash"]):
            score += 10

        # 惩罚：缓慢开始
        if any(kw in text for kw in ["slow intro", "fade in", "gentle opening"]):
            score -= 15

        return min(100.0, max(0.0, score))
