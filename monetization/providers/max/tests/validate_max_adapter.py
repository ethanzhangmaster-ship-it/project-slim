"""
E14.3.2 — AppLovin MAX Adapter Validation
==========================================

~46 checks proving the MAX adapter honours the E14.3.1 frozen contract and
delivers the three required capabilities (bid floor, waterfall, revenue read)
across the three sandbox modes, with multi-game credential isolation.

Run:  python monetization/providers/max/tests/validate_max_adapter.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

# make launchforge importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from monetization.providers import (
    CredentialRef, Change, MonetizationProvider, ProviderRegistry, SandboxMode,
)
from monetization.providers.max import (
    MaxProvider, MaxGameState, MaxMappingError, RevenueMetrics,
    map_change_to_operation, move_network, parse_target,
)


PASS = 0
FAIL = 0
_log: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        _log.append(f"  [PASS] {name}")
    else:
        FAIL += 1
        _log.append(f"  [FAIL] {name}  {detail}")


def mk(target, ctype, old=None, new=None, note="", game="game_A",
       sandbox=SandboxMode.SIMULATION, cred=None):
    return Change(target=target, change_type=ctype, old=old, new=new,
                  game_id=game, note=note, sandbox=sandbox,
                  credential_ref=cred)


# --------------------------------------------------------------------------- #
# 1) Contract completeness
# --------------------------------------------------------------------------- #
check("M1 MaxProvider is a MonetizationProvider",
      issubclass(MaxProvider, MonetizationProvider))
check("M2 apply_change returns ProviderResult",
      isinstance(MaxProvider().apply_change(mk("US_android_reward_applovin_floor",
            "bid_floor", 12.0, 14.4)), __import__("monetization.providers.models",
            fromlist=["ProviderResult"]).ProviderResult))
prov = MaxProvider()
r = prov.apply_change(mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4))
for k in ("provider", "operation", "success", "latency_ms", "real_api_called"):
    check(f"M3 ProviderResult has {k}", k in r.to_dict(), str(list(r.to_dict().keys())))
rb = prov.rollback_change(mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4))
h = prov.health_check()
check("M4 real_api_called present on apply/rollback/health",
      all(hasattr(x, "real_api_called") for x in (r, rb, h)))
check("M5 simulation real_api_called False (apply/rollback/health)",
      r.real_api_called is False and rb.real_api_called is False
      and h.real_api_called is False)

# --------------------------------------------------------------------------- #
# 2) Bid Floor
# --------------------------------------------------------------------------- #
prov = MaxProvider()
res = prov.apply_change(mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4))
check("M6 bid_floor +20% success", res.success is True)
check("M7 bid_floor before=12 after=14.4", res.before == 12.0 and res.after == 14.4)
check("M8 client floor updated to 14.4",
      prov._client.state.get_floor("US", "reward") == 14.4)
rb = prov.rollback_change(mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4))
check("M9 bid_floor rollback success", rb.success is True)
check("M10 after rollback client floor=12",
      prov._client.state.get_floor("US", "reward") == 12.0)
check("M11 rollback result before=14.4 after=12",
      rb.before == 14.4 and rb.after == 12.0)

# invalid geo
bad = prov.apply_change(mk("usa_android_reward_applovin_floor", "bid_floor", 12.0, 14.4))
check("M12 invalid geo rejected (success=False)", bad.success is False)
check("M13 invalid geo error mentions geo", "geo" in (bad.error or "").lower())

# missing old/new
miss = prov.apply_change(mk("US_android_reward_applovin_floor", "bid_floor", None, None))
check("M14 bid_floor missing old/new rejected", miss.success is False)

# unsupported change_type for MAX
uns = prov.apply_change(mk("US_android_reward_applovin_remote", "remote_param",
                           {"a": 1}, {"a": 2}))
check("M15 unsupported change_type rejected", uns.success is False)

# --------------------------------------------------------------------------- #
# 3) Waterfall
# --------------------------------------------------------------------------- #
old_order = ["applovin", "ironsource", "mintegral", "adtiming", "unityads"]
prov = MaxProvider()
wf_change = mk("US_android_reward_applovin_waterfall", "waterfall_priority",
              old_order, {"network": "mintegral", "priority_change": "+1"})
res = prov.apply_change(wf_change)
check("M16 waterfall reorder success", res.success is True)
check("M17 waterfall snapshot before==old after==new",
      res.before == old_order and res.after == ["applovin", "mintegral",
      "ironsource", "adtiming", "unityads"])
check("M18 client waterfall updated",
      prov._client.state.get_waterfall("reward") == res.after)
rb = prov.rollback_change(wf_change)
check("M19 waterfall rollback restores original",
      prov._client.state.get_waterfall("reward") == old_order)

# explicit new list
prov2 = MaxProvider()
explicit = mk("US_android_reward_applovin_waterfall", "waterfall_priority",
              old_order, ["mintegral", "applovin", "ironsource", "adtiming", "unityads"])
res2 = prov2.apply_change(explicit)
check("M20 waterfall explicit new list applied",
      res2.after == ["mintegral", "applovin", "ironsource", "adtiming", "unityads"])

# priority_change "-1" moves down
prov3 = MaxProvider()
down = mk("US_android_reward_applovin_waterfall", "waterfall_priority",
          old_order, {"network": "mintegral", "priority_change": "-1"})
res3 = prov3.apply_change(down)
check("M21 waterfall -1 moves mintegral down one",
      res3.after == ["applovin", "ironsource", "adtiming", "mintegral", "unityads"])

# invalid network spec
prov4 = MaxProvider()
badnet = mk("US_android_reward_applovin_waterfall", "waterfall_priority",
            old_order, {"network": "nonexistent", "priority_change": "+1"})
check("M22 waterfall invalid network rejected",
      prov4.apply_change(badnet).success is False)

# missing old order
prov5 = MaxProvider()
no_old = mk("US_android_reward_applovin_waterfall", "waterfall_priority",
            None, {"network": "mintegral", "priority_change": "+1"})
check("M23 waterfall missing old order rejected",
      prov5.apply_change(no_old).success is False)

# --------------------------------------------------------------------------- #
# 4) Mapper unit checks
# --------------------------------------------------------------------------- #
op = map_change_to_operation(
    mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4), "app_x")
check("M24 mapper bid_floor -> UPDATE_BID_FLOOR + multiplier 1.2",
      op.operation == "UPDATE_BID_FLOOR" and abs((op.multiplier or 0) - 1.2) < 1e-6)
c, p, a, n = parse_target("US_android_reward_applovin_floor")
check("M25 parse_target US/reward/applovin",
      c == "US" and a == "reward" and n == "applovin")
try:
    parse_target("usa_android_reward_applovin_floor")
    check("M26 invalid geo raises", False)
except MaxMappingError:
    check("M26 invalid geo raises", True)
check("M27 move_network up correct",
      move_network(["a", "b", "mintegral", "c"], "mintegral", 1)
      == ["a", "mintegral", "b", "c"])
opr = map_change_to_operation(
    mk("US_android_reward_applovin_floor", "revenue_read", note="2026-07-23"), "app_x")
check("M28 revenue_read -> READ_REVENUE", opr.operation == "READ_REVENUE")
try:
    map_change_to_operation(
        mk("US_android_reward_applovin_remote", "remote_param", {}, {}), "app_x")
    check("M29 unsupported change_type raises", False)
except MaxMappingError:
    check("M29 unsupported change_type raises", True)

# --------------------------------------------------------------------------- #
# 5) Revenue read
# --------------------------------------------------------------------------- #
state = MaxGameState(app_id="game_A")
state.set_revenue(RevenueMetrics(date="2026-07-23", geo="US", placement="reward",
                                 impressions=100000, revenue=1200.0, ecpm=12.0))
prov = MaxProvider(initial_state=state)
rm = prov.get_revenue_metrics("2026-07-23", "US", "reward")
check("M30 seeded revenue read returns numbers",
      rm.impressions == 100000 and rm.revenue == 1200.0 and rm.ecpm == 12.0)
res = prov.apply_change(mk("US_android_reward_applovin_floor", "revenue_read",
                           note="2026-07-23"))
check("M31 revenue read via apply returns metrics in extra",
      res.success is True and res.extra.get("revenue", {}).get("ecpm") == 12.0)
fact = prov._revenue.to_reality_fact("2026-07-23", "US", "reward")
check("M32 to_reality_fact shape",
      set(fact.keys()) == {"date", "geo", "placement", "impressions",
                           "revenue", "ecpm"})
# revenue read must not mutate floors
prov.apply_change(mk("US_android_reward_applovin_floor", "revenue_read",
                      note="2026-07-23"))
check("M33 revenue read does not mutate floors",
      prov._client.state.get_floor("US", "reward") is None)
# unknown cell -> zeroed
rz = prov.get_revenue_metrics("2099-01-01", "XX", "reward")
check("M34 unknown revenue cell zeroed",
      rz.impressions == 0 and rz.revenue == 0.0 and rz.ecpm == 0.0)

# --------------------------------------------------------------------------- #
# 6) Sandbox three modes
# --------------------------------------------------------------------------- #
prov = MaxProvider()  # simulation
for i in range(5):
    prov.apply_change(mk(f"US_android_reward_applovin_floor", "bid_floor",
                         12.0 + i, 14.0 + i))
check("M35 simulation: 0 real network calls",
      prov._client.real_network_calls == 0)

# shadow: no writes
shadow = MaxProvider(sandbox=SandboxMode.SHADOW)
shadow._client.state.set_floor("US", "reward", 12.0)
before_writes = shadow._client.write_calls
sres = shadow.apply_change(mk("US_android_reward_applovin_floor", "bid_floor",
                              12.0, 14.4))
check("M36 shadow: write_calls == 0", shadow._client.write_calls == before_writes)
check("M37 shadow: read-only flag + floor unchanged",
      sres.shadow_read_only is True
      and shadow._client.state.get_floor("US", "reward") == 12.0)

# shadow waterfall: no write
shadow2 = MaxProvider(sandbox=SandboxMode.SHADOW)
shadow2._client.state.set_waterfall("reward", old_order)
bw = shadow2._client.write_calls
shadow2.apply_change(mk("US_android_reward_applovin_waterfall",
                        "waterfall_priority", old_order,
                        {"network": "mintegral", "priority_change": "+1"}))
check("M38 shadow waterfall: write_calls == 0 + order unchanged",
      shadow2._client.write_calls == bw
      and shadow2._client.state.get_waterfall("reward") == old_order)

# production locked
locked = MaxProvider(sandbox=SandboxMode.PRODUCTION)
lres = locked.apply_change(mk("US_android_reward_applovin_floor", "bid_floor",
                              12.0, 14.4))
check("M39 production LOCKED: real_api_called False", lres.real_api_called is False)

# production unlocked
unlocked = MaxProvider(sandbox=SandboxMode.PRODUCTION)
unlocked._production_locked = False
before_real = unlocked._client.real_network_calls
ures = unlocked.apply_change(mk("US_android_reward_applovin_floor", "bid_floor",
                                12.0, 14.4))
check("M40 production UNLOCKED: real_api_called True",
      ures.real_api_called is True)
check("M41 production UNLOCKED: real_network_calls incremented",
      unlocked._client.real_network_calls == before_real + 1)

# --------------------------------------------------------------------------- #
# 7) Health (E14.2 Runtime)
# --------------------------------------------------------------------------- #
prov = MaxProvider()
h = prov.health_check()
check("M42 health healthy when cred+api ok", h.extra.get("status") == "healthy")
check("M43 health extra has credential_valid/api_available/status",
      all(k in h.extra for k in
          ("credential_valid", "api_available", "status")))
check("M44 health real_api_called False", h.real_api_called is False)

degraded = MaxProvider()
degraded._client.set_credential_valid(False)
dh = degraded.health_check()
check("M45 degraded when credential invalid",
      dh.extra.get("status") == "degraded" and dh.success is False)

# --------------------------------------------------------------------------- #
# 8) Multi-game credential isolation (E14.1 / E14.3.5)
# --------------------------------------------------------------------------- #
credA = CredentialRef(game_id="game_001", provider="MAX",
                      key_ref="credentials/game_001/max")
credB = CredentialRef(game_id="game_002", provider="MAX",
                      key_ref="credentials/game_002/max")
provA = MaxProvider(credential_ref=credA, app_id="game_001")
provB = MaxProvider(credential_ref=credB, app_id="game_002")
provA.apply_change(mk("US_android_reward_applovin_floor", "bid_floor",
                      12.0, 14.4, game="game_001", cred=credA))
check("M46 game_A apply does NOT affect game_B state",
      provB._client.state.get_floor("US", "reward") is None
      and provA._client.state.get_floor("US", "reward") == 14.4)
check("M47 credential key_ref isolated by game",
      credA.key_ref != credB.key_ref)

# registry integration (MaxProvider slots into the frozen registry)
reg = ProviderRegistry()
reg.register("MAX", lambda sb, cr, _p=MaxProvider: _p(sandbox=sb,
             credential_ref=cr, app_id=cr.game_id if cr else None))
mp = reg.instance("game_X", "MAX")
check("M48 registry returns MaxProvider for MAX",
      isinstance(mp, MaxProvider) and mp.name == "MAX")
mres = reg.provider_for("game_X",
        mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4,
           game="game_X")).apply_change(
        mk("US_android_reward_applovin_floor", "bid_floor", 12.0, 14.4, game="game_X"))
check("M49 registry-routed bid_floor executes via MaxProvider", mres.success is True)


# --------------------------------------------------------------------------- #
def main() -> int:
    print("\n".join(_log))
    print(f"\nE14.3.2 AppLovin MAX Adapter: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
