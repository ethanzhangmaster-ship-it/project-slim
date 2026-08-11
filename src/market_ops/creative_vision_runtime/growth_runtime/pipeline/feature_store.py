"""E13.2.3 Growth Feature Store — 创意特征向量生成.

核心职责: 基于归因结果，为每个 Creative 生成多维适应度向量 (CreativeFitnessVector)，
作为 E11 Evolution Engine 的真实商业数据输入。

特征向量维度:
  - Acquisition: CTR, CPI, CPM, CPC, Impressions, Clicks, Installs
  - Revenue: IAP Revenue, Ad Revenue, Total Revenue
  - ROAS: D1/D7/D30 ROAS
  - LTV: D7/D30/Predicted LTV
  - Retention: D1/D7/D30 Retention
  - Conversion: IAP Conversion, Payer Rate
  - IAA: Ad ARPDAU, eCPM, Fill Rate
  - Composite: Fitness Score, Revenue Score, Growth Score, Efficiency Score

数据流:
  AttributionEdge[] → GrowthFeatureStore → CreativeFitnessVector[] → E11 Evolution Engine
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import (
    AttributionEdge,
    CreativeFitnessVector,
    PipelineConfig,
    PipelineStats,
)


# ═══════════════════════════════════════════════════════════════
# Growth Feature Store
# ═══════════════════════════════════════════════════════════════


class GrowthFeatureStore:
    """E13.2.3 Growth Feature Store.

    功能:
      1. 从 AttributionEdge 聚合生成 CreativeFitnessVector
      2. 计算复合得分 (Fitness / Revenue / Growth / Efficiency)
      3. 识别 Winner / Fatigued 创意
      4. 输出特征向量供 E11 Evolution Engine 使用
    """

    def __init__(self, config: PipelineConfig | None = None):
        self._config = config or PipelineConfig()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

        # Feature vectors
        self._vectors: dict[str, CreativeFitnessVector] = {}

        # History (for trend detection)
        self._vector_history: dict[str, list[CreativeFitnessVector]] = defaultdict(list)

    # ── Properties ────────────────────────────────────────────

    @property
    def config(self) -> PipelineConfig:
        return self._config

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    @property
    def vector_count(self) -> int:
        return len(self._vectors)

    # ── Feature Computation ───────────────────────────────────

    def compute_features(
        self, attribution_edges: list[AttributionEdge],
    ) -> list[CreativeFitnessVector]:
        """从 AttributionEdge 计算 CreativeFitnessVector.

        Args:
            attribution_edges: 归因边列表

        Returns:
            list[CreativeFitnessVector]: 创意适应度向量列表
        """
        if not attribution_edges:
            return []

        # 1. 按 creative_id 聚合
        creative_data: dict[str, dict[str, Any]] = self._aggregate_edges(attribution_edges)

        # 2. 为每个 Creative 生成向量
        new_vectors: list[CreativeFitnessVector] = []
        for cid, data in creative_data.items():
            vector = self._build_fitness_vector(cid, data)
            self._vectors[cid] = vector
            self._vector_history[cid].append(vector)
            new_vectors.append(vector)

        # 3. 识别 Winner 和 Fatigued
        self._identify_winners_and_fatigued()

        # 4. 更新统计
        self._stats.feature_vectors = len(self._vectors)
        self._stats.total_featurized += len(new_vectors)
        self._stats.winners_count = sum(1 for v in self._vectors.values() if v.is_winner)
        self._stats.fatigued_count = sum(1 for v in self._vectors.values() if v.is_fatigued)

        return new_vectors

    def _aggregate_edges(
        self, edges: list[AttributionEdge],
    ) -> dict[str, dict[str, Any]]:
        """按 creative_id 聚合 AttributionEdge."""
        data: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "creative_name": "",
            "genome_id": "",
            "campaign_id": "",
            "network": "",
            "product_id": "",
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "installs": 0,
            "iap_revenue": 0.0,
            "ad_revenue": 0.0,
            "total_revenue": 0.0,
            "d7_ltv": 0.0,
            "d30_ltv": 0.0,
            "predicted_ltv": 0.0,
            "d1_retention": 0.0,
            "d7_retention": 0.0,
            "d30_retention": 0.0,
            "payer_rate": 0.0,
            "user_count": 0,
            "payer_count": 0,
            "edge_count": 0,
            "dates": set(),
            "attribution_confidences": [],
        })

        for edge in edges:
            cid = edge.creative_id
            d = data[cid]

            d["creative_name"] = edge.creative_name or d["creative_name"]
            d["genome_id"] = edge.genome_id or d["genome_id"]
            d["campaign_id"] = edge.campaign_id or d["campaign_id"]
            d["network"] = edge.network or d["network"]
            d["spend"] += edge.spend
            d["impressions"] += edge.impressions
            d["clicks"] += edge.clicks
            d["installs"] += edge.installs
            d["iap_revenue"] += edge.iap_revenue
            d["ad_revenue"] += edge.ad_revenue
            d["total_revenue"] += edge.total_revenue
            d["d7_ltv"] = max(d["d7_ltv"], edge.d7_ltv)
            d["d30_ltv"] = max(d["d30_ltv"], edge.d30_ltv)
            d["predicted_ltv"] = max(d["predicted_ltv"], edge.predicted_ltv)
            d["d1_retention"] = max(d["d1_retention"], edge.d1_retention)
            d["d7_retention"] = max(d["d7_retention"], edge.d7_retention)
            d["d30_retention"] = max(d["d30_retention"], edge.d30_retention)
            d["user_count"] += 1
            if edge.is_payer:
                d["payer_count"] += 1
            d["edge_count"] += 1
            if edge.date:
                d["dates"].add(edge.date)
            d["attribution_confidences"].append(edge.attribution_confidence)

        # Compute derived metrics
        for cid, d in data.items():
            d["ctr"] = d["clicks"] / d["impressions"] if d["impressions"] > 0 else 0.0
            d["cpi"] = d["spend"] / d["installs"] if d["installs"] > 0 else 0.0
            d["cpm"] = d["spend"] / d["impressions"] * 1000 if d["impressions"] > 0 else 0.0
            d["cpc"] = d["spend"] / d["clicks"] if d["clicks"] > 0 else 0.0
            d["d1_roas"] = d["d7_ltv"] / d["spend"] * 0.3 if d["spend"] > 0 else 0.0
            d["d7_roas"] = d["d7_ltv"] / d["spend"] if d["spend"] > 0 else 0.0
            d["d30_roas"] = d["d30_ltv"] / d["spend"] if d["spend"] > 0 else 0.0
            d["payer_rate"] = d["payer_count"] / d["user_count"] if d["user_count"] > 0 else 0.0
            d["iap_conversion"] = d["payer_rate"]
            d["ad_arpdau"] = d["ad_revenue"] / d["user_count"] if d["user_count"] > 0 else 0.0
            d["ecpm"] = d["ad_revenue"] / d["impressions"] * 1000 if d["impressions"] > 0 else 0.0
            d["fill_rate"] = 0.5  # placeholder, should come from MAX data
            d["sample_size"] = d["user_count"]
            d["confidence"] = (
                sum(d["attribution_confidences"]) / len(d["attribution_confidences"])
                if d["attribution_confidences"] else 0.0
            )

        return data

    def _build_fitness_vector(
        self, creative_id: str, data: dict[str, Any],
    ) -> CreativeFitnessVector:
        """构建 CreativeFitnessVector."""
        # 计算复合得分
        revenue_score = self._compute_revenue_score(data)
        growth_score = self._compute_growth_score(data)
        efficiency_score = self._compute_efficiency_score(data)
        fitness_score = self._compute_fitness_score(
            revenue_score, growth_score, efficiency_score, data
        )
        fatigue_score = self._compute_fatigue_score(data)

        return CreativeFitnessVector(
            creative_id=creative_id,
            creative_name=data["creative_name"],
            genome_id=data["genome_id"],
            product_id=data["product_id"],
            date=max(data["dates"]) if data["dates"] else "",
            # Acquisition
            ctr=data["ctr"],
            cpi=data["cpi"],
            cpm=data["cpm"],
            cpc=data["cpc"],
            impressions=data["impressions"],
            clicks=data["clicks"],
            installs=data["installs"],
            spend=data["spend"],
            # Revenue
            iap_revenue=data["iap_revenue"],
            ad_revenue=data["ad_revenue"],
            total_revenue=data["total_revenue"],
            # ROAS
            d1_roas=data["d1_roas"],
            d7_roas=data["d7_roas"],
            d30_roas=data["d30_roas"],
            # LTV
            d7_ltv=data["d7_ltv"],
            d30_ltv=data["d30_ltv"],
            predicted_ltv=data["predicted_ltv"],
            # Retention
            d1_retention=data["d1_retention"],
            d7_retention=data["d7_retention"],
            d30_retention=data["d30_retention"],
            # Conversion
            iap_conversion=data["iap_conversion"],
            payer_rate=data["payer_rate"],
            # IAA
            ad_arpdau=data["ad_arpdau"],
            ecpm=data["ecpm"],
            fill_rate=data["fill_rate"],
            # Composite
            fitness_score=fitness_score,
            revenue_score=revenue_score,
            growth_score=growth_score,
            efficiency_score=efficiency_score,
            # Confidence
            sample_size=data["sample_size"],
            confidence=data["confidence"],
            # Fatigue
            fatigue_score=fatigue_score,
        )

    # ── Score Computation ─────────────────────────────────────

    def _compute_revenue_score(self, data: dict[str, Any]) -> float:
        """收入得分: 基于 ROAS 和 LTV."""
        d7_roas = data["d7_roas"]
        d30_roas = data["d30_roas"]
        d30_ltv = data["d30_ltv"]

        # ROAS 贡献 (0-1)
        roas_score = min(1.0, max(0.0, (d7_roas * 0.3 + d30_roas * 0.7) / 3.0))

        # LTV 贡献 (0-1)
        ltv_score = min(1.0, d30_ltv / 10.0) if d30_ltv > 0 else 0.0

        # 加权: ROAS 60% + LTV 40%
        return round(roas_score * 0.6 + ltv_score * 0.4, 4)

    def _compute_growth_score(self, data: dict[str, Any]) -> float:
        """增长得分: 基于 CTR, CPI, Install 量."""
        ctr = data["ctr"]
        cpi = data["cpi"]
        installs = data["installs"]

        # CTR 贡献 (0-1)
        ctr_score = min(1.0, ctr / 0.05)  # 5% CTR = 满分

        # CPI 贡献 (0-1): 越低越好
        cpi_score = max(0.0, 1.0 - cpi / 5.0) if cpi > 0 else 1.0

        # Install 贡献 (0-1): 规模越大越好
        install_score = min(1.0, installs / 10000)

        # 加权: CTR 30% + CPI 30% + Install 40%
        return round(ctr_score * 0.3 + cpi_score * 0.3 + install_score * 0.4, 4)

    def _compute_efficiency_score(self, data: dict[str, Any]) -> float:
        """效率得分: 基于 Retention, Payer Rate, CPI."""
        d7_retention = data["d7_retention"]
        payer_rate = data["payer_rate"]
        cpi = data["cpi"]

        # Retention 贡献 (0-1)
        retention_score = min(1.0, d7_retention / 0.3)  # 30% D7 = 满分

        # Payer Rate 贡献 (0-1)
        payer_score = min(1.0, payer_rate / 0.1)  # 10% payer rate = 满分

        # CPI 效率 (0-1): CPI 越低效率越高
        cpi_efficiency = max(0.0, 1.0 - cpi / 3.0) if cpi > 0 else 1.0

        # 加权: Retention 40% + Payer 30% + CPI 30%
        return round(retention_score * 0.4 + payer_score * 0.3 + cpi_efficiency * 0.3, 4)

    def _compute_fitness_score(
        self,
        revenue_score: float,
        growth_score: float,
        efficiency_score: float,
        data: dict[str, Any],
    ) -> float:
        """综合适应度得分.

        公式: revenue×0.4 + efficiency×0.3 + growth×0.3
        (与 E11.6.3 的 fitness 公式保持一致)
        """
        return round(revenue_score * 0.4 + efficiency_score * 0.3 + growth_score * 0.3, 4)

    def _compute_fatigue_score(self, data: dict[str, Any]) -> float:
        """计算疲劳得分 (0-1, 越高越疲劳)."""
        # 基于 CTR 趋势和历史数据
        # 简化实现: 基于样本量 / impressions 的衰减
        impressions = data["impressions"]
        ctr = data["ctr"]

        if impressions == 0:
            return 0.0

        # 高曝光量 + 低 CTR = 疲劳信号
        impression_factor = min(1.0, impressions / 100000)
        ctr_factor = max(0.0, 1.0 - ctr / 0.03)  # CTR < 3% 开始疲劳

        return round(impression_factor * 0.6 + ctr_factor * 0.4, 4)

    # ── Winner / Fatigued Identification ──────────────────────

    def _identify_winners_and_fatigued(self) -> None:
        """识别 Winner 和 Fatigued 创意."""
        if not self._vectors:
            return

        # 按 fitness_score 排序
        sorted_vectors = sorted(
            self._vectors.values(),
            key=lambda v: v.fitness_score,
            reverse=True,
        )

        # Winner: fitness_score >= threshold 且 sample_size >= min
        threshold = self._config.winner_threshold
        min_sample = self._config.min_sample_size

        for vector in sorted_vectors:
            if vector.fitness_score >= threshold and vector.sample_size >= min_sample:
                vector.is_winner = True

            # Fatigued: fatigue_score >= 0.7
            if vector.fatigue_score >= 0.7:
                vector.is_fatigued = True

    # ── Query ─────────────────────────────────────────────────

    def get_vector(self, creative_id: str) -> CreativeFitnessVector | None:
        """获取指定 Creative 的适应度向量."""
        return self._vectors.get(creative_id)

    def get_all_vectors(self) -> list[CreativeFitnessVector]:
        """获取所有适应度向量."""
        return list(self._vectors.values())

    def get_winners(self) -> list[CreativeFitnessVector]:
        """获取所有 Winner."""
        return [v for v in self._vectors.values() if v.is_winner]

    def get_fatigued(self) -> list[CreativeFitnessVector]:
        """获取所有 Fatigued."""
        return [v for v in self._vectors.values() if v.is_fatigued]

    def get_hybrid_vectors(self) -> list[CreativeFitnessVector]:
        """获取混合变现的 Creative."""
        return [v for v in self._vectors.values() if v.is_hybrid]

    def get_confident_vectors(self) -> list[CreativeFitnessVector]:
        """获取高置信度的向量."""
        return [v for v in self._vectors.values() if v.is_confident]

    def get_top_by_fitness(self, limit: int = 10) -> list[CreativeFitnessVector]:
        """按 fitness_score 排序."""
        sorted_vectors = sorted(
            self._vectors.values(),
            key=lambda v: v.fitness_score,
            reverse=True,
        )
        return sorted_vectors[:limit]

    def get_top_by_revenue(self, limit: int = 10) -> list[CreativeFitnessVector]:
        """按 total_revenue 排序."""
        sorted_vectors = sorted(
            self._vectors.values(),
            key=lambda v: v.total_revenue,
            reverse=True,
        )
        return sorted_vectors[:limit]

    def get_top_by_roas(self, limit: int = 10) -> list[CreativeFitnessVector]:
        """按 d30_roas 排序."""
        sorted_vectors = sorted(
            self._vectors.values(),
            key=lambda v: v.d30_roas,
            reverse=True,
        )
        return sorted_vectors[:limit]

    # ── Export ────────────────────────────────────────────────

    def export_feature_matrix(self) -> dict[str, list[float]]:
        """导出特征矩阵 (用于 ML 训练)."""
        matrix: dict[str, list[float]] = {}
        for cid, vector in self._vectors.items():
            matrix[cid] = vector.to_vector()
        return matrix

    def export_for_evolution(self) -> list[dict[str, Any]]:
        """导出给 E11 Evolution Engine 的数据."""
        result: list[dict[str, Any]] = []
        for vector in self.get_confident_vectors():
            result.append({
                "creative_id": vector.creative_id,
                "genome_id": vector.genome_id,
                "fitness_score": vector.fitness_score,
                "revenue_score": vector.revenue_score,
                "growth_score": vector.growth_score,
                "efficiency_score": vector.efficiency_score,
                "d30_roas": vector.d30_roas,
                "d30_ltv": vector.d30_ltv,
                "is_winner": vector.is_winner,
                "is_fatigued": vector.is_fatigued,
                "sample_size": vector.sample_size,
                "confidence": vector.confidence,
                "feature_vector": vector.to_vector(),
            })
        return result

    # ── Lifecycle ─────────────────────────────────────────────

    def flush(self) -> None:
        """清空特征数据."""
        self._vectors.clear()
        self._vector_history.clear()

    def reset(self) -> None:
        """重置 Feature Store."""
        self.flush()
        self._stats = PipelineStats(pipeline_name=self._config.pipeline_name)

    def get_summary(self) -> dict[str, Any]:
        """获取 Feature Store 摘要."""
        return {
            "total_vectors": self.vector_count,
            "winners_count": len(self.get_winners()),
            "fatigued_count": len(self.get_fatigued()),
            "hybrid_count": len(self.get_hybrid_vectors()),
            "confident_count": len(self.get_confident_vectors()),
            "avg_fitness": round(
                sum(v.fitness_score for v in self._vectors.values()) / max(1, self.vector_count), 4
            ),
            "top_winners": [
                {
                    "creative_id": v.creative_id,
                    "fitness_score": v.fitness_score,
                    "d30_roas": v.d30_roas,
                    "total_revenue": v.total_revenue,
                }
                for v in self.get_top_by_fitness(5)
            ],
        }