"""Prompt Statistics - 提示词统计模块"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List

from ..models.master_prompt import MasterPrompt, PromptStatistics


class PromptStatisticsGenerator:
    """提示词统计生成器"""

    def generate(self, master: MasterPrompt) -> PromptStatistics:
        """生成统计信息"""
        stats = PromptStatistics()

        all_tokens = []
        all_prompts = []

        for scene in master.scenes:
            prompts = [
                scene.image_prompt,
                scene.video_prompt,
                scene.motion_prompt,
                scene.lighting_prompt,
                scene.character_prompt,
                scene.negative_prompt,
            ]

            for prompt in prompts:
                if prompt and prompt.strip():
                    all_prompts.append(prompt)
                    tokens = prompt.split()
                    all_tokens.extend(tokens)

        stats.total_prompts = len(all_prompts)
        stats.total_tokens = len(all_tokens)

        if stats.total_prompts > 0:
            stats.avg_length = sum(len(p.split()) for p in all_prompts) / stats.total_prompts
        else:
            stats.avg_length = 0.0

        if all_tokens:
            counter = Counter(all_tokens)
            duplicates = sum(c - 1 for c in counter.values())
            stats.duplicate_rate = duplicates / len(all_tokens)
        else:
            stats.duplicate_rate = 0.0

        if stats.total_tokens > 0:
            unique_tokens = len(set(all_tokens))
            stats.compression_rate = 1.0 - (unique_tokens / stats.total_tokens)
        else:
            stats.compression_rate = 0.0

        return stats

    def save(self, stats: PromptStatistics, path: str) -> None:
        """保存统计信息"""
        data = {
            "total_tokens": stats.total_tokens,
            "total_prompts": stats.total_prompts,
            "avg_length": round(stats.avg_length, 2),
            "duplicate_rate": round(stats.duplicate_rate, 4),
            "compression_rate": round(stats.compression_rate, 4),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)