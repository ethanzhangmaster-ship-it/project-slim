"""E11.6.4 Fitness Weights — 权重配置。

定义 Revenue Fitness 各项维度的权重分配。

公式：
  Revenue Fitness =
    0.35 × Revenue Score
    + 0.25 × ROAS Score
    + 0.20 × Retention Score
    + 0.10 × Payer Rate
    + 0.10 × Creative Quality

同时定义 CalibratedFitness 的合并权重：
  Final Fitness = 0.6 × Evolution Fitness + 0.4 × Revenue Fitness
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ═══════════════════════════════════════════════════════════
# 默认权重
# ═══════════════════════════════════════════════════════════

DEFAULT_REVENUE_FITNESS_WEIGHTS: dict[str, float] = {
    "revenue": 0.35,
    "roas": 0.25,
    "retention": 0.20,
    "payer_rate": 0.10,
    "creative_quality": 0.10,
}

DEFAULT_CALIBRATION_WEIGHTS: dict[str, float] = {
    "evolution": 0.60,
    "revenue": 0.40,
}

# 冷启动阈值
COLD_START_THRESHOLD: int = 100

# LTV 归一化基准
LTV_BENCHMARK: float = 5.0  # 行业基准 LTV $5

# ROAS 归一化基准
ROAS_BENCHMARK: float = 1.0  # ROAS=1.0 为盈亏平衡

# 留存率归一化基准
RETENTION_D1_BENCHMARK: float = 0.40  # 40% D1
RETENTION_D7_BENCHMARK: float = 0.15  # 15% D7
RETENTION_D30_BENCHMARK: float = 0.05  # 5% D30

# 付费率归一化基准
PAYER_RATE_BENCHMARK: float = 0.05  # 5%


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


def normalize_ltv(ltv: float) -> float:
    """归一化 LTV：以 LTV_BENCHMARK 为基准。

    $0  → 0.0
    $5  → 0.5
    $10 → 1.0
    """
    return _linear_normalize(ltv, 0.0, LTV_BENCHMARK * 2)


def normalize_roas(roas: float) -> float:
    """归一化 ROAS：以 ROAS_BENCHMARK=1.0 为基准。

    0.0  → 0.0
    1.0  → 0.5
    2.0  → 1.0
    """
    return _linear_normalize(roas, 0.0, ROAS_BENCHMARK * 2)


def normalize_payer_rate(payer_rate: float) -> float:
    """归一化付费率：以 PAYER_RATE_BENCHMARK=5% 为基准。

    0%   → 0.0
    5%   → 0.5
    10%  → 1.0
    """
    return _linear_normalize(payer_rate, 0.0, PAYER_RATE_BENCHMARK * 2)


def normalize_retention(retention: float, benchmark: float) -> float:
    """归一化留存率。

    0%      → 0.0
    benchmark → 0.5
    2×benchmark → 1.0
    """
    return _linear_normalize(retention, 0.0, benchmark * 2)


def normalize_creative_score(score: float) -> float:
    """归一化创意质量评分（0-100 → 0.0-1.0）。"""
    return _clamp(score / 100.0)


def calc_confidence_factor(sample_size: int) -> float:
    """计算冷启动置信度因子。

    使用 sigmoid 平滑过渡：
      sample 10   → ~0.2
      sample 100  → ~0.5
      sample 1000 → ~1.0

    Args:
        sample_size: 样本量（用户数）

    Returns:
        confidence_factor (0.0~1.0)
    """
    if sample_size <= 0:
        return 0.0
    import math
    return round(1.0 / (1.0 + math.exp(-0.005 * (sample_size - 200))), 4)


# ═══════════════════════════════════════════════════════════
# FitnessWeights — 可配置权重
# ═══════════════════════════════════════════════════════════

@dataclass
class FitnessWeights:
    """Revenue Fitness 权重配置。

    可自定义权重，未指定则使用默认值。

    Usage:
        weights = FitnessWeights()  # 使用默认权重
        weights = FitnessWeights(revenue=0.40, roas=0.20)  # 自定义
    """
    revenue: float = 0.35
    roas: float = 0.25
    retention: float = 0.20
    payer_rate: float = 0.10
    creative_quality: float = 0.10

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        """验证权重总和为 1.0。"""
        total = (self.revenue + self.roas + self.retention
                 + self.payer_rate + self.creative_quality)
        if abs(total - 1.0) > 0.001:
            # 自动归一化
            if total > 0:
                self.revenue = round(self.revenue / total, 4)
                self.roas = round(self.roas / total, 4)
                self.retention = round(self.retention / total, 4)
                self.payer_rate = round(self.payer_rate / total, 4)
                self.creative_quality = round(self.creative_quality / total, 4)

    def to_dict(self) -> dict[str, float]:
        return {
            "revenue": self.revenue,
            "roas": self.roas,
            "retention": self.retention,
            "payer_rate": self.payer_rate,
            "creative_quality": self.creative_quality,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitnessWeights:
        return cls(
            revenue=data.get("revenue", 0.35),
            roas=data.get("roas", 0.25),
            retention=data.get("retention", 0.20),
            payer_rate=data.get("payer_rate", 0.10),
            creative_quality=data.get("creative_quality", 0.10),
        )

    def __repr__(self) -> str:
        return (
            f"FitnessWeights(rev={self.revenue}, "
            f"roas={self.roas}, "
            f"ret={self.retention}, "
            f"payer={self.payer_rate}, "
            f"creative={self.creative_quality})"
        )