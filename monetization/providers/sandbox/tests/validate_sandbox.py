"""
E14.3.4 — Provider Sandbox Validation
======================================

Proves the three sandbox modes are now a complete OPERATING STRATEGY:

  A. Contract preservation      — sandbox layer never breaks E14.3.1 shapes
  B. Shadow tracker             — prediction vs reality, accuracy, readiness
  C. Health scoring             — 0-100, bands, failure/latency penalties
  D. Rollback gate              — hold vs auto-rollback + alerts
  E. Canary controller          — staged rollout, stage gate, reverse rollback
  F. Promotion ladder           — sim -> shadow -> production, gated
  G. Automatic demotion         — gate fire / unhealthy -> back to simulation
  H. Multi-game isolation       — policies + scores never bleed across games
  I. Integration                — registry routing + MockAlertProvider wiring

Run:
    python monetization/providers/sandbox/tests/validate_sandbox.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..")))

from monetization.providers import (            # noqa: E402
    Change, ProviderRegistry, ProviderResult, ReferenceMockProvider, SandboxMode,
)
from monetization.providers.models import (     # noqa: E402
    CHANGE_BID_FLOOR, CHANGE_REWARD_FREQUENCY,
)
from monetization.providers.capability import (  # noqa: E402
    PROVIDER_MAX, PROVIDER_REMOTE_CONFIG,
)
from monetization.providers.sandbox import (    # noqa: E402
    CANARY_PASSED, CANARY_ROLLED_BACK, CanaryController,
    GATE_HOLD, GATE_ROLLBACK, HealthScorer, RollbackGate, SandboxManager,
    SHADOW_CLOSED, SHADOW_OPEN, ShadowTracker,
    STATUS_DEGRADED, STATUS_HEALTHY, STATUS_UNHEALTHY,
)
from monetization.runtime.alerting import (     # noqa: E402
    ALERT_CRITICAL, ALERT_INFO, ALERT_WARNING, MockAlertProvider,
)

PASS = 0
FAIL = 0
FAILED: list = []


def check(cond: bool, label: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  FAIL  {label}")


def mk_change(game: str, ctype: str = CHANGE_BID_FLOOR,
              old=12.0, new=14.4) -> Change:
    return Change(target="US_android_reward_applovin_floor",
                  change_type=ctype, old=old, new=new, game_id=game)


# =========================================================================== #
print("\n[A] Contract preservation")
# =========================================================================== #
mgr = SandboxManager(alert_provider=MockAlertProvider())
c = mk_change("game_A")
r = mgr.execute(c)
check(isinstance(r, ProviderResult), "A1 execute returns ProviderResult")
d = r.to_dict()
for k in ("provider", "operation", "success", "latency_ms", "real_api_called"):
    check(k in d, f"A2 mandatory key present: {k}")
check(r.real_api_called is False, "A3 simulation: real_api_called locked False")
check(r.success is True, "A4 simulated apply succeeds")

# =========================================================================== #
print("\n[B] Shadow tracker — prediction vs reality")
# =========================================================================== #
st = ShadowTracker()
prov = ReferenceMockProvider(SandboxMode.SHADOW)
prov.name = "max"
ch = mk_change("game_A")
res = prov.apply_change(ch)
check(res.shadow_read_only is True, "B1 shadow apply is read-only")
rec = st.record_proposal(ch, res, predicted_metric=10.0)
check(rec.status == SHADOW_OPEN, "B2 proposal recorded as open")
check(st.open_count("game_A", "max") == 1, "B3 open count = 1")
closed = st.ingest_reality(rec.record_id, actual_metric=9.0)
check(closed is not None and closed.status == SHADOW_CLOSED,
      "B4 reality ingestion closes record")
check(abs(closed.error_pct - (1.0 / 9.0 * 100)) < 0.01,
      "B5 error_pct computed correctly (|10-9|/9)")
check(st.ingest_reality(rec.record_id, 5.0) is None,
      "B6 double-close refused")
check(st.ingest_reality("nonexistent", 5.0) is None,
      "B7 unknown id returns None")
# close by change_id path
ch2 = mk_change("game_A")
rec2 = st.record_proposal(ch2, prov.apply_change(ch2), predicted_metric=8.0)
check(st.ingest_reality(ch2.change_id, 8.0) is not None,
      "B8 close by change_id works")
check(st.mean_error_pct("game_A", "max") is not None,
      "B9 mean error available")
check(st.ready("game_A", "max", min_closed=2, max_error_pct=15.0),
      "B10 ready() true with 2 closed + low error")
check(not st.ready("game_A", "max", min_closed=5, max_error_pct=15.0),
      "B11 ready() false when not enough closed records")

# =========================================================================== #
print("\n[C] Health scoring")
# =========================================================================== #
hs = HealthScorer()
ok = ProviderResult("max", "bid_floor", True, 50.0, False)
bad = ProviderResult("max", "bid_floor", False, 50.0, False)
for _ in range(10):
    hs.observe("game_A", ok)
snap = hs.score("game_A", "max")
check(snap.score >= 90 and snap.status == STATUS_HEALTHY,
      "C1 all-success window -> healthy")
for _ in range(5):
    hs.observe("game_A", bad)
snap = hs.score("game_A", "max")
check(snap.failure_rate > 0.3, "C2 failure rate reflects window")
check(snap.status in (STATUS_DEGRADED, STATUS_UNHEALTHY),
      "C3 heavy failures degrade status")
hs2 = HealthScorer()
slow = ProviderResult("max", "bid_floor", True, 900.0, False)
for _ in range(10):
    hs2.observe("game_A", slow)
check(hs2.score("game_A", "max").score < 100,
      "C4 high latency penalised")
hs3 = HealthScorer()
hfail = ProviderResult("max", "health_check", False, 10.0, False)
for _ in range(3):
    hs3.observe("game_A", hfail)
check(hs3.score("game_A", "max").health_fails == 3,
      "C5 failed health checks counted")
check(hs3.score("game_A", "max").score <= 100 - 45 + 1e-9 + 45,  # sanity
      "C6 health-fail penalty applied")
check(hs.score("game_B", "max").window == 0,
      "C7 game_B window isolated from game_A")

# =========================================================================== #
print("\n[D] Rollback gate")
# =========================================================================== #
alerts = MockAlertProvider()
gate = RollbackGate(alert_provider=alerts)
gprov = ReferenceMockProvider(SandboxMode.SIMULATION)
gprov.name = "max"
gc = mk_change("game_A")
gprov.apply_change(gc)
gate.arm(gc, gprov, metric_name="ecpm", baseline=12.0, max_drop_pct=15.0)
check(gate.active_count() == 1, "D1 change is guarded after arm")
dec = gate.observe(gc.change_id, 11.5)
check(dec is not None and dec.verdict == GATE_HOLD,
      "D2 small dip -> HOLD")
check(gprov.rolled_back_count() == 0, "D3 no rollback on hold")
dec = gate.observe(gc.change_id, 9.0)   # 25% drop
check(dec.verdict == GATE_ROLLBACK, "D4 25% drop -> ROLLBACK verdict")
check(gprov.rolled_back_count() == 1, "D5 provider.rollback_change fired")
check(gate.active_count() == 0, "D6 guard disarmed after rollback")
check(len(alerts.by_level(ALERT_CRITICAL)) == 1,
      "D7 CRITICAL alert emitted")
check(gate.observe(gc.change_id, 1.0) is None,
      "D8 disarmed change no longer observed")
# hard floor path
gc2 = mk_change("game_A")
gate.arm(gc2, gprov, metric_name="ecpm", baseline=12.0,
         max_drop_pct=90.0, hard_floor=5.0)
dec = gate.observe(gc2.change_id, 4.0)
check(dec.verdict == GATE_ROLLBACK, "D9 hard floor breach -> ROLLBACK")
check(gate.rollbacks_fired == 2, "D10 rollback counter accurate")

# =========================================================================== #
print("\n[E] Canary controller")
# =========================================================================== #
alerts_e = MockAlertProvider()
cn = CanaryController(alert_provider=alerts_e, max_drop_pct=10.0)
cprov = ReferenceMockProvider(SandboxMode.SIMULATION)
cprov.name = "max"
cc = mk_change("game_A")
run = cn.start(cc, cprov, baseline_metric=12.0)
check(len(run.stages) == 3 and [s.percent for s in run.stages] == [10, 50, 100],
      "E1 default stages 10/50/100")
run = cn.advance(run.run_id, observed_metric=12.1)
check(run.stages[0].status == CANARY_PASSED, "E2 stage 10% passes gate")
run = cn.advance(run.run_id, observed_metric=11.8)
check(run.stages[1].status == CANARY_PASSED, "E3 stage 50% passes gate")
run = cn.advance(run.run_id, observed_metric=12.4)
check(run.status == CANARY_PASSED, "E4 full rollout completes")
check(cprov.applied_count() == 3, "E5 three staged applies executed")
check(len(alerts_e.by_level(ALERT_INFO)) >= 1,
      "E6 rollout-complete info alert")
# failing canary: breach at stage 2 -> reverse rollback of applied stages
cprov2 = ReferenceMockProvider(SandboxMode.SIMULATION)
cprov2.name = "max"
cc2 = mk_change("game_A")
run2 = cn.start(cc2, cprov2, baseline_metric=12.0)
run2 = cn.advance(run2.run_id, observed_metric=12.0)   # 10% ok
run2 = cn.advance(run2.run_id, observed_metric=9.0)    # 50% breach (25% drop)
check(run2.status == CANARY_ROLLED_BACK, "E7 breach stops run + rolls back")
check(run2.rolled_back is True, "E8 run flagged rolled_back")
check(cprov2.rolled_back_count() == 2,
      "E9 BOTH applied stages reversed (reverse order)")
check(len(alerts_e.by_level(ALERT_CRITICAL)) == 1,
      "E10 canary failure CRITICAL alert")
check(run2.stages[2].status == "pending",
      "E11 stage 100% never attempted after failure")
# apply failure path
cprov3 = ReferenceMockProvider(SandboxMode.SIMULATION, fail_next=True)
cprov3.name = "max"
cc3 = mk_change("game_A")
run3 = cn.start(cc3, cprov3, baseline_metric=12.0)
run3 = cn.advance(run3.run_id, observed_metric=12.0)
check(run3.status in ("failed", CANARY_ROLLED_BACK) and
      run3.stages[0].result_success is False,
      "E12 stage apply failure stops the run")

# =========================================================================== #
print("\n[F] Promotion ladder (sim -> shadow -> production)")
# =========================================================================== #
alerts_f = MockAlertProvider()
m = SandboxManager(alert_provider=alerts_f)
G, K = "word_quest", PROVIDER_MAX
check(m.mode(G, K) == SandboxMode.SIMULATION, "F1 default mode simulation")
ok_, why = m.try_promote(G, K)
check(not ok_, "F2 promotion refused with zero history")
for _ in range(3):
    m.execute(mk_change(G))
ok_, why = m.try_promote(G, K)
check(ok_ and m.mode(G, K) == SandboxMode.SHADOW,
      "F3 3 clean sims -> promoted to shadow")
ok_, why = m.try_promote(G, K)
check(not ok_, "F4 shadow -> prod refused with no closed records")
# run shadow proposals + close them accurately
ids = []
for _ in range(3):
    sc = mk_change(G)
    m.execute(sc, predicted_metric=10.0)
    ids.append(sc.change_id)
check(m.shadow.open_count(G, K) == 3, "F5 3 open shadow records")
for cid in ids:
    m.ingest_reality(cid, actual_metric=9.5)   # ~5% error
check(m.shadow.closed_count(G, K) == 3, "F6 all shadows closed by reality")
ok_, why = m.try_promote(G, K)
check(ok_ and m.mode(G, K) == SandboxMode.PRODUCTION,
      "F7 accurate shadows + healthy -> promoted to production")
pol = m.policy(G, K)
check(pol.promotions == 2 and len(pol.history) >= 2,
      "F8 policy audit trail records promotions")
check(len(alerts_f.by_level(ALERT_INFO)) >= 2,
      "F9 promotion info alerts emitted")
ok_, why = m.try_promote(G, K)
check(not ok_ and "production" in why, "F10 cannot promote past production")
# inaccurate shadow blocks promotion
m2 = SandboxManager()
G2 = "merge_witch"
for _ in range(3):
    m2.execute(mk_change(G2))
m2.try_promote(G2, K)
for _ in range(3):
    sc = mk_change(G2)
    m2.execute(sc, predicted_metric=10.0)
    m2.ingest_reality(sc.change_id, actual_metric=5.0)   # 100% error
ok_, why = m2.try_promote(G2, K)
check(not ok_ and m2.mode(G2, K) == SandboxMode.SHADOW,
      "F11 inaccurate predictions BLOCK production promotion")

# =========================================================================== #
print("\n[G] Automatic demotion")
# =========================================================================== #
# G-a: rollback gate fire -> instant demotion to simulation
alerts_g = MockAlertProvider()
mg = SandboxManager(alert_provider=alerts_g)
G3 = "puzzle_pop"
for _ in range(3):
    mg.execute(mk_change(G3))
mg.try_promote(G3, K)
for _ in range(3):
    sc = mk_change(G3)
    mg.execute(sc, predicted_metric=10.0)
    mg.ingest_reality(sc.change_id, 9.8)
mg.try_promote(G3, K)
check(mg.mode(G3, K) == SandboxMode.PRODUCTION, "G1 pair reaches production")
pc = mk_change(G3)
mg.execute(pc, baseline_metric=12.0, metric_name="ecpm", max_drop_pct=15.0)
check(mg.gate.active_count() == 1, "G2 production execute arms the gate")
rep = mg.ingest_reality(pc.change_id, 8.0)   # 33% drop -> gate fires
check(rep.get("gate_verdict") == GATE_ROLLBACK, "G3 gate fires on collapse")
check(mg.mode(G3, K) == SandboxMode.SIMULATION,
      "G4 gate fire DEMOTES pair to simulation")
pol3 = mg.policy(G3, K)
check(pol3.demotions == 1 and pol3.sim_success_count == 0,
      "G5 demotion resets the ladder (must re-earn)")
check(len(alerts_g.by_level(ALERT_WARNING)) >= 1,
      "G6 demotion warning alert emitted")
check(len(alerts_g.by_level(ALERT_CRITICAL)) >= 1,
      "G7 rollback critical alert emitted")
# G-b: unhealthy score -> demotion
mh = SandboxManager()
G4 = "block_blast"
for _ in range(3):
    mh.execute(mk_change(G4))
mh.try_promote(G4, K)
check(mh.mode(G4, K) == SandboxMode.SHADOW, "G8 pair at shadow")
prov4 = mh.registry.instance(G4, K)
for _ in range(20):   # 20 consecutive failures -> score collapses
    prov4.set_fail_next(True)
    mh.execute(mk_change(G4))
check(mh.mode(G4, K) == SandboxMode.SIMULATION,
      "G9 unhealthy score auto-demotes to simulation")

# =========================================================================== #
print("\n[H] Multi-game isolation")
# =========================================================================== #
iso = SandboxManager()
A, B = "game_A", "game_B"
for _ in range(3):
    iso.execute(mk_change(A))
iso.try_promote(A, K)
check(iso.mode(A, K) == SandboxMode.SHADOW and
      iso.mode(B, K) == SandboxMode.SIMULATION,
      "H1 game_A promotion does not move game_B")
provA = iso.registry.instance(A, K)
provB = iso.registry.instance(B, K)
check(provA is not provB, "H2 provider instances isolated")
check(provA.credential_ref.game_id == A and
      provB.credential_ref.game_id == B,
      "H3 credential refs scoped per game")
sc = mk_change(A)
iso.execute(sc, predicted_metric=10.0)
check(iso.shadow.open_count(A, K) == 1 and iso.shadow.open_count(B, K) == 0,
      "H4 shadow records do not bleed across games")
snapA = iso.scorer.score(A, K)
snapB = iso.scorer.score(B, K)
check(snapA.window > 0 and snapB.window == 0,
      "H5 health windows isolated per game")
stA = iso.status(A)
check(stA["game_id"] == A and len(stA["policies"]) == 1,
      "H6 status report game-scoped")

# =========================================================================== #
print("\n[I] Integration — registry routing + policy override")
# =========================================================================== #
mi = SandboxManager()
fc = Change(target="ads.reward_frequency", change_type=CHANGE_REWARD_FREQUENCY,
            old=5, new=4, game_id="game_A")
r = mi.execute(fc)
check(fc.provider == PROVIDER_REMOTE_CONFIG,
      "I1 capability routing fills provider kind (RemoteConfig)")
check(r.provider == PROVIDER_REMOTE_CONFIG, "I2 result labelled by routed kind")
bc = mk_change("game_A")
r = mi.execute(bc)
check(bc.provider == PROVIDER_MAX, "I3 bid_floor routes to MAX")
# policy override: caller-set sandbox is ignored, policy wins
oc = mk_change("game_A")
oc.sandbox = SandboxMode.PRODUCTION      # caller tries to sneak production
r = mi.execute(oc)
check(oc.sandbox == SandboxMode.SIMULATION,
      "I4 policy OVERRIDES caller-supplied sandbox mode")
check(r.real_api_called is False, "I5 no real call under policy override")
# canary requires production policy
try:
    mi.execute_canary(mk_change("game_A"), baseline_metric=12.0)
    check(False, "I6 canary refused outside production policy")
except PermissionError:
    check(True, "I6 canary refused outside production policy")

# =========================================================================== #
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"E14.3.4 Provider Sandbox validation: {PASS}/{total} PASS")
if FAILED:
    print("FAILED checks:")
    for f in FAILED:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
