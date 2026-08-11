"""E12.5.2 — Correlation Engine。

计算基因特征与创意表现之间的相关性，量化每个基因的影响力。

核心流程:
  MetaPatterns + Performance Data
         │
         ▼
  Feature Impact Calculation
         │
         ▼
  GeneImpactScore ranking
         │
         ▼
  输出: 哪些 Gene 对 ROAS/CTR/CVR 影响最大

算法:
  - 对每个基因特征的每个值，计算 success_rate 与全局平均的偏离
  - impact_score = (feature_success_rate - global_success_rate) × sample_factor
  - 正数表示正向影响，负数表示负向影响
"""

from __future__ import annotations

from collections import defaultdict

from .models import GeneImpactScore, MetaPattern


class CorrelationEngine:
    """基因相关性引擎 —— 计算基因对结果的影响力。

    通过比较每个基因特征的成功率与全局平均水平，
    量化每个基因特征对创意表现的贡献。

    Usage:
        >>> engine = CorrelationEngine()
        >>> impacts = engine.calculate_gene_impact(patterns)
        >>> for imp in impacts:
        ...     print(imp.gene_feature, imp.impact_score)
    """

    def calculate_gene_impact(
        self,
        patterns: list[MetaPattern],
    ) -> list[GeneImpactScore]:
        """计算所有基因特征的影响力评分。

        Args:
            patterns: MetaPattern 列表

        Returns:
            GeneImpactScore 列表（按 impact_score 绝对值降序）
        """
        if not patterns:
            return []

        # 全局平均成功率
        global_success_rate = self._calculate_global_success_rate(patterns)

        # 按基因特征聚合
        feature_stats = self._aggregate_feature_stats(patterns)

        # 计算影响力
        impacts: list[GeneImpactScore] = []
        for (gene_category, feature_name, feature_value), stats in feature_stats.items():
            sample_count = stats["count"]
            feature_success_rate = stats["success_rate"]
            avg_roas_gain = stats["avg_roas_gain"]

            # 影响力 = 特征成功率与全局成功率的偏离
            deviation = feature_success_rate - global_success_rate

            # 样本因子：样本越多，置信度越高
            sample_factor = min(sample_count / 10, 1.0)

            # 综合影响力分数
            impact_score = deviation * sample_factor

            # 相关性系数（简化版）
            correlation = deviation * 2  # 缩放到 [-1, 1]

            # 提升百分比
            lift_pct = (feature_success_rate - global_success_rate) / max(global_success_rate, 0.01)

            # 置信度
            confidence = 0.5 + 0.5 * sample_factor

            impact = GeneImpactScore(
                gene_category=gene_category,
                gene_feature=feature_name,
                gene_value=feature_value,
                impact_score=impact_score,
                sample_count=sample_count,
                confidence=confidence,
                correlation=correlation,
                lift_pct=lift_pct,
            )
            impacts.append(impact)

        # 按 impact_score 绝对值降序
        impacts.sort(key=lambda x: abs(x.impact_score), reverse=True)

        return impacts

    def calculate_from_patterns(
        self,
        patterns: list[MetaPattern],
    ) -> list[GeneImpactScore]:
        """从 MetaPattern 列表计算基因影响力（别名）。"""
        return self.calculate_gene_impact(patterns)

    def get_top_positive_impacts(
        self,
        patterns: list[MetaPattern],
        n: int = 10,
    ) -> list[GeneImpactScore]:
        """获取 Top N 正向影响力基因。

        Args:
            patterns: MetaPattern 列表
            n:        返回数量

        Returns:
            正向影响力评分列表
        """
        impacts = self.calculate_gene_impact(patterns)
        positive = [i for i in impacts if i.is_positive]
        return sorted(positive, key=lambda x: x.impact_score, reverse=True)[:n]

    def get_top_negative_impacts(
        self,
        patterns: list[MetaPattern],
        n: int = 10,
    ) -> list[GeneImpactScore]:
        """获取 Top N 负向影响力基因。

        Args:
            patterns: MetaPattern 列表
            n:        返回数量

        Returns:
            负向影响力评分列表
        """
        impacts = self.calculate_gene_impact(patterns)
        negative = [i for i in impacts if i.is_negative]
        return sorted(negative, key=lambda x: x.impact_score)[:n]

    def get_significant_impacts(
        self,
        patterns: list[MetaPattern],
    ) -> list[GeneImpactScore]:
        """获取显著影响力基因。

        Args:
            patterns: MetaPattern 列表

        Returns:
            显著影响力评分列表
        """
        impacts = self.calculate_gene_impact(patterns)
        return [i for i in impacts if i.is_significant]

    def generate_impact_report(
        self,
        patterns: list[MetaPattern],
    ) -> dict:
        """生成基因影响力报告。

        Args:
            patterns: MetaPattern 列表

        Returns:
            报告字典
        """
        impacts = self.calculate_gene_impact(patterns)

        positive = [i for i in impacts if i.is_positive]
        negative = [i for i in impacts if i.is_negative]
        neutral = [i for i in impacts if not i.is_positive and not i.is_negative]

        return {
            "total_genes_analyzed": len(impacts),
            "positive_impact_count": len(positive),
            "negative_impact_count": len(negative),
            "neutral_count": len(neutral),
            "top_positive": [
                {
                    "gene": f"{i.gene_feature}={i.gene_value}",
                    "impact": round(i.impact_score, 4),
                    "category": i.gene_category,
                    "samples": i.sample_count,
                    "confidence": round(i.confidence, 4),
                }
                for i in positive[:5]
            ],
            "top_negative": [
                {
                    "gene": f"{i.gene_feature}={i.gene_value}",
                    "impact": round(i.impact_score, 4),
                    "category": i.gene_category,
                    "samples": i.sample_count,
                    "confidence": round(i.confidence, 4),
                }
                for i in negative[:5]
            ],
            "recommendation": self._generate_recommendation(positive, negative),
        }

    # ── Private ──────────────────────────────────────────────

    @staticmethod
    def _calculate_global_success_rate(patterns: list[MetaPattern]) -> float:
        """计算全局平均成功率。"""
        total_samples = sum(p.sample_count for p in patterns)
        total_successes = sum(p.success_count for p in patterns)
        if total_samples == 0:
            return 0.0
        return total_successes / total_samples

    @staticmethod
    def _aggregate_feature_stats(
        patterns: list[MetaPattern],
    ) -> dict[tuple[str, str, str], dict]:
        """按基因特征聚合统计。

        Args:
            patterns: MetaPattern 列表

        Returns:
            {(gene_category, feature_name, feature_value): {count, success_rate, avg_roas_gain}}
        """
        feature_map: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
            lambda: {"count": 0, "success_count": 0, "total_roas_gain": 0.0}
        )

        for pattern in patterns:
            gene_category = pattern.pattern_type.value
            for feat_name, feat_value in pattern.genes.items():
                key = (gene_category, feat_name, feat_value)
                stats = feature_map[key]
                stats["count"] += pattern.sample_count
                stats["success_count"] += pattern.success_count
                stats["total_roas_gain"] += pattern.avg_roas_gain * pattern.sample_count

        # 计算成功率
        result: dict[tuple[str, str, str], dict] = {}
        for key, stats in feature_map.items():
            count = stats["count"]
            result[key] = {
                "count": int(count),
                "success_rate": stats["success_count"] / count if count > 0 else 0.0,
                "avg_roas_gain": stats["total_roas_gain"] / count if count > 0 else 0.0,
            }

        return result

    @staticmethod
    def _generate_recommendation(
        positive: list[GeneImpactScore],
        negative: list[GeneImpactScore],
    ) -> str:
        """生成影响力推荐。"""
        parts: list[str] = []

        if positive:
            top_pos = positive[:3]
            parts.append(
                "Amplify: "
                + ", ".join(f"{i.gene_feature}={i.gene_value}" for i in top_pos)
            )

        if negative:
            top_neg = negative[:3]
            parts.append(
                "Suppress: "
                + ", ".join(f"{i.gene_feature}={i.gene_value}" for i in top_neg)
            )

        if not parts:
            return "No significant gene impact found. Continue exploration."

        return " | ".join(parts)

    def __repr__(self) -> str:
        return "CorrelationEngine()"