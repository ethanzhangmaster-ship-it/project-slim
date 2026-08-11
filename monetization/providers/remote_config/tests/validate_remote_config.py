"""
E14.3.3 — Remote Config Adapter Validation
===========================================

50+ checks proving the Remote Config adapter honours the E14.3.1 frozen
contract and delivers the three experience-side mutations (frequency / cooldown
/ multiplier) across the three sandbox modes, with a retention-safety validator
and multi-game credential isolation.

Run:  python monetization/providers/remote_config/tests/validate_remote_config.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# make launchforge importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from monetization.providers import (
    CredentialRef, Change, MonetizationProvider, ProviderRegistry, SandboxMode,
)
from monetization.providers.models import ProviderResult
from monetization.providers.remote_config import (
    RemoteConfigProvider, ConfigGameState, ConfigMappingError,
    ConfigValidationError, LocalConfigClient, MockConfigClient,
    RemoteConfigOperation, map_change_to_config_op, resolve_key, category_for,
    CONFIG_GENE_MAP, validate_config_op, is_valid, SAFE_BOUNDS,
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
check("R1 RemoteConfigProvider is a MonetizationProvider",
      issubclass(RemoteConfigProvider, MonetizationProvider))
prov = RemoteConfigProvider()
r = prov.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R2 apply_change returns ProviderResult", isinstance(r, ProviderResult))
for k in ("provider", "operation", "success", "latency_ms", "real_api_called"):
    check(f"R3 ProviderResult has {k}", k in r.to_dict(), str(list(r.to_dict().keys())))
rb = prov.rollback_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
h = prov.health_check()
check("R4 real_api_called present on apply/rollback/health",
      all(hasattr(x, "real_api_called") for x in (r, rb, h)))
check("R5 simulation real_api_called False (apply/rollback/health)",
      r.real_api_called is False and rb.real_api_called is False
      and h.real_api_called is False)
check("R6 provider label is RemoteConfig", r.provider == "RemoteConfig")

# --------------------------------------------------------------------------- #
# 2) Frequency mutation (5 -> 4, rollback 4 -> 5)
# --------------------------------------------------------------------------- #
prov = RemoteConfigProvider()
prov._client.state.set("ads.reward_frequency", 5)
res = prov.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R7 frequency 5->4 success", res.success is True)
check("R8 frequency before=5 after=4", res.before == 5 and res.after == 4)
check("R9 client value updated to 4",
      prov._client.get_config("ads.reward_frequency") == 4)
rbk = prov.rollback_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R10 frequency rollback success", rbk.success is True)
check("R11 rollback restores 5",
      prov._client.get_config("ads.reward_frequency") == 5)
check("R12 rollback result before=4 after=5",
      rbk.before == 4 and rbk.after == 5)

# gene alias resolves the same
prov2 = RemoteConfigProvider()
resg = prov2.apply_change(mk("frequency_gene", "reward_frequency", 5, 4))
check("R13 frequency_gene resolves to ads.reward_frequency",
      resg.success is True
      and prov2._client.get_config("ads.reward_frequency") == 4)

# --------------------------------------------------------------------------- #
# 3) Cooldown mutation (30 -> 20)
# --------------------------------------------------------------------------- #
prov = RemoteConfigProvider()
rc = prov.apply_change(mk("ads.reward_cooldown", "remote_param", 30, 20))
check("R14 cooldown 30->20 success", rc.success is True)
check("R15 cooldown before=30 after=20", rc.before == 30 and rc.after == 20)
check("R16 client cooldown updated to 20",
      prov._client.get_config("ads.reward_cooldown") == 20)
# relative delta spec (-10s)
prov_d = RemoteConfigProvider()
rcd = prov_d.apply_change(mk("cooldown_gene", "remote_param", 30, {"delta": -10}))
check("R17 cooldown delta -10 -> 20", rcd.success is True and rcd.after == 20)

# --------------------------------------------------------------------------- #
# 4) Reward multiplier mutation (1.5 -> 2.0)
# --------------------------------------------------------------------------- #
prov = RemoteConfigProvider()
rm = prov.apply_change(mk("ads.reward_multiplier", "remote_param", 1.5, 2.0))
check("R18 multiplier 1.5->2.0 success", rm.success is True)
check("R19 multiplier before=1.5 after=2.0", rm.before == 1.5 and rm.after == 2.0)
check("R20 client multiplier updated to 2.0",
      prov._client.get_config("ads.reward_multiplier") == 2.0)
# multiplier spec: 1.5 * 1.333.. ~ 2.0
prov_m = RemoteConfigProvider()
rmm = prov_m.apply_change(mk("reward_gene", "remote_param", 1.5,
                             {"multiplier": 2.0}))
check("R21 reward_gene multiplier x2 -> 3.0", rmm.success is True and rmm.after == 3.0)

# --------------------------------------------------------------------------- #
# 5) Mapper unit checks (gene -> key)
# --------------------------------------------------------------------------- #
check("R22 resolve_key frequency_gene", resolve_key("frequency_gene") == "ads.reward_frequency")
check("R23 resolve_key cooldown_gene", resolve_key("cooldown_gene") == "ads.reward_cooldown")
check("R24 resolve_key reward_gene", resolve_key("reward_gene") == "ads.reward_multiplier")
check("R25 resolve_key identity dotted key",
      resolve_key("ads.reward_frequency") == "ads.reward_frequency")
op = map_change_to_config_op(mk("frequency_gene", "reward_frequency", 5, 4))
check("R26 map -> UPDATE_CONFIG key + int coerce",
      op.operation == "UPDATE_CONFIG" and op.key == "ads.reward_frequency"
      and op.new_value == 4 and isinstance(op.new_value, int))
check("R27 category_for frequency", category_for("ads.reward_frequency") == "frequency")
try:
    resolve_key("totally_unknown_gene")
    check("R28 unknown gene raises", False)
except ConfigMappingError:
    check("R28 unknown gene raises", True)
try:
    map_change_to_config_op(mk("US_android_reward_applovin_floor", "bid_floor",
                               12.0, 14.4))
    check("R29 non-config change_type raises", False)
except ConfigMappingError:
    check("R29 non-config change_type raises", True)
# missing new value
try:
    map_change_to_config_op(mk("ads.reward_frequency", "reward_frequency", 5, None))
    check("R30 missing new value raises", False)
except ConfigMappingError:
    check("R30 missing new value raises", True)

# --------------------------------------------------------------------------- #
# 6) Safety validator (retention guardrail)
# --------------------------------------------------------------------------- #
check("R31 SAFE_BOUNDS covers frequency/cooldown/multiplier/interval",
      set(SAFE_BOUNDS) == {"frequency", "cooldown", "multiplier", "interval"})
check("R32 frequency=4 valid",
      is_valid(RemoteConfigOperation("UPDATE_CONFIG", "ads.reward_frequency",
               "frequency", 5, 4)))
check("R33 frequency=0 invalid (would spam ads)",
      not is_valid(RemoteConfigOperation("UPDATE_CONFIG", "ads.reward_frequency",
               "frequency", 5, 0)))
check("R34 multiplier=50 invalid (out of bound)",
      not is_valid(RemoteConfigOperation("UPDATE_CONFIG", "ads.reward_multiplier",
               "multiplier", 2.0, 50.0)))
# provider refuses unsafe value as success=False (no exception leak)
prov = RemoteConfigProvider()
prov._client.state.set("ads.reward_frequency", 5)
unsafe = prov.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 0))
check("R35 provider refuses unsafe freq=0 (success=False)", unsafe.success is False)
check("R36 unsafe rejection did NOT mutate client (still 5)",
      prov._client.get_config("ads.reward_frequency") == 5)
check("R37 unsafe rejection error mentions bound",
      "bound" in (unsafe.error or "").lower())

# --------------------------------------------------------------------------- #
# 7) Sandbox three modes
# --------------------------------------------------------------------------- #
# simulation: no real network, but does publish to in-memory state
prov = RemoteConfigProvider()
for i in range(5):
    prov.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R38 simulation: 0 real network calls",
      prov._client.real_network_calls == 0)

# shadow: read-only, no publish
shadow = RemoteConfigProvider(sandbox=SandboxMode.SHADOW)
shadow._client.state.set("ads.reward_frequency", 5)
before_pub = shadow._client.publish_calls
sres = shadow.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R39 shadow: publish_calls == 0", shadow._client.publish_calls == before_pub)
check("R40 shadow: read-only flag + value unchanged",
      sres.shadow_read_only is True
      and shadow._client.get_config("ads.reward_frequency") == 5)
check("R41 shadow: proposed value carried in extra",
      sres.extra.get("proposed") == 4)

# production locked
locked = RemoteConfigProvider(sandbox=SandboxMode.PRODUCTION)
locked._client.state.set("ads.reward_frequency", 5)
lres = locked.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R42 production LOCKED: real_api_called False", lres.real_api_called is False)

# production unlocked
unlocked = RemoteConfigProvider(sandbox=SandboxMode.PRODUCTION)
unlocked._production_locked = False
before_real = unlocked._client.real_network_calls
ures = unlocked.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
check("R43 production UNLOCKED: real_api_called True", ures.real_api_called is True)
check("R44 production UNLOCKED: real_network_calls incremented",
      unlocked._client.real_network_calls == before_real + 1)

# --------------------------------------------------------------------------- #
# 8) Health (E14.2 Runtime)
# --------------------------------------------------------------------------- #
prov = RemoteConfigProvider()
h = prov.health_check()
check("R45 health healthy when cred+api ok", h.extra.get("status") == "healthy")
check("R46 health extra has backend/credential_valid/api_available/config_version",
      all(k in h.extra for k in
          ("backend", "credential_valid", "api_available", "config_version")))
check("R47 health real_api_called False", h.real_api_called is False)
degraded = RemoteConfigProvider()
degraded._client.set_credential_valid(False)
dh = degraded.health_check()
check("R48 degraded when credential invalid",
      dh.extra.get("status") == "degraded" and dh.success is False)

# --------------------------------------------------------------------------- #
# 9) Multi-game credential + state isolation (E14.1 / E14.3.5)
# --------------------------------------------------------------------------- #
credA = CredentialRef(game_id="game_001", provider="RemoteConfig",
                      key_ref="credentials/game_001/remote_config")
credB = CredentialRef(game_id="game_002", provider="RemoteConfig",
                      key_ref="credentials/game_002/remote_config")
provA = RemoteConfigProvider(credential_ref=credA, game_id="game_001")
provB = RemoteConfigProvider(credential_ref=credB, game_id="game_002")
provA._client.state.set("ads.reward_frequency", 5)
provB._client.state.set("ads.reward_frequency", 5)
provA.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4,
                      game="game_001", cred=credA))
check("R49 game_A apply does NOT affect game_B config",
      provB._client.get_config("ads.reward_frequency") == 5
      and provA._client.get_config("ads.reward_frequency") == 4)
check("R50 credential key_ref isolated by game", credA.key_ref != credB.key_ref)
check("R51 isolated client instances", provA._client is not provB._client)

# --------------------------------------------------------------------------- #
# 10) Registry integration (routing lands on RemoteConfig)
# --------------------------------------------------------------------------- #
reg = ProviderRegistry()
reg.register("RemoteConfig",
             lambda sb, cr, _p=RemoteConfigProvider: _p(
                 sandbox=sb, credential_ref=cr,
                 game_id=cr.game_id if cr else None))
rp = reg.instance("game_X", "RemoteConfig")
check("R52 registry returns RemoteConfigProvider",
      isinstance(rp, RemoteConfigProvider) and rp.name == "RemoteConfig")
routed = reg.provider_for("game_X",
        mk("ads.reward_frequency", "reward_frequency", 5, 4, game="game_X"))
check("R53 reward_frequency routes to RemoteConfig provider",
      isinstance(routed, RemoteConfigProvider))
rres = routed.apply_change(
    mk("ads.reward_frequency", "reward_frequency", 5, 4, game="game_X"))
check("R54 registry-routed frequency executes via RemoteConfigProvider",
      rres.success is True)

# --------------------------------------------------------------------------- #
# 11) LocalConfigClient real publish (armed PRODUCTION writes a real file)
# --------------------------------------------------------------------------- #
with tempfile.TemporaryDirectory() as td:
    cfg_path = str(Path(td) / "gamefactory_config.json")
    lp = RemoteConfigProvider(sandbox=SandboxMode.PRODUCTION, game_id="game_local")
    lp.arm_local_client(cfg_path)
    lp._production_locked = False
    lp._client.state.set("ads.reward_frequency", 5)
    lres = lp.apply_change(mk("ads.reward_frequency", "reward_frequency", 5, 4))
    check("R55 local client armed publish success + real",
          lres.success is True and lres.real_api_called is True)
    check("R56 gamefactory_config.json written to disk",
          Path(cfg_path).exists())
    import json as _json
    data = _json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    check("R57 published file carries ads.reward_frequency=4",
          data.get("values", {}).get("ads.reward_frequency") == 4)


# --------------------------------------------------------------------------- #
def main() -> int:
    print("\n".join(_log))
    print(f"\nE14.3.3 Remote Config Adapter: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
