"""Consistency Checker - 一致性检查器

检测 AI 视频常见问题：
- 角色变脸
- 衣服变化
- 外观漂移

方法：基于 prompt 文本的一致性推断
（未来可用 CLIP embedding similarity）
"""
from __future__ import annotations

from typing import Any

from .models import ConsistencyResult


class ConsistencyChecker:
    """一致性检查器"""

    # 一致性风险关键词（prompt 中出现越多，一致性风险越高）
    HIGH_RISK_KEYWORDS: list[str] = [
        "morphing", "rapidly changing", "shifting appearance",
        "constantly changing", "unstable", "flickering",
    ]

    # 一致性保障关键词
    STABILITY_KEYWORDS: list[str] = [
        "consistent", "stable", "same character", "uniform",
        "coherent", "smooth transition",
    ]

    def __init__(self):
        self._risk_kw = list(self.HIGH_RISK_KEYWORDS)
        self._stable_kw = list(self.STABILITY_KEYWORDS)

    def check(self, prompt_text: str) -> ConsistencyResult:
        """检查一致性

        Args:
            prompt_text: 视频生成 prompt

        Returns:
            ConsistencyResult
        """
        text = prompt_text.lower()
        result = ConsistencyResult()

        # 检测风险
        risk_count = sum(1 for kw in self._risk_kw if kw in text)
        stable_count = sum(1 for kw in self._stable_kw if kw in text)

        # 角色一致性（基于 prompt 复杂度推断）
        # 角色描述越详细，一致性越高
        char_detail = 0
        for kw in ["face", "hair", "eyes", "outfit", "costume", "dress"]:
            if kw in text:
                char_detail += 1

        # 计算角色一致性分数
        result.character_consistency = 80.0 + char_detail * 3 - risk_count * 10 + stable_count * 5
        result.character_consistency = min(100.0, max(0.0, result.character_consistency))

        # 颜色一致性
        color_mentions = sum(1 for kw in ["color", "tone", "palette", "hue"] if kw in text)
        result.color_consistency = 70.0 + color_mentions * 5 - risk_count * 8
        result.color_consistency = min(100.0, max(0.0, result.color_consistency))

        # 风格一致性
        style_mentions = sum(1 for kw in ["style", "art style", "consistent style"] if kw in text)
        result.style_consistency = 75.0 + style_mentions * 5 - risk_count * 5 + stable_count * 5
        result.style_consistency = min(100.0, max(0.0, result.style_consistency))

        # 记录问题
        if risk_count > 0:
            result.issues.append(f"检测到 {risk_count} 个一致性风险关键词")
        if char_detail < 2:
            result.issues.append("角色描述不够详细，可能导致外观漂移")

        return result
