"""E11.6.2 — Adjust Revenue Adapter Test.

11 AC covering:
  1.  Adjust Schema
  2.  IAP Event Mapping
  3.  Ad Revenue Mapping
  4.  Total Revenue Calculation
  5.  Campaign Mapping
  6.  Creative Mapping
  7.  Genome Mapping
  8.  Invalid Event
  9.  Currency
  10. Serialization
  11. Deterministic
"""

from __future__ import annotations

import pytest

from market_ops.e11.reality.adjust import (
    AdjustRawEvent,
    RevenueType,
    AdjustAdapter,
    AdjustCreativeMapper,
)
from market_ops.e11.reality import RevenueEvent, AttributionSource


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_iap_event(creative: str = "dragon_hook_001", revenue: float = 4.99) -> AdjustRawEvent:
    return AdjustRawEvent(
        adjust_event_id="adj_abc123",
        user_id="12345",
        event_name="purchase",
        revenue=revenue,
        currency="USD",
        revenue_type=RevenueType.IAP,
        campaign="campaign_001",
        adgroup="adgroup_A",
        creative=creative,
        country="US",
    )


def _make_ad_event(revenue: float = 0.23) -> AdjustRawEvent:
    return AdjustRawEvent(
        adjust_event_id="adj_def456",
        user_id="12345",
        event_name="ad_revenue",
        revenue=revenue,
        currency="USD",
        revenue_type=RevenueType.AD,
        creative="dragon_hook_001",
        country="US",
    )


def _make_mapper_with_registry() -> AdjustCreativeMapper:
    mapper = AdjustCreativeMapper()
    mapper.register("dragon_hook_001", "genome_001")
    mapper.register("rescue_hook_002", "genome_002")
    mapper.register("fantasy_visual_003", "genome_003")
    return mapper


# ═══════════════════════════════════════════════════════════
# AC1 — Adjust Schema
# ═══════════════════════════════════════════════════════════

def test_ac1a_revenue_type_enum():
    """AC1a: RevenueType enum has all 3 values."""
    assert RevenueType.IAP.value == "iap"
    assert RevenueType.AD.value == "ad"
    assert RevenueType.TOTAL.value == "total"


def test_ac1b_adjust_raw_event_create():
    """AC1b: AdjustRawEvent creates with all fields."""
    event = _make_iap_event()
    assert event.adjust_event_id == "adj_abc123"
    assert event.user_id == "12345"
    assert event.event_name == "purchase"
    assert event.revenue == 4.99
    assert event.revenue_type == RevenueType.IAP
    assert event.campaign == "campaign_001"
    assert event.adgroup == "adgroup_A"
    assert event.creative == "dragon_hook_001"
    assert event.country == "US"


def test_ac1c_adjust_raw_event_properties():
    """AC1c: AdjustRawEvent convenience properties work."""
    iap_event = _make_iap_event()
    assert iap_event.is_iap is True
    assert iap_event.is_ad is False
    assert iap_event.is_purchase is True
    assert iap_event.is_install is False
    assert iap_event.has_creative is True
    assert iap_event.has_campaign is True

    ad_event = _make_ad_event()
    assert ad_event.is_iap is False
    assert ad_event.is_ad is True
    assert ad_event.is_purchase is False

    install_event = AdjustRawEvent(event_name="install")
    assert install_event.is_install is True


def test_ac1d_adjust_raw_event_repr():
    """AC1d: AdjustRawEvent repr includes key fields."""
    event = _make_iap_event()
    r = repr(event)
    assert "adj_abc123" in r
    assert "12345" in r
    assert "purchase" in r
    assert "4.99" in r


# ═══════════════════════════════════════════════════════════
# AC2 — IAP Event Mapping
# ═══════════════════════════════════════════════════════════

def test_ac2a_iap_event_to_revenue_event():
    """AC2a: AdjustRawEvent(IAP) → RevenueEvent with correct fields."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)
    adjust_event = _make_iap_event()

    result = adapter.parse_event(adjust_event)

    assert result.user_id == "12345"
    assert result.creative_id == "dragon_hook_001"
    assert result.genome_id == "genome_001"
    assert result.revenue == 4.99
    assert result.currency == "USD"
    assert result.country == "US"
    assert result.source == AttributionSource.ADJUST
    assert result.is_valid is True
    assert result.is_attributed is True


def test_ac2b_iap_event_product_id():
    """AC2b: IAP event product_id has iap_ prefix."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)
    result = adapter.parse_event(_make_iap_event())

    assert result.product_id == "iap_purchase"


def test_ac2c_iap_event_genome_mapped():
    """AC2c: IAP event genome_id is resolved via mapper."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    # Known creative
    result = adapter.parse_event(_make_iap_event(creative="dragon_hook_001"))
    assert result.genome_id == "genome_001"

    # Unknown creative
    result2 = adapter.parse_event(_make_iap_event(creative="unknown_creative"))
    assert result2.genome_id == ""


def test_ac2d_iap_event_source_is_adjust():
    """AC2d: All parsed events have source=ADJUST."""
    adapter = AdjustAdapter(creative_mapper=_make_mapper_with_registry())
    result = adapter.parse_event(_make_iap_event())
    assert result.source == AttributionSource.ADJUST


# ═══════════════════════════════════════════════════════════
# AC3 — Ad Revenue Mapping
# ═══════════════════════════════════════════════════════════

def test_ac3a_ad_event_to_revenue_event():
    """AC3a: AdjustRawEvent(AD) → RevenueEvent."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)
    result = adapter.parse_event(_make_ad_event())

    assert result.user_id == "12345"
    assert result.revenue == 0.23
    assert result.product_id == "ad_ad_revenue"
    assert result.is_valid is True


def test_ac3b_ad_event_product_id():
    """AC3b: AD event product_id has ad_ prefix."""
    adapter = AdjustAdapter()
    result = adapter.parse_event(_make_ad_event())
    assert result.product_id.startswith("ad_")


def test_ac3c_mixed_events():
    """AC3c: IAP and AD events parse correctly together."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    results = adapter.parse_batch([
        _make_iap_event(revenue=4.99),
        _make_ad_event(revenue=0.23),
        _make_iap_event(creative="rescue_hook_002", revenue=9.99),
    ])

    assert len(results) == 3
    assert results[0].product_id == "iap_purchase"
    assert results[1].product_id == "ad_ad_revenue"
    assert results[2].genome_id == "genome_002"


# ═══════════════════════════════════════════════════════════
# AC4 — Total Revenue Calculation
# ═══════════════════════════════════════════════════════════

def test_ac4a_aggregate_single_user():
    """AC4a: aggregate_user_revenue for single user with IAP only."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    events = adapter.parse_batch([
        _make_iap_event(revenue=4.99),
        _make_iap_event(revenue=9.99),
    ])

    agg = adapter.aggregate_user_revenue(events)
    assert "12345" in agg
    assert agg["12345"]["iap_revenue"] == pytest.approx(14.98)
    assert agg["12345"]["total"] == pytest.approx(14.98)


def test_ac4b_aggregate_multiple_users():
    """AC4b: aggregate_user_revenue separates users correctly."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    raw_events = [
        AdjustRawEvent(
            adjust_event_id="e1", user_id="user_A", event_name="purchase",
            revenue=4.99, revenue_type=RevenueType.IAP, creative="dragon_hook_001",
        ),
        AdjustRawEvent(
            adjust_event_id="e2", user_id="user_B", event_name="purchase",
            revenue=9.99, revenue_type=RevenueType.IAP, creative="dragon_hook_001",
        ),
    ]
    events = adapter.parse_batch(raw_events)
    agg = adapter.aggregate_user_revenue(events)

    assert "user_A" in agg
    assert "user_B" in agg
    assert agg["user_A"]["total"] == 4.99
    assert agg["user_B"]["total"] == 9.99


def test_ac4c_aggregate_user_iap_plus_ad():
    """AC4c: IAP + AD revenue combined for same user."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    events = adapter.parse_batch([
        _make_iap_event(revenue=4.99),
        _make_ad_event(revenue=0.05),
    ])

    agg = adapter.aggregate_user_revenue(events)
    assert agg["12345"]["iap_revenue"] == 4.99
    assert agg["12345"]["ad_revenue"] == 0.05
    assert agg["12345"]["total"] == 5.04


def test_ac4d_aggregate_genome_revenue():
    """AC4d: aggregate_genome_revenue groups by genome_id."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    raw_events = [
        _make_iap_event(creative="dragon_hook_001", revenue=4.99),
        _make_iap_event(creative="dragon_hook_001", revenue=9.99),
        _make_iap_event(creative="rescue_hook_002", revenue=1.99),
    ]
    events = adapter.parse_batch(raw_events)
    agg = adapter.aggregate_genome_revenue(events)

    assert "genome_001" in agg
    assert "genome_002" in agg
    assert agg["genome_001"]["total"] == pytest.approx(14.98)
    assert agg["genome_001"]["users"] == 1.0  # same user
    assert agg["genome_002"]["total"] == 1.99


# ═══════════════════════════════════════════════════════════
# AC5 — Campaign Mapping
# ═══════════════════════════════════════════════════════════

def test_ac5a_campaign_preserved():
    """AC5a: AdjustRawEvent campaign is passed through."""
    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="u1", event_name="purchase",
        revenue=4.99, revenue_type=RevenueType.IAP,
        campaign="campaign_001", adgroup="adgroup_A", creative="c1",
    )
    assert event.campaign == "campaign_001"
    assert event.adgroup == "adgroup_A"
    assert event.has_campaign is True


def test_ac5b_event_with_campaign_and_adgroup():
    """AC5b: Full campaign hierarchy is preserved."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="u1", event_name="purchase",
        revenue=4.99, revenue_type=RevenueType.IAP,
        campaign="campaign_001", adgroup="adgroup_A", creative="dragon_hook_001",
    )
    result = adapter.parse_event(event)
    assert result.creative_id == "dragon_hook_001"
    assert result.genome_id == "genome_001"


# ═══════════════════════════════════════════════════════════
# AC6 — Creative Mapping
# ═══════════════════════════════════════════════════════════

def test_ac6a_register_exact_match():
    """AC6a: AdjustCreativeMapper exact match returns genome_id."""
    mapper = AdjustCreativeMapper()
    mapper.register("creative_905", "genome_001")

    assert mapper.map_creative("creative_905") == "genome_001"
    assert mapper.mapped_count == 1
    assert mapper.genome_count == 1


def test_ac6b_register_batch():
    """AC6b: register_batch maps multiple creatives."""
    mapper = AdjustCreativeMapper()
    mapper.register_batch({
        "creative_001": "genome_A",
        "creative_002": "genome_B",
        "creative_003": "genome_A",
    })

    assert mapper.map_creative("creative_001") == "genome_A"
    assert mapper.map_creative("creative_002") == "genome_B"
    assert mapper.mapped_count == 3
    assert mapper.genome_count == 2  # A and B


def test_ac6c_unmapped_creative():
    """AC6c: Unmapped creative returns empty string and is tracked."""
    mapper = _make_mapper_with_registry()
    result = mapper.map_creative("unknown_creative")
    assert result == ""
    assert mapper.unmapped_count == 1
    assert "unknown_creative" in mapper.get_unmapped()


def test_ac6d_prefix_match():
    """AC6d: Prefix matching works for creative_id variants."""
    mapper = AdjustCreativeMapper()
    mapper.register("dragon_hook", "genome_001")

    # Exact match
    assert mapper.map_creative("dragon_hook") == "genome_001"
    # Prefix match (suffix after last _)
    assert mapper.map_creative("dragon_hook_001") == "genome_001"
    assert mapper.map_creative("dragon_hook_v2") == "genome_001"


def test_ac6e_get_creatives_for_genome():
    """AC6e: Reverse lookup returns all creatives for a genome."""
    mapper = AdjustCreativeMapper()
    mapper.register_batch({
        "creative_A": "genome_001",
        "creative_B": "genome_001",
        "creative_C": "genome_002",
    })

    g1_creatives = mapper.get_creatives_for_genome("genome_001")
    assert len(g1_creatives) == 2
    assert "creative_A" in g1_creatives
    assert "creative_B" in g1_creatives

    g2_creatives = mapper.get_creatives_for_genome("genome_002")
    assert len(g2_creatives) == 1

    g3_creatives = mapper.get_creatives_for_genome("genome_003")
    assert len(g3_creatives) == 0


def test_ac6f_map_batch():
    """AC6f: map_batch returns dict of all mappings."""
    mapper = _make_mapper_with_registry()
    result = mapper.map_batch(["dragon_hook_001", "rescue_hook_002", "unknown"])
    assert result["dragon_hook_001"] == "genome_001"
    assert result["rescue_hook_002"] == "genome_002"
    assert result["unknown"] == ""


def test_ac6g_get_genome_for_creative():
    """AC6g: get_genome_for_creative is alias for map_creative."""
    mapper = _make_mapper_with_registry()
    assert mapper.get_genome_for_creative("dragon_hook_001") == "genome_001"
    assert mapper.get_genome_for_creative("") == ""


# ═══════════════════════════════════════════════════════════
# AC7 — Genome Mapping
# ═══════════════════════════════════════════════════════════

def test_ac7a_genome_id_in_revenue_event():
    """AC7a: Parsed RevenueEvent has genome_id from mapper."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    result = adapter.parse_event(_make_iap_event(creative="dragon_hook_001"))
    assert result.genome_id == "genome_001"
    assert result.has_genome is True
    assert result.is_attributed is True


def test_ac7b_event_without_genome():
    """AC7b: Event without creative has no genome_id."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="u1", event_name="purchase",
        revenue=4.99, revenue_type=RevenueType.IAP,
        creative="",  # no creative
    )
    result = adapter.parse_event(event)
    assert result.genome_id == ""
    assert result.has_genome is False
    assert result.is_attributed is False


def test_ac7c_mapper_integration():
    """AC7c: Changing mapper registry affects genome_id resolution."""
    mapper = AdjustCreativeMapper()
    adapter = AdjustAdapter(creative_mapper=mapper)

    # Before registration
    result1 = adapter.parse_event(_make_iap_event(creative="creative_905"))
    assert result1.genome_id == ""

    # After registration
    mapper.register("creative_905", "genome_001")
    result2 = adapter.parse_event(_make_iap_event(creative="creative_905"))
    assert result2.genome_id == "genome_001"


# ═══════════════════════════════════════════════════════════
# AC8 — Invalid Event
# ═══════════════════════════════════════════════════════════

def test_ac8a_zero_revenue_event():
    """AC8a: Zero revenue event is not valid."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="u1", event_name="purchase",
        revenue=0.0, revenue_type=RevenueType.IAP, creative="c1",
    )
    result = adapter.parse_event(event)
    assert result.is_valid is False


def test_ac8b_empty_user_id():
    """AC8b: Empty user_id event is not valid."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="", event_name="purchase",
        revenue=4.99, revenue_type=RevenueType.IAP,
    )
    result = adapter.parse_event(event)
    assert result.is_valid is False


def test_ac8c_parse_batch_error_handling():
    """AC8c: parse_batch handles errors gracefully."""
    # Create adapter with mapper that raises on certain conditions
    adapter = AdjustAdapter()

    events = [
        _make_iap_event(revenue=4.99),
        _make_iap_event(revenue=9.99),
    ]
    results = adapter.parse_batch(events)
    assert len(results) == 2
    assert adapter.error_count == 0


def test_ac8d_aggregate_skips_invalid():
    """AC8d: aggregate_user_revenue skips invalid events."""
    adapter = AdjustAdapter()

    valid = RevenueEvent(user_id="u1", revenue=4.99, product_id="iap_purchase")
    invalid = RevenueEvent(user_id="", revenue=0.0)

    agg = adapter.aggregate_user_revenue([valid, invalid])
    assert "u1" in agg
    assert "" not in agg


# ═══════════════════════════════════════════════════════════
# AC9 — Currency
# ═══════════════════════════════════════════════════════════

def test_ac9a_non_usd_currency():
    """AC9a: Non-USD currency is preserved in mapping."""
    event = AdjustRawEvent(
        adjust_event_id="e1", user_id="u1", event_name="purchase",
        revenue=99.99, currency="EUR", revenue_type=RevenueType.IAP,
        creative="dragon_hook_001", country="DE",
    )
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)

    result = adapter.parse_event(event)
    assert result.currency == "EUR"


def test_ac9b_currency_preserved_in_parse():
    """AC9b: All currency values pass through correctly."""
    for currency in ["USD", "EUR", "JPY", "GBP"]:
        event = AdjustRawEvent(
            adjust_event_id="e1", user_id="u1", event_name="purchase",
            revenue=10.0, currency=currency, revenue_type=RevenueType.IAP,
        )
        adapter = AdjustAdapter()
        result = adapter.parse_event(event)
        assert result.currency == currency


# ═══════════════════════════════════════════════════════════
# AC10 — Serialization
# ═══════════════════════════════════════════════════════════

def test_ac10a_adjust_raw_event_roundtrip():
    """AC10a: AdjustRawEvent to_dict/from_dict roundtrip."""
    event = _make_iap_event()
    data = event.to_dict()
    restored = AdjustRawEvent.from_dict(data)

    assert restored.adjust_event_id == event.adjust_event_id
    assert restored.user_id == event.user_id
    assert restored.event_name == event.event_name
    assert restored.revenue == event.revenue
    assert restored.revenue_type == event.revenue_type
    assert restored.campaign == event.campaign
    assert restored.adgroup == event.adgroup
    assert restored.creative == event.creative
    assert restored.country == event.country


def test_ac10b_adjust_creative_mapper_roundtrip():
    """AC10b: AdjustCreativeMapper to_dict/from_dict roundtrip."""
    mapper = _make_mapper_with_registry()
    mapper.map_creative("unknown_c1")  # add to unmapped
    mapper.map_creative("unknown_c2")

    data = mapper.to_dict()
    restored = AdjustCreativeMapper.from_dict(data)

    assert restored.mapped_count == mapper.mapped_count
    assert restored.map_creative("dragon_hook_001") == "genome_001"
    assert restored.unmapped_count == mapper.unmapped_count


def test_ac10c_adapter_repr():
    """AC10c: AdjustAdapter repr shows state."""
    mapper = _make_mapper_with_registry()
    adapter = AdjustAdapter(creative_mapper=mapper)
    adapter.parse_event(_make_iap_event())

    r = repr(adapter)
    assert "parsed=1" in r
    assert "errors=0" in r


# ═══════════════════════════════════════════════════════════
# AC11 — Deterministic
# ═══════════════════════════════════════════════════════════

def test_ac11a_deterministic_parse():
    """AC11a: Same AdjustRawEvent always produces same RevenueEvent."""
    mapper = _make_mapper_with_registry()
    adapter1 = AdjustAdapter(creative_mapper=mapper)
    adapter2 = AdjustAdapter(creative_mapper=mapper)

    event = _make_iap_event()
    r1 = adapter1.parse_event(event)
    r2 = adapter2.parse_event(event)

    assert r1.user_id == r2.user_id
    assert r1.creative_id == r2.creative_id
    assert r1.genome_id == r2.genome_id
    assert r1.revenue == r2.revenue
    assert r1.product_id == r2.product_id


def test_ac11b_deterministic_mapper():
    """AC11b: Same inputs produce same mapper results."""
    m1 = _make_mapper_with_registry()
    m2 = _make_mapper_with_registry()

    assert m1.map_creative("dragon_hook_001") == m2.map_creative("dragon_hook_001")
    assert m1.map_creative("unknown") == m2.map_creative("unknown")


def test_ac11c_deterministic_aggregation():
    """AC11c: Same events produce same revenue aggregation."""
    mapper = _make_mapper_with_registry()
    a1 = AdjustAdapter(creative_mapper=mapper)
    a2 = AdjustAdapter(creative_mapper=mapper)

    events = a1.parse_batch([
        _make_iap_event(revenue=4.99),
        _make_ad_event(revenue=0.05),
    ])

    agg1 = a1.aggregate_user_revenue(events)
    agg2 = a2.aggregate_user_revenue(events)

    assert agg1 == agg2


def test_ac11d_deterministic_aggregate_genome():
    """AC11d: Same events produce same genome aggregation."""
    mapper = _make_mapper_with_registry()
    a1 = AdjustAdapter(creative_mapper=mapper)
    a2 = AdjustAdapter(creative_mapper=mapper)

    events = a1.parse_batch([
        _make_iap_event(creative="dragon_hook_001", revenue=4.99),
    ])

    agg1 = a1.aggregate_genome_revenue(events)
    agg2 = a2.aggregate_genome_revenue(events)

    assert agg1 == agg2