"""E13.3.1 Creative Rules — 创意信号检测规则.

规则:
  - CreativeFatigueDetector: 素材疲劳检测
  - CreativeWinnerDetector: 赢家素材发现
  - CreativeUnderperformDetector: 低效素材检测
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
    # Fatigue
    "fatigue_ctr_drop_pct": 0.25,        # CTR 下降 25% 触发疲劳
    "fatigue_roas_drop_pct": 0.25,       # ROAS 下降 25% 触发疲劳
    "fatigue_frequency_min": 3.0,        # Frequency > 3
    "fatigue_score_threshold": 0.75,     # 综合疲劳分数阈值
    "fatigue_conf_min": 0.6,             # 疲劳最低置信度
    "fatigue_min_sample": 1000,          # 最小样本量

    # Winner
    "winner_roas_multiplier": 1.3,       # ROAS > category_avg * 1.3
    "winner_roas_absolute": 1.5,         # 或 ROAS > 1.5 绝对值
    "winner_ltv_min": 5.0,               # D30 LTV > $5
    "winner_fitness_min": 0.8,           # Fitness Score > 0.8
    "winner_sample_min": 5000,           # 最小样本量
    "winner_conf_min": 0.5,              # 最低置信度

    # Underperform
    "underperform_roas_max": 0.5,        # ROAS < 0.5
    "underperform_ctr_max": 0.005,       # CTR < 0.5%
    "underperform_spend_min": 100,       # 至少花费 $100
    "underperform_sample_min": 500,      # 最小样本量
    "underperform_conf_min": 0.6,        # 最低置信度
}


# ═══════════════════════════════════════════════════════════════
# CreativeFatigueDetector
# ═══════════════════════════════════════════════════════════════


class CreativeFatigueDetector:
    """素材疲劳检测器.

    检测逻辑:
      fatigue_score = ctr_decay * 0.4 + roas_decay * 0.4 + frequency_norm * 0.2
      当 fatigue_score > 0.75 时触发 CREATIVE_FATIGUE 信号.
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        """检测单个向量的素材疲劳.

        Args:
            vector: CreativeFitnessVector 实例
            benchmarks: 分类基准数据 (可选)
        """
        t = self._thresholds

        # 需要足够的样本量
        if vector.sample_size < t["fatigue_min_sample"]:
            return None

        # 如果已经标记为疲劳，直接返回
        if getattr(vector, "is_fatigued", False) and vector.fatigue_score > t["fatigue_score_threshold"]:
            return self._build_signal(vector, vector.fatigue_score, 0.9, {})

        # 计算 CTR 下降
        ctr = vector.ctr
        ctr_benchmark = (benchmarks or {}).get("avg_ctr", 0.03)
        ctr_decay = max(0.0, (ctr_benchmark - ctr) / max(ctr_benchmark, 0.001)) if ctr_benchmark > 0 else 0.0

        # 计算 ROAS 下降
        roas = vector.d7_roas
        roas_benchmark = (benchmarks or {}).get("avg_d7_roas", 1.0)
        roas_decay = max(0.0, (roas_benchmark - roas) / max(roas_benchmark, 0.001)) if roas_benchmark > 0 else 0.0

        # Frequency normalization (假设 frequency 保存为 impressions/clicks 的替代)
        frequency = getattr(vector, "frequency", 0.0)
        if frequency <= 0 and vector.clicks > 0:
            frequency = vector.impressions / max(vector.clicks, 1)
        freq_norm = min(1.0, max(0.0, frequency / 10.0))

        # 综合疲劳分数
        fatigue_score = ctr_decay * 0.4 + roas_decay * 0.4 + freq_norm * 0.2

        if fatigue_score < t["fatigue_score_threshold"]:
            return None

        # 置信度计算
        conf = self._calc_confidence(
            ctr_decay > t["fatigue_ctr_drop_pct"],
            roas_decay > t["fatigue_roas_drop_pct"],
            frequency > t["fatigue_frequency_min"],
        )

        if conf < t["fatigue_conf_min"]:
            return None

        return self._build_signal(vector, fatigue_score, conf, benchmarks or {})

    def _build_signal(
        self, vector: Any, fatigue_score: float, confidence: float, benchmarks: dict[str, float]
    ) -> GrowthSignal:
        severity = SignalSeverity.CRITICAL if fatigue_score > 0.9 else (
            SignalSeverity.HIGH if fatigue_score > 0.75 else SignalSeverity.MEDIUM
        )

        return GrowthSignal(
            signal_type=SignalType.CREATIVE_FATIGUE,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.CREATIVE,
            severity=severity,
            confidence=round(confidence, 4),
            metrics={
                "ctr": vector.ctr,
                "d7_roas": vector.d7_roas,
                "fatigue_score": round(fatigue_score, 4),
                "frequency": getattr(vector, "frequency", 0.0),
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "fatigue_score_threshold": self._thresholds["fatigue_score_threshold"],
                "ctr_drop_pct": self._thresholds["fatigue_ctr_drop_pct"],
                "roas_drop_pct": self._thresholds["fatigue_roas_drop_pct"],
                "frequency_min": self._thresholds["fatigue_frequency_min"],
            },
            explanation=(
                f"Creative fatigue detected: CTR={vector.ctr:.4f}, "
                f"D7 ROAS={vector.d7_roas:.2f}, fatigue_score={fatigue_score:.3f}"
            ),
            rule_name="creative_fatigue_detector",
            source_vector_id=vector.creative_id,
        )

    def _calc_confidence(self, ctr_drop: bool, roas_drop: bool, freq_high: bool) -> float:
        """多信号一致性置信度."""
        signals = [ctr_drop, roas_drop, freq_high]
        count = sum(signals)
        return 0.4 + 0.2 * count  # 0.4 ~ 1.0


# ═══════════════════════════════════════════════════════════════
# CreativeWinnerDetector
# ═══════════════════════════════════════════════════════════════


class CreativeWinnerDetector:
    """赢家素材检测器.

    检测逻辑:
      ROAS > category_avg * 1.3 AND LTV > $5 AND fitness > 0.8 AND sample > 5000
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["winner_sample_min"]:
            return None

        roas = vector.d30_roas
        ltv = vector.d30_ltv
        fitness = vector.fitness_score

        avg_roas = (benchmarks or {}).get("avg_d30_roas", 0.0)
        avg_ltv = (benchmarks or {}).get("avg_d30_ltv", 0.0)

        reasons: list[str] = []
        confidence = 0.0

        # ROAS 检查
        if roas > t["winner_roas_absolute"]:
            reasons.append(f"D30 ROAS ({roas:.2f}) above absolute threshold")
            confidence += 0.3
        if avg_roas > 0 and roas > avg_roas * t["winner_roas_multiplier"]:
            reasons.append(f"D30 ROAS {((roas/avg_roas)-1)*100:.0f}% above category avg")
            confidence += 0.25

        # LTV 检查
        if ltv > t["winner_ltv_min"]:
            reasons.append(f"D30 LTV (${ltv:.2f}) above ${t['winner_ltv_min']}")
            confidence += 0.2
        if avg_ltv > 0 and ltv > avg_ltv * 1.2:
            reasons.append(f"D30 LTV {((ltv/avg_ltv)-1)*100:.0f}% above category avg")
            confidence += 0.15

        # Fitness 检查
        if fitness > t["winner_fitness_min"]:
            reasons.append(f"Fitness score ({fitness:.2f}) > {t['winner_fitness_min']}")
            confidence += 0.1

        if confidence < t["winner_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if confidence > 0.8 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.CREATIVE_WINNER,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.CREATIVE,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "d30_roas": roas,
                "d30_ltv": ltv,
                "d7_roas": vector.d7_roas,
                "fitness_score": fitness,
                "sample_size": float(vector.sample_size),
                "spend": vector.spend,
            },
            thresholds={
                "winner_roas_absolute": t["winner_roas_absolute"],
                "winner_roas_multiplier": t["winner_roas_multiplier"],
                "winner_ltv_min": t["winner_ltv_min"],
                "winner_fitness_min": t["winner_fitness_min"],
            },
            explanation="; ".join(reasons),
            rule_name="creative_winner_detector",
            source_vector_id=vector.creative_id,
        )


# ═══════════════════════════════════════════════════════════════
# CreativeUnderperformDetector
# ═══════════════════════════════════════════════════════════════


class CreativeUnderperformDetector:
    """低效素材检测器.

    检测逻辑:
      ROAS < 0.5 AND spend > $100 AND sample > 500
    """

    def __init__(self, thresholds: dict[str, float] | None = None):
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    def detect(self, vector: Any, benchmarks: dict[str, float] | None = None) -> GrowthSignal | None:
        t = self._thresholds

        if vector.sample_size < t["underperform_sample_min"]:
            return None

        if vector.spend < t["underperform_spend_min"]:
            return None

        roas = vector.d7_roas
        ctr = vector.ctr
        reasons: list[str] = []
        confidence = 0.0

        if roas < t["underperform_roas_max"]:
            reasons.append(f"D7 ROAS ({roas:.2f}) below {t['underperform_roas_max']}")
            confidence += 0.5

        if ctr < t["underperform_ctr_max"]:
            reasons.append(f"CTR ({ctr:.4f}) below {t['underperform_ctr_max']}")
            confidence += 0.3

        if confidence < t["underperform_conf_min"]:
            return None

        severity = SignalSeverity.HIGH if roas < 0.2 else SignalSeverity.MEDIUM

        return GrowthSignal(
            signal_type=SignalType.CREATIVE_UNDERPERFORM,
            entity_id=vector.creative_id,
            entity_type="creative",
            category=SignalCategory.CREATIVE,
            severity=severity,
            confidence=round(min(1.0, confidence), 4),
            metrics={
                "d7_roas": roas,
                "ctr": ctr,
                "spend": vector.spend,
                "sample_size": float(vector.sample_size),
            },
            thresholds={
                "underperform_roas_max": t["underperform_roas_max"],
                "underperform_ctr_max": t["underperform_ctr_max"],
                "underperform_spend_min": t["underperform_spend_min"],
            },
            explanation="; ".join(reasons) if reasons else "Underperforming creative",
            rule_name="creative_underperform_detector",
            source_vector_id=vector.creative_id,
        )