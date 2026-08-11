"""Adapter bridge tests: reality snapshot -> RevenueSnapshot, and the real
OperationRecord-backed PatternMemory (E13.4 seam)."""
import tempfile
from pathlib import Path

from src.revenue_intelligence.adapters import (
    OperationRecordPatternMemory,
    reality_snapshot_to_revenue_snapshot,
)
from src.revenue_intelligence.models import RevenueAction


def _fake_reality_snapshot():
    """Minimal stand-in for monetization.reality.production.normalizer.RealitySnapshot."""

    class Seg:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class RS:
        game_id = "game_x"
        generated_at = "2026-07-27T00:00:00+00:00"
        segments = [
            Seg(
                country="US", platform="ios", ad_format="reward",
                installs=100, sessions=300, dau=5000,
                spend=1000, iap_revenue=3000, ad_revenue=2000,
                arpdau=1.0, ecpm=12.0, fill_rate=0.9,
                d1=0.5, d7=0.4, d30=0.2, payer_conversion=0.05,
            ),
            Seg(
                country="US", platform="android", ad_format="reward",
                installs=150, sessions=400, dau=7000,
                spend=1500, iap_revenue=4200, ad_revenue=2800,
                arpdau=1.0, ecpm=11.0, fill_rate=0.88,
                d1=0.45, d7=0.35, d30=0.18, payer_conversion=0.04,
            ),
        ]

    return RS()


def test_reality_to_revenue_snapshot_aggregates():
    rs = _fake_reality_snapshot()
    rev = reality_snapshot_to_revenue_snapshot(rs, date="2026-W30")
    assert rev.game_id == "game_x"
    assert rev.revenue_total == 3000 + 4200 + 2000 + 2800
    assert rev.dau == 12000
    assert rev.spend == 2500
    # ROAS = revenue / spend
    assert abs(rev.roas - rev.revenue_total / rev.spend) < 1e-6
    # weighted retention (d7)
    expected_d7 = (0.4 * 5000 + 0.35 * 7000) / 12000
    assert abs(rev.retention_d7 - expected_d7) < 1e-3


def test_operation_record_pattern_memory_search():
    # Build a real OperationRecord and persist it, then search.
    try:
        from operation.memory.models import OperationRecord, record_factory
    except Exception:
        import pytest

        pytest.skip("operation.memory not importable in this env")

    path = Path(tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False).name)
    try:
        rec = record_factory(
            game_id="game_x",
            operation="raise_bid_floor",
            provider="max",
            sandbox="PRODUCTION",
            context={"country": "US"},
            before_state={"revenue_daily": 100.0},
            after_state={"revenue_daily": 130.0},
            result_metrics={"revenue_change_pct": 30.0},
            confidence=0.8,
            tags=["profitable", "low_risk"],
        )
        mem = OperationRecordPatternMemory(str(path))
        mem.add(rec)
        results = mem.search_similar(
            "game_x", {"operation": "raise_bid_floor"}, limit=3
        )
        assert results, "expected a historical pattern from OperationRecord"
        top = results[0]
        assert top.confidence == 0.8
        assert top.recommended_action == RevenueAction.INCREASE_UA_BUDGET
    finally:
        path.unlink(missing_ok=True)
