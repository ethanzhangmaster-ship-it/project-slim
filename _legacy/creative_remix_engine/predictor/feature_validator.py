"""Feature Validator — 特征质量检查与填充"""
import numpy as np
from typing import List, Dict, Tuple

from ..predictor.feature_schema import CreativeFeatureVector, MODEL_FEATURES


class FeatureValidator:
    """验证特征向量质量，自动填充缺失值"""

    def __init__(self):
        self.median_cache: Dict[str, float] = {}

    def validate(self, features: List[CreativeFeatureVector]) -> Tuple[List[CreativeFeatureVector], Dict]:
        """
        验证并修复特征
        返回: (修复后的features, 质量报告)
        """
        if not features:
            return [], {"feature_quality": 0, "missing": 0, "status": "no_data"}

        # 计算中位数（用于填充）
        self._compute_medians(features)

        fixed_count = 0
        missing_total = 0

        for f in features:
            missing = self._fix_feature(f)
            if missing > 0:
                fixed_count += 1
                missing_total += missing

        quality = max(0, 100 - (missing_total / max(len(features), 1)) * 10)

        report = {
            "feature_quality": round(quality, 1),
            "missing": missing_total,
            "fixed_samples": fixed_count,
            "total_samples": len(features),
            "status": "ok" if quality >= 80 else "warning" if quality >= 50 else "critical",
        }

        return features, report

    def _compute_medians(self, features: List[CreativeFeatureVector]):
        """计算每个特征的中位数"""
        for attr in MODEL_FEATURES:
            values = [getattr(f, attr, 0) for f in features if getattr(f, attr, 0) > 0]
            self.median_cache[attr] = np.median(values) if values else 0

    def _fix_feature(self, f: CreativeFeatureVector) -> int:
        """修复单个特征，返回缺失数"""
        missing = 0
        for attr in MODEL_FEATURES:
            val = getattr(f, attr, 0)
            if val == 0 or val is None or (isinstance(val, float) and np.isnan(val)):
                median = self.median_cache.get(attr, 0)
                setattr(f, attr, median)
                missing += 1
        return missing
