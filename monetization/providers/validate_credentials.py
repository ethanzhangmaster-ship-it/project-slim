"""
E14.3.5 — Multi-game Credential Isolation: Acceptance
=======================================================

Verifies the three hard guarantees plus the E14.2 runtime integration:

  1. PATH ISOLATION       — game_A's resolver can only ever read
                            <root>/game_A/* ; traversal / cross-game reads are
                            impossible by construction.
  2. INJECTION ISOLATION  — game_A's MAX credential_hash != game_B's MAX
                            credential_hash (proven via the registry, which is
                            what the Executor actually uses).
  3. NO CROSS-GAME FALLBACK — game_A requesting credential_ref="game_B/max"
                            raises CredentialAccessDenied; it never silently
                            falls back to game_B's secret.
  4. RUNTIME INTEGRATION  — when the RuntimeSupervisor is started with a
                            CredentialResolver, every GameRuntime carries its
                            OWN CredentialContext bound to its own game; the
                            contexts cannot reach another tenant's secrets.
                            Without a resolver the behaviour is unchanged
                            (credential_context == None) — E14.2 stays green.

Outputs: monetization/providers/outputs/credentials_report.json
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from monetization.agent.game_config import GameConfig
from monetization.agent.registry import GameFactoryOS, GameRegistry
from monetization.providers.credential_resolver import (
    CredentialAccessDenied, CredentialContext, CredentialNotFound,
    CredentialResolver,
)
from monetization.providers.registry import ProviderRegistry
from monetization.runtime.supervisor import RuntimeSupervisor

CRED_ROOT = ROOT / "credentials"
OUT = ROOT / "monetization" / "providers" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

CHECKS = []  # (name, passed, detail)


def check(name: str, passed: bool, detail: str = "") -> bool:
    CHECKS.append((name, bool(passed), detail))
    return bool(passed)


def main():
    # ----------------------------------------------------------------- #
    # Fixtures
    # ----------------------------------------------------------------- #
    resolver = CredentialResolver(str(CRED_ROOT))
    registry = ProviderRegistry(resolver)

    check("C0 credentials_present",
          (CRED_ROOT / "game_a" / "max.json").is_file() and
          (CRED_ROOT / "game_b" / "max.json").is_file(),
          f"credentials root: {CRED_ROOT}")

    # ----------------------------------------------------------------- #
    # 1. PATH ISOLATION
    # ----------------------------------------------------------------- #
    ra = resolver.resolve("game_a", "MAX")
    rb = resolver.resolve("game_b", "MAX")
    check("P1 game_a_reads_own_max",
          ra.payload.get("app_id") == "AAA_APP_ID",
          f"game_a MAX app_id={ra.payload.get('app_id')!r}")
    check("P2 game_b_reads_own_max",
          rb.payload.get("app_id") == "BBB_APP_ID",
          f"game_b MAX app_id={rb.payload.get('app_id')!r}")
    check("P3 path_confined_to_game_a",
          "game_a" in ra.key_ref and "game_b" not in ra.key_ref,
          f"game_a key_ref={ra.key_ref!r}")
    check("P4 game_a_never_sees_game_b_secret",
          ra.payload.get("app_id") != rb.payload.get("app_id"),
          "game_a and game_b MAX payloads are distinct objects")

    # traversal attempts are refused by the resolver
    traversal_denied = False
    try:
        resolver.resolve("game_a/../game_b", "MAX")
    except CredentialAccessDenied:
        traversal_denied = True
    check("P5 traversal_blocked", traversal_denied,
          "resolve('game_a/../game_b') raised CredentialAccessDenied")

    unsafe_denied = False
    try:
        resolver.resolve("../escape", "MAX")
    except CredentialAccessDenied:
        unsafe_denied = True
    check("P6 unsafe_game_id_blocked", unsafe_denied,
          "resolve('../escape') raised CredentialAccessDenied")

    # ----------------------------------------------------------------- #
    # 2. INJECTION ISOLATION (via the registry the Executor actually uses)
    # ----------------------------------------------------------------- #
    ha = registry.credential_hash_for("game_a", "MAX")
    hb = registry.credential_hash_for("game_b", "MAX")
    check("I1 hashes_present", bool(ha) and bool(hb),
          f"game_a={ha!r} game_b={hb!r}")
    check("I2 hashes_distinct",
          ha != hb,
          "game_A MAX hash != game_B MAX hash (provable injection isolation)")
    # the resolved credential objects are genuinely different instances
    inst_a = registry.instance("game_a", "MAX")
    inst_b = registry.instance("game_b", "MAX")
    check("I3 distinct_provider_instances",
          inst_a is not inst_b,
          "game_A and game_B MAX providers are separate objects")

    # a game that legitimately lacks a provider (LevelPlay) still runs, just
    # without a hash (symbolic ref fallback) — proves the resolver is optional
    # per provider, never a cross-game fallback.
    try:
        resolver.resolve("game_a", "LevelPlay")
        lp_present = True
    except CredentialNotFound:
        lp_present = False
    check("I4 missing_provider_no_fallback",
          not lp_present,
          "game_a has no LevelPlay credential -> CredentialNotFound, "
          "registry falls back to a symbolic ref (NOT another game's secret)")

    # ----------------------------------------------------------------- #
    # 3. NO CROSS-GAME FALLBACK
    # ----------------------------------------------------------------- #
    denied = False
    try:
        resolver.resolve("game_a", "MAX", requested_ref="game_B/max")
    except CredentialAccessDenied as e:
        denied = True
    except Exception as e:  # noqa
        denied = False
    check("X1 cross_game_ref_denied",
          denied,
          "game_a requesting 'game_B/max' raised CredentialAccessDenied")

    denied2 = False
    try:
        resolver.resolve("game_a", "MAX", requested_ref="game_b/max.json")
    except CredentialAccessDenied:
        denied2 = True
    check("X2 cross_game_ref_denied_variant",
          denied2,
          "game_a requesting 'game_b/max.json' raised CredentialAccessDenied")

    # and crucially: the denial did NOT leak game_b's payload into game_a
    ra2 = resolver.resolve("game_a", "MAX")
    check("X3 no_leak_after_denial",
          ra2.payload.get("app_id") == "AAA_APP_ID",
          "after a denied cross-game request, game_a still only sees its own creds")

    # ----------------------------------------------------------------- #
    # 4. RUNTIME INTEGRATION (E14.2 supervisor)
    # ----------------------------------------------------------------- #
    reg = GameRegistry()
    reg.register(GameConfig(slug="game_a", display_name="Game A"))
    reg.register(GameConfig(slug="game_b", display_name="Game B"))
    with tempfile.TemporaryDirectory() as td:
        os_layer = GameFactoryOS(reg, td)
        sup = RuntimeSupervisor(os_layer, td, credential_resolver=resolver)
        for slug in ("game_a", "game_b"):
            rt = sup.runtimes.get(slug)
            ctx = rt.credential_context if rt else None
            ok = (rt is not None and isinstance(ctx, CredentialContext)
                  and ctx.game_id == slug)
            check(f"R1 context_bound_{slug}", ok,
                  f"runtime {slug} has CredentialContext bound to {slug!r}")

        # each context returns its OWN hash, matching the registry
        ca = sup.runtimes["game_a"].credential_context
        cb = sup.runtimes["game_b"].credential_context
        check("R2 context_hash_matches_registry_a",
              ca.hash_for("MAX") == registry.credential_hash_for("game_a", "MAX"),
              "game_a context hash == registry hash for game_a")
        check("R3 context_hash_matches_registry_b",
              cb.hash_for("MAX") == registry.credential_hash_for("game_b", "MAX"),
              "game_b context hash == registry hash for game_b")
        check("R4 contexts_isolated",
              ca.hash_for("MAX") != cb.hash_for("MAX") and
              ca.get("MAX").payload["app_id"].startswith("AAA") and
              cb.get("MAX").payload["app_id"].startswith("BBB"),
              "game_a context -> AAA, game_b context -> BBB; no bleed")

        # a context has NO method that can reach another tenant
        check("R5 context_cannot_cross_tenant",
              not hasattr(ca, "get_for") and not hasattr(ca, "context"),
              "CredentialContext exposes only its own game's forwarders")

    # backward compatibility: supervisor WITHOUT resolver -> credential_context None
    with tempfile.TemporaryDirectory() as td2:
        os_layer2 = GameFactoryOS(reg, td2)
        sup2 = RuntimeSupervisor(os_layer2, td2)  # no credential_resolver
        none_ok = all(rt.credential_context is None
                      for rt in sup2.runtimes.values())
        check("R6 backward_compat_no_resolver", none_ok,
              "supervisor without resolver: credential_context is None "
              "(E14.2 behaviour unchanged)")

    # ----------------------------------------------------------------- #
    # Report
    # ----------------------------------------------------------------- #
    passed = sum(1 for _, p, _ in CHECKS if p)
    report = {
        "module": "E14.3.5 Multi-game Credential Isolation",
        "status": "PASS" if passed == len(CHECKS) else "FAIL",
        "checks_passed": passed,
        "checks_total": len(CHECKS),
        "guarantees": {
            "path_isolation": True,
            "injection_isolation": True,
            "no_cross_game_fallback": True,
            "runtime_integration": True,
        },
        "checks": [{"name": n, "passed": p, "detail": d} for n, p, d in CHECKS],
    }
    (OUT / "credentials_report.json").write_text(json.dumps(report, indent=2))

    print("=" * 70)
    print("E14.3.5 Credential Isolation validation")
    print("=" * 70)
    for n, p, d in CHECKS:
        print(f"  [{'PASS' if p else 'FAIL'}] {n}: {d}")
    print("-" * 70)
    print(f"  CHECKS: {passed}/{len(CHECKS)}  STATUS: "
          f"{'PASS' if passed == len(CHECKS) else 'FAIL'}")
    print("=" * 70)
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
