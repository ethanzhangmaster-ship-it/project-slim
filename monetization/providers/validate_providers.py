"""
E14.3.1 — Provider Contract Freeze Validation
==============================================

24 checks proving the frozen contract holds before any real adapter lands:

  * Interface completeness (ABC + 3 methods)
  * ProviderResult shape (5 mandatory keys)
  * Simulation: real_api_called always False
  * SHADOW: read-only, no write, no real call
  * PRODUCTION lock: a real call is refused unless armed + production
  * Capability routing: bid_floor->MAX, reward_frequency->RemoteConfig, ...
  * Multi-game credential + state isolation (E14.1 / E14.3.5)
  * Rollback reverses old/new
  * Legacy Change bridge (decoupling-safe)
  * Registry health_all

Run:  python monetization/providers/validate_providers.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

# make the launchforge package importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from monetization.providers import (
    PROVIDER_MAX, PROVIDER_REMOTE_CONFIG, Change, CredentialRef,
    MonetizationProvider, ProviderRegistry, ProviderResult, ReferenceMockProvider,
    SandboxMode, capabilities_for, provider_kind_for_change_type,
)
from monetization.providers.models import CHANGE_BID_FLOOR, CHANGE_REWARD_FREQUENCY


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


# --------------------------------------------------------------------------- #
# 1) Interface completeness
# --------------------------------------------------------------------------- #
abstract_methods = MonetizationProvider.__abstractmethods__
check("C1 MonetizationProvider is ABC",
      inspect.isabstract(MonetizationProvider), str(abstract_methods))
for m in ("apply_change", "rollback_change", "health_check"):
    check(f"C2 abstract method present: {m}",
          m in abstract_methods, f"have={abstract_methods}")

check("C3 ReferenceMockProvider instantiable",
      isinstance(ReferenceMockProvider(), MonetizationProvider))

# --------------------------------------------------------------------------- #
# 2) ProviderResult shape
# --------------------------------------------------------------------------- #
r = ProviderResult(provider="max", operation="bid_floor", success=True,
                   latency_ms=120.0, real_api_called=False)
rd = r.to_dict()
for k in ("provider", "operation", "success", "latency_ms", "real_api_called"):
    check(f"C4 ProviderResult has {k}", k in rd, f"keys={list(rd.keys())}")
check("C5 ProviderResult round-trip", ProviderResult.from_dict(rd).to_dict() == rd)

# --------------------------------------------------------------------------- #
# 3) Simulation: real_api_called always False
# --------------------------------------------------------------------------- #
prov = ReferenceMockProvider()
ch = Change(target="US_android_reward_applovin_floor", change_type=CHANGE_BID_FLOOR,
            old=12.0, new=14.4, game_id="game_A")
res = prov.apply_change(ch)
check("C6 simulation apply success", res.success is True)
check("C7 simulation real_api_called False", res.real_api_called is False)
check("C8 simulation latency recorded", res.latency_ms >= 0.0)
check("C9 simulation before/after present",
      res.before == 12.0 and res.after == 14.4)

# failing apply still never claims a real call
prov2 = ReferenceMockProvider()
prov2.set_fail_next(True)
bad = prov2.apply_change(ch)
check("C10 failed apply success=False", bad.success is False)
check("C11 failed apply real_api_called False", bad.real_api_called is False)

# --------------------------------------------------------------------------- #
# 4) SHADOW: read-only, no write, no real call
# --------------------------------------------------------------------------- #
shadow = ReferenceMockProvider(sandbox=SandboxMode.SHADOW)
before = shadow.applied_count()
sres = shadow.apply_change(ch)
check("C12 shadow success", sres.success is True)
check("C13 shadow read-only flag", sres.shadow_read_only is True)
check("C14 shadow no real call", sres.real_api_called is False)
check("C15 shadow does not write (applied unchanged)",
      shadow.applied_count() == before)
check("C16 shadow before == after (no mutation)",
      sres.before == sres.after == 12.0)

# --------------------------------------------------------------------------- #
# 5) PRODUCTION lock
# --------------------------------------------------------------------------- #
class RealishProvider(ReferenceMockProvider):
    """A provider that *tries* to perform a real call."""
    def apply_change(self, change):
        # pretend it has a client and wants to write for real
        return self._result(change.change_type, True, real_api_called=True,
                            before=change.old, after=change.new)

# default: locked -> refused
locked = RealishProvider(sandbox=SandboxMode.PRODUCTION)
raised = False
try:
    locked.apply_change(ch)
except RuntimeError as e:
    raised = True
check("C17 production lock refuses real call when locked", raised)

# arming the lock still refuses in NON-production sandbox
armed = RealishProvider(sandbox=SandboxMode.SIMULATION)
armed._production_locked = False
raised2 = False
try:
    armed.apply_change(ch)
except RuntimeError:
    raised2 = True
check("C18 real call refused outside PRODUCTION sandbox even if armed", raised2)

# --------------------------------------------------------------------------- #
# 6) Capability routing
# --------------------------------------------------------------------------- #
check("C19 bid_floor -> MAX",
      provider_kind_for_change_type(CHANGE_BID_FLOOR) == PROVIDER_MAX)
check("C20 reward_frequency -> RemoteConfig",
      provider_kind_for_change_type(CHANGE_REWARD_FREQUENCY) == PROVIDER_REMOTE_CONFIG)
check("C21 backup_network -> LevelPlay",
      provider_kind_for_change_type("backup_network") == "LevelPlay")
check("C22 revenue_read -> MAX",
      provider_kind_for_change_type("revenue_read") == PROVIDER_MAX)
check("C23 ad_frequency -> RemoteConfig",
      provider_kind_for_change_type("ad_frequency") == PROVIDER_REMOTE_CONFIG)
# capability admission control
check("C24 MAX supports bid_floor", capabilities_for(PROVIDER_MAX).supports(CHANGE_BID_FLOOR))
check("C25 MAX does NOT support reward_frequency",
      not capabilities_for(PROVIDER_MAX).supports(CHANGE_REWARD_FREQUENCY))
check("C26 RemoteConfig supports reward_frequency",
      capabilities_for(PROVIDER_REMOTE_CONFIG).supports(CHANGE_REWARD_FREQUENCY))
raised3 = False
try:
    provider_kind_for_change_type("nonexistent_type")
except ValueError:
    raised3 = True
check("C27 unknown change_type raises", raised3)

# --------------------------------------------------------------------------- #
# 7) Multi-game credential + state isolation
# --------------------------------------------------------------------------- #
reg = ProviderRegistry()
maxA = reg.instance("game_A", PROVIDER_MAX)
maxB = reg.instance("game_B", PROVIDER_MAX)
check("C28 distinct MAX instances per game", maxA is not maxB)
check("C29 game_A credential game_id", maxA.credential_ref.game_id == "game_A")
check("C30 game_B credential game_id", maxB.credential_ref.game_id == "game_B")
check("C31 credential key_ref isolated by game",
      maxA.credential_ref.key_ref != maxB.credential_ref.key_ref)

# applying to game_A must not affect game_B
reg.provider_for("game_A", ch).apply_change(ch)
check("C32 game_A MAX recorded the change", maxA.applied_count() == 1)
check("C33 game_B MAX untouched (isolation)", maxB.applied_count() == 0)

# routing via provider_for fills change.provider + credential_ref
ch2 = Change(target="x", change_type=CHANGE_REWARD_FREQUENCY, old=5, new=4,
             game_id="game_A")
p = reg.provider_for("game_A", ch2)
check("C34 provider_for routes to RemoteConfig", p.name == PROVIDER_REMOTE_CONFIG)
check("C35 provider_for fills change.provider", ch2.provider == PROVIDER_REMOTE_CONFIG)
check("C36 provider_for fills credential_ref", ch2.credential_ref is not None)

# --------------------------------------------------------------------------- #
# 8) Rollback reverses old/new
# --------------------------------------------------------------------------- #
rres = maxA.rollback_change(ch)
check("C37 rollback success", rres.success is True)
check("C38 rollback real_api_called False", rres.real_api_called is False)
check("C39 rollback reverses (before=new, after=old)",
      rres.before == 14.4 and rres.after == 12.0)
check("C40 rollback recorded", maxA.rolled_back_count() == 1)

# --------------------------------------------------------------------------- #
# 9) Legacy Change bridge (decoupling-safe)
# --------------------------------------------------------------------------- #
legacy = ch.to_legacy_dict()
check("C41 legacy dict has target/provider/change_type/old/new",
      all(k in legacy for k in ("target", "provider", "change_type", "old", "new")))
back = Change.from_legacy_dict(legacy, game_id="game_X")
check("C42 legacy->Change round-trips change_type",
      back.change_type == CHANGE_BID_FLOOR)
check("C43 legacy->Change preserves old/new",
      back.old == 12.0 and back.new == 14.4)

# --------------------------------------------------------------------------- #
# 10) Registry health_all
# --------------------------------------------------------------------------- #
healths = reg.health_all("game_A")
check("C44 health_all returns one result per provider kind",
      len(healths) == 4)
check("C45 every health result succeeds",
      all(h.success for h in healths))
check("C46 every health result real_api_called False",
      all(h.real_api_called is False for h in healths))

# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def main() -> int:
    print("\n".join(_log))
    print(f"\nE14.3.1 Provider Contract Freeze: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
