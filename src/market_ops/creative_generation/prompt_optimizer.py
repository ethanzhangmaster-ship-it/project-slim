"""Prompt Optimizer - 多版本 Prompt 优化

输入: Master Prompt
输出: Version A / B / C / D

例如:
A: Pixar
B: Disney
C: Dreamworks
D: Semi Realistic
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OptimizedPrompt:
    """优化后的提示词版本"""
    version: str           # A / B / C / D
    style: str
    prompt: str
    negative_prompt: str
    params_override: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "style": self.style,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "params_override": self.params_override,
            "metadata": self.metadata,
        }


class PromptOptimizer:
    """提示词优化器

    将单个 Master Prompt 扩展为多个风格版本，用于 A/B 测试。
    """

    # 风格变体定义
    STYLE_VARIANTS: dict[str, dict[str, Any]] = {
        "A": {
            "style": "pixar",
            "suffix": "Pixar 3D animation style, soft rounded forms, warm color palette, "
                      "subsurface scattering, Toy Story quality, cinematic lighting",
            "negative_add": [],
        },
        "B": {
            "style": "disney",
            "suffix": "Disney animation style, classic hand-drawn feel with modern polish, "
                      "elegant character design, magical sparkle effects, Frozen visual quality",
            "negative_add": [],
        },
        "C": {
            "style": "dreamworks",
            "suffix": "DreamWorks animation style, stylized proportions, "
                      "bold expressive faces, How to Train Your Dragon visual style",
            "negative_add": [],
        },
        "D": {
            "style": "semi_realistic",
            "suffix": "semi-realistic digital art, anime game style, "
                      "Genshin Impact quality, detailed textures, beautiful detailed eyes, "
                      "soft shading, realistic lighting",
            "negative_add": ["chibi", "super deformed"],
        },
    }

    # 更激进的风格变体 (用于 Explore 桶)
    BOLD_VARIANTS: dict[str, dict[str, Any]] = {
        "E": {
            "style": "chibi",
            "suffix": "chibi super-deformed style, big head small body, "
                      "extremely cute kawaii, rounded features, collectable feel",
            "negative_add": ["realistic", "semi-realistic"],
        },
        "F": {
            "style": "anime",
            "suffix": "anime style, vibrant colors, dynamic pose, "
                      "shonen jump energy, speed lines, intense expression",
            "negative_add": ["3d render", "pixar"],
        },
        "G": {
            "style": "watercolor",
            "suffix": "watercolor painting style, soft edges, dreamy atmosphere, "
                      "artistic brush strokes, painterly quality, ethereal lighting",
            "negative_add": ["3d render", "photorealistic"],
        },
    }

    def __init__(self):
        self._variants = dict(self.STYLE_VARIANTS)
        self._bold_variants = dict(self.BOLD_VARIANTS)

    # ------------------------------------------------------------------
    # 核心优化方法
    # ------------------------------------------------------------------
    def optimize(
        self,
        master_prompt: str,
        negative_prompt: str = "",
        versions: list[str] | None = None,
        portfolio_tier: str = "safe",
    ) -> list[OptimizedPrompt]:
        """优化 Master Prompt 为多个版本

        Args:
            master_prompt: 主提示词
            negative_prompt: 负面提示词
            versions: 指定版本 (A/B/C/D)，默认全部
            portfolio_tier: safe/growth/explore，影响风格激进程度

        Returns:
            优化后的版本列表
        """
        if versions is None:
            versions = ["A", "B", "C", "D"]

        # Explore 桶加入更激进的风格
        if portfolio_tier.lower() == "explore":
            versions = versions + ["E", "F", "G"]

        results = []
        for ver in versions:
            variant = self._variants.get(ver) or self._bold_variants.get(ver)
            if not variant:
                continue

            # 构建版本特定 prompt
            styled_prompt = self._apply_style(master_prompt, variant)
            styled_negative = self._apply_negative(negative_prompt, variant)

            results.append(OptimizedPrompt(
                version=ver,
                style=variant["style"],
                prompt=styled_prompt,
                negative_prompt=styled_negative,
                params_override={"style": variant["style"]},
                metadata={
                    "portfolio_tier": portfolio_tier,
                    "original_length": len(master_prompt),
                    "optimized_length": len(styled_prompt),
                },
            ))

        return results

    def _apply_style(self, master_prompt: str, variant: dict[str, Any]) -> str:
        """应用风格变体"""
        # 移除原有风格词（如果存在）
        prompt = master_prompt

        # 添加新风格后缀
        suffix = variant.get("suffix", "")
        if suffix:
            prompt = f"{prompt}, {suffix}"

        return prompt

    def _apply_negative(self, negative: str, variant: dict[str, Any]) -> str:
        """应用版本特定的负面词"""
        extra = variant.get("negative_add", [])
        if extra:
            if negative:
                return f"{negative}, {', '.join(extra)}"
            return ", ".join(extra)
        return negative

    # ------------------------------------------------------------------
    # 批量优化
    # ------------------------------------------------------------------
    def optimize_batch(
        self,
        master_prompts: list[dict[str, Any]],
        portfolio_tier: str = "safe",
    ) -> dict[str, list[OptimizedPrompt]]:
        """批量优化多个 Prompt

        Args:
            master_prompts: MasterPrompt 字典列表
            portfolio_tier: 组合层级

        Returns:
            {prompt_id: [OptimizedPrompt, ...]}
        """
        results = {}
        for mp in master_prompts:
            prompt_id = mp.get("prompt_id", "")
            master = mp.get("master_prompt", "")
            negative = mp.get("negative_prompt", "")
            results[prompt_id] = self.optimize(master, negative, portfolio_tier=portfolio_tier)
        return results

    # ------------------------------------------------------------------
    # 智能优化
    # ------------------------------------------------------------------
    def smart_optimize(
        self,
        master_prompt: str,
        negative_prompt: str = "",
        decision_score: float = 0,
        risk_level: str = "medium",
        portfolio_tier: str = "safe",
    ) -> list[OptimizedPrompt]:
        """基于决策分数和风险等级的智能优化

        - Safe 桶: 保守风格，高质量稳定输出
        - Growth 桶: 中等风格变体
        - Explore 桶: 激进风格，大胆尝试
        """
        # 根据风险等级调整版本
        if risk_level.lower() == "low":
            versions = ["A", "B"]  # 保守
        elif risk_level.lower() == "high":
            versions = ["D", "E", "F"]  # 激进
        else:
            versions = ["A", "B", "C", "D"]  # 标准

        # 高分决策加入更多变体
        if decision_score > 85:
            versions = list(set(versions + ["A", "B", "C", "D"]))

        return self.optimize(
            master_prompt,
            negative_prompt,
            versions=sorted(versions),
            portfolio_tier=portfolio_tier,
        )

    # ------------------------------------------------------------------
    # Prompt 增强
    # ------------------------------------------------------------------
    def enhance_prompt(self, prompt: str, enhancement_type: str = "quality") -> str:
        """增强 Prompt 质量"""
        enhancements = {
            "quality": "masterpiece, best quality, ultra detailed, 8k uhd",
            "lighting": "professional lighting, cinematic, dramatic shadows, volumetric light",
            "detail": "hyper detailed, intricate details, sharp focus, crisp textures",
            "color": "vibrant colors, rich saturation, color graded, beautiful palette",
            "mood": "atmospheric, immersive, engaging, emotionally resonant",
        }

        suffix = enhancements.get(enhancement_type, "")
        if suffix:
            return f"{prompt}, {suffix}"
        return prompt

    def add_facebook_optimization(self, prompt: str, placement: str = "feed") -> str:
        """加入 Facebook 投放优化"""
        fb_optimizations = {
            "feed": "scroll-stopper, thumb-stopping, bold contrast, small-size readable",
            "reels": "vertical video, mobile-first, sound-on, trending",
            "stories": "quick hook, tap-to-play, 15-seconds, swipe-up",
        }
        opt = fb_optimizations.get(placement.lower(), "")
        if opt:
            return f"{prompt}, {opt}"
        return prompt
