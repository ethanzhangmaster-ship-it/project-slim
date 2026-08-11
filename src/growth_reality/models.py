"""E17.1 Growth Reality Hub — 统一业务快照数据模型。

这是整个 AI 游戏公司的「统一事实层」契约。
每个部门（Revenue / UA / ASO / Creative / Product）各自 reality 的信号，
最终归一到 GrowthRealitySnapshot 的五个领域：
    revenue / acquisition / aso / creative / product

约定（与既有 Intelligence 模块一致）：
- 纯 dataclass + to_dict / from_dict，无 LLM、无 IO
- 确定性；SIM 模式下所有采集不得触发真实 API（real_api_called 锁由 collector 层负责）
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConfidenceLevel(str, Enum):
    """置信度分级（决策系统 E17.3 会消费）。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.75:
            return cls.HIGH
        if score >= 0.40:
            return cls.MEDIUM
        return cls.LOW


# --------------------------------------------------------------------------- #
# 五域 Fact
# --------------------------------------------------------------------------- #
@dataclass
class RevenueFact:
    daily_revenue: float = 0.0
    payer_count: int = 0
    arpdau: float = 0.0
    ltv: float = 0.0
    # —— MAX / IAA 原生变现指标（P1.2 起由 MaxRealitySource 填充，向后兼容默认 0/空）——
    impressions: int = 0
    requests: int = 0           # 广告请求数（报表 attempts 字段）
    ecpm: float = 0.0           # 混合 eCPM = revenue / impressions * 1000
    rewarded_video_revenue: float = 0.0
    network_distribution: Dict[str, float] = field(default_factory=dict)  # network -> 收入占比

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "RevenueFact":
        d = d or {}
        nd = d.get("network_distribution") or {}
        return cls(
            daily_revenue=float(d.get("daily_revenue", 0.0)),
            payer_count=int(d.get("payer_count", 0)),
            arpdau=float(d.get("arpdau", 0.0)),
            ltv=float(d.get("ltv", 0.0)),
            impressions=int(d.get("impressions", 0)),
            requests=int(d.get("requests", 0)),
            ecpm=float(d.get("ecpm", 0.0)),
            rewarded_video_revenue=float(d.get("rewarded_video_revenue", 0.0)),
            network_distribution=dict(nd) if isinstance(nd, dict) else {},
        )


@dataclass
class AcquisitionFact:
    spend: float = 0.0
    installs: int = 0
    cpi: float = 0.0
    roas: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "AcquisitionFact":
        d = d or {}
        return cls(
            spend=float(d.get("spend", 0.0)),
            installs=int(d.get("installs", 0)),
            cpi=float(d.get("cpi", 0.0)),
            roas=float(d.get("roas", 0.0)),
        )


@dataclass
class AsoFact:
    ranking: int = 0
    store_cvr: float = 0.0
    rating: float = 0.0
    review_velocity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "AsoFact":
        d = d or {}
        return cls(
            ranking=int(d.get("ranking", 0)),
            store_cvr=float(d.get("store_cvr", 0.0)),
            rating=float(d.get("rating", 0.0)),
            review_velocity=float(d.get("review_velocity", 0.0)),
        )


@dataclass
class CreativeFact:
    ctr: float = 0.0
    fatigue_score: float = 0.0
    creative_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "CreativeFact":
        d = d or {}
        return cls(
            ctr=float(d.get("ctr", 0.0)),
            fatigue_score=float(d.get("fatigue_score", 0.0)),
            creative_score=float(d.get("creative_score", 0.0)),
        )


@dataclass
class ProductFact:
    dau: int = 0
    retention: float = 0.0
    conversion: float = 0.0
    release_status: Optional[str] = None  # development / published / live

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "ProductFact":
        d = d or {}
        return cls(
            dau=int(d.get("dau", 0)),
            retention=float(d.get("retention", 0.0)),
            conversion=float(d.get("conversion", 0.0)),
            release_status=d.get("release_status"),
        )


@dataclass
class RealityAttribution:
    """P1.4 — 真实 ROAS 归因（仅在收入与花费均为真实源时计算）。

    有机 vs 付费分解是启发式估计（无 cohort 数据），方法透明可审计：
        roas            = 月化日收入 / 月花费
        paid_share_est  = clamp(月花费 / 月化日收入, 0, 1)
        organic_share_est = 1 - paid_share_est
    含义：把「花费能解释的收入占比」视作付费归因，其余视为有机。
    """

    roas: float = 0.0
    paid_share_est: float = 0.0
    organic_share_est: float = 0.0
    method: str = "heuristic_revenue_minus_spend"
    is_real: bool = False  # 收入与花费均来自真实源才 True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "RealityAttribution":
        d = d or {}
        return cls(
            roas=float(d.get("roas", 0.0)),
            paid_share_est=float(d.get("paid_share_est", 0.0)),
            organic_share_est=float(d.get("organic_share_est", 0.0)),
            method=str(d.get("method", "heuristic_revenue_minus_spend")),
            is_real=bool(d.get("is_real", False)),
        )


# --------------------------------------------------------------------------- #
# 统一快照
# --------------------------------------------------------------------------- #
@dataclass
class GrowthRealitySnapshot:
    """整个公司的统一业务快照（单游戏视角）。"""

    game_id: str
    timestamp: str

    revenue: Optional[RevenueFact] = None
    acquisition: Optional[AcquisitionFact] = None
    aso: Optional[AsoFact] = None
    creative: Optional[CreativeFact] = None
    product: Optional[ProductFact] = None

    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)

    # —— P1.4 真实覆盖感知 ——
    real_confidence: float = 0.0          # 仅统计真实源覆盖的域 / 5
    real_domains: List[str] = field(default_factory=list)  # 来自真实源的域名
    attribution: Optional[RealityAttribution] = None       # 真实 ROAS 归因

    # -- 序列化 --
    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "timestamp": self.timestamp,
            "revenue": self.revenue.to_dict() if self.revenue else None,
            "acquisition": self.acquisition.to_dict() if self.acquisition else None,
            "aso": self.aso.to_dict() if self.aso else None,
            "creative": self.creative.to_dict() if self.creative else None,
            "product": self.product.to_dict() if self.product else None,
            "confidence": self.confidence,
            "sources": list(self.sources),
            "real_confidence": self.real_confidence,
            "real_domains": list(self.real_domains),
            "attribution": self.attribution.to_dict() if self.attribution else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrowthRealitySnapshot":
        # 缺失的域必须保持 None（而不是空 Fact 的 0 值），
        # 否则会让「无收入数据」的游戏被误判为 revenue<=0 → at_risk。
        rev = d.get("revenue")
        acq = d.get("acquisition")
        aso = d.get("aso")
        cre = d.get("creative")
        pro = d.get("product")
        att = d.get("attribution")
        return cls(
            game_id=d["game_id"],
            timestamp=d["timestamp"],
            revenue=RevenueFact.from_dict(rev) if rev else None,
            acquisition=AcquisitionFact.from_dict(acq) if acq else None,
            aso=AsoFact.from_dict(aso) if aso else None,
            creative=CreativeFact.from_dict(cre) if cre else None,
            product=ProductFact.from_dict(pro) if pro else None,
            confidence=float(d.get("confidence", 0.0)),
            sources=list(d.get("sources", [])),
            real_confidence=float(d.get("real_confidence", 0.0)),
            real_domains=list(d.get("real_domains", [])),
            attribution=RealityAttribution.from_dict(att) if att else None,
        )

    # -- 派生属性 --
    @property
    def confidence_level(self) -> ConfidenceLevel:
        return ConfidenceLevel.from_score(self.confidence)

    def domain_coverage(self) -> int:
        return sum(
            1
            for f in (
                self.revenue,
                self.acquisition,
                self.aso,
                self.creative,
                self.product,
            )
            if f is not None
        )

    def covered_domains(self) -> List[str]:
        out = []
        if self.revenue:
            out.append("revenue")
        if self.acquisition:
            out.append("acquisition")
        if self.aso:
            out.append("aso")
        if self.creative:
            out.append("creative")
        if self.product:
            out.append("product")
        return out
