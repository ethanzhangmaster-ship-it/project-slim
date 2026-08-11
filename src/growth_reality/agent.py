"""E17.1 Growth Reality Hub — 数据大脑编排入口。

对外 API：
    hub = GrowthRealityHub(sources=[...])
    company = hub.refresh(game_ids, as_of)   # 采集→归一→持久化→聚合
    snap    = hub.query_game(game_id)         # 取最新快照
    md      = hub.to_markdown(company)        # CEO 视图

SIM 纪律：内置源均不触发真实 API；若将来接入 Adjust/MAX/Meta/Play 真实源，
该源应在 collect() 内把 collector.real_api_called 置 True，Hub 会透出。
"""
from __future__ import annotations

from typing import List, Optional

from .collector import RealityCollector, RealitySource
from .feature_store import GrowthFeatureStore
from .models import GrowthRealitySnapshot
from .normalizer import RealityNormalizer
from .snapshot import CompanySnapshot, build_company_snapshot


class GrowthRealityHub:
    def __init__(
        self,
        sources: List[RealitySource],
        store: Optional[GrowthFeatureStore] = None,
    ):
        self.collector = RealityCollector(sources)
        self.normalizer = RealityNormalizer()
        self.store = store or GrowthFeatureStore()

    def refresh(
        self, game_ids: List[str], as_of: str, persist: bool = True
    ) -> CompanySnapshot:
        raws = self.collector.collect_fleet(game_ids, as_of)
        snaps: List[GrowthRealitySnapshot] = [
            self.normalizer.normalize_game(g, as_of, raw) for g, raw in raws.items()
        ]
        if persist:
            for s in snaps:
                self.store.append(s)
        return build_company_snapshot(snaps, as_of)

    def query_game(self, game_id: str) -> Optional[GrowthRealitySnapshot]:
        return self.store.latest(game_id)

    def query_fleet(self) -> CompanySnapshot:
        latest = self.store.all_latest()
        # as_of 取最新快照的时间戳（若有）
        as_of = max((s.timestamp for s in latest.values()), default="")
        return build_company_snapshot(list(latest.values()), as_of)

    @property
    def last_real_api_called(self) -> bool:
        return self.collector.real_api_called

    def to_markdown(self, company: CompanySnapshot) -> str:
        return company.to_markdown()
