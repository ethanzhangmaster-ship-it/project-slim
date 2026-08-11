"""E14.5.2 Population Analyzer — 群体多样性+进化趋势.

职责:
  1. 分析当前 Creative Population 的多样性 (是否同质化风险)
  2. 检测进化趋势 (哪些基因值在上升/下降)
  3. 生成群体健康报告 (PopulationHealthReport)
  4. 为 EvolutionPlanner (E14.5.3) 提供决策依据

核心概念:
  - PopulationDiversity: 群体多样性分析
  - EvolutionTrend: 进化趋势检测
  - PopulationHealthReport: 群体健康综合报告

数据流:
  GenomeIntelligence (E14.5.1) 分析结果
       ↓
  PopulationAnalyzer.analyze()
       ↓
  PopulationHealthReport
       ↓
  EvolutionPlanner (E14.5.3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.genome_intelligence import (
    GenomeIntelligence,
    GeneIntelligence,
    GenomeIntelligenceReport,
    GenePerformance,
)


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class DiversityMetrics:
    """单个基因类别的多样性指标.

    Attributes:
        gene_category: 基因类别
        unique_values: 唯一值数量
        total_samples: 总样本数
        diversity_score: 多样性分数 [0, 1]
        entropy: 香农熵 (越高越均匀/多元)
        dominant_value: 主导基因值
        dominance_ratio: 主导值占比
        risk_level: 风险等级 (low/medium/high/critical)
    """
    gene_category: str = ""
    unique_values: int = 0
    total_samples: int = 0
    diversity_score: float = 0.0
    entropy: float = 0.0
    dominant_value: str = ""
    dominance_ratio: float = 0.0
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "unique_values": self.unique_values,
            "total_samples": self.total_samples,
            "diversity_score": round(self.diversity_score, 3),
            "entropy": round(self.entropy, 3),
            "dominant_value": self.dominant_value,
            "dominance_ratio": round(self.dominance_ratio, 3),
            "risk_level": self.risk_level,
        }


@dataclass
class TrendSignal:
    """单个基因值的趋势信号.

    Attributes:
        gene_category: 基因类别
        gene_value: 基因值
        direction: 趋势方向 (rising/declining/stable)
        strength: 趋势强度 [0, 1]
        recent_win_rate: 近期胜率
        historical_win_rate: 历史胜率
        delta: 变化幅度
        confidence: 置信度
    """
    gene_category: str = ""
    gene_value: str = ""
    direction: str = "stable"
    strength: float = 0.0
    recent_win_rate: float = 0.0
    historical_win_rate: float = 0.0
    delta: float = 0.0
    confidence: float = 0.0

    @property
    def is_significant(self) -> bool:
        """趋势是否显著 (strength >= 0.3 且 confidence >= 0.5)."""
        return self.strength >= 0.3 and self.confidence >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene_category": self.gene_category,
            "gene_value": self.gene_value,
            "direction": self.direction,
            "strength": round(self.strength, 3),
            "recent_win_rate": round(self.recent_win_rate, 3),
            "historical_win_rate": round(self.historical_win_rate, 3),
            "delta": round(self.delta, 3),
            "confidence": round(self.confidence, 3),
            "is_significant": self.is_significant,
        }


@dataclass
class PopulationHealthReport:
    """群体健康综合报告.

    Attributes:
        report_id: 报告 ID
        population_size: 群体大小
        diversity: 各基因类别多样性指标
        overall_diversity_score: 整体多样性分数
        overall_risk_level: 整体风险等级
        trends: 进化趋势信号列表
        rising_genes: 上升基因值列表
        declining_genes: 下降基因值列表
        recommendations: 建议列表
        created_at: 创建时间
    """
    report_id: str = ""
    population_size: int = 0
    diversity: dict[str, DiversityMetrics] = field(default_factory=dict)
    overall_diversity_score: float = 0.0
    overall_risk_level: str = "low"
    trends: list[TrendSignal] = field(default_factory=list)
    rising_genes: list[str] = field(default_factory=list)
    declining_genes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = ""

    @property
    def has_collapse_risk(self) -> bool:
        """是否存在群体崩溃风险."""
        return self.overall_risk_level in ("high", "critical")

    @property
    def significant_trends(self) -> list[TrendSignal]:
        """返回显著趋势."""
        return [t for t in self.trends if t.is_significant]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "population_size": self.population_size,
            "diversity": {k: v.to_dict() for k, v in self.diversity.items()},
            "overall_diversity_score": round(self.overall_diversity_score, 3),
            "overall_risk_level": self.overall_risk_level,
            "trends": [t.to_dict() for t in self.trends],
            "rising_genes": self.rising_genes,
            "declining_genes": self.declining_genes,
            "recommendations": self.recommendations,
            "has_collapse_risk": self.has_collapse_risk,
            "significant_trends": [t.to_dict() for t in self.significant_trends],
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# PopulationAnalyzer — 核心引擎
# ═══════════════════════════════════════════════════════════

class PopulationAnalyzer:
    """群体分析器 — 多样性 + 进化趋势.

    分析当前 Creative Population 的健康状况:
      - 各基因类别多样性
      - 同质化风险检测
      - 进化趋势 (上升/下降)

    用法:
        analyzer = PopulationAnalyzer(genome_intelligence)
        report = analyzer.analyze()
        if report.has_collapse_risk:
            print("WARNING: Population collapse risk detected!")
    """

    # 风险等级阈值
    DIVERSITY_CRITICAL = 0.2   # 多样性 < 0.2 → 严重风险
    DIVERSITY_HIGH_RISK = 0.35  # 多样性 < 0.35 → 高风险
    DIVERSITY_MEDIUM_RISK = 0.5  # 多样性 < 0.5 → 中等风险
    DOMINANCE_CRITICAL = 0.8    # 主导值占比 > 80% → 严重风险

    def __init__(
        self,
        genome_intelligence: GenomeIntelligence | None = None,
        min_trend_samples: int = 10,
        trend_threshold: float = 0.1,
    ):
        self._genome_intelligence = genome_intelligence or GenomeIntelligence()
        self._min_trend_samples = min_trend_samples
        self._trend_threshold = trend_threshold  # 最小变化幅度

    # ── 核心分析 ──────────────────────────────────────────

    def analyze(
        self,
        genome_report: GenomeIntelligenceReport | None = None,
        historical_report: GenomeIntelligenceReport | None = None,
    ) -> PopulationHealthReport:
        """执行群体健康分析.

        Args:
            genome_report: 当前基因组智能报告 (None = 自动生成)
            historical_report: 历史基因组智能报告 (None = 仅分析当前)

        Returns:
            PopulationHealthReport: 群体健康综合报告
        """
        if genome_report is None:
            genome_report = self._genome_intelligence.analyze()

        # 1. 多样性分析
        diversity = self._analyze_diversity(genome_report)

        # 2. 整体多样性分数
        overall_diversity = genome_report.overall_diversity_score

        # 3. 整体风险等级
        overall_risk = self._calculate_overall_risk(diversity, overall_diversity)

        # 4. 趋势分析
        trends: list[TrendSignal] = []
        rising: list[str] = []
        declining: list[str] = []
        if historical_report is not None:
            trends = self._detect_trends(genome_report, historical_report)
            rising = [t.gene_value for t in trends if t.direction == "rising"]
            declining = [t.gene_value for t in trends if t.direction == "declining"]

        # 5. 生成建议
        recommendations = self._generate_recommendations(
            diversity, overall_risk, trends,
        )

        return PopulationHealthReport(
            report_id=f"ph_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            population_size=genome_report.total_dnas_analyzed,
            diversity=diversity,
            overall_diversity_score=overall_diversity,
            overall_risk_level=overall_risk,
            trends=trends,
            rising_genes=rising,
            declining_genes=declining,
            recommendations=recommendations,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── 多样性分析 ────────────────────────────────────────

    def _analyze_diversity(
        self,
        report: GenomeIntelligenceReport,
    ) -> dict[str, DiversityMetrics]:
        """分析各基因类别的多样性."""
        metrics: dict[str, DiversityMetrics] = {}

        for category, gene_intel in report.genes.items():
            total = gene_intel.total_samples
            unique = gene_intel.diversity

            # 计算香农熵
            entropy = self._calculate_entropy(gene_intel.values, total)

            # 多样性分数 (归一化)
            diversity_score = self._normalize_diversity(unique, total)

            # 主导值
            dominant_value = ""
            dominance_ratio = 0.0
            if gene_intel.values:
                dominant = gene_intel.values[0]
                dominant_value = dominant.gene_value
                dominance_ratio = dominant.samples / max(total, 1)

            # 风险等级
            risk = self._assess_diversity_risk(diversity_score, dominance_ratio)

            metrics[category] = DiversityMetrics(
                gene_category=category,
                unique_values=unique,
                total_samples=total,
                diversity_score=diversity_score,
                entropy=entropy,
                dominant_value=dominant_value,
                dominance_ratio=dominance_ratio,
                risk_level=risk,
            )

        return metrics

    def _calculate_entropy(
        self,
        values: list[GenePerformance],
        total_samples: int,
    ) -> float:
        """计算香农熵.

        H = -Σ(p_i * log2(p_i))
        熵越高表示分布越均匀 (多样性越高).
        """
        if total_samples == 0:
            return 0.0

        import math
        entropy = 0.0
        for v in values:
            p = v.samples / total_samples
            if p > 0:
                entropy -= p * math.log2(p)

        return entropy

    def _normalize_diversity(self, unique_values: int, total_samples: int) -> float:
        """归一化多样性分数.

        使用 tanh 映射到 [0, 1].
        """
        if total_samples == 0:
            return 0.0
        import math
        return math.tanh(unique_values / 10.0)

    def _assess_diversity_risk(
        self,
        diversity_score: float,
        dominance_ratio: float,
    ) -> str:
        """评估多样性风险等级."""
        if diversity_score < self.DIVERSITY_CRITICAL or dominance_ratio > self.DOMINANCE_CRITICAL:
            return "critical"
        elif diversity_score < self.DIVERSITY_HIGH_RISK:
            return "high"
        elif diversity_score < self.DIVERSITY_MEDIUM_RISK:
            return "medium"
        return "low"

    def _calculate_overall_risk(
        self,
        diversity: dict[str, DiversityMetrics],
        overall_diversity: float,
    ) -> str:
        """计算整体风险等级."""
        risk_levels = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        if not diversity:
            return "low"

        max_risk = max(risk_levels.get(d.risk_level, 1) for d in diversity.values())

        if max_risk >= 4:
            return "critical"
        elif max_risk >= 3:
            return "high"
        elif max_risk >= 2 or overall_diversity < 0.4:
            return "medium"
        return "low"

    # ── 趋势检测 ──────────────────────────────────────────

    def _detect_trends(
        self,
        current: GenomeIntelligenceReport,
        historical: GenomeIntelligenceReport,
    ) -> list[TrendSignal]:
        """检测进化趋势.

        对比当前 vs 历史基因组报告，识别上升/下降的基因值.
        """
        trends: list[TrendSignal] = []

        for category in self._genome_intelligence.GENE_CATEGORIES:
            cur_gi = current.get_gene(category)
            hist_gi = historical.get_gene(category)
            if not cur_gi or not hist_gi:
                continue

            # 建立历史映射
            hist_rates = {v.gene_value: v for v in hist_gi.values}

            for cur_val in cur_gi.values:
                hist_val = hist_rates.get(cur_val.gene_value)
                if hist_val is None:
                    # 新出现的基因值
                    continue

                # 计算变化
                delta = cur_val.win_rate - hist_val.win_rate
                abs_delta = abs(delta)

                if abs_delta < self._trend_threshold:
                    continue

                # 方向
                direction = "rising" if delta > 0 else "declining"

                # 强度
                sample_factor = min(
                    (cur_val.samples + hist_val.samples) / self._min_trend_samples,
                    1.0,
                )
                strength = min(abs_delta * sample_factor * 3.0, 1.0)

                # 置信度
                confidence = min(
                    (cur_val.confidence + hist_val.confidence) / 2.0,
                    1.0,
                )

                if strength >= 0.2 or direction == "rising":
                    trends.append(TrendSignal(
                        gene_category=category,
                        gene_value=cur_val.gene_value,
                        direction=direction,
                        strength=strength,
                        recent_win_rate=cur_val.win_rate,
                        historical_win_rate=hist_val.win_rate,
                        delta=delta,
                        confidence=confidence,
                    ))

        # 按强度排序
        trends.sort(key=lambda t: t.strength, reverse=True)
        return trends

    # ── 建议生成 ──────────────────────────────────────────

    def _generate_recommendations(
        self,
        diversity: dict[str, DiversityMetrics],
        overall_risk: str,
        trends: list[TrendSignal],
    ) -> list[str]:
        """生成群体健康建议."""
        recommendations: list[str] = []

        # 多样性风险
        for cat, dm in diversity.items():
            if dm.risk_level == "critical":
                recommendations.append(
                    f"CRITICAL: {cat} 基因多样性极低 ({dm.unique_values} 个值), "
                    f"主导值 '{dm.dominant_value}' 占比 {dm.dominance_ratio:.0%}, "
                    f"建议立即引入新变异方向"
                )
            elif dm.risk_level == "high":
                recommendations.append(
                    f"HIGH: {cat} 基因多样性不足, "
                    f"建议增加 {cat} 基因的变异探索"
                )

        # 整体风险
        if overall_risk == "critical":
            recommendations.append(
                "CRITICAL: 群体面临崩溃风险, 建议立即启动多样性拯救计划"
            )
        elif overall_risk == "high":
            recommendations.append(
                "HIGH: 群体同质化严重, 建议扩大基因探索范围"
            )

        # 趋势建议
        significant_rising = [t for t in trends if t.direction == "rising" and t.is_significant]
        significant_declining = [t for t in trends if t.direction == "declining" and t.is_significant]

        if significant_rising:
            genes = [f"{t.gene_category}={t.gene_value}" for t in significant_rising[:3]]
            recommendations.append(
                f"上升趋势: {', '.join(genes)} — 建议加大这些基因的投放比例"
            )

        if significant_declining:
            genes = [f"{t.gene_category}={t.gene_value}" for t in significant_declining[:3]]
            recommendations.append(
                f"下降趋势: {', '.join(genes)} — 建议减少或淘汰这些基因"
            )

        return recommendations

    # ── 快捷查询 ──────────────────────────────────────────

    def check_collapse_risk(
        self,
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> dict[str, Any]:
        """快速检查群体崩溃风险.

        Returns:
            {risk_level, has_risk, critical_genes, recommendations}
        """
        report = self.analyze(genome_report=genome_report)

        critical_genes = [
            cat for cat, dm in report.diversity.items()
            if dm.risk_level == "critical"
        ]

        return {
            "risk_level": report.overall_risk_level,
            "has_risk": report.has_collapse_risk,
            "critical_genes": critical_genes,
            "overall_diversity": report.overall_diversity_score,
            "recommendations": report.recommendations,
        }

    def get_diversity_summary(
        self,
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> dict[str, Any]:
        """获取多样性摘要."""
        if genome_report is None:
            genome_report = self._genome_intelligence.analyze()

        diversity = self._analyze_diversity(genome_report)
        return {
            "overall_score": genome_report.overall_diversity_score,
            "per_gene": {k: v.to_dict() for k, v in diversity.items()},
        }

    def get_evolution_direction(
        self,
        genome_report: GenomeIntelligenceReport,
        historical_report: GenomeIntelligenceReport,
    ) -> dict[str, list[str]]:
        """获取进化方向建议.

        Returns:
            {amplify: [...], suppress: [...], explore: [...]}
        """
        trends = self._detect_trends(genome_report, historical_report)

        amplify = [
            f"{t.gene_category}={t.gene_value}"
            for t in trends if t.direction == "rising" and t.is_significant
        ]
        suppress = [
            f"{t.gene_category}={t.gene_value}"
            for t in trends if t.direction == "declining" and t.is_significant
        ]

        # 探索：当前多样性不足的基因类别
        diversity = self._analyze_diversity(genome_report)
        explore = [
            cat for cat, dm in diversity.items()
            if dm.risk_level in ("high", "critical")
        ]

        return {
            "amplify": amplify,
            "suppress": suppress,
            "explore": explore,
        }

    # ── 生命周期 ──────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "min_trend_samples": self._min_trend_samples,
            "trend_threshold": self._trend_threshold,
            "diversity_thresholds": {
                "critical": self.DIVERSITY_CRITICAL,
                "high": self.DIVERSITY_HIGH_RISK,
                "medium": self.DIVERSITY_MEDIUM_RISK,
            },
        }

    def reset(self) -> None:
        self._genome_intelligence.reset()


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_population_analyzer(
    genome_intelligence: GenomeIntelligence | None = None,
    min_trend_samples: int = 10,
    trend_threshold: float = 0.1,
) -> PopulationAnalyzer:
    """创建 PopulationAnalyzer 实例."""
    return PopulationAnalyzer(
        genome_intelligence=genome_intelligence,
        min_trend_samples=min_trend_samples,
        trend_threshold=trend_threshold,
    )