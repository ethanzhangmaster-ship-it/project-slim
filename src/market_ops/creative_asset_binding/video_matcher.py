"""E11 Phase 3 — Facebook Video Matcher。

将 Facebook 视频广告实体匹配到 Eagle 本地视频文件。

3 级匹配优先级：
  Level 1 — 精确 creative_asset_id 匹配
    Facebook: "MW_VIDEO_260721_000123"
    Eagle:    "MW_VIDEO_260721_000123.mp4"
    成功率最高，confidence = 1.0

  Level 2 — 文件名解析匹配
    Facebook: "dragon_rescue_video_000123"
    Eagle:    "dragon_rescue_000123.mp4"
    提取序列号（6位数字）进行匹配

  Level 3 — 视觉 Hash 匹配（模拟）
    Facebook thumbnail → CLIP embedding
    Eagle first frame → CLIP embedding
    cosine similarity:
      > 0.95 → exact (confidence=0.95)
      0.85-0.95 → possible (confidence=0.85)
      < 0.85 → unknown
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import (
    EagleAsset,
    AssetBindingResult,
    BindingMethod,
    AssetSourceType,
)
from .eagle_indexer import EagleIndex


# 序列号提取：文件名末尾的 _XXXXXX（6位数字，在末尾或扩展名前）
SERIAL_PATTERN = re.compile(r"_(\d{6})(?:\.\w+)?$")


@dataclass
class VideoMatchResult:
    """视频匹配结果集合。"""

    creative_asset_id: str = ""
    matched: bool = False
    results: list[AssetBindingResult] = field(default_factory=list)
    best_result: AssetBindingResult | None = None

    @property
    def best_confidence(self) -> float:
        if self.best_result:
            return self.best_result.confidence
        return 0.0

    @property
    def best_method(self) -> BindingMethod:
        if self.best_result:
            return self.best_result.method
        return BindingMethod.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_asset_id": self.creative_asset_id,
            "matched": self.matched,
            "results": [r.to_dict() for r in self.results],
            "best_result": self.best_result.to_dict() if self.best_result else None,
        }


class VideoMatcher:
    """Facebook 视频 → Eagle 视频匹配器。

    3 级匹配，按优先级依次尝试，找到第一个高置信度匹配后停止。

    Usage:
        matcher = VideoMatcher(eagle_index)
        result = matcher.match("MW_VIDEO_260721_000123")
        if result.matched:
            print(f"Found: {result.best_result.asset_path}")
    """

    # 置信度阈值
    EXACT_CONFIDENCE = 1.0
    HIGH_CONFIDENCE = 0.95
    POSSIBLE_CONFIDENCE = 0.85
    LOW_CONFIDENCE = 0.5

    def __init__(self, eagle_index: EagleIndex) -> None:
        self._index = eagle_index

    # ── Public API ───────────────────────────────────────

    def match(self, creative_asset_id: str, creative_name: str = "") -> VideoMatchResult:
        """3 级匹配入口。

        Args:
            creative_asset_id: 统一编号，如 "MW_VIDEO_260721_000123"
            creative_name:     Facebook 广告名称，用于 Level 2 解析

        Returns:
            VideoMatchResult
        """
        result = VideoMatchResult(creative_asset_id=creative_asset_id)

        # Level 1: 精确 ID 匹配
        exact = self._match_exact_id(creative_asset_id)
        if exact:
            result.results.append(exact)
            result.matched = True
            result.best_result = exact
            return result

        # Level 2: 文件名解析匹配
        filename_result = self._match_filename(creative_asset_id, creative_name)
        if filename_result:
            result.results.append(filename_result)
            if filename_result.confidence >= self.HIGH_CONFIDENCE:
                result.matched = True
                result.best_result = filename_result
                return result

        # Level 3: 视觉 Hash 匹配
        hash_result = self._match_visual_hash(creative_asset_id)
        if hash_result:
            result.results.append(hash_result)
            if hash_result.confidence >= self.POSSIBLE_CONFIDENCE:
                result.matched = True
                result.best_result = hash_result
                return result

        # 未匹配
        result.results.append(AssetBindingResult(
            creative_asset_id=creative_asset_id,
            source=AssetSourceType.EAGLE,
            matched=False,
            confidence=0.0,
            method=BindingMethod.UNKNOWN,
            error="No matching Eagle asset found",
        ))
        return result

    def match_batch(
        self,
        creative_ids: dict[str, str],
    ) -> list[VideoMatchResult]:
        """批量匹配。

        Args:
            creative_ids: {creative_asset_id: creative_name} 字典

        Returns:
            VideoMatchResult 列表
        """
        return [
            self.match(cid, name)
            for cid, name in creative_ids.items()
        ]

    # ── Level 1: 精确 ID 匹配 ─────────────────────────

    def _match_exact_id(self, creative_asset_id: str) -> AssetBindingResult | None:
        """精确 creative_asset_id 匹配。"""
        asset = self._index.find_by_id(creative_asset_id)
        if asset:
            return AssetBindingResult(
                creative_asset_id=creative_asset_id,
                source=AssetSourceType.EAGLE,
                matched=True,
                confidence=self.EXACT_CONFIDENCE,
                method=BindingMethod.EXACT_ID,
                asset_path=asset.path,
                asset_filename=asset.filename,
            )
        return None

    # ── Level 2: 文件名解析匹配 ───────────────────────

    def _match_filename(
        self,
        creative_asset_id: str,
        creative_name: str,
    ) -> AssetBindingResult | None:
        """从文件名中提取序列号进行匹配。

        从 creative_asset_id 和 creative_name 中提取 6 位序列号，
        在 Eagle 索引中查找包含该序列号的文件。
        """
        serial = self._extract_serial(creative_asset_id)
        if not serial and creative_name:
            serial = self._extract_serial(creative_name)

        if not serial:
            return None

        # 在 Eagle 索引中搜索包含该序列号的资产
        for asset in self._index.assets:
            if serial in asset.filename:
                return AssetBindingResult(
                    creative_asset_id=creative_asset_id,
                    source=AssetSourceType.EAGLE,
                    matched=True,
                    confidence=self.HIGH_CONFIDENCE,
                    method=BindingMethod.FILENAME,
                    asset_path=asset.path,
                    asset_filename=asset.filename,
                )

        return None

    # ── Level 3: 视觉 Hash 匹配 ───────────────────────

    def _match_visual_hash(
        self,
        creative_asset_id: str,
    ) -> AssetBindingResult | None:
        """视觉 Hash 匹配（模拟实现）。

        实际项目需要：
          1. 下载 Facebook 缩略图
          2. 生成 CLIP embedding
          3. 与 Eagle 首帧 embedding 做 cosine similarity
          4. 根据阈值判断

        当前模拟：从 creative_asset_id 中提取序列号，
        在 Eagle 中模糊搜索，返回可能的匹配。
        """
        serial = self._extract_serial(creative_asset_id)
        if not serial:
            return None

        # 模糊搜索
        candidates = self._index.find_by_id_fuzzy(serial)
        if not candidates:
            return None

        # 模拟：返回第一个候选，置信度中等
        best = candidates[0]
        return AssetBindingResult(
            creative_asset_id=creative_asset_id,
            source=AssetSourceType.EAGLE,
            matched=True,
            confidence=self.POSSIBLE_CONFIDENCE,
            method=BindingMethod.VISUAL_HASH,
            asset_path=best.path,
            asset_filename=best.filename,
        )

    # ── Helpers ─────────────────────────────────────────

    def _extract_serial(self, text: str) -> str | None:
        """提取 6 位序列号。"""
        match = SERIAL_PATTERN.search(text)
        if match:
            return match.group(1)
        return None

    def __repr__(self) -> str:
        return f"VideoMatcher(assets={self._index.total})"