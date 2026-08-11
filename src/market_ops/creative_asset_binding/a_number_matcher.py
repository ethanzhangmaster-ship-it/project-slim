"""E11.2.2 — A-Number Matcher。

核心匹配逻辑：从 Facebook ad_name 提取 A-number，匹配 Eagle v-number。

规则：
  Facebook ad_name: "P4-IOS-T1-A536-0707" → A-number = "A536"
  Eagle filename:   "P4-v2601536-mg-2d-juesezhanshi-en-42s-9X16.mp4" → v-number = "v2601536"
  匹配: A536 → 536 → v2601536

Usage:
    matcher = ANumberMatcher()
    result = matcher.match(ad_name="P4-IOS-T1-A536-0707", eagle_filename="P4-v2601536-...mp4")
    # → (True, 1.0)

    # 从 EagleScanner 自动匹配
    ref = matcher.match_to_asset(
        creative_id="123",
        ad_name="P4-IOS-T1-A536-0707",
        scanner=eagle_scanner,
    )
    # → CreativeAssetReference
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from market_ops.creative_repository.assets.asset_reference import (
    CreativeAssetReference,
    AssetSource,
    AssetType,
    MatchMethod,
)

if TYPE_CHECKING:
    from .eagle_scanner import EagleScanner


# A-number 正则：匹配 "A" 后跟 1-4 位数字
A_NUMBER_RE = re.compile(r"A(\d{1,4})", re.IGNORECASE)

# V-number 正则：匹配 "v" 后跟 6-8 位数字
V_NUMBER_RE = re.compile(r"v(\d{4,8})", re.IGNORECASE)


class ANumberMatcher:
    """A-Number 匹配器。

    支持两种匹配模式：
      1. 直接匹配：给定 ad_name + eagle_filename，判断是否匹配
      2. 扫描匹配：给定 ad_name，在 EagleScanner 索引中搜索匹配的素材
    """

    # ── Public API ───────────────────────────────────────

    @staticmethod
    def extract_a_number(ad_name: str) -> str | None:
        """从 ad_name 提取 A-number。

        "P4-IOS-T1-A536-0707" → "A536"
        "P04-AND-T1-A800-0722" → "A800"
        """
        match = A_NUMBER_RE.search(ad_name)
        if match:
            return f"A{match.group(1)}"
        return None

    @staticmethod
    def extract_numeric_a(ad_name: str) -> str | None:
        """从 ad_name 提取 A-number 的数字部分。

        "P4-IOS-T1-A536-0707" → "536"
        """
        match = A_NUMBER_RE.search(ad_name)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def extract_v_number(eagle_filename: str) -> str | None:
        """从 Eagle 文件名提取 v-number。

        "P4-v2601536-mg-2d-...mp4" → "v2601536"
        """
        match = V_NUMBER_RE.search(eagle_filename)
        if match:
            return f"v{match.group(1)}"
        return None

    @staticmethod
    def extract_numeric_v(eagle_filename: str) -> str | None:
        """从 Eagle 文件名提取 v-number 的数字部分。

        "P4-v2601536-mg-2d-...mp4" → "2601536"
        """
        match = V_NUMBER_RE.search(eagle_filename)
        if match:
            return match.group(1)
        return None

    def match(self, ad_name: str, eagle_filename: str) -> tuple[bool, float]:
        """判断 ad_name 和 eagle_filename 是否通过 A-number 匹配。

        Args:
            ad_name:         Facebook 广告名称
            eagle_filename:  Eagle 文件名

        Returns:
            (is_match, confidence)
        """
        a_num = self.extract_numeric_a(ad_name)
        v_num = self.extract_numeric_v(eagle_filename)

        if not a_num or not v_num:
            return False, 0.0

        # 匹配逻辑：A-number 数字部分 在 v-number 数字部分中
        # 例如: A536 → 536 → v2601536 中的 "536"
        if a_num in v_num:
            return True, 1.0

        # 反向：v-number 数字部分 在 A-number 中
        if v_num in a_num:
            return True, 0.9

        return False, 0.0

    def match_to_asset(
        self,
        creative_id: str,
        ad_name: str,
        scanner: EagleScanner,
    ) -> CreativeAssetReference | None:
        """从 ad_name 提取 A-number，在 EagleScanner 中搜索匹配的素材。

        Args:
            creative_id: Facebook creative_id
            ad_name:     Facebook 广告名称
            scanner:     EagleScanner 实例（需已 scan）

        Returns:
            CreativeAssetReference 或 None
        """
        a_num = self.extract_numeric_a(ad_name)
        if not a_num:
            return None

        # 搜索 Eagle 索引
        asset = scanner.find_by_v_number(a_num)
        if not asset:
            return None

        eagle_filename = asset.filename
        ext = Path(eagle_filename).suffix.lower() if eagle_filename else ""
        is_video = ext in {".mp4", ".mov", ".avi", ".webm", ".mkv"}

        return CreativeAssetReference(
            creative_id=creative_id,
            asset_type=AssetType.VIDEO if is_video else AssetType.IMAGE,
            source=AssetSource.EAGLE,
            eagle_filename=eagle_filename,
            local_path=asset.path,
            match_method=MatchMethod.A_NUMBER,
            confidence=1.0,
            ad_name=ad_name,
            a_number=self.extract_a_number(ad_name) or "",
            eagle_v_number=self.extract_v_number(eagle_filename) or "",
        )

    def match_all(
        self,
        facebook_creatives: list[dict[str, str]],
        scanner: EagleScanner,
    ) -> list[CreativeAssetReference]:
        """批量匹配。

        Args:
            facebook_creatives: [
                {"creative_id": "123", "ad_name": "P4-IOS-T1-A536-0707"},
                ...
            ]
            scanner: EagleScanner 实例

        Returns:
            CreativeAssetReference 列表（仅匹配成功的）
        """
        results: list[CreativeAssetReference] = []
        for fb in facebook_creatives:
            ref = self.match_to_asset(
                creative_id=fb["creative_id"],
                ad_name=fb["ad_name"],
                scanner=scanner,
            )
            if ref:
                results.append(ref)
        return results

    def __repr__(self) -> str:
        return "ANumberMatcher()"


# 延迟导入避免循环引用
from pathlib import Path