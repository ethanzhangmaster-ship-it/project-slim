"""P3.4.1 测试共用 fixture：构造最小 GrowthRealitySnapshot。"""

from src.growth_reality.models import (
    AcquisitionFact,
    GrowthRealitySnapshot,
    RevenueFact,
)


def make_reality(
    game_id: str,
    *,
    daily_revenue: float = None,
    spend: float = None,
    roas: float = None,
    confidence: float = 0.0,
    real_domains: list = None,
    sources: list = None,
    timestamp: str = "2026-07-30T00:00:00Z",
) -> GrowthRealitySnapshot:
    revenue = RevenueFact(daily_revenue=daily_revenue) if daily_revenue is not None else None
    acquisition = None
    if spend is not None or roas is not None:
        acquisition = AcquisitionFact(spend=spend or 0.0, roas=roas or 0.0)
    return GrowthRealitySnapshot(
        game_id=game_id,
        timestamp=timestamp,
        revenue=revenue,
        acquisition=acquisition,
        confidence=confidence,
        real_domains=real_domains or [],
        sources=sources or [],
    )
