"""Prediction Calibration — 预测值校准"""
from typing import Dict, List


class PredictionCalibrator:
    """基于历史数据范围校准预测值，防止异常输出"""

    # P04 游戏的历史范围（从Adjust数据计算得出）
    DEFAULT_BOUNDS = {
        "expected_ctr": {"min": 0.005, "max": 0.08, "default": 0.02},
        "expected_cvr": {"min": 0.001, "max": 0.05, "default": 0.005},
        "purchase_rate": {"min": 0.0001, "max": 0.02, "default": 0.002},
        "expected_roas": {"min": 0.2, "max": 3.5, "default": 0.8},
    }

    def __init__(self, bounds: Dict = None):
        self.bounds = bounds or self.DEFAULT_BOUNDS

    def calibrate(self, predictions: Dict[str, float]) -> Dict[str, float]:
        """校准预测值到合理范围"""
        result = {}
        for key, value in predictions.items():
            if key in self.bounds:
                bound = self.bounds[key]
                # 限制在范围内
                calibrated = max(bound["min"], min(bound["max"], float(value)))
                # 如果原始值异常（超出范围2倍以上），用默认值
                if float(value) > bound["max"] * 2 or float(value) < bound["min"] * 0.5:
                    calibrated = bound["default"]
                result[key] = round(calibrated, 4)
            else:
                result[key] = value
        return result

    def update_bounds(self, historical_values: Dict[str, List[float]]):
        """根据历史数据更新范围"""
        for key, values in historical_values.items():
            if values:
                import numpy as np
                self.bounds[key] = {
                    "min": max(0, np.percentile(values, 5)),
                    "max": np.percentile(values, 95),
                    "default": np.median(values),
                }
