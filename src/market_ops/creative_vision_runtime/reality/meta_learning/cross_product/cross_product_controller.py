"""E12.6.4 — Cross Product Controller。

跨产品智能控制器 —— E12.6.4 核心。

整合:
  - ProductProfiler:     产品画像构建
  - SimilarityEngine:    相似度计算
  - UniversalPatternLibrary: 通用模式库
  - TransferEngine:      知识迁移决策

流程:
  Products → Profiles → Similarity → Patterns → Transfer → CrossLearningResult
"""

from __future__ import annotations

from typing import Any

from .models import (
    CrossLearningResult,
    KnowledgeTransfer,
    ProductFeature,
    ProductProfile,
    SimilarityResult,
    TransferDecision,
    UniversalPattern,
)
from .product_profiler import ProductProfiler
from .similarity_engine import SimilarityEngine
from .universal_pattern_library import UniversalPatternLibrary
from .transfer_engine import TransferEngine


class CrossProductController:
    """跨产品智能控制器。

    职责:
      1. 构建产品画像
      2. 计算产品间相似度
      3. 挖掘通用模式
      4. 评估知识迁移
      5. 更新模式库
      6. 输出跨产品学习结果
    """

    def __init__(
        self,
        profiler: ProductProfiler | None = None,
        similarity_engine: SimilarityEngine | None = None,
        pattern_library: UniversalPatternLibrary | None = None,
        transfer_engine: TransferEngine | None = None,
    ) -> None:
        self.profiler = profiler or ProductProfiler()
        self.similarity_engine = similarity_engine or SimilarityEngine()
        self.pattern_library = pattern_library or UniversalPatternLibrary()
        self.transfer_engine = transfer_engine or TransferEngine()

    def learn_from_products(
        self,
        product_data: list[dict[str, Any]],
        patterns: list[UniversalPattern] | None = None,
    ) -> CrossLearningResult:
        """核心入口：从产品列表学习跨产品知识。

        流程:
          1. 构建产品画像
          2. 计算相似度
          3. 聚类产品
          4. 评估知识迁移
          5. 更新模式库

        Args:
            product_data: 产品数据列表
            patterns:     通用模式列表（可选，不传则使用库中已有模式）

        Returns:
            CrossLearningResult
        """
        # 1. 构建产品画像
        profiles = self.profiler.profile_many(product_data)

        # 2. 计算相似度
        similarities = self.similarity_engine.compute_pairwise_from_profiles(profiles)

        # 3. 聚类
        clusters = self.similarity_engine.cluster_from_profiles(profiles)

        # 4. 获取或使用已有模式
        all_patterns = patterns or self.pattern_library.get_all_patterns()

        # 5. 评估迁移
        transferred: list[KnowledgeTransfer] = []
        rejected = 0

        profile_map = {p.product_id: p for p in profiles}

        for sim in similarities:
            for pattern in all_patterns:
                # 只评估 pattern 来源产品到目标产品的迁移
                if sim.source_product not in pattern.source_products:
                    continue

                decision = self.transfer_engine.evaluate(
                    sim,
                    pattern,
                    profile_map.get(sim.source_product),
                    profile_map.get(sim.target_product),
                )

                if decision.is_allowed:
                    kt = KnowledgeTransfer(
                        source_product=sim.source_product,
                        target_product=sim.target_product,
                        pattern_id=pattern.pattern_id,
                        confidence=decision.confidence,
                        expected_uplift=decision.expected_uplift,
                        decision=decision,
                    )
                    transferred.append(kt)
                    self.pattern_library.record_transfer(pattern.pattern_id, True)
                else:
                    rejected += 1

        # 6. 构建建议
        recommendations = self._build_recommendations(
            profiles, clusters, transferred, similarities
        )

        # 7. 计算置信度增益
        confidence_gain = self._calculate_confidence_gain(transferred)

        return CrossLearningResult(
            source_products=[p.product_id for p in profiles],
            transferred_patterns=len(transferred),
            rejected_patterns=rejected,
            confidence_gain=round(confidence_gain, 4),
            recommendations=recommendations,
            transfers=transferred,
        )

    def evaluate_transfer(
        self,
        source_profile: ProductProfile,
        target_profile: ProductProfile,
        pattern: UniversalPattern,
    ) -> TransferDecision:
        """评估单个知识迁移。

        Args:
            source_profile: 来源产品画像
            target_profile: 目标产品画像
            pattern:        通用模式

        Returns:
            TransferDecision
        """
        similarity = self.similarity_engine.compute_similarity_from_profiles(
            source_profile, target_profile
        )
        return self.transfer_engine.evaluate(
            similarity, pattern, source_profile, target_profile
        )

    def add_pattern(self, pattern: UniversalPattern) -> None:
        """添加通用模式到库。"""
        self.pattern_library.add_pattern(pattern)

    def get_patterns(
        self,
        pattern_type: str | None = None,
        genre: str | None = None,
        min_confidence: float = 0.0,
        proven_only: bool = False,
        limit: int = 50,
    ) -> list[UniversalPattern]:
        """查询通用模式。"""
        return self.pattern_library.query(
            pattern_type=pattern_type,
            genre=genre,
            min_confidence=min_confidence,
            proven_only=proven_only,
            limit=limit,
        )

    def get_clusters(
        self,
        profiles: list[ProductProfile],
    ) -> list[Any]:
        """获取产品聚类。"""
        return self.similarity_engine.cluster_from_profiles(profiles)

    def get_similarity_matrix(
        self,
        profiles: list[ProductProfile],
    ) -> list[SimilarityResult]:
        """获取相似度矩阵。"""
        return self.similarity_engine.compute_pairwise_from_profiles(profiles)

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息。"""
        return self.pattern_library.get_statistics()

    def _build_recommendations(
        self,
        profiles: list[ProductProfile],
        clusters: list[Any],
        transfers: list[KnowledgeTransfer],
        similarities: list[SimilarityResult],
    ) -> list[str]:
        """构建建议列表。"""
        recommendations: list[str] = []

        # 基于聚类建议
        for cluster in clusters:
            if len(cluster.products) >= 2:
                recommendations.append(
                    f"Cluster {cluster.cluster_id}: Products {', '.join(cluster.products)} "
                    f"are highly similar (avg={cluster.avg_similarity:.2f}) — "
                    f"recommend sharing patterns"
                )

        # 基于迁移建议
        if transfers:
            top_transfers = sorted(transfers, key=lambda t: t.confidence, reverse=True)[:3]
            for t in top_transfers:
                recommendations.append(
                    f"Transfer {t.pattern_id} from {t.source_product} to "
                    f"{t.target_product} (confidence={t.confidence:.2f}, "
                    f"expected uplift={t.expected_uplift:.2%})"
                )

        # 高相似度对建议
        top_similar = sorted(similarities, key=lambda s: s.total_similarity, reverse=True)[:3]
        for s in top_similar:
            if s.is_high_similarity:
                recommendations.append(
                    f"High similarity pair: {s.source_product} ↔ {s.target_product} "
                    f"(total={s.total_similarity:.2f}) — "
                    f"prioritize knowledge sharing"
                )

        return recommendations

    def _calculate_confidence_gain(
        self,
        transfers: list[KnowledgeTransfer],
    ) -> float:
        """计算置信度增益。"""
        if not transfers:
            return 0.0
        return sum(t.confidence for t in transfers) / len(transfers)

    def __repr__(self) -> str:
        return (
            f"CrossProductController(patterns={len(self.pattern_library.get_all_patterns())})"
        )