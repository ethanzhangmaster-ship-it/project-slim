"""Shared fixtures for E16.1 tests (deterministic, no I/O)."""
from src.revenue_intelligence.models import RevenueSnapshot


def snap(
    game_id="game_x",
    date="P1",
    revenue_total=0.0,
    iap_revenue=0.0,
    ad_revenue=0.0,
    spend=0.0,
    roas=0.0,
    dau=0,
    payer_count=0,
    payer_conversion=0.0,
    arppu=0.0,
    retention_d1=0.0,
    retention_d7=0.0,
    retention_d30=0.0,
    version=None,
):
    return RevenueSnapshot(
        game_id=game_id,
        date=date,
        revenue_total=revenue_total,
        iap_revenue=iap_revenue,
        ad_revenue=ad_revenue,
        spend=spend,
        roas=roas,
        dau=dau,
        payer_count=payer_count,
        payer_conversion=payer_conversion,
        arppu=arppu,
        retention_d1=retention_d1,
        retention_d7=retention_d7,
        retention_d30=retention_d30,
        version=version,
    )


# --- Test1: revenue growth 10000 -> 12000, ROAS 1.2 -> 1.5
def growth_pair():
    prev = snap(
        date="P0", revenue_total=10000, iap_revenue=6000, ad_revenue=4000,
        spend=8333.33, roas=1.2, dau=10000, payer_count=500,
        payer_conversion=0.05, arppu=12.0, retention_d7=0.40,
    )
    cur = snap(
        date="P1", revenue_total=12000, iap_revenue=7200, ad_revenue=4800,
        spend=8000, roas=1.5, dau=11000, payer_count=600,
        payer_conversion=600 / 11000, arppu=12.0, retention_d7=0.40,
    )
    return prev, cur


# --- Test2: revenue decline 10000 -> 7000, retention down
def decline_pair():
    prev = snap(
        date="P0", revenue_total=10000, iap_revenue=6000, ad_revenue=4000,
        spend=2000, roas=5.0, dau=10000, payer_count=500,
        payer_conversion=0.05, arppu=12.0,
        retention_d1=0.50, retention_d7=0.40, retention_d30=0.20,
    )
    cur = snap(
        date="P1", revenue_total=7000, iap_revenue=4200, ad_revenue=2800,
        spend=2000, roas=3.5, dau=9000, payer_count=350,
        payer_conversion=350 / 9000, arppu=12.0,
        retention_d1=0.40, retention_d7=0.30, retention_d30=0.15,
    )
    return prev, cur


# --- Test3: UA contribution — Spend +50%, Revenue +80%
def ua_pair():
    prev = snap(
        date="P0", revenue_total=10000, iap_revenue=6000, ad_revenue=4000,
        spend=2000, roas=5.0, dau=10000, payer_count=500,
        payer_conversion=0.05, arppu=12.0, retention_d7=0.40,
    )
    cur = snap(
        date="P1", revenue_total=18000, iap_revenue=10800, ad_revenue=7200,
        spend=3000, roas=6.0, dau=15000, payer_count=900,
        payer_conversion=0.06, arppu=12.0, retention_d7=0.40,
    )
    return prev, cur


# --- Test5: high ROAS channel -> INCREASE_UA_BUDGET
def high_roas_pair():
    prev = snap(
        date="P0", revenue_total=15000, iap_revenue=9000, ad_revenue=6000,
        spend=5000, roas=3.0, dau=12000, payer_count=750,
        payer_conversion=750 / 12000, arppu=12.0, retention_d7=0.40,
    )
    cur = snap(
        date="P1", revenue_total=20000, iap_revenue=12000, ad_revenue=8000,
        spend=5000, roas=4.0, dau=14000, payer_count=1000,
        payer_conversion=1000 / 14000, arppu=12.0, retention_d7=0.40,
    )
    return prev, cur
