"""Negative Prompt Engine - 自动生成负面提示词

根据目标模型自动生成对应的负面提示词，提升生成质量。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NegativePromptSet:
    """负面提示词集合"""
    model: str
    base: list[str] = field(default_factory=list)           # 基础负面词
    anatomy: list[str] = field(default_factory=list)        # 解剖学问题
    quality: list[str] = field(default_factory=list)        # 质量问题
    branding: list[str] = field(default_factory=list)       # 品牌/水印问题
    composition: list[str] = field(default_factory=list)    # 构图问题
    facebook_policy: list[str] = field(default_factory=list)  # Facebook 政策风险

    def to_prompt(self, include_policy: bool = True) -> str:
        """合并为负面提示词字符串"""
        all_terms = (
            self.base
            + self.anatomy
            + self.quality
            + self.branding
            + self.composition
        )
        if include_policy:
            all_terms += self.facebook_policy
        return ", ".join(sorted(set(all_terms)))


class NegativePromptEngine:
    """负面提示词引擎

    支持模型:
    - lovart / flux / sdxl / comfyui / midjourney
    """

    def __init__(self):
        self._sets: dict[str, NegativePromptSet] = {}
        self._init_sets()

    def _init_sets(self) -> None:
        # 基础通用负面词
        base_anatomy = [
            "bad anatomy", "disfigured", "malformed limbs", "extra fingers",
            "missing fingers", "fused fingers", "too many fingers", "mutated hands",
            "poorly drawn hands", "poorly drawn face", "mutation", "deformed",
            "ugly", "bad proportions", "duplicate", "morbid", "mutilated",
            "extra limbs", "missing arms", "missing legs", "extra arms",
            "extra legs", "floating limbs", "disconnected limbs",
        ]

        base_quality = [
            "low quality", "worst quality", "normal quality", "lowres",
            "blurry", "out of focus", "depth of field", "jpeg artifacts",
            "compression artifacts", "noise", "grainy", "pixelated",
            "oversaturated", "underexposed", "overexposed", "bad lighting",
            "flat lighting", "harsh shadows", "dull colors", "faded",
        ]

        base_branding = [
            "text", "watermark", "signature", "logo", "brand name",
            "copyright", "trademark", "url", "website", "qr code",
            "barcode", "ui", "user interface", "hud", "buttons", "menus",
        ]

        base_composition = [
            "cropped", "out of frame", "bad framing", "tilted horizon",
            "dutch angle", "awkward pose", "stiff pose", "unnatural pose",
            "cluttered", "busy background", "distracting elements",
            "off-center", "bad composition",
        ]

        facebook_policy = [
            "nudity", "sexual content", "violence", "gore", "blood",
            "weapons", "guns", "realistic violence", "political symbols",
            "hate symbols", "drugs", "alcohol", "tobacco", "gambling",
            "misleading", "fake", "scam", "clickbait text", "before after",
            "shocking content", "sensationalism",
        ]

        # Lovart (与 SDXL 类似)
        self._sets["lovart"] = NegativePromptSet(
            model="lovart",
            base=base_anatomy + base_quality,
            anatomy=["cross-eyed", "lazy eye", "asymmetric eyes"],
            quality=["boring", "lifeless", "static"],
            branding=base_branding,
            composition=base_composition,
            facebook_policy=facebook_policy,
        )

        # Flux (新模型，负面词较少但精准)
        self._sets["flux"] = NegativePromptSet(
            model="flux",
            base=base_anatomy[:10] + base_quality[:10],
            anatomy=["anatomical error", "unnatural proportions"],
            quality=["amateur", "unprofessional", "draft quality"],
            branding=base_branding[:8],
            composition=base_composition[:6],
            facebook_policy=facebook_policy[:10],
        )

        # SDXL
        self._sets["sdxl"] = NegativePromptSet(
            model="sdxl",
            base=base_anatomy + base_quality,
            anatomy=["long neck", "cross-eyed", "asymmetric face"],
            quality=["boring", "lifeless", "overprocessed"],
            branding=base_branding,
            composition=base_composition,
            facebook_policy=facebook_policy,
        )

        # ComfyUI (基于工作流，负面词取决于底层模型)
        self._sets["comfyui"] = NegativePromptSet(
            model="comfyui",
            base=base_anatomy + base_quality,
            anatomy=["wrong anatomy", "uncanny valley"],
            quality=["low detail", "underrendered"],
            branding=base_branding,
            composition=base_composition,
            facebook_policy=facebook_policy,
        )

        # Midjourney (支持 --no 参数)
        self._sets["midjourney"] = NegativePromptSet(
            model="midjourney",
            base=base_anatomy[:12],
            anatomy=["weird anatomy", "unnatural body"],
            quality=base_quality[:12],
            branding=base_branding[:8],
            composition=base_composition[:6],
            facebook_policy=facebook_policy[:8],
        )

    def generate(
        self,
        model: str,
        extra_terms: list[str] | None = None,
        include_policy: bool = True,
    ) -> str:
        """生成负面提示词

        Args:
            model: 目标模型 (lovart/flux/sdxl/comfyui/midjourney)
            extra_terms: 额外负面词
            include_policy: 是否包含 Facebook 政策相关负面词

        Returns:
            负面提示词字符串
        """
        model_lower = model.lower()
        ps = self._sets.get(model_lower)
        if not ps:
            # 回退到通用负面词
            ps = self._sets.get("sdxl", NegativePromptSet(model="generic"))

        prompt = ps.to_prompt(include_policy=include_policy)

        if extra_terms:
            prompt += ", " + ", ".join(extra_terms)

        return prompt

    def generate_for_midjourney(
        self,
        extra_terms: list[str] | None = None,
        include_policy: bool = True,
    ) -> str:
        """生成 Midjourney 专用的 --no 格式"""
        terms = self.generate("midjourney", extra_terms, include_policy)
        # Midjourney 用逗号分隔的词列表
        return terms

    def generate_structured(
        self,
        model: str,
        extra_terms: list[str] | None = None,
        include_policy: bool = True,
    ) -> dict[str, Any]:
        """生成结构化的负面提示词"""
        model_lower = model.lower()
        ps = self._sets.get(model_lower)
        if not ps:
            ps = self._sets.get("sdxl", NegativePromptSet(model="generic"))

        result = {
            "model": model,
            "prompt": ps.to_prompt(include_policy=include_policy),
            "categories": {
                "anatomy": ps.anatomy,
                "quality": ps.quality,
                "branding": ps.branding,
                "composition": ps.composition,
                "facebook_policy": ps.facebook_policy if include_policy else [],
            },
        }

        if extra_terms:
            result["extra_terms"] = extra_terms
            result["prompt"] += ", " + ", ".join(extra_terms)

        return result

    def list_models(self) -> list[str]:
        """列出支持的模型"""
        return list(self._sets.keys())
