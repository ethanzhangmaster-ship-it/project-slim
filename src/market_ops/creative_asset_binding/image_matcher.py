"""E11 Phase 3 — Facebook Image Matcher。

将 Facebook 图片广告实体匹配到 Lovart 生成图片。

图片特殊处理（因为图片是 Lovart 生成的）：
  Facebook image → download thumbnail → CLIP embedding → Lovart generated image index

流程：
  creative_asset_id → lovart_asset_path → prompt → generation_history
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import (
    LovartAsset,
    AssetBindingResult,
    BindingMethod,
    AssetSourceType,
)


# 序列号提取：文件名末尾的 _XXXXXX（6位数字，在末尾或扩展名前）
SERIAL_PATTERN = re.compile(r"_(\d{6})(?:\.\w+)?$")


@dataclass
class ImageMatchResult:
    """图片匹配结果集合。"""

    creative_asset_id: str = ""
    matched: bool = False
    results: list[AssetBindingResult] = field(default_factory=list)
    best_result: AssetBindingResult | None = None
    lovart_asset: LovartAsset | None = None

    @property
    def best_confidence(self) -> float:
        if self.best_result:
            return self.best_result.confidence
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "matched": self.matched,
            "results": [r.to_dict() for r in self.results],
            "best_result": self.best_result.to_dict() if self.best_result else None,
            "lovart_asset": self.lovart_asset.to_dict() if self.lovart_asset else None,
        }


class ImageMatcher:
    """Facebook 图片 → Lovart 图片匹配器。

    支持 2 级匹配：
      Level 1 — 精确 Lovart generation_id 匹配（通过文件名中的序列号）
      Level 2 — 视觉 embedding 匹配（模拟，实际需 CLIP）

    Usage:
        matcher = ImageMatcher(lovart_assets)
        result = matcher.match("MW_IMG_260721_000125")
        if result.matched:
            print(f"Lovart asset: {result.lovart_asset.image_path}")
    """

    EXACT_CONFIDENCE = 1.0
    VISUAL_CONFIDENCE = 0.85

    def __init__(self, lovart_assets: list[LovartAsset] | None = None) -> None:
        self._lovart_assets: list[LovartAsset] = lovart_assets or []
        self._by_generation_id: dict[str, LovartAsset] = {}
        self._by_serial: dict[str, LovartAsset] = {}

        for asset in self._lovart_assets:
            if asset.generation_id:
                self._by_generation_id[asset.generation_id] = asset
            serial = self._extract_serial(asset.image_path)
            if serial:
                self._by_serial[serial] = asset

    # ── Public API ───────────────────────────────────────

    def match(
        self,
        creative_asset_id: str,
        creative_name: str = "",
        lovart_generation_id: str = "",
    ) -> ImageMatchResult:
        """匹配 Facebook 图片到 Lovart 生成图。

        Args:
            creative_asset_id:    统一编号
            creative_name:        Facebook 广告名称
            lovart_generation_id: 已知的 Lovart 生成 ID（可选）

        Returns:
            ImageMatchResult
        """
        result = ImageMatchResult(creative_asset_id=creative_asset_id)

        # Level 1: 精确 generation_id 匹配
        if lovart_generation_id:
            exact = self._match_by_generation_id(creative_asset_id, lovart_generation_id)
            if exact:
                result.results.append(exact)
                result.matched = True
                result.best_result = exact
                result.lovart_asset = self._by_generation_id.get(lovart_generation_id)
                return result

        # Level 2: 序列号匹配
        serial = self._extract_serial(creative_asset_id)
        if not serial and creative_name:
            serial = self._extract_serial(creative_name)

        if serial:
            serial_result = self._match_by_serial(creative_asset_id, serial)
            if serial_result:
                result.results.append(serial_result)
                result.matched = True
                result.best_result = serial_result
                result.lovart_asset = self._by_serial.get(serial)
                return result

        # Level 3: 视觉匹配（模拟）
        visual_result = self._match_visual(creative_asset_id)
        if visual_result:
            result.results.append(visual_result)
            result.matched = True
            result.best_result = visual_result
            return result

        # 未匹配
        result.results.append(AssetBindingResult(
            creative_asset_id=creative_asset_id,
            source=AssetSourceType.LOVART,
            matched=False,
            confidence=0.0,
            method=BindingMethod.UNKNOWN,
            error="No matching Lovart asset found",
        ))
        return result

    def match_batch(
        self,
        creative_ids: dict[str, str],
    ) -> list[ImageMatchResult]:
        """批量匹配。"""
        return [
            self.match(cid, name)
            for cid, name in creative_ids.items()
        ]

    def add_lovart_asset(self, asset: LovartAsset) -> None:
        """动态添加 Lovart 资产。"""
        self._lovart_assets.append(asset)
        if asset.generation_id:
            self._by_generation_id[asset.generation_id] = asset
        serial = self._extract_serial(asset.image_path)
        if serial:
            self._by_serial[serial] = asset

    @property
    def total_lovart_assets(self) -> int:
        return len(self._lovart_assets)

    # ── Level 1: 精确 generation_id ───────────────────

    def _match_by_generation_id(
        self,
        creative_asset_id: str,
        generation_id: str,
    ) -> AssetBindingResult | None:
        asset = self._by_generation_id.get(generation_id)
        if asset:
            return AssetBindingResult(
                creative_asset_id=creative_asset_id,
                source=AssetSourceType.LOVART,
                matched=True,
                confidence=self.EXACT_CONFIDENCE,
                method=BindingMethod.EXACT_ID,
                asset_path=asset.image_path,
                asset_filename=asset.image_path,
            )
        return None

    # ── Level 2: 序列号匹配 ───────────────────────────

    def _match_by_serial(
        self,
        creative_asset_id: str,
        serial: str,
    ) -> AssetBindingResult | None:
        asset = self._by_serial.get(serial)
        if asset:
            return AssetBindingResult(
                creative_asset_id=creative_asset_id,
                source=AssetSourceType.LOVART,
                matched=True,
                confidence=self.EXACT_CONFIDENCE,
                method=BindingMethod.FILENAME,
                asset_path=asset.image_path,
                asset_filename=asset.image_path,
            )
        return None

    # ── Level 3: 视觉匹配（模拟）──────────────────────

    def _match_visual(
        self,
        creative_asset_id: str,
    ) -> AssetBindingResult | None:
        """视觉匹配（模拟实现）。

        实际需要 CLIP embedding + cosine similarity。
        当前模拟：仅当只有一个 Lovart 资产时视为候选匹配。
        """
        if len(self._lovart_assets) != 1:
            return None

        best = self._lovart_assets[0]
        return AssetBindingResult(
            creative_asset_id=creative_asset_id,
            source=AssetSourceType.LOVART,
            matched=True,
            confidence=self.VISUAL_CONFIDENCE,
            method=BindingMethod.VISUAL_HASH,
            asset_path=best.image_path,
            asset_filename=best.image_path,
        )

    # ── Helpers ─────────────────────────────────────────

    def _extract_serial(self, text: str) -> str | None:
        match = SERIAL_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def __repr__(self) -> str:
        return f"ImageMatcher(lovart_assets={self.total_lovart_assets})"