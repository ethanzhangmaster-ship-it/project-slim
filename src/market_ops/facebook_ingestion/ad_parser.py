r"""E11 Phase 1.5 — Ad Parser (升级版)。

解析广告名称，生成统一 creative_asset_id。

Phase 1.5 升级：
  - 新格式: {产品}_{类型}_{日期}_{序号}  如 MW_IMG_260721_000123
  - 保留 legacy_id 兼容旧格式
  - 根据 entity.creative_type 自动确定 IMG/VID 前缀

规则：
  1. 从 ad_name 中提取 6 位数字编号 → legacy_id
  2. 生成新格式 creative_asset_id
  3. Fallback: "FB_{creative_id}" → legacy_id
"""

from __future__ import annotations

import re
from datetime import datetime

from .models import FacebookCreativeEntity, CreativeType

# 匹配 6 位数字编号（旧格式 legacy_id）
_LEGACY_ID_PATTERN = re.compile(r"\d{6}")


class AdParser:
    """广告名称解析器（Phase 1.5 升级版）。

    生成新格式 creative_asset_id: {product}_{type}_{YYMMDD}_{legacy_id}

    Usage:
        parser = AdParser(product="MW")
        entity = parser.parse(entity)
        # → creative_asset_id = "MW_IMG_260721_000123"
        # → legacy_id = "000123"
    """

    def __init__(self, product: str = "MW") -> None:
        """初始化解析器。

        Args:
            product: 产品前缀，如 "MW" (Merge Witches)
        """
        self._product = product

    def parse(self, entity: FacebookCreativeEntity) -> FacebookCreativeEntity:
        """解析 creative_asset_id 和 legacy_id 并填充到 entity。

        Args:
            entity: FacebookCreativeEntity (creative_asset_id 为空)

        Returns:
            填充了 creative_asset_id 和 legacy_id 的 entity
        """
        # 1. 提取 legacy_id
        legacy_id = self.extract_legacy_id(entity.ad_name, entity.creative_id)
        entity.legacy_id = legacy_id

        # 2. 生成新格式 creative_asset_id
        if legacy_id:
            entity.creative_asset_id = self._build_new_id(
                entity_type=entity.creative_type,
                legacy_id=legacy_id,
                created_time=entity.created_time,
            )
        else:
            entity.creative_asset_id = ""

        return entity

    def parse_batch(
        self, entities: list[FacebookCreativeEntity],
    ) -> list[FacebookCreativeEntity]:
        """批量解析。"""
        for entity in entities:
            self.parse(entity)
        return entities

    def extract_legacy_id(self, ad_name: str, creative_id: str = "") -> str:
        """从广告名称提取 legacy_id（6位数字）。

        规则：
          1. 匹配 6 位数字 → 如 "dragon_video_000123" → "000123"
          2. Fallback → "FB_{creative_id}"

        Args:
            ad_name:     Facebook 广告名称
            creative_id: Facebook creative_id (fallback 时使用)

        Returns:
            legacy_id
        """
        if ad_name:
            match = _LEGACY_ID_PATTERN.search(ad_name)
            if match:
                return match.group(0)

        # Fallback: 使用 creative_id
        if creative_id:
            return f"FB_{creative_id}"

        return ""

    def get_legacy_id_from_name(self, ad_name: str) -> str | None:
        """从广告名称中提取数字编号，找不到返回 None。"""
        if ad_name:
            match = _LEGACY_ID_PATTERN.search(ad_name)
            if match:
                return match.group(0)
        return None

    def _build_new_id(
        self,
        entity_type: CreativeType,
        legacy_id: str,
        created_time: str = "",
    ) -> str:
        """构建新格式 creative_asset_id。

        Args:
            entity_type:  CreativeType.IMAGE 或 CreativeType.VIDEO
            legacy_id:    旧格式 6 位数字编号
            created_time: Facebook created_time 字符串

        Returns:
            新格式 ID，如 "MW_IMG_260721_000123"
        """
        # 类型前缀
        if entity_type == CreativeType.IMAGE:
            type_prefix = "IMG"
        elif entity_type == CreativeType.VIDEO:
            type_prefix = "VID"
        else:
            type_prefix = "UNK"

        # 日期
        date_str = self._extract_date_str(created_time)

        return f"{self._product}_{type_prefix}_{date_str}_{legacy_id}"

    def _extract_date_str(self, created_time: str) -> str:
        """从 created_time 提取 YYMMDD 格式日期。"""
        if created_time:
            try:
                # Facebook 格式: "2026-07-01T00:00:00+0000"
                dt = datetime.fromisoformat(created_time[:19])
                return dt.strftime("%y%m%d")
            except (ValueError, IndexError):
                pass
        return datetime.now().strftime("%y%m%d")

    @property
    def product(self) -> str:
        return self._product

    def __repr__(self) -> str:
        return f"AdParser(product={self._product!r})"