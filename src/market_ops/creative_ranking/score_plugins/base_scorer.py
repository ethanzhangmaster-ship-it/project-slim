"""Scorer Plugin 基类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreResult:
    """单个评分维度的结果"""
    score: float = 0.0           # 0-100
    breakdown: dict = field(default_factory=dict)  # 评分明细
    recommendations: list[str] = field(default_factory=list)  # 推荐理由
    risks: list[str] = field(default_factory=list)  # 风险分析
    raw_features: dict = field(default_factory=dict)  # 原始特征值


class BaseScorer(ABC):
    """评分器基类

    所有评分器必须实现:
    - name: 评分维度名称
    - score(variant_dna, base_dna, fb_meta) -> ScoreResult
    """

    name: str = ""
    weight_key: str = ""  # 在 config 中的权重键名

    @abstractmethod
    def score(
        self,
        variant_dna: dict,
        base_dna: dict,
        fb_meta: dict | None = None,
    ) -> ScoreResult:
        """对单个 Variant 评分

        Args:
            variant_dna: Variant 的 modified DNA
            base_dna: Winning Creative 的 DNA
            fb_meta: Facebook 元数据（可选）
        """
        ...

    def _safe_get(self, d: dict, path: list[str], default: Any = None) -> Any:
        """安全地沿路径取值"""
        current = d
        for key in path:
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is None:
                return default
        return current
