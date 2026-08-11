"""E11.6.4 Fitness Calibration — 收入驱动 Fitness 校准层。

将 Adjust 真实商业结果反馈到 Genome Fitness，
让进化系统按真实赚钱能力选择下一代。

模块：
  - fitness_calibration_schema: RevenueFitnessProfile, CalibratedFitness
  - fitness_weights:         权重配置 + 归一化工具
  - revenue_fitness_calculator: RevenueFitnessCalculator
  - fitness_calibrator:      FitnessCalibrator（合并 Evolution + Revenue）
"""

from .fitness_calibration_schema import (
    ROASProfile,
    RetentionProfile,
    RevenueFitnessProfile,
    CalibratedFitness,
)
from .fitness_weights import (
    FitnessWeights,
    normalize_ltv,
    normalize_roas,
    normalize_payer_rate,
    normalize_retention,
    normalize_creative_score,
    calc_confidence_factor,
    DEFAULT_REVENUE_FITNESS_WEIGHTS,
    DEFAULT_CALIBRATION_WEIGHTS,
    COLD_START_THRESHOLD,
)
from .revenue_fitness_calculator import RevenueFitnessCalculator
from .fitness_calibrator import FitnessCalibrator

__all__ = [
    "ROASProfile",
    "RetentionProfile",
    "RevenueFitnessProfile",
    "CalibratedFitness",
    "FitnessWeights",
    "normalize_ltv",
    "normalize_roas",
    "normalize_payer_rate",
    "normalize_retention",
    "normalize_creative_score",
    "calc_confidence_factor",
    "DEFAULT_REVENUE_FITNESS_WEIGHTS",
    "DEFAULT_CALIBRATION_WEIGHTS",
    "COLD_START_THRESHOLD",
    "RevenueFitnessCalculator",
    "FitnessCalibrator",
]