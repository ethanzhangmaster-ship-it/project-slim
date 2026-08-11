"""E13.3.1 Growth Intelligence — 增长洞察分析.

核心职责: 从 CreativeFitnessVector 中发现增长洞察。

分析维度:
  - Winner Discovery: ROAS/LTV 高于品类均值
  - Creative Fatigue: CTR 下降, Frequency 上升
  - ROAS Drop: ROAS 趋势下降
  - Scale Opportunity: 高 ROAS + 低疲劳
  - Budget Misallocation: 低效素材消耗过高预算
  - Hybrid Winner: IAP+IAA 双高

输入: CreativeFitnessVector[]
输出: GrowthInsight[]
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from ..pipeline.models import CreativeFitnessVector
from .models import (
    GrowthInsight,
    InsightType,
    OpportunitySeverity,
)


# ═══════════════════════════════════════════════════════════════
# Growth Intelligence
# ═══════════════════════════════════════════════════════════════


class GrowthIntelligence:
    """E13.3.1 Growth Intelligence — 增长洞察分析器.

    功能:
      1. 从 CreativeFitnessVector 分析增长信号
      2. 识别 Winner / Fatigued / ROAS Drop / Scale Opportunity
      3. 输出可执行的 GrowthInsight
    """

    # 默认阈值
    DEFAULT_THRESHOLDS = {
        "winner_roas": 1.5,          # ROAS > 1.5 视为 Winner
        "winner_ltv": 5.0,           # D30 LTV > $5 视为 Winner
        "fatigue_ctr_drop": 0.3,     # CTR 下降 30% 视为疲劳
        "fatigue_frequency": 3.0,    # Frequency > 3 视为疲劳
        "roas_drop_threshold": 0.3,  # ROAS 下降 30% 视为 ROAS Drop
        "scale_min_roas": 1.3,       # 放量最低 ROAS
        "scale_max_fatigue": 0.3,    # 放量最高疲劳度
        "scale_min_confidence": 0.8, # 放量最低置信度
        "budget_misallocation_roas": 0.8,  # ROAS < 0.8 视为预算错配
        "hybrid_min_iap": 100.0,     # 混合变现最低 IAP
        "hybrid_min_ad": 50.0,       # 混合变现最低 IAA
        "retention_drop": 0.3,       # 留存下降 30%
        "cpi_alert_threshold": 3.0,  # CPI > $3 告警
        "underperforming_roas": 0.5, # ROAS < 0.5 视为严重低效
    }

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._insights: list[GrowthInsight] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def thresholds(self) -> dict[str, float]:
        return self._thresholds

    @property
    def insight_count(self) -> int:
        return len(self._insights)

    # ── Core Analysis ─────────────────────────────────────────

    def analyze(
        self, vectors: list[CreativeFitnessVector],
    ) -> list[GrowthInsight]:
        """分析所有 CreativeFitnessVector，生成洞察列表.

        Args:
            vectors: 创意适应度向量列表

        Returns:
            list[GrowthInsight]: 增长洞察列表
        """
        if not vectors:
            return []

        self._insights = []

        # 计算品类均值
        benchmarks = self._compute_benchmarks(vectors)

        for vector in vectors:
            insights = self._analyze_vector(vector, benchmarks)
            self._insights.extend(insights)

        return self._insights

    def _analyze_vector(
        self, vector: CreativeFitnessVector, benchmarks: dict[str, float],
    ) -> list[GrowthInsight]:
        """分析单个 CreativeFitnessVector."""
        insights: list[GrowthInsight] = []

        # 1. Winner Discovery
        winner = self._detect_winner(vector, benchmarks)
        if winner:
            insights.append(winner)

        # 2. Creative Fatigue
        fatigue = self._detect_fatigue(vector)
        if fatigue:
            insights.append(fatigue)

        # 3. ROAS Drop
        roas_drop = self._detect_roas_drop(vector, benchmarks)
        if roas_drop:
            insights.append(roas_drop)

        # 4. Scale Opportunity
        scale = self._detect_scale_opportunity(vector)
        if scale:
            insights.append(scale)

        # 5. Budget Misallocation
        budget = self._detect_budget_misallocation(vector)
        if budget:
            insights.append(budget)

        # 6. Hybrid Winner
        hybrid = self._detect_hybrid_winner(vector)
        if hybrid:
            insights.append(hybrid)

        # 7. Retention Signal
        retention = self._detect_retention_signal(vector, benchmarks)
        if retention:
            insights.append(retention)

        # 8. CPI Alert
        cpi_alert = self._detect_cpi_alert(vector, benchmarks)
        if cpi_alert:
            insights.append(cpi_alert)

        # 9. Underperforming
        under = self._detect_underperforming(vector)
        if under:
            insights.append(under)

        return insights

    # ── Detection Methods ─────────────────────────────────────

    def _detect_winner(
        self, vector: CreativeFitnessVector, benchmarks: dict[str, float],
    ) -> GrowthInsight | None:
        """检测 Winner Creative."""
        roas = vector.d30_roas
        ltv = vector.d30_ltv
        avg_roas = benchmarks.get("avg_d30_roas", 0)
        avg_ltv = benchmarks.get("avg_d30_ltv", 0)

        reasons: list[str] = []
        confidence = 0.0

        if roas > self._thresholds["winner_roas"]:
            reasons.append(f"D30 ROAS ({roas:.2f}) above threshold ({self._thresholds['winner_roas']})")
            confidence += 0.4

        if avg_roas > 0 and roas > avg_roas * 1.2:
            reasons.append(f"D30 ROAS {((roas/avg_roas)-1)*100:.0f}% above category average")
            confidence += 0.3

        if ltv > self._thresholds["winner_ltv"]:
            reasons.append(f"D30 LTV (${ltv:.2f}) above threshold (${self._thresholds['winner_ltv']})")
            confidence += 0.2

        if avg_ltv > 0 and ltv > avg_ltv * 1.3:
            reasons.append(f"D30 LTV {((ltv/avg_ltv)-1)*100:.0f}% above category average")
            confidence += 0.1

        confidence = min(confidence, 1.0)

        if confidence >= 0.5:
            return GrowthInsight(
                insight_type=InsightType.WINNER_DISCOVERY,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason="; ".join(reasons),
                confidence=confidence,
                severity=OpportunitySeverity.HIGH,
                metrics={"d30_roas": roas, "d30_ltv": ltv, "fitness_score": vector.fitness_score},
                benchmark={"avg_d30_roas": avg_roas, "avg_d30_ltv": avg_ltv},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_fatigue(
        self, vector: CreativeFitnessVector,
    ) -> GrowthInsight | None:
        """检测素材疲劳."""
        fatigue_score = vector.fatigue_score
        ctr = vector.ctr

        reasons: list[str] = []
        confidence = 0.0

        if vector.is_fatigued:
            reasons.append(f"Fatigue score ({fatigue_score:.2f}) above threshold")
            confidence += 0.5

        if ctr < 0.01:
            reasons.append(f"CTR ({ctr:.4f}) critically low")
            confidence += 0.3

        if fatigue_score > 0.5:
            reasons.append(f"High fatigue detected ({fatigue_score:.2f})")
            confidence += 0.2

        confidence = min(confidence, 1.0)

        if confidence >= 0.4:
            return GrowthInsight(
                insight_type=InsightType.CREATIVE_FATIGUE,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason="; ".join(reasons),
                confidence=confidence,
                severity=OpportunitySeverity.HIGH if fatigue_score > 0.7 else OpportunitySeverity.MEDIUM,
                metrics={"fatigue_score": fatigue_score, "ctr": ctr},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_roas_drop(
        self, vector: CreativeFitnessVector, benchmarks: dict[str, float],
    ) -> GrowthInsight | None:
        """检测 ROAS 下降."""
        roas = vector.d30_roas
        avg_roas = benchmarks.get("avg_d30_roas", 0)

        if avg_roas > 0 and roas < avg_roas * 0.7:
            drop_pct = (1 - roas / avg_roas) * 100
            return GrowthInsight(
                insight_type=InsightType.ROAS_DROP,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"ROAS dropped {drop_pct:.0f}% below category average ({roas:.2f} vs {avg_roas:.2f})",
                confidence=0.7,
                severity=OpportunitySeverity.HIGH,
                metrics={"d30_roas": roas, "avg_roas": avg_roas},
                benchmark={"avg_d30_roas": avg_roas},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_scale_opportunity(
        self, vector: CreativeFitnessVector,
    ) -> GrowthInsight | None:
        """检测放量机会."""
        roas = vector.d30_roas
        fatigue = vector.fatigue_score
        confidence = vector.confidence

        if (roas > self._thresholds["scale_min_roas"]
                and fatigue < self._thresholds["scale_max_fatigue"]
                and confidence > self._thresholds["scale_min_confidence"]):
            return GrowthInsight(
                insight_type=InsightType.SCALE_OPPORTUNITY,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"High ROAS ({roas:.2f}) with low fatigue ({fatigue:.2f}) — scale opportunity",
                confidence=0.85,
                severity=OpportunitySeverity.HIGH,
                metrics={"d30_roas": roas, "fatigue_score": fatigue, "confidence": confidence},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_budget_misallocation(
        self, vector: CreativeFitnessVector,
    ) -> GrowthInsight | None:
        """检测预算错配."""
        roas = vector.d30_roas
        spend = vector.spend
        avg_spend = self._thresholds.get("avg_spend", 0)

        if roas < self._thresholds["budget_misallocation_roas"] and spend > 0:
            return GrowthInsight(
                insight_type=InsightType.BUDGET_MISALLOCATION,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"Low ROAS ({roas:.2f}) with high spend (${spend:.2f}) — budget misallocation",
                confidence=0.75,
                severity=OpportunitySeverity.MEDIUM,
                metrics={"d30_roas": roas, "spend": spend},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_hybrid_winner(
        self, vector: CreativeFitnessVector,
    ) -> GrowthInsight | None:
        """检测混合变现 Winner."""
        if vector.is_hybrid:
            iap = vector.iap_revenue
            ad = vector.ad_revenue
            if iap > self._thresholds["hybrid_min_iap"] and ad > self._thresholds["hybrid_min_ad"]:
                return GrowthInsight(
                    insight_type=InsightType.HYBRID_WINNER,
                    creative_id=vector.creative_id,
                    creative_name=vector.creative_name,
                    genome_id=vector.genome_id,
                    product_id=vector.product_id,
                    reason=f"Hybrid monetization winner: IAP ${iap:.2f} + IAA ${ad:.2f}",
                    confidence=0.8,
                    severity=OpportunitySeverity.HIGH,
                    metrics={"iap_revenue": iap, "ad_revenue": ad, "total_revenue": vector.total_revenue},
                    source_vector=vector,
                    date=vector.date,
                )

        return None

    def _detect_retention_signal(
        self, vector: CreativeFitnessVector, benchmarks: dict[str, float],
    ) -> GrowthInsight | None:
        """检测留存信号."""
        d7 = vector.d7_retention
        avg_d7 = benchmarks.get("avg_d7_retention", 0)

        if avg_d7 > 0 and d7 > avg_d7 * 1.3:
            return GrowthInsight(
                insight_type=InsightType.RETENTION_SIGNAL,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"D7 retention ({d7:.2%}) {((d7/avg_d7)-1)*100:.0f}% above average ({avg_d7:.2%})",
                confidence=0.7,
                severity=OpportunitySeverity.MEDIUM,
                metrics={"d7_retention": d7, "avg_d7_retention": avg_d7},
                benchmark={"avg_d7_retention": avg_d7},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_cpi_alert(
        self, vector: CreativeFitnessVector, benchmarks: dict[str, float],
    ) -> GrowthInsight | None:
        """检测 CPI 告警."""
        cpi = vector.cpi
        if cpi > self._thresholds["cpi_alert_threshold"]:
            return GrowthInsight(
                insight_type=InsightType.CPI_ALERT,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"CPI (${cpi:.2f}) above alert threshold (${self._thresholds['cpi_alert_threshold']})",
                confidence=0.8,
                severity=OpportunitySeverity.MEDIUM,
                metrics={"cpi": cpi},
                source_vector=vector,
                date=vector.date,
            )

        return None

    def _detect_underperforming(
        self, vector: CreativeFitnessVector,
    ) -> GrowthInsight | None:
        """检测严重低效素材."""
        roas = vector.d30_roas
        if roas < self._thresholds["underperforming_roas"] and vector.spend > 0:
            return GrowthInsight(
                insight_type=InsightType.UNDERPERFORMING,
                creative_id=vector.creative_id,
                creative_name=vector.creative_name,
                genome_id=vector.genome_id,
                product_id=vector.product_id,
                reason=f"Severely underperforming: ROAS {roas:.2f} below {self._thresholds['underperforming_roas']}",
                confidence=0.9,
                severity=OpportunitySeverity.CRITICAL,
                metrics={"d30_roas": roas, "spend": vector.spend},
                source_vector=vector,
                date=vector.date,
            )

        return None

    # ── Benchmarks ────────────────────────────────────────────

    def _compute_benchmarks(
        self, vectors: list[CreativeFitnessVector],
    ) -> dict[str, float]:
        """计算品类均值."""
        if not vectors:
            return {}

        n = len(vectors)
        benchmarks = {
            "avg_d30_roas": sum(v.d30_roas for v in vectors) / n,
            "avg_d30_ltv": sum(v.d30_ltv for v in vectors) / n,
            "avg_d7_retention": sum(v.d7_retention for v in vectors) / n,
            "avg_ctr": sum(v.ctr for v in vectors) / n,
            "avg_cpi": sum(v.cpi for v in vectors) / n,
            "avg_fitness": sum(v.fitness_score for v in vectors) / n,
            "avg_fatigue": sum(v.fatigue_score for v in vectors) / n,
            "avg_spend": sum(v.spend for v in vectors) / n,
            "avg_payer_rate": sum(v.payer_rate for v in vectors) / n,
        }
        return {k: round(v, 4) for k, v in benchmarks.items()}

    # ── Query ─────────────────────────────────────────────────

    def get_insights_by_type(self, insight_type: InsightType) -> list[GrowthInsight]:
        """按类型获取洞察."""
        return [i for i in self._insights if i.insight_type == insight_type]

    def get_insights_by_creative(self, creative_id: str) -> list[GrowthInsight]:
        """按创意获取洞察."""
        return [i for i in self._insights if i.creative_id == creative_id]

    def get_actionable_insights(self) -> list[GrowthInsight]:
        """获取可执行的洞察 (confidence >= 0.70)."""
        return [i for i in self._insights if i.is_actionable]

    def get_high_confidence_insights(self) -> list[GrowthInsight]:
        """获取高置信度洞察."""
        return [i for i in self._insights if i.is_high_confidence]

    def get_winners(self) -> list[GrowthInsight]:
        """获取 Winner 洞察."""
        return self.get_insights_by_type(InsightType.WINNER_DISCOVERY)

    def get_fatigued(self) -> list[GrowthInsight]:
        """获取疲劳洞察."""
        return self.get_insights_by_type(InsightType.CREATIVE_FATIGUE)

    def get_scale_opportunities(self) -> list[GrowthInsight]:
        """获取放量机会."""
        return self.get_insights_by_type(InsightType.SCALE_OPPORTUNITY)

    def get_all_insights(self) -> list[GrowthInsight]:
        return list(self._insights)

    # ── Lifecycle ─────────────────────────────────────────────

    def reset(self) -> None:
        self._insights.clear()

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_insights": self.insight_count,
            "by_type": {
                t.value: len(self.get_insights_by_type(t))
                for t in InsightType
                if self.get_insights_by_type(t)
            },
            "actionable": len(self.get_actionable_insights()),
            "high_confidence": len(self.get_high_confidence_insights()),
            "winners": len(self.get_winners()),
            "fatigued": len(self.get_fatigued()),
            "scale_opportunities": len(self.get_scale_opportunities()),
        }