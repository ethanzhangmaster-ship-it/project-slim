"""E13.3.1 Revenue Rules — 收入信号检测规则.

规则:
  - ROASDropDetector: ROAS 下降检测
  - LTVUpsideDetector: LTV 上升潜力检测
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
    # ROAS Drop
    "roas_drop_pct": 0.30,              # ROAS 下降 30% 触发
    "roas_drop_absolute": 0.3,          # ROAS 绝对值下降 0.3
    "roas_drop_conf_min": 0.6,          # 最低置信度
    "roas_drop_sample_min": 1000,       # 最小样本量
    "roas_drop_spend_min": 100,         # 最小花费

    # LTV Upside
    "ltv_upside_pct": 0.20,             # LTV 超预期 20%
    "ltv_upside_absolute": 2.0,         # LTV 超预期 $2
    "ltv_upside_conf_min": 0.6,         # 最低置信度
    "ltv_upside_sample_min": 1000,      # 最小样本量
}


# ═══════════════════════════════════════════════════════════════
# ROASDropDetector
# ═══════════════════════════════════════════════════════════════


class ROASDropDetector:
    """ROAS 下降检测器.

    检测逻辑:
      roas_decay = (predicted_roas - current_roas) / predicted_roas
      当 roas_decay > 30% 时触发 ROAS_DROP 信号.
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["roas_drop_sample_min"]:
            return None

        if vector.spend < t["roas_drop_spend_min"]:
            return None

        current_roas = vector.d7_roas
        # 使用 D30 ROAS 作为预测基准
        predicted_roas = vector.d30_roas

        if predicted_roas <= 0:
            # 没有预测 ROAS 时，使用分类基准
            predicted_roas = (benchmarks or {}).get("avg_d7_roas", 1.0)

        if predicted_roas <= 0:
            return None

        # 计算 ROAS 衰减
        roas_decay = (predicted_roas - current_roas) / max(predicted_roas, 0.001)
        roas_absolute_drop = predicted_roas - current_roas

        reasons: list[str] = []
        confidence = 0.0

        if roas_decay > t["roas_drop_pct"]:
            reasons.append(f"ROAS decay {roas_decay*100:.0f}% exceeds threshold {t['roas_drop_pct']*100:.0f}%")
            confidence += 0.5

        if roas_absolute_drop > t["roas_drop_absolute"]:
            reasons.append(f"ROAS absolute drop {roas_absolute_drop:.2f} exceeds {t['roas_drop_absolute']}")
            confidence += 0.3

        if confidence < t["roas_drop_conf_min"]:
            return None

        severity = SignalSeverity.CRITICAL if roas_decay > 0.5 else (
            SignalSeverity.HIGH if roas_decay > 0.3 else SignalSeverity.MEDIUM
        )

        return GrowthSignal(
            signal_type=SignalType.ROAS_DROP,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.REVENUE,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "current_d7_roas": current_roas,
                "predicted_roas": predicted_roas,
                "roas_decay_pct": round(roas_decay, 4),
                "roas_absolute_drop": round(roas_absolute_drop, 4),
                "spend": vector.spend,
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "roas_drop_pct": t["roas_drop_pct"],
                "roas_drop_absolute": t["roas_drop_absolute"],
            },
            explanation=(
                f"ROAS dropping: D7={current_roas:.2f} vs predicted={predicted_roas:.2f}, "
                f"decay={roas_decay*100:.1f}%"
            ),
            rule_name="roas_drop_detector",
            source_vector_id=vector.creative_id,
        )


# ═══════════════════════════════════════════════════════════════
# LTVUpsideDetector
# ═══════════════════════════════════════════════════════════════


class LTVUpsideDetector:
    """LTV 上升潜力检测器.

    检测逻辑:
      D30 LTV 显著高于 D7 预测 → 存在 LTV 上升空间
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["ltv_upside_sample_min"]:
            return None

        d7_ltv = vector.d7_ltv
        d30_ltv = vector.d30_ltv

        if d7_ltv <= 0:
            return None

        ltv_ratio = (d30_ltv - d7_ltv) / d7_ltv
        ltv_absolute_gain = d30_ltv - d7_ltv

        reasons: list[str] = []
        confidence = 0.0

        if ltv_ratio > t["ltv_upside_pct"]:
            reasons.append(f"LTV upside {ltv_ratio*100:.0f}% exceeds threshold")
            confidence += 0.5

        if ltv_absolute_gain > t["ltv_upside_absolute"]:
            reasons.append(f"LTV absolute gain ${ltv_absolute_gain:.2f} exceeds ${t['ltv_upside_absolute']}")
            confidence += 0.3

        if confidence < t["ltv_upside_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if ltv_ratio > 0.5 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.LTV_UPSIDE,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.REVENUE,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "d7_ltv": d7_ltv,
                "d30_ltv": d30_ltv,
                "ltv_ratio": round(ltv_ratio, 4),
                "ltv_absolute_gain": round(ltv_absolute_gain, 4),
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "ltv_upside_pct": t["ltv_upside_pct"],
                "ltv_upside_absolute": t["ltv_upside_absolute"],
            },
            explanation=(
                f"LTV upside detected: D30=${d30_ltv:.2f} vs D7=${d7_ltv:.2f}, "
                f"gain={ltv_ratio*100:.1f}%"
            ),
            rule_name="ltv_upside_detector",
            source_vector_id=vector.creative_id,
        )