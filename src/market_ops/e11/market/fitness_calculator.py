"""E11.5.3 Fitness Calculator — IAP 适应度计算器。

将 MarketSignal 中的多维度信号权重加权为 GenomeFitness。

权重分配（IAP 产品导向）：
  - Monetization (40%): pay_rate + ARPU + ARPPU + d30_ltv
  - Retention (30%): d1 + d7 + d30 retention
  - Acquisition (20%): CTR + CVR + CPI
  - Confidence (10%): 数据可靠性

归一化策略：
  - 所有指标归一化到 0-1 区间
  - 参考区间基于 IAP 游戏行业基准

数据流：
  MarketSignal → FitnessCalculator.calculate() → GenomeFitness
"""

from __future__ import annotations

from typing import Any

from .feedback_schema import (
    UAMetrics,
    EngagementMetrics,
    IAPMetrics,
)
from .market_signal_schema import MarketSignal
from .fitness_schema import GenomeFitness


# ═══════════════════════════════════════════════════════════
# 归一化工具
# ═══════════════════════════════════════════════════════════

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(max_val, value))


def _linear_normalize(value: float, ref_low: float, ref_high: float) -> float:
    """线性归一化：value 在 [ref_low, ref_high] 区间映射到 [0, 1]。"""
    if ref_high <= ref_low:
        return 0.0
    return _clamp((value - ref_low) / (ref_high - ref_low))


def _inverse_normalize(value: float, ref_low: float, ref_high: float) -> float:
    """逆向归一化：值越低越好。"""
    return 1.0 - _linear_normalize(value, ref_low, ref_high)


# ═══════════════════════════════════════════════════════════
# 指标归一化函数
# ═══════════════════════════════════════════════════════════

def normalize_ltv(ltv: float) -> float:
    """归一化 LTV。

    参考区间：
      - $0  → 0.0
      - $3  → 0.5
      - $10 → 1.0
    """
    return _linear_normalize(ltv, 0.0, 10.0)


def normalize_pay_rate(pay_rate: float) -> float:
    """归一化付费率。

    参考区间：
      - 0%   → 0.0
      - 5%   → 0.5
      - 10%  → 1.0
    """
    return _linear_normalize(pay_rate, 0.0, 0.10)


def normalize_arpu(arpu: float) -> float:
    """归一化 ARPU。

    参考区间：
      - $0  → 0.0
      - $2  → 0.5
      - $5  → 1.0
    """
    return _linear_normalize(arpu, 0.0, 5.0)


def normalize_arppu(arppu: float) -> float:
    """归一化 ARPPU。

    参考区间：
      - $0   → 0.0
      - $50  → 0.5
      - $150 → 1.0
    """
    return _linear_normalize(arppu, 0.0, 150.0)


def normalize_retention(retention: float) -> float:
    """归一化留存率。

    参考区间：
      - 0%   → 0.0
      - 30%  → 0.5
      - 60%  → 1.0
    """
    return _linear_normalize(retention, 0.0, 0.60)


def normalize_cpi(cpi: float) -> float:
    """归一化 CPI（越低越好）。

    参考区间：
      - $0  → 1.0
      - $2  → 0.5
      - $5  → 0.0
    """
    return _inverse_normalize(cpi, 0.0, 5.0)


def normalize_ctr(ctr: float) -> float:
    """归一化 CTR。

    参考区间：
      - 0%   → 0.0
      - 5%   → 0.5
      - 10%  → 1.0
    """
    return _linear_normalize(ctr, 0.0, 0.10)


def normalize_install_cvr(cvr: float) -> float:
    """归一化 Install CVR。

    参考区间：
      - 0%   → 0.0
      - 30%  → 0.5
      - 60%  → 1.0
    """
    return _linear_normalize(cvr, 0.0, 0.60)


def normalize_confidence(sample_size: int, data_quality: float) -> float:
    """归一化置信度。

    基于样本量和数据完整性：
      - sample_weight = min(sample_size / 10000, 1.0)
      - confidence = sample_weight * 0.7 + data_quality * 0.3

    Args:
        sample_size: 安装量
        data_quality: 数据完整性 (0.0 ~ 1.0)

    Returns:
        0.0 ~ 1.0 的置信度评分
    """
    sample_weight = min(sample_size / 10000.0, 1.0)
    return round(sample_weight * 0.7 + data_quality * 0.3, 4)


# ═══════════════════════════════════════════════════════════
# FitnessCalculator — 适应度计算器
# ═══════════════════════════════════════════════════════════

class FitnessCalculator:
    """IAP 产品适应度计算器。

    将 MarketSignal 的多维度信号按权重加权为 GenomeFitness。

    Usage:
        calc = FitnessCalculator()
        fitness = calc.calculate(market_signal)
    """

    # 权重配置
    WEIGHTS = {
        "monetization": 0.40,
        "retention": 0.30,
        "acquisition": 0.20,
        "confidence": 0.10,
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        """初始化。

        Args:
            weights: 自定义权重（默认使用 WEIGHTS）
        """
        self._weights = weights or dict(self.WEIGHTS)

    @property
    def weights(self) -> dict[str, float]:
        return self._weights

    # ── 主入口 ────────────────────────────────────────

    def calculate(self, signal: MarketSignal) -> GenomeFitness:
        """计算 GenomeFitness。

        Args:
            signal: MarketSignal 实例

        Returns:
            GenomeFitness
        """
        # 1. 各维度评分
        monetization = self._calc_monetization(signal)
        retention = self._calc_retention(signal)
        acquisition = self._calc_acquisition(signal)
        ltv = self._calc_ltv(signal)
        confidence = self._calc_confidence(signal)

        # 2. 加权综合
        fitness_score = round(
            monetization * self._weights["monetization"]
            + retention * self._weights["retention"]
            + acquisition * self._weights["acquisition"]
            + confidence * self._weights["confidence"],
            4,
        )

        return GenomeFitness(
            genome_id=signal.genome_id,
            creative_id=signal.creative_id,
            signal_id=signal.signal_id,
            fitness_score=fitness_score,
            monetization_score=monetization,
            retention_score=retention,
            acquisition_score=acquisition,
            ltv_score=ltv,
            confidence=confidence,
            sample_size=signal.sample_size,
            weight_breakdown={
                "monetization": self._weights["monetization"],
                "retention": self._weights["retention"],
                "acquisition": self._weights["acquisition"],
                "confidence": self._weights["confidence"],
            },
        )

    # ── 维度计算 ──────────────────────────────────────

    def _calc_monetization(self, signal: MarketSignal) -> float:
        """计算商业化维度评分。

        综合 pay_rate + ARPU + ARPPU。
        """
        # 从 signals 中提取付费相关信号
        reward_score = signal.signals.get("reward", 0.0)
        return round(reward_score, 4)

    def _calc_retention(self, signal: MarketSignal) -> float:
        """计算留存维度评分。

        综合 emotion + gameplay 信号。
        """
        emotion_score = signal.signals.get("emotion", 0.0)
        gameplay_score = signal.signals.get("gameplay", 0.0)
        return round(emotion_score * 0.6 + gameplay_score * 0.4, 4)

    def _calc_acquisition(self, signal: MarketSignal) -> float:
        """计算获客维度评分。

        综合 hook + visual 信号。
        """
        hook_score = signal.signals.get("hook", 0.0)
        visual_score = signal.signals.get("visual", 0.0)
        return round(hook_score * 0.6 + visual_score * 0.4, 4)

    def _calc_ltv(self, signal: MarketSignal) -> float:
        """计算 LTV 维度评分。

        从 monetization 方向提取 LTV 信号。
        """
        return signal.signals.get("reward", 0.0)

    def _calc_confidence(self, signal: MarketSignal) -> float:
        """计算置信度评分。

        使用 signal 中已有的 confidence。
        """
        return signal.confidence

    # ── 批量计算 ──────────────────────────────────────

    def calculate_batch(
        self,
        signals: list[MarketSignal],
    ) -> list[GenomeFitness]:
        """批量计算适应度。

        Args:
            signals: MarketSignal 列表

        Returns:
            GenomeFitness 列表
        """
        return [self.calculate(s) for s in signals]

    def __repr__(self) -> str:
        return f"FitnessCalculator(weights={self._weights})"