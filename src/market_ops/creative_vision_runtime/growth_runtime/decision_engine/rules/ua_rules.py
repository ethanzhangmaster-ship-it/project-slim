"""E13.3.1 UA Rules — 投放信号检测规则.

规则:
  - ScaleOpportunityDetector: 放量机会检测
  - BudgetWasteDetector: 预算浪费检测
  - MonetizationIssueDetector: 变现问题检测
"""

from __future__ import annotations

from typing import Any

from ..models import (
    GrowthSignal,
    SignalCategory,
    SignalSeverity,
    SignalType,
)


# ═══════════════════════════════════════════════════════════════
# Default Thresholds
# ═══════════════════════════════════════════════════════════════

DEFAULT_THRESHOLDS = {
    # Scale Opportunity
    "scale_roas_multiplier": 1.3,       # ROAS > category_avg * 1.3
    "scale_roas_absolute": 1.5,         # 或 ROAS > 1.5
    "scale_spend_max_ratio": 0.5,       # 当前 spend < category_avg * 0.5 (表示预算偏低)
    "scale_conf_min": 0.6,              # 最低置信度
    "scale_sample_min": 3000,           # 最小样本量
    "scale_growth_potential_min": 0.5,  # 增长潜力最低分

    # Budget Waste
    "waste_roas_max": 0.5,             # ROAS < 0.5
    "waste_spend_min": 200,             # 至少花费 $200
    "waste_spend_increase": 0.3,        # Spend 增长 30% 但 Revenue 不涨
    "waste_conf_min": 0.5,              # 最低置信度
    "waste_sample_min": 1000,           # 最小样本量

    # Monetization Issue
    "monetization_iap_conversion_min": 0.01,  # IAP 转化率 < 1%
    "monetization_ad_arpdau_min": 0.01,       # IAA ARPDAU < $0.01
    "monetization_conf_min": 0.4,             # 最低置信度
    "monetization_sample_min": 1000,          # 最小样本量
}


# ═══════════════════════════════════════════════════════════════
# ScaleOpportunityDetector
# ═══════════════════════════════════════════════════════════════


class ScaleOpportunityDetector:
    """放量机会检测器.

    检测逻辑:
      ROAS 高 + 预算相对低 + 增长空间大 → SCALE_OPPORTUNITY
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["scale_sample_min"]:
            return None

        roas = vector.d30_roas or vector.d7_roas
        spend = vector.spend

        avg_roas = (benchmarks or {}).get("avg_d30_roas", 0.0)
        avg_spend = (benchmarks or {}).get("avg_spend", 0.0)

        reasons: list[str] = []
        confidence = 0.0

        # ROAS 高于基准
        if roas > t["scale_roas_absolute"]:
            reasons.append(f"ROAS ({roas:.2f}) above absolute threshold {t['scale_roas_absolute']}")
            confidence += 0.35

        if avg_roas > 0 and roas > avg_roas * t["scale_roas_multiplier"]:
            reasons.append(f"ROAS {((roas/avg_roas)-1)*100:.0f}% above category avg")
            confidence += 0.25

        # 预算相对偏低 (有增长空间)
        if avg_spend > 0 and spend < avg_spend * t["scale_spend_max_ratio"]:
            reasons.append(f"Spend (${spend:.0f}) below {t['scale_spend_max_ratio']*100:.0f}% of category avg (${avg_spend:.0f})")
            confidence += 0.2

        # 增长潜力 (fitness_score 高)
        if vector.fitness_score > t["scale_growth_potential_min"]:
            reasons.append(f"Growth potential (fitness={vector.fitness_score:.2f})")
            confidence += 0.2

        if confidence < t["scale_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if confidence > 0.8 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.SCALE_OPPORTUNITY,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.UA,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "d30_roas": roas,
                "spend": spend,
                "sample_size": float(vector.sample_size),
                "fitness_score": vector.fitness_score,
                "growth_potential": vector.fitness_score,
            },
            thresholds={
                "scale_roas_absolute": t["scale_roas_absolute"],
                "scale_roas_multiplier": t["scale_roas_multiplier"],
                "scale_spend_max_ratio": t["scale_spend_max_ratio"],
            },
            explanation="; ".join(reasons) if reasons else "Scale opportunity detected",
            rule_name="scale_opportunity_detector",
            source_vector_id=vector.creative_id,
        )


# ═══════════════════════════════════════════════════════════════
# BudgetWasteDetector
# ═══════════════════════════════════════════════════════════════


class BudgetWasteDetector:
    """预算浪费检测器.

    检测逻辑:
      Spend 高 + Revenue 低 + ROAS < target → BUDGET_WASTE
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["waste_sample_min"]:
            return None

        if vector.spend < t["waste_spend_min"]:
            return None

        roas = vector.d7_roas
        spend = vector.spend
        revenue = vector.total_revenue

        reasons: list[str] = []
        confidence = 0.0

        if roas < t["waste_roas_max"]:
            reasons.append(f"D7 ROAS ({roas:.2f}) below waste threshold {t['waste_roas_max']}")
            confidence += 0.5

        # Spend 增长但 Revenue 不成比例
        avg_spend = (benchmarks or {}).get("avg_spend", 0.0)
        if avg_spend > 0 and spend > avg_spend * (1 + t["waste_spend_increase"]):
            if revenue < spend * t["waste_roas_max"]:
                reasons.append(f"Spend (${spend:.0f}) growing but revenue (${revenue:.0f}) not following")
                confidence += 0.3

        if confidence < t["waste_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if roas < 0.2 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.BUDGET_WASTE,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.UA,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "d7_roas": roas,
                "spend": spend,
                "total_revenue": revenue,
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "waste_roas_max": t["waste_roas_max"],
                "waste_spend_min": t["waste_spend_min"],
            },
            explanation=(
                f"Budget waste: ROAS={roas:.2f}, Spend=${spend:.0f}, Revenue=${revenue:.0f}"
            ),
            rule_name="budget_waste_detector",
            source_vector_id=vector.creative_id,
        )


# ═══════════════════════════════════════════════════════════════
# MonetizationIssueDetector
# ═══════════════════════════════════════════════════════════════


class MonetizationIssueDetector:
    """变现问题检测器.

    检测逻辑:
      IAP 转化率低 或 IAA ARPDAU 低 → MONETIZATION_ISSUE
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["monetization_sample_min"]:
            return None

        iap_conv = vector.iap_conversion
        ad_arpdau = vector.ad_arpdau

        reasons: list[str] = []
        confidence = 0.0

        if iap_conv > 0 and iap_conv < t["monetization_iap_conversion_min"]:
            reasons.append(f"IAP conversion ({iap_conv:.4f}) below {t['monetization_iap_conversion_min']}")
            confidence += 0.4

        if ad_arpdau > 0 and ad_arpdau < t["monetization_ad_arpdau_min"]:
            reasons.append(f"IAA ARPDAU (${ad_arpdau:.4f}) below ${t['monetization_ad_arpdau_min']}")
            confidence += 0.4

        if confidence < t["monetization_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if confidence > 0.7 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.MONETIZATION_ISSUE,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.MONETIZATION,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "iap_conversion": iap_conv,
                "ad_arpdau": ad_arpdau,
                "ecpm": vector.ecpm,
                "fill_rate": vector.fill_rate,
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "monetization_iap_conversion_min": t["monetization_iap_conversion_min"],
                "monetization_ad_arpdau_min": t["monetization_ad_arpdau_min"],
            },
            explanation="; ".join(reasons) if reasons else "Monetization issue detected",
            rule_name="monetization_issue_detector",
            source_vector_id=vector.creative_id,
        )