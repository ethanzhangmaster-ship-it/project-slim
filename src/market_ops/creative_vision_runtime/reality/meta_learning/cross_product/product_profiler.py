"""E12.6.4 — Product Profiler。

产品画像构建器。

从产品数据中提取 ProductFeature 和 ProductProfile。
"""

from __future__ import annotations

from typing import Any

from .models import (
    ProductFeature,
    ProductProfile,
)


class ProductProfiler:
    """产品画像构建器。

    负责:
      1. 从原始数据构建 ProductFeature
      2. 聚合成功模式和性能指标
      3. 输出 ProductProfile
    """

    def __init__(self) -> None:
        pass

    def build_feature(
        self,
        product_id: str,
        genre: str = "",
        monetization: str = "",
        audience: str = "",
        gameplay_tags: list[str] | None = None,
        creative_patterns: list[str] | None = None,
        market: str = "",
        performance: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductFeature:
        """构建产品特征。

        Args:
            product_id:       产品 ID
            genre:            品类
            monetization:     变现模式
            audience:         目标受众
            gameplay_tags:    玩法标签
            creative_patterns: 创意模式
            market:           市场
            performance:      性能指标
            metadata:         附加元数据

        Returns:
            ProductFeature
        """
        return ProductFeature(
            product_id=product_id,
            genre=genre,
            monetization=monetization,
            audience=audience,
            gameplay_tags=gameplay_tags or [],
            creative_patterns=creative_patterns or [],
            market=market,
            performance=performance or {},
            metadata=metadata or {},
        )

    def build_profile(
        self,
        features: ProductFeature,
        successful_patterns: list[dict[str, Any]] | None = None,
        performance_summary: dict[str, float] | None = None,
        experiment_count: int = 0,
        winner_count: int = 0,
    ) -> ProductProfile:
        """构建产品画像。

        Args:
            features:             产品特征
            successful_patterns:  成功模式列表
            performance_summary:  性能摘要
            experiment_count:     实验总数
            winner_count:         winner 数量

        Returns:
            ProductProfile
        """
        return ProductProfile(
            product_id=features.product_id,
            features=features,
            successful_patterns=successful_patterns or [],
            performance_summary=performance_summary or {},
            experiment_count=experiment_count,
            winner_count=winner_count,
        )

    def profile_product(
        self,
        product_id: str,
        genre: str = "",
        monetization: str = "",
        audience: str = "",
        gameplay_tags: list[str] | None = None,
        creative_patterns: list[str] | None = None,
        market: str = "",
        successful_patterns: list[dict[str, Any]] | None = None,
        performance_summary: dict[str, float] | None = None,
        experiment_count: int = 0,
        winner_count: int = 0,
    ) -> ProductProfile:
        """一键构建产品画像。

        Args:
            product_id:          产品 ID
            genre:               品类
            monetization:        变现模式
            audience:            目标受众
            gameplay_tags:       玩法标签
            creative_patterns:   创意模式
            market:              市场
            successful_patterns: 成功模式
            performance_summary: 性能摘要
            experiment_count:    实验总数
            winner_count:        winner 数量

        Returns:
            ProductProfile
        """
        feature = self.build_feature(
            product_id=product_id,
            genre=genre,
            monetization=monetization,
            audience=audience,
            gameplay_tags=gameplay_tags,
            creative_patterns=creative_patterns,
            market=market,
            performance=performance_summary or {},
        )

        return self.build_profile(
            features=feature,
            successful_patterns=successful_patterns,
            performance_summary=performance_summary,
            experiment_count=experiment_count,
            winner_count=winner_count,
        )

    def profile_many(
        self,
        product_data: list[dict[str, Any]],
    ) -> list[ProductProfile]:
        """批量构建产品画像。

        Args:
            product_data: 产品数据列表

        Returns:
            ProductProfile 列表
        """
        profiles: list[ProductProfile] = []
        for data in product_data:
            profile = self.profile_product(**data)
            profiles.append(profile)
        return profiles

    def __repr__(self) -> str:
        return "ProductProfiler()"