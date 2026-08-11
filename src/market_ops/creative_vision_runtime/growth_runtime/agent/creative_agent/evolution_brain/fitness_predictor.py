"""E14.5.5 Fitness Prediction Engine — 预测试筛选.

职责:
  1. 在真实投放前，基于历史基因表现预测新基因组的 Fitness
  2. 筛选出预测表现好的基因组进入 Meta 实验
  3. 降低测试成本 — 1000 个创意中只投放预测 Fitness 高的

核心概念:
  - 类似 AlphaZero 的预模拟 — 先预测，再验证
  - 基于基因级别的历史表现 (GenePerformance) 推算基因组级别表现
  - 每个基因槽位按权重贡献到最终预测
  - 置信度基于样本量 — 数据越多，预测越可靠

数据流:
  CreativeGenome (genes dict)
       ↓
  FitnessPredictor.predict(genome)
       ↓
  FitnessPrediction (predicted_ctr, predicted_roas, confidence)
       ↓
  threshold check → 进入 Meta 实验 / 跳过

用法:
    predictor = FitnessPredictor(genome_intelligence=gi)
    prediction = predictor.predict(genome)
    if prediction.is_above_threshold():
        # 投放 Meta 测试
        pass
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.genome_intelligence import (
    GenomeIntelligence,
    GenomeIntelligenceReport,
    GeneIntelligence,
    GenePerformance,
)
from market_ops.e11.genome.schema import CreativeGenome


# ═══════════════════════════════════════════════════════════
# 基因重要性权重
# ═══════════════════════════════════════════════════════════

# 基于创意分析经验:
#   hook (心理钩子) > visual (视觉风格) > gameplay (游戏机制) > emotion (情感) > monetization (变现)
GENE_IMPORTANCE_WEIGHTS: dict[str, float] = {
    "hook": 0.35,
    "visual": 0.25,
    "gameplay": 0.20,
    "emotion": 0.15,
    "reward": 0.05,  # 变现基因
}

# 默认基因表现 (当没有历史数据时使用)
DEFAULT_GENE_PERFORMANCE: dict[str, float] = {
    "ctr": 0.02,     # 2% CTR
    "roas": 1.0,     # 1.0 ROAS
    "cpi": 2.0,      # $2 CPI
    "ltv": 3.0,      # $3 LTV
    "payer_rate": 0.03,  # 3% 付费率
}


# ═══════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessPrediction:
    """单个基因组的 Fitness 预测.

    Attributes:
        prediction_id: 预测 ID
        genome_id: 基因组 ID
        predicted_ctr: 预测 CTR
        predicted_roas: 预测 ROAS
        predicted_cpi: 预测 CPI
        predicted_ltv: 预测 LTV
        predicted_payer_rate: 预测付费率
        confidence: 综合置信度 (0-1)
        fitness_score: 综合 Fitness 分数
        gene_contributions: 各基因的贡献详情
        pass_threshold: 是否通过阈值
        summary: 预测摘要
        created_at: 创建时间
    """
    prediction_id: str = field(default_factory=lambda: f"fp_{uuid.uuid4().hex[:8]}")
    genome_id: str = ""
    predicted_ctr: float = 0.0
    predicted_roas: float = 0.0
    predicted_cpi: float = 0.0
    predicted_ltv: float = 0.0
    predicted_payer_rate: float = 0.0
    confidence: float = 0.0
    fitness_score: float = 0.0
    gene_contributions: dict[str, dict[str, Any]] = field(default_factory=dict)
    pass_threshold: bool = False
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def is_pass(self) -> bool:
        """是否通过阈值."""
        return self.pass_threshold

    def is_high_confidence(self) -> bool:
        """是否高置信度."""
        return self.confidence >= 0.6

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "genome_id": self.genome_id,
            "predicted_ctr": round(self.predicted_ctr, 6),
            "predicted_roas": round(self.predicted_roas, 4),
            "predicted_cpi": round(self.predicted_cpi, 4),
            "predicted_ltv": round(self.predicted_ltv, 4),
            "predicted_payer_rate": round(self.predicted_payer_rate, 6),
            "confidence": round(self.confidence, 4),
            "fitness_score": round(self.fitness_score, 4),
            "gene_contributions": self.gene_contributions,
            "pass_threshold": self.pass_threshold,
            "summary": self.summary,
            "created_at": self.created_at,
        }


@dataclass
class FitnessPredictionReport:
    """Fitness 预测报告.

    Attributes:
        report_id: 报告 ID
        total_predicted: 总预测数
        passed_count: 通过阈值数
        pass_rate: 通过率
        avg_predicted_roas: 平均预测 ROAS
        avg_confidence: 平均置信度
        predictions: 预测结果列表
        summary: 报告摘要
        created_at: 创建时间
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    total_predicted: int = 0
    passed_count: int = 0
    pass_rate: float = 0.0
    avg_predicted_roas: float = 0.0
    avg_confidence: float = 0.0
    predictions: list[FitnessPrediction] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_predicted": self.total_predicted,
            "passed_count": self.passed_count,
            "pass_rate": round(self.pass_rate, 4),
            "avg_predicted_roas": round(self.avg_predicted_roas, 4),
            "avg_confidence": round(self.avg_confidence, 4),
            "predictions": [p.to_dict() for p in self.predictions],
            "summary": self.summary,
            "created_at": self.created_at,
        }


# ═══════════════════════════════════════════════════════════
# FitnessPredictor
# ═══════════════════════════════════════════════════════════

class FitnessPredictor:
    """Fitness 预测引擎 — 在投放前预测基因组表现.

    核心逻辑:
      1. 将基因组拆解为基因槽位
      2. 从 GenomeIntelligence 查找每个基因值的历史表现
      3. 按基因重要性权重加权组合
      4. 生成综合 Fitness 预测

    基因贡献计算:
      Fitness = Σ (gene_weight × gene_performance)
      Confidence = min(gene_confidences) × coverage_factor

    用法:
        predictor = FitnessPredictor(genome_intelligence=gi)
        prediction = predictor.predict(genome)
        if prediction.is_pass():
            # 进入 Meta 实验
    """

    # 默认阈值
    DEFAULT_ROAS_THRESHOLD = 1.0      # ROAS >= 1.0
    DEFAULT_CTR_THRESHOLD = 0.015     # CTR >= 1.5%
    DEFAULT_CONFIDENCE_THRESHOLD = 0.3  # 置信度 >= 0.3
    DEFAULT_MIN_SAMPLES = 2           # 每个基因最少样本数

    def __init__(
        self,
        genome_intelligence: GenomeIntelligence | None = None,
        roas_threshold: float = DEFAULT_ROAS_THRESHOLD,
        ctr_threshold: float = DEFAULT_CTR_THRESHOLD,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ):
        self._genome_intelligence = genome_intelligence
        self._roas_threshold = roas_threshold
        self._ctr_threshold = ctr_threshold
        self._confidence_threshold = confidence_threshold
        self._min_samples = min_samples
        self._prediction_count: int = 0
        self._prediction_history: list[FitnessPrediction] = []

    # ── 主入口 ──────────────────────────────────────────────

    def predict(
        self,
        genome: CreativeGenome,
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> FitnessPrediction:
        """预测单个基因组的 Fitness.

        Args:
            genome: 目标基因组
            genome_report: 基因组智能报告 (可选，不提供则自动获取)

        Returns:
            FitnessPrediction: 预测结果
        """
        self._prediction_count += 1

        report = genome_report
        if report is None and self._genome_intelligence:
            report = self._genome_intelligence.analyze()

        # 计算各基因贡献
        contributions: dict[str, dict[str, Any]] = {}
        weighted_ctr = 0.0
        weighted_roas = 0.0
        weighted_cpi = 0.0
        weighted_ltv = 0.0
        weighted_payer = 0.0
        total_weight = 0.0
        confidences: list[float] = []
        covered_genes = 0

        for gene_slot, gene_data in genome.genes.items():
            weight = GENE_IMPORTANCE_WEIGHTS.get(gene_slot, 0.05)
            gene_value = self._extract_gene_value(gene_data)

            # 查找历史表现
            perf = self._lookup_performance(gene_slot, gene_value, report)

            ctr = perf.avg_ctr if perf and perf.avg_ctr > 0 else DEFAULT_GENE_PERFORMANCE["ctr"]
            roas = perf.avg_roas if perf and perf.avg_roas > 0 else DEFAULT_GENE_PERFORMANCE["roas"]
            ltv = perf.avg_ltv if perf and perf.avg_ltv > 0 else DEFAULT_GENE_PERFORMANCE["ltv"]
            payer = perf.avg_payer_rate if perf and perf.avg_payer_rate > 0 else DEFAULT_GENE_PERFORMANCE["payer_rate"]
            conf = perf.confidence if perf else 0.1

            weighted_ctr += ctr * weight
            weighted_roas += roas * weight
            weighted_ltv += ltv * weight
            weighted_payer += payer * weight
            total_weight += weight

            if perf and perf.samples >= self._min_samples:
                confidences.append(conf)
                covered_genes += 1

            contributions[gene_slot] = {
                "gene_value": gene_value,
                "weight": weight,
                "ctr": round(ctr, 6),
                "roas": round(roas, 4),
                "ltv": round(ltv, 4),
                "payer_rate": round(payer, 6),
                "confidence": round(conf, 4),
                "samples": perf.samples if perf else 0,
            }

        # 归一化
        if total_weight > 0:
            predicted_ctr = weighted_ctr / total_weight
            predicted_roas = weighted_roas / total_weight
            predicted_ltv = weighted_ltv / total_weight
            predicted_payer = weighted_payer / total_weight
        else:
            predicted_ctr = DEFAULT_GENE_PERFORMANCE["ctr"]
            predicted_roas = DEFAULT_GENE_PERFORMANCE["roas"]
            predicted_ltv = DEFAULT_GENE_PERFORMANCE["ltv"]
            predicted_payer = DEFAULT_GENE_PERFORMANCE["payer_rate"]

        # CPI 从 ROAS 和 LTV 反推: CPI = LTV / ROAS (简化)
        if predicted_roas > 0:
            predicted_cpi = predicted_ltv / predicted_roas
        else:
            predicted_cpi = DEFAULT_GENE_PERFORMANCE["cpi"]

        # 综合置信度
        if confidences:
            min_conf = min(confidences)
            coverage = covered_genes / max(len(genome.genes), 1)
            confidence = min_conf * 0.6 + coverage * 0.4
        else:
            confidence = 0.1

        # 综合 Fitness 分数
        fitness_score = self._calculate_fitness_score(
            predicted_roas, predicted_ctr, predicted_ltv, predicted_payer
        )

        # 阈值判断
        pass_threshold = (
            predicted_roas >= self._roas_threshold
            and predicted_ctr >= self._ctr_threshold
            and confidence >= self._confidence_threshold
        )

        # 生成摘要
        summary = self._generate_summary(
            genome.genome_id,
            predicted_roas,
            predicted_ctr,
            confidence,
            pass_threshold,
            covered_genes,
            len(genome.genes),
        )

        prediction = FitnessPrediction(
            genome_id=genome.genome_id,
            predicted_ctr=predicted_ctr,
            predicted_roas=predicted_roas,
            predicted_cpi=predicted_cpi,
            predicted_ltv=predicted_ltv,
            predicted_payer_rate=predicted_payer,
            confidence=confidence,
            fitness_score=fitness_score,
            gene_contributions=contributions,
            pass_threshold=pass_threshold,
            summary=summary,
        )

        self._prediction_history.append(prediction)
        return prediction

    def predict_batch(
        self,
        genomes: list[CreativeGenome],
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> list[FitnessPrediction]:
        """批量预测基因组 Fitness.

        Args:
            genomes: 目标基因组列表
            genome_report: 基因组智能报告

        Returns:
            list[FitnessPrediction]: 预测结果列表
        """
        report = genome_report
        if report is None and self._genome_intelligence:
            report = self._genome_intelligence.analyze()

        predictions = []
        for genome in genomes:
            predictions.append(self.predict(genome, genome_report=report))

        return predictions

    def filter_by_threshold(
        self,
        predictions: list[FitnessPrediction],
    ) -> list[FitnessPrediction]:
        """筛选通过阈值的预测."""
        return [p for p in predictions if p.pass_threshold]

    def rank_by_fitness(
        self,
        predictions: list[FitnessPrediction],
        top_n: int | None = None,
    ) -> list[FitnessPrediction]:
        """按 Fitness 分数降序排列."""
        ranked = sorted(predictions, key=lambda p: p.fitness_score, reverse=True)
        if top_n:
            return ranked[:top_n]
        return ranked

    def select_top_candidates(
        self,
        genomes: list[CreativeGenome],
        top_n: int = 10,
        genome_report: GenomeIntelligenceReport | None = None,
    ) -> list[FitnessPrediction]:
        """选择 Top N 候选基因组进入实验.

        Pipeline:
          predict_batch → filter_by_threshold → rank_by_fitness → top_n

        Args:
            genomes: 候选基因组列表
            top_n: 返回 Top N
            genome_report: 基因组智能报告

        Returns:
            list[FitnessPrediction]: Top N 预测结果
        """
        predictions = self.predict_batch(genomes, genome_report=genome_report)
        passed = self.filter_by_threshold(predictions)
        return self.rank_by_fitness(passed, top_n=top_n)

    # ── 内部方法 ────────────────────────────────────────────

    def _extract_gene_value(self, gene_data: Any) -> str:
        """从基因数据中提取基因值."""
        if isinstance(gene_data, dict):
            # 尝试提取具体的基因值: type > style > primary > mechanic > value
            for key in ("type", "style", "primary", "mechanic", "value"):
                if key in gene_data:
                    return str(gene_data[key])
            return str(gene_data)
        return str(gene_data)

    def _lookup_performance(
        self,
        gene_slot: str,
        gene_value: str,
        report: GenomeIntelligenceReport | None,
    ) -> GenePerformance | None:
        """从 GenomeIntelligence 查找基因值的历史表现."""
        if not report:
            return None

        gi = report.genes.get(gene_slot)
        if not gi:
            return None

        for perf in gi.values:
            if perf.gene_value == gene_value:
                return perf

        return None

    def _calculate_fitness_score(
        self,
        roas: float,
        ctr: float,
        ltv: float,
        payer_rate: float,
    ) -> float:
        """计算综合 Fitness 分数.

        公式: ROAS×0.4 + CTR_norm×0.3 + LTV_norm×0.2 + payer_rate_norm×0.1
        """
        ctr_norm = min(ctr / 0.05, 1.0)       # 归一化到 5% CTR
        ltv_norm = min(ltv / 10.0, 1.0)        # 归一化到 $10 LTV
        payer_norm = min(payer_rate / 0.10, 1.0)  # 归一化到 10% 付费率

        return roas * 0.4 + ctr_norm * 0.3 + ltv_norm * 0.2 + payer_norm * 0.1

    def _generate_summary(
        self,
        genome_id: str,
        roas: float,
        ctr: float,
        confidence: float,
        pass_threshold: bool,
        covered_genes: int,
        total_genes: int,
    ) -> str:
        """生成预测摘要."""
        status = "通过" if pass_threshold else "未通过"
        parts = [
            f"Genome {genome_id}: {status}",
            f"预测ROAS={roas:.2f}",
            f"CTR={ctr:.1%}",
            f"置信度={confidence:.0%}",
            f"覆盖基因={covered_genes}/{total_genes}",
        ]
        return " | ".join(parts)

    # ── 查询与报告 ──────────────────────────────────────────

    def get_prediction(self, genome_id: str) -> FitnessPrediction | None:
        """获取指定基因组的预测."""
        for p in reversed(self._prediction_history):
            if p.genome_id == genome_id:
                return p
        return None

    def get_passed(self) -> list[FitnessPrediction]:
        """获取所有通过阈值的预测."""
        return [p for p in self._prediction_history if p.pass_threshold]

    def get_failed(self) -> list[FitnessPrediction]:
        """获取所有未通过阈值的预测."""
        return [p for p in self._prediction_history if not p.pass_threshold]

    def get_recent(self, n: int = 20) -> list[FitnessPrediction]:
        """获取最近的预测."""
        return self._prediction_history[-n:]

    def generate_report(self) -> FitnessPredictionReport:
        """生成预测报告."""
        recent = self._prediction_history[-50:]
        passed = [p for p in recent if p.pass_threshold]

        total = len(recent)
        passed_count = len(passed)
        pass_rate = passed_count / max(total, 1)

        avg_roas = sum(p.predicted_roas for p in recent) / max(total, 1)
        avg_conf = sum(p.confidence for p in recent) / max(total, 1)

        if passed:
            summary = (
                f"共预测 {total} 个基因组，{passed_count} 个通过阈值 "
                f"(通过率 {pass_rate:.0%})。平均预测ROAS={avg_roas:.2f}，"
                f"平均置信度={avg_conf:.0%}"
            )
        elif total > 0:
            summary = (
                f"共预测 {total} 个基因组，0 个通过阈值。"
                f"平均预测ROAS={avg_roas:.2f}，平均置信度={avg_conf:.0%}"
            )
        else:
            summary = "暂无预测记录"

        return FitnessPredictionReport(
            total_predicted=total,
            passed_count=passed_count,
            pass_rate=pass_rate,
            avg_predicted_roas=avg_roas,
            avg_confidence=avg_conf,
            predictions=recent,
            summary=summary,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "total_predictions": len(self._prediction_history),
            "prediction_count": self._prediction_count,
            "passed_count": len(self.get_passed()),
            "failed_count": len(self.get_failed()),
            "roas_threshold": self._roas_threshold,
            "ctr_threshold": self._ctr_threshold,
            "confidence_threshold": self._confidence_threshold,
        }

    def reset(self) -> None:
        self._prediction_history.clear()
        self._prediction_count = 0


# ═══════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════

def create_fitness_predictor(
    genome_intelligence: GenomeIntelligence | None = None,
    roas_threshold: float = 1.0,
    ctr_threshold: float = 0.015,
    confidence_threshold: float = 0.3,
) -> FitnessPredictor:
    """创建默认 FitnessPredictor."""
    return FitnessPredictor(
        genome_intelligence=genome_intelligence,
        roas_threshold=roas_threshold,
        ctr_threshold=ctr_threshold,
        confidence_threshold=confidence_threshold,
    )