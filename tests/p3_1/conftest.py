"""P3.1 测试夹具 — 全部落在 tmp_path，绝不污染 data/。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
from src.growth_reality.feature_store import GrowthFeatureStore
from src.growth_reality.models import (
    AcquisitionFact,
    AsoFact,
    CreativeFact,
    GrowthRealitySnapshot,
    ProductFact,
    RevenueFact,
)
from src.growth_reality.snapshot import build_company_snapshot
from src.operator.context import build_operator_context
from src.operator.state import OperatorRunStore

AS_OF = "2026-07-30"


def _fleet(store: GrowthFeatureStore, n: int = 8):
    """确定性小舰队：轮转触发 收入跌 / ROAS跌 / 素材疲劳 / 商店CVR跌。"""
    gids = [f"t_game_{i:03d}" for i in range(n)]
    for i, gid in enumerate(gids):
        d0 = GrowthRealitySnapshot(
            gid, "d0",
            revenue=RevenueFact(daily_revenue=1000.0, payer_count=10),
            acquisition=AcquisitionFact(spend=100.0, installs=1000,
                                        cpi=0.1, roas=2.0),
            creative=CreativeFact(ctr=0.05, fatigue_score=0.30,
                                  creative_score=0.60),
            aso=AsoFact(ranking=10, store_cvr=0.10, rating=3.5,
                        review_velocity=4.0),
            product=ProductFact(dau=3000 + i, retention=0.3, conversion=0.02),
            confidence=0.6 + (i % 3) * 0.1,
            sources=["sim"],
        )
        rev1, roas1, spend1, ctr1, fat1, cvr1 = (
            1000.0, 2.0, 100.0, 0.05, 0.30, 0.10,
        )
        p = i % 4
        if p == 0:
            rev1 = 1000.0 * (1 - (0.20 + (i % 5) * 0.04))
        elif p == 1:
            roas1 = 2.0 * (1 - (0.15 + (i % 5) * 0.04))
            spend1 = 100.0 * (1 + (0.20 + (i % 5) * 0.04))
        elif p == 2:
            ctr1 = 0.05 * (1 - (0.20 + (i % 5) * 0.04))
            fat1 = min(0.95, 0.70 + (i % 5) * 0.05)
        else:
            cvr1 = 0.10 * (1 - (0.15 + (i % 5) * 0.04))
        d1 = GrowthRealitySnapshot(
            gid, "d1",
            revenue=RevenueFact(daily_revenue=rev1, payer_count=10),
            acquisition=AcquisitionFact(spend=spend1, installs=1000,
                                        cpi=0.1, roas=roas1),
            creative=CreativeFact(ctr=ctr1, fatigue_score=fat1,
                                  creative_score=0.60),
            aso=AsoFact(ranking=10, store_cvr=cvr1, rating=3.5,
                        review_velocity=4.0),
            product=ProductFact(dau=3000 + i, retention=0.3, conversion=0.02),
            confidence=0.6 + (i % 3) * 0.1,
            sources=["sim"],
        )
        store.append(d0)
        store.append(d1)
    return gids


@pytest.fixture
def fleet(tmp_path: Path):
    store = GrowthFeatureStore(root=str(tmp_path / "gr"))
    gids = _fleet(store)
    company = build_company_snapshot(
        [store.latest(g) for g in gids], AS_OF
    )
    return company, store, gids


@pytest.fixture
def ctx(tmp_path: Path, fleet):
    company, store, gids = fleet
    return build_operator_context(
        company=company,
        game_ids=gids,
        feature_store=store,
        data_dir=str(tmp_path / "data"),
        out_dir=str(tmp_path / "outputs" / "operator"),
        operator_memory=JsonlOperatorMemory(
            str(tmp_path / "operator_memory.jsonl")
        ),
        approval_queue_path=str(tmp_path / "approval_queue.jsonl"),
        audit_dir=str(tmp_path / "audit"),
        report_dir=str(tmp_path / "reports"),
    )


@pytest.fixture
def run_store(tmp_path: Path) -> OperatorRunStore:
    return OperatorRunStore(str(tmp_path / "runs.jsonl"))
