"""
E15.2.10 — Monetization Operation Acceptance Gate
===================================================
Validates the complete E15.2 Monetization Operation Agent.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monetization.providers.models import SandboxMode
from operation.monetization_ops.ads.agent import AdsAgent
from operation.monetization_ops.config.agent import ConfigAgent
from operation.monetization_ops.iap.provider import IAPOperationProvider
from operation.monetization_ops.max_ops.provider import MaxOperationProvider
from operation.monetization_ops.monitor.agent import MonitorAgent
from operation.monetization_ops.orchestrator.agent import MonetizationOrchestrator
from operation.monetization_ops.providers.models import (
    MonetizationOpChange, OP_CREATE, OP_UPDATE, OP_FETCH,
    AD_REWARDED, AD_INTERSTITIAL, AD_BANNER,
    IAP_CONSUMABLE, IAP_SUBSCRIPTION, IAP_NON_CONSUMABLE,
)
from operation.monetization_ops.revenue.agent import RevenueAgent, RevenueEvent

_passed = 0
_failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1; print(f"  [PASS] {name}" + (f" -- {detail}" if detail else ""))
    else:
        _failed += 1; print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    print("E15.2 Monetization Operation Agent -- Acceptance Gate\n")

    # ================================================================ #
    # 1. Provider Contract
    # ================================================================ #
    print("=== 1. Provider Contract ===")
    mx = MaxOperationProvider(sandbox=SandboxMode.SIMULATION)
    ip = IAPOperationProvider(sandbox=SandboxMode.SIMULATION)
    for p in [mx, ip]:
        hc = p.health_check()
        check(f"{p.name} health_check", hc.success)
        check(f"{p.name} real_api_called=False", not hc.real_api_called)

    # ================================================================ #
    # 2. Ads create ad units (3 formats × 2 platforms = 6)
    # ================================================================ #
    print("\n=== 2. Ads Create Ad Units ===")
    ads = AdsAgent()
    units = ads.create_all("game_00")
    check("created 6 ad units", len(units) == 6, f"got={len(units)}")
    formats = {(u.platform, u.format) for u in units}
    check("all platforms covered", len(formats) == 6)
    check("rewarded video exists", ("android", AD_REWARDED) in formats)
    check("interstitial exists", ("ios", AD_INTERSTITIAL) in formats)

    # ================================================================ #
    # 3. Ads validate SDK
    # ================================================================ #
    print("\n=== 3. Ads SDK Validation ===")
    full_report = ads.validate(units)
    check("full set validates OK", full_report.valid)
    partial = ads.create_all("game_partial")
    partial.pop(0)  # remove one → missing
    pr = ads.validate(partial)
    check("partial set flags missing", len(pr.missing) > 0, f"missing={pr.missing}")

    # ================================================================ #
    # 4. MAX app create + waterfall
    # ================================================================ #
    print("\n=== 4. MAX Operations ===")
    ch = MonetizationOpChange(
        target="test/max/create", operation=OP_CREATE,
        provider="max_ops", game_id="game_00",
        new={"package_name": "com.fake.game00"})
    r = mx.apply_change(ch)
    check("MAX create app", r.success, r.detail)
    check("MAX app_id returned", "app_id" in (r.data or {}))

    # waterfall
    ch2 = MonetizationOpChange(
        target="test/max/waterfall", operation=OP_UPDATE,
        provider="max_ops", game_id="game_00",
        new={"ad_unit_id": "max_game_00_reward",
             "networks": ["applovin", "meta"], "floor": 0.05})
    r2 = mx.apply_change(ch2)
    check("MAX waterfall configured", r2.success)

    # ================================================================ #
    # 5. MAX revenue read
    # ================================================================ #
    print("\n=== 5. MAX Revenue Read ===")
    rev = mx.client.read_revenue("game_00")
    check("MAX revenue > 0", rev["total_revenue"] > 0)
    check("MAX ecpm present", rev["ecpm"] > 0)
    check("MAX fill_rate present", rev["fill_rate"] > 0)

    # ================================================================ #
    # 6. IAP product create
    # ================================================================ #
    print("\n=== 6. IAP Product Create ===")
    for pid, ptype in [("coin100", IAP_CONSUMABLE),
                       ("vip_monthly", IAP_SUBSCRIPTION),
                       ("remove_ads", IAP_NON_CONSUMABLE)]:
        ch = MonetizationOpChange(
            target=f"game_00/iap/{pid}", operation=OP_CREATE,
            provider="iap_ops", game_id="game_00",
            new={"product_id": f"com.game00.{pid}",
                 "product_type": ptype, "price": 0.99,
                 "platform": "android", "title": pid})
        r = ip.apply_change(ch)
        check(f"IAP {pid} created", r.success)

    check("3 products in catalog", len(ip.client.list_products("game_00")) == 3)

    # ================================================================ #
    # 7. IAP price update
    # ================================================================ #
    print("\n=== 7. IAP Price Update ===")
    ch = MonetizationOpChange(
        target="game_00/iap/price", operation=OP_UPDATE,
        provider="iap_ops", game_id="game_00",
        new={"product_id": "com.game00.coin100", "price": 1.99})
    r = ip.apply_change(ch)
    check("price updated", r.success)
    check("new price applied", r.data.get("new_price") == 1.99)

    # ================================================================ #
    # 8. Revenue aggregation
    # ================================================================ #
    print("\n=== 8. Revenue Aggregation ===")
    rev_agent = RevenueAgent()
    events = [
        RevenueEvent("game_00", "2026-07-23", "max", 1200.0, extra={"impressions": 80000}),
        RevenueEvent("game_00", "2026-07-23", "app_store", 340.0, extra={"purchases": 50}),
    ]
    rep = rev_agent.aggregate("game_00", events)
    check("IAA revenue present", rep.iaa_revenue > 0)
    check("IAP revenue present", rep.iap_revenue > 0)
    check("total revenue = IAA + IAP", rep.total_revenue == rep.iaa_revenue + rep.iap_revenue)

    # ================================================================ #
    # 9. Config update
    # ================================================================ #
    print("\n=== 9. Config Update ===")
    cfg_agent = ConfigAgent()
    cfg = cfg_agent.build_default("game_00")
    check("default reward_cooldown = 30", cfg.reward_cooldown_min == 30)
    cfg = cfg_agent.update(cfg, "reward_cooldown_min", 45)
    check("updated reward_cooldown = 45", cfg.reward_cooldown_min == 45)
    cfg = cfg_agent.rollback(cfg)
    check("rolled back reward_cooldown = 30", cfg.reward_cooldown_min == 30)

    # ================================================================ #
    # 10. Health monitor
    # ================================================================ #
    print("\n=== 10. Health Monitor ===")
    mon = MonitorAgent()
    h = mon.check("game_00",
                  mx.client.read_revenue("game_00"),
                  ip.client.check_status("game_00", "com.game00.coin100"))
    check("health report generated", not h.healthy, f"flags={h.flags}")

    # force unhealthy
    h2 = mon.check("game_00", {"ecpm": 5.0, "fill_rate": 0.85}, {"exists": False})
    check("ecpm_below_10 flag", "ecpm_below_10" in h2.flags)
    check("fill_rate_below_90 flag", "fill_rate_below_90" in h2.flags)

    # ================================================================ #
    # 11. Orchestrator (setup_game)
    # ================================================================ #
    print("\n=== 11. Orchestrator ===")
    orch = MonetizationOrchestrator(mx, ip, ads, cfg_agent, rev_agent, mon)
    report = orch.setup_game("game_05", package_name="com.fake.game05")
    check("orchestrator setup complete", report.status == "setup_complete",
          f"status={report.status}")
    check("ad report valid", report.ad_report.get("valid", False))
    check("iap products created", len(report.iap_report.get("products", [])) == 3)
    check("tasks tracked", len(report.tasks) >= 5)

    # ================================================================ #
    # 12. Fleet Isolation
    # ================================================================ #
    print("\n=== 12. Fleet Isolation ===")
    cfg_a = cfg_agent.build_default("game_A")
    cfg_b = cfg_agent.build_default("game_B")
    check("config game_A != game_B (different objects)",
          id(cfg_a) != id(cfg_b))

    units_a = ads.create_all("game_A")
    units_b = ads.create_all("game_B")
    check("ad units game_A != game_B (different game_ids)",
          units_a[0].game_id != units_b[0].game_id)

    # ================================================================ #
    # 13. Zero real API calls
    # ================================================================ #
    print("\n=== 13. Zero Real API Calls ===")
    all_sim = mx.health_check().real_api_called is False
    all_sim &= ip.health_check().real_api_called is False
    ch = MonetizationOpChange(
        target="t/max/create", operation=OP_CREATE,
        provider="max_ops", game_id="t",
        new={"package_name": "com.t"})
    all_sim &= mx.apply_change(ch).real_api_called is False
    check("all SIMULATION operations real_api_called=False", all_sim)

    # ================================================================ #
    # Final
    # ================================================================ #
    print(f"\n{'='*50}")
    print(f"  E15.2 MONETIZATION ACCEPTANCE GATE")
    print(f"  Result: {'MONETIZATION READY' if _failed == 0 else 'ISSUES FOUND'}")
    print(f"  Passed: {_passed}  Failed: {_failed}")
    print(f"{'='*50}")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
