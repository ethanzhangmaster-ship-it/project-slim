from datetime import date

import pytest

from market_ops.product.evidence_adapter import assert_fresh, assert_performance_coverage_fresh


def test_freshness_gate_rejects_stale_decision_report():
    with pytest.raises(ValueError, match="stale"):
        assert_fresh({"report_date": "2026-06-24"}, as_of=date(2026, 7, 31), max_age_days=7)


def test_freshness_gate_accepts_current_decision_report():
    assert_fresh({"report_date": "2026-07-30"}, as_of=date(2026, 7, 31), max_age_days=7)


def test_performance_coverage_gate_rejects_old_data(tmp_path):
    source = tmp_path / "ads.csv"
    source.write_text("date,spend\n2026-07-22,100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="coverage is stale"):
        assert_performance_coverage_fresh(source, as_of=date(2026, 8, 3), max_age_days=2)
