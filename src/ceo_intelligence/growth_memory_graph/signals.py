"""
P3.5.1 — Knowledge Signal（经验信号，只读）。

把 Growth Knowledge Graph 的查询结果收敛成一个结构化、可被两个决策入口
（P3.4 Portfolio Ranker / P3.3 Strategy Loop）消费的信号。

纯 dataclass + to_dict / from_dict，无 LLM、无 IO、无写回。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class KnowledgeSignal:
    """经验信号（供决策入口做经验修正）。

    字段与 P3.5.1 契约一致：

    - ``confidence``            : 信号自身可信度（经验越多越可信，0..1）
    - ``historical_success_rate``: 相似历史经验的成功率（0..1）
    - ``similar_case_count``    : 命中的相似经验条数
    - ``risk_flags``            : 风险标记（空 = 无风险）
    - ``evidence``              : 人可读证据行
    """

    confidence: float = 0.0
    historical_success_rate: float = 0.0
    similar_case_count: int = 0
    risk_flags: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": round(float(self.confidence), 6),
            "historical_success_rate": round(float(self.historical_success_rate), 6),
            "similar_case_count": int(self.similar_case_count),
            "risk_flags": list(self.risk_flags),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeSignal":
        return cls(
            confidence=float(d.get("confidence", 0.0)),
            historical_success_rate=float(d.get("historical_success_rate", 0.0)),
            similar_case_count=int(d.get("similar_case_count", 0)),
            risk_flags=list(d.get("risk_flags", [])),
            evidence=list(d.get("evidence", [])),
        )

    def has_risk(self) -> bool:
        return bool(self.risk_flags)

    def is_empty(self) -> bool:
        return self.similar_case_count <= 0 and not self.risk_flags


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def experience_adjustment(signal: "KnowledgeSignal") -> Tuple[float, float]:
    """把信号转成 Ranker 可用的 (experience_score, risk_penalty)。

    用于 Rank 公式：``augmented = base + experience_score - risk_penalty``。

    - 无经验（similar_case_count<=0）一律中性（0, 0），**不惩罚无历史游戏**。
    - ``experience_score`` 为 signed：success_rate>0.5 为正、否则为负，归一 [-1, 1]。
    - ``risk_penalty`` 由 risk_flags 数量决定，封顶 0.5。
    """
    if signal.similar_case_count <= 0:
        return 0.0, 0.0
    sr = _clamp(signal.historical_success_rate, 0.0, 1.0)
    experience_score = _clamp((sr - 0.5) * 2.0, -1.0, 1.0)
    risk_penalty = min(0.5, 0.15 * len(signal.risk_flags))
    return experience_score, risk_penalty


def augmented_score(base_score: float, signal: "KnowledgeSignal") -> float:
    """经验修正后的分数（不封顶，调用方按需 clamp）。"""
    exp, pen = experience_adjustment(signal)
    return base_score + exp - pen


def knowledge_adjusted_confidence(
    base_confidence: float, signal: "KnowledgeSignal"
) -> float:
    """经验降权：历史失败模式显著时压低有效置信（封底 base*0.4）。"""
    if not signal.risk_flags:
        return float(base_confidence)
    factor = max(0.4, 1.0 - 0.18 * len(signal.risk_flags))
    return round(float(base_confidence) * factor, 6)


def knowledge_requires_approval(signal: "KnowledgeSignal") -> bool:
    """历史失败模式 → 强制走审批（不自动放行）。"""
    return bool(signal.risk_flags)


# 契约命名别名（PortfolioExperienceSignal 即 KnowledgeSignal）
PortfolioExperienceSignal = KnowledgeSignal


__all__ = [
    "KnowledgeSignal",
    "PortfolioExperienceSignal",
    "experience_adjustment",
    "augmented_score",
    "knowledge_adjusted_confidence",
    "knowledge_requires_approval",
]
