"""P3.3 测试夹具 — 全部落在 tmp_path，绝不污染 data/。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ceo_intelligence.daily_operator.memory import JsonlOperatorMemory
from src.ceo_intelligence.daily_operator.models import (
    ActionKind,
    DailyActionItem,
    DailyRunResult,
)
from src.ceo_intelligence.growth_memory_graph.patterns import GraphPattern
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
from src.operator.strategy.models import StrategyFeedback, StrategyState

AS_OF = "2026-07-31"


def _fleet(store: GrowthFeatureStore, n: int = 8):
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


@pytest.fixture
def tmp_store(tmp_path: Path) -> str:
    return str(tmp_path / "strategy_memory.jsonl")


@pytest.fixture
def adapter(tmp_store):
    from src.operator.strategy.memory import StrategyMemoryAdapter
    return StrategyMemoryAdapter(store_path=tmp_store)


@pytest.fixture
def daily_with_actions() -> DailyRunResult:
    actions = [
        DailyActionItem(kind=ActionKind.AUTO, game_id="g1",
                        action="DISABLE_NETWORK",
                        opportunity_type="network_cleanup",
                        decision_audit_id="a1"),
        DailyActionItem(kind=ActionKind.APPROVAL, game_id="g2",
                        action="PAUSE_CAMPAIGN",
                        opportunity_type="ua_scale",
                        decision_audit_id="a2"),
        DailyActionItem(kind=ActionKind.BLOCK, game_id="g3",
                        action="SCALE",
                        opportunity_type="aggressive_scale",
                        decision_audit_id="a3"),
    ]
    return DailyRunResult(date=AS_OF, actions=actions)


@pytest.fixture
def fake_patterns() -> list:
    """E17.7 提炼结果（network_cleanup 高成功，aggressive_scale 低成功）。"""
    return [
        GraphPattern("network_cleanup", "monetization", "disable_network",
                     87, 76, 0.87, 0.42, 0.13),
        GraphPattern("aggressive_scale", "ua", "scale",
                     30, 8, 0.26, -0.10, 0.04),
    ]


def make_feedback(strategy_id: str, outcome: str, reward: float = 1.0,
                 action_id: str = "a1") -> StrategyFeedback:
    return StrategyFeedback(
        action_id=action_id,
        strategy_id=strategy_id,
        reward=reward,
        outcome=outcome,
        evidence="unit-test",
    )
