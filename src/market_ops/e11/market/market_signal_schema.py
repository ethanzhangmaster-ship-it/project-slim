"""E11.5.2 Market Signal Schema — 市场信号数据模型。

将 PerformanceFeedback 转换为可驱动 Genome 进化的学习信号。

  SignalType      — 信号类型 (ACQUISITION / ENGAGEMENT / MONETIZATION / CREATIVE)
  SignalStrength  — 信号强度 (VERY_STRONG / STRONG / MEDIUM / WEAK / NONE)
  MarketSignal    — 市场信号 (creative_id + signals + confidence)

数据流：
  PerformanceFeedback → MarketSignalProcessor → MarketSignal → E11.5.3 Fitness Engine
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# SignalType — 信号类型
# ═══════════════════════════════════════════════════════════

class SignalType(Enum):
    """市场信号类型。

    ACQUISITION  — 获取能力：CTR, CPI, Install CVR
    ENGAGEMENT   — 用户质量：D1, D7, D30 retention
    MONETIZATION — 商业价值：Pay Rate, ARPU, LTV
    CREATIVE     — 素材因素：Hook, Visual, Reward, Character
    """
    ACQUISITION = "acquisition"
    ENGAGEMENT = "engagement"
    MONETIZATION = "monetization"
    CREATIVE = "creative"


# ═══════════════════════════════════════════════════════════
# SignalStrength — 信号强度
# ═══════════════════════════════════════════════════════════

class SignalStrength(Enum):
    """信号强度等级。

    VERY_STRONG — 远超基准
    STRONG      — 超过基准
    MEDIUM      — 接近基准
    WEAK        — 低于基准
    NONE        — 无数据
    """
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    NONE = "none"

    @classmethod
    def from_score(cls, score: float) -> SignalStrength:
        """根据数值评分确定强度等级。

        Args:
            score: 0.0 ~ 1.0 的标准化评分

        Returns:
            SignalStrength
        """
        if score >= 0.85:
            return cls.VERY_STRONG
        elif score >= 0.70:
            return cls.STRONG
        elif score >= 0.40:
            return cls.MEDIUM
        elif score > 0.0:
            return cls.WEAK
        else:
            return cls.NONE


# ═══════════════════════════════════════════════════════════
# MarketSignal — 市场信号
# ═══════════════════════════════════════════════════════════

@dataclass
class MarketSignal:
    """代表一个 Creative DNA 在市场中的表现反馈。

    将 PerformanceFeedback 中的原始数据提炼为可驱动进化的信号。

    例如：
        MarketSignal(
            creative_id="creative_001",
            genome_id="genome_001",
            quality_score=0.85,
            signals={
                "hook": 0.92,
                "visual": 0.75,
                "reward": 0.88,
                "character": 0.81,
            },
            signal_composition={
                "acquisition": "strong",
                "engagement": "medium",
                "monetization": "very_strong",
            },
            confidence=0.95,
        )
    """
    signal_id: str = field(default_factory=lambda: f"sig_{uuid.uuid4().hex[:8]}")
    creative_id: str = ""
    genome_id: str = ""
    quality_score: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)
    signal_composition: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    sample_size: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 便捷属性 ──────────────────────────────────────

    @property
    def has_genome_id(self) -> bool:
        """是否关联 Genome。"""
        return bool(self.genome_id)

    @property
    def is_reliable(self) -> bool:
        """信号是否可靠（confidence >= 0.5）。"""
        return self.confidence >= 0.5

    @property
    def is_high_confidence(self) -> bool:
        """信号是否高置信（confidence >= 0.8）。"""
        return self.confidence >= 0.8

    @property
    def best_signal(self) -> tuple[str, float] | None:
        """最强的信号基因。"""
        if not self.signals:
            return None
        best_gene = max(self.signals, key=self.signals.get)
        return (best_gene, self.signals[best_gene])

    @property
    def weakest_signal(self) -> tuple[str, float] | None:
        """最弱的信号基因。"""
        if not self.signals:
            return None
        worst_gene = min(self.signals, key=self.signals.get)
        return (worst_gene, self.signals[worst_gene])

    def get_signal_strength(self, gene_name: str) -> SignalStrength:
        """获取指定基因的信号强度等级。

        Args:
            gene_name: 基因名称

        Returns:
            SignalStrength
        """
        score = self.signals.get(gene_name, 0.0)
        return SignalStrength.from_score(score)

    def get_signals_above(self, threshold: float) -> dict[str, float]:
        """获取超过阈值的信号。

        Args:
            threshold: 最低评分阈值

        Returns:
            {gene_name: score} 字典
        """
        return {k: v for k, v in self.signals.items() if v >= threshold}

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "creative_id": self.creative_id,
            "genome_id": self.genome_id,
            "quality_score": self.quality_score,
            "signals": self.signals,
            "signal_composition": self.signal_composition,
            "confidence": self.confidence,
            "sample_size": self.sample_size,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MarketSignal:
        created_at = data.get("created_at")
        return cls(
            signal_id=data.get("signal_id", ""),
            creative_id=data.get("creative_id", ""),
            genome_id=data.get("genome_id", ""),
            quality_score=data.get("quality_score", 0.0),
            signals=data.get("signals", {}),
            signal_composition=data.get("signal_composition", {}),
            confidence=data.get("confidence", 0.0),
            sample_size=data.get("sample_size", 0),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(timezone.utc),
        )

    def __repr__(self) -> str:
        return (
            f"MarketSignal(id={self.signal_id!r}, "
            f"creative={self.creative_id!r}, "
            f"quality={self.quality_score}, "
            f"confidence={self.confidence})"
        )