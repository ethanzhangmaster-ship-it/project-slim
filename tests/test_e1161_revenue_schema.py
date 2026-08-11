"""E11.6.1 — Revenue Data Schema Test.

8 AC covering:
  1.  RevenueEvent 创建
  2.  Revenue 序列化
  3.  UserValueProfile
  4.  RevenueSummary
  5.  Currency 支持
  6.  AttributionSource
  7.  Schema Roundtrip
  8.  Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.reality import (
    AttributionSource,
    PayerType,
    RevenueEvent,
    UserValueProfile,
    RevenueSummary,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_event(creative_id: str = "creative_023", genome_id: str = "genome_dragon_01") -> RevenueEvent:
    return RevenueEvent(
        user_id="u10001",
        creative_id=creative_id,
        genome_id=genome_id,
        product_id="remove_ads",
        revenue=4.99,
        currency="USD",
        country="US",
        source=AttributionSource.ADJUST,
    )


# ═══════════════════════════════════════════════════════════
# AC1 — RevenueEvent 创建
# ═══════════════════════════════════════════════════════════

def test_ac1a_create_basic():
    """AC1a: RevenueEvent creates with default values."""
    event = RevenueEvent()
    assert event.event_id.startswith("rev_")
    assert event.user_id == ""
    assert event.revenue == 0.0
    assert event.currency == "USD"
    assert event.source == AttributionSource.INTERNAL
    assert event.is_valid is False


def test_ac1b_create_with_all_fields():
    """AC1b: RevenueEvent creates with all fields populated."""
    event = _make_event()
    assert event.user_id == "u10001"
    assert event.creative_id == "creative_023"
    assert event.genome_id == "genome_dragon_01"
    assert event.product_id == "remove_ads"
    assert event.revenue == 4.99
    assert event.country == "US"
    assert event.source == AttributionSource.ADJUST


def test_ac1c_is_valid_true():
    """AC1c: is_valid returns True when revenue > 0 and user_id present."""
    event = RevenueEvent(user_id="u10001", revenue=4.99)
    assert event.is_valid is True


def test_ac1d_is_valid_false():
    """AC1d: is_valid returns False when revenue=0 or no user_id."""
    e1 = RevenueEvent(revenue=4.99)       # no user_id
    e2 = RevenueEvent(user_id="u10001")   # revenue=0
    e3 = RevenueEvent()                   # both missing
    assert e1.is_valid is False
    assert e2.is_valid is False
    assert e3.is_valid is False


def test_ac1e_has_genome():
    """AC1e: has_genome checks genome_id presence."""
    assert RevenueEvent(genome_id="g1").has_genome is True
    assert RevenueEvent().has_genome is False


def test_ac1f_has_creative():
    """AC1f: has_creative checks creative_id presence."""
    assert RevenueEvent(creative_id="c1").has_creative is True
    assert RevenueEvent().has_creative is False


def test_ac1g_is_attributed():
    """AC1g: is_attributed requires both genome_id and creative_id."""
    assert RevenueEvent(genome_id="g1", creative_id="c1").is_attributed is True
    assert RevenueEvent(genome_id="g1").is_attributed is False
    assert RevenueEvent(creative_id="c1").is_attributed is False
    assert RevenueEvent().is_attributed is False


# ═══════════════════════════════════════════════════════════
# AC2 — Revenue 序列化
# ═══════════════════════════════════════════════════════════

def test_ac2a_revenue_event_to_dict():
    """AC2a: RevenueEvent.to_dict returns all fields."""
    event = _make_event()
    data = event.to_dict()
    assert data["user_id"] == "u10001"
    assert data["creative_id"] == "creative_023"
    assert data["genome_id"] == "genome_dragon_01"
    assert data["revenue"] == 4.99
    assert data["currency"] == "USD"
    assert data["source"] == "adjust"


def test_ac2b_revenue_event_from_dict():
    """AC2b: RevenueEvent.from_dict restores all fields."""
    data = {
        "user_id": "u10001",
        "creative_id": "creative_023",
        "genome_id": "genome_dragon_01",
        "product_id": "remove_ads",
        "revenue": 4.99,
        "currency": "USD",
        "country": "US",
        "source": "adjust",
        "timestamp": "2026-07-15T10:30:00+00:00",
    }
    event = RevenueEvent.from_dict(data)
    assert event.user_id == "u10001"
    assert event.revenue == 4.99
    assert event.source == AttributionSource.ADJUST


def test_ac2c_revenue_event_repr():
    """AC2c: RevenueEvent repr includes key fields."""
    event = _make_event()
    r = repr(event)
    assert "u10001" in r
    assert "genome_dragon_01" in r
    assert "4.99" in r
    assert "adjust" in r


def test_ac2d_revenue_event_default_timestamp():
    """AC2d: RevenueEvent timestamp defaults to now."""
    from datetime import datetime, timezone, timedelta
    event = RevenueEvent()
    diff = datetime.now(timezone.utc) - event.timestamp
    assert diff < timedelta(seconds=5)


# ═══════════════════════════════════════════════════════════
# AC3 — UserValueProfile
# ═══════════════════════════════════════════════════════════

def test_ac3a_create_basic():
    """AC3a: UserValueProfile creates with default values."""
    profile = UserValueProfile()
    assert profile.user_id == ""
    assert profile.genome_id == ""
    assert profile.total_revenue == 0.0
    assert profile.payer_type == PayerType.FREE
    assert profile.is_payer is False


def test_ac3b_is_payer():
    """AC3b: is_payer returns True for all payer types except FREE."""
    assert UserValueProfile(payer_type=PayerType.WHALE).is_payer is True
    assert UserValueProfile(payer_type=PayerType.MID_PAYER).is_payer is True
    assert UserValueProfile(payer_type=PayerType.MINI_PAYER).is_payer is True
    assert UserValueProfile(payer_type=PayerType.FREE).is_payer is False


def test_ac3c_days_to_first_purchase():
    """AC3c: days_to_first_purchase computes correct difference."""
    p1 = UserValueProfile(
        install_date="2026-07-01",
        first_purchase_date="2026-07-03",
    )
    assert p1.days_to_first_purchase == 2

    p2 = UserValueProfile(
        install_date="2026-07-01",
        first_purchase_date="2026-07-01",
    )
    assert p2.days_to_first_purchase == 0

    p3 = UserValueProfile()
    assert p3.days_to_first_purchase is None


def test_ac3d_days_to_first_purchase_invalid():
    """AC3d: days_to_first_purchase returns None for invalid dates."""
    p = UserValueProfile(
        install_date="not-a-date",
        first_purchase_date="2026-07-03",
    )
    assert p.days_to_first_purchase is None


def test_ac3e_user_value_profile_repr():
    """AC3e: UserValueProfile repr includes key fields."""
    p = UserValueProfile(
        user_id="u10001",
        total_revenue=29.99,
        payer_type=PayerType.MID_PAYER,
    )
    r = repr(p)
    assert "u10001" in r
    assert "mid_payer" in r
    assert "29.99" in r


# ═══════════════════════════════════════════════════════════
# AC4 — RevenueSummary
# ═══════════════════════════════════════════════════════════

def test_ac4a_create_basic():
    """AC4a: RevenueSummary creates with default values."""
    s = RevenueSummary()
    assert s.genome_id == ""
    assert s.total_users == 0
    assert s.total_payers == 0
    assert s.total_revenue == 0.0
    assert s.payer_rate == 0.0
    assert s.arpu == 0.0
    assert s.arppu == 0.0


def test_ac4b_create_with_values():
    """AC4b: RevenueSummary with explicit values."""
    s = RevenueSummary(
        genome_id="genome_dragon_01",
        total_users=100000,
        total_payers=6000,
        total_revenue=50000.0,
        payer_rate=0.06,
        arpu=0.50,
        arppu=8.33,
        d7_revenue=10000.0,
        d30_revenue=50000.0,
        d90_revenue=80000.0,
    )
    assert s.genome_id == "genome_dragon_01"
    assert s.total_users == 100000
    assert s.total_payers == 6000
    assert s.total_revenue == 50000.0
    assert s.payer_rate == 0.06
    assert s.arpu == 0.50
    assert s.arppu == 8.33
    assert s.d7_revenue == 10000.0
    assert s.d30_revenue == 50000.0
    assert s.d90_revenue == 80000.0


def test_ac4c_is_significant():
    """AC4c: is_significant returns True when total_users >= 100."""
    assert RevenueSummary(total_users=100).is_significant is True
    assert RevenueSummary(total_users=1000).is_significant is True
    assert RevenueSummary(total_users=99).is_significant is False
    assert RevenueSummary(total_users=0).is_significant is False


def test_ac4d_revenue_summary_repr():
    """AC4d: RevenueSummary repr includes key fields."""
    s = RevenueSummary(
        genome_id="genome_dragon_01",
        total_users=100000,
        total_payers=6000,
        total_revenue=50000.0,
        payer_rate=0.06,
        arpu=0.50,
    )
    r = repr(s)
    assert "genome_dragon_01" in r
    assert "100000" in r
    assert "6000" in r


# ═══════════════════════════════════════════════════════════
# AC5 — Currency 支持
# ═══════════════════════════════════════════════════════════

def test_ac5a_different_currency():
    """AC5a: RevenueEvent supports non-USD currencies."""
    event = RevenueEvent(
        user_id="u10001",
        revenue=99.99,
        currency="EUR",
        country="DE",
    )
    assert event.currency == "EUR"


def test_ac5b_currency_in_serialization():
    """AC5b: Currency is preserved in roundtrip."""
    event = RevenueEvent(
        user_id="u10001",
        revenue=5800.0,
        currency="JPY",
        country="JP",
    )
    data = event.to_dict()
    restored = RevenueEvent.from_dict(data)
    assert restored.currency == "JPY"


# ═══════════════════════════════════════════════════════════
# AC6 — AttributionSource
# ═══════════════════════════════════════════════════════════

def test_ac6a_attribution_source_values():
    """AC6a: AttributionSource has all 6 values."""
    assert AttributionSource.ADJUST.value == "adjust"
    assert AttributionSource.APPSFLYER.value == "appsflyer"
    assert AttributionSource.FIREBASE.value == "firebase"
    assert AttributionSource.GOOGLE_PLAY.value == "google_play"
    assert AttributionSource.APP_STORE.value == "app_store"
    assert AttributionSource.INTERNAL.value == "internal"


def test_ac6b_attribution_source_from_string():
    """AC6b: AttributionSource can be constructed from string."""
    assert AttributionSource("adjust") == AttributionSource.ADJUST
    assert AttributionSource("appsflyer") == AttributionSource.APPSFLYER
    assert AttributionSource("internal") == AttributionSource.INTERNAL
    assert AttributionSource("google_play") == AttributionSource.GOOGLE_PLAY


def test_ac6c_payer_type_values():
    """AC6c: PayerType has all 4 values."""
    assert PayerType.WHALE.value == "whale"
    assert PayerType.MID_PAYER.value == "mid_payer"
    assert PayerType.MINI_PAYER.value == "mini_payer"
    assert PayerType.FREE.value == "free"


def test_ac6d_payer_type_from_revenue():
    """AC6d: PayerType.from_revenue classifies correctly."""
    assert PayerType.from_revenue(0.0) == PayerType.FREE
    assert PayerType.from_revenue(5.0) == PayerType.MINI_PAYER
    assert PayerType.from_revenue(10.0) == PayerType.MID_PAYER
    assert PayerType.from_revenue(50.0) == PayerType.MID_PAYER
    assert PayerType.from_revenue(99.99) == PayerType.MID_PAYER
    assert PayerType.from_revenue(100.0) == PayerType.WHALE
    assert PayerType.from_revenue(500.0) == PayerType.WHALE


# ═══════════════════════════════════════════════════════════
# AC7 — Schema Roundtrip
# ═══════════════════════════════════════════════════════════

def test_ac7a_revenue_event_roundtrip():
    """AC7a: RevenueEvent to_dict/from_dict roundtrip."""
    event = _make_event()
    data = event.to_dict()
    restored = RevenueEvent.from_dict(data)
    assert restored.user_id == event.user_id
    assert restored.creative_id == event.creative_id
    assert restored.genome_id == event.genome_id
    assert restored.product_id == event.product_id
    assert restored.revenue == event.revenue
    assert restored.currency == event.currency
    assert restored.country == event.country
    assert restored.source == event.source


def test_ac7b_user_value_profile_roundtrip():
    """AC7b: UserValueProfile to_dict/from_dict roundtrip."""
    profile = UserValueProfile(
        user_id="u10001",
        genome_id="genome_dragon_01",
        install_date="2026-07-01",
        first_purchase_date="2026-07-03",
        total_revenue=29.99,
        purchase_count=3,
        lifetime_days=30,
        payer_type=PayerType.MID_PAYER,
    )
    data = profile.to_dict()
    restored = UserValueProfile.from_dict(data)
    assert restored.user_id == profile.user_id
    assert restored.genome_id == profile.genome_id
    assert restored.install_date == profile.install_date
    assert restored.first_purchase_date == profile.first_purchase_date
    assert restored.total_revenue == profile.total_revenue
    assert restored.purchase_count == profile.purchase_count
    assert restored.lifetime_days == profile.lifetime_days
    assert restored.payer_type == profile.payer_type


def test_ac7c_revenue_summary_roundtrip():
    """AC7c: RevenueSummary to_dict/from_dict roundtrip."""
    summary = RevenueSummary(
        genome_id="genome_dragon_01",
        total_users=100000,
        total_payers=6000,
        total_revenue=50000.0,
        payer_rate=0.06,
        arpu=0.50,
        arppu=8.33,
        d7_revenue=10000.0,
        d30_revenue=50000.0,
        d90_revenue=80000.0,
    )
    data = summary.to_dict()
    restored = RevenueSummary.from_dict(data)
    assert restored.genome_id == summary.genome_id
    assert restored.total_users == summary.total_users
    assert restored.total_payers == summary.total_payers
    assert restored.total_revenue == summary.total_revenue
    assert restored.payer_rate == summary.payer_rate
    assert restored.arpu == summary.arpu
    assert restored.arppu == summary.arppu
    assert restored.d7_revenue == summary.d7_revenue
    assert restored.d30_revenue == summary.d30_revenue
    assert restored.d90_revenue == summary.d90_revenue


# ═══════════════════════════════════════════════════════════
# AC8 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac8a_deterministic_event():
    """AC8a: Same inputs produce same RevenueEvent fields (except event_id/timestamp)."""
    e1 = RevenueEvent(user_id="u10001", revenue=4.99, source=AttributionSource.ADJUST)
    e2 = RevenueEvent(user_id="u10001", revenue=4.99, source=AttributionSource.ADJUST)
    assert e1.user_id == e2.user_id
    assert e1.revenue == e2.revenue
    assert e1.source == e2.source
    assert e1.is_valid == e2.is_valid


def test_ac8b_deterministic_summary():
    """AC8b: Same inputs produce same RevenueSummary."""
    s1 = RevenueSummary(
        total_users=10000, total_payers=650, total_revenue=8500.0,
        payer_rate=0.065, arpu=0.85, arppu=13.08,
    )
    s2 = RevenueSummary(
        total_users=10000, total_payers=650, total_revenue=8500.0,
        payer_rate=0.065, arpu=0.85, arppu=13.08,
    )
    assert s1.payer_rate == s2.payer_rate
    assert s1.arpu == s2.arpu
    assert s1.arppu == s2.arppu
    assert s1.is_significant == s2.is_significant


def test_ac8c_deterministic_payer_type():
    """AC8c: PayerType.from_revenue is deterministic."""
    assert PayerType.from_revenue(50.0) == PayerType.from_revenue(50.0)
    assert PayerType.from_revenue(0.0) == PayerType.from_revenue(0.0)
    assert PayerType.from_revenue(500.0) == PayerType.from_revenue(500.0)


def test_ac8d_deterministic_profile():
    """AC8d: Same inputs produce same UserValueProfile computed properties."""
    kwargs = dict(
        user_id="u10001",
        total_revenue=30.0,
        purchase_count=3,
        lifetime_days=30,
        payer_type=PayerType.MID_PAYER,
        install_date="2026-07-01",
        first_purchase_date="2026-07-03",
    )
    p1 = UserValueProfile(**kwargs)
    p2 = UserValueProfile(**kwargs)
    assert p1.days_to_first_purchase == p2.days_to_first_purchase
    assert p1.is_payer == p2.is_payer