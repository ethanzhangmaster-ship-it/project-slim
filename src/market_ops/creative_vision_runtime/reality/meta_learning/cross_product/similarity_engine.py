"""E12.6.4 — Similarity Engine。

产品相似度引擎。

计算产品间的相似度评分，支持:
  - Jaccard 相似度（特征向量）
  - 加权相似度（Genre × 0.25 + Audience × 0.25 + DNA × 0.30 + Market × 0.20）
  - 产品聚类
"""

from __future__ import annotations

from .models import (
    ProductCluster,
    ProductFeature,
    ProductProfile,
    SimilarityResult,
)


class SimilarityEngine:
    """产品相似度引擎。

    计算产品间相似度并聚类。
    """

    # 权重配置
    GENRE_WEIGHT = 0.25
    AUDIENCE_WEIGHT = 0.25
    DNA_WEIGHT = 0.30
    MARKET_WEIGHT = 0.20

    # 聚类阈值
    HIGH_SIMILARITY_THRESHOLD = 0.70
    CLUSTER_THRESHOLD = 0.50

    def __init__(
        self,
        genre_weight: float | None = None,
        audience_weight: float | None = None,
        dna_weight: float | None = None,
        market_weight: float | None = None,
        cluster_threshold: float | None = None,
    ) -> None:
        self.genre_weight = genre_weight if genre_weight is not None else self.GENRE_WEIGHT
        self.audience_weight = audience_weight if audience_weight is not None else self.AUDIENCE_WEIGHT
        self.dna_weight = dna_weight if dna_weight is not None else self.DNA_WEIGHT
        self.market_weight = market_weight if market_weight is not None else self.MARKET_WEIGHT
        self.cluster_threshold = cluster_threshold if cluster_threshold is not None else self.CLUSTER_THRESHOLD

    def compute_similarity(
        self,
        source: ProductFeature,
        target: ProductFeature,
    ) -> SimilarityResult:
        """计算两个产品间的相似度。

        公式:
          total = genre × 0.25 + audience × 0.25 + dna × 0.30 + market × 0.20

        Args:
            source: 来源产品特征
            target: 目标产品特征

        Returns:
            SimilarityResult
        """
        genre_sim = self._jaccard([source.genre], [target.genre])
        audience_sim = self._jaccard([source.audience], [target.audience])
        dna_sim = self._jaccard(source.creative_patterns, target.creative_patterns)
        market_sim = self._jaccard([source.market], [target.market])

        total = (
            genre_sim * self.genre_weight
            + audience_sim * self.audience_weight
            + dna_sim * self.dna_weight
            + market_sim * self.market_weight
        )

        return SimilarityResult(
            source_product=source.product_id,
            target_product=target.product_id,
            genre_similarity=round(genre_sim, 4),
            audience_similarity=round(audience_sim, 4),
            dna_similarity=round(dna_sim, 4),
            market_similarity=round(market_sim, 4),
            total_similarity=round(total, 4),
        )

    def compute_similarity_from_profiles(
        self,
        source: ProductProfile,
        target: ProductProfile,
    ) -> SimilarityResult:
        """从产品画像计算相似度。"""
        return self.compute_similarity(source.features, target.features)

    def compute_pairwise(
        self,
        features: list[ProductFeature],
    ) -> list[SimilarityResult]:
        """计算所有产品对之间的相似度。

        Args:
            features: 产品特征列表

        Returns:
            SimilarityResult 列表
        """
        results: list[SimilarityResult] = []
        for i, src in enumerate(features):
            for j, tgt in enumerate(features):
                if i >= j:
                    continue
                results.append(self.compute_similarity(src, tgt))
        return results

    def compute_pairwise_from_profiles(
        self,
        profiles: list[ProductProfile],
    ) -> list[SimilarityResult]:
        """从产品画像计算所有产品对相似度。"""
        features = [p.features for p in profiles]
        return self.compute_pairwise(features)

    def cluster(
        self,
        features: list[ProductFeature],
    ) -> list[ProductCluster]:
        """将产品聚类为相似组。

        使用简单贪心聚类：每个产品分配到最相似的已有聚类，
        如果相似度低于阈值，则创建新聚类。

        Args:
            features: 产品特征列表

        Returns:
            ProductCluster 列表
        """
        if not features:
            return []

        clusters: list[ProductCluster] = []
        # 第一个产品作为第一个聚类
        clusters.append(ProductCluster(
            products=[features[0].product_id],
            centroid=features[0],
        ))

        for feature in features[1:]:
            best_cluster_idx = -1
            best_similarity = 0.0

            for idx, cluster in enumerate(clusters):
                if cluster.centroid is None:
                    continue
                sim = self.compute_similarity(feature, cluster.centroid)
                if sim.total_similarity > best_similarity:
                    best_similarity = sim.total_similarity
                    best_cluster_idx = idx

            if best_cluster_idx >= 0 and best_similarity >= self.cluster_threshold:
                clusters[best_cluster_idx].products.append(feature.product_id)
                # 更新平均相似度
                n = len(clusters[best_cluster_idx].products)
                old_avg = clusters[best_cluster_idx].avg_similarity
                clusters[best_cluster_idx].avg_similarity = (
                    (old_avg * (n - 1) + best_similarity) / n
                )
            else:
                clusters.append(ProductCluster(
                    products=[feature.product_id],
                    centroid=feature,
                ))

        return clusters

    def cluster_from_profiles(
        self,
        profiles: list[ProductProfile],
    ) -> list[ProductCluster]:
        """从产品画像聚类。"""
        features = [p.features for p in profiles]
        return self.cluster(features)

    def get_most_similar(
        self,
        source: ProductFeature,
        candidates: list[ProductFeature],
        top_n: int = 3,
    ) -> list[SimilarityResult]:
        """找到最相似的目标产品。

        Args:
            source:     来源产品
            candidates: 候选产品列表
            top_n:      返回前 N 个

        Returns:
            SimilarityResult 列表（按相似度降序）
        """
        results = [self.compute_similarity(source, c) for c in candidates]
        results.sort(key=lambda r: r.total_similarity, reverse=True)
        return results[:top_n]

    def _jaccard(self, set_a: list[str], set_b: list[str]) -> float:
        """计算 Jaccard 相似度。

        Jaccard = |A ∩ B| / |A ∪ B|
        """
        a = set(set_a)
        b = set(set_b)
        union = a | b
        if not union:
            return 0.0
        intersection = a & b
        return len(intersection) / len(union)

    def __repr__(self) -> str:
        return (
            f"SimilarityEngine(genre={self.genre_weight:.2f}, "
            f"audience={self.audience_weight:.2f}, "
            f"dna={self.dna_weight:.2f}, "
            f"market={self.market_weight:.2f})"
        )